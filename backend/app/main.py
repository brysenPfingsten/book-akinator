import subprocess
import uuid
from uuid import uuid4

import requests
from fastapi import FastAPI, Response, Request
from fastapi import UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import spacy
from spacy.cli import download

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("[INFO] Downloading spaCy model: en_core_web_sm")
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

from starlette.staticfiles import StaticFiles
from app.tasks import process_audio_job, download_book_task
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
BOOKS_DIR = "/data/books"
if os.path.exists(BOOKS_DIR):
    app.mount("/ebooks", StaticFiles(directory=BOOKS_DIR), name="ebooks")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.exception_handler(Exception)
async def catch_all_exceptions(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "An unexpected error occurred"},
    )


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


class TTSRequest(BaseModel):
    text: str
    split: bool = False

SPEAKER_WAV = "app/voice_samples/your_sample.wav"
MODEL_NAME = "tts_models/multilingual/multi-dataset/your_tts"

def split_sentences(text: str) -> list[str]:
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents]

VOICE_CLONE_URL = "http://voice-clone:5002/speak"  # Docker internal hostname

@app.post("/speak")
async def speak(req: TTSRequest):
    if not req.text:
        return JSONResponse(status_code=400, content={"error": "Missing 'text'"})

    if req.split:
        sentences = split_sentences(req.text)
        return {"sentences": sentences}

    try:
        response = requests.post(
            VOICE_CLONE_URL,
            json={"text": req.text}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Voice synthesis failed: " + response.text)
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error contacting voice service: {str(e)}")

    return Response(
        content=response.content,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=output.wav"}
    )


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