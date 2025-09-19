# src_common/admin/ingestion.py
"""
Ingestion Console Service - ADM-002
Environment-scoped ingestion job monitoring and management
"""

import json
import time
import asyncio
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

from ..ttrpg_logging import get_logger
from .logs import AdminLogService


logger = get_logger(__name__)


@dataclass
class IngestionJob:
    """Ingestion job information"""
    job_id: str
    environment: str
    status: str  # 'running', 'completed', 'failed', 'pending'
    created_at: float
    started_at: Optional[float]
    completed_at: Optional[float]
    source_file: str
    total_phases: int
    completed_phases: int
    current_phase: Optional[str] = None
    job_type: str = "unknown"
    error_message: Optional[str] = None
    artifacts_path: Optional[str] = None
    process_id: Optional[int] = None
    lane: str = "A"
    hgrn_enabled: bool = False
    hgrn_report_path: Optional[str] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return None
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage"""
        if self.total_phases == 0:
            return 0.0
        return (self.completed_phases / self.total_phases) * 100.0


@dataclass
class JobLogEntry:
    """Log entry for ingestion job"""
    timestamp: float
    level: str
    phase: str
    message: str
    metadata: Dict[str, Any]


@dataclass
class IngestionMetrics:
    """Real-time metrics for ingestion observability"""
    job_id: str
    environment: str
    timestamp: float
    phase: str
    status: str  # 'started', 'progress', 'completed', 'failed'
    total_sources: int
    processed_sources: int
    current_source: Optional[str]
    records_processed: int
    records_failed: int
    processing_rate: float  # records per second
    estimated_completion: Optional[float]
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class PhaseProgress:
    """Progress tracking for individual phases"""
    phase: str
    status: str
    start_time: float
    current_time: float
    total_items: int
    completed_items: int
    failed_items: int
    current_item: Optional[str]
    processing_rate: float
    estimated_completion: Optional[float]

    @property
    def progress_percent(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100.0

    @property
    def duration_seconds(self) -> float:
        return self.current_time - self.start_time


class AdminIngestionService:
    """
    Ingestion Console Service
    
    Provides monitoring and management capabilities for ingestion jobs
    across all environments with proper isolation.
    """
    
    def __init__(self):
        self.environments = ['dev', 'test', 'prod']
        self._active_jobs = {}  # Track running async tasks
        self._pass_sequence = ["A", "B", "C", "D", "E", "F", "G"]  # Lane A pipeline phases
        self._metrics_callbacks: List[Callable[[IngestionMetrics], None]] = []  # FR-034: Metrics broadcasting
        self._job_progress: Dict[str, Dict[str, PhaseProgress]] = {}  # Track phase progress per job
        self.log_service = AdminLogService()
        logger.info("Admin Ingestion Service initialized")
    
    async def get_ingestion_overview(self) -> Dict[str, Any]:
        """
        Get overview of ingestion status across all environments
        
        Returns:
            Dictionary with job counts and status summaries per environment
        """
        try:
            overview = {
                "timestamp": time.time(),
                "environments": {}
            }
            
            for env in self.environments:
                env_jobs = await self.list_jobs(env)
                
                # Calculate statistics
                status_counts = {}
                for job in env_jobs:
                    status = job['status']
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                overview["environments"][env] = {
                    "total_jobs": len(env_jobs),
                    "status_breakdown": status_counts,
                    "recent_jobs": env_jobs[:5],  # Last 5 jobs
                    "artifacts_path": f"artifacts/{env}"
                }
            
            return overview
            
        except Exception as e:
            logger.error(f"Error getting ingestion overview: {e}")
            raise
    
    async def list_jobs(self, environment: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List ingestion jobs for a specific environment
        
        Args:
            environment: Environment name (dev/test/prod)
            limit: Maximum number of jobs to return
            
        Returns:
            List of job dictionaries sorted by creation time (newest first)
        """
        try:
            artifacts_path = Path(f"artifacts/{environment}")
            
            if not artifacts_path.exists():
                return []
            
            jobs = []
            
            # Scan for job directories
            for job_dir in artifacts_path.iterdir():
                if job_dir.is_dir() and job_dir.name != "ingest":
                    job_info = await self._load_job_info(environment, job_dir.name)
                    if job_info:
                        jobs.append(asdict(job_info))
            
            # Also check ingest subdirectory
            ingest_path = artifacts_path / "ingest" / environment
            if ingest_path.exists():
                for job_dir in ingest_path.iterdir():
                    if job_dir.is_dir():
                        job_info = await self._load_job_info(environment, job_dir.name, ingest_path)
                        if job_info:
                            jobs.append(asdict(job_info))
            
            # Sort by creation time (newest first) and apply limit
            jobs.sort(key=lambda x: x['created_at'], reverse=True)
            return jobs[:limit]
            
        except Exception as e:
            logger.error(f"Error listing jobs for {environment}: {e}")
            return []
    
    async def get_job_details(self, environment: str, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific job
        
        Args:
            environment: Environment name
            job_id: Job identifier
            
        Returns:
            Job details dictionary or None if not found
        """
        try:
            job_info = await self._find_job(environment, job_id)
            if not job_info:
                return None
            
            # Get additional details
            job_dict = asdict(job_info)
            
            # Add artifact information
            if job_info.artifacts_path:
                artifacts = await self._get_job_artifacts(job_info.artifacts_path)
                job_dict["artifacts"] = artifacts
            
            # Add recent logs
            logs = await self.get_job_logs(environment, job_id, limit=100)
            job_dict["recent_logs"] = logs
            
            return job_dict
            
        except Exception as e:
            logger.error(f"Error getting job details for {environment}/{job_id}: {e}")
            return None
    
    async def get_job_logs(self, environment: str, job_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get log entries for a specific job
        
        Args:
            environment: Environment name
            job_id: Job identifier
            limit: Maximum number of log entries
            
        Returns:
            List of log entry dictionaries
        """
        try:
            # Look for job-specific log files
            log_paths = [
                Path(f"env/{environment}/logs/{job_id}.log"),
                Path(f"artifacts/{environment}/{job_id}/job.log"),
                Path(f"artifacts/ingest/{environment}/{job_id}/job.log")
            ]
            
            logs = []
            
            for log_path in log_paths:
                if log_path.exists():
                    logs.extend(await self._parse_log_file(log_path, job_id))
            
            # If no job-specific logs, get relevant entries from main log
            if not logs:
                logs = await self._get_main_log_entries(environment, job_id, limit)
            
            # Sort by timestamp and apply limit
            logs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return logs[:limit]
            
        except Exception as e:
            logger.error(f"Error getting job logs for {environment}/{job_id}: {e}")
            return []
    
    async def start_ingestion_job(
        self,
        environment: str,
        source_file: str,
        options: Optional[Dict[str, Any]] = None,
        job_type: str = "ad_hoc",
        lane: str = "A",
    ) -> str:
        """
        Start a new ingestion job with unified pipeline execution

        Args:
            environment: Target environment
            source_file: Path to source PDF file or comma-separated list for selective
            options: Additional job options including selected_sources for selective jobs
            job_type: Type of job ("ad_hoc", "nightly", or "selective")

        Returns:
            Job ID for the new job
        """
        try:
            # Generate job ID and log file name based on job type
            timestamp = datetime.now()

            if job_type == "nightly":
                # Nightly jobs use special naming pattern
                formatted_time = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
                job_id = f"nightly_{formatted_time}_{environment}"
                log_filename = f"nightly_ingestion_{formatted_time}.log"
            elif job_type == "selective":
                # Selective jobs use descriptive naming
                job_id = f"selective_{int(timestamp.timestamp())}_{environment}"
                log_filename = f"selective_ingestion_{int(timestamp.timestamp())}.log"
            else:
                # Ad-hoc jobs use timestamp-based naming
                job_id = f"job_{int(timestamp.timestamp())}_{environment}"
                log_filename = f"{job_id}.log"

            options_dict = options or {}
            lane_value = "A"
            if job_type == "nightly" and options_dict.get("lane"):
                candidate = str(options_dict.get("lane"))
                if candidate.upper() in {"A", "B", "C"}:
                    lane_value = candidate.upper()

            # Create job directory
            job_path = Path(f"artifacts/{environment}/{job_id}")
            job_path.mkdir(parents=True, exist_ok=True)

            # Ensure logs directory exists for environment
            logs_dir = Path(f"env/{environment}/logs")
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Handle selective source processing
            selected_sources = None
            if job_type == "selective":
                selected_sources = options_dict.get("selected_sources", [])
                if isinstance(selected_sources, str):
                    selected_sources = [s.strip() for s in selected_sources.split(",")]
                if not selected_sources:
                    raise ValueError("Selective ingestion requires selected_sources in options")

            # Create job manifest
            job_manifest = {
                "job_id": job_id,
                "environment": environment,
                "source_file": source_file,
                "status": "pending",
                "created_at": timestamp.timestamp(),
                "options": options_dict,
                "job_type": job_type,
                "lane": lane_value,
                "log_file": log_filename,
                "phases": ["A", "B", "C", "D", "E", "F", "G"],
                "hgrn_enabled": options_dict.get("hgrn_enabled", True),
                "selected_sources": selected_sources,
                "source_count": len(selected_sources) if selected_sources else 1,
                "pipeline_version": "unified_v1"
            }

            manifest_file = job_path / "manifest.json"
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(job_manifest, f, indent=2)

            # Create log file path for the job
            log_file_path = logs_dir / log_filename
            log_lines = [
                f"[{timestamp.isoformat()}] Ingestion job created",
                f"job_id={job_id} environment={environment} type={job_type}",
                f"lane={lane_value}",
            ]
            if source_file:
                log_lines.append(f"source={source_file}")
            if options_dict:
                log_lines.append(f"options={json.dumps(options_dict, sort_keys=True)}")
            with open(log_file_path, 'w', encoding='utf-8') as log_file:
                log_file.write("\n".join(log_lines) + "\n")

            # Pre-flight validation: Verify source files exist and are readable
            validation_results = await self._validate_source_files(
                environment, source_file, selected_sources, log_file_path
            )

            if not validation_results["all_valid"]:
                # Update job status to failed and log errors
                await self._append_log(log_file_path,
                    f"[{datetime.now().isoformat()}] Pre-flight validation failed: {validation_results['summary']}")

                # Update manifest with failure
                job_manifest["status"] = "failed"
                job_manifest["error_message"] = f"Pre-flight validation failed: {validation_results['summary']}"
                job_manifest["completed_at"] = datetime.now().timestamp()
                with open(manifest_file, 'w', encoding='utf-8') as f:
                    json.dump(job_manifest, f, indent=2)

                raise ValueError(f"Source file validation failed: {validation_results['summary']}")

            self._start_ingestion_pipeline(
                job_id=job_id,
                environment=environment,
                job_path=job_path,
                manifest=job_manifest.copy(),
                manifest_file=manifest_file,
                log_file_path=log_file_path,
                lane=lane_value,
                job_type=job_type,
                options=options_dict,
            )

            logger.info(f"Created {job_type} ingestion job {job_id} for {environment} with log file {log_filename}")

            # In a real implementation, this would trigger the actual ingestion pipeline
            # For now, we just create the job structure

            return job_id

        except Exception as e:
            logger.error(f"Error starting ingestion job: {e}")
            raise

    def _start_ingestion_pipeline(
        self,
        job_id: str,
        environment: str,
        job_path: Path,
        manifest: Dict[str, Any],
        manifest_file: Path,
        log_file_path: Path,
        lane: str,
        job_type: str,
        options: Dict[str, Any],
    ) -> None:
        if os.getenv("DISABLE_INGESTION_RUNNER", "").lower() in {"1", "true", "yes"}:
            logger.info(f"Ingestion runner disabled for job {job_id}")
            return

        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Create the task
            task = asyncio.create_task(
                self._run_ingestion_pipeline(
                    job_id=job_id,
                    environment=environment,
                    manifest=manifest,
                    manifest_file=manifest_file,
                    log_file_path=log_file_path,
                    lane=lane,
                    job_type=job_type,
                    options=options,
                )
            )
            self._active_jobs[job_id] = task

            def _cleanup(_):
                self._active_jobs.pop(job_id, None)
                logger.info(f"Cleaned up task for job {job_id}")

            task.add_done_callback(_cleanup)
            logger.info(f"Started ingestion pipeline task for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to start ingestion pipeline for job {job_id}: {e}")
            # Update manifest to show failure
            try:
                manifest["status"] = "failed"
                manifest["error_message"] = f"Failed to start pipeline: {str(e)}"
                with open(manifest_file, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)
            except Exception as manifest_error:
                logger.error(f"Failed to update manifest after pipeline start failure: {manifest_error}")

    async def _run_ingestion_pipeline(
        self,
        job_id: str,
        environment: str,
        manifest: Dict[str, Any],
        manifest_file: Path,
        log_file_path: Path,
        lane: str,
        job_type: str,
        options: Dict[str, Any],
    ) -> None:
        try:
            start_ts = time.time()
            manifest["status"] = "running"
            manifest["started_at"] = start_ts
            manifest["current_phase"] = None
            manifest["completed_phases"] = 0
            await self._write_manifest(manifest_file, manifest)
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Job {job_id} started lane={lane}")

            job_path = manifest_file.parent

            # Execute unified Lane A pipeline
            await self.execute_lane_a_pipeline(
                job_id=job_id,
                environment=environment,
                manifest=manifest,
                job_path=job_path,
                log_file_path=log_file_path
            )

            manifest["current_phase"] = None
            manifest["status"] = "completed"
            manifest["completed_at"] = time.time()
            await self._write_manifest(manifest_file, manifest)
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Job {job_id} completed successfully")

        except Exception as exc:
            manifest["status"] = "failed"
            manifest["current_phase"] = None
            manifest["error_message"] = str(exc)
            manifest["completed_at"] = time.time()
            await self._write_manifest(manifest_file, manifest)
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Job {job_id} failed: {exc}")
            logger.exception("Ingestion pipeline failed for %s", job_id)

    async def _write_manifest(self, manifest_file: Path, manifest: Dict[str, Any]) -> None:
        def _write() -> None:
            manifest_file.parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_file, 'w', encoding='utf-8') as handle:
                json.dump(manifest, handle, indent=2)

        await asyncio.to_thread(_write)

    async def _append_log(self, log_file_path: Path, message: str) -> None:
        def _write() -> None:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file_path, 'a', encoding='utf-8') as handle:
                handle.write(message + "\n")

        await asyncio.to_thread(_write)

    async def execute_lane_a_pipeline(
        self,
        job_id: str,
        environment: str,
        manifest: Dict[str, Any],
        job_path: Path,
        log_file_path: Path
    ) -> None:
        """
        Real Lane A pipeline execution implementing Passes A-G

        Args:
            job_id: Job identifier
            environment: Environment name
            manifest: Job manifest with configuration
            job_path: Path to job artifacts directory
            log_file_path: Path to job log file
        """
        try:
            job_type = manifest.get("job_type", "ad_hoc")
            selected_sources = manifest.get("selected_sources", [])

            logger.info(f"Starting Lane A pipeline (Passes A-G) for {job_type} job {job_id}")
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Starting Lane A pipeline (Passes A-G)")

            # Determine sources to process
            if job_type == "selective" and selected_sources:
                sources_to_process = selected_sources
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Processing {len(sources_to_process)} selected sources")
            else:
                source_file = manifest.get("source_file", "unknown.pdf")
                if not source_file or source_file == "unknown.pdf":
                    raise ValueError("No valid source file specified for ingestion")
                sources_to_process = [source_file]
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Processing single source: {sources_to_process[0]}")

            # Initialize job progress tracking
            if job_id not in self._job_progress:
                self._job_progress[job_id] = {}

            # Process each source file through Passes A-G
            for source_file in sources_to_process:
                # Resolve source file path
                source_path = await self._resolve_source_path(source_file, environment)
                if not source_path.exists():
                    raise FileNotFoundError(f"Source file not found: {source_path}")

                # Gate 0: SHA-based bypass check
                should_bypass = await self._check_gate_0_bypass(source_path, job_path, log_file_path)
                if should_bypass:
                    await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Gate 0: Bypassing {source_file} - already up to date")
                    continue

                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Gate 0: Processing {source_file} - changes detected")

                # Execute Passes A-G in sequence
                manifest_file = job_path / "manifest.json"

                for idx, pass_name in enumerate(self._pass_sequence, start=1):
                    phase_start_time = time.time()

                    # Initialize phase progress
                    self._job_progress[job_id][pass_name] = PhaseProgress(
                        phase=pass_name,
                        status="started",
                        start_time=phase_start_time,
                        current_time=phase_start_time,
                        total_items=1,
                        completed_items=0,
                        failed_items=0,
                        current_item=source_file,
                        processing_rate=0.0,
                        estimated_completion=None
                    )

                    # Emit start metrics
                    await self._emit_metrics(IngestionMetrics(
                        job_id=job_id,
                        environment=environment,
                        timestamp=phase_start_time,
                        phase=pass_name,
                        status="started",
                        total_sources=len(sources_to_process),
                        processed_sources=0,
                        current_source=source_file,
                        records_processed=0,
                        records_failed=0,
                        processing_rate=0.0,
                        estimated_completion=None
                    ))

                    # Execute the actual pass
                    pass_result = await self._execute_real_pass(
                        pass_name=pass_name,
                        source_path=source_path,
                        job_path=job_path,
                        job_id=job_id,
                        environment=environment,
                        log_file_path=log_file_path
                    )

                    # Update phase progress
                    phase_end_time = time.time()
                    phase_progress = self._job_progress[job_id][pass_name]
                    phase_progress.status = "completed"
                    phase_progress.current_time = phase_end_time
                    phase_progress.completed_items = 1
                    phase_progress.processing_rate = self._calculate_processing_rate(1, phase_progress.duration_seconds)

                    # Update manifest with pass results
                    manifest[f"pass_{pass_name.lower()}_result"] = pass_result
                    manifest["completed_phases"] = idx

                    # Emit completion metrics
                    await self._emit_metrics(IngestionMetrics(
                        job_id=job_id,
                        environment=environment,
                        timestamp=phase_end_time,
                        phase=pass_name,
                        status="completed",
                        total_sources=len(sources_to_process),
                        processed_sources=1,
                        current_source=source_file,
                        records_processed=pass_result.get("processed_count", 0),
                        records_failed=0,
                        processing_rate=phase_progress.processing_rate,
                        estimated_completion=None
                    ))

                    await self._append_log(log_file_path,
                        f"[{datetime.now().isoformat()}] Pass {pass_name} completed: "
                        f"processed={pass_result.get('processed_count', 0)}, "
                        f"artifacts={pass_result.get('artifact_count', 0)}, "
                        f"duration={phase_progress.duration_seconds:.2f}s")

            logger.info(f"Lane A pipeline (Passes A-G) completed for job {job_id}")
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Lane A pipeline completed successfully")

        except Exception as e:
            logger.error(f"Error in Lane A pipeline for job {job_id}: {e}")
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pipeline failed: {str(e)}")
            raise

    async def _resolve_source_path(self, source_file: str, environment: str) -> Path:
        """Resolve source file path with environment-aware configuration and proper validation"""
        # Get uploads directory from environment configuration
        uploads_dir = os.getenv('UPLOADS_DIR', f"env/{environment}/data/uploads")

        # Try environment-specific path first (highest priority)
        env_specific_dirs = [
            Path(uploads_dir),
            Path(f"env/{environment}/data/uploads"),
        ]

        # Fallback paths for compatibility
        fallback_dirs = [
            Path("uploads"),
            Path("data/uploads"),
            Path(".")  # Current directory as last resort
        ]

        all_upload_dirs = env_specific_dirs + fallback_dirs

        # Try each directory in priority order
        for upload_dir in all_upload_dirs:
            potential_path = upload_dir / source_file
            if potential_path.exists() and potential_path.is_file():
                logger.info(f"Resolved source file '{source_file}' to '{potential_path.absolute()}'")
                return potential_path.resolve()  # Return absolute path

        # If not found in upload dirs, try as absolute path
        source_path = Path(source_file)
        if source_path.exists() and source_path.is_file():
            logger.info(f"Using absolute path for source file: '{source_path.absolute()}'")
            return source_path.resolve()

        # Log attempted paths for debugging
        attempted_paths = [str((upload_dir / source_file).absolute()) for upload_dir in all_upload_dirs]
        logger.error(f"Source file '{source_file}' not found. Attempted paths: {attempted_paths}")

        # Return environment-specific path for clear error reporting
        preferred_path = env_specific_dirs[0] / source_file
        return preferred_path

    async def _validate_source_files(
        self,
        environment: str,
        source_file: str,
        selected_sources: Optional[List[str]],
        log_file_path: Path
    ) -> Dict[str, Any]:
        """
        Pre-flight validation to verify source files exist and are readable

        Returns:
            Dict containing validation results with 'all_valid' boolean and detailed results
        """
        validation_results = {
            "all_valid": True,
            "valid_files": [],
            "invalid_files": [],
            "summary": "",
            "details": {}
        }

        try:
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Starting pre-flight validation")

            # Determine which source files to validate
            files_to_validate = []
            if selected_sources:
                # Selective ingestion - validate all selected sources
                files_to_validate = selected_sources
                await self._append_log(log_file_path, f"Validating {len(selected_sources)} selected sources")
            elif source_file and source_file not in ["nightly_run"]:
                # Single file ingestion (exclude special nightly placeholder)
                files_to_validate = [source_file]
                await self._append_log(log_file_path, f"Validating single source: {source_file}")
            else:
                # Nightly runs or special cases - skip validation
                await self._append_log(log_file_path, "Skipping validation for special job type")
                validation_results["summary"] = "Validation skipped for special job type"
                return validation_results

            # Validate each source file
            for file_name in files_to_validate:
                try:
                    resolved_path = await self._resolve_source_path(file_name, environment)

                    if resolved_path.exists() and resolved_path.is_file():
                        # Check if file is readable and get size
                        file_size = resolved_path.stat().st_size
                        validation_results["valid_files"].append({
                            "name": file_name,
                            "path": str(resolved_path.absolute()),
                            "size_bytes": file_size,
                            "size_mb": round(file_size / (1024 * 1024), 2)
                        })
                        await self._append_log(log_file_path,
                            f"✓ {file_name} -> {resolved_path.absolute()} ({round(file_size / (1024 * 1024), 2)} MB)")
                    else:
                        validation_results["invalid_files"].append({
                            "name": file_name,
                            "expected_path": str(resolved_path.absolute()),
                            "error": "File not found or not readable"
                        })
                        validation_results["all_valid"] = False
                        await self._append_log(log_file_path,
                            f"✗ {file_name} -> NOT FOUND at {resolved_path.absolute()}")

                except Exception as e:
                    validation_results["invalid_files"].append({
                        "name": file_name,
                        "error": f"Validation error: {str(e)}"
                    })
                    validation_results["all_valid"] = False
                    await self._append_log(log_file_path, f"✗ {file_name} -> ERROR: {str(e)}")

            # Generate summary
            valid_count = len(validation_results["valid_files"])
            invalid_count = len(validation_results["invalid_files"])

            if validation_results["all_valid"]:
                validation_results["summary"] = f"All {valid_count} source file(s) validated successfully"
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] ✓ Pre-flight validation passed")
            else:
                invalid_names = [f["name"] for f in validation_results["invalid_files"]]
                validation_results["summary"] = f"{invalid_count} file(s) failed validation: {invalid_names}"
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] ✗ Pre-flight validation failed")

            validation_results["details"] = {
                "total_files": len(files_to_validate),
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "validation_timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            validation_results["all_valid"] = False
            validation_results["summary"] = f"Validation process error: {str(e)}"
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] ✗ Validation process failed: {str(e)}")

        return validation_results

    async def _check_gate_0_bypass(self, source_path: Path, job_path: Path, log_file_path: Path) -> bool:
        """
        Gate 0: Check if file should be bypassed based on SHA and chunk count cache

        Returns True if file should be bypassed (already up to date)
        """
        try:
            # Calculate current file SHA
            current_sha = await self._calculate_file_sha(source_path)

            # Check cache file
            cache_file = job_path / "source_cache.json"
            if not cache_file.exists():
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Gate 0: No cache found, proceeding with ingestion")
                return False

            # Load cache data
            cache_data = json.loads(cache_file.read_text())
            cached_sha = cache_data.get("file_sha")
            cached_chunk_count = cache_data.get("chunk_count", 0)

            if current_sha == cached_sha and cached_chunk_count > 0:
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Gate 0: SHA match ({current_sha[:8]}) with {cached_chunk_count} chunks - bypassing")
                return True

            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Gate 0: SHA mismatch or no chunks - proceeding with ingestion")
            return False

        except Exception as e:
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Gate 0: Cache check failed - {e}")
            return False

    async def _calculate_file_sha(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        def _compute():
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()

        return await asyncio.to_thread(_compute)

    async def _execute_real_pass(
        self,
        pass_name: str,
        source_path: Path,
        job_path: Path,
        job_id: str,
        environment: str,
        log_file_path: Path
    ) -> Dict[str, Any]:
        """Execute actual pass implementation instead of stub"""
        try:
            if pass_name == "A":
                return await self._execute_pass_a(source_path, job_path, job_id, environment, log_file_path)
            elif pass_name == "B":
                return await self._execute_pass_b(source_path, job_path, job_id, environment, log_file_path)
            elif pass_name == "C":
                return await self._execute_pass_c(source_path, job_path, job_id, environment, log_file_path)
            elif pass_name == "D":
                return await self._execute_pass_d(source_path, job_path, job_id, environment, log_file_path)
            elif pass_name == "E":
                return await self._execute_pass_e(source_path, job_path, job_id, environment, log_file_path)
            elif pass_name == "F":
                return await self._execute_pass_f(source_path, job_path, job_id, environment, log_file_path)
            elif pass_name == "G":
                return await self._execute_pass_g(source_path, job_path, job_id, environment, log_file_path)
            else:
                raise ValueError(f"Unknown pass: {pass_name}")

        except Exception as e:
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass {pass_name} failed: {str(e)}")
            raise

    async def _execute_pass_a(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass A: TOC → Metadata via OpenAI"""
        from ..pass_a_toc_parser import process_pass_a

        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass A: TOC parsing and metadata extraction")

        def _run_pass_a():
            return process_pass_a(source_path, job_path, job_id, environment)

        result = await asyncio.to_thread(_run_pass_a)

        return {
            "processed_count": result.dictionary_entries,
            "artifact_count": len(result.artifacts),
            "sections_parsed": result.sections_parsed,
            "duration_ms": result.processing_time_ms,
            "success": result.success,
            "error_message": result.error_message
        }

    async def _execute_pass_b(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass B: Size-based Split (>25 MB)"""
        from ..pass_b_logical_splitter import process_pass_b

        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass B: Logical splitting check")

        def _run_pass_b():
            return process_pass_b(source_path, job_path, job_id, environment)

        result = await asyncio.to_thread(_run_pass_b)

        return {
            "processed_count": result.parts_created,
            "artifact_count": len(result.artifacts),
            "split_performed": result.split_performed,
            "total_pages": result.total_pages,
            "duration_ms": result.processing_time_ms,
            "success": result.success,
            "error_message": result.error_message
        }

    async def _execute_pass_c(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass C: Unstructured.io → Chunking"""
        from ..pass_c_extraction import process_pass_c

        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass C: Unstructured.io extraction")

        def _run_pass_c():
            return process_pass_c(source_path, job_path, job_id, environment)

        result = await asyncio.to_thread(_run_pass_c)

        return {
            "processed_count": result.chunks_extracted,
            "artifact_count": len(result.artifacts),
            "chunks_loaded": result.chunks_loaded,
            "parts_processed": result.parts_processed,
            "duration_ms": result.processing_time_ms,
            "success": result.success,
            "error_message": result.error_message
        }

    async def _execute_pass_d(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass D: Haystack Enrichment"""
        from ..pass_d_vector_enrichment import process_pass_d

        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass D: Haystack enrichment and vectorization")

        def _run_pass_d():
            return process_pass_d(job_path, job_id, environment)

        result = await asyncio.to_thread(_run_pass_d)

        return {
            "processed_count": result.chunks_vectorized if hasattr(result, 'chunks_vectorized') else 0,
            "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 0,
            "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
            "success": result.success if hasattr(result, 'success') else True,
            "error_message": result.error_message if hasattr(result, 'error_message') else None
        }

    async def _execute_pass_e(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass E: LlamaIndex Graph"""
        from ..pass_e_graph_builder import process_pass_e

        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass E: LlamaIndex graph building")

        def _run_pass_e():
            return process_pass_e(job_path, job_id, environment)

        result = await asyncio.to_thread(_run_pass_e)

        return {
            "processed_count": result.chunks_processed if hasattr(result, 'chunks_processed') else 0,
            "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 0,
            "graph_nodes": result.graph_nodes if hasattr(result, 'graph_nodes') else 0,
            "graph_edges": result.graph_edges if hasattr(result, 'graph_edges') else 0,
            "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
            "success": result.success if hasattr(result, 'success') else True,
            "error_message": result.error_message if hasattr(result, 'error_message') else None
        }

    async def _execute_pass_f(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass F: Cleanup"""
        from ..pass_f_finalizer import process_pass_f

        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass F: Cleanup artifacts and temp files")

        def _run_pass_f():
            return process_pass_f(job_path, job_id, environment)

        result = await asyncio.to_thread(_run_pass_f)

        # Additionally update source cache for Gate 0
        file_sha = await self._calculate_file_sha(source_path)

        # Get chunk count from Pass C results
        chunk_count = 0
        pass_c_file = job_path / f"{job_id}_pass_c_raw_chunks.jsonl"
        if pass_c_file.exists():
            chunk_count = len(pass_c_file.read_text().strip().split('\n'))

        cache_data = {
            "file_sha": file_sha,
            "chunk_count": chunk_count,
            "last_updated": time.time(),
            "source_file": source_path.name
        }

        cache_file = job_path / "source_cache.json"
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

        return {
            "processed_count": result.processed_count if hasattr(result, 'processed_count') else 0,
            "artifact_count": len(result.artifacts) if hasattr(result, 'artifacts') else 1,
            "cache_updated": True,
            "file_sha": file_sha[:8],
            "chunk_count": chunk_count,
            "duration_ms": result.processing_time_ms if hasattr(result, 'processing_time_ms') else 0,
            "success": result.success if hasattr(result, 'success') else True,
            "error_message": result.error_message if hasattr(result, 'error_message') else None
        }

    async def _execute_pass_g(self, source_path: Path, job_path: Path, job_id: str, environment: str, log_file_path: Path) -> Dict[str, Any]:
        """Execute Pass G: HGRN Sanity Check"""
        await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass G: HGRN sanity checks")

        try:
            # Run HGRN validation if available
            hgrn_success = await self.run_pass_d_hgrn(job_id, environment, job_path)

            recommendations_count = 0
            high_priority_count = 0

            # Check for HGRN report
            hgrn_report_file = job_path / "hgrn_report.json"
            if hgrn_report_file.exists():
                hgrn_data = json.loads(hgrn_report_file.read_text())
                recommendations_count = len(hgrn_data.get("recommendations", []))
                high_priority_count = len([r for r in hgrn_data.get("recommendations", []) if r.get("priority") == "high"])

            return {
                "processed_count": 1,
                "artifact_count": 1 if hgrn_report_file.exists() else 0,
                "recommendations_count": recommendations_count,
                "high_priority_count": high_priority_count,
                "hgrn_success": hgrn_success,
                "success": True
            }

        except Exception as e:
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Pass G: HGRN failed - {str(e)}")
            return {
                "processed_count": 0,
                "artifact_count": 0,
                "success": False,
                "error_message": str(e)
            }

    async def _execute_phase_unified(
        self,
        phase: str,
        job_path: Path,
        manifest: Dict[str, Any],
        job_id: str,
        sources_to_process: List[str],
        log_file_path: Path
    ) -> Dict[str, Any]:
        """Execute a unified phase with enhanced progress tracking and selective source support"""
        try:
            phase_start = datetime.now()
            await self._append_log(log_file_path, f"[{phase_start.isoformat()}] Starting phase {phase}")

            processed_sources = []
            total_artifacts = 0
            phase_data = {
                "phase": phase,
                "job_id": job_id,
                "started_at": phase_start.isoformat(),
                "sources": []
            }

            for idx, source in enumerate(sources_to_process):
                # Update progress tracking
                if job_id in self._job_progress and phase in self._job_progress[job_id]:
                    phase_progress = self._job_progress[job_id][phase]
                    phase_progress.current_time = time.time()
                    phase_progress.current_item = source
                    phase_progress.completed_items = idx
                    phase_progress.processing_rate = self._calculate_processing_rate(
                        phase_progress.completed_items,
                        phase_progress.duration_seconds
                    )

                    # Emit progress metrics
                    await self._emit_metrics(IngestionMetrics(
                        job_id=job_id,
                        environment=manifest.get("environment", "unknown"),
                        timestamp=time.time(),
                        phase=phase,
                        status="progress",
                        total_sources=len(sources_to_process),
                        processed_sources=idx,
                        current_source=source,
                        records_processed=idx,
                        records_failed=0,
                        processing_rate=phase_progress.processing_rate,
                        estimated_completion=self._estimate_completion_time(
                            len(sources_to_process),
                            idx,
                            phase_progress.processing_rate
                        )
                    ))

                source_result = await self._execute_phase_for_source(phase, source, job_path, manifest, job_id)
                phase_data["sources"].append(source_result)
                processed_sources.append(source)
                total_artifacts += source_result.get("artifact_count", 0)

                await self._append_log(log_file_path,
                    f"[{datetime.now().isoformat()}] {phase} processed source '{source}': "
                    f"chunks={source_result.get('chunk_count', 0)}, "
                    f"artifacts={source_result.get('artifact_count', 0)}")

            # Create phase completion timestamp and checksum
            phase_end = datetime.now()
            phase_data.update({
                "completed_at": phase_end.isoformat(),
                "duration_seconds": (phase_end - phase_start).total_seconds(),
                "processed_sources": processed_sources,
                "total_sources": len(sources_to_process)
            })

            # Generate checksum for verification
            phase_content = json.dumps(phase_data, sort_keys=True)
            checksum = hashlib.sha256(phase_content.encode()).hexdigest()

            # Save phase results
            phase_file = job_path / f"phase_{phase}_results.json"
            await self._write_json_file(phase_file, phase_data)

            return {
                "phase": phase,
                "processed_count": len(processed_sources),
                "artifact_count": total_artifacts,
                "duration_seconds": phase_data["duration_seconds"],
                "checksum": checksum,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Error executing unified phase {phase} for job {job_id}: {e}")
            await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] Phase {phase} failed: {str(e)}")
            raise

    async def _execute_phase_for_source(
        self,
        phase: str,
        source: str,
        job_path: Path,
        manifest: Dict[str, Any],
        job_id: str
    ) -> Dict[str, Any]:
        """Execute a phase for a specific source with realistic artifact generation"""
        try:
            source_safe = source.replace('/', '_').replace('\\', '_').replace(':', '_').replace('.', '_')

            if phase == "parse":
                # Pass A: Create source-specific chunks from PDF parsing
                chunk_count = 15 + hash(source) % 10  # Vary chunk count by source
                chunks_data = {
                    "source_file": source,
                    "job_id": job_id,
                    "processed_at": datetime.now().isoformat(),
                    "chunk_count": chunk_count,
                    "chunks": [
                        {
                            "chunk_id": f"{source_safe}_chunk_{i}",
                            "content": f"Sample content from {source} chunk {i}",
                            "page": i % 10 + 1,
                            "metadata": {"source": source, "type": "text", "phase": "parse"}
                        }
                        for i in range(chunk_count)
                    ]
                }

                chunks_file = job_path / f"passA_chunks_{source_safe}.json"
                await self._write_json_file(chunks_file, chunks_data)

                return {
                    "source": source,
                    "chunk_count": chunk_count,
                    "artifact_count": 1,
                    "artifacts": [str(chunks_file.name)]
                }

            elif phase == "enrich":
                # Pass B: Create source-specific enriched content data
                entities_count = 20 + hash(source) % 15
                enriched_data = {
                    "source_file": source,
                    "job_id": job_id,
                    "enriched_at": datetime.now().isoformat(),
                    "enrichment_results": {
                        "entities_extracted": entities_count,
                        "keywords_identified": entities_count // 2,
                        "semantic_tags_added": entities_count // 3
                    },
                    "dictionary_updates": [
                        {"term": f"term_from_{source_safe}_{i}", "definition": f"Definition {i} from {source}"}
                        for i in range(3)
                    ]
                }

                enriched_file = job_path / f"passB_enriched_{source_safe}.json"
                await self._write_json_file(enriched_file, enriched_data)

                return {
                    "source": source,
                    "entities_count": entities_count,
                    "artifact_count": 1,
                    "artifacts": [str(enriched_file.name)]
                }

            elif phase == "compile":
                # Pass C: Create source-specific graph compilation results
                nodes_count = 30 + hash(source) % 20
                graph_data = {
                    "source_file": source,
                    "job_id": job_id,
                    "compiled_at": datetime.now().isoformat(),
                    "graph_structure": {
                        "nodes": nodes_count,
                        "edges": int(nodes_count * 1.2),
                        "clusters": max(1, nodes_count // 8)
                    },
                    "compilation_status": "completed"
                }

                graph_file = job_path / f"passC_graph_{source_safe}.json"
                await self._write_json_file(graph_file, graph_data)

                return {
                    "source": source,
                    "nodes_count": nodes_count,
                    "artifact_count": 1,
                    "artifacts": [str(graph_file.name)]
                }

            else:
                raise ValueError(f"Unknown phase: {phase}")

        except Exception as e:
            logger.error(f"Error executing phase {phase} for source {source}: {e}")
            raise

    async def _write_json_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Write JSON data to file asynchronously"""
        def _write() -> None:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=2)

        await asyncio.to_thread(_write)

    # ===========================
    # FR-034: Observability Methods
    # ===========================

    def register_metrics_callback(self, callback: Callable[[IngestionMetrics], None]) -> None:
        """Register a callback for real-time metrics broadcasting"""
        if callback not in self._metrics_callbacks:
            self._metrics_callbacks.append(callback)
            logger.debug(f"Registered metrics callback: {callback.__name__}")

    def unregister_metrics_callback(self, callback: Callable[[IngestionMetrics], None]) -> None:
        """Unregister a metrics callback"""
        if callback in self._metrics_callbacks:
            self._metrics_callbacks.remove(callback)
            logger.debug(f"Unregistered metrics callback: {callback.__name__}")

    async def _emit_metrics(self, metrics: IngestionMetrics) -> None:
        """Emit metrics to all registered callbacks"""
        try:
            for callback in self._metrics_callbacks:
                try:
                    # Handle both sync and async callbacks
                    if asyncio.iscoroutinefunction(callback):
                        await callback(metrics)
                    else:
                        callback(metrics)
                except Exception as e:
                    logger.error(f"Error in metrics callback {callback.__name__}: {e}")
        except Exception as e:
            logger.error(f"Error emitting metrics: {e}")

    def _calculate_processing_rate(self, completed_items: int, duration: float) -> float:
        """Calculate processing rate in items per second"""
        if duration <= 0:
            return 0.0
        return completed_items / duration

    def _estimate_completion_time(self, total_items: int, completed_items: int, rate: float) -> Optional[float]:
        """Estimate completion time based on current progress"""
        if rate <= 0 or completed_items >= total_items:
            return None
        remaining_items = total_items - completed_items
        estimated_seconds = remaining_items / rate
        return time.time() + estimated_seconds

    async def get_job_metrics(self, job_id: str) -> Dict[str, Any]:
        """Get current metrics for a specific job"""
        try:
            job_progress = self._job_progress.get(job_id, {})

            if not job_progress:
                return {
                    "job_id": job_id,
                    "status": "not_found",
                    "message": "Job not found or not started"
                }

            # Aggregate metrics across all phases
            total_items = sum(phase.total_items for phase in job_progress.values())
            completed_items = sum(phase.completed_items for phase in job_progress.values())
            failed_items = sum(phase.failed_items for phase in job_progress.values())

            current_phase = None
            for phase_name, phase in job_progress.items():
                if phase.status in ["started", "progress"]:
                    current_phase = phase_name
                    break

            overall_rate = 0.0
            if job_progress:
                total_duration = max(phase.duration_seconds for phase in job_progress.values())
                overall_rate = self._calculate_processing_rate(completed_items, total_duration)

            return {
                "job_id": job_id,
                "status": "running" if current_phase else "completed",
                "current_phase": current_phase,
                "overall_progress": {
                    "total_items": total_items,
                    "completed_items": completed_items,
                    "failed_items": failed_items,
                    "success_rate": (completed_items / total_items * 100) if total_items > 0 else 0,
                    "processing_rate": overall_rate
                },
                "phases": {
                    name: {
                        "status": phase.status,
                        "progress_percent": phase.progress_percent,
                        "duration_seconds": phase.duration_seconds,
                        "processing_rate": phase.processing_rate,
                        "current_item": phase.current_item
                    }
                    for name, phase in job_progress.items()
                },
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Error getting job metrics for {job_id}: {e}")
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e)
            }

    async def get_historical_job_metrics(self, environment: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get historical job metrics from manifest files for trend analysis"""
        try:
            historical_jobs = []
            artifacts_path = Path(f"artifacts/{environment}")

            if not artifacts_path.exists():
                return []

            # Find all job directories with manifest files
            job_dirs = [d for d in artifacts_path.iterdir() if d.is_dir() and (d / "manifest.json").exists()]

            # Sort by modification time (most recent first)
            job_dirs.sort(key=lambda x: (x / "manifest.json").stat().st_mtime, reverse=True)

            for job_dir in job_dirs[:limit]:
                manifest_file = job_dir / "manifest.json"
                try:
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)

                    # Extract metrics from manifest
                    job_metrics = {
                        "job_id": manifest.get("job_id"),
                        "job_type": manifest.get("job_type"),
                        "environment": manifest.get("environment"),
                        "created_at": manifest.get("created_at"),
                        "completed_at": manifest.get("completed_at"),
                        "status": manifest.get("status"),
                        "source_count": manifest.get("source_count", 1),
                        "phases": {}
                    }

                    # Extract phase-specific metrics
                    for phase in self._pass_sequence:
                        phase_key = f"{phase}_result"
                        if phase_key in manifest:
                            phase_result = manifest[phase_key]
                            job_metrics["phases"][phase] = {
                                "processed_count": phase_result.get("processed_count", 0),
                                "artifact_count": phase_result.get("artifact_count", 0),
                                "duration_seconds": phase_result.get("duration_seconds", 0),
                                "status": phase_result.get("status")
                            }

                    historical_jobs.append(job_metrics)

                except Exception as e:
                    logger.warning(f"Error reading manifest {manifest_file}: {e}")
                    continue

            return historical_jobs

        except Exception as e:
            logger.error(f"Error getting historical job metrics for {environment}: {e}")
            return []

    async def get_available_sources(self, environment: str) -> List[Dict[str, Any]]:
        """
        Get list of sources available for selective ingestion

        Args:
            environment: Environment name

        Returns:
            List of available source dictionaries with metadata
        """
        try:
            sources = []

            # Get sources from local artifacts (previously ingested)
            local_sources = await self._get_local_sources(environment)

            # Get sources from vector store (currently ingested)
            vector_sources = await self._get_vector_store_sources(environment)

            # Get uploaded files waiting to be ingested
            uploaded_sources = await self._get_uploaded_sources(environment)

            # Combine and deduplicate sources
            source_map = {}

            # Add uploaded sources (new files waiting to be ingested)
            for source in uploaded_sources:
                key = source.get('source_file', source.get('id', 'unknown'))
                source_map[key] = {
                    **source,
                    'available_for_ingestion': True,
                    'available_for_reingestion': False,
                    'is_new_upload': True,
                    'last_upload': source.get('last_modified', 0)
                }

            # Add local sources (previously ingested, can be re-ingested)
            for source in local_sources:
                key = source.get('source_file', source.get('id', 'unknown'))
                if key in source_map:
                    # Update existing uploaded file with reingestion capability
                    source_map[key].update({
                        'available_for_reingestion': True,
                        'last_local_ingestion': source.get('last_modified', 0)
                    })
                else:
                    source_map[key] = {
                        **source,
                        'available_for_reingestion': True,
                        'is_new_upload': False,
                        'last_local_ingestion': source.get('last_modified', 0)
                    }

            # Add/update with vector store sources
            for source in vector_sources:
                key = source.get('source_file', source.get('id', 'unknown'))
                if key in source_map:
                    source_map[key].update({
                        'in_database': True,
                        'chunk_count': source.get('chunk_count', 0),
                        'last_database_update': source.get('last_modified', 0)
                    })
                else:
                    source_map[key] = {
                        **source,
                        'available_for_reingestion': False,  # No local artifacts
                        'in_database': True,
                        'last_local_ingestion': None
                    }

            sources = list(source_map.values())

            # Sort by health and name for consistent ordering
            health_priority = {'red': 0, 'yellow': 1, 'green': 2}
            sources.sort(key=lambda x: (health_priority.get(x.get('health', 'red'), 0), x.get('source_file', x.get('id', ''))))

            logger.info(f"Found {len(sources)} available sources for {environment}")
            return sources

        except Exception as e:
            logger.error(f"Error getting available sources for {environment}: {e}")
            return []

    async def start_selective_ingestion_job(
        self,
        environment: str,
        selected_sources: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a selective ingestion job for specific sources

        Args:
            environment: Target environment
            selected_sources: List of source files or IDs to process
            options: Additional job options

        Returns:
            Job ID for the new selective job
        """
        try:
            if not selected_sources:
                raise ValueError("At least one source must be selected for selective ingestion")

            # Validate sources exist and are available for reingestion
            available_sources = await self.get_available_sources(environment)
            available_source_files = {s.get('source_file', s.get('id', '')) for s in available_sources if s.get('available_for_reingestion', False)}

            invalid_sources = [src for src in selected_sources if src not in available_source_files]
            if invalid_sources:
                raise ValueError(f"Sources not available for reingestion: {invalid_sources}")

            # Prepare options with selected sources
            selective_options = options or {}
            selective_options['selected_sources'] = selected_sources
            selective_options['source_validation'] = True

            # Create source file description for manifest
            source_file_desc = f"selective:{','.join(selected_sources[:3])}"
            if len(selected_sources) > 3:
                source_file_desc += f"+{len(selected_sources)-3}more"

            # Start the selective ingestion job
            job_id = await self.start_ingestion_job(
                environment=environment,
                source_file=source_file_desc,
                options=selective_options,
                job_type="selective",
                lane="A"
            )

            logger.info(f"Started selective ingestion job {job_id} for {len(selected_sources)} sources in {environment}")
            return job_id

        except Exception as e:
            logger.error(f"Error starting selective ingestion job: {e}")
            raise

    async def run_pass_d_hgrn(self, job_id: str, environment: str, artifacts_path: Path) -> bool:
        """
        Run Pass D HGRN validation on ingestion artifacts.

        Args:
            job_id: Ingestion job identifier
            environment: Environment name
            artifacts_path: Path to job artifacts directory

        Returns:
            True if HGRN validation completed successfully
        """
        try:
            logger.info(f"Starting Pass D HGRN validation for job {job_id} in {environment}")

            # Import HGRN runner
            from ..hgrn.runner import HGRNRunner

            # Initialize HGRN runner for environment
            hgrn_runner = HGRNRunner(environment=environment)

            # Run HGRN validation
            report = hgrn_runner.run_pass_d_validation(
                job_id=job_id,
                artifacts_path=artifacts_path
            )

            # Update job manifest with HGRN results
            manifest_file = artifacts_path / "manifest.json"
            if manifest_file.exists():
                manifest = json.loads(manifest_file.read_text())
                manifest["hgrn_enabled"] = hgrn_runner.hgrn_enabled
                manifest["hgrn_status"] = report.status
                manifest["hgrn_report_path"] = str(artifacts_path / "hgrn_report.json")

                if report.recommendations:
                    manifest["hgrn_recommendations_count"] = len(report.recommendations)
                    manifest["hgrn_high_priority_count"] = len(report.get_high_priority_recommendations())

                with open(manifest_file, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)

            logger.info(
                f"Pass D HGRN validation completed for job {job_id}. "
                f"Status: {report.status}, "
                f"Recommendations: {len(report.recommendations)}"
            )

            return report.status != "failed"

        except Exception as e:
            logger.error(f"Pass D HGRN validation failed for job {job_id}: {str(e)}")
            return False
    
    async def retry_job(self, environment: str, job_id: str) -> bool:
        """
        Retry a failed ingestion job
        
        Args:
            environment: Environment name
            job_id: Job identifier
            
        Returns:
            True if retry initiated successfully
        """
        try:
            job_info = await self._find_job(environment, job_id)
            if not job_info:
                return False
            
            if job_info.status != 'failed':
                logger.warning(f"Cannot retry job {job_id} with status {job_info.status}")
                return False
            
            # Update job status to pending for retry
            if job_info.artifacts_path:
                manifest_file = Path(job_info.artifacts_path) / "manifest.json"
                if manifest_file.exists():
                    manifest = json.loads(manifest_file.read_text())
                    manifest["status"] = "pending"
                    manifest["retried_at"] = time.time()
                    
                    with open(manifest_file, 'w', encoding='utf-8') as f:
                        json.dump(manifest, f, indent=2)
            
            logger.info(f"Initiated retry for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error retrying job {environment}/{job_id}: {e}")
            return False
    
    async def delete_job(self, environment: str, job_id: str) -> bool:
        """
        Delete an ingestion job and its artifacts
        
        Args:
            environment: Environment name
            job_id: Job identifier
            
        Returns:
            True if deletion successful
        """
        try:
            job_info = await self._find_job(environment, job_id)
            if not job_info:
                return False
            
            # Cannot delete running jobs
            if job_info.status == 'running':
                logger.warning(f"Cannot delete running job {job_id}")
                return False
            
            # Delete job artifacts
            if job_info.artifacts_path:
                job_path = Path(job_info.artifacts_path)
                if job_path.exists():
                    import shutil
                    shutil.rmtree(job_path)
            
            logger.info(f"Deleted job {job_id} from {environment}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting job {environment}/{job_id}: {e}")
            return False
    
    async def stream_job_progress(self, environment: str, job_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream real-time progress updates for a job
        
        Args:
            environment: Environment name
            job_id: Job identifier
            
        Yields:
            Progress update dictionaries
        """
        try:
            last_update = 0
            
            while True:
                job_info = await self._find_job(environment, job_id)
                if not job_info:
                    break
                
                # Check if job completed
                if job_info.status in ['completed', 'failed']:
                    yield {
                        "type": "final_status",
                        "job_id": job_id,
                        "status": job_info.status,
                        "timestamp": time.time()
                    }
                    break
                
                # Get recent logs
                recent_logs = await self.get_job_logs(environment, job_id, limit=5)
                new_logs = [log for log in recent_logs if log.get('timestamp', 0) > last_update]
                
                if new_logs:
                    last_update = max(log.get('timestamp', 0) for log in new_logs)
                    
                    yield {
                        "type": "logs",
                        "job_id": job_id,
                        "logs": new_logs,
                        "timestamp": time.time()
                    }
                
                # Wait before next check
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Error streaming job progress: {e}")
            yield {
                "type": "error",
                "job_id": job_id,
                "error": str(e),
                "timestamp": time.time()
            }
    
    async def _load_job_info(self, environment: str, job_id: str, base_path: Optional[Path] = None) -> Optional[IngestionJob]:
        """Load job information from manifest file"""
        try:
            if base_path is None:
                job_path = Path(f"artifacts/{environment}/{job_id}")
            else:
                job_path = base_path / job_id
            
            manifest_file = job_path / "manifest.json"
            if not manifest_file.exists():
                return None
            
            manifest = json.loads(manifest_file.read_text())
            
            return IngestionJob(
                job_id=manifest.get("job_id", job_id),
                environment=environment,
                status=manifest.get("status", "unknown"),
                created_at=manifest.get("created_at", 0),
                started_at=manifest.get("started_at"),
                completed_at=manifest.get("completed_at"),
                source_file=manifest.get("source_file", "unknown"),
                job_type=manifest.get("job_type", manifest.get("name", "unknown")),
                lane=manifest.get("lane", "A"),
                total_phases=len(manifest.get("phases", [])),
                completed_phases=manifest.get("completed_phases", 0),
                current_phase=manifest.get("current_phase"),
                error_message=manifest.get("error_message"),
                artifacts_path=str(job_path),
                process_id=manifest.get("process_id")
            )
            
        except Exception as e:
            logger.warning(f"Could not load job info for {job_id}: {e}")
            return None
    
    async def _find_job(self, environment: str, job_id: str) -> Optional[IngestionJob]:
        """Find job across different possible locations"""
        # Try different paths where jobs might be stored
        paths = [
            Path(f"artifacts/{environment}"),
            Path(f"artifacts/ingest/{environment}")
        ]
        
        for base_path in paths:
            if base_path.exists():
                for job_dir in base_path.iterdir():
                    if job_dir.is_dir() and (job_dir.name == job_id or job_id in job_dir.name):
                        job_info = await self._load_job_info(environment, job_dir.name, base_path.parent if 'ingest' in str(base_path) else None)
                        if job_info:
                            return job_info
        
        return None
    
    async def _get_job_artifacts(self, artifacts_path: str) -> List[Dict[str, Any]]:
        """Get list of artifacts for a job"""
        try:
            job_path = Path(artifacts_path)
            artifacts = []
            
            for item in job_path.rglob('*.json'):
                if item.is_file():
                    stat = item.stat()
                    artifacts.append({
                        "name": item.name,
                        "path": str(item.relative_to(job_path)),
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime
                    })
            
            return sorted(artifacts, key=lambda x: x['modified_at'], reverse=True)
            
        except Exception as e:
            logger.warning(f"Could not get artifacts for {artifacts_path}: {e}")
            return []
    
    async def _parse_log_file(self, log_path: Path, job_id: str) -> List[Dict[str, Any]]:
        """Parse log file and extract relevant entries"""
        logs = []
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Plain text log entry
                        logs.append({
                            "timestamp": time.time(),
                            "level": "INFO", 
                            "message": line.strip(),
                            "job_id": job_id
                        })
        except Exception as e:
            logger.warning(f"Could not parse log file {log_path}: {e}")
        
        return logs
    
    async def _get_main_log_entries(self, environment: str, job_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get relevant entries from main application log"""
        try:
            log_file = Path(f"env/{environment}/logs/app.log")
            
            if not log_file.exists():
                return []
            
            logs = []
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if job_id in line:
                        try:
                            log_entry = json.loads(line.strip())
                            logs.append(log_entry)
                        except json.JSONDecodeError:
                            logs.append({
                                "timestamp": time.time(),
                                "level": "INFO",
                                "message": line.strip(),
                                "job_id": job_id
                            })
            
            return logs[-limit:] if len(logs) > limit else logs
            
        except Exception as e:
            logger.warning(f"Could not get main log entries: {e}")
            return []

    async def get_sources_health(self, environment: str) -> List[Dict[str, Any]]:
        """
        Get health status and chunk counts for all ingested sources

        Args:
            environment: Environment name (dev/test/prod)

        Returns:
            List of source dictionaries with health indicators
        """
        try:
            sources = []

            # Get sources from local artifacts
            local_sources = await self._get_local_sources(environment)

            # Get sources from the active vector store backend
            vector_sources = await self._get_vector_store_sources(environment)

            # Combine and correlate sources from both locations
            combined_sources = await self._combine_source_data(local_sources, vector_sources, environment)

            # Sort by health (red, yellow, green) then by name
            health_priority = {'red': 0, 'yellow': 1, 'green': 2}
            combined_sources.sort(key=lambda x: (health_priority.get(x['health'], 0), x['id']))

            return combined_sources

        except Exception as e:
            logger.error(f"Error getting sources health for {environment}: {e}")
            return []

    async def _get_local_sources(self, environment: str) -> List[Dict[str, Any]]:
        """Get sources from local artifact directories"""
        sources = []
        artifacts_path = Path(f"artifacts/{environment}")

        if not artifacts_path.exists():
            return sources

        # Check ingest directory for completed jobs
        ingest_path = artifacts_path / "ingest" / environment
        if ingest_path.exists():
            for job_dir in ingest_path.iterdir():
                if job_dir.is_dir():
                    source_info = await self._analyze_source_health(job_dir)
                    if source_info:
                        sources.append(source_info)

        # Also check direct artifacts directory
        for item in artifacts_path.iterdir():
            if item.is_dir() and item.name != "ingest":
                source_info = await self._analyze_source_health(item)
                if source_info:
                    sources.append(source_info)

        return sources

    async def _get_vector_store_sources(self, environment: str) -> List[Dict[str, Any]]:
        """Get sources from the active vector store backend."""
        try:
            from ..astra_loader import AstraLoader

            loader = AstraLoader(env=environment)
            backend = getattr(loader, "backend", "vector_store")
            sources_data = loader.get_sources_with_chunk_counts()

            if sources_data.get('status') == 'simulation_mode':
                logger.info(f"Vector store backend={backend} in simulation mode for {environment}")
                store_sources: List[Dict[str, Any]] = []
                for source in sources_data.get('sources', []):
                    store_sources.append({
                        'id': source['source_hash'][:12],
                        'source_file': source['source_file'],
                        'chunk_count': source.get('chunk_count', 0),
                        'health': 'green',
                        'status': 'ingested',
                        'source_type': backend,
                        'source_hash': source['source_hash'],
                        'last_modified': source.get('last_updated')
                    })
                return store_sources

            if sources_data.get('status') == 'error':
                logger.warning(
                    f"Error accessing vector store backend={backend} for {environment}: "
                    f"{sources_data.get('error', 'Unknown error')}"
                )
                return []

            store_sources: List[Dict[str, Any]] = []
            for source in sources_data.get('sources', []):
                chunk_count = source.get('chunk_count', 0)
                health = 'green' if chunk_count >= 5 else 'yellow' if chunk_count > 0 else 'red'
                store_sources.append({
                    'id': source['source_hash'][:12],
                    'source_file': source.get('source_file'),
                    'chunk_count': chunk_count,
                    'health': health,
                    'status': 'ingested',
                    'source_type': backend,
                    'source_hash': source.get('source_hash'),
                    'last_modified': source.get('last_updated')
                })

            logger.info(
                f"Retrieved {len(store_sources)} sources from vector store backend={backend} for {environment}"
            )
            return store_sources

        except Exception as e:
            logger.warning(f"Could not query vector store for {environment}: {e}")
            return []

    async def _get_uploaded_sources(self, environment: str) -> List[Dict[str, Any]]:
        """Get sources from the uploads directory (new files waiting to be ingested)."""
        sources = []
        try:
            # Use the same upload directory logic as admin_routes.py
            import os
            uploads_dir_path = os.getenv("UPLOADS_DIR", "/data/uploads")
            uploads_dir = Path(uploads_dir_path)

            # Ensure directory exists (should already exist from container setup)
            os.makedirs(uploads_dir, exist_ok=True)

            if not uploads_dir.exists():
                logger.warning(f"Uploads directory does not exist: {uploads_dir}")
                return sources

            # Scan for PDF files in uploads directory
            for file_path in uploads_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() == '.pdf':
                    try:
                        stat = file_path.stat()
                        file_size = stat.st_size

                        # Create source info for uploaded file
                        source_info = {
                            'id': file_path.stem,  # filename without extension
                            'source_file': file_path.name,
                            'file_path': str(file_path),
                            'file_size': file_size,
                            'file_size_mb': round(file_size / (1024 * 1024), 2),
                            'last_modified': stat.st_mtime,
                            'health': 'blue',  # Use blue to indicate "new upload"
                            'status': 'uploaded',
                            'source_type': 'upload',
                            'description': f"New upload: {file_path.name} ({round(file_size / (1024 * 1024), 2)} MB)"
                        }

                        sources.append(source_info)
                        logger.debug(f"Found uploaded file: {file_path.name} ({round(file_size / (1024 * 1024), 2)} MB)")

                    except Exception as e:
                        logger.warning(f"Could not analyze uploaded file {file_path}: {e}")
                        continue

            logger.info(f"Found {len(sources)} uploaded files in {uploads_dir}")
            return sources

        except Exception as e:
            logger.error(f"Error scanning uploads directory {uploads_dir}: {e}")
            return []

    async def _combine_source_data(self, local_sources: List[Dict[str, Any]],
                                   vector_sources: List[Dict[str, Any]],
                                   environment: str) -> List[Dict[str, Any]]:
        """Combine local and vector store source data for comprehensive health view"""
        combined: List[Dict[str, Any]] = []
        vector_backend = vector_sources[0].get('source_type', 'vector_store') if vector_sources else 'vector_store'

        # Add all local sources
        for source in local_sources:
            combined.append(source)

        # Add vector store sources (these represent the actual ingested data)
        for source in vector_sources:
            combined.append(source)

        # If we have vector store data but no local sources, it means sources are ingested
        # but local artifacts may have been cleaned up
        if vector_sources and not local_sources:
            logger.info(f"Found {len(vector_sources)} vector store sources but no local artifacts for {environment}")

        # If we have local sources but no vector store data, ingestion may have failed
        if local_sources and not vector_sources:
            logger.warning(f"Found {len(local_sources)} local sources but no vector store data for {environment}")
            # Mark local sources as potentially problematic
            for source in combined:
                if source.get('source_type') != vector_backend and source.get('health') == 'green':
                    source['health'] = 'yellow'  # Downgrade since missing from vector store

        return combined
    async def remove_source(self, environment: str, source_id: str) -> bool:
        """
        Remove an ingested source and all its artifacts

        Args:
            environment: Environment name
            source_id: Source identifier

        Returns:
            True if removal successful
        """
        try:
            removed = False

            # Search in different possible locations
            search_paths = [
                Path(f"artifacts/{environment}"),
                Path(f"artifacts/{environment}/ingest/{environment}"),
                Path(f"artifacts/ingest/{environment}")
            ]

            for base_path in search_paths:
                if not base_path.exists():
                    continue

                for item in base_path.iterdir():
                    if item.is_dir():
                        # Check if this directory matches the source
                        manifest_file = item / "manifest.json"
                        if manifest_file.exists():
                            try:
                                manifest = json.loads(manifest_file.read_text())
                                source_file = manifest.get("source_file", "")
                                job_id = manifest.get("job_id", "")

                                # Match by source file name or job ID
                                if (source_id in source_file or
                                    source_id == job_id or
                                    source_id in item.name):

                                    import shutil
                                    shutil.rmtree(item)
                                    removed = True
                                    logger.info(f"Removed source artifacts: {item}")
                                    break
                            except Exception as e:
                                logger.warning(f"Could not parse manifest in {item}: {e}")
                                continue

                if removed:
                    break

            if not removed:
                logger.warning(f"Source {source_id} not found for removal")

            return removed

        except Exception as e:
            logger.error(f"Error removing source {source_id} from {environment}: {e}")
            return False

    async def _analyze_source_health(self, job_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Analyze source health based on artifacts and manifest

        Args:
            job_dir: Path to job directory

        Returns:
            Source health information dictionary or None
        """
        try:
            manifest_file = job_dir / "manifest.json"
            if not manifest_file.exists():
                return None

            manifest = json.loads(manifest_file.read_text())
            source_file = manifest.get("source_file", job_dir.name)
            status = manifest.get("status", "unknown")

            # Skip placeholder jobs that aren't actual document sources
            if source_file in ["nightly_run", "placeholder", "test_job"]:
                logger.debug(f"Skipping placeholder job {source_file} from source health")
                return None

            # Only consider jobs that have processed actual PDF files
            if not source_file.endswith('.pdf') and source_file != "unknown":
                logger.debug(f"Skipping non-PDF source {source_file} from source health")
                return None

            # Count chunks from Pass A output
            chunk_count = 0
            pass_a_file = job_dir / "passA_chunks.json"
            if pass_a_file.exists():
                try:
                    chunks_data = json.loads(pass_a_file.read_text())
                    if isinstance(chunks_data, list):
                        chunk_count = len(chunks_data)
                    elif isinstance(chunks_data, dict) and "chunks" in chunks_data:
                        chunk_count = len(chunks_data["chunks"])
                except Exception:
                    pass

            # Only include sources that have actually produced chunks
            if chunk_count == 0:
                logger.debug(f"Skipping source {source_file} with no chunks from source health")
                return None

            # Calculate health based on status and chunk processing
            health = self._calculate_source_health(status, chunk_count, job_dir)

            # Extract source name from file path
            source_name = Path(source_file).stem if source_file else job_dir.name

            return {
                "id": source_name,
                "source_file": source_file,
                "chunk_count": chunk_count,
                "health": health,
                "status": status,
                "job_path": str(job_dir),
                "last_modified": job_dir.stat().st_mtime if job_dir.exists() else 0
            }

        except Exception as e:
            logger.warning(f"Could not analyze source health for {job_dir}: {e}")
            return None

    def _calculate_source_health(self, status: str, chunk_count: int, job_dir: Path) -> str:
        """
        Calculate health indicator based on job status and artifacts

        Returns:
            'green', 'yellow', or 'red'
        """
        try:
            # Red: Failed job or no chunks
            if status == "failed" or chunk_count == 0:
                return "red"

            # Check for error indicators in artifacts
            error_indicators = 0

            # Check if Pass B and C completed successfully
            pass_b_file = job_dir / "passB_enriched.json"
            pass_c_file = job_dir / "passC_graph.json"

            if not pass_b_file.exists():
                error_indicators += 1
            if not pass_c_file.exists():
                error_indicators += 1

            # Check for error messages in manifest
            if job_dir / "manifest.json":
                try:
                    manifest = json.loads((job_dir / "manifest.json").read_text())
                    if manifest.get("error_message"):
                        error_indicators += 1
                except Exception:
                    pass

            # Green: Completed successfully with good chunk count
            if status == "completed" and chunk_count >= 5 and error_indicators == 0:
                return "green"

            # Yellow: Some issues but functional
            if chunk_count >= 1 and error_indicators <= 1:
                return "yellow"

            # Red: Significant issues
            return "red"

        except Exception:
            return "red"

    async def kill_job(self, environment: str, job_id: str) -> bool:
        """
        Kill/cancel a running or pending ingestion job

        Args:
            environment: Environment name
            job_id: Job identifier to kill

        Returns:
            True if job was killed, False if not found or already completed
        """
        try:
            import signal
            import psutil

            logger.info(f"Attempting to kill job {job_id} in {environment}")

            # First try to find the job artifacts directory
            artifacts_path = Path(f"artifacts/{environment}/ingest/{environment}")
            job_dir = artifacts_path / job_id

            if not job_dir.exists():
                # Try alternative path
                artifacts_path = Path(f"artifacts/ingest/{environment}")
                job_dir = artifacts_path / job_id

            if not job_dir.exists():
                logger.warning(f"Job directory not found for {job_id}")
                return False

            # Check manifest for job status and process info
            manifest_file = job_dir / "manifest.json"
            if manifest_file.exists():
                try:
                    manifest = json.loads(manifest_file.read_text())
                    current_status = manifest.get("status", "unknown")
                    process_id = manifest.get("process_id")

                    # If already completed/failed, can't kill
                    if current_status in ["completed", "failed", "killed"]:
                        logger.info(f"Job {job_id} is already {current_status}, cannot kill")
                        return False

                    # Try to kill the process if we have a PID
                    killed_process = False
                    if process_id:
                        try:
                            process = psutil.Process(process_id)
                            process.terminate()
                            killed_process = True
                            logger.info(f"Terminated process {process_id} for job {job_id}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                            logger.warning(f"Could not kill process {process_id}: {e}")

                    # Update manifest to reflect killed status
                    manifest["status"] = "killed"
                    manifest["killed_at"] = datetime.now().isoformat()
                    manifest["error_message"] = "Job manually killed by administrator"

                    with open(manifest_file, 'w') as f:
                        json.dump(manifest, f, indent=2)

                    logger.info(f"Job {job_id} marked as killed in manifest")
                    return True

                except Exception as e:
                    logger.error(f"Error updating manifest for killed job {job_id}: {e}")
                    return False
            else:
                logger.warning(f"No manifest found for job {job_id}")
                return False

        except Exception as e:
            logger.error(f"Error killing job {job_id} in {environment}: {e}")
            return False

    async def get_recent_jobs(self, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Get the most recent ingestion jobs across all environments with standardized status

        Args:
            limit: Maximum number of jobs to return (default 3 for FR-013)

        Returns:
            List of recent job dictionaries with standardized status
        """
        try:
            all_jobs = []

            # Collect jobs from all environments
            for environment in self.environments:
                env_jobs = await self.list_jobs(environment, limit=20)  # Get more to sort globally
                for job in env_jobs:
                    # Add standardized status
                    job['standardized_status'] = self._standardize_job_status(job['status'])
                    all_jobs.append(job)

            # Sort by creation time (newest first) and take top N
            all_jobs.sort(key=lambda x: x['created_at'], reverse=True)
            recent_jobs = all_jobs[:limit]

            # Enrich with log-derived status information when available
            for job in recent_jobs:
                await self._hydrate_job_status_from_logs(job)

            logger.info(f"Retrieved {len(recent_jobs)} recent jobs from all environments")
            return recent_jobs

        except Exception as e:
            logger.error(f"Error getting recent jobs: {e}")
            return []

    async def _hydrate_job_status_from_logs(self, job: Dict[str, Any]) -> None:
        """Update job metadata using the log management service for consistency."""
        try:
            job_id = job.get('job_id')
            env = job.get('environment', 'dev')
            if not job_id:
                return
            log_status = await self.log_service.get_job_status(job_id, env)
        except Exception as exc:
            logger.debug(f"Log status lookup failed for {job.get('job_id')}: {exc}")
            return

        status = log_status.get('status')
        if status in {'pending', 'running', 'completed', 'failed', 'cancelled', 'killed'}:
            job['status'] = status
            job['standardized_status'] = self._standardize_job_status(status)

        start_time = log_status.get('start_time')
        if start_time and not job.get('started_at'):
            job['started_at'] = start_time

        end_time = log_status.get('end_time')
        if end_time:
            job['completed_at'] = end_time

        if log_status.get('pid') is not None:
            job['process_id'] = log_status['pid']

    def _standardize_job_status(self, raw_status: str) -> Dict[str, Any]:
        """
        Standardize job status according to FR-013 semantics

        Args:
            raw_status: Raw status from job manifest

        Returns:
            Dictionary with standardized status information
        """
        status_mapping = {
            'pending': {
                'display': 'Pending',
                'description': 'Scheduled',
                'category': 'pending',
                'color': 'warning',
                'icon': 'clock'
            },
            'running': {
                'display': 'Running',
                'description': 'Active',
                'category': 'running',
                'color': 'primary',
                'icon': 'play-circle'
            },
            'completed': {
                'display': 'Completed',
                'description': 'Finished (Success)',
                'category': 'completed',
                'color': 'success',
                'icon': 'check-circle'
            },
            'failed': {
                'display': 'Failed',
                'description': 'Finished (Failed)',
                'category': 'completed',
                'color': 'danger',
                'icon': 'x-circle'
            },
            'killed': {
                'display': 'Cancelled',
                'description': 'Finished (Cancelled)',
                'category': 'completed',
                'color': 'secondary',
                'icon': 'stop-circle'
            },
            'cancelled': {
                'display': 'Cancelled',
                'description': 'Finished (Cancelled)',
                'category': 'completed',
                'color': 'secondary',
                'icon': 'stop-circle'
            }
        }

        return status_mapping.get(raw_status, {
            'display': 'Unknown',
            'description': raw_status,
            'category': 'unknown',
            'color': 'secondary',
            'icon': 'question-circle'
        })










