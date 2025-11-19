"""Celery application entrypoint for worker processes."""

from __future__ import annotations

from ingestion.core.celery_app import create_celery_app

app = create_celery_app()

__all__ = ["app"]
