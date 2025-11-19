#!/usr/bin/env python3
"""
pass_e_graph_builder_worker.py - Async Worker for Pass E Graph Building
========================================================================

Async worker that wraps pass_e_graph_builder.py to build knowledge graph
structure from Cassandra vectors and Pass C metadata.

Usage:
    python pass_e_graph_builder_worker.py [options]

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


class PassEGraphBuilderWorker(AsyncWorkerBase):
    """Async worker for Pass E graph building."""

    stage_name = "pass_e_graph_builder"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Pass E graph building for a job.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Get required file paths from status
            pass_d_manifest = status.get("pass_d_manifest_output")
            if not pass_d_manifest:
                self.logger.error(f"Job {job_dir.name} missing pass_d_manifest_output path")
                return False

            manifest_path = Path(pass_d_manifest)
            if not manifest_path.exists():
                self.logger.error(f"Pass D manifest not found: {manifest_path}")
                return False

            # Build command for pass_e_graph_builder.py
            script_path = Path(__file__).parent / "pass_e_graph_builder.py"

            cmd = [
                sys.executable,
                str(script_path),
                str(manifest_path)
            ]

            # Note: Similarity computation disabled by default for performance
            # Add --enable-similarity flag if needed based on status
            enable_similarity = status.get("enable_similarity", False)
            if enable_similarity:
                cmd.append("--enable-similarity")
                self.logger.info("Similarity edge computation ENABLED")

            self.logger.info(f"Running: {' '.join(cmd)}")

            # Execute pass_e_graph_builder.py
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=1800  # 30 minute timeout for graph building
            )

            # Log output
            if result.stdout:
                self.logger.info(f"Graph builder output:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")

            if result.returncode != 0:
                self.logger.error(f"pass_e_graph_builder.py failed with exit code {result.returncode}")
                # Update status with error
                from async_job_utils import add_error, write_json_atomic, get_job_status_path
                status = add_error(status, f"pass_e_graph_builder.py exit code {result.returncode}")
                write_json_atomic(get_job_status_path(job_dir), status)
                return False

            # Determine graph file path
            document_id = status.get("document_id")
            if not document_id:
                self.logger.error("Missing document_id in status")
                return False

            output_dir = resolve_transfer_path("Pass_E_Out")
            graph_filename = f"{document_id}_graph.json"
            graph_path = output_dir / graph_filename

            if not graph_path.exists():
                self.logger.error(f"Graph file not created: {graph_path}")
                return False

            # Update job status with graph file path
            from async_job_utils import write_json_atomic, get_job_status_path
            status["pass_e_graph_output"] = str(graph_path)
            status["graph_built"] = True
            write_json_atomic(get_job_status_path(job_dir), status)

            self.logger.info(f"Graph building completed: {graph_path.name}")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"pass_e_graph_builder.py timed out after 30 minutes")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error in graph building: {e}")
            return False


if __name__ == "__main__":
    PassEGraphBuilderWorker.main()
