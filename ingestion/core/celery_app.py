"""
Celery application factory.

Each worker container invokes :func:`create_celery_app` to obtain a Celery
instance configured for the async ingestion pipeline. Using a factory function
avoids cross-import issues and allows per-container customization later.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

import os

from ingestion.config import Settings
from ingestion.core.health_server import start_health_server


def create_celery_app(*, settings: Settings | None = None) -> Celery:
    cfg = settings or Settings()
    app = Celery(
        "ttrpg_ingestion",
        broker=cfg.broker_url,
        backend=cfg.result_backend,
        include=[
            "ingestion.workers.source_sentinel.tasks",
            "ingestion.workers.unstructured.tasks",
            "ingestion.workers.ingestion_engine.tasks",
            "ingestion.workers.haystack.tasks",
            "ingestion.workers.llamaindex.tasks",
            "ingestion.workers.cassandra_upsert.tasks",
            "ingestion.workers.graph_upsert.tasks",
            "ingestion.workers.housekeeping.tasks",
            "ingestion.workers.health_verifier.tasks",
            "ingestion.workers.dlq.tasks",
        ],
    )

    app.conf.update(
        task_queues=[Queue(name) for name in cfg.task_queues],
        task_default_queue="ingestion_engine",
        worker_prefetch_multiplier=cfg.worker_prefetch_multiplier,
        task_soft_time_limit=cfg.task_soft_time_limit,
        task_time_limit=cfg.task_hard_time_limit,
        task_acks_late=True,
        task_default_retry_delay=cfg.retry_initial_wait,
        task_annotations={
            "*": {
                "autoretry_for": (Exception,),
                "retry_kwargs": {"max_retries": cfg.retry_max_retries},
                "retry_backoff": cfg.retry_backoff,
                "retry_backoff_max": cfg.retry_max_wait,
                "retry_jitter": cfg.retry_jitter,
            }
        },
        timezone="UTC",
    )

    start_health_server(os.getenv("CELERY_QUEUE", "ingestion_engine"), app, cfg)

    app.conf.beat_schedule = {
        "source-scan": {
            "task": "source_sentinel.scan",
            "schedule": cfg.source_scan_interval,
        },
        "nightly-health": {
            "task": "health_verifier.verify",
            "schedule": crontab(hour=2, minute=0),
        },
        "nightly-artifact-cleanup": {
            "task": "housekeeping.cleanup_old_artifacts",
            "schedule": crontab(hour=3, minute=0),
        },
        "daily-full-pipeline": {
            "task": "source_sentinel.scan",
            "schedule": crontab(hour=2, minute=0),
        },
    }

    return app

