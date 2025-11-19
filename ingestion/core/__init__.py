"""Core utilities shared across workers."""

from .job_registry import JobRegistry, JobState, new_record
from .pipeline import kickoff_ingestion, deterministic_job_id

try:  # Celery might be absent in minimal environments (e.g., unit tests)
    from .celery_app import create_celery_app
except ImportError:  # pragma: no cover - optional dependency during scaffold
    create_celery_app = None  # type: ignore[assignment]

__all__ = [
    "create_celery_app",
    "JobRegistry",
    "JobState",
    "new_record",
    "kickoff_ingestion",
    "deterministic_job_id",
]
