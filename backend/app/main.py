from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult
from uuid import uuid4
import os

from app.celeryconfig import celery_app
from app.tasks import process_audio_job
from app.job_store import *

# FastAPI app
app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)

# Directories (ensure these match your Docker volumes)
UPLOAD_DIR = '/data/audio/uploads' # os.getenv('UPLOAD_DIR', '/data/audio/uploads')
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
    save_job(job_id, {
        'status': 'pending',
        'task_id': async_result.id,
        'result': None,
        'transcription': None
    })

    return JSONResponse({
        'job_id': job_id,
        'status_url': f"/status/{job_id}"
    })

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = get_job(job_id)
    print(f"[DEBUG] {job}")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    task_id = job['task_id']
    async_res = AsyncResult(task_id, app=celery_app)
    state = async_res.state

    if state == 'SUCCESS':
        if not job.get('result'):
            result = async_res.result or {}
            job['result'] = result
        job['status'] = 'completed'
    elif state in ('PENDING', 'STARTED', 'RETRY'):
        job['status'] = 'pending'
    else:
        job['status'] = 'failed'

    response = {
        'job_id': job_id,
        'status': job['status']
    }

    if 'result' in job and job['result']:
        response['result'] = job['result']

    if 'transcription' in job and job['transcription']:
        response['transcription'] = job['transcription']

    print(f"[DEBUG] /status/{job_id} response: {response}")
    return JSONResponse(response)

