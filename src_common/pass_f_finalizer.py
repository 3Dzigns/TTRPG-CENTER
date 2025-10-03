"""Pass F finalization ensuring artifact integrity and manifest snapshot."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from src_common.logging import get_logger
from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete

logger = get_logger(__name__)


@dataclass
class PassFResult:
    """Structured Pass F result."""

    job_id: str
    checksum_failures: List[str]
    artifacts_indexed: int
    merged_delta_path: str
    manifest_snapshot_path: str
    processing_time_ms: int
    artifacts: List[str]
    success: bool = True
    error_message: Optional[str] = None


class FinalizationRunner:
    """Verifies artifacts and produces manifest snapshot."""

    def __init__(self, job_id: str, env: str, job_log_file: Optional[Path] = None) -> None:
        self.job_id = job_id
        self.env = env
        self.job_log_file = job_log_file

    def process(self, job_dir: Path) -> PassFResult:
        started_at = time.perf_counter()

        # Pass start logging
        log_pass_start("F", "Finalization & Artifact Validation", self.job_log_file)

        pass_dir = job_dir / "pass_f"
        pass_dir.mkdir(parents=True, exist_ok=True)

        checksum_failures = self._verify_checksums(job_dir)
        merged_delta = self._merge_deltas(job_dir, pass_dir)
        manifest_snapshot = self._write_manifest_snapshot(job_dir, pass_dir, merged_delta)
        validation_report = pass_dir / "validation_report.json"
        with validation_report.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "checksum_failures": checksum_failures,
                    "artifact_count": manifest_snapshot["artifact_count"],
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )

        artifacts = [
            merged_delta.relative_to(job_dir).as_posix(),
            manifest_snapshot["path"].relative_to(job_dir).as_posix(),
            validation_report.relative_to(job_dir).as_posix(),
        ]

        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        duration_seconds = processing_time_ms / 1000

        logger.info(
            "pass_f_complete",
            extra={
                "job_id": self.job_id,
                "checksum_failures": len(checksum_failures),
                "artifact_count": manifest_snapshot["artifact_count"],
                "duration_ms": processing_time_ms,
            },
        )

        # Pass complete logging
        stats = {
            "artifacts_indexed": manifest_snapshot["artifact_count"],
            "checksum_failures": len(checksum_failures),
            "success": len(checksum_failures) == 0
        }
        log_pass_complete("F", duration_seconds, stats, self.job_log_file)

        return PassFResult(
            job_id=self.job_id,
            checksum_failures=checksum_failures,
            artifacts_indexed=manifest_snapshot["artifact_count"],
            merged_delta_path=artifacts[0],
            manifest_snapshot_path=artifacts[1],
            processing_time_ms=processing_time_ms,
            artifacts=artifacts,
        )

    def _verify_checksums(self, job_dir: Path) -> List[str]:
        failures: List[str] = []
        split_index = job_dir / "pass_b" / "split_index.json"
        if not split_index.exists():
            return failures
        with split_index.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for part in data.get("parts", []):
            relative_path = part.get("relative_path")
            expected_checksum = part.get("checksum_sha256")
            if not relative_path or not expected_checksum:
                continue
            part_path = job_dir / Path(relative_path)
            if not part_path.exists():
                failures.append(f"missing:{relative_path}")
                continue
            actual_checksum = _sha256(part_path)
            if actual_checksum != expected_checksum:
                failures.append(f"checksum_mismatch:{relative_path}")
        return failures

    def _merge_deltas(self, job_dir: Path, pass_dir: Path) -> Path:
        delta_paths = [
            job_dir / "pass_d" / "dict_delta.passD.json",
            job_dir / "pass_e" / "dict_delta.passE.json",
        ]
        merged: Dict[str, object] = {"job_id": self.job_id, "deltas": []}
        for path in delta_paths:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            merged["deltas"].append(payload)
        output_path = pass_dir / "dict_delta.passF.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=2)
        return output_path

    def _write_manifest_snapshot(self, job_dir: Path, pass_dir: Path, merged_delta: Path) -> Dict[str, object]:
        artifacts = []
        for path in sorted(job_dir.rglob("*")):
            if path.is_file():
                artifacts.append(
                    {
                        "path": path.relative_to(job_dir).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "checksum_sha256": _sha256(path),
                    }
                )
        manifest_path = pass_dir / "manifest.snapshot.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "artifact_count": len(artifacts),
                    "artifacts": artifacts,
                    "merged_delta": merged_delta.relative_to(job_dir).as_posix(),
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )
        return {"path": manifest_path, "artifact_count": len(artifacts)}


def process_pass_f(job_dir: Path, job_id: str, env: str, job_log_file: Optional[Path] = None) -> PassFResult:
    runner = FinalizationRunner(job_id=job_id, env=env, job_log_file=job_log_file)
    return runner.process(job_dir)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
