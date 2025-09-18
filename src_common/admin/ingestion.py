# src_common/admin/ingestion.py
"""
Ingestion Console Service - ADM-002
Environment-scoped ingestion job monitoring and management
"""

import json
import time
import asyncio
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime

from ..ttrpg_logging import get_logger


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
    current_phase: Optional[str]
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


class AdminIngestionService:
    """
    Ingestion Console Service
    
    Provides monitoring and management capabilities for ingestion jobs
    across all environments with proper isolation.
    """
    
    def __init__(self):
        self.environments = ['dev', 'test', 'prod']
        self._active_jobs = {}  # Track running async tasks
        self._pass_sequence = ["parse", "enrich", "compile"]  # Lane A pipeline phases
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
        Start a new ingestion job (stub implementation)

        Args:
            environment: Target environment
            source_file: Path to source PDF file
            options: Additional job options
            job_type: Type of job ("ad_hoc" or "nightly")

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
                "phases": ["parse", "enrich", "compile", "hgrn_validate"],
                "hgrn_enabled": options_dict.get("hgrn_enabled", True)
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

            for idx, phase in enumerate(self._pass_sequence, start=1):
                manifest["current_phase"] = phase
                manifest["completed_phases"] = idx - 1
                await self._write_manifest(manifest_file, manifest)
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] phase={phase} status=started")

                # Simulate actual pipeline work and create artifacts
                await self._execute_phase(phase, job_path, manifest, job_id)

                # Small delay to simulate processing time
                await asyncio.sleep(0.5)

                manifest["completed_phases"] = idx
                await self._write_manifest(manifest_file, manifest)
                await self._append_log(log_file_path, f"[{datetime.now().isoformat()}] phase={phase} status=completed")

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

    async def _execute_phase(self, phase: str, job_path: Path, manifest: Dict[str, Any], job_id: str) -> None:
        """Execute a specific phase of the ingestion pipeline and create artifacts"""
        try:
            if phase == "parse":
                # Pass A: Create sample chunks from PDF parsing
                chunks_data = {
                    "source_file": manifest.get("source_file", "unknown.pdf"),
                    "job_id": job_id,
                    "processed_at": datetime.now().isoformat(),
                    "chunks": [
                        {
                            "chunk_id": f"chunk_{i}",
                            "content": f"Sample content from PDF chunk {i}",
                            "page": i % 10 + 1,
                            "metadata": {"source": "PDF", "type": "text"}
                        }
                        for i in range(15)  # Create 15 sample chunks
                    ]
                }

                chunks_file = job_path / "passA_chunks.json"
                await self._write_json_file(chunks_file, chunks_data)

            elif phase == "enrich":
                # Pass B: Create enriched content data
                enriched_data = {
                    "source_file": manifest.get("source_file", "unknown.pdf"),
                    "job_id": job_id,
                    "enriched_at": datetime.now().isoformat(),
                    "enrichment_results": {
                        "entities_extracted": 25,
                        "keywords_identified": 12,
                        "semantic_tags_added": 8
                    },
                    "dictionary_updates": [
                        {"term": "sample_term_1", "definition": "Example definition 1"},
                        {"term": "sample_term_2", "definition": "Example definition 2"}
                    ]
                }

                enriched_file = job_path / "passB_enriched.json"
                await self._write_json_file(enriched_file, enriched_data)

            elif phase == "compile":
                # Pass C: Create graph compilation results
                graph_data = {
                    "source_file": manifest.get("source_file", "unknown.pdf"),
                    "job_id": job_id,
                    "compiled_at": datetime.now().isoformat(),
                    "graph_structure": {
                        "nodes": 35,
                        "edges": 42,
                        "clusters": 6
                    },
                    "compilation_status": "completed"
                }

                graph_file = job_path / "passC_graph.json"
                await self._write_json_file(graph_file, graph_data)

            logger.debug(f"Completed phase {phase} for job {job_id}")

        except Exception as e:
            logger.error(f"Error executing phase {phase} for job {job_id}: {e}")
            raise

    async def _write_json_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Write JSON data to file asynchronously"""
        def _write() -> None:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, indent=2)

        await asyncio.to_thread(_write)

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

            # Get sources from AstraDB (the source of truth)
            astradb_sources = await self._get_astradb_sources(environment)

            # Combine and correlate sources from both locations
            combined_sources = await self._combine_source_data(local_sources, astradb_sources, environment)

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

    async def _get_astradb_sources(self, environment: str) -> List[Dict[str, Any]]:
        """Get sources from AstraDB (source of truth)"""
        try:
            # Import AstraLoader to query the database
            from ..astra_loader import AstraLoader

            loader = AstraLoader(env=environment)

            # Get detailed source information with chunk counts
            sources_data = loader.get_sources_with_chunk_counts()

            if sources_data.get('status') == 'simulation_mode':
                logger.info(f"AstraDB in simulation mode for {environment}")
                # Convert simulation data to expected format
                astra_sources = []
                for source in sources_data.get('sources', []):
                    astra_sources.append({
                        'id': source['source_hash'][:12],  # Truncated hash for display
                        'source_file': source['source_file'],
                        'chunk_count': source['chunk_count'],
                        'health': 'green',
                        'status': 'ingested',
                        'source_type': 'astradb',
                        'source_hash': source['source_hash'],
                        'last_modified': source['last_updated']
                    })
                return astra_sources

            if sources_data.get('status') == 'error':
                logger.warning(f"Error accessing AstraDB for {environment}: {sources_data.get('error', 'Unknown error')}")
                return []

            # Convert real AstraDB sources to expected format
            astra_sources = []
            for source in sources_data.get('sources', []):
                # Determine health based on chunk count
                health = 'green' if source['chunk_count'] >= 5 else 'yellow' if source['chunk_count'] > 0 else 'red'

                astra_sources.append({
                    'id': source['source_hash'][:12],  # Truncated hash for display
                    'source_file': source['source_file'],
                    'chunk_count': source['chunk_count'],
                    'health': health,
                    'status': 'ingested',
                    'source_type': 'astradb',
                    'source_hash': source['source_hash'],
                    'last_modified': source['last_updated']
                })

            logger.info(f"Retrieved {len(astra_sources)} sources from AstraDB for {environment}")
            return astra_sources

        except Exception as e:
            logger.warning(f"Could not query AstraDB for {environment}: {e}")
            return []

    async def _combine_source_data(self, local_sources: List[Dict[str, Any]],
                                   astradb_sources: List[Dict[str, Any]],
                                   environment: str) -> List[Dict[str, Any]]:
        """Combine local and AstraDB source data for comprehensive health view"""
        combined = []

        # Add all local sources
        for source in local_sources:
            combined.append(source)

        # Add AstraDB sources (these represent the actual ingested data)
        for source in astradb_sources:
            combined.append(source)

        # If we have AstraDB data but no local sources, it means sources are ingested
        # but local artifacts may have been cleaned up
        if astradb_sources and not local_sources:
            logger.info(f"Found {len(astradb_sources)} sources in AstraDB but no local artifacts for {environment}")

        # If we have local sources but no AstraDB data, it means ingestion may have failed
        if local_sources and not astradb_sources:
            logger.warning(f"Found {len(local_sources)} local sources but no AstraDB data for {environment}")
            # Mark local sources as potentially problematic
            for source in combined:
                if source.get('source_type') != 'astradb' and source.get('health') == 'green':
                    source['health'] = 'yellow'  # Downgrade since not in AstraDB

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

            logger.info(f"Retrieved {len(recent_jobs)} recent jobs from all environments")
            return recent_jobs

        except Exception as e:
            logger.error(f"Error getting recent jobs: {e}")
            return []

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
                'display': 'Completed',
                'description': 'Finished (Failed)',
                'category': 'completed',
                'color': 'danger',
                'icon': 'x-circle'
            },
            'killed': {
                'display': 'Completed',
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
