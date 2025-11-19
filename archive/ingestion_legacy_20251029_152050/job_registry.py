#!/usr/bin/env python3
"""
job_registry.py - Postgres-backed job registry for async ingestion
===============================================================

Implements the canonical job/state storage described in the
Fully-Async Ingestion Pipeline plan. Provides a thin wrapper around
the ``jobs.registry`` and ``jobs.history`` tables so workers and
Celery tasks can coordinate without filesystem markers.

Key features:
  * Deterministic job registration with idempotent upsert semantics
  * Stage/state transitions with automatic history entries
  * Safe job claiming via SELECT ... FOR UPDATE SKIP LOCKED
  * Heartbeat/lock tracking for stuck worker detection
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import psycopg2
import psycopg2.extras


class JobRegistryError(RuntimeError):
    """Raised when the registry encounters an unrecoverable error."""


def _build_dsn() -> str:
    """Build a libpq connection string from environment variables."""
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    database = os.getenv("POSTGRES_DB", user)

    return f"host={host} port={port} dbname={database} user={user} password={password}"


@contextmanager
def _postgres_cursor(dsn: str):
    """Context manager that yields a RealDictCursor and commits on success."""
    conn = psycopg2.connect(dsn, connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5")))
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@dataclass(frozen=True)
class JobRecord:
    """Dataclass representing the current registry snapshot for a job."""

    job_id: uuid.UUID
    source_id: str
    source_path: str
    job_type: str
    refresh: bool
    state: str
    stage: Optional[str]
    attempts: int
    priority: int
    created_at: datetime
    updated_at: datetime
    locked_by: Optional[str]
    locked_at: Optional[datetime]
    last_error: Optional[str]
    next_run_at: Optional[datetime]
    metadata: Dict[str, Any]

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "JobRecord":
        """Construct a JobRecord from a RealDictCursor row."""
        job_id = row["job_id"]
        if isinstance(job_id, str):
            job_id = uuid.UUID(job_id)
        return cls(
            job_id=job_id,
            source_id=row["source_id"],
            source_path=row["source_path"],
            job_type=row["job_type"],
            refresh=row["refresh"],
            state=row["state"],
            stage=row.get("stage"),
            attempts=row["attempts"],
            priority=row["priority"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            locked_by=row.get("locked_by"),
            locked_at=row.get("locked_at"),
            last_error=row.get("last_error"),
            next_run_at=row.get("next_run_at"),
            metadata=row.get("metadata") or {},
        )


class JobRegistry:
    """Main entry point for interacting with the jobs registry schema."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or _build_dsn()

    # ------------------------------------------------------------------
    # Registration & upsert
    # ------------------------------------------------------------------
    def register_job(
        self,
        *,
        job_id: Optional[uuid.UUID],
        source_id: str,
        source_path: str,
        job_type: str,
        refresh: bool = False,
        initial_stage: str = "NEW",
        initial_state: str = "queued",
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> JobRecord:
        """
        Register (or upsert) a job in the registry.

        Returns the canonical JobRecord after insertion.
        """
        job_uuid = job_id or uuid.uuid4()
        payload = psycopg2.extras.Json(metadata or {})

        with _postgres_cursor(self.dsn) as cur:
            cur.execute(
                """
                INSERT INTO jobs.registry (
                    job_id, source_id, source_path, job_type, refresh,
                    state, stage, priority, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id)
                DO UPDATE SET
                    source_id = EXCLUDED.source_id,
                    source_path = EXCLUDED.source_path,
                    job_type = EXCLUDED.job_type,
                    refresh = EXCLUDED.refresh,
                    state = EXCLUDED.state,
                    stage = EXCLUDED.stage,
                    priority = EXCLUDED.priority,
                    metadata = EXCLUDED.metadata,
                    last_error = NULL,
                    attempts = CASE
                        WHEN jobs.registry.state IN ('failed', 'dlq') THEN 0
                        ELSE jobs.registry.attempts
                    END
                RETURNING *
                """,
                (
                    job_uuid,
                    source_id,
                    source_path,
                    job_type,
                    refresh,
                    initial_state,
                    initial_stage,
                    priority,
                    payload,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise JobRegistryError("Failed to register job")

            self._append_history(
                cur,
                job_uuid,
                stage=initial_stage,
                state=initial_state,
                message="job registered",
                details=metadata,
            )
            return JobRecord.from_row(row)

    # ------------------------------------------------------------------
    # Claiming & locking
    # ------------------------------------------------------------------
    def claim_next_job(self, *, stage: str, worker_id: str) -> Optional[JobRecord]:
        """Claim the next queued job for a stage in a race-safe manner."""
        with _postgres_cursor(self.dsn) as cur:
            cur.execute(
                """
                SELECT *
                FROM jobs.registry
                WHERE state = 'queued'
                  AND stage = %s
                  AND (next_run_at IS NULL OR next_run_at <= NOW())
                ORDER BY priority DESC, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (stage,),
            )
            row = cur.fetchone()
            if not row:
                return None

            job_uuid = row["job_id"]
            cur.execute(
                """
                UPDATE jobs.registry
                SET state = 'claimed',
                    locked_by = %s,
                    locked_at = NOW(),
                    attempts = attempts + 1
                WHERE job_id = %s
                RETURNING *
                """,
                (worker_id, job_uuid),
            )
            updated = cur.fetchone()
            self._append_history(
                cur,
                job_uuid,
                stage=stage,
                state="claimed",
                message=f"claimed by {worker_id}",
            )
            return JobRecord.from_row(updated)

    def release_job(self, job_id: uuid.UUID, *, new_state: str = "queued", delay_seconds: Optional[int] = None) -> JobRecord:
        """
        Release a claimed job back to a queue (after failure or retry).

        Optionally set ``delay_seconds`` to push next attempt into the future.
        """
        with _postgres_cursor(self.dsn) as cur:
            cur.execute(
                """
                UPDATE jobs.registry
                SET state = %s,
                    locked_by = NULL,
                    locked_at = NULL,
                    next_run_at = CASE
                        WHEN %s IS NOT NULL THEN NOW() + (%s || ' seconds')::INTERVAL
                        ELSE NULL
                    END
                WHERE job_id = %s
                RETURNING *
                """,
                (new_state, delay_seconds, delay_seconds, job_id),
            )
            row = cur.fetchone()
            if not row:
                raise JobRegistryError(f"Job {job_id} not found while releasing")
            self._append_history(
                cur,
                job_id,
                stage=row.get("stage"),
                state=new_state,
                message="job released back to queue",
                details={"delay_seconds": delay_seconds} if delay_seconds else None,
            )
            return JobRecord.from_row(row)

    def mark_completed(self, job_id: uuid.UUID, *, stage: str, next_stage: Optional[str]) -> JobRecord:
        """Mark a job as completed for its current stage and optionally advance."""
        next_state = "queued" if next_stage else "completed"
        with _postgres_cursor(self.dsn) as cur:
            cur.execute(
                """
                UPDATE jobs.registry
                SET state = %s,
                    stage = %s,
                    locked_by = NULL,
                    locked_at = NULL,
                    next_run_at = NULL
                WHERE job_id = %s
                RETURNING *
                """,
                (next_state, next_stage, job_id),
            )
            row = cur.fetchone()
            if not row:
                raise JobRegistryError(f"Job {job_id} not found while completing stage")

            self._append_history(
                cur,
                job_id,
                stage=stage,
                state="completed",
                message=f"stage {stage} completed",
                details={"next_stage": next_stage},
            )

            if next_stage:
                self._append_history(
                    cur,
                    job_id,
                    stage=next_stage,
                    state="queued",
                    message="moved to next stage",
                )

            return JobRecord.from_row(row)

    def mark_failed(
        self,
        job_id: uuid.UUID,
        *,
        stage: str,
        error_message: str,
        permanent: bool = False,
        backoff_seconds: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> JobRecord:
        """
        Mark job as failed. If ``permanent`` set state to ``dlq``; otherwise
        requeue with optional backoff.
        """
        state = "dlq" if permanent else "queued"
        with _postgres_cursor(self.dsn) as cur:
            cur.execute(
                """
                UPDATE jobs.registry
                SET state = %s,
                    last_error = %s,
                    locked_by = NULL,
                    locked_at = NULL,
                    next_run_at = CASE
                        WHEN %s IS NOT NULL THEN NOW() + (%s || ' seconds')::INTERVAL
                        ELSE NULL
                    END
                WHERE job_id = %s
                RETURNING *
                """,
                (state, error_message, backoff_seconds, backoff_seconds, job_id),
            )
            row = cur.fetchone()
            if not row:
                raise JobRegistryError(f"Job {job_id} not found while marking failure")

            context = details.copy() if details else {}
            context["permanent"] = permanent
            if backoff_seconds:
                context["backoff_seconds"] = backoff_seconds

            self._append_history(
                cur,
                job_id,
                stage=stage,
                state="failed" if not permanent else "dlq",
                message=error_message,
                details=context,
            )
            return JobRecord.from_row(row)

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------
    def fetch_job(self, job_id: uuid.UUID) -> Optional[JobRecord]:
        """Fetch a single job record."""
        with _postgres_cursor(self.dsn) as cur:
            cur.execute(
                "SELECT * FROM jobs.registry WHERE job_id = %s",
                (job_id,),
            )
            row = cur.fetchone()
            return JobRecord.from_row(row) if row else None

    def iter_jobs(self, *, states: Optional[Iterable[str]] = None, limit: int = 100) -> Iterable[JobRecord]:
        """Yield jobs filtered by states (defaults to all)."""
        clause = ""
        params: tuple[Any, ...] = ()
        if states:
            placeholders = ", ".join(["%s"] * len(states))
            clause = f"WHERE state IN ({placeholders})"
            params = tuple(states)

        query = f"""
            SELECT *
            FROM jobs.registry
            {clause}
            ORDER BY created_at DESC
            LIMIT %s
        """
        with _postgres_cursor(self.dsn) as cur:
            cur.execute(query, params + (limit,))
            for row in cur.fetchall():
                yield JobRecord.from_row(row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _append_history(
        self,
        cur: psycopg2.extensions.cursor,
        job_id: uuid.UUID,
        *,
        stage: Optional[str],
        state: str,
        message: Optional[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert a history row using an existing cursor/transaction."""
        cur.execute(
            """
            INSERT INTO jobs.history (job_id, stage, state, message, details)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (job_id, stage, state, message, psycopg2.extras.Json(details) if details else None),
        )


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)
