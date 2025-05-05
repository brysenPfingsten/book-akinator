from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult
from uuid import uuid4
import os

from app.celeryconfig import celery_app
from app.tasks import process_audio_job, download_list_task, download_book_task
from app.job_store import *

# FastAPI app
app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)

# Directories
UPLOAD_DIR = '/data/audio/uploads' # os.getenv('UPLOAD_DIR', '/data/audio/uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/health")
def health_check():
    return {"status": "ok"}


async def save_and_process_audio(file: UploadFile, job_id: str = None, is_clarification: bool = False):
    """Common function to handle audio upload and processing"""
    job_id = job_id or str(uuid4())

    # Generate unique filename for clarifications
    if is_clarification:
        unique_id = f"{job_id}_clarification_{uuid4().hex[:8]}"
    else:
        unique_id = job_id

    extension = os.path.splitext(file.filename)[1] or '.webm'
    filename = f"{unique_id}{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        contents = await file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)

        # Verify the file is not empty
        if os.path.getsize(file_path) == 0:
            raise HTTPException(status_code=400, detail="Empty audio file")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save audio file: {str(e)}"
        )

    # Enqueue processing
    async_result = process_audio_job.delay(job_id, filename)

    if is_clarification:
        update_job(job_id, {
            'phase': 'pending',
            'task_id': async_result.id,
        })
    else:
        save_job(job_id, {
            'phase': 'pending',
            'task_id': async_result.id,
            'result': None,
            'transcription': None,
            'history': [],
        })

    return job_id


@app.post("/recognize")
async def recognize_audio(file: UploadFile = File(...)):
    """Endpoint for initial audio recognition"""
    try:
        job_id = await save_and_process_audio(file)
        return JSONResponse({
            'job_id': job_id,
            'status_url': f"/status/{job_id}"
        })
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Audio processing failed: {str(e)}"
        )


@app.post("/answer_clarification/{job_id}")
async def answer_clarification(job_id: str, file: UploadFile = File(...)):
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        await save_and_process_audio(file, job_id, is_clarification=True)
        return JSONResponse({'job_id': job_id, 'status_url': f"/status/{job_id}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download_book/{job_id}")
async def download_book(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async_result = download_book_task.delay(job_id)

    update_job(job_id, {
        'phase': 'downloading_list',
        'task_id': async_result.id
    })

    return JSONResponse({
        'job_id': job_id,
        'status_url': f"/status/{job_id}"
    })
@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = {
        'job_id': job_id,
        'phase': job.get('phase', 'unknown'),
        'transcription': job.get('transcription', ''),
        'guess': job.get('guess', ''),
        'list': job.get('list', ''),
        'ebook_path': job.get('ebook_path', ''),
    }

    return JSONResponse(response)