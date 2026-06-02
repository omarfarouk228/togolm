"""
Celery application for TogoLM background tasks.

Configure brokers via .env:
    CELERY_BROKER_URL=redis://localhost:6379/0
    CELERY_RESULT_BACKEND=redis://localhost:6379/1

Start worker (from project root):
    celery -A corpus.celery_app worker --loglevel=info

Start beat scheduler (from project root):
    celery -A corpus.celery_app beat --loglevel=info

Or both together (dev only):
    celery -A corpus.celery_app worker --beat --loglevel=info
"""

import os
from pathlib import Path

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = Celery(
    "togolm",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=["corpus.tasks"],
)

app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="Africa/Lome",
    enable_utc=True,
    # Beat schedule — incremental weekly scraping
    beat_schedule={
        # Run all spiders every Sunday at 2:00 AM Lomé time
        "weekly-full-scrape": {
            "task": "corpus.tasks.run_all_spiders",
            "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
            "kwargs": {"embed": True},
        },
        # Run just the news spiders daily at 6:00 AM (press sources update frequently)
        "daily-news-scrape": {
            "task": "corpus.tasks.run_news_spiders",
            "schedule": crontab(hour=6, minute=0),
            "kwargs": {"embed": False},  # Embeddings done in weekly batch
        },
    },
    # Prevent tasks from running simultaneously on the same worker
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
