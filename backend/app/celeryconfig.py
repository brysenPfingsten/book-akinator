from celery import Celery
import os

# Configure Celery to use Redis (defaults match docker-compose)
celery_app = Celery(
    "book_akinator",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
)

# Optional: customize task routes or serialization
celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
)