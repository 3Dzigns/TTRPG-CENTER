#!/usr/bin/env python3
"""
gate_0_hash_worker.py - Async worker for Gate 0 Hash stage
===========================================================

Polls job queue for new source files, computes SHA-256 hash,
generates document_id, and routes to gate_0_validate stage.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict

from async_job_utils import add_error, update_job_status, write_json_atomic
from async_worker_base import AsyncWorkerBase
from path_utils import resolve_transfer_path


class Gate0HashWorker(AsyncWorkerBase):
    """Async worker for Gate 0 Hash computation."""

    stage_name = "gate_0_hash"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gate_0_out_dir = resolve_transfer_path("Gate_0_Out")
        self.gate_0_out_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename for use in document_id.

        Args:
            filename: Original filename (with or without extension)

        Returns:
            Sanitized filename (lowercase, alphanumeric + underscores)
        """
        # Remove extension
        name_without_ext = Path(filename).stem

        # Convert to lowercase
        sanitized = name_without_ext.lower()

        # Replace spaces and special characters with underscores
        sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        # Collapse multiple underscores
        sanitized = re.sub(r'_+', '_', sanitized)

        # Limit length to 100 characters
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip('_')

        return sanitized

    @staticmethod
    def compute_sha256(file_path: Path, chunk_size: int = 8192) -> str:
        """
        Compute SHA-256 hash of file.

        Args:
            file_path: Path to input file
            chunk_size: Buffer size for reading file (default: 8KB)

        Returns:
            Hexadecimal SHA-256 hash string (64 characters)
        """
        sha256_hash = hashlib.sha256()

        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    def generate_document_id(self, file_path: Path, sha256_hash: str) -> str:
        """
        Generate deterministic document_id from filename and hash.

        Args:
            file_path: Path to input file
            sha256_hash: SHA-256 hash string for the file

        Returns:
            document_id in format: <sanitized_filename>_<sha[:12]>
        """
        sanitized_name = self.sanitize_filename(file_path.name)
        hash_prefix = sha256_hash[:12] if sha256_hash else 'unknown'
        return f"{sanitized_name}_{hash_prefix}"

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process Gate 0 Hash job: compute SHA-256 and generate document_id.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if successful
        """
        try:
            # Get source file path from status
            source_file = status.get("source_file")
            if not source_file:
                self.logger.error("Job status missing 'source_file' field")
                add_error(status, "Missing source_file in job status", self.stage_name)
                return False

            source_path = Path(source_file)

            # Verify source file exists
            if not source_path.exists():
                self.logger.error(f"Source file not found: {source_path}")
                add_error(status, f"Source file not found: {source_path}", self.stage_name)
                return False

            self.logger.info(f"Computing SHA-256 for {source_path.name}")

            # Compute SHA-256 hash
            sha256_hash = self.compute_sha256(source_path)

            # Generate document_id
            document_id = self.generate_document_id(source_path, sha256_hash)

            self.logger.info(f"Generated document_id: {document_id}")

            # Create Gate 0 marker file
            marker_data = {
                "document_id": document_id,
                "original_filename": source_path.name,
                "original_path": str(source_path),
                "file_size_bytes": source_path.stat().st_size,
                "sha256_hash": sha256_hash,
                "computed_at": status.get("started_at") or status.get("created_at"),
                "rebuild_mode": True,  # Default for async pipeline
                "rebuild_scope": {
                    "mongodb": True,
                    "cassandra": True,
                    "neo4j": True
                }
            }

            marker_path = self.gate_0_out_dir / f"{document_id}.json"
            write_json_atomic(marker_path, marker_data)

            self.logger.info(f"Created Gate 0 marker: {marker_path}")

            # Update job status with hash results
            status = update_job_status(status, {
                "document_id": document_id,
                "sha256_hash": sha256_hash,
                "gate_0_marker_path": str(marker_path),
                "file_size_bytes": marker_data["file_size_bytes"]
            })

            # Save updated status
            from async_job_utils import get_job_status_path
            status_path = get_job_status_path(job_dir)
            write_json_atomic(status_path, status)

            return True

        except Exception as e:
            self.logger.exception(f"Failed to process Gate 0 Hash: {e}")
            add_error(status, f"Gate 0 Hash failed: {str(e)}", self.stage_name)
            return False


if __name__ == "__main__":
    Gate0HashWorker.main()
