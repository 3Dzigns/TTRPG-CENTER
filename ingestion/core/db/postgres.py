"""
Postgres connection utilities for the ingestion pipeline.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

try:
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - optional dependency for tests
    ConnectionPool = None  # type: ignore[assignment]

try:
    import psycopg
except ImportError:  # pragma: no cover - caller guards via backend selection
    psycopg = None  # type: ignore[assignment]

from ingestion.config import Settings

_LOG = logging.getLogger(__name__)


class PostgresPool:
    """Lightweight wrapper around psycopg connection pooling."""

    def __init__(self, settings: Settings) -> None:
        if ConnectionPool is None and psycopg is None:  # pragma: no cover - handled upstream
            raise RuntimeError("psycopg not installed")
        self._settings = settings
        if ConnectionPool is not None:
            self._pool = ConnectionPool(
                conninfo=settings.postgres_dsn,
                min_size=1,
                max_size=10,
                kwargs={"autocommit": True},
            )
        else:
            self._pool = None
        _LOG.info("Postgres pool initialized", extra={"dsn": settings.postgres_dsn})

    @contextmanager
    def connection(self):
        if ConnectionPool is not None and self._pool is not None:
            with self._pool.connection() as conn:
                yield conn
            return
        if psycopg is None:  # pragma: no cover - guarded in __init__
            raise RuntimeError("psycopg not available")
        conn = psycopg.connect(self._settings.postgres_dsn)
        conn.autocommit = True
        try:
            yield conn
        finally:
            conn.close()

    def close(self) -> None:
        if ConnectionPool is not None and self._pool is not None:
            self._pool.close()
