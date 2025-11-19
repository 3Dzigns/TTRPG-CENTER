#!/usr/bin/env python3
"""
pass_a_mongo_upsert_worker.py - Async Worker for Pass A dictionary upsert
=========================================================================

Wraps pass_a_mongo_upsert.py (now Postgres-backed) so Pass A metadata is
persisted automatically during the async pipeline.

Usage:
    python pass_a_mongo_upsert_worker.py [options]

Options:
    --jobs-dir DIR         Root directory for job queues
    --log-dir DIR          Directory for worker logs
    --poll-interval SECS   Seconds between queue polls (default: 5)
    --log-level LEVEL      Logging level (DEBUG|INFO|WARNING|ERROR)
    --once                 Process one job and exit (for testing)
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from async_worker_base import AsyncWorkerBase
from path_utils import resolve_transfer_path


class PassAMongoUpsertWorker(AsyncWorkerBase):
    """Async worker for Pass A dictionary upsert."""

    stage_name = "pass_a_mongo_upsert"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Pass A MongoDB upsert for a job.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Get required file paths from status
            elements_file = status.get("pass_a_unstructured_output")
            metadata_file = status.get("pass_a_metadata_output")

            if not elements_file:
                self.logger.error(f"Job {job_dir.name} missing pass_a_unstructured_output path")
                return False

            if not metadata_file:
                self.logger.error(f"Job {job_dir.name} missing pass_a_metadata_output path")
                return False

            elements_path = Path(elements_file)
            metadata_path = Path(metadata_file)

            if not elements_path.exists():
                self.logger.error(f"Elements file not found: {elements_path}")
                return False

            if not metadata_path.exists():
                self.logger.error(f"Metadata file not found: {metadata_path}")
                return False

            # Build command for pass_a_mongo_upsert.py
            script_path = Path(__file__).parent / "pass_a_mongo_upsert.py"

            cmd = [
                sys.executable,
                str(script_path),
                str(elements_path),
                str(metadata_path),
                "--stage", "initial"
            ]

            # Add gate marker if available for rebuild mode
            gate_marker = status.get("gate_0_marker_file")
            if gate_marker and Path(gate_marker).exists():
                cmd.extend(["--gate-marker", str(gate_marker)])

            # Check for rebuild mode from status
            if status.get("rebuild_mode") or status.get("force_reprocess"):
                self.logger.info("Rebuild mode enabled - will clean existing MongoDB entries")

            self.logger.info(f"Running: {' '.join(cmd)}")

            # Execute pass_a_mongo_upsert.py
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=600  # 10 minute timeout for database operations
            )

            # Log output
            if result.stdout:
                self.logger.info(f"Dictionary upsert output:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")

            if result.returncode != 0:
                self.logger.error(f"pass_a_mongo_upsert.py failed with exit code {result.returncode}")
                # Update status with error
                from async_job_utils import add_error, write_json_atomic, get_job_status_path
                status = add_error(status, f"pass_a_mongo_upsert.py exit code {result.returncode}")
                write_json_atomic(get_job_status_path(job_dir), status)
                return False

            # Update job status
            from async_job_utils import write_json_atomic, get_job_status_path
            status["dictionary_upserted"] = True
            status["dictionary_stage"] = "pass_a"
            write_json_atomic(get_job_status_path(job_dir), status)

            self.logger.info("Dictionary upsert completed successfully")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"pass_a_mongo_upsert.py timed out after 10 minutes")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error in dictionary upsert: {e}")
            return False


if __name__ == "__main__":
    PassAMongoUpsertWorker.main()
