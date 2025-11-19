"""
OpenTelemetry tracing helpers with graceful fallbacks.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Dict, Iterator, Optional, Tuple

from ingestion.config import Settings

_LOG = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace
    from opentelemetry.trace import Tracer, Span
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.context import attach, detach
except Exception:  # pragma: no cover - tracing optional
    trace = None  # type: ignore[assignment]
    Tracer = None  # type: ignore[assignment]
    TraceContextTextMapPropagator = None  # type: ignore[assignment]
    attach = None  # type: ignore[assignment]
    detach = None  # type: ignore[assignment]

_TRACER: Optional["Tracer"] = None
_TRACING_ENABLED: Optional[bool] = None
_PROPAGATOR: Optional["TraceContextTextMapPropagator"] = None
_LOG_FILTER_INSTALLED = False


class _NullSpan:
    def set_attribute(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
        return


class _TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover
        trace_id, span_id = get_current_trace_ids()
        record.trace_id = trace_id or ""
        record.span_id = span_id or ""
        return True


def _ensure_log_filter() -> None:
    global _LOG_FILTER_INSTALLED
    if _LOG_FILTER_INSTALLED:
        return
    logging.getLogger().addFilter(_TraceContextFilter())
    _LOG_FILTER_INSTALLED = True


def _ensure_propagator() -> Optional["TraceContextTextMapPropagator"]:
    global _PROPAGATOR
    if _PROPAGATOR is None and TraceContextTextMapPropagator is not None:
        _PROPAGATOR = TraceContextTextMapPropagator()
    return _PROPAGATOR


def _is_tracing_enabled() -> bool:
    global _TRACING_ENABLED
    if _TRACING_ENABLED is None:
        _TRACING_ENABLED = Settings().enable_tracing
        _ensure_log_filter()
    return _TRACING_ENABLED


def get_tracer() -> Optional["Tracer"]:
    global _TRACER
    if trace is None or not _is_tracing_enabled():
        return None
    if _TRACER is None:
        try:
            _TRACER = trace.get_tracer("ingestion.pipeline")
        except Exception as exc:  # pragma: no cover
            _LOG.warning("Failed to initialize tracer: %s", exc)
            _TRACER = None
    return _TRACER


def get_current_span() -> Optional["Span"]:
    if trace is None:
        return None
    try:
        span = trace.get_current_span()
    except Exception:
        return None
    if span is None or not span.get_span_context().is_valid:
        return None
    return span


def get_current_trace_ids() -> Tuple[Optional[str], Optional[str]]:
    span = get_current_span()
    if span is None:
        return None, None
    ctx = span.get_span_context()
    trace_id = f"{ctx.trace_id:032x}"
    span_id = f"{ctx.span_id:016x}"
    return trace_id, span_id


def inject_trace_headers(carrier: Dict[str, str]) -> Dict[str, str]:
    if not carrier:
        carrier = {}
    if trace is None or not _is_tracing_enabled():
        return carrier
    propagator = _ensure_propagator()
    if propagator is None:
        return carrier
    try:
        propagator.inject(carrier)
    except Exception:
        _LOG.debug("Failed to inject trace headers", exc_info=True)
    return carrier


def attach_trace_context(headers: Optional[Dict[str, str]]) -> Optional[object]:
    if trace is None or attach is None or headers is None or not _is_tracing_enabled():
        return None
    propagator = _ensure_propagator()
    if propagator is None:
        return None
    try:
        ctx = propagator.extract(headers)
        if ctx is None:
            return None
        return attach(ctx)
    except Exception:
        _LOG.debug("Failed to attach trace context", exc_info=True)
        return None


def detach_trace_context(token: Optional[object]) -> None:
    if detach is None or token is None:
        return
    try:
        detach(token)
    except Exception:
        _LOG.debug("Failed to detach trace context", exc_info=True)


@contextmanager
def start_span(name: str, attributes: Optional[Dict[str, object]] = None) -> Iterator[object]:
    tracer = get_tracer()
    if tracer is None:
        yield _NullSpan()
        return
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                try:
                    span.set_attribute(key, value)
                except Exception:
                    _LOG.debug("Failed to set span attribute %s", key, exc_info=True)
        yield span


def reset_tracer() -> None:
    global _TRACER, _TRACING_ENABLED, _PROPAGATOR
    _TRACER = None
    _TRACING_ENABLED = None
    _PROPAGATOR = None


__all__ = [
    "get_tracer",
    "start_span",
    "reset_tracer",
    "inject_trace_headers",
    "attach_trace_context",
    "detach_trace_context",
    "get_current_trace_ids",
    "send_task_with_tracing",
]


def send_task_with_tracing(app, task_name: str, *, args=None, kwargs=None, queue: Optional[str] = None):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    headers = inject_trace_headers({})
    try:
        return app.send_task(task_name, args=args, kwargs=kwargs, queue=queue, headers=headers)
    except TypeError:
        return app.send_task(task_name, args=args, kwargs=kwargs, queue=queue)
