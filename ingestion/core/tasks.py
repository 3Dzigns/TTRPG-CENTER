"""
Celery task base classes and helpers.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable

from celery import Task

from ingestion.config import Settings
from ingestion.core.metrics import get_metrics
from ingestion.core.job_registry import JobRegistry
from ingestion.core.tracing import (
    attach_trace_context,
    detach_trace_context,
    send_task_with_tracing,
    get_current_trace_ids,
)

_LOG = logging.getLogger(__name__)


class BaseTask(Task):
    """Common task configuration with automatic retries, DLQ forwarding, and metrics."""

    abstract = True

    _settings = Settings()

    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": _settings.retry_max_retries}
    retry_backoff = _settings.retry_backoff
    retry_backoff_max = _settings.retry_max_wait
    retry_jitter = _settings.retry_jitter

    def __call__(self, *args, **kwargs):
        token = attach_trace_context(getattr(self.request, "headers", None))
        metrics = get_metrics(self._settings)
        labels = self._metric_labels()
        metrics.task_started_inc(labels)
        start = time.perf_counter()
        try:
            result = super().__call__(*args, **kwargs)
        except Exception:
            metrics.task_failed_inc(labels)
            raise
        else:
            metrics.task_succeeded_inc(labels)
            return result
        finally:
            metrics.task_duration_observe(labels, time.perf_counter() - start)
            detach_trace_context(token)

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: Iterable[Any],
        kwargs: Dict[str, Any],
        einfo,
    ) -> None:
        metrics = get_metrics(self._settings)
        metrics.task_retried_inc(self._metric_labels())
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: Iterable[Any],
        kwargs: Dict[str, Any],
        einfo,
    ) -> None:
        job_id = None
        for arg in args:
            if isinstance(arg, str):
                job_id = arg
                break
        try:
            retries = getattr(self.request, "retries", 0)
        except Exception:  # pragma: no cover - defensive
            retries = 0

        max_retries = self.retry_kwargs.get("max_retries", self.max_retries or 0)
        if retries >= max_retries:
            trace_id, span_id = get_current_trace_ids()
            payload = {
                "task": self.name,
                "task_id": task_id,
                "job_id": job_id,
                "args": list(args),
                "kwargs": kwargs,
                "exception": repr(exc),
                "message": str(exc),
                "retries": retries,
                "max_retries": max_retries,
                "trace_id": trace_id,
                "span_id": span_id,
            }
            try:
                send_task_with_tracing(self.app, "dlq.record_failure", args=[payload], queue="dlq")
            except Exception as dlq_exc:  # pragma: no cover - avoid crash
                _LOG.warning("Failed to publish DLQ entry: %s", dlq_exc)

        if job_id:
            try:
                registry = JobRegistry.global_instance()
                record = registry.get(job_id)
                if record:
                    # Surface the latest error in the status snapshot so operators do not need to parse logs.
                    from ingestion.core.status import write_status_snapshot

                    write_status_snapshot(record, registry.settings, last_error=str(exc))
            except Exception:  # pragma: no cover - best effort
                _LOG.debug("Failed to update status snapshot on failure", exc_info=True)

        super().on_failure(exc, task_id, args, kwargs, einfo)

    def _metric_labels(self) -> Dict[str, str]:
        queue = "unknown"
        try:
            delivery = getattr(self.request, "delivery_info", None)
            if isinstance(delivery, dict):
                queue = delivery.get("routing_key") or queue
        except Exception:  # pragma: no cover - defensive
            queue = "unknown"
        return {"task_name": self.name or self.__class__.__name__, "queue": queue}


__all__ = ["BaseTask"]
