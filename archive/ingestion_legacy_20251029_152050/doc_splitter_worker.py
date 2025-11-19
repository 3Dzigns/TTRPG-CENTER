#!/usr/bin/env python3
"""
doc_splitter_worker.py - Async worker for TOC extraction stage
===============================================================

Polls job queue for validated documents, extracts TOC from pages 1-10,
and routes to pass_a_unstructured stage.

This is an OPTIONAL stage - can be skipped if UNSTRUCTURED_USE_TOC_SPLIT=false
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from async_job_utils import add_error, add_warning, update_job_status, write_json_atomic, get_job_status_path
from async_worker_base import AsyncWorkerBase
from path_utils import resolve_transfer_path


class DocSplitterWorker(AsyncWorkerBase):
    """Async worker for TOC extraction from PDFs."""

    stage_name = "doc_splitter"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pass_a_out_dir = resolve_transfer_path("Pass_A_Out")
        self.pass_a_out_dir.mkdir(parents=True, exist_ok=True)
        self.doc_splitter_path = Path(__file__).parent / "doc_splitter.py"

        # Check if TOC splitting is enabled
        self.toc_split_enabled = os.getenv("UNSTRUCTURED_USE_TOC_SPLIT", "true").lower() in ("true", "1", "yes")

    def extract_toc(self, source_file: Path, document_id: str, gate_0_marker_path: str) -> Dict[str, Any]:
        """
        Extract TOC from PDF pages 1-10 using doc_splitter.py.

        Args:
            source_file: Path to source PDF
            document_id: Document identifier
            gate_0_marker_path: Path to Gate 0 marker file for updating

        Returns:
            Dict with toc_file_path and metadata, or None if extraction failed
        """
        # Check file extension - only PDF supported for TOC extraction
        if source_file.suffix.lower() != '.pdf':
            self.logger.info(f"Skipping TOC extraction for non-PDF file: {source_file.suffix}")
            return {
                "toc_extracted": False,
                "reason": "non_pdf_file",
                "file_type": source_file.suffix
            }

        # Generate TOC filename
        toc_filename = f"{document_id}_toc.pdf"
        toc_path = self.pass_a_out_dir / toc_filename

        try:
            # Run doc_splitter.py to extract pages 1-10
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.doc_splitter_path),
                    str(source_file),
                    "1",  # start_page
                    "10",  # end_page
                    str(toc_path),
                    "--update-marker",
                    gate_0_marker_path,
                    "--split-type",
                    "toc"
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                self.logger.error(f"TOC extraction failed: {result.stderr}")
                return {
                    "toc_extracted": False,
                    "error": result.stderr,
                    "return_code": result.returncode
                }

            self.logger.info(f"TOC extracted successfully: {toc_path}")

            return {
                "toc_extracted": True,
                "toc_file_path": str(toc_path),
                "toc_filename": toc_filename,
                "pages_extracted": "1-10",
                "file_size_bytes": toc_path.stat().st_size if toc_path.exists() else 0,
                "gate_0_marker_updated": True
            }

        except subprocess.TimeoutExpired:
            self.logger.error("TOC extraction timed out after 120 seconds")
            return {
                "toc_extracted": False,
                "error": "timeout_after_120s"
            }
        except Exception as e:
            self.logger.exception(f"TOC extraction failed with exception: {e}")
            return {
                "toc_extracted": False,
                "error": str(e)
            }

    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process doc_splitter job: extract TOC from PDF pages 1-10.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if successful (even if TOC extraction skipped)
        """
        try:
            # Check if TOC splitting is enabled
            if not self.toc_split_enabled:
                self.logger.info("TOC splitting disabled (UNSTRUCTURED_USE_TOC_SPLIT=false), skipping stage")
                status = update_job_status(status, {
                    "toc_extracted": False,
                    "skip_reason": "toc_split_disabled"
                })
                add_warning(status, "TOC extraction skipped (config disabled)", self.stage_name)
                status_path = get_job_status_path(job_dir)
                write_json_atomic(status_path, status)
                return True

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

            # Get document_id and gate_0_marker_path from status
            document_id = status.get("document_id")
            gate_0_marker_path = status.get("gate_0_marker_path")

            if not document_id:
                self.logger.error("Job status missing 'document_id' field")
                add_error(status, "Missing document_id in job status", self.stage_name)
                return False

            if not gate_0_marker_path:
                self.logger.error("Job status missing 'gate_0_marker_path' field")
                add_error(status, "Missing gate_0_marker_path in job status", self.stage_name)
                return False

            self.logger.info(f"Extracting TOC for document_id: {document_id}")

            # Extract TOC
            toc_result = self.extract_toc(source_path, document_id, gate_0_marker_path)

            # Update job status with TOC extraction results
            status = update_job_status(status, toc_result)

            # Add warning if extraction failed
            if not toc_result.get("toc_extracted", False):
                reason = toc_result.get("reason") or toc_result.get("error", "unknown")
                add_warning(status, f"TOC extraction failed: {reason}", self.stage_name)
                self.logger.warning(f"TOC extraction failed: {reason}")
            else:
                self.logger.info(f"TOC extraction successful: {toc_result.get('toc_file_path')}")

            # Save updated status
            status_path = get_job_status_path(job_dir)
            write_json_atomic(status_path, status)

            # Return True even if TOC extraction failed - job can continue
            # The pipeline doesn't hard-fail on missing TOC
            return True

        except Exception as e:
            self.logger.exception(f"Failed to process doc_splitter job: {e}")
            add_error(status, f"Doc splitter failed: {str(e)}", self.stage_name)
            status_path = get_job_status_path(job_dir)
            write_json_atomic(status_path, status)
            return False


if __name__ == "__main__":
    DocSplitterWorker.main()
