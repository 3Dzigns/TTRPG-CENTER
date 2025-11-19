"""
Lightweight HTTP health server for worker containers.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Tuple

from ingestion.config import Settings

try:  # pragma: no cover - optional dependency
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
except Exception:  # pragma: no cover - optional dependency
    generate_latest = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"

_LOG = logging.getLogger(__name__)

_SERVER_STARTED = False
_LOCK = threading.Lock()


class _HealthState:
    def __init__(self, queue_name: str, celery_app, settings: Settings) -> None:
        self.queue_name = queue_name
        self.celery_app = celery_app
        self.settings = settings
        self.start_time = time.monotonic()
        self._ready_cache: Tuple[float, bool, Dict[str, str]] = (0.0, False, {})
        self._ready_lock = threading.Lock()

    def health_payload(self) -> Dict[str, object]:
        return {
            "status": "ok",
            "queue": self.queue_name,
            "uptime_s": round(time.monotonic() - self.start_time, 3),
        }

    def readiness_payload(self) -> Tuple[Dict[str, object], bool]:
        ttl = 30.0
        now = time.monotonic()
        with self._ready_lock:
            cached_at, cached_status, cached_details = self._ready_cache
            if now - cached_at < ttl:
                status = "ok" if cached_status else "error"
                return {"status": status, "checks": cached_details}, cached_status

            checks: Dict[str, str] = {}
            all_ok = True

            broker_ok, broker_detail = self._check_broker()
            checks["broker"] = broker_detail
            all_ok &= broker_ok

            dict_ok, dict_detail = self._check_dictionary()
            checks["dictionary"] = dict_detail
            all_ok &= dict_ok

            cass_ok, cass_detail = self._check_cassandra()
            checks["cassandra"] = cass_detail
            all_ok &= cass_ok

            status = "ok" if all_ok else "error"
            self._ready_cache = (now, all_ok, checks)
            return {"status": status, "checks": checks}, all_ok

    def _check_broker(self) -> Tuple[bool, str]:
        if self.celery_app is None:
            return False, "unavailable"
        try:
            with self.celery_app.connection() as conn:
                conn.connect()
            return True, "ok"
        except Exception as exc:  # pragma: no cover - connectivity check
            return False, f"error: {exc}"

    def _check_dictionary(self) -> Tuple[bool, str]:
        try:
            from ingestion.core.db.dictionary import get_dictionary_store

            store = get_dictionary_store(self.settings)
            store.count_terms("__health__")  # type: ignore[attr-defined]
            return True, "ok"
        except Exception as exc:  # pragma: no cover - best effort
            return False, f"error: {exc}"

    def _check_cassandra(self) -> Tuple[bool, str]:
        try:
            from ingestion.core.db.cassandra_store import get_cassandra_store

            store = get_cassandra_store(self.settings)
            store.fetch_source("__health__")  # type: ignore[attr-defined]
            return True, "ok"
        except Exception as exc:  # pragma: no cover - best effort
            return False, f"error: {exc}"


def start_health_server(queue_name: str, celery_app, settings: Settings) -> None:
    """Start the health HTTP server if configured."""

    host = os.getenv("WORKER_HEALTH_HOST", "0.0.0.0")
    port_value = os.getenv("WORKER_HEALTH_PORT")
    try:
        port = int(port_value) if port_value else 0
    except ValueError:
        port = 0

    if port <= 0:
        return

    global _SERVER_STARTED
    with _LOCK:
        if _SERVER_STARTED:
            return

        state = _HealthState(queue_name, celery_app, settings)

        class _Handler(BaseHTTPRequestHandler):
            server_state = state

            def log_message(self, format: str, *args) -> None:  # pragma: no cover - silence default logging
                return

            def do_GET(self):  # type: ignore[override]
                if self.path == "/healthz":
                    payload = self.server_state.health_payload()
                    self._write_json(payload)
                elif self.path == "/readyz":
                    payload, ok = self.server_state.readiness_payload()
                    status = HTTPStatus.OK if ok else HTTPStatus.SERVICE_UNAVAILABLE
                    self._write_json(payload, status=status)
                elif self.path == "/metrics":
                    self._write_metrics()
                else:
                    self.send_response(HTTPStatus.NOT_FOUND)
                    self.end_headers()

            def _write_json(self, payload: Dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _write_metrics(self) -> None:
                if generate_latest is None:
                    body = b"# metrics disabled\n"
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                try:
                    body = generate_latest()
                except Exception as exc:  # pragma: no cover - best effort
                    message = f"# metrics unavailable: {exc}\n".encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(message)))
                    self.end_headers()
                    self.wfile.write(message)
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        try:
            httpd = ThreadingHTTPServer((host, port), _Handler)
        except OSError as exc:  # pragma: no cover - best effort
            _LOG.warning("Failed to start health server on %s:%s: %s", host, port, exc)
            _SERVER_STARTED = True
            return

        thread = threading.Thread(target=httpd.serve_forever, name="health-server", daemon=True)
        thread.start()
        _SERVER_STARTED = True
        _LOG.info("Health server listening", extra={"host": host, "port": port, "queue": queue_name})


__all__ = ["start_health_server"]
