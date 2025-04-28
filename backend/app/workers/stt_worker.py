# backend/app/stt_worker.py
import os
from openai import OpenAI, Audio


def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribe audio using OpenAI's Whisper-like model via the OpenAI Python SDK.
    Returns the transcript text.
    """
    # Initialize client
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )

    # Read the audio file and send for transcription
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )

    return transcription.text.strip()
