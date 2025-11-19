#!/usr/bin/env python3
"""
unstructured_job_worker.py - Async Pass A/B/C job processor
================================================================

Watches the shared Transfer Station jobs directory for queued Unstructured
processing jobs, claims them, executes Pass A/B/C workflows, and writes
status updates and metrics that the ingestion wrapper can poll.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import IngestionConfig
from path_utils import resolve_transfer_path
from doc_splitter import DocumentSplitterError, get_splitter

try:
    from ingestion import pass_c_parsing
except ImportError:
    # Allow running when executed inside the package directory
    import pass_c_parsing  # type: ignore


SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_JOBS_ROOT = resolve_transfer_path("jobs/unstructured")
DEFAULT_LOG_DIR = resolve_transfer_path("Logs/unstructured")
PYTHON_EXECUTABLE = Path(sys.executable)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


class UnstructuredJobWorker:
    """Polls the job directory and executes Pass A/B/C workloads."""

    def __init__(
        self,
        jobs_root: Path = DEFAULT_JOBS_ROOT,
        log_dir: Path = DEFAULT_LOG_DIR,
        poll_interval: Optional[int] = None,
        log_level: str = "INFO",
    ) -> None:
        self.jobs_root = ensure_directory(jobs_root)
        self.log_dir = ensure_directory(log_dir)
        self.poll_interval = poll_interval or max(
            2, getattr(IngestionConfig, "UNSTRUCTURED_JOB_POLL_INTERVAL", 5)
        )
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"

        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )
        self.logger = logging.getLogger("unstructured_worker")
        self.logger.info(
            "Worker starting (jobs_root=%s, poll_interval=%ss)",
            self.jobs_root,
            self.poll_interval,
        )

    def run(self, once: bool = False) -> None:
        """Run the worker loop indefinitely (or a single iteration when once=True)."""
        try:
            while True:
                job_dir = self._claim_job()
                if job_dir is None:
                    if once:
                        self.logger.debug("No queued jobs found; exiting (--once).")
                        return
                    time.sleep(self.poll_interval)
                    continue

                try:
                    self._process_job(job_dir)
                except Exception as exc:  # pragma: no cover - defensive logging
                    self.logger.exception("Job %s crashed: %s", job_dir.name, exc)

                if once:
                    return
        except KeyboardInterrupt:
            self.logger.info("Worker interrupted; shutting down.")

    # ------------------------------------------------------------------ #
    # Job coordination                                                   #
    # ------------------------------------------------------------------ #

    def _claim_job(self) -> Optional[Path]:
        """Attempt to claim a queued job directory."""
        for job_dir in sorted(self.jobs_root.iterdir()):
            if not job_dir.is_dir():
                continue

            manifest_path = job_dir / "manifest.json"
            status_path = job_dir / "status.json"

            if not manifest_path.exists() or not status_path.exists():
                continue

            try:
                status = load_json(status_path)
            except (json.JSONDecodeError, OSError) as exc:
                self.logger.error("Skipping job %s: unreadable status (%s)", job_dir.name, exc)
                continue

            if status.get("state") != "queued":
                continue

            marker_path = job_dir / "queued.marker"
            claim_marker = job_dir / f"in_progress.{self.worker_id}.marker"
            marker_claimed = False
            try:
                if marker_path.exists():
                    marker_path.rename(claim_marker)
                    marker_claimed = True
                else:
                    claim_marker.touch(exist_ok=False)
                    marker_claimed = True
            except FileExistsError:
                continue
            except OSError as exc:
                self.logger.debug("Unable to claim marker for %s: %s", job_dir.name, exc)
                continue

            now_iso = datetime.utcnow().isoformat() + "Z"
            status.update(
                {
                    "state": "in_progress",
                    "worker": self.worker_id,
                    "claimed_at": now_iso,
                    "updated_at": now_iso,
                    "current_stage": None,
                    "stages": status.get("stages") or {},
                }
            )

            try:
                write_json_atomic(status_path, status)
            except OSError as exc:
                self.logger.error("Failed to update status for %s: %s", job_dir.name, exc)
                if marker_claimed:
                    claim_marker.unlink(missing_ok=True)
                continue

            self.logger.info("Claimed job %s", job_dir.name)
            return job_dir

        return None

    # ------------------------------------------------------------------ #
    # Job execution                                                      #
    # ------------------------------------------------------------------ #

    def _process_job(self, job_dir: Path) -> None:
        manifest_path = job_dir / "manifest.json"
        status_path = job_dir / "status.json"
        claim_markers = list(job_dir.glob("in_progress.*.marker"))

        manifest = load_json(manifest_path)
        status = load_json(status_path)
        job_id = manifest.get("job_id", job_dir.name)

        job_log_handler = logging.FileHandler(
            self.log_dir / f"{job_id}.log", encoding="utf-8"
        )
        job_log_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        self.logger.addHandler(job_log_handler)

        job_statistics: Dict[str, Any] = {"stages": {}}
        outputs: Dict[str, str] = {}

        try:
            self.logger.info("Starting job %s", job_id)
            status["state"] = "in_progress"
            status["started_at"] = status.get("started_at") or datetime.utcnow().isoformat() + "Z"
            status["updated_at"] = datetime.utcnow().isoformat() + "Z"
            write_json_atomic(status_path, status)

            options = manifest.get("options", {})
            single_chunk = bool(options.get("single_chunk"))

            (
                pass_a_elements,
                pass_a_metrics,
            ) = self._execute_stage(
                job_id,
                "pass_a",
                status,
                status_path,
                job_statistics,
                lambda: self._run_pass_a(manifest),
            )
            outputs["pass_a_elements"] = str(pass_a_elements)

            (
                pass_a_metadata,
                pass_a_meta_metrics,
            ) = self._execute_stage(
                job_id,
                "pass_a_metadata",
                status,
                status_path,
                job_statistics,
                lambda: self._run_pass_a_metadata(manifest, pass_a_elements),
            )
            outputs["pass_a_metadata"] = str(pass_a_metadata)

            (
                pass_b_manifest,
                pass_b_manifest_data,
                pass_b_manifest_metrics,
            ) = self._execute_stage(
                job_id,
                "pass_b_splitter",
                status,
                status_path,
                job_statistics,
                lambda: self._create_single_chunk_manifest(manifest) if single_chunk else self._run_pass_b_splitter(manifest, pass_a_metadata),
            )
            outputs["pass_b_manifest"] = str(pass_b_manifest)

            (
                _,
                pass_b_chunk_metrics,
            ) = self._execute_stage(
                job_id,
                "pass_b_chunker",
                status,
                status_path,
                job_statistics,
                lambda: self._run_pass_b_chunker(manifest, pass_b_manifest, pass_b_manifest_data),
            )

            (
                pass_c_stage_metrics,
            ) = self._execute_stage(
                job_id,
                "pass_c_parsing",
                status,
                status_path,
                job_statistics,
                lambda: self._run_pass_c_chunks(manifest, pass_b_manifest_data),
            )

            (
                pass_c_metadata_path,
                pass_c_meta_metrics,
            ) = self._execute_stage(
                job_id,
                "pass_c_metadata",
                status,
                status_path,
                job_statistics,
                lambda: self._run_pass_c_metadata(manifest, pass_b_manifest),
            )
            outputs["pass_c_metadata"] = str(pass_c_metadata_path)

            job_statistics.update(
                {
                    "elements_count": pass_a_metrics.get("elements_count"),
                    "chunk_count": pass_b_chunk_metrics.get("chunks_created"),
                    "pass_c_elements": pass_c_stage_metrics.get("elements_generated"),
                    "unique_terms": pass_c_meta_metrics.get("unique_terms"),
                }
            )

            status.update(
                {
                    "state": "completed",
                    "completed_at": datetime.utcnow().isoformat() + "Z",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "current_stage": None,
                    "outputs": outputs,
                    "statistics": job_statistics,
                }
            )
            write_json_atomic(status_path, status)
            self.logger.info("Job %s completed successfully", job_id)
        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "state": "failed",
                    "error": error_message,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "current_stage": status.get("current_stage"),
                }
            )
            write_json_atomic(status_path, status)
            self.logger.error("Job %s failed: %s", job_id, error_message, exc_info=True)
            raise
        finally:
            for marker in claim_markers:
                marker.unlink(missing_ok=True)
            self.logger.removeHandler(job_log_handler)
            job_log_handler.close()

    # ------------------------------------------------------------------ #
    # Stage execution helpers                                            #
    # ------------------------------------------------------------------ #

    def _execute_stage(
        self,
        job_id: str,
        stage_name: str,
        status: Dict[str, Any],
        status_path: Path,
        job_statistics: Dict[str, Any],
        func,
    ):
        """Execute a stage callable with status updates."""
        start_time = time.time()
        started_at = datetime.utcnow().isoformat() + "Z"

        status["current_stage"] = stage_name
        stages = status.setdefault("stages", {})
        stage_state = stages.setdefault(stage_name, {})
        stage_state.update({"status": "in_progress", "started_at": started_at})
        status["updated_at"] = started_at
        write_json_atomic(status_path, status)

        self.logger.info("[%s] Stage %s started", job_id, stage_name)

        try:
            result = func()
        except Exception as exc:
            duration = round(time.time() - start_time, 2)
            failed_at = datetime.utcnow().isoformat() + "Z"
            stage_state.update(
                {
                    "status": "failed",
                    "completed_at": failed_at,
                    "duration_seconds": duration,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            status["updated_at"] = failed_at
            write_json_atomic(status_path, status)

            job_statistics["stages"][stage_name] = {
                "duration_seconds": duration,
                "error": f"{type(exc).__name__}: {exc}",
            }

            self.logger.error(
                "[%s] Stage %s failed after %.2fs: %s",
                job_id,
                stage_name,
                duration,
                exc,
            )
            raise

        duration = round(time.time() - start_time, 2)
        completed_at = datetime.utcnow().isoformat() + "Z"
        metrics = result[-1] if isinstance(result, tuple) else result

        stage_state.update(
            {
                "status": "completed",
                "completed_at": completed_at,
                "duration_seconds": duration,
                "metrics": metrics if isinstance(metrics, dict) else {},
            }
        )
        status["updated_at"] = completed_at
        write_json_atomic(status_path, status)

        job_statistics["stages"][stage_name] = {
            "duration_seconds": duration,
            "metrics": stage_state.get("metrics", {}),
        }

        self.logger.info(
            "[%s] Stage %s completed in %.2fs", job_id, stage_name, duration
        )

        return result if isinstance(result, tuple) else (result,)

    # ------------------------------------------------------------------ #
    # Pass execution                                                     #
    # ------------------------------------------------------------------ #

    def _run_pass_a(self, manifest: Dict[str, Any]) -> Tuple[Path, Dict[str, Any]]:
        source = manifest["source"]
        options = manifest.get("options", {})
        targets = manifest["targets"]

        input_path = Path(source.get("toc_path") or source["path"])
        pass_a_dir = ensure_directory(Path(targets["pass_a"]))

        elements_path = pass_a_dir / f"{input_path.stem}_elements.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_a_unstructured.py"),
            str(input_path),
            "-o",
            str(pass_a_dir),
            "-l",
            options.get("language", "eng"),
            "-s",
            options.get("strategy", "hi_res"),
        ]

        extra_env = {"UNSTRUCTURED_USE_LOCAL_PIPELINE": "1"}
        self._run_command(command, "pass_a", extra_env=extra_env)

        try:
            elements = load_json(elements_path)
            elements_count = len(elements) if isinstance(elements, list) else 0
        except (json.JSONDecodeError, OSError):
            elements_count = 0

        metrics = {"elements_count": elements_count}
        return elements_path, metrics

    def _run_pass_a_metadata(
        self,
        manifest: Dict[str, Any],
        elements_path: Path,
    ) -> Tuple[Path, Dict[str, Any]]:
        source = manifest["source"]
        targets = manifest["targets"]

        pass_a_dir = ensure_directory(Path(targets["pass_a"]))
        marker_path = Path(source["marker_path"])
        metadata_path = pass_a_dir / elements_path.name.replace("_elements.json", "_metadata.json")

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_a_metadata.py"),
            str(elements_path),
        ]

        if marker_path.exists():
            command.extend(["--gate-marker", str(marker_path)])

        self._run_command(command, "pass_a_metadata")

        try:
            metadata = load_json(metadata_path)
            toc_entries = len(metadata.get("table_of_contents", [])) if isinstance(metadata, dict) else 0
        except (json.JSONDecodeError, OSError):
            toc_entries = 0

        metrics = {"toc_entries": toc_entries}
        return metadata_path, metrics

    def _create_single_chunk_manifest(
        self,
        manifest: Dict[str, Any],
    ) -> Tuple[Path, Dict[str, Any], Dict[str, Any]]:
        document_id = manifest["document_id"]
        source_path = Path(manifest["source"]["path"])
        targets = manifest["targets"]

        pass_b_dir = ensure_directory(Path(targets["pass_b"]))
        manifest_path = pass_b_dir / f"{document_id}_pass_b_manifest.json"

        total_pages = self._determine_total_pages(source_path)

        manifest_data: Dict[str, Any] = {
            "document_id": document_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "total_pages": total_pages,
            "parts": [
                {
                    "part": 1,
                    "start_page": 1,
                    "end_page": total_pages,
                }
            ],
        }

        write_json_atomic(manifest_path, manifest_data)
        metrics = {"parts": 1, "total_pages": total_pages}
        return manifest_path, manifest_data, metrics

    def _run_pass_b_splitter(
        self,
        manifest: Dict[str, Any],
        metadata_path: Path,
    ) -> Tuple[Path, Dict[str, Any], Dict[str, Any]]:
        document_id = manifest["document_id"]
        source_path = Path(manifest["source"]["path"])
        targets = manifest["targets"]

        pass_b_dir = ensure_directory(Path(targets["pass_b"]))
        manifest_path = pass_b_dir / f"{document_id}_pass_b_manifest.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_b_splitter.py"),
            str(source_path),
            str(metadata_path),
            "-o",
            str(pass_b_dir),
            "--prefix",
            document_id,
            "--output-file",
            str(manifest_path),
        ]

        self._run_command(command, "pass_b_splitter")

        manifest_data = load_json(manifest_path)
        parts = manifest_data.get("parts", [])
        metrics = {
            "parts": len(parts),
            "total_pages": manifest_data.get("total_pages"),
        }

        return manifest_path, manifest_data, metrics

    def _run_pass_b_chunker(
        self,
        manifest: Dict[str, Any],
        manifest_path: Path,
        manifest_data: Dict[str, Any],
    ) -> Tuple[None, Dict[str, Any]]:
        document_id = manifest["document_id"]
        source_path = Path(manifest["source"]["path"])
        targets = manifest["targets"]

        pass_b_dir = ensure_directory(Path(targets["pass_b"]))

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_b_chunker.py"),
            str(source_path),
            str(manifest_path),
            "-o",
            str(pass_b_dir),
            "--prefix",
            document_id,
        ]

        self._run_command(command, "pass_b_chunker")

        # Count generated chunk files
        suffix = source_path.suffix
        parts = manifest_data.get("parts", [])
        chunk_count = 0
        for part in parts:
            part_number = int(part.get("part") or part.get("part_number") or 0)
            chunk_name = f"{document_id}_part{part_number:02d}{suffix}"
            if (pass_b_dir / chunk_name).exists():
                chunk_count += 1

        metrics = {"chunks_created": chunk_count or len(parts)}
        return None, metrics

    def _run_pass_c_chunks(
        self,
        manifest: Dict[str, Any],
        manifest_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        document_id = manifest["document_id"]
        targets = manifest["targets"]
        options = manifest.get("options", {})

        pass_b_dir = Path(targets["pass_b"])
        pass_c_dir = ensure_directory(Path(targets["pass_c"]))

        strategy = options.get("strategy", "hi_res")
        language = options.get("language", "eng")

        parts = manifest_data.get("parts", [])
        chunk_metrics: List[Dict[str, Any]] = []
        total_elements = 0

        for part in parts:
            part_number = int(part.get("part") or part.get("part_number") or 0)
            chunk_path = pass_c_parsing.discover_chunk_path(pass_b_dir, document_id, part_number)
            if not chunk_path:
                raise FileNotFoundError(f"Chunk file missing for part {part_number}")

            chunk_start = time.time()
            self.logger.info("Processing chunk %s", chunk_path.name)

            result = pass_c_parsing.run_pass_a_unstructured(
                chunk_path=chunk_path,
                output_dir=pass_c_dir,
                strategy=strategy,
                language=language,
                toc_only=False,
                max_pages=0,
            )

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                raise RuntimeError(
                    f"pass_a_unstructured failed for {chunk_path.name} (rc={result.returncode}): {stderr}"
                )

            duration = round(time.time() - chunk_start, 2)
            self.logger.info("Completed chunk %s in %.2fs", chunk_path.name, duration)

            chunk_output = pass_c_dir / f"{chunk_path.stem}_elements.json"
            try:
                elements = load_json(chunk_output)
                total_elements += len(elements) if isinstance(elements, list) else 0
            except (json.JSONDecodeError, OSError):
                pass

            chunk_metrics.append(
                {
                    "chunk": chunk_path.name,
                    "duration_seconds": duration,
                }
            )

        metrics = {
            "chunks_processed": len(chunk_metrics),
            "chunk_durations": chunk_metrics,
            "elements_generated": total_elements,
        }
        return metrics

    def _run_pass_c_metadata(
        self,
        manifest: Dict[str, Any],
        pass_b_manifest: Path,
    ) -> Tuple[Path, Dict[str, Any]]:
        document_id = manifest["document_id"]
        targets = manifest["targets"]
        source = manifest["source"]

        pass_c_dir = ensure_directory(Path(targets["pass_c"]))
        metadata_path = pass_c_dir / f"{document_id}_pass_c_metadata.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_c_metadata.py"),
            str(pass_b_manifest),
            "--pass-c-dir",
            str(pass_c_dir),
        ]

        marker_path = Path(source["marker_path"])
        if marker_path.exists():
            command.extend(["--gate-marker", str(marker_path)])

        self._run_command(command, "pass_c_metadata")

        try:
            metadata = load_json(metadata_path)
            statistics = metadata.get("statistics") if isinstance(metadata, dict) else {}
            metrics = {
                "total_elements": statistics.get("total_elements"),
                "unique_terms": statistics.get("unique_terms"),
                "unique_categories": statistics.get("unique_categories"),
            }
        except (json.JSONDecodeError, OSError):
            metrics = {}

        return metadata_path, metrics

    # ------------------------------------------------------------------ #
    # Utilities                                                          #
    # ------------------------------------------------------------------ #

    def _determine_total_pages(self, source_path: Path) -> int:
        """Return total page count for a document using doc_splitter helpers."""
        try:
            splitter = get_splitter(source_path)
            return splitter.get_total_pages()
        except DocumentSplitterError as exc:
            raise RuntimeError(f"Unable to determine total pages for {source_path.name}: {exc}") from exc

    def _run_command(self, command: List[str], stage: str, extra_env: Optional[Dict[str, str]] = None) -> None:
        """Run a subprocess command and raise an error on failure."""
        self.logger.debug("[%s] Command: %s", stage, " ".join(command))
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(command, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            error_message = stderr or stdout or "Unknown error"
            raise RuntimeError(f"{stage} failed: {error_message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unstructured async job worker",
        add_help=True,
    )
    parser.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_ROOT, help="Jobs directory to watch")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="Directory for worker logs")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=None,
        help="Poll interval for scanning jobs (seconds)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        help="Logging level (INFO, DEBUG, ...)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job and then exit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    worker = UnstructuredJobWorker(
        jobs_root=args.jobs_dir,
        log_dir=args.log_dir,
        poll_interval=args.poll_interval,
        log_level=args.log_level,
    )
    worker.run(once=args.once)
    return 0


if __name__ == "__main__":
    sys.exit(main())
