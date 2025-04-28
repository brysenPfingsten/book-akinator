# Use a slim Python image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps for some libraries (adjust as needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libsndfile1 \
        ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /usr/src/app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose the FastAPI port
EXPOSE 8000

# Default to running Uvicorn; override in docker-compose for workers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
