"""Utilities for building ingestion manifests and recording pass metadata."""

from __future__ import annotations

from dataclasses import is_dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
import hashlib

from src_common.ttrpg_logging import get_logger
from src_common.artifact_validator import write_json_atomically

logger = get_logger(__name__)


_PIPELINE_VERSION = "mvp_v2_pass_0_g"


def utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def isoformat(ts: datetime) -> str:
    """Return ISO 8601 string with trailing Z for UTC."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


def create_base_manifest(job_id: str, environment: str, source_file: Path, tool_versions: Dict[str, str]) -> Dict[str, Any]:
    """Create base manifest structure before passes execute."""
    started_at = utc_now()
    return {
        "job_id": job_id,
        "environment": environment,
        "status": "running",
        "created_at": isoformat(started_at),
        "source": {
            "file_path": str(source_file),
            "file_sha": None,
            "page_count": None,
        },
        "pipeline": {
            "version": _PIPELINE_VERSION,
            "started_at": isoformat(started_at),
        },
        "tool_versions": tool_versions,
        "passes": {},
        "artifacts": [],
        "run_summary": {
            "passes_completed": 0,
            "passes_failed": 0,
            "total_duration_ms": 0,
        },
    }


def dataclass_to_dict(result: Any) -> Any:
    """Convert dataclass instances to plain dictionaries recursively."""
    if is_dataclass(result):
        result = asdict(result)
    if isinstance(result, dict):
        return {key: dataclass_to_dict(value) for key, value in result.items()}
    if isinstance(result, (list, tuple)):
        return [dataclass_to_dict(item) for item in result]
    if isinstance(result, Path):
        return str(result)
    return result


def compute_artifact_metadata(job_dir: Path, artifact_entries: Iterable[Any], pass_name: str) -> List[Dict[str, Any]]:
    """Return normalized artifact metadata for manifest recording."""
    metadata: List[Dict[str, Any]] = []
    for entry in artifact_entries or []:
        path = Path(entry)
        full_path = path if path.is_absolute() else job_dir / path
        if not full_path.exists():
            logger.warning("Artifact not found for manifest entry", extra={"path": str(full_path)})
            continue

        try:
            rel_path = str(full_path.relative_to(job_dir))
        except ValueError:
            rel_path = str(full_path)

        stat = full_path.stat()
        metadata.append(
            {
                "path": rel_path.replace("\\", "/"),
                "size_bytes": stat.st_size,
                "checksum_sha256": _sha256_file(full_path),
                "modified_at": isoformat(datetime.fromtimestamp(stat.st_mtime, timezone.utc)),
                "pass": pass_name,
            }
        )
    return metadata


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 checksum for the provided file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize_for_json(value: Any) -> Any:
    """Ensure values are JSON serializable."""
    if isinstance(value, dict):
        return {k: sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return isoformat(value)
    return value


def persist_manifest(manifest_path: Path, manifest: Dict[str, Any]) -> None:
    """Write manifest to disk atomically."""
    serializable = sanitize_for_json(manifest)
    write_json_atomically(serializable, manifest_path)


def gather_tool_versions() -> Dict[str, str]:
    """Gather versions of key ingestion tools if available."""
    versions: Dict[str, str] = {}
    for module_name, attr in [
        ("unstructured", "__version__"),
        ("haystack", "__version__"),
        ("llama_index", "__version__"),
        ("pytesseract", "get_tesseract_version"),
    ]:
        try:
            module = __import__(module_name, fromlist=[attr])
            value = module.get_tesseract_version() if attr == "get_tesseract_version" else getattr(module, attr)
            versions[module_name] = str(value)
        except Exception:
            versions[module_name] = "unavailable"
    return versions
