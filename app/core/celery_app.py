# app/core/celery_app.py

import os
from celery import Celery
from kombu import Queue
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = os.getenv("REDIS_DB", "0")

# Build Redis URL
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Create Celery instance
celery_app = Celery(
    "wedding_app",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks.email_tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Queue configuration
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="task.#"),
        Queue("emails", routing_key="email.#"),
        Queue("notifications", routing_key="notification.#"),
    ),
    task_routes={
        "app.tasks.email_tasks.*": {"queue": "emails"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
    },

    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Beat schedule (if needed for periodic tasks)
    beat_schedule={},

    # Error handling
    task_annotations={
        "*": {"rate_limit": "100/m"},  # Global rate limit
        "app.tasks.email_tasks.send_email_notification": {"rate_limit": "30/m"},  # Email-specific rate limit
    }
)

if __name__ == "__main__":
    celery_app.start()