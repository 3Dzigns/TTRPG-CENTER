"""
Helpers for enforcing per-stage idempotency markers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ingestion.config import Settings


def _stage_dir(settings: Settings, job_id: str) -> Path:
    directory = settings.jobs_dir / job_id / "stages"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _stage_file(settings: Settings, job_id: str, stage: str) -> Path:
    safe_stage = stage.replace("/", "_").replace(":", "_")
    return _stage_dir(settings, job_id) / f"{safe_stage}.json"


def _normalize_fingerprint(fingerprint: Optional[str]) -> str:
    if fingerprint is None:
        return ""
    return fingerprint


def stage_completed(
    settings: Settings,
    job_id: str,
    stage: str,
    *,
    fingerprint: Optional[str] = None,
) -> bool:
    """
    Return True if the stage marker already exists.
    """

    path = _stage_file(settings, job_id, stage)
    if not path.exists():
        return False

    if fingerprint is None:
        return True

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return True

    return data.get("fingerprint") == fingerprint


def mark_stage_completed(
    settings: Settings,
    job_id: str,
    stage: str,
    *,
    fingerprint: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Persist a completion marker for the given job stage.
    """

    payload = {
        "job_id": job_id,
        "stage": stage,
        "fingerprint": _normalize_fingerprint(fingerprint),
        "completed_at": datetime.now(tz=timezone.utc).isoformat(),
        "details": details or {},
    }

    path = _stage_file(settings, job_id, stage)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def fingerprint_payload(value: object) -> str:
    """Deterministic fingerprint helper for JSON-serialisable payloads."""

    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


__all__ = [
    "stage_completed",
    "mark_stage_completed",
    "fingerprint_payload",
]

