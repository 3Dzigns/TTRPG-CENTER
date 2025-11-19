"""
Prometheus metrics helpers for task instrumentation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from ingestion.config import Settings

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Histogram, start_http_server
except Exception:  # pragma: no cover - fall back to no-op metrics
    Counter = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    start_http_server = None  # type: ignore[assignment]

_LOG = logging.getLogger(__name__)
_METRICS: "_MetricsRecorder" | None = None
_SERVER_STARTED = False


def _ensure_server(settings: Settings) -> None:
    global _SERVER_STARTED
    if (
        _SERVER_STARTED
        or start_http_server is None
        or not settings.enable_metrics
        or settings.metrics_port <= 0
    ):
        return
    try:
        start_http_server(settings.metrics_port, addr=settings.metrics_host)
        _SERVER_STARTED = True
        _LOG.info(
            "Prometheus metrics server started",
            extra={"host": settings.metrics_host, "port": settings.metrics_port},
        )
    except Exception as exc:  # pragma: no cover - best effort
        _LOG.warning("Failed to start Prometheus server: %s", exc)
        _SERVER_STARTED = True  # Avoid repeated attempts


@dataclass(slots=True)
class _MetricsRecorder:
    enabled: bool
    task_started: Counter | None
    task_succeeded: Counter | None
    task_failed: Counter | None
    task_retried: Counter | None
    task_duration: Histogram | None

    def task_started_inc(self, labels: Dict[str, str]) -> None:
        if self.enabled and self.task_started is not None:
            self.task_started.labels(**labels).inc()

    def task_succeeded_inc(self, labels: Dict[str, str]) -> None:
        if self.enabled and self.task_succeeded is not None:
            self.task_succeeded.labels(**labels).inc()

    def task_failed_inc(self, labels: Dict[str, str]) -> None:
        if self.enabled and self.task_failed is not None:
            self.task_failed.labels(**labels).inc()

    def task_retried_inc(self, labels: Dict[str, str]) -> None:
        if self.enabled and self.task_retried is not None:
            self.task_retried.labels(**labels).inc()

    def task_duration_observe(self, labels: Dict[str, str], value: float) -> None:
        if self.enabled and self.task_duration is not None:
            self.task_duration.labels(**labels).observe(value)


class _NoOpMetricsRecorder(_MetricsRecorder):
    def __init__(self) -> None:
        super().__init__(False, None, None, None, None, None)

    def task_started_inc(self, labels: Dict[str, str]) -> None:  # pragma: no cover - trivial
        return

    task_succeeded_inc = task_failed_inc = task_retried_inc = task_started_inc

    def task_duration_observe(self, labels: Dict[str, str], value: float) -> None:
        return


def _build_metrics(settings: Settings) -> _MetricsRecorder:
    if (
        not settings.enable_metrics
        or Counter is None
        or Histogram is None
    ):
        return _NoOpMetricsRecorder()

    task_started = Counter(
        "pipeline_task_started_total",
        "Total number of pipeline tasks started",
        ("task_name", "queue"),
    )
    task_succeeded = Counter(
        "pipeline_task_succeeded_total",
        "Total number of pipeline tasks succeeded",
        ("task_name", "queue"),
    )
    task_failed = Counter(
        "pipeline_task_failed_total",
        "Total number of pipeline tasks failed",
        ("task_name", "queue"),
    )
    task_retried = Counter(
        "pipeline_retries_total",
        "Total number of task retries",
        ("task_name", "queue"),
    )
    task_duration = Histogram(
        "pipeline_task_duration_seconds",
        "Pipeline task execution duration",
        ("task_name", "queue"),
        buckets=(
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
            30.0,
            60.0,
            float("inf"),
        ),
    )
    _ensure_server(settings)
    return _MetricsRecorder(
        True,
        task_started,
        task_succeeded,
        task_failed,
        task_retried,
        task_duration,
    )


def get_metrics(settings: Settings | None = None) -> _MetricsRecorder:
    global _METRICS
    if _METRICS is not None:
        return _METRICS
    settings = settings or Settings()
    _METRICS = _build_metrics(settings)
    return _METRICS


__all__ = ["get_metrics"]

