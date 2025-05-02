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
def continue_book_pipeline(self, job_id: str):
    """
    Phase 2: After confident guess, download and speak the book.
    """
    workflow = chain(
        download_book.s({'job_id': job_id}),
        convert_book.s(),
        speak_text.s()
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
def download_list_task(self, title: str, author: str, job_id: str):
    job = get_job(job_id)
    from app.workers.irc_worker import download_list
    path = download_list(title, author, job_id)
    print(f"[DEBUG] List downloaded to {path}")
    update_job(job_id, {
        "phase": "downloaded_list",
        "list": path,
    })
    return path

@celery_app.task(bind=True)
def download_book(self, previous_result: dict) -> dict:
    """Fetch the guessed book via IRC."""
    job_id = previous_result.get('job_id')
    query = previous_result.get('query')
    from app.workers.irc_worker import download_book
    path = download_book(query, job_id)
    print(f"[DEBUG] Book downloaded to {path}")
    update_job(job_id, {
        "phase": "downloaded_book",
        "ebook_path": path
    })
    return {'job_id': job_id, 'ebook_path': path}

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
