"""
Prometheus metrics exporter placeholder.

The exporter exposes task-level metrics via an HTTP endpoint when enabled.
"""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict

from ingestion.config import Settings

_LOG = logging.getLogger(__name__)


class _MetricsHandler(BaseHTTPRequestHandler):
    registry: Dict[str, float] = {}  # type: ignore[var-annotated]

    def do_GET(self) -> None:  # noqa: N802
        body = "\n".join(f"{key} {value}" for key, value in self.registry.items())
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        _LOG.debug("metrics: " + format, *args)


class MetricsExporter:
    """Start a background HTTP server to expose Prometheus metrics."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9464) -> None:
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server:
            return
        self._server = HTTPServer((self._host, self._port), _MetricsHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="metrics-exporter",
            daemon=True,
        )
        self._thread.start()
        _LOG.info("Metrics exporter running", extra={"port": self._port})

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        _LOG.info("Metrics exporter stopped")

    @staticmethod
    def observe(metric: str, value: float) -> None:
        _MetricsHandler.registry[metric] = value


def bootstrap_metrics(settings: Settings | None = None) -> MetricsExporter | None:
    cfg = settings or Settings()
    if not cfg.enable_metrics:
        return None
    exporter = MetricsExporter()
    exporter.start()
    return exporter
