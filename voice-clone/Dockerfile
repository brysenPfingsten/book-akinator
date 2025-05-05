FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg espeak libsndfile1 \
    gcc g++ build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install TTS and Flask
RUN pip install --upgrade pip \
    && pip install TTS flask

# Create output and voice sample dirs
RUN mkdir -p /app/output /app/voice_samples

# Copy server script
COPY app/server.py /app/server.py

EXPOSE 5002

CMD ["python", "server.py"]
