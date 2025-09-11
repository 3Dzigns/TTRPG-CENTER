"""
P2.1: Job Status Storage and Retrieval System

Provides persistent storage for job progress and status information
with support for real-time updates and historical queries.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from threading import Lock
import asyncio

from .ttrpg_logging import get_logger
from .progress_callback import JobProgress, PassProgress, PassStatus


@dataclass
class JobStatusRecord:
    """Complete job status record for API responses"""
    job_id: str
    source_path: str
    environment: str
    status: str  # queued, running, completed, failed
    
    # Timing information
    queued_time: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    # Progress tracking
    current_pass: Optional[str] = None
    progress_percentage: float = 0.0
    estimated_completion_time: Optional[float] = None
    
    # Pass details
    passes: Dict[str, Dict[str, Any]] = None
    
    # Result information
    processing_time: Optional[float] = None
    wait_time: Optional[float] = None
    error_message: Optional[str] = None
    artifacts_path: Optional[str] = None
    
    # Metadata
    thread_name: Optional[str] = None
    created_at: str = None
    
    def __post_init__(self):
        if self.passes is None:
            self.passes = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
    
    @classmethod
    def from_job_progress(cls, job_progress: JobProgress) -> 'JobStatusRecord':
        """Create status record from JobProgress"""
        # Convert pass progress to serializable format
        passes = {}
        for pass_type, pass_progress in job_progress.passes.items():
            passes[pass_type.value] = {
                "status": pass_progress.status.value,
                "start_time": pass_progress.start_time,
                "end_time": pass_progress.end_time,
                "duration_ms": pass_progress.duration_ms,
                "toc_entries": pass_progress.toc_entries,
                "chunks_processed": pass_progress.chunks_processed,
                "vectors_created": pass_progress.vectors_created,
                "graph_nodes": pass_progress.graph_nodes,
                "graph_edges": pass_progress.graph_edges,
                "error_message": pass_progress.error_message,
                "error_type": pass_progress.error_type,
                "metadata": pass_progress.metadata
            }
        
        return cls(
            job_id=job_progress.job_id,
            source_path=job_progress.source_path,
            environment=job_progress.environment,
            status=job_progress.overall_status,
            queued_time=job_progress.start_time,
            start_time=job_progress.start_time,
            current_pass=job_progress.current_pass.value if job_progress.current_pass else None,
            progress_percentage=job_progress.get_progress_percentage(),
            estimated_completion_time=job_progress.get_estimated_completion_time(),
            passes=passes
        )


class JobStatusStore:
    """Thread-safe in-memory job status storage with disk persistence"""
    
    def __init__(self, storage_dir: Path = None):
        self.logger = get_logger(__name__)
        # Anchor storage under repo root to avoid CWD issues (e.g., Task Scheduler)
        if storage_dir is None:
            project_root = Path(__file__).resolve().parents[1]
            env_name = os.getenv("APP_ENV", "dev")
            self.storage_dir = project_root / "env" / env_name / "data" / "job_status"
        else:
            self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for fast access
        self._active_jobs: Dict[str, JobStatusRecord] = {}
        self._completed_jobs: Dict[str, JobStatusRecord] = {}
        self._lock = Lock()
        
        # Load existing data
        self._load_from_disk()
        
    def _load_from_disk(self):
        """Load job status from disk storage"""
        try:
            active_file = self.storage_dir / "active_jobs.json"
            completed_file = self.storage_dir / "completed_jobs.json"
            
            if active_file.exists():
                with open(active_file, 'r') as f:
                    data = json.load(f)
                    for job_id, job_data in data.items():
                        self._active_jobs[job_id] = JobStatusRecord(**job_data)
                        
            if completed_file.exists():
                with open(completed_file, 'r') as f:
                    data = json.load(f)
                    for job_id, job_data in data.items():
                        self._completed_jobs[job_id] = JobStatusRecord(**job_data)
                        
            self.logger.info(f"Loaded {len(self._active_jobs)} active and {len(self._completed_jobs)} completed jobs")
            
        except Exception as e:
            self.logger.error(f"Failed to load job status from disk: {e}")
    
    def _save_to_disk(self):
        """Persist job status to disk"""
        try:
            active_file = self.storage_dir / "active_jobs.json"
            completed_file = self.storage_dir / "completed_jobs.json"
            
            with open(active_file, 'w') as f:
                active_data = {job_id: asdict(record) for job_id, record in self._active_jobs.items()}
                json.dump(active_data, f, indent=2)
                
            with open(completed_file, 'w') as f:
                completed_data = {job_id: asdict(record) for job_id, record in self._completed_jobs.items()}
                json.dump(completed_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save job status to disk: {e}")
    
    def create_job(self, job_id: str, source_path: str, environment: str) -> JobStatusRecord:
        """Create a new job status record"""
        with self._lock:
            record = JobStatusRecord(
                job_id=job_id,
                source_path=source_path,
                environment=environment,
                status="queued",
                queued_time=time.time()
            )
            
            self._active_jobs[job_id] = record
            self._save_to_disk()
            
            self.logger.info(f"Created job status record for {job_id}")
            return record
    
    def update_job_from_progress(self, job_progress: JobProgress):
        """Update job status from JobProgress object"""
        with self._lock:
            if job_progress.job_id not in self._active_jobs:
                # Create record if it doesn't exist
                self._active_jobs[job_progress.job_id] = JobStatusRecord.from_job_progress(job_progress)
            else:
                # Update existing record
                record = self._active_jobs[job_progress.job_id]
                updated = JobStatusRecord.from_job_progress(job_progress)
                
                # Preserve original queued time
                updated.queued_time = record.queued_time
                self._active_jobs[job_progress.job_id] = updated
            
            self._save_to_disk()
    
    def complete_job(self, job_id: str, result: Dict[str, Any]):
        """Mark job as completed and move to completed jobs"""
        with self._lock:
            if job_id not in self._active_jobs:
                self.logger.warning(f"Attempting to complete unknown job: {job_id}")
                return
                
            record = self._active_jobs[job_id]
            
            # Update with completion details
            record.status = result.get("status", "completed")
            record.end_time = time.time()
            record.processing_time = result.get("processing_time")
            record.wait_time = result.get("wait_time")
            record.error_message = result.get("error_message")
            record.artifacts_path = result.get("artifacts_path")
            record.thread_name = result.get("thread_name")
            
            # Move to completed jobs
            self._completed_jobs[job_id] = record
            del self._active_jobs[job_id]
            
            # Clean up old completed jobs (keep last 100)
            if len(self._completed_jobs) > 100:
                sorted_jobs = sorted(self._completed_jobs.items(), 
                                   key=lambda x: x[1].end_time or 0)
                to_remove = sorted_jobs[:-100]
                for job_id_to_remove, _ in to_remove:
                    del self._completed_jobs[job_id_to_remove]
            
            self._save_to_disk()
            self.logger.info(f"Completed job {job_id} with status: {record.status}")
    
    def get_job_status(self, job_id: str) -> Optional[JobStatusRecord]:
        """Get status for a specific job"""
        with self._lock:
            if job_id in self._active_jobs:
                return self._active_jobs[job_id]
            if job_id in self._completed_jobs:
                return self._completed_jobs[job_id]
            return None
    
    def get_active_jobs(self) -> List[JobStatusRecord]:
        """Get all active jobs"""
        with self._lock:
            return list(self._active_jobs.values())
    
    def get_job_history(self, limit: int = 50, environment: str = None) -> List[JobStatusRecord]:
        """Get recent job history"""
        with self._lock:
            completed = list(self._completed_jobs.values())
            
            # Filter by environment if specified
            if environment:
                completed = [job for job in completed if job.environment == environment]
            
            # Sort by completion time and limit
            completed.sort(key=lambda x: x.end_time or 0, reverse=True)
            return completed[:limit]
    
    def get_job_statistics(self, environment: str = None) -> Dict[str, Any]:
        """Get job execution statistics"""
        with self._lock:
            active_jobs = list(self._active_jobs.values())
            completed_jobs = list(self._completed_jobs.values())
            
            if environment:
                active_jobs = [j for j in active_jobs if j.environment == environment]
                completed_jobs = [j for j in completed_jobs if j.environment == environment]
            
            # Calculate statistics
            total_completed = len(completed_jobs)
            successful = len([j for j in completed_jobs if j.status == "completed"])
            failed = total_completed - successful
            
            # Average processing time for successful jobs
            processing_times = [j.processing_time for j in completed_jobs 
                              if j.processing_time and j.status == "completed"]
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            return {
                "active_jobs": len(active_jobs),
                "total_completed": total_completed,
                "successful": successful,
                "failed": failed,
                "success_rate": (successful / total_completed * 100) if total_completed > 0 else 0,
                "average_processing_time": avg_processing_time,
                "environment": environment
            }


# Global job status store instance
_job_store = None
_store_lock = asyncio.Lock()

async def get_job_store() -> JobStatusStore:
    """Get the global job status store instance"""
    global _job_store
    async with _store_lock:
        if _job_store is None:
            _job_store = JobStatusStore()
        return _job_store
