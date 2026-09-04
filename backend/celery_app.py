"""
RiskShield AI - Celery Asynchronous Task Queue Application
Configured with Redis broker & result backend for background task execution.
"""

import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "riskshield",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["backend.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    broker_connection_retry_on_startup=True
)

def get_celery_telemetry() -> dict:
    """
    Retrieves status of Celery workers and inspects active queues.
    Returns graceful fallback telemetry if workers are not reachable.
    """
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        ping_res = inspect.ping() if inspect else None
        if ping_res:
            active_workers = list(ping_res.keys())
            active_tasks = inspect.active() or {}
            reserved_tasks = inspect.reserved() or {}

            total_active = sum(len(v) for v in active_tasks.values())
            total_reserved = sum(len(v) for v in reserved_tasks.values())

            return {
                "status": "ONLINE",
                "available": True,
                "worker_count": len(active_workers),
                "workers": active_workers,
                "active_tasks_count": total_active,
                "reserved_tasks_count": total_reserved,
                "broker_url": BROKER_URL,
                "result_backend": RESULT_BACKEND
            }
    except Exception as e:
        logger.debug("Celery worker telemetry check: %s", str(e))

    return {
        "status": "OFFLINE",
        "available": False,
        "mode": "Synchronous Fallback (Inline API Execution)",
        "worker_count": 0,
        "broker_url": BROKER_URL,
        "result_backend": RESULT_BACKEND
    }
