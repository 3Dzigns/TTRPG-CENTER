#!/usr/bin/env python3
"""
pass_d_hayhooks_worker.py - Async Worker for Pass D Vector Embeddings
======================================================================

Async worker that wraps pass_d_hayhooks.py to generate OpenAI embeddings
and store vectors in Cassandra. This is the long-running hayhooks container operation.

Usage:
    python pass_d_hayhooks_worker.py [options]

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


class PassDHayhooksWorker(AsyncWorkerBase):
    """Async worker for Pass D hayhooks embedding generation."""

    stage_name = "pass_d_hayhooks"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Pass D embedding generation for a job.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Get required file paths from status
            pass_b_manifest = status.get("pass_b_manifest_output")
            if not pass_b_manifest:
                self.logger.error(f"Job {job_dir.name} missing pass_b_manifest_output path")
                return False

            manifest_path = Path(pass_b_manifest)
            if not manifest_path.exists():
                self.logger.error(f"Pass B manifest not found: {manifest_path}")
                return False

            # Build command for pass_d_hayhooks.py
            script_path = Path(__file__).parent / "pass_d_hayhooks.py"

            cmd = [
                sys.executable,
                str(script_path),
                str(manifest_path)
            ]

            # Add gate marker if available for rebuild mode
            gate_marker = status.get("gate_0_marker_file")
            if gate_marker and Path(gate_marker).exists():
                cmd.extend(["--gate-marker", str(gate_marker)])

            # Check for rebuild mode from status
            if status.get("rebuild_mode") or status.get("force_reprocess"):
                self.logger.info("Rebuild mode enabled - will clean existing Cassandra entries")

            self.logger.info(f"Running: {' '.join(cmd)}")
            self.logger.info("WARNING: This is a long-running operation (hayhooks processing)")

            # Execute pass_d_hayhooks.py with extended timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=7200  # 2 hour timeout for embedding generation
            )

            # Log output
            if result.stdout:
                self.logger.info(f"Hayhooks output:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")

            if result.returncode != 0:
                self.logger.error(f"pass_d_hayhooks.py failed with exit code {result.returncode}")
                # Update status with error
                from async_job_utils import add_error, write_json_atomic, get_job_status_path
                status = add_error(status, f"pass_d_hayhooks.py exit code {result.returncode}")
                write_json_atomic(get_job_status_path(job_dir), status)
                return False

            # Determine manifest file path
            document_id = status.get("document_id")
            if not document_id:
                self.logger.error("Missing document_id in status")
                return False

            output_dir = resolve_transfer_path("Pass_D_Out")
            manifest_filename = f"{document_id}_pass_d_manifest.json"
            manifest_output_path = output_dir / manifest_filename

            if not manifest_output_path.exists():
                self.logger.error(f"Pass D manifest not created: {manifest_output_path}")
                return False

            # Update job status with manifest file path
            from async_job_utils import write_json_atomic, get_job_status_path
            status["pass_d_manifest_output"] = str(manifest_output_path)
            status["embeddings_generated"] = True
            write_json_atomic(get_job_status_path(job_dir), status)

            self.logger.info(f"Embedding generation completed: {manifest_output_path.name}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"pass_d_hayhooks.py timed out after 2 hours")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error in embedding generation: {e}")
            return False


if __name__ == "__main__":
    PassDHayhooksWorker.main()
