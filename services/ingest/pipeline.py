"""
Ingest Service Pipeline

MVP v2 Pass 0-G pipeline implementation.
Coordinates execution of all ingestion passes with structured manifests and
artifact bookkeeping.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src_common.logging import get_logger
from src_common.environment_isolation import get_environment_validator
from src_common.ingestion.manifest_utils import (
    create_base_manifest,
    dataclass_to_dict,
    compute_artifact_metadata,
    gather_tool_versions,
    persist_manifest,
    utc_now,
    isoformat,
)
from src_common.pass_0_preflight import run_preflight_checks
from src_common.pass_a_toc_parser import process_pass_a
from src_common.pass_b_logical_splitter import process_pass_b
from src_common.pass_c_extraction import process_pass_c
from src_common.pass_d_vector_enrichment import process_pass_d
from src_common.pass_e_graph_builder import process_pass_e
from src_common.pass_f_finalizer import process_pass_f
from src_common.pass_g_hgrn_consistency import run_hgrn_consistency_check

logger = get_logger(__name__)


class PipelineError(Exception):
    """Pipeline execution error."""


class IngestionPipeline:
    """MVP v2 Pass 0?G ingestion pipeline coordinator."""

    def __init__(self, job_id: str, source_file: Path, env_root: Path):
        self.job_id = job_id
        self.source_file = source_file
        self.env_root = env_root
        self.env_validator = get_environment_validator()
        self.environment = self.env_validator.current_env
        self.job_dir = env_root / "artifacts" / job_id
        self.manifest_path = self.job_dir / "manifest.json"
        self.tool_versions = gather_tool_versions()
        self.manifest = create_base_manifest(job_id, self.environment, source_file, self.tool_versions)
        self.current_pass: str = ""
        self._artifact_index: set[str] = set()
        self._pipeline_clock: Optional[float] = None

    async def execute(self) -> Dict[str, Any]:
        """Execute full Pass 0?G pipeline and return manifest."""
        logger.info("Starting ingestion pipeline", extra={"job_id": self.job_id})
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self._pipeline_clock = time.perf_counter()
        self._write_manifest()

        try:
            await self._run_pass_0()
            if self.manifest["status"] == "skipped":
                self._finalize_run(status="skipped")
                self._write_manifest()
                return self.manifest

            await self._run_pass_a()
            await self._run_pass_b()
            await self._run_pass_c()
            await self._run_pass_d()
            await self._run_pass_e()
            await self._run_pass_f()
            await self._run_pass_g()

            self._finalize_run(status="completed")
            self._write_manifest()
            logger.info("Pipeline completed", extra={"job_id": self.job_id})
            return self.manifest

        except Exception as exc:  # noqa: BLE001
            logger.error("Pipeline failed", extra={"job_id": self.job_id, "error": str(exc)})
            self._record_pipeline_failure(exc)
            self._finalize_run(status="failed")
            self._write_manifest()
            raise PipelineError(f"Pipeline execution failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Pass helpers

    async def _run_pass_0(self) -> None:
        self.current_pass = "pass_0_preflight"
        started_at = utc_now()
        timer = time.perf_counter()
        logger.info("Pass 0: preflight start", extra={"job_id": self.job_id})

        preflight_result = run_preflight_checks(self.source_file)
        duration_ms = int((time.perf_counter() - timer) * 1000)

        pass_details: Dict[str, Any] = {
            "file_sha": preflight_result.file_sha,
            "page_count": preflight_result.page_count,
            "duplicate": preflight_result.should_skip,
            "reason": preflight_result.reason,
        }

        self.manifest["source"].update(
            {
                "file_sha": preflight_result.file_sha,
                "page_count": preflight_result.page_count,
            }
        )

        if preflight_result.should_skip:
            entry = self._build_pass_entry("skipped", started_at, duration_ms, pass_details, [])
            self.manifest["passes"][self.current_pass] = entry
            self.manifest["status"] = "skipped"
            self.manifest["skip_reason"] = preflight_result.reason or "duplicate_content"
            self.manifest["pipeline"]["completed_at"] = isoformat(utc_now())
            self.manifest["run_summary"]["passes_completed"] = 0
            self._write_manifest()
            logger.info("Preflight detected duplicate content; skipping pipeline", extra={"job_id": self.job_id})
            return

        entry = self._build_pass_entry("completed", started_at, duration_ms, pass_details, [])
        self.manifest["passes"][self.current_pass] = entry
        self._write_manifest()
        logger.info(
            "Preflight completed",
            extra={"job_id": self.job_id, "sha": preflight_result.file_sha, "pages": preflight_result.page_count},
        )

    async def _run_pass_a(self) -> None:
        self._run_sync_pass(
            pass_name="pass_a_toc",
            executor=lambda: process_pass_a(
                self.job_dir / self.source_file.name,
                self.job_dir,
                self.job_id,
                self.environment,
                force_dict_init=False,
            ),
            setup=self._prepare_job_source,
        )

    async def _run_pass_b(self) -> None:
        self._run_sync_pass(
            pass_name="pass_b_split",
            executor=lambda: process_pass_b(
                self.job_dir / self.source_file.name,
                self.job_dir,
                self.job_id,
                env=self.environment,
            ),
        )

    async def _run_pass_c(self) -> None:
        self._run_sync_pass(
            pass_name="pass_c_extraction",
            executor=lambda: process_pass_c(
                self.job_dir / self.source_file.name,
                self.job_dir,
                self.job_id,
                env=self.environment,
            ),
        )

    async def _run_pass_d(self) -> None:
        self._run_sync_pass(
            pass_name="pass_d_embeddings",
            executor=lambda: process_pass_d(
                self.job_dir,
                self.job_id,
                env=self.environment,
            ),
        )

    async def _run_pass_e(self) -> None:
        self._run_sync_pass(
            pass_name="pass_e_graph",
            executor=lambda: process_pass_e(
                self.job_dir,
                self.job_id,
                env=self.environment,
            ),
        )

    async def _run_pass_f(self) -> None:
        self._run_sync_pass(
            pass_name="pass_f_validation",
            executor=lambda: process_pass_f(
                self.job_dir,
                self.job_id,
                env=self.environment,
            ),
        )

    async def _run_pass_g(self) -> None:
        self._run_sync_pass(
            pass_name="pass_g_hgrn",
            executor=lambda: run_hgrn_consistency_check(
                self.job_dir,
                env=self.environment,
            ),
        )

    # ------------------------------------------------------------------
    # Internal helpers

    def _run_sync_pass(
        self,
        pass_name: str,
        executor,
        setup=None,
    ) -> None:
        """Execute a synchronous pass and record manifest metadata."""
        self.current_pass = pass_name
        started_at = utc_now()
        timer = time.perf_counter()
        logger.info("Pass start", extra={"job_id": self.job_id, "pass": pass_name})

        try:
            if setup:
                setup()
            result = executor()
            duration_ms = int((time.perf_counter() - timer) * 1000)
            artifacts = getattr(result, "artifacts", None) if result is not None else None
            self.manifest["passes"][pass_name] = self._build_pass_entry(
                status="completed",
                started_at=started_at,
                duration_ms=duration_ms,
                details=dataclass_to_dict(result),
                artifacts=artifacts,
                pass_name=pass_name,
            )
            self._write_manifest()
            logger.info("Pass completed", extra={"job_id": self.job_id, "pass": pass_name, "duration_ms": duration_ms})
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.perf_counter() - timer) * 1000)
            self.manifest["passes"][pass_name] = self._build_pass_entry(
                status="failed",
                started_at=started_at,
                duration_ms=duration_ms,
                details={"error": str(exc)},
                artifacts=[],
                pass_name=pass_name,
            )
            self.manifest["status"] = "failed"
            self.manifest["failed_pass"] = pass_name
            self._write_manifest()
            logger.error("Pass failed", extra={"job_id": self.job_id, "pass": pass_name, "error": str(exc)})
            raise

    def _prepare_job_source(self) -> None:
        """Ensure the source PDF is present in the job directory."""
        target = self.job_dir / self.source_file.name
        if not target.exists():
            shutil.copy2(self.source_file, target)

    def _build_pass_entry(
        self,
        status: str,
        started_at: datetime,
        duration_ms: int,
        details: Dict[str, Any],
        artifacts,
        pass_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        completed_at = utc_now()
        artifact_meta = compute_artifact_metadata(self.job_dir, artifacts or [], pass_name or self.current_pass)
        self._register_artifacts(artifact_meta)
        return {
            "status": status,
            "started_at": isoformat(started_at),
            "completed_at": isoformat(completed_at),
            "duration_ms": duration_ms,
            "details": details,
            "artifacts": artifact_meta,
        }

    def _register_artifacts(self, artifacts: List[Dict[str, Any]]) -> None:
        for artifact in artifacts:
            key = artifact["path"]
            if key in self._artifact_index:
                continue
            self._artifact_index.add(key)
            self.manifest["artifacts"].append(artifact)

    def _record_pipeline_failure(self, exc: Exception) -> None:
        self.manifest["status"] = "failed"
        self.manifest["error"] = str(exc)
        if self.current_pass:
            self.manifest["failed_pass"] = self.current_pass

    def _finalize_run(self, status: str) -> None:
        completed = utc_now()
        if self._pipeline_clock is not None:
            total_ms = int((time.perf_counter() - self._pipeline_clock) * 1000)
            self.manifest["run_summary"]["total_duration_ms"] = total_ms
        self.manifest["run_summary"]["passes_completed"] = sum(
            1 for entry in self.manifest["passes"].values() if entry["status"] == "completed"
        )
        self.manifest["run_summary"]["passes_failed"] = sum(
            1 for entry in self.manifest["passes"].values() if entry["status"] == "failed"
        )
        self.manifest["pipeline"]["completed_at"] = isoformat(completed)
        self.manifest["status"] = status
        self.manifest["completed_at"] = isoformat(completed)

    def _write_manifest(self) -> None:
        persist_manifest(self.manifest_path, self.manifest)


async def run_ingestion_pipeline(job_id: str, source_file: Path) -> Dict[str, Any]:
    """Convenience entry point for running the ingestion pipeline."""
    env_validator = get_environment_validator()
    env_root = Path(env_validator.get_environment_root())
    pipeline = IngestionPipeline(job_id, source_file, env_root)
    return await pipeline.execute()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        job = sys.argv[1]
        file_path = Path(sys.argv[2])
        asyncio.run(run_ingestion_pipeline(job, file_path))


