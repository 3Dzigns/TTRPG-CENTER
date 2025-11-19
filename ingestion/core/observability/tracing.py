"""
OpenTelemetry tracing bootstrap.
"""

from __future__ import annotations

import logging

from ingestion.config import Settings

_LOG = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError:  # pragma: no cover - tracing optional
    trace = None  # type: ignore[assignment]


def configure_tracing(
    service_name: str,
    *,
    settings: Settings | None = None,
) -> None:
    cfg = settings or Settings()
    if not cfg.enable_tracing or trace is None:
        _LOG.info("Tracing disabled")
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    _LOG.info("Tracing configured", extra={"service": service_name})
