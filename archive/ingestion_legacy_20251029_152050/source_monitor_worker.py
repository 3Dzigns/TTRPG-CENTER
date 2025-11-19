#!/usr/bin/env python3
"""
source_monitor_worker.py - Automatic Source Directory Monitor

Monitors /Transfer_Station/sources/ for PDF changes every 5 minutes:
- Auto-queues ingestion jobs for new PDFs
- Auto-queues cleanup jobs when PDFs are removed

This worker runs continuously inside ttrpg_ingestion_engine container.
"""

import os
import sys
import json
import time
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Dict, Set, List
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from async_worker_base import AsyncWorkerBase
from path_utils import get_transfer_station_path


class SourceMonitorWorker(AsyncWorkerBase):
    """
    Monitors /Transfer_Station/sources/ directory for PDF changes.

    Features:
    - Polls sources directory every 5 minutes
    - Tracks known PDFs in manifest file
    - Auto-queues ingestion jobs for new PDFs
    - Auto-queues cleanup jobs for removed PDFs
    """

    def __init__(self, sources_dir: str, manifest_path: str, poll_interval: int = 300):
        """
        Initialize source monitor worker.

        Args:
            sources_dir: Path to sources directory (/Transfer_Station/sources/)
            manifest_path: Path to manifest file tracking known PDFs
            poll_interval: Polling interval in seconds (default: 300 = 5 minutes)
        """
        super().__init__(
            stage_name="source_monitor",
            jobs_dir="/Transfer_Station/jobs",  # Not used for monitoring
            log_dir="/Transfer_Station/Logs/source_monitor",
            poll_interval=poll_interval
        )

        self.sources_dir = Path(sources_dir)
        self.manifest_path = Path(manifest_path)
        self.known_pdfs: Dict[str, str] = {}  # {filename: sha256_hash}

        # Ensure directories exist
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing manifest
        self._load_manifest()

        self.logger.info(f"Source monitor initialized: {self.sources_dir}")
        self.logger.info(f"Manifest: {self.manifest_path}")
        self.logger.info(f"Poll interval: {poll_interval}s ({poll_interval // 60} minutes)")
        self.logger.info(f"Known PDFs: {len(self.known_pdfs)}")

    def _load_manifest(self):
        """Load manifest of known PDFs from disk."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    self.known_pdfs = json.load(f)
                self.logger.info(f"Loaded manifest: {len(self.known_pdfs)} known PDFs")
            except Exception as e:
                self.logger.error(f"Failed to load manifest: {e}")
                self.known_pdfs = {}
        else:
            self.logger.info("No existing manifest found, starting fresh")
            self.known_pdfs = {}

    def _save_manifest(self):
        """Save manifest of known PDFs to disk."""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.known_pdfs, f, indent=2)
            self.logger.info(f"Saved manifest: {len(self.known_pdfs)} known PDFs")
        except Exception as e:
            self.logger.error(f"Failed to save manifest: {e}")

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA-256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hex string of SHA-256 hash
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def _scan_sources_directory(self) -> Dict[str, str]:
        """
        Scan sources directory for PDF files.

        Returns:
            Dictionary mapping filename to SHA-256 hash
        """
        current_pdfs = {}

        if not self.sources_dir.exists():
            self.logger.warning(f"Sources directory does not exist: {self.sources_dir}")
            return current_pdfs

        try:
            for pdf_file in self.sources_dir.glob("*.pdf"):
                if pdf_file.is_file():
                    try:
                        file_hash = self._compute_file_hash(pdf_file)
                        current_pdfs[pdf_file.name] = file_hash
                    except Exception as e:
                        self.logger.error(f"Failed to hash {pdf_file.name}: {e}")
        except Exception as e:
            self.logger.error(f"Failed to scan sources directory: {e}")

        return current_pdfs

    def _queue_ingestion_job(self, pdf_filename: str) -> bool:
        """
        Queue ingestion job for new PDF using ingestion_wrapper_async.py.

        Args:
            pdf_filename: Name of PDF file in sources directory

        Returns:
            True if job queued successfully, False otherwise
        """
        source_pdf_path = self.sources_dir / pdf_filename

        self.logger.info(f"Queueing ingestion job for: {pdf_filename}")

        try:
            # Use ingestion_wrapper_async.py to queue the job
            wrapper_script = Path(__file__).parent / "ingestion_wrapper_async.py"

            cmd = [
                "python3",
                str(wrapper_script),
                "--source-pdf", str(source_pdf_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60
            )

            if result.returncode == 0:
                self.logger.info(f"✅ Ingestion job queued for {pdf_filename}")
                self.logger.info(f"Output: {result.stdout}")
                return True
            else:
                self.logger.error(f"❌ Failed to queue ingestion job for {pdf_filename}")
                self.logger.error(f"Error: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Exception queueing ingestion job for {pdf_filename}: {e}")
            return False

    def _queue_cleanup_job(self, pdf_filename: str) -> bool:
        """
        Queue cleanup job for removed PDF using cleanup_document.py.

        Args:
            pdf_filename: Name of PDF file that was removed

        Returns:
            True if cleanup job queued successfully, False otherwise
        """
        self.logger.info(f"Queueing cleanup job for removed PDF: {pdf_filename}")

        try:
            # Use cleanup_document.py to remove all artifacts
            cleanup_script = Path(__file__).parent / "cleanup_document.py"

            cmd = [
                "python3",
                str(cleanup_script),
                "--filename", pdf_filename
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=300  # 5 minute timeout for cleanup
            )

            if result.returncode == 0:
                self.logger.info(f"✅ Cleanup completed for {pdf_filename}")
                self.logger.info(f"Output: {result.stdout}")
                return True
            else:
                self.logger.error(f"❌ Cleanup failed for {pdf_filename}")
                self.logger.error(f"Error: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Exception during cleanup for {pdf_filename}: {e}")
            return False

    def _process_changes(self, current_pdfs: Dict[str, str]):
        """
        Process changes between current and known PDFs.

        Args:
            current_pdfs: Dictionary of currently detected PDFs {filename: hash}
        """
        current_filenames = set(current_pdfs.keys())
        known_filenames = set(self.known_pdfs.keys())

        # Detect new PDFs
        new_pdfs = current_filenames - known_filenames
        if new_pdfs:
            self.logger.info(f"🆕 Detected {len(new_pdfs)} new PDF(s): {list(new_pdfs)}")
            for pdf_filename in new_pdfs:
                if self._queue_ingestion_job(pdf_filename):
                    # Add to known PDFs only if job queued successfully
                    self.known_pdfs[pdf_filename] = current_pdfs[pdf_filename]

        # Detect removed PDFs
        removed_pdfs = known_filenames - current_filenames
        if removed_pdfs:
            self.logger.info(f"🗑️ Detected {len(removed_pdfs)} removed PDF(s): {list(removed_pdfs)}")
            for pdf_filename in removed_pdfs:
                if self._queue_cleanup_job(pdf_filename):
                    # Remove from known PDFs only if cleanup completed
                    del self.known_pdfs[pdf_filename]

        # Detect modified PDFs (hash changed)
        modified_pdfs = []
        for pdf_filename in (current_filenames & known_filenames):
            if current_pdfs[pdf_filename] != self.known_pdfs[pdf_filename]:
                modified_pdfs.append(pdf_filename)

        if modified_pdfs:
            self.logger.info(f"📝 Detected {len(modified_pdfs)} modified PDF(s): {modified_pdfs}")
            for pdf_filename in modified_pdfs:
                # Modified = cleanup old + queue new
                self.logger.info(f"Processing modified PDF: {pdf_filename}")
                if self._queue_cleanup_job(pdf_filename):
                    if self._queue_ingestion_job(pdf_filename):
                        # Update hash
                        self.known_pdfs[pdf_filename] = current_pdfs[pdf_filename]

        # Save manifest after processing changes
        if new_pdfs or removed_pdfs or modified_pdfs:
            self._save_manifest()
        else:
            self.logger.info("No changes detected in sources directory")

    def run(self):
        """
        Main worker loop - monitor sources directory continuously.

        This overrides AsyncWorkerBase.run() since we're not processing
        job queues but monitoring a directory.
        """
        self.logger.info(f"Starting source monitor worker (poll interval: {self.poll_interval}s)")
        self.logger.info(f"Monitoring: {self.sources_dir}")

        while not self.shutdown_event.is_set():
            try:
                # Update heartbeat
                self._update_heartbeat()

                # Scan sources directory
                self.logger.info("Scanning sources directory...")
                current_pdfs = self._scan_sources_directory()

                self.logger.info(f"Found {len(current_pdfs)} PDF(s) in sources directory")

                # Process changes
                self._process_changes(current_pdfs)

                # Update heartbeat with scan complete
                self.last_activity = datetime.now().isoformat()
                self._update_heartbeat()

                # Wait for next poll interval
                self.logger.info(f"Next scan in {self.poll_interval}s ({self.poll_interval // 60} minutes)")
                self.shutdown_event.wait(self.poll_interval)

            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}", exc_info=True)
                # Wait a bit before retrying on error
                self.shutdown_event.wait(30)

        self.logger.info("Source monitor worker stopped")


def main():
    """Main entry point for source monitor worker."""
    import argparse

    parser = argparse.ArgumentParser(description="Source Monitor Worker - Auto-detect PDF changes")
    parser.add_argument(
        "--sources-dir",
        default="/Transfer_Station/sources",
        help="Sources directory to monitor (default: /Transfer_Station/sources)"
    )
    parser.add_argument(
        "--manifest-path",
        default="/Transfer_Station/Logs/source_monitor/manifest.json",
        help="Path to manifest file (default: /Transfer_Station/Logs/source_monitor/manifest.json)"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=300,
        help="Polling interval in seconds (default: 300 = 5 minutes)"
    )

    args = parser.parse_args()

    # Create and run worker
    worker = SourceMonitorWorker(
        sources_dir=args.sources_dir,
        manifest_path=args.manifest_path,
        poll_interval=args.poll_interval
    )

    try:
        worker.run()
    except KeyboardInterrupt:
        print("\n\nReceived shutdown signal, stopping worker...")
        worker.shutdown_event.set()
        sys.exit(0)


if __name__ == "__main__":
    main()
