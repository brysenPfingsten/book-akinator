# backend/app/tasks.py
import time

from app.celeryconfig import celery_app
from celery import chain
import os
from uuid import uuid4
from app.workers.stt_worker import transcribe_audio_file
from app.workers.llm_worker import query_llm_for_book
from app.workers.irc_worker import fetch_book_via_irc
from app.workers.convert_worker import extract_text_from_ebook
from app.workers.tts_worker import synthesize_speech
from app.job_store import *
from fastapi import HTTPException

# Directory where uploaded audio files are stored
UPLOAD_DIR = '/data/audio/uploads'
DATA_DIR = os.getenv('DATA_DIR', '/data')

@celery_app.task(bind=True)
def process_audio_job(self, job_id: str, filename: str):
    """
    Orchestrator task: transcribe -> guess -> download -> convert -> speak
    """
    filepath = os.path.join(UPLOAD_DIR, filename)
    # Build pipeline
    workflow = chain(
        transcribe_audio.s(job_id, filepath),
        guess_book.s(),
        download_book.s(),
        convert_book.s(),
        speak_text.s()
    )
    result = workflow.apply_async()
    return {'workflow_id': result.id, 'job_id': job_id}


@celery_app.task(bind=True)
def transcribe_audio(self, job_id: str, filepath: str) -> dict:
    transcript = transcribe_audio_file(filepath)
    update_job(job_id, {'transcription': transcript})
    return {'job_id': job_id, 'transcription': transcript}


@celery_app.task(bind=True)
def guess_book(self, previous_result: dict) -> dict:
    """Call LLM to guess the book title from transcript."""
    job_id = previous_result.get('job_id')
    transcript = previous_result.get('transcript')
    book_info = query_llm_for_book(transcript)
    return {'job_id': job_id, 'book_info': book_info}

@celery_app.task(bind=True)
def download_book(self, previous_result: dict) -> dict:
    """Fetch the guessed book via IRC."""
    job_id = previous_result.get('job_id')
    book_info = previous_result.get('book_info')
    ebook_path = fetch_book_via_irc(book_info, DATA_DIR)
    return {'job_id': job_id, 'ebook_path': ebook_path}

@celery_app.task(bind=True)
def convert_book(self, previous_result: dict) -> dict:
    """Convert eBook file to plain text."""
    job_id = previous_result.get('job_id')
    ebook_path = previous_result.get('ebook_path')
    text_path = extract_text_from_ebook(ebook_path, DATA_DIR)
    return {'job_id': job_id, 'text_path': text_path}

@celery_app.task(bind=True)
def speak_text(self, previous_result: dict) -> dict:
    """Synthesize speech from extracted text."""
    job_id = previous_result.get('job_id')
    text_path = previous_result.get('text_path')
    audio_path = synthesize_speech(text_path, DATA_DIR)
    return {'job_id': job_id, 'audio_path': audio_path}
