from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from uuid import uuid4
import os

from celeryconfig import celery_app
from tasks import process_audio_job

# FastAPI app
app = FastAPI()

# In-memory job store for mapping job_id -> task info
jobs = {}

# Directories (ensure these match your Docker volumes)
UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/data/uploads')
# Create upload dir if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/recognize")
async def recognize_audio(file: UploadFile = File(...)):
    # 1. Generate a unique job ID
    job_id = str(uuid4())
    # 2. Derive a filename and save the file
    extension = os.path.splitext(file.filename)[1] or '.webm'
    filename = f"{job_id}{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    contents = await file.read()
    with open(file_path, 'wb') as f:
        f.write(contents)

    # 3. Enqueue background Celery workflow
    async_result = process_audio_job.delay(job_id, filename)

    # 4. Store job metadata
    jobs[job_id] = {
        'status': 'pending',
        'task_id': async_result.id,
        'result': None
    }

    return JSONResponse({
        'job_id': job_id,
        'status_url': f"/status/{job_id}"
    })

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # 1. Fetch latest task state from Celery
    task_id = job['task_id']
    async_res = AsyncResult(task_id, app=celery_app)
    state = async_res.state

    # 2. If finished, attach result
    if state == 'SUCCESS':
        result = async_res.result or {}
        job['status'] = 'completed'
        job['result'] = result
    elif state in ('PENDING', 'STARTED', 'RETRY'):
        job['status'] = 'pending'
    else:
        job['status'] = 'failed'

    response = {
        'job_id': job_id,
        'status': job['status'],
    }
    if job['result']:
        response['result'] = job['result']

    return JSONResponse(response)
