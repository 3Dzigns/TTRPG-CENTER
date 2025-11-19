"""
Artifact retention helpers for housekeeping sweeper.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from ingestion.config import Settings
from ingestion.core.job_registry import JobRecord, JobRegistry, JobState

LOG = logging.getLogger(__name__)
RETENTION_LOG_FILENAME = "artifact_retention.jsonl"
TERMINAL_STATES = {JobState.COMPLETED, JobState.REMOVED}


@dataclass(slots=True)
class FinalizedMarker:
    finalized: bool
    finalized_at: Optional[datetime]
    source_path: Optional[str]
    payload: Dict[str, object]


@dataclass(slots=True)
class RetentionStats:
    pruned: int = 0
    expired: int = 0
    skipped: int = 0
    files_removed: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "pruned": self.pruned,
            "expired": self.expired,
            "skipped": self.skipped,
            "files_removed": self.files_removed,
        }


def _parse_iso_timestamp(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_marker(marker_path: Path) -> FinalizedMarker:
    if not marker_path.exists():
        return FinalizedMarker(False, None, None, {})
    try:
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - malformed marker
        LOG.warning("Failed to parse finalized marker: %s", marker_path)
        return FinalizedMarker(False, None, None, {})

    finalized = bool(payload.get("finalized"))
    finalized_at = _parse_iso_timestamp(payload.get("finalized_at"))
    source_path = payload.get("source_path")
    if source_path is not None and not isinstance(source_path, str):
        source_path = None
    return FinalizedMarker(finalized, finalized_at, source_path, payload)


def _build_active_sources(records: Iterable[JobRecord]) -> Dict[str, Set[str]]:
    active: Dict[str, Set[str]] = {}
    for record in records:
        if record.state in TERMINAL_STATES:
            continue
        active.setdefault(record.source_path, set()).add(record.job_id)
    return active


def _build_keep_set(job_dir: Path) -> Set[Path]:
    """
    Build set of files to preserve during cleanup.

    CRITICAL: Only keep marker files for future corruption detection.
    All large artifact files (elements.json, embeddings.json, etc.) should be deleted.
    """
    keep: Set[Path] = {Path("finalized.marker")}

    # Keep ALL ready.marker files permanently for corruption detection
    ready_markers = list(job_dir.glob("**/ready.marker"))
    for marker in ready_markers:
        keep.add(marker.relative_to(job_dir))

    # Keep manifest files for tracking (small files)
    manifest_files = list(job_dir.glob("**/graph_manifest.json"))
    for manifest in manifest_files:
        keep.add(manifest.relative_to(job_dir))

    return keep


def _prune_job_directory(job_dir: Path) -> List[str]:
    keep_set = _build_keep_set(job_dir)
    removed: List[str] = []

    for path in sorted(job_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(job_dir)
        if relative_path in keep_set:
            continue
        try:
            path.unlink()
            removed.append(relative_path.as_posix())
        except FileNotFoundError:
            continue
        except Exception as exc:  # pragma: no cover - best effort removal
            LOG.warning("Failed to remove artifact %s: %s", path, exc)

    # Remove empty directories, deepest first.
    for directory in sorted(job_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not directory.is_dir():
            continue
        try:
            directory.rmdir()
            rel_dir = directory.relative_to(job_dir).as_posix()
            if rel_dir:
                removed.append(f"{rel_dir}/")
        except OSError:
            continue
        except Exception as exc:  # pragma: no cover - best effort
            LOG.debug("Failed to prune directory %s: %s", directory, exc)

    return removed


def _expire_job_artifacts(job_dir: Path, status_path: Path) -> Dict[str, object]:
    removed_files = 0
    if job_dir.exists():
        removed_files = sum(1 for item in job_dir.rglob("*") if item.is_file())
    status_removed = False
    try:
        if job_dir.exists():
            shutil.rmtree(job_dir)
    except Exception as exc:  # pragma: no cover - best effort
        LOG.warning("Failed to delete artifacts directory %s: %s", job_dir, exc)
    if status_path.exists():
        try:
            status_path.unlink()
            status_removed = True
            removed_files += 1
        except Exception as exc:  # pragma: no cover - best effort
            LOG.warning("Failed to remove status snapshot %s: %s", status_path, exc)
    return {
        "removed_files": removed_files,
        "status_removed": status_removed,
    }


def _should_skip_due_to_refresh(
    job_id: str,
    marker: FinalizedMarker,
    active_sources: Dict[str, Set[str]],
) -> bool:
    if not marker.source_path:
        return False
    inflight = active_sources.get(marker.source_path, set())
    return any(other_id != job_id for other_id in inflight)


def _log_retention_event(settings: Settings, payload: Dict[str, object]) -> None:
    logs_dir = settings.logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / RETENTION_LOG_FILENAME
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
    except Exception as exc:  # pragma: no cover - best effort
        LOG.warning("Failed to append retention log entry: %s", exc)


def enforce_retention(
    settings: Settings,
    registry: JobRegistry,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    stats = RetentionStats()
    current_time = now or datetime.now(tz=timezone.utc)
    retention_days = max(settings.artifact_retention_days, 0)
    retention_window = timedelta(days=retention_days)

    job_records = {record.job_id: record for record in registry.list()}
    active_sources = _build_active_sources(job_records.values())
    artifacts_root = settings.artifacts_dir
    if not artifacts_root.exists():
        return stats.as_dict()

    for job_dir in sorted(artifacts_root.iterdir()):
        if not job_dir.is_dir():
            continue
        job_id = job_dir.name
        marker = _load_marker(job_dir / "finalized.marker")
        record = job_records.get(job_id)

        if not marker.finalized or marker.finalized_at is None:
            stats.skipped += 1
            continue

        if record and record.state not in TERMINAL_STATES:
            stats.skipped += 1
            continue

        if _should_skip_due_to_refresh(job_id, marker, active_sources):
            stats.skipped += 1
            continue

        status_path = settings.jobs_dir / f"{job_id}.status.json"

        age = current_time - marker.finalized_at
        if age >= retention_window:
            result = _expire_job_artifacts(job_dir, status_path)
            stats.expired += 1
            stats.files_removed += int(result.get("removed_files", 0) or 0)
            if record:
                registry.append_history(
                    job_id,
                    stage="housekeeping.retention",
                    message=f"Artifacts expired after {retention_days} day(s)",
                )
            _log_retention_event(
                settings,
                {
                    "timestamp": current_time.isoformat(),
                    "job_id": job_id,
                    "action": "expired",
                    "removed_files": result.get("removed_files", 0),
                    "status_removed": result.get("status_removed", False),
                    "retention_days": retention_days,
                    "finalized_at": marker.finalized_at.isoformat(),
                },
            )
            continue

        removed = _prune_job_directory(job_dir)
        if removed:
            stats.pruned += 1
            stats.files_removed += len(removed)
            if record:
                registry.append_history(
                    job_id,
                    stage="housekeeping.retention",
                    message="Pruned artifacts post-finalization",
                )
            _log_retention_event(
                settings,
                {
                    "timestamp": current_time.isoformat(),
                    "job_id": job_id,
                    "action": "pruned",
                    "removed": removed,
                    "retention_days": retention_days,
                    "finalized_at": marker.finalized_at.isoformat(),
                },
            )
        else:
            stats.skipped += 1

    return stats.as_dict()


__all__ = ["enforce_retention"]
