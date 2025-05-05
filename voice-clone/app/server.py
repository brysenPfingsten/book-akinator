# app/server.py
from flask import Flask, request, send_file, jsonify
import subprocess
import os
import uuid

app = Flask(__name__)
SPEAKER_WAV = "app/voice_samples/your_sample.wav"
MODEL_NAME = "tts_models/multilingual/multi-dataset/your_tts"

@app.route("/speak", methods=["POST"])
def speak():
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "Missing 'text' field"}), 400

    text = data["text"]
    output_path = f"output/{uuid.uuid4().hex}.wav"

    try:
        subprocess.run([
            "tts",
            "--model_name", MODEL_NAME,
            "--language_idx=en",
            "--text", text,
            "--speaker_wav", SPEAKER_WAV,
            "--out_path", output_path
        ], check=True)
    except subprocess.CalledProcessError:
        return jsonify({"error": "Synthesis failed"}), 500

    return send_file(output_path, mimetype="audio/wav")

@app.route("/")
def health():
    return "Voice clone API is running."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
