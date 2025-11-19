"""
Job registry backed by pluggable storage (Postgres by default).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Iterable, List, Optional

from ingestion.config import Settings
from ingestion.core.db.postgres import PostgresPool
from ingestion.core.status import write_status_snapshot

try:
    import psycopg
except ImportError:  # pragma: no cover - fallback to memory in tests
    psycopg = None  # type: ignore[assignment]

_LOG = logging.getLogger(__name__)


class JobState(str, Enum):
    NEW = "NEW"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    STAGED = "STAGED"
    UPSERTING = "UPSERTING"
    VERIFYING = "VERIFYING"
    CLEANUP = "CLEANUP"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REMOVED = "REMOVED"


@dataclass(slots=True)
class JobRecord:
    job_id: str
    source_path: str
    state: JobState
    refresh: bool
    stage: str
    updated_at: datetime
    message: Optional[str] = None
    expected_checksum: Optional[str] = None
    expected_count: Optional[int] = None


class _BaseBackend:
    def upsert(self, record: JobRecord) -> JobRecord:
        raise NotImplementedError

    def get(self, job_id: str) -> Optional[JobRecord]:
        raise NotImplementedError

    def list(self) -> Iterable[JobRecord]:
        raise NotImplementedError

    def update_state(
        self,
        job_id: str,
        *,
        state: JobState,
        stage: str,
        message: Optional[str],
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> JobRecord:
        raise NotImplementedError

    def exists_for_source(self, source_path: str) -> bool:
        raise NotImplementedError

    def append_history(
        self,
        job_id: str,
        *,
        state: str,
        stage: str,
        message: Optional[str],
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Release backend resources if needed."""


class _InMemoryBackend(_BaseBackend):
    def __init__(self) -> None:
        from threading import RLock

        self._lock = RLock()
        self._store: Dict[str, JobRecord] = {}
        self._history: Dict[str, List[dict]] = {}

    def upsert(self, record: JobRecord) -> JobRecord:
        with self._lock:
            self._store[record.job_id] = record
            return record

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._store.get(job_id)

    def list(self) -> Iterable[JobRecord]:
        with self._lock:
            return list(self._store.values())

    def update_state(
        self,
        job_id: str,
        *,
        state: JobState,
        stage: str,
        message: Optional[str],
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> JobRecord:
        with self._lock:
            if job_id not in self._store:
                raise KeyError(job_id)
            record = self._store[job_id]
            record.state = state
            record.stage = stage
            record.updated_at = datetime.now(tz=timezone.utc)
            record.message = message
            if expected_checksum is not None:
                record.expected_checksum = expected_checksum
            if expected_count is not None:
                record.expected_count = expected_count
            self._history.setdefault(job_id, []).append(
                {
                    "state": state.value,
                    "stage": stage,
                    "message": message,
                    "expected_checksum": record.expected_checksum,
                    "expected_count": record.expected_count,
                    "created_at": datetime.now(tz=timezone.utc),
                }
            )
            return record

    def exists_for_source(self, source_path: str) -> bool:
        with self._lock:
            return any(r.source_path == source_path for r in self._store.values())

    def append_history(
        self,
        job_id: str,
        *,
        state: str,
        stage: str,
        message: Optional[str],
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> None:
        with self._lock:
            entry = {
                "state": state,
                "stage": stage,
                "message": message,
                "expected_checksum": expected_checksum,
                "expected_count": expected_count,
                "created_at": datetime.now(tz=timezone.utc),
            }
            self._history.setdefault(job_id, []).append(entry)

    def close(self) -> None:
        with self._lock:
            self._store.clear()
            self._history.clear()


class _PostgresBackend(_BaseBackend):
    def __init__(self, settings: Settings) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg not installed")
        self._pool = PostgresPool(settings)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    state TEXT NOT NULL,
                    refresh BOOLEAN NOT NULL,
                    stage TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    message TEXT,
                    expected_checksum TEXT,
                    expected_count INTEGER
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs_history (
                    id BIGSERIAL PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    message TEXT,
                    expected_checksum TEXT,
                    expected_count INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )

    @staticmethod
    def _row_to_record(row) -> JobRecord:
        return JobRecord(
            job_id=row[0],
            source_path=row[1],
            state=JobState(row[2]),
            refresh=row[3],
            stage=row[4],
            updated_at=row[5],
            message=row[6],
            expected_checksum=row[7],
            expected_count=row[8],
        )

    def upsert(self, record: JobRecord) -> JobRecord:
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_jobs (job_id, source_path, state, refresh, stage, updated_at, message, expected_checksum, expected_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    source_path = EXCLUDED.source_path,
                    state = EXCLUDED.state,
                    refresh = EXCLUDED.refresh,
                    stage = EXCLUDED.stage,
                    updated_at = EXCLUDED.updated_at,
                    message = EXCLUDED.message,
                    expected_checksum = EXCLUDED.expected_checksum,
                    expected_count = EXCLUDED.expected_count;
                """,
                (
                    record.job_id,
                    record.source_path,
                    record.state.value,
                    record.refresh,
                    record.stage,
                    record.updated_at,
                    record.message,
                    record.expected_checksum,
                    record.expected_count,
                ),
            )

            return record

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT job_id, source_path, state, refresh, stage, updated_at, message, expected_checksum, expected_count FROM ingestion_jobs WHERE job_id=%s",
                (job_id,),
            ).fetchone()
            return self._row_to_record(row) if row else None

    def list(self) -> Iterable[JobRecord]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT job_id, source_path, state, refresh, stage, updated_at, message, expected_checksum, expected_count FROM ingestion_jobs ORDER BY updated_at DESC"
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def update_state(
        self,
        job_id: str,
        *,
        state: JobState,
        stage: str,
        message: Optional[str],
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> JobRecord:
        updated_at = datetime.now(tz=timezone.utc)
        with self._pool.connection() as conn:
            result = conn.execute(
                """
                UPDATE ingestion_jobs
                SET state=%s,
                    stage=%s,
                    updated_at=%s,
                    message=%s,
                    expected_checksum=COALESCE(%s, expected_checksum),
                    expected_count=COALESCE(%s, expected_count)
                WHERE job_id=%s
                RETURNING job_id, source_path, state, refresh, stage, updated_at, message, expected_checksum, expected_count;
                """,
                (state.value, stage, updated_at, message, expected_checksum, expected_count, job_id),
            ).fetchone()
            if not result:
                raise KeyError(job_id)
            conn.execute(
                """
                INSERT INTO ingestion_jobs_history (job_id, state, stage, message, expected_checksum, expected_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (job_id, state.value, stage, message, expected_checksum, expected_count),
            )
            return self._row_to_record(result)

    def exists_for_source(self, source_path: str) -> bool:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM ingestion_jobs WHERE source_path=%s LIMIT 1",
                (source_path,),
            ).fetchone()
            return row is not None

    def append_history(
        self,
        job_id: str,
        *,
        state: str,
        stage: str,
        message: Optional[str],
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_jobs_history (job_id, state, stage, message, expected_checksum, expected_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (job_id, state, stage, message, expected_checksum, expected_count),
            )

    def close(self) -> None:
        self._pool.close()


class JobRegistry:
    _GLOBAL: Optional[JobRegistry] = None

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()
        backend_choice = self._settings.job_registry_backend.lower()
        if backend_choice == "postgres" and psycopg is not None:
            try:
                self._backend: _BaseBackend = _PostgresBackend(self._settings)
                _LOG.info("Using Postgres job registry backend")
            except Exception as exc:  # pragma: no cover
                _LOG.warning("Falling back to in-memory registry: %s", exc)
                self._backend = _InMemoryBackend()
        else:
            _LOG.info("Using in-memory job registry backend (%s)", backend_choice)
            self._backend = _InMemoryBackend()

    def upsert(self, record: JobRecord) -> None:
        stored = self._backend.upsert(record)
        try:
            # Keep the human-readable status snapshot in sync with the latest registry state.
            write_status_snapshot(stored, self._settings)
        except Exception:  # pragma: no cover - best effort
            _LOG.debug("Failed to write status snapshot on upsert", exc_info=True)

    def get(self, job_id: str) -> Optional[JobRecord]:
        return self._backend.get(job_id)

    def list(self) -> Iterable[JobRecord]:
        return self._backend.list()

    def update_state(
        self,
        job_id: str,
        *,
        state: JobState,
        stage: str,
        message: Optional[str] = None,
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> JobRecord:
        try:
            updated = self._backend.update_state(
                job_id,
                state=state,
                stage=stage,
                message=message,
                expected_checksum=expected_checksum,
                expected_count=expected_count,
            )
            write_status_snapshot(updated, self._settings)
            return updated
        except KeyError:
            fallback = new_record(
                job_id=job_id,
                source_path=job_id,
                state=state,
                refresh=False,
                stage=stage,
                message=message,
                expected_checksum=expected_checksum,
                expected_count=expected_count,
            )
            stored = self._backend.upsert(fallback)
            # Persist the fallback snapshot before retrying the update to ensure files exist.
            write_status_snapshot(stored, self._settings)
            updated = self._backend.update_state(
                job_id,
                state=state,
                stage=stage,
                message=message,
                expected_checksum=expected_checksum,
                expected_count=expected_count,
            )
            write_status_snapshot(updated, self._settings)
            return updated

    def exists_for_source(self, source_path: str) -> bool:
        return self._backend.exists_for_source(source_path)

    def append_history(
        self,
        job_id: str,
        *,
        state: str = "TOMBSTONE",
        stage: str,
        message: Optional[str] = None,
        expected_checksum: Optional[str] = None,
        expected_count: Optional[int] = None,
    ) -> None:
        self._backend.append_history(
            job_id,
            state=state,
            stage=stage,
            message=message,
            expected_checksum=expected_checksum,
            expected_count=expected_count,
        )

    def close(self) -> None:
        self._backend.close()

    @property
    def settings(self) -> Settings:
        return self._settings

    @classmethod
    def global_instance(cls, settings: Settings | None = None) -> JobRegistry:
        if cls._GLOBAL is None:
            cls._GLOBAL = cls(settings=settings)
        return cls._GLOBAL

    @classmethod
    def reset_global(cls) -> None:
        if cls._GLOBAL:
            cls._GLOBAL.close()
        cls._GLOBAL = None


def new_record(
    *,
    job_id: str,
    source_path: str,
    state: JobState,
    refresh: bool,
    stage: str,
    message: Optional[str] = None,
    expected_checksum: Optional[str] = None,
    expected_count: Optional[int] = None,
) -> JobRecord:
    return JobRecord(
        job_id=job_id,
        source_path=source_path,
        state=state,
        refresh=refresh,
        stage=stage,
        updated_at=datetime.now(tz=timezone.utc),
        message=message,
        expected_checksum=expected_checksum,
        expected_count=expected_count,
    )
