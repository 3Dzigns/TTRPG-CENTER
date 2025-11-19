#!/usr/bin/env python3
"""
ingestion_wrapper.py - TTRPG Document Ingestion Pipeline Wrapper
===================================================================

Orchestrates the complete ingestion pipeline from source documents into the Postgres dictionary store, Cassandra embeddings, and Neo4j graph layers.
Supports batch processing (cron), ad-hoc execution, and selective file processing.

Pipeline Steps:
  1. gate_0_hash             - Generate document_id and SHA-256 hash
  2. gate_0_validate         - Compare Gate 0 checksum with Cassandra (early exit)
  3. doc_splitter            - Extract TOC (pages 1-10)
  4. pass_unstructured_async - Run Pass A/B/C via asynchronous Unstructured job
  5. pass_a_mongo_upsert     - Persist dictionary artifacts into Postgres
  6. pass_d_hayhooks         - Generate embeddings and store in Cassandra
  7. pass_d_checksum         - Record embedded chunk count for Gate 0 validation
  8. pass_e_graph_builder    - Build knowledge graph artifacts from embeddings
  9. pass_e_neo4j_upsert     - Upsert graph data into Neo4j

Modes:
  - batch      : Process all files (cron-friendly, minimal output)
  - ad-hoc     : Process all files (interactive, progress indicators)
  - selective  : Process specific files from command line

Usage:
  ingestion_wrapper.py --mode batch [--concurrency N] [--clean-run]
  ingestion_wrapper.py --mode ad-hoc [--concurrency N] [--clean-run]
  ingestion_wrapper.py --mode selective --files file1.pdf file2.pdf [--concurrency N] [--clean-run]
  ingestion_wrapper.py -v | --version
  ingestion_wrapper.py -? | --help

Arguments:
  --mode {batch|ad-hoc|selective}  Execution mode (required)
  --files FILE [FILE ...]          Files for selective mode (required for selective)
  --concurrency N                  Max concurrent file processing (default: 1)
  --log-level {debug|info|warning} Logging verbosity (default: info)
  --clean-run                      Danger: clear DBs and generated files before ingestion
  --clean-force                    Skip interactive confirmation (use with --clean-run)

Examples:
  # Batch mode (for cron)
  ingestion_wrapper.py --mode batch

  # Ad-hoc mode (all files, interactive)
  ingestion_wrapper.py --mode ad-hoc

  # Selective mode (specific files)
  ingestion_wrapper.py --mode selective --files manual.pdf rulebook.pdf

  # Parallel processing (when multiple unstructured containers available)
  ingestion_wrapper.py --mode ad-hoc --concurrency 3

  # Clean run (purge databases and generated artifacts first)
  ingestion_wrapper.py --mode ad-hoc --clean-run

Output:
  - Logs: /Transfer_Station/Ingestion_Logs/{timestamp}_ingestion.log
  - State files: /Transfer_Station/State_Files/{document_id}_state.json
  - Pipeline outputs: /Transfer_Station/Gate_0_Out, /Transfer_Station/Pass_A_Out, /Transfer_Station/Pass_B_Out, /Transfer_Station/Pass_C_Out

Version: 1.2.0
Author: n8n TTRPG Center
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .config_loader import ConfigurationError, load_config
    from .config import IngestionConfig
    from .path_utils import ENV_TRANSFER_ROOT, get_transfer_root, resolve_transfer_path
except ImportError:  # pragma: no cover - script entrypoint fallback
    from config_loader import ConfigurationError, load_config  # type: ignore
    from config import IngestionConfig  # type: ignore
    from path_utils import ENV_TRANSFER_ROOT, get_transfer_root, resolve_transfer_path  # type: ignore


__version__ = "1.2.0"


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS AND CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# Directory paths (initialized dynamically)
SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON_EXECUTABLE = Path(sys.executable)
TRANSFER_ROOT = Path()  # set by _refresh_paths
SOURCES_DIR = Path()
GATE_0_OUT = Path()
PASS_A_OUT = Path()
PASS_B_OUT = Path()
PASS_C_OUT = Path()
PASS_D_OUT = Path()
PASS_E_OUT = Path()
GATE_0_CHECK = Path()
PROMPT_LIB = Path()
LOG_DIR = Path()
STATE_DIR = Path()
UNSTRUCTURED_JOBS_DIR = Path()
TRANSFER_SCRIPTS_DIR = Path()
CLEAN_PROTECTED_PATHS: set[Path] = set()
CLEAN_DEFAULT_TARGETS: List[Path] = []


def _refresh_paths(root: Path) -> None:
    """Recompute derived Transfer Station paths."""
    base = Path(root)
    globals()['TRANSFER_ROOT'] = base
    globals()['SOURCES_DIR'] = base / "sources"
    globals()['GATE_0_OUT'] = base / "Gate_0_Out"
    globals()['PASS_A_OUT'] = base / "Pass_A_Out"
    globals()['PASS_B_OUT'] = base / "Pass_B_Out"
    globals()['PASS_C_OUT'] = base / "Pass_C_Out"
    globals()['PASS_D_OUT'] = base / "Pass_D_Out"
    globals()['PASS_E_OUT'] = base / "Pass_E_Out"
    globals()['GATE_0_CHECK'] = base / "Gate_0_Check"
    globals()['PROMPT_LIB'] = base / "Prompt_Lib"
    globals()['LOG_DIR'] = base / "Ingestion_Logs"
    globals()['STATE_DIR'] = base / "State_Files"
    globals()['UNSTRUCTURED_JOBS_DIR'] = base / "jobs" / "unstructured"
    globals()['TRANSFER_SCRIPTS_DIR'] = base / "scripts"

    globals()['CLEAN_PROTECTED_PATHS'] = {
        globals()['SOURCES_DIR'],      # Preserve original source documents
        globals()['LOG_DIR'],           # Preserve ingestion logs for audit trail
        globals()['TRANSFER_SCRIPTS_DIR'],  # Never remove on-device ingestion scripts
        base / "Logs",                  # Preserve all service logs
        base / "Logs" / "unstructured", # Preserve async unstructured worker logs
        base / "jobs" / "unstructured", # Preserve async job queue
    }

    globals()['CLEAN_DEFAULT_TARGETS'] = [
        globals()['GATE_0_OUT'],        # Gate 0 hash markers
        globals()['GATE_0_CHECK'],      # Gate 0 validation checksums (forces fresh rebuild)
        globals()['PASS_A_OUT'],        # Pass A TOC extraction artifacts
        globals()['PASS_B_OUT'],        # Pass B document splitting artifacts
        globals()['PASS_C_OUT'],        # Pass C full processing artifacts
        globals()['PASS_D_OUT'],        # Pass D embedding generation artifacts
        globals()['PASS_E_OUT'],        # Pass E knowledge graph artifacts
        globals()['PROMPT_LIB'],        # AI-generated pipeline recommendations
        globals()['STATE_DIR'],         # Pipeline state tracking files
    ]


_refresh_paths(get_transfer_root())

# TOC extraction configuration
TOC_START_PAGE = 1
TOC_END_PAGE = 10

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt'}

# Unstructured API configuration
UNSTRUCTURED_LANGUAGE = "eng"
UNSTRUCTURED_STRATEGY = "hi_res"


# ═══════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════

class IngestionWrapperError(Exception):
    """Base exception for ingestion wrapper errors."""
    pass


class PipelineStepError(IngestionWrapperError):
    """Raised when a pipeline step fails."""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class PipelineStep(Enum):
    """Pipeline step definitions."""
    GATE_0_HASH = "gate_0_hash"
    GATE_0_VALIDATE = "gate_0_validate"
    DOC_SPLITTER = "doc_splitter"
    PASS_UNSTRUCTURED_ASYNC = "pass_unstructured_async"
    PASS_A_UNSTRUCTURED = "pass_a_unstructured"
    PASS_A_METADATA = "pass_a_metadata"
    PASS_B_SPLITTER = "pass_b_splitter"
    PASS_B_CHUNKER = "pass_b_chunker"
    PASS_C_PARSING = "pass_c_parsing"
    PASS_C_METADATA = "pass_c_metadata"
    PASS_D_HAYHOOKS = "pass_d_hayhooks"
    PASS_D_CHECKSUM = "pass_d_checksum"
    PASS_E_GRAPH_BUILDER = "pass_e_graph_builder"
    PASS_E_NEO4J_UPSERT = "pass_e_neo4j_upsert"
    PASS_A_MONGO_UPSERT_INITIAL = "pass_a_mongo_upsert_initial"
    PASS_A_MONGO_UPSERT = "pass_a_mongo_upsert"


class ProcessingMode(Enum):
    """Execution modes."""
    BATCH = "batch"
    AD_HOC = "ad-hoc"
    SELECTIVE = "selective"


def prompt_clean_confirmation() -> bool:
    """
    Prompt user for confirmation before running destructive clean mode.

    Returns:
        True if user confirmed, otherwise False.
    """
    warning = (
        "DANGER: Clean run will DROP MongoDB/Cassandra/Neo4j/Postgres data and "
        f"remove generated files under {TRANSFER_ROOT} (except sources).\n"
        "Type YES to continue: "
    )
    try:
        response = input(warning)
    except EOFError:
        return False

    return response.strip().upper() == "YES"


# ═══════════════════════════════════════════════════════════════════════════
# INGESTION PIPELINE CLASS
# ═══════════════════════════════════════════════════════════════════════════

class IngestionPipeline:
    """Main orchestration class for document ingestion pipeline."""

    def __init__(
        self,
        mode: ProcessingMode,
        concurrency: int = 1,
        container_limit: int = 1,
        log_level: str = "info",
        clean_run: bool = False,
        tenant_id: Optional[str] = None,
        transfer_root: Optional[Path] = None,
    ):
        """
        Initialize ingestion pipeline.

        Args:
            mode: Processing mode (batch, ad-hoc, selective)
            concurrency: Maximum concurrent file processing per container
            container_limit: Maximum number of Unstructured containers to use
            log_level: Logging verbosity level
            clean_run: Whether to perform destructive cleanup before execution
            tenant_id: Optional tenant key for multi-tenant data stores
            transfer_root: Optional override for Transfer Station root directory
        """
        self.mode = mode
        self.concurrency = concurrency
        self.container_limit = container_limit
        self.log_level = log_level
        self.clean_run = clean_run
        self.logger = logging.getLogger(__name__)

        # Processing statistics
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0
        }
        self._stats_lock = threading.Lock()

        # Apply transfer root overrides before loading further configuration.
        self.transfer_root = Path(transfer_root) if transfer_root else get_transfer_root()
        _refresh_paths(self.transfer_root)
        os.environ[ENV_TRANSFER_ROOT] = str(self.transfer_root)

        # Set container limit in IngestionConfig for use by pass_a_unstructured.py
        from config import IngestionConfig
        IngestionConfig.UNSTRUCTURED_CONTAINER_LIMIT = container_limit

        try:
            self.config = load_config()
        except ConfigurationError as exc:
            self.logger.warning(f"Configuration load failed: {exc}")
            self.config = None

        self.tenant_key = tenant_id or "default"
        self.logger.debug("Tenant key configured: %s", self.tenant_key)

    def _increment_stat(self, key: str, amount: int = 1) -> None:
        """Thread-safe increment of pipeline statistics."""
        with self._stats_lock:
            self.stats[key] += amount

    def run(self, files: Optional[List[Path]] = None) -> int:
        """
        Main entry point for pipeline execution.

        Args:
            files: Optional list of files for selective mode

        Returns:
            Exit code (0 = success, 1 = failure)
        """
        try:
            # Perform optional clean run before creating directories
            if self.clean_run:
                if not self._execute_clean_run():
                    self.logger.error("Clean run failed; aborting pipeline")
                    return 1

            # Setup directories (recreate after clean if needed)
            self._setup_directories()

            if self.clean_run:
                setup_logging(self.mode, self.log_level, force=True)
                self.logger = logging.getLogger(__name__)

            self._log_run_banner()

            # Discover files to process
            if files:
                files_to_process = files
            else:
                files_to_process = self._discover_files()

            if not files_to_process:
                self.logger.warning("No files to process")
                return 0

            self.stats['total'] = len(files_to_process)
            self.logger.info(f"Discovered {self.stats['total']} files")

            # Process files
            if self.concurrency == 1:
                # Sequential processing
                for idx, file_path in enumerate(files_to_process, 1):
                    self._process_file_with_logging(idx, file_path)
            else:
                # Parallel processing
                self._process_files_parallel(files_to_process)

            # Print summary
            self._print_summary()

            return 0 if self.stats['failed'] == 0 else 1

        except KeyboardInterrupt:
            self.logger.warning("\nOperation cancelled by user")
            return 130
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            return 1

    def _setup_directories(self) -> None:
        """Create required directories if they don't exist."""
        for directory in [
            GATE_0_OUT,
            PASS_A_OUT,
            PASS_B_OUT,
            PASS_C_OUT,
            PASS_D_OUT,
            PASS_E_OUT,
            PROMPT_LIB,
            LOG_DIR,
            STATE_DIR,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def _log_run_banner(self) -> None:
        """Emit standardized run header."""
        self.logger.info("=" * 60)
        self.logger.info(f"Ingestion Wrapper v{__version__}")
        self.logger.info(f"Mode: {self.mode.value}")
        self.logger.info(f"Concurrency: {self.concurrency} files per container")
        self.logger.info(f"Container Limit: {self.container_limit} Unstructured containers")
        self.logger.info(f"Total Parallelism: {self.concurrency * self.container_limit} operations")
        self.logger.info("=" * 60)

    def _execute_clean_run(self) -> bool:
        """Run clean mode (Transfer Station purge + database clears)."""
        self.logger.warning("Clean run enabled. Clearing generated files and databases.")
        success = True

        try:
            self._clean_transfer_station_outputs()
        except Exception as exc:
            success = False
            self.logger.error(f"Transfer Station cleanup failed: {exc}", exc_info=True)

        db_cleaned = self._clean_databases()
        success = success and db_cleaned

        if success:
            self.logger.info("Clean run completed successfully.")
        else:
            self.logger.error("Clean run completed with errors.")

        return success

    def _clean_transfer_station_outputs(self) -> None:
        """Remove generated files under /Transfer_Station except sources."""
        if not TRANSFER_ROOT.exists():
            self.logger.info("Transfer Station root missing; nothing to clean.")
            return

        targets: List[Path] = []
        for child in TRANSFER_ROOT.iterdir():
            if child in CLEAN_PROTECTED_PATHS:
                continue
            targets.append(child)

        for path in CLEAN_DEFAULT_TARGETS:
            if path not in targets:
                targets.append(path)

        for target in targets:
            if target in CLEAN_PROTECTED_PATHS:
                continue
            if target.is_dir():
                self.logger.info(f"Cleaning directory: {target}")
                self._clear_directory_contents(target)
            elif target.exists():
                self.logger.info(f"Removing file: {target}")
                target.unlink()

    def _clear_directory_contents(self, directory: Path) -> None:
        """Delete directory contents while keeping the directory itself."""
        directory.mkdir(parents=True, exist_ok=True)
        protected_roots = {path.resolve() for path in CLEAN_PROTECTED_PATHS if path}
        if TRANSFER_SCRIPTS_DIR:
            try:
                protected_roots.add(TRANSFER_SCRIPTS_DIR.resolve())
            except OSError:
                pass

        for entry in directory.iterdir():
            try:
                entry_resolved = entry.resolve()
            except OSError:
                entry_resolved = entry

            if any(
                entry_resolved == protected or protected in entry_resolved.parents
                for protected in protected_roots
            ):
                self.logger.debug(f"Skipping protected path during cleanup: {entry}")
                continue

            if entry.is_dir():
                # Use robust deletion with ignore_errors for Windows file locking issues
                # and active log files from background workers
                shutil.rmtree(entry, ignore_errors=True)

                # If directory still exists (couldn't be fully deleted), just log it
                if entry.exists():
                    self.logger.warning(
                        f"Could not fully remove directory (may contain active log files): {entry}"
                    )
            else:
                try:
                    entry.unlink()
                except (OSError, PermissionError) as e:
                    # Handle Windows file locking on active log files
                    self.logger.warning(f"Could not remove file (may be in use): {entry} - {e}")

    def _clean_databases(self) -> bool:
        """Invoke db_manager.py to clear databases."""
        db_manager = SCRIPTS_DIR / "db_manager.py"
        if not db_manager.exists():
            self.logger.error(f"db_manager.py not found at {db_manager}")
            return False

        command = [
            str(PYTHON_EXECUTABLE),
            str(db_manager),
            "--clear",
            "--db",
            "all",
            "--force",
        ]

        result = self._run_command(command, "clean_databases")
        if result['exit_code'] != 0:
            self.logger.error("Database cleanup failed via db_manager.py")
            return False

        return True

    def _discover_files(self) -> List[Path]:
        """
        Discover processable files in sources directory.

        Returns:
            List of file paths sorted naturally
        """
        if not SOURCES_DIR.exists():
            self.logger.error(f"Sources directory not found: {SOURCES_DIR}")
            return []

        files = [
            f for f in SOURCES_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        # Natural sort
        files.sort(key=lambda x: x.name.lower())

        return files

    def _process_file_with_logging(self, index: int, file_path: Path) -> None:
        """
        Process single file with index logging.

        Args:
            index: File number in sequence
            file_path: Path to file
        """
        self.logger.info("")
        self.logger.info(f"Starting file {index}/{self.stats['total']}: {file_path.name}")

        start_time = datetime.utcnow()
        success = self._process_file(file_path)
        duration = (datetime.utcnow() - start_time).total_seconds()

        if success:
            self._increment_stat('completed')
            self.logger.info(f"File {index}/{self.stats['total']} completed successfully ({duration:.1f}s total)")
        else:
            self._increment_stat('failed')
            self.logger.error(f"File {index}/{self.stats['total']} failed ({duration:.1f}s total)")

    def _process_files_parallel(self, files: List[Path]) -> None:
        """
        Process files in parallel using thread pool.

        Args:
            files: List of files to process
        """
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_file = {
                executor.submit(self._process_file, f): (idx, f)
                for idx, f in enumerate(files, 1)
            }

            for future in as_completed(future_to_file):
                idx, file_path = future_to_file[future]
                try:
                    success = future.result()
                    if success:
                        self._increment_stat('completed')
                        self.logger.info(f"File {idx}/{self.stats['total']} completed: {file_path.name}")
                    else:
                        self._increment_stat('failed')
                        self.logger.error(f"File {idx}/{self.stats['total']} failed: {file_path.name}")
                except Exception as e:
                    self._increment_stat('failed')
                    self.logger.error(f"File {idx}/{self.stats['total']} error: {file_path.name} - {e}")

    def _process_file(self, file_path: Path) -> bool:
        """
        Process single file through complete pipeline.

        Args:
            file_path: Path to source file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize state tracking
            state = self._initialize_state(file_path)

            if state.get('status') in {'completed', 'skipped'}:
                self.logger.info(
                    f"Skipping {file_path.name}; pipeline previously marked as {state['status']}."
                )
                return True

            # STEP 1: Gate 0 Hash
            marker_path = self._run_gate_0_hash(file_path, state)
            if not marker_path:
                return False

            # STEP 2: Gate 0 Validation (post-hash)
            validation = self._run_gate_0_validate(state, phase="post_hash")
            if validation is None:
                return False

            validation_status = validation['status']
            if validation_status == 'valid':
                self.logger.info("[gate_0_validate_post_hash] Match detected; skipping Passes A-E.")
                steps_to_skip = [
                    PipelineStep.DOC_SPLITTER.value,
                    PipelineStep.PASS_A_UNSTRUCTURED.value,
                    PipelineStep.PASS_A_METADATA.value,
                    PipelineStep.PASS_B_SPLITTER.value,
                    PipelineStep.PASS_B_CHUNKER.value,
                    PipelineStep.PASS_C_PARSING.value,
                    PipelineStep.PASS_C_METADATA.value,
                    PipelineStep.PASS_D_HAYHOOKS.value,
                    PipelineStep.PASS_D_CHECKSUM.value,
                    PipelineStep.PASS_E_GRAPH_BUILDER.value,
                    PipelineStep.PASS_E_NEO4J_UPSERT.value,
                    PipelineStep.PASS_A_MONGO_UPSERT_INITIAL.value,
                    PipelineStep.PASS_A_MONGO_UPSERT.value,
                    PipelineStep.PASS_F_VALIDATION.value,
                ]
                self._mark_steps_skipped(
                    state,
                    steps_to_skip,
                    reason="Gate 0 validation matched; reuse existing outputs."
                )
                state['status'] = 'skipped'
                state['completed_at'] = datetime.utcnow().isoformat() + 'Z'
                state['last_checkpoint'] = f"{PipelineStep.GATE_0_VALIDATE.value}_post_hash"
                self._save_state(state)
                return True

            if validation_status == 'mismatch':
                self.logger.warning("[gate_0_validate_post_hash] Mismatch detected; clearing previous data.")
                if not self._cleanup_existing_document_data(state):
                    return False
            elif validation_status == 'unprocessed':
                self.logger.info("[gate_0_validate_post_hash] Gate 0 difference is -1 (0=0); continuing pipeline.")
            else:
                self.logger.error("[gate_0_validate_post_hash] Validation failed; aborting document.")
                state['status'] = 'failed'
                state['completed_at'] = datetime.utcnow().isoformat() + 'Z'
                self._save_state(state)
                return False

            # STEP 3: Document Splitter (TOC Extraction)
            toc_file: Optional[Path] = None
            if IngestionConfig.UNSTRUCTURED_USE_TOC_SPLIT:
                toc_file = self._run_doc_splitter(file_path, marker_path, state)
                if not toc_file:
                    return False

            unstructured_outputs = self._run_unstructured_async(file_path, toc_file, marker_path, state)
            if not unstructured_outputs:
                return False

            elements_path_str = unstructured_outputs.get("pass_a_elements")
            metadata_path_str = unstructured_outputs.get("pass_a_metadata")
            manifest_path_str = unstructured_outputs.get("pass_b_manifest")
            pass_c_metadata_path_str = unstructured_outputs.get("pass_c_metadata")

            if not elements_path_str or not metadata_path_str or not manifest_path_str:
                self.logger.error("Unstructured job did not provide required outputs.")
                return False

            elements_file = Path(elements_path_str)
            metadata_file = Path(metadata_path_str)
            manifest_file = Path(manifest_path_str)
            pass_c_metadata_file = Path(pass_c_metadata_path_str) if pass_c_metadata_path_str else None

            state['pass_a_elements'] = str(elements_file)
            state['pass_a_metadata'] = str(metadata_file)
            if pass_c_metadata_file:
                state['pass_c_metadata'] = str(pass_c_metadata_file)

            if not self._run_pass_a_mongo_upsert(elements_file, metadata_file, state, stage="initial"):
                return False

            # STEP 9: Pass D Hayhooks (Embedding Generation)
            pass_d_manifest = self._run_pass_d_hayhooks(manifest_file, state)
            if not pass_d_manifest:
                return False

            # STEP 10: Pass D Checksum (Gate 0 Validation)
            if not self._run_pass_d_checksum(pass_d_manifest, state):
                return False

            final_metadata_path = state.get('pass_c_metadata') or (str(pass_c_metadata_file) if pass_c_metadata_file else None)
            final_elements_path = state.get('pass_a_elements', str(elements_file))
            if final_metadata_path:
                if not self._run_pass_a_mongo_upsert(Path(final_elements_path), Path(final_metadata_path), state, stage="final"):
                    return False
            else:
                self.logger.warning('Pass C metadata missing; skipping final Mongo upsert')

            # STEP 11: Pass E Graph Builder
            graph_file = self._run_pass_e_graph_builder(pass_d_manifest, state)
            pass_e_failed = graph_file is None

            # STEP 12: Pass E Neo4j Upsert
            if not pass_e_failed and not self._run_pass_e_neo4j_upsert(graph_file, state):
                pass_e_failed = True

            if pass_e_failed:
                self._handle_pass_e_failure(state, "pass_e_failed")
                return False

            # Gate 0 Validation health check after Pass E
            post_validation = self._run_gate_0_validate(state, phase="post_pass_e")
            if post_validation is None:
                self._handle_pass_e_failure(state, "gate_0_validation_post_pass_e_failed")
                return False

            post_status = post_validation['status']
            if post_status == 'mismatch':
                self.logger.error("[gate_0_validate_post_pass_e] Validation mismatch after Pass E; marking job failed.")
                self._handle_pass_e_failure(state, "gate_0_validation_post_pass_e_mismatch")
                return False
            if post_status == 'unprocessed':
                self.logger.error("[gate_0_validate_post_pass_e] Validation returned -1 after Pass E; marking job failed.")
                self._handle_pass_e_failure(state, "gate_0_validation_post_pass_e_unprocessed")
                return False

            # Mark as completed
            state['status'] = 'completed'
            state['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            self._save_state(state)

            self.logger.info(f"State saved: {self._get_state_file(state['document_id']).name}")
            return True

        except Exception as e:
            self.logger.error(f"Error processing {file_path.name}: {e}", exc_info=True)
            return False

    # ═══════════════════════════════════════════════════════════════════════════
    # PIPELINE STEP METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _run_gate_0_hash(self, file_path: Path, state: Dict) -> Optional[Path]:
        """
        Execute gate_0_hash.py to generate document_id and marker file.

        Args:
            file_path: Source file path
            state: State tracking dictionary

        Returns:
            Path to marker file, or None on failure
        """
        step = PipelineStep.GATE_0_HASH.value

        # Check if already completed
        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            marker_path = Path(state['pipeline'][step]['output_file'])
            if not state.get('gate_0_marker'):
                state['gate_0_marker'] = str(marker_path)
            if not state.get('source_sha256'):
                marker_data = self._safe_load_json(marker_path)
                if marker_data and marker_data.get("sha256_hash"):
                    state['source_sha256'] = marker_data['sha256_hash']
            return marker_path

        self.logger.info(f"[{step}] Starting")

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "gate_0_hash.py"),
            str(file_path),
            "-o", str(GATE_0_OUT),
            "--quiet"
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        # Extract document_id from stdout
        document_id = result['stdout'].strip()
        marker_path = GATE_0_OUT / f"{document_id}.json"

        # Update state with document_id
        state['document_id'] = document_id

        marker_data = self._safe_load_json(marker_path)
        if marker_data and marker_data.get("sha256_hash"):
            state['source_sha256'] = marker_data['sha256_hash']
        state['gate_0_marker'] = str(marker_path)

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(marker_path)
        )

        self.logger.info(f"[{step}] Output: {document_id}")
        return marker_path

    def _run_gate_0_validate(self, state: Dict, phase: str) -> Optional[Dict[str, Any]]:
        """
        Execute gate_0_validate.py and capture results for the given phase.
        """
        sha256_hash = state.get('source_sha256')
        if not sha256_hash:
            marker_path = state.get('gate_0_marker')
            if marker_path:
                marker_data = self._safe_load_json(Path(marker_path))
                if marker_data and marker_data.get("sha256_hash"):
                    sha256_hash = marker_data["sha256_hash"]
                    state['source_sha256'] = sha256_hash

        if not sha256_hash:
            self.logger.error("[gate_0_validate] Missing SHA-256 hash; cannot run validation.")
            return None

        step = f"{PipelineStep.GATE_0_VALIDATE.value}_{phase}"
        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "gate_0_validate.py"),
            sha256_hash,
            "--json"
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        payload: Optional[Dict[str, Any]] = None
        statistics: Dict[str, Any] = {"exit_code": result['exit_code']}
        status_map = {0: "valid", 1: "mismatch", 2: "unprocessed"}
        status = status_map.get(result['exit_code'], "error")
        error_msg: Optional[str] = None

        stdout = (result.get('stdout') or "").strip()
        if stdout and result['exit_code'] in {0, 1, 2}:
            try:
                payload = json.loads(stdout)
                status = payload.get("status", status)
            except json.JSONDecodeError as exc:
                error_msg = f"Failed to parse gate_0_validate output: {exc}"
        elif result['exit_code'] not in {0, 1, 2}:
            error_msg = result.get('stderr') or "gate_0_validate reported an error."

        if payload:
            statistics.update({
                "status": payload.get("status"),
                "difference": payload.get("difference"),
                "expected": payload.get("expected_chunks"),
                "actual": payload.get("actual_chunks"),
            })

        record: Dict[str, Any] = {
            "phase": phase,
            "exit_code": result['exit_code'],
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
        }

        if payload:
            record.update(payload)

        state.setdefault('gate_0_validation', {})[phase] = record

        if status == "error":
            self._update_step_state(state, step, 'failed', start_time, error=error_msg or "Validation error.")
            self._save_state(state)
            return None

        if status == "mismatch":
            self.logger.warning(f"[{step}] Mismatch detected (difference={record.get('difference')}).")
        elif status == "unprocessed":
            self.logger.info(f"[{step}] Validation returned -1 (no prior processing).")
        else:
            self.logger.info(f"[{step}] Validation passed.")

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            statistics=statistics
        )
        self._save_state(state)
        return record

    def _run_doc_splitter(
        self,
        file_path: Path,
        marker_path: Path,
        state: Dict
    ) -> Optional[Path]:
        """
        Execute doc_splitter.py to extract TOC pages.

        Args:
            file_path: Source file path
            marker_path: Path to Gate 0 marker file
            state: State tracking dictionary

        Returns:
            Path to TOC file, or None on failure
        """
        step = PipelineStep.DOC_SPLITTER.value

        # Check if already completed
        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return Path(state['pipeline'][step]['output_file'])

        self.logger.info(f"[{step}] Starting")

        # Build output filename: {basename}_toc.{ext}
        toc_filename = f"{file_path.stem}_toc{file_path.suffix}"
        toc_path = PASS_A_OUT / toc_filename

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "doc_splitter.py"),
            str(file_path),
            str(TOC_START_PAGE),
            str(TOC_END_PAGE),
            str(toc_path),
            "--update-marker", str(marker_path),
            "--split-type", "toc"
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(toc_path)
        )

        return toc_path

    def _run_unstructured_async(
        self,
        source_file: Path,
        toc_file: Optional[Path],
        marker_path: Path,
        state: Dict
    ) -> Optional[Dict[str, str]]:
        """Execute Pass A/B/C via asynchronous job or fall back to synchronous execution."""
        if not IngestionConfig.UNSTRUCTURED_ASYNC_ENABLED:
            input_file = toc_file or source_file
            elements_file = self._run_pass_a_unstructured(input_file, state)
            if not elements_file:
                return None
            metadata_file = self._run_pass_a_metadata(elements_file, marker_path, state)
            if not metadata_file:
                return None
            manifest_file = self._run_pass_b_splitter(source_file, metadata_file, state)
            if not manifest_file:
                return None
            if not self._run_pass_b_chunker(source_file, manifest_file, state):
                return None
            if not self._run_pass_c_parsing(manifest_file, state):
                return None
            pass_c_metadata_file = self._run_pass_c_metadata(manifest_file, state)
            if not pass_c_metadata_file:
                return None

            outputs = {
                "pass_a_elements": str(elements_file),
                "pass_a_metadata": str(metadata_file),
                "pass_b_manifest": str(manifest_file),
                "pass_c_metadata": str(pass_c_metadata_file)
            }
            state['pass_a_metadata'] = outputs["pass_a_metadata"]
            state['pass_c_metadata'] = outputs["pass_c_metadata"]
            return outputs

        pipeline = state.setdefault('pipeline', {})
        step = PipelineStep.PASS_UNSTRUCTURED_ASYNC.value
        document_id = state.get('document_id') or source_file.stem

        # Short-circuit when prior run already produced outputs.
        if self._should_skip_step(state, step):
            cached = pipeline.get(step, {}).get('outputs')
            if cached:
                return cached

        jobs_root = UNSTRUCTURED_JOBS_DIR
        jobs_root.mkdir(parents=True, exist_ok=True)

        existing_job = state.get('unstructured_job') or {}
        job_dir: Optional[Path] = None
        manifest_path: Optional[Path] = None
        status_path: Optional[Path] = None
        job_id: Optional[str] = None

        if existing_job:
            try:
                job_dir_candidate = Path(existing_job.get('job_dir', ''))
                manifest_candidate = Path(existing_job.get('manifest_path', ''))
                status_candidate = Path(existing_job.get('status_path', ''))
            except TypeError:
                existing_job = {}
            else:
                if job_dir_candidate.exists() and manifest_candidate.exists() and status_candidate.exists():
                    job_dir = job_dir_candidate
                    manifest_path = manifest_candidate
                    status_path = status_candidate
                    job_id = existing_job.get('job_id')

        if job_dir is None:
            job_id = f"{document_id}_{uuid.uuid4().hex[:8]}"
            job_dir = jobs_root / job_id
            job_dir.mkdir(parents=True, exist_ok=True)

            created_at = datetime.utcnow().isoformat() + 'Z'
            rebuild_scope = state.get('pending_cleanup') or self._derive_cleanup_scope(state)
            source_info = {
                "path": str(source_file),
                "marker_path": str(marker_path)
            }
            if toc_file:
                source_info["toc_path"] = str(toc_file)

            manifest = {
                "job_id": job_id,
                "job_type": "unstructured_pass_abc",
                "document_id": document_id,
                "created_at": created_at,
                "source": source_info,
                "targets": {
                    "pass_a": str(PASS_A_OUT),
                    "pass_b": str(PASS_B_OUT),
                    "pass_c": str(PASS_C_OUT)
                },
                "rebuild_scope": rebuild_scope,
                "options": {
                    "language": UNSTRUCTURED_LANGUAGE,
                    "strategy": UNSTRUCTURED_STRATEGY,
                    "single_chunk": IngestionConfig.UNSTRUCTURED_SINGLE_CHUNK,
                    "use_toc_split": IngestionConfig.UNSTRUCTURED_USE_TOC_SPLIT
                }
            }

            manifest_path = job_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')

            status_path = job_dir / "status.json"
            initial_status = {
                "job_id": job_id,
                "state": "queued",
                "created_at": created_at,
                "updated_at": created_at,
                "worker": None
            }
            status_path.write_text(json.dumps(initial_status, indent=2), encoding='utf-8')

            # Drop a marker file so the worker can detect new jobs without polling every manifest.
            marker_file = job_dir / "queued.marker"
            marker_file.touch(exist_ok=True)

            job_state = {
                "job_id": job_id,
                "job_dir": str(job_dir),
                "manifest_path": str(manifest_path),
                "status_path": str(status_path),
                "created_at": created_at,
                "status": "queued"
            }
            state['unstructured_job'] = job_state
            self._save_state(state)

            self.logger.info(f"[{step}] Submitted Unstructured job {job_id}")
        else:
            status_path = status_path or (job_dir / "status.json")
            manifest_path = manifest_path or (job_dir / "manifest.json")
            job_id = job_id or job_dir.name
            self.logger.info(f"[{step}] Resuming Unstructured job {job_id}")

        pipeline_step_state = pipeline.setdefault(step, {})
        pipeline_step_state['job_id'] = job_id
        pipeline_step_state['job_dir'] = str(job_dir)

        start_time = datetime.utcnow()
        result = self._wait_for_unstructured_job(job_dir, status_path, step, job_id or job_dir.name)

        job_status = result.get("state")
        state['unstructured_job'] = state.get('unstructured_job', {})
        state['unstructured_job'].update({
            "status": job_status,
            "last_updated": result.get("updated_at"),
            "completed_at": result.get("completed_at"),
            "statistics": result.get("statistics"),
            "outputs": result.get("outputs"),
            "error": result.get("error")
        })
        self._save_state(state)

        if job_status != "completed":
            error = result.get("error", "Unstructured job failed")
            self._update_step_state(state, step, 'failed', start_time, error=error)
            state['pipeline'].setdefault(step, {})
            state['pipeline'][step]['job_id'] = job_id
            state['pipeline'][step]['job_dir'] = str(job_dir)
            return None

        outputs = result.get("outputs", {})
        statistics = result.get("statistics", {})
        output_file = (
            outputs.get("pass_c_metadata")
            or outputs.get("pass_b_manifest")
            or outputs.get("pass_a_metadata")
        )

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            output_file=output_file,
            statistics=statistics
        )
        state['pipeline'].setdefault(step, {})
        state['pipeline'][step]['outputs'] = outputs
        state['pipeline'][step]['job_id'] = job_id
        state['pipeline'][step]['job_dir'] = str(job_dir)

        self._record_unstructured_substeps(state, job_id, result)

        if outputs.get("pass_a_metadata"):
            state['pass_a_metadata'] = outputs["pass_a_metadata"]
        if outputs.get("pass_a_elements"):
            state['pass_a_elements'] = outputs["pass_a_elements"]
        if outputs.get("pass_b_manifest"):
            state['pass_b_manifest'] = outputs["pass_b_manifest"]
        if outputs.get("pass_c_metadata"):
            state['pass_c_metadata'] = outputs["pass_c_metadata"]

        return outputs

    def _wait_for_unstructured_job(
        self,
        job_dir: Path,
        status_path: Path,
        step: str,
        job_id: str
    ) -> Dict[str, Any]:
        """
        Poll the shared status file until the Unstructured worker completes the job.

        Args:
            job_dir: Path to the job directory
            status_path: Path to the status file
            step: Parent pipeline step name
            job_id: Job identifier for logging

        Returns:
            Final status dictionary (success or failure metadata)
        """
        poll_interval = max(1, getattr(IngestionConfig, "UNSTRUCTURED_JOB_POLL_INTERVAL", 5))
        timeout = max(poll_interval, getattr(IngestionConfig, "UNSTRUCTURED_JOB_TIMEOUT", 3600))

        start_time = time.time()
        last_state: Optional[str] = None
        last_stage: Optional[str] = None
        next_heartbeat = start_time + 60

        while True:
            try:
                with status_path.open('r', encoding='utf-8') as handle:
                    status = json.load(handle)
            except FileNotFoundError:
                status = {"job_id": job_id, "state": "queued"}
            except json.JSONDecodeError as exc:
                status = {
                    "job_id": job_id,
                    "state": "failed",
                    "error": f"Malformed status.json: {exc}"
                }
            except OSError as exc:
                status = {
                    "job_id": job_id,
                    "state": "failed",
                    "error": f"Unable to read status.json: {exc}"
                }

            status.setdefault("job_id", job_id)
            state_value = status.get("state") or "unknown"
            stage_value = status.get("current_stage")

            if state_value != last_state or stage_value != last_stage:
                stage_msg = f", stage={stage_value}" if stage_value else ""
                self.logger.info(f"[{step}] Job {job_id} -> {state_value}{stage_msg}")
                last_state = state_value
                last_stage = stage_value

            now = time.time()

            if state_value in {"completed", "failed"}:
                if state_value == "completed":
                    status.setdefault("completed_at", status.get("updated_at") or datetime.utcnow().isoformat() + 'Z')
                return status

            elapsed = now - start_time
            if elapsed >= timeout:
                timeout_msg = f"Unstructured job {job_id} exceeded timeout ({timeout}s)"
                status["state"] = "failed"
                status["error"] = status.get("error") or timeout_msg
                status["timeout"] = True
                status["updated_at"] = datetime.utcnow().isoformat() + 'Z'
                try:
                    status_path.write_text(json.dumps(status, indent=2), encoding='utf-8')
                except OSError:
                    pass
                self.logger.error(f"[{step}] {timeout_msg}")
                return status

            if now >= next_heartbeat:
                stage_msg = stage_value or state_value
                self.logger.info(
                    f"[{step}] Waiting on job {job_id} "
                    f"(stage={stage_msg}, elapsed={int(elapsed)}s)"
                )
                next_heartbeat = now + 60

            time.sleep(poll_interval)

    def _record_unstructured_substeps(
        self,
        state: Dict,
        job_id: str,
        job_result: Dict[str, Any]
    ) -> None:
        """
        Persist sub-stage metadata for delegated Pass A/B/C steps.

        Args:
            state: Pipeline state dictionary
            job_id: Job identifier
            job_result: Final job result payload
        """
        stages = job_result.get("stages") or {}
        if not stages:
            return

        mapping = {
            "pass_a": PipelineStep.PASS_A_UNSTRUCTURED.value,
            "pass_a_metadata": PipelineStep.PASS_A_METADATA.value,
            "pass_b_splitter": PipelineStep.PASS_B_SPLITTER.value,
            "pass_b_chunker": PipelineStep.PASS_B_CHUNKER.value,
            "pass_c_parsing": PipelineStep.PASS_C_PARSING.value,
            "pass_c_metadata": PipelineStep.PASS_C_METADATA.value,
        }

        for stage_key, pipeline_step in mapping.items():
            stage_data = stages.get(stage_key)
            if not stage_data:
                continue

            stage_state = {
                "status": stage_data.get("status", "completed"),
                "delegated_job_id": job_id,
                "started_at": stage_data.get("started_at"),
                "completed_at": stage_data.get("completed_at"),
                "duration_seconds": stage_data.get("duration_seconds"),
                "job_id": job_id
            }

            metrics = stage_data.get("metrics")
            if metrics:
                stage_state["statistics"] = metrics

            state['pipeline'][pipeline_step] = stage_state

        self._save_state(state)

    def _run_pass_a_unstructured(self, input_file: Path, state: Dict) -> Optional[Path]:
        """
        Execute pass_a_unstructured.py on the provided document.

        Args:
            input_file: Path to source document for Pass A
            state: State tracking dictionary

        Returns:
            Path to elements JSON file, or None on failure
        """
        step = PipelineStep.PASS_A_UNSTRUCTURED.value

        # Check if already completed
        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return Path(state['pipeline'][step]['output_file'])

        self.logger.info(f"[{step}] Starting")

        # Output will be {basename}_elements.json
        elements_path = PASS_A_OUT / f"{input_file.stem}_elements.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_a_unstructured.py"),
            str(input_file),
            "-l", UNSTRUCTURED_LANGUAGE,
            "-s", UNSTRUCTURED_STRATEGY
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(elements_path)
        )

        return elements_path

    def _run_pass_a_metadata(
        self,
        elements_file: Path,
        marker_path: Path,
        state: Dict
    ) -> Optional[Path]:
        """
        Execute pass_a_metadata.py to extract metadata.

        Args:
            elements_file: Path to elements JSON file
            marker_path: Path to Gate 0 marker file
            state: State tracking dictionary

        Returns:
            Path to metadata JSON file, or None on failure
        """
        step = PipelineStep.PASS_A_METADATA.value

        # Check if already completed
        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return Path(state['pipeline'][step]['output_file'])

        self.logger.info(f"[{step}] Starting")

        # Output will be {basename}_metadata.json
        metadata_path = PASS_A_OUT / elements_file.name.replace('_elements.json', '_metadata.json')

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_a_metadata.py"),
            str(elements_file),
            "--gate-marker", str(marker_path)
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(metadata_path)
        )

        return metadata_path

    def _run_pass_b_splitter(
        self,
        source_file: Path,
        metadata_file: Path,
        state: Dict
    ) -> Optional[Path]:
        """
        Execute pass_b_splitter.py to build Pass B manifest.
        """
        step = PipelineStep.PASS_B_SPLITTER.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return Path(state['pipeline'][step]['output_file'])

        self.logger.info(f"[{step}] Starting")

        document_id = state.get('document_id') or source_file.stem
        manifest_path = PASS_B_OUT / f"{document_id}_pass_b_manifest.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_b_splitter.py"),
            str(source_file),
            str(metadata_file),
            "-o", str(PASS_B_OUT),
            "--prefix", document_id,
            "--output-file", str(manifest_path)
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        if not manifest_path.exists():
            error_msg = f"Pass B manifest not found: {manifest_path}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return None

        manifest_data = self._safe_load_json(manifest_path)
        if manifest_data is None:
            self._update_step_state(state, step, 'failed', start_time, error="Invalid manifest JSON")
            return None

        part_count = len(manifest_data.get("parts", []))
        total_pages = manifest_data.get("total_pages")

        statistics = {
            "parts": part_count,
            "total_pages": total_pages
        }

        message = (
            f"Created Pass B manifest ({part_count} parts, total_pages={total_pages}). "
            f"File: {manifest_path.name}"
        )
        self.logger.info(f"[{step}] {message}")
        print(message)

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(manifest_path),
            statistics=statistics
        )

        return manifest_path

    def _run_pass_b_chunker(
        self,
        source_file: Path,
        manifest_file: Path,
        state: Dict
    ) -> bool:
        """
        Execute pass_b_chunker.py to create chunk documents.
        """
        step = PipelineStep.PASS_B_CHUNKER.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return True

        self.logger.info(f"[{step}] Starting")

        document_id = state.get('document_id') or source_file.stem

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_b_chunker.py"),
            str(source_file),
            str(manifest_file),
            "-o", str(PASS_B_OUT),
            "--prefix", document_id
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return False

        manifest_data = self._safe_load_json(manifest_file) or {}
        parts = manifest_data.get("parts", [])
        suffix = source_file.suffix

        chunk_files: List[str] = []
        for part in parts:
            part_id = part.get("part")
            if part_id is not None:
                chunk_name = f"{document_id}_part{int(part_id):02d}{suffix}"
            else:
                start_page = part.get("start_page")
                end_page = part.get("end_page")
                chunk_name = f"{document_id}_{start_page}_{end_page}{suffix}"
            chunk_path = PASS_B_OUT / chunk_name
            if chunk_path.exists():
                chunk_files.append(str(chunk_path))

        statistics = {
            "chunks_created": len(chunk_files) or len(parts)
        }

        completion_msg = f"Pass B chunker created {statistics['chunks_created']} files."
        self.logger.info(f"[{step}] {completion_msg}")
        print(completion_msg)

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(manifest_file),
            statistics=statistics
        )

        return True

    def _run_pass_c_parsing(
        self,
        manifest_file: Path,
        state: Dict
    ) -> bool:
        """
        Execute pass_c_parsing.py to process Pass B chunks.
        """
        step = PipelineStep.PASS_C_PARSING.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return True

        self.logger.info(f"[{step}] Starting")

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_c_parsing.py"),
            str(manifest_file),
            "--chunks-dir", str(PASS_B_OUT),
            "--output", str(PASS_C_OUT),
            "--strategy", UNSTRUCTURED_STRATEGY,
            "--language", UNSTRUCTURED_LANGUAGE
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return False

        manifest_data = self._safe_load_json(manifest_file) or {}
        document_id = manifest_data.get("document_id", state.get("document_id"))
        part_count = len(manifest_data.get("parts", []))

        statistics = {
            "parts_processed": part_count
        }

        summary = f"Pass C parsing processed {part_count} parts for {document_id}."
        self.logger.info(f"[{step}] {summary}")
        print(summary)

        self._update_step_state(
            state, step, 'completed', start_time,
            output_file=str(manifest_file),
            statistics=statistics
        )

        return True

    def _run_pass_c_metadata(
        self,
        manifest_file: Path,
        state: Dict
    ) -> Optional[Path]:
        """
        Execute pass_c_metadata.py to aggregate metadata across all parts.
        """
        step = PipelineStep.PASS_C_METADATA.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            metadata_path = Path(state['pipeline'][step]['output_file'])
            state['pass_c_metadata'] = str(metadata_path)
            return metadata_path

        self.logger.info(f"[{step}] Starting")

        document_id = state.get('document_id')
        if not document_id:
            error_msg = "Document ID missing prior to Pass C metadata"
            self.logger.error(f"[{step}] {error_msg}")
            return None

        metadata_path = PASS_C_OUT / f"{document_id}_pass_c_metadata.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_c_metadata.py"),
            str(manifest_file),
            "-o", str(PASS_C_OUT),
            "--pass-c-dir", str(PASS_C_OUT)
        ]

        gate_marker = state.get('gate_0_marker')
        if gate_marker:
            command.extend(["--gate-marker", gate_marker])

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        if not metadata_path.exists():
            error_msg = f"Pass C metadata file not found: {metadata_path}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return None

        metadata_data = self._safe_load_json(metadata_path)
        if metadata_data is None:
            self._update_step_state(state, step, 'failed', start_time, error="Invalid Pass C metadata JSON")
            return None

        statistics = metadata_data.get("statistics", {})
        summary_stats = {
            "unique_terms": statistics.get("unique_terms"),
            "unique_categories": statistics.get("unique_categories")
        }

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            output_file=str(metadata_path),
            statistics=summary_stats
        )

        state['pass_c_metadata'] = str(metadata_path)
        return metadata_path

    def _run_pass_d_hayhooks(
        self,
        manifest_file: Path,
        state: Dict
    ) -> Optional[Path]:
        """
        Execute pass_d_hayhooks.py to generate embeddings and manifest.
        """
        step = PipelineStep.PASS_D_HAYHOOKS.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            pass_d_path = Path(state['pipeline'][step]['output_file'])
            state['pass_d_manifest'] = str(pass_d_path)
            return pass_d_path

        self.logger.info(f"[{step}] Starting")

        document_id = state.get('document_id')
        if not document_id:
            error_msg = "Document ID missing prior to Pass D execution"
            self.logger.error(f"[{step}] {error_msg}")
            return None

        pass_d_manifest = PASS_D_OUT / f"{document_id}_pass_d_manifest.json"

        start_time = datetime.utcnow()
        if not self._ensure_store_cleanup(state, "cassandra"):
            error_msg = "Cassandra cleanup failed"
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return None

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_d_hayhooks.py"),
            str(manifest_file),
            "-o", str(PASS_D_OUT),
            "--pass-c-dir", str(PASS_C_OUT)
        ]

        # v3.0.0: Pass Gate 0 marker for rebuild control
        gate_marker = state.get('gate_0_marker')
        if gate_marker:
            command.extend(["--gate-marker", str(gate_marker)])

        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        if not pass_d_manifest.exists():
            error_msg = f"Pass D manifest not found: {pass_d_manifest}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return None

        manifest_data = self._safe_load_json(pass_d_manifest)
        if manifest_data is None:
            self._update_step_state(state, step, 'failed', start_time, error="Invalid Pass D manifest JSON")
            return None

        processing = manifest_data.get("processing", {})
        cassandra = manifest_data.get("cassandra", {})

        statistics: Dict[str, Any] = {}
        if processing.get("embedded_chunks") is not None:
            statistics["embedded_chunks"] = processing["embedded_chunks"]
        if processing.get("failed_chunks") is not None:
            statistics["failed_chunks"] = processing["failed_chunks"]
        if cassandra.get("rows_inserted") is not None:
            statistics["rows_inserted"] = cassandra["rows_inserted"]

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            output_file=str(pass_d_manifest),
            statistics=statistics
        )

        state['pass_d_manifest'] = str(pass_d_manifest)
        return pass_d_manifest

    def _run_pass_d_checksum(
        self,
        pass_d_manifest: Path,
        state: Dict
    ) -> bool:
        """
        Execute pass_d_checksum.py to record chunk upsert counts.
        """
        step = PipelineStep.PASS_D_CHECKSUM.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            checksum_path = Path(state['pipeline'][step]['output_file'])
            state['gate_0_checksum'] = str(checksum_path)
            return True

        self.logger.info(f"[{step}] Starting")

        start_time = datetime.utcnow()

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_d_checksum.py"),
            str(pass_d_manifest),
            "--output-dir", str(GATE_0_CHECK)
        ]

        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return False

        sha256_hash = state.get('source_sha256')
        if not sha256_hash:
            marker_path = state.get('gate_0_marker')
            if marker_path:
                marker_data = self._safe_load_json(Path(marker_path))
                if marker_data and marker_data.get('sha256_hash'):
                    sha256_hash = marker_data['sha256_hash']

        output_file = GATE_0_CHECK / f"{sha256_hash}.json" if sha256_hash else None

        if not output_file or not output_file.exists():
            # Attempt to parse stdout for created path if SHA unavailable or mismatched
            output_file = self._extract_checksum_path(result.get('stdout'))  # type: ignore[arg-type]

        if not output_file or not output_file.exists():
            error_msg = f"Checksum file not created: {output_file}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return False

        try:
            with output_file.open('r', encoding='utf-8') as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            error_msg = f"Failed to read checksum output: {exc}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return False

        chunk_count = payload.get('chunks_upserted')
        try:
            chunk_count_int = int(chunk_count)
        except (TypeError, ValueError):
            chunk_count_int = chunk_count

        statistics = {"chunks_upserted": chunk_count_int}

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            output_file=str(output_file),
            statistics=statistics
        )

        state['gate_0_checksum'] = str(output_file)
        return True

    def _run_pass_e_graph_builder(
        self,
        pass_d_manifest: Path,
        state: Dict
    ) -> Optional[Path]:
        """
        Execute pass_e_graph_builder.py to construct knowledge graph artifacts.
        """
        step = PipelineStep.PASS_E_GRAPH_BUILDER.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            graph_path = Path(state['pipeline'][step]['output_file'])
            state['pass_e_graph'] = str(graph_path)
            return graph_path

        self.logger.info(f"[{step}] Starting")

        document_id = state.get('document_id')
        if not document_id:
            error_msg = "Document ID missing prior to Pass E graph builder"
            self.logger.error(f"[{step}] {error_msg}")
            return None

        graph_path = PASS_E_OUT / f"{document_id}_graph.json"

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_e_graph_builder.py"),
            str(pass_d_manifest),
            "-o", str(PASS_E_OUT),
            "--pass-c-dir", str(PASS_C_OUT)
        ]

        start_time = datetime.utcnow()
        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return None

        if not graph_path.exists():
            error_msg = f"Pass E graph file not found: {graph_path}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return None

        graph_data = self._safe_load_json(graph_path)
        if graph_data is None:
            self._update_step_state(state, step, 'failed', start_time, error="Invalid Pass E graph JSON")
            return None

        statistics = graph_data.get("statistics", {})
        summary_stats = {
            "total_nodes": statistics.get("total_nodes"),
            "total_edges": statistics.get("total_edges")
        }

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            output_file=str(graph_path),
            statistics=summary_stats
        )

        state['pass_e_graph'] = str(graph_path)
        return graph_path

    def _run_pass_e_neo4j_upsert(
        self,
        graph_file: Path,
        state: Dict
    ) -> bool:
        """
        Execute pass_e_neo4j_upsert.py to upsert graph data into Neo4j.
        """
        step = PipelineStep.PASS_E_NEO4J_UPSERT.value

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            manifest_path = Path(state['pipeline'][step]['output_file'])
            state['pass_e_manifest'] = str(manifest_path)
            return True

        self.logger.info(f"[{step}] Starting")

        if not graph_file.exists():
            error_msg = f"Graph file not found: {graph_file}"
            self.logger.error(f"[{step}] {error_msg}")
            return False

        document_id = state.get('document_id')
        manifest_path = PASS_E_OUT / f"{document_id}_pass_e_manifest.json" if document_id else None

        start_time = datetime.utcnow()
        if not self._ensure_store_cleanup(state, "neo4j"):
            error_msg = "Neo4j cleanup failed"
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return False

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_e_neo4j_upsert.py"),
            str(graph_file),
            "-o", str(PASS_E_OUT)
        ]

        # v2.0.0: Pass Gate 0 marker for rebuild control
        gate_marker = state.get('gate_0_marker')
        if gate_marker:
            command.extend(["--gate-marker", str(gate_marker)])

        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return False

        if manifest_path and not manifest_path.exists():
            manifest_path = self._extract_pass_e_manifest_path(result.get('stdout'))

        if not manifest_path:
            error_msg = "Pass E manifest not created"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return False

        manifest_path_obj = Path(manifest_path)
        if not manifest_path_obj.exists():
            error_msg = f"Pass E manifest not found: {manifest_path_obj}"
            self.logger.error(f"[{step}] {error_msg}")
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return False

        manifest_data = self._safe_load_json(manifest_path_obj)
        statistics = {}
        if manifest_data:
            statistics = manifest_data.get("neo4j", {}).get("summary", {})

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            output_file=str(manifest_path_obj),
            statistics=statistics
        )

        state['pass_e_manifest'] = str(manifest_path_obj)
        return True

    def _run_pass_a_mongo_upsert(
        self,
        elements_file: Path,
        metadata_file: Path,
        state: Dict,
        stage: str = "final"
    ) -> bool:
        """
        Execute pass_a_mongo_upsert.py to upload to MongoDB.

        Args:
            elements_file: Path to elements JSON file
            metadata_file: Path to metadata JSON file
            state: State tracking dictionary
            stage: 'initial' or 'final'

        Returns:
            True if successful, False otherwise
        """
        if stage not in {"initial", "final"}:
            raise ValueError(f"Unknown mongo upsert stage: {stage}")

        step = (
            PipelineStep.PASS_A_MONGO_UPSERT_INITIAL.value
            if stage == "initial"
            else PipelineStep.PASS_A_MONGO_UPSERT.value
        )

        if self._should_skip_step(state, step):
            self.logger.info(f"[{step}] Skipping (already completed)")
            return True

        self.logger.info(f"[{step}] Starting ({stage})")

        start_time = datetime.utcnow()
        if not self._ensure_store_cleanup(state, "mongodb"):
            error_msg = "MongoDB cleanup failed"
            self._update_step_state(state, step, 'failed', start_time, error=error_msg)
            return False

        command = [
            str(PYTHON_EXECUTABLE),
            str(SCRIPTS_DIR / "pass_a_mongo_upsert.py"),
            str(elements_file),
            str(metadata_file),
            "--stage",
            stage,
        ]
        command.extend(["--tenant-key", self.tenant_key])

        # v2.0.0: Pass Gate 0 marker for rebuild control
        gate_marker = state.get('gate_0_marker')
        if gate_marker:
            command.extend(["--gate-marker", str(gate_marker)])

        result = self._run_command(command, step)

        if result['exit_code'] != 0:
            self._update_step_state(state, step, 'failed', start_time, error=result['stderr'])
            return False

        statistics = self._parse_mongo_statistics(result['stdout'])

        self._update_step_state(
            state,
            step,
            'completed',
            start_time,
            statistics=statistics,
        )

        if stage == "initial":
            state['pass_a_elements'] = str(elements_file)
        state['tenant_key'] = self.tenant_key

        if statistics:
            stats_str = ", ".join([f"{k}: {v}" for k, v in statistics.items()])
            self.logger.info(f"[{step}] Statistics: {stats_str}")

        return True

    def _handle_pass_e_failure(self, state: Dict, reason: str) -> None:
        """Mark the job as failed when Pass E or downstream validation fails."""
        state['status'] = 'failed'
        state['failure_reason'] = reason
        state['failed_at'] = datetime.utcnow().isoformat() + 'Z'
        self._save_state(state)
        self.logger.error("Post-Pass E pipeline failure (%s); job marked failed.", reason)

    def _print_summary(self) -> None:
        """Print processing summary."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("Ingestion Summary")
        self.logger.info(f"Total files: {self.stats['total']}")
        self.logger.info(f"Completed: {self.stats['completed']}")
        self.logger.info(f"Failed: {self.stats['failed']}")
        self.logger.info(f"Skipped: {self.stats['skipped']}")
        self.logger.info("=" * 60)


# ═══════════════════════════════════════════════════════════════════════════
# SETUP AND UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def setup_logging(mode: ProcessingMode, log_level: str, force: bool = False) -> None:
    """
    Setup logging configuration.

    Args:
        mode: Processing mode
        log_level: Logging level
    """
    # Create log directory
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Log filename with timestamp
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    log_file = LOG_DIR / f"{timestamp}_ingestion.log"

    # Logging format
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Configure root logger
    level = getattr(logging, log_level.upper(), logging.INFO)

    # File handler (always enabled)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Console handler (depends on mode)
    handlers = [file_handler]

    if mode != ProcessingMode.BATCH:
        # Enable console output for ad-hoc and selective modes
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(console_handler)

    # Configure logging
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
        force=force
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging to: {log_file}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='TTRPG Document Ingestion Pipeline Wrapper',
        add_help=False
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['batch', 'ad-hoc', 'selective'],
        required=True,
        help='Execution mode (required)'
    )
    parser.add_argument(
        '--files',
        type=Path,
        nargs='+',
        metavar='FILE',
        help='Files for selective mode (required for selective)'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=1,
        metavar='N',
        help='Max concurrent file processing per container (default: 1)'
    )
    parser.add_argument(
        '--container-limit',
        type=int,
        default=1,
        metavar='N',
        help='Max Unstructured containers to use for load balancing (default: 1)'
    )
    parser.add_argument(
        '--transfer-root',
        type=Path,
        default=None,
        help=f'Override Transfer Station root (default: {TRANSFER_ROOT})'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['debug', 'info', 'warning'],
        default='info',
        help='Logging verbosity (default: info)'
    )
    parser.add_argument(
        '--clean-run',
        action='store_true',
        help='Dangerous: clear databases and Transfer Station outputs before processing'
    )
    parser.add_argument(
        '--clean-force',
        action='store_true',
        help='Skip interactive confirmation for --clean-run (use with caution)'
    )
    parser.add_argument(
        '--tenant-id',
        type=str,
        default='default',
        help='Tenant identifier for multi-tenant data stores (default: default)'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'ingestion_wrapper v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    args = parser.parse_args()

    # Validate selective mode
    if args.mode == 'selective' and not args.files:
        parser.error("--files is required when using --mode selective")

    # Validate concurrency
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    # Validate container limit
    if args.container_limit < 1:
        parser.error("--container-limit must be >= 1")

    # Validate files exist (for selective mode)
    if args.files:
        for file_path in args.files:
            if not file_path.exists():
                parser.error(f"File not found: {file_path}")
            if not file_path.is_file():
                parser.error(f"Not a file: {file_path}")

    return args


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        # Determine transfer root override before any filesystem operations
        transfer_root = Path(args.transfer_root).expanduser() if args.transfer_root else get_transfer_root()
        _refresh_paths(transfer_root)
        os.environ[ENV_TRANSFER_ROOT] = str(transfer_root)

        # Convert mode string to enum by matching enum values
        mode_map = {
            'batch': ProcessingMode.BATCH,
            'ad-hoc': ProcessingMode.AD_HOC,
            'selective': ProcessingMode.SELECTIVE
        }
        mode = mode_map[args.mode]

        if args.clean_run and not args.clean_force:
            if not prompt_clean_confirmation():
                print("Clean run aborted by user", file=sys.stderr)
                return 1

        # Setup logging
        setup_logging(mode, args.log_level)

        # Create pipeline
        pipeline = IngestionPipeline(
            mode=mode,
            concurrency=args.concurrency,
            container_limit=args.container_limit,
            log_level=args.log_level,
            clean_run=args.clean_run,
            tenant_id=args.tenant_id,
            transfer_root=transfer_root
        )

        # Run pipeline
        return pipeline.run(files=args.files)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())






