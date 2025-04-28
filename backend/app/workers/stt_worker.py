# backend/app/stt_worker.py
import os, subprocess
from openai import OpenAI, Audio


def convert_webm_to_wav(input_path: str) -> str:
    output_path = input_path.replace(".webm", ".wav")
    command = [
        "ffmpeg", "-i", input_path,
        "-ar", "16000",  # 16kHz, recommended for Whisper
        "-ac", "1",      # mono channel
        output_path
    ]
    subprocess.run(command, check=True)
    return output_path



def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribe audio using OpenAI's Whisper-like model via the OpenAI Python SDK.
    Returns the transcript text.
    """
    # Initialize client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable!")

    client = OpenAI(api_key=api_key)

    if file_path.endswith(".webm"):
        file_path = convert_webm_to_wav(file_path)

    # Read the audio file and send for transcription
    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )

    return transcription.text.strip()
