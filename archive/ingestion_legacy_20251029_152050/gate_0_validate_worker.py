#!/usr/bin/env python3
"""
gate_0_validate_worker.py - Async worker for Gate 0 Validation stage
=====================================================================

Polls job queue for jobs with computed hashes, queries Cassandra to check
if document already exists, and routes based on validation result.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from async_job_utils import add_error, add_warning, update_job_status, write_json_atomic, get_job_status_path
from async_worker_base import AsyncWorkerBase
from path_utils import resolve_transfer_path


class Gate0ValidateWorker(AsyncWorkerBase):
    """Async worker for Gate 0 Validation (Cassandra chunk count check)."""

    stage_name = "gate_0_validate"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gate_0_check_dir = resolve_transfer_path("Gate_0_Check")
        self.gate_0_check_dir.mkdir(parents=True, exist_ok=True)
        self.db_manager_path = Path(__file__).parent / "db_manager.py"

    def load_checksum_file(self, sha256: str) -> Dict[str, Any]:
        """
        Load checksum file from Gate_0_Check directory.

        Args:
            sha256: SHA-256 hash

        Returns:
            Dict with document_id and chunks_upserted (0 if not found)
        """
        checksum_path = self.gate_0_check_dir / f"{sha256}.json"

        if not checksum_path.exists():
            return {
                "document_id": None,
                "chunks_upserted": 0,
                "file_found": False
            }

        try:
            with checksum_path.open('r', encoding='utf-8') as f:
                data = json.load(f)

            return {
                "document_id": data.get("document_id"),
                "chunks_upserted": int(data.get("chunks_upserted", 0)),
                "file_found": True,
                "sha256_from_file": data.get("sha256"),
                "pass_d_manifest": data.get("pass_d_manifest")
            }
        except Exception as e:
            self.logger.error(f"Failed to load checksum file: {e}")
            return {
                "document_id": None,
                "chunks_upserted": 0,
                "file_found": False
            }

    def get_cassandra_chunk_count(self, document_id: Optional[str]) -> int:
        """
        Query Cassandra via db_manager for chunk count.

        Args:
            document_id: Document ID to query

        Returns:
            Number of chunks in Cassandra (0 if not found)
        """
        if not document_id:
            return 0

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.db_manager_path),
                    "--count-document",
                    document_id,
                    "--cassandra-keyspace",
                    "ttrpg_vectors",
                    "--cassandra-table",
                    "embeddings",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                self.logger.error(f"db_manager query failed: {result.stderr}")
                return 0

            # Parse output for chunk count
            chunk_count = 0
            in_manifest_section = False

            for raw_line in result.stdout.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                if line.startswith("Manifest:"):
                    in_manifest_section = "not found" not in line.lower()
                    continue

                if in_manifest_section and line.startswith("Chunk Count:"):
                    count_str = line.split(":", 1)[1].strip().split(" ")[0].replace(",", "")
                    try:
                        chunk_count = int(count_str)
                    except ValueError:
                        pass
                    break

            return chunk_count

        except Exception as e:
            self.logger.error(f"Failed to query Cassandra: {e}")
            return 0

    def determine_validation_status(self, expected_count: int, actual_count: int) -> str:
        """
        Determine validation status based on chunk counts.

        Args:
            expected_count: Expected chunks from Gate_0_Check
            actual_count: Actual chunks in Cassandra

        Returns:
            One of: "valid", "mismatch", "unprocessed", "failed"
        """
        difference = actual_count - expected_count

        if difference == 0 and expected_count > 0:
            # Perfect match
            return "valid"
        elif difference == -1 and expected_count == 0 and actual_count == 0:
            # Unprocessed (both 0)
            return "unprocessed"
        elif difference != 0:
            # Mismatch detected
            return "mismatch"
        else:
            # Shouldn't reach here, but handle gracefully
            return "unprocessed"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Gate 0 Validation job: compare expected vs actual chunk counts.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if successful (regardless of validation result)
        """
        try:
            # Get SHA-256 hash from job status
            sha256_hash = status.get("sha256_hash")
            if not sha256_hash:
                self.logger.error("Job status missing 'sha256_hash' field")
                add_error(status, "Missing sha256_hash in job status", self.stage_name)
                return False

            document_id = status.get("document_id")
            if not document_id:
                self.logger.error("Job status missing 'document_id' field")
                add_error(status, "Missing document_id in job status", self.stage_name)
                return False

            self.logger.info(f"Validating document_id: {document_id}")

            # Load checksum file (expected count)
            checksum_data = self.load_checksum_file(sha256_hash)
            expected_count = checksum_data.get("chunks_upserted", 0)

            self.logger.info(f"Expected chunks from checksum file: {expected_count}")

            # Query Cassandra (actual count)
            actual_count = self.get_cassandra_chunk_count(document_id)

            self.logger.info(f"Actual chunks in Cassandra: {actual_count}")

            # Determine validation status
            validation_status = self.determine_validation_status(expected_count, actual_count)

            self.logger.info(f"Validation result: {validation_status}")

            # Update job status with validation results
            status = update_job_status(status, {
                "validation_status": validation_status,
                "expected_chunk_count": expected_count,
                "actual_chunk_count": actual_count,
                "chunk_count_difference": actual_count - expected_count,
                "checksum_file_found": checksum_data.get("file_found", False)
            })

            # Add warnings or notes based on result
            if validation_status == "valid":
                self.logger.info(f"Document {document_id} already processed, will skip remaining stages")
                add_warning(status, f"Document already processed (chunks match: {actual_count})", self.stage_name)
            elif validation_status == "mismatch":
                self.logger.warning(f"Chunk count mismatch (expected: {expected_count}, actual: {actual_count})")
                add_warning(status, f"Chunk count mismatch, will cleanup and reprocess", self.stage_name)
            elif validation_status == "unprocessed":
                self.logger.info(f"Document {document_id} not yet processed, continuing pipeline")

            # Save updated status
            status_path = get_job_status_path(job_dir)
            write_json_atomic(status_path, status)

            return True

        except Exception as e:
            self.logger.exception(f"Failed to process Gate 0 Validation: {e}")
            add_error(status, f"Gate 0 Validation failed: {str(e)}", self.stage_name)
            # Set validation_status to failed so routing knows what to do
            status["validation_status"] = "failed"
            status_path = get_job_status_path(job_dir)
            write_json_atomic(status_path, status)
            return False


if __name__ == "__main__":
    Gate0ValidateWorker.main()
