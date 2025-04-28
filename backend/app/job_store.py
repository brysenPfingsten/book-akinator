# app/job_store.py
from typing import Any

import redis
import json
import os

# Connect to Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=2
)

def save_job(job_id: str, data: dict):
    redis_client.set(job_id, json.dumps(data))

def get_job(job_id: str) -> Any | None:
    job_data = redis_client.get(job_id)
    if job_data:
        return json.loads(job_data)
    return None

def update_job(job_id: str, update: dict):
    job = get_job(job_id) or {}
    job.update(update)
    save_job(job_id, job)
