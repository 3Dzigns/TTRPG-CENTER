# src_common/admin/ingestion.py
"""
Ingestion Console Service - ADM-002
Environment-scoped ingestion job monitoring and management
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime

from ..logging import get_logger


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
    
    async def start_ingestion_job(self, environment: str, source_file: str, options: Dict[str, Any] = None) -> str:
        """
        Start a new ingestion job (stub implementation)
        
        Args:
            environment: Target environment
            source_file: Path to source PDF file
            options: Additional job options
            
        Returns:
            Job ID for the new job
        """
        try:
            job_id = f"job_{int(time.time())}_{environment}"
            
            # Create job directory
            job_path = Path(f"artifacts/{environment}/{job_id}")
            job_path.mkdir(parents=True, exist_ok=True)
            
            # Create job manifest
            job_manifest = {
                "job_id": job_id,
                "environment": environment,
                "source_file": source_file,
                "status": "pending",
                "created_at": time.time(),
                "options": options or {},
                "phases": ["parse", "enrich", "compile"]
            }
            
            manifest_file = job_path / "manifest.json"
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(job_manifest, f, indent=2)
            
            logger.info(f"Created ingestion job {job_id} for {environment}")
            
            # In a real implementation, this would trigger the actual ingestion pipeline
            # For now, we just create the job structure
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error starting ingestion job: {e}")
            raise
    
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
                total_phases=len(manifest.get("phases", [])),
                completed_phases=manifest.get("completed_phases", 0),
                current_phase=manifest.get("current_phase"),
                error_message=manifest.get("error_message"),
                artifacts_path=str(job_path)
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