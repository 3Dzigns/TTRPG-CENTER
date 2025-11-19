#!/usr/bin/env python3
"""
pass_d_checksum_worker.py - Async Worker for Pass D Checksum Writing
====================================================================

Async worker that wraps pass_d_checksum.py to write checksum records
containing the number of chunks upserted to Cassandra.

Usage:
    python pass_d_checksum_worker.py [options]

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


class PassDChecksumWorker(AsyncWorkerBase):
    """Async worker for Pass D checksum writing."""

    stage_name = "pass_d_checksum"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Pass D checksum writing for a job.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Get required file paths from status
            manifest_file = status.get("pass_d_manifest_output")
            if not manifest_file:
                self.logger.error(f"Job {job_dir.name} missing pass_d_manifest_output path")
                return False

            manifest_path = Path(manifest_file)
            if not manifest_path.exists():
                self.logger.error(f"Manifest file not found: {manifest_path}")
                return False

            # Build command for pass_d_checksum.py
            script_path = Path(__file__).parent / "pass_d_checksum.py"

            cmd = [
                sys.executable,
                str(script_path),
                str(manifest_path)
            ]

            self.logger.info(f"Running: {' '.join(cmd)}")

            # Execute pass_d_checksum.py
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60  # 1 minute timeout
            )

            # Log output
            if result.stdout:
                self.logger.info(f"Checksum output:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")

            if result.returncode != 0:
                self.logger.error(f"pass_d_checksum.py failed with exit code {result.returncode}")
                # Update status with error
                from async_job_utils import add_error, write_json_atomic, get_job_status_path
                status = add_error(status, f"pass_d_checksum.py exit code {result.returncode}")
                write_json_atomic(get_job_status_path(job_dir), status)
                return False

            # Parse checksum file path from output
            # Output format: "Checksum written: /path/to/checksum.json (N chunks, checksum=X)"
            checksum_path = None
            for line in result.stdout.split('\n'):
                if line.startswith("Checksum written:"):
                    parts = line.split()
                    if len(parts) >= 3:
                        checksum_path = Path(parts[2])
                        break

            if checksum_path and checksum_path.exists():
                # Update job status with checksum file path
                from async_job_utils import write_json_atomic, get_job_status_path
                status["pass_d_checksum_output"] = str(checksum_path)
                status["checksum_written"] = True
                write_json_atomic(get_job_status_path(job_dir), status)

                self.logger.info(f"Checksum writing completed: {checksum_path.name}")
            else:
                self.logger.warning("Could not determine checksum file path from output")
                # Still consider it successful if exit code was 0
                from async_job_utils import write_json_atomic, get_job_status_path
                status["checksum_written"] = True
                write_json_atomic(get_job_status_path(job_dir), status)

            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"pass_d_checksum.py timed out after 1 minute")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error in checksum writing: {e}")
            return False


if __name__ == "__main__":
    PassDChecksumWorker.main()
