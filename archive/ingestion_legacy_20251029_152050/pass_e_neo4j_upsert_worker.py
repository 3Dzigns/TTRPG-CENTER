#!/usr/bin/env python3
"""
pass_e_neo4j_upsert_worker.py - Async Worker for Pass E Neo4j Upsert
====================================================================

Async worker that wraps pass_e_neo4j_upsert.py to upsert knowledge graph
nodes and edges into Neo4j.

Usage:
    python pass_e_neo4j_upsert_worker.py [options]

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


class PassENeo4jUpsertWorker(AsyncWorkerBase):
    """Async worker for Pass E Neo4j upsert."""

    stage_name = "pass_e_neo4j_upsert"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Pass E Neo4j upsert for a job.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Get required file paths from status
            graph_file = status.get("pass_e_graph_output")
            if not graph_file:
                self.logger.error(f"Job {job_dir.name} missing pass_e_graph_output path")
                return False

            graph_path = Path(graph_file)
            if not graph_path.exists():
                self.logger.error(f"Graph file not found: {graph_path}")
                return False

            # Build command for pass_e_neo4j_upsert.py
            script_path = Path(__file__).parent / "pass_e_neo4j_upsert.py"

            cmd = [
                sys.executable,
                str(script_path),
                str(graph_path),
                "--create-indexes"  # Ensure indexes are created
            ]

            # Add gate marker if available for rebuild mode
            gate_marker = status.get("gate_0_marker_file")
            if gate_marker and Path(gate_marker).exists():
                cmd.extend(["--gate-marker", str(gate_marker)])

            # Check for rebuild mode from status
            if status.get("rebuild_mode") or status.get("force_reprocess"):
                self.logger.info("Rebuild mode enabled - will clean existing Neo4j entries")

            self.logger.info(f"Running: {' '.join(cmd)}")

            # Execute pass_e_neo4j_upsert.py
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=1800  # 30 minute timeout for Neo4j operations
            )

            # Log output
            if result.stdout:
                self.logger.info(f"Neo4j upsert output:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")

            if result.returncode != 0:
                self.logger.error(f"pass_e_neo4j_upsert.py failed with exit code {result.returncode}")
                # Update status with error
                from async_job_utils import add_error, write_json_atomic, get_job_status_path
                status = add_error(status, f"pass_e_neo4j_upsert.py exit code {result.returncode}")
                write_json_atomic(get_job_status_path(job_dir), status)
                return False

            # Update job status
            from async_job_utils import write_json_atomic, get_job_status_path
            status["neo4j_upserted"] = True
            write_json_atomic(get_job_status_path(job_dir), status)

            self.logger.info(f"Neo4j upsert completed successfully")
            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"pass_e_neo4j_upsert.py timed out after 30 minutes")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error in Neo4j upsert: {e}")
            return False


if __name__ == "__main__":
    PassENeo4jUpsertWorker.main()
