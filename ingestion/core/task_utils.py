"""
Shared task helper with Celery fallback.
"""

from __future__ import annotations

try:
    from celery import shared_task as celery_shared_task
    from ingestion.core.tasks import BaseTask

    def shared_task(*dargs, **dkwargs):
        if "base" not in dkwargs:
            dkwargs["base"] = BaseTask
        return celery_shared_task(*dargs, **dkwargs)

except ImportError:  # pragma: no cover - Celery not available

    def shared_task(*dargs, **dkwargs):  # type: ignore
        def decorator(func):
            return func

        return decorator

__all__ = ["shared_task"]
