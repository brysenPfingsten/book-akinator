# backend/app/tasks.py
import time

from app.celeryconfig import celery_app
from celery import chain
import os
from uuid import uuid4
from app.workers.stt_worker import transcribe_audio_file
from app.workers.llm_worker import query_llm_for_book
from app.workers.tts_worker import synthesize_speech
from app.job_store import *
from fastapi import HTTPException

# Directory where uploaded audio files are stored
UPLOAD_DIR = '/data/audio/uploads'
DATA_DIR = os.getenv('DATA_DIR', '/data')

@celery_app.task(bind=True)
def process_audio_job(self, job_id: str, filename: str):
    """
    Phase 1: Transcribe and make first guess.
    """
    filepath = os.path.join(UPLOAD_DIR, filename)
    workflow = chain(
        transcribe_audio.s(job_id, filepath),
        guess_book.s()
    )
    result = workflow.apply_async()

    return {'workflow_id': result.id, 'job_id': job_id}

@celery_app.task(bind=True)
def transcribe_audio(self, job_id: str, filepath: str) -> dict:
    """Run speech-to-text on the uploaded audio file."""
    transcript = transcribe_audio_file(filepath)

    # Load the existing job so we can preserve existing history
    job = get_job(job_id)
    history = job.get('history', [])

    # Add the user's transcript to history
    history.append({"role": "user", "content": transcript})

    # Update the job
    update_job(job_id, {
        'transcription': transcript,
        'history': history,
        'phase': 'transcribed'
    })
    return {'job_id': job_id, 'transcription': transcript}


@celery_app.task(bind=True)
def guess_book(self, previous_result: dict) -> dict:
    job_id = previous_result["job_id"]
    job    = get_job(job_id)
    history = job.get("history", [])

    # This returns a dict like {"status":"need_clarification","question": "..."}
    guess_obj = query_llm_for_book(history)

    # Turn that into a string for the assistant message
    if guess_obj.get("status") == "need_clarification":
        assistant_content = guess_obj["question"]
    elif guess_obj.get("status") == "confident":
        assistant_content = f"\"{guess_obj['title']}\" by {guess_obj['author']}"
        update_job(job_id, {
            "title": guess_obj["title"],
            "author": guess_obj["author"]
        })
    else:
        assistant_content = str(guess_obj)

    # Append a proper string message
    history.append({
      "role": "assistant",
      "content": assistant_content
    })

    # Save both the raw object and the updated history
    update_job(job_id, {
      "guess":   guess_obj,
      "history": history,
      "phase":   "guessed"
    })

    return {"job_id": job_id, "guess": guess_obj}


@celery_app.task(bind=True)
def download_book_task(self, job_id: str):
    """
    Phase 1: Transcribe and make first guess.
    """
    job = get_job(job_id)
    workflow = chain(
        download_list_task.s(job.get('title'), job.get('author'), job_id),
        actually_download_book.s(),
        convert_book_task.s()
    )
    result = workflow.apply_async()

    return {'workflow_id': result.id, 'job_id': job_id}

@celery_app.task(bind=True)
def download_list_task(self, title: str, author: str, job_id: str):
    job = get_job(job_id)
    from app.workers.irc_worker import download_list
    path = download_list(title, author, job_id)
    print(f"[DEBUG] List downloaded to {path}")
    update_job(job_id, {
        "phase": "downloaded_list",
        "list": path,
    })
    return {'path': path, 'job_id': job_id}

@celery_app.task(bind=True)
def actually_download_book(self, prev: dict) -> dict:
    """Fetch the guessed book via IRC."""
    job_id: str = prev.get('job_id')
    list_path: str = prev.get('path')
    update_job(job_id, {
        "phase": "downloading_book"
    })
    from app.workers.select_worker import parse_and_sort
    query: str = parse_and_sort(list_path)[0]['original_line']
    from app.workers.irc_worker import download_book
    path = download_book(query, job_id)
    print(f"[DEBUG] Book downloaded to {path}")
    update_job(job_id, {
        "phase": "downloaded_book",
        "ebook_path": path
    })
    return {'job_id': job_id, 'ebook_path': path}

@celery_app.task(bind=True)
def convert_book_task(self, prev: dict):
    """Convert the downloaded book to txt files"""
    job_id: str = prev.get('job_id')
    ebook_path: str = prev.get('ebook_path')
    update_job(job_id, {
        "phase": "converting_book"
    })
    from app.workers.convert_worker import convert_ebook
    convert_ebook(ebook_path, f'/data/books/{job_id}/parsed')
    update_job(job_id, {
        "phase": "converted_book"
    })
    return {'job_id': job_id}

@celery_app.task(bind=True)
def speak_text(self, previous_result: dict) -> dict:
    """Synthesize speech from extracted text."""
    job_id = previous_result.get('job_id')
    text_path = previous_result.get('text_path')
    audio_path = synthesize_speech(text_path, DATA_DIR)
    return {'job_id': job_id, 'audio_path': audio_path}
