"""
Pydantic models for pipeline-worker microservice.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class PassType(str, Enum):
    """Pipeline pass types."""
    PASS_0 = "pass_0"
    PASS_A = "pass_a"
    PASS_B = "pass_b"
    PASS_C = "pass_c"
    PASS_D = "pass_d"
    PASS_E = "pass_e"
    PASS_F = "pass_f"
    PASS_G = "pass_g"


class JobStatus(str, Enum):
    """Job status states."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerMode(str, Enum):
    """Pipeline trigger modes."""
    NIGHTLY = "nightly"
    AD_HOC = "ad_hoc"
    SELECTIVE = "selective"
    INDEPENDENT = "independent"


class JobPriority(int, Enum):
    """Job priority levels."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


class PassExecutionRequest(BaseModel):
    """Request to execute a single pass."""
    pass_type: PassType
    source_file: str
    env: str = "dev"
    job_id: Optional[str] = None
    priority: JobPriority = JobPriority.NORMAL
    context: Optional[Dict[str, Any]] = None


class PipelineExecutionRequest(BaseModel):
    """Request to execute full pipeline."""
    trigger_mode: TriggerMode
    source_files: List[str]
    env: str = "dev"
    job_id: Optional[str] = None
    priority: JobPriority = JobPriority.NORMAL
    start_pass: PassType = PassType.PASS_0
    end_pass: PassType = PassType.PASS_G
    context: Optional[Dict[str, Any]] = None


class JobRequest(BaseModel):
    """Generic job request."""
    job_id: str
    trigger_mode: TriggerMode
    source_files: List[str]
    env: str = "dev"
    priority: JobPriority = JobPriority.NORMAL
    current_pass: Optional[PassType] = None
    context: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PassResult(BaseModel):
    """Result of a single pass execution."""
    pass_type: PassType
    status: JobStatus
    source_file: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    output: Optional[Dict[str, Any]] = None


class JobResult(BaseModel):
    """Complete job execution result."""
    job_id: str
    status: JobStatus
    trigger_mode: TriggerMode
    source_files: List[str]
    env: str
    passes_completed: List[PassType] = []
    pass_results: List[PassResult] = []
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


class WorkerStatus(BaseModel):
    """Status of a single worker."""
    worker_id: str
    pass_type: PassType
    status: str  # "idle", "busy"
    current_job_id: Optional[str] = None
    current_source: Optional[str] = None
    jobs_completed: int = 0
    jobs_failed: int = 0


class WorkerPoolStatus(BaseModel):
    """Status of a worker pool."""
    pass_type: PassType
    pool_size: int
    active_workers: int
    idle_workers: int
    workers: List[WorkerStatus]
    queue_size: int
    total_jobs_completed: int = 0
    total_jobs_failed: int = 0


class PipelineStatus(BaseModel):
    """Overall pipeline status."""
    service_healthy: bool
    worker_pools: List[WorkerPoolStatus]
    active_jobs: int
    queued_jobs: int
    total_jobs_completed: int
    total_jobs_failed: int
    uptime_seconds: float


class HealthResponse(BaseModel):
    """Service health check response."""
    service: str = "pipeline-worker"
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    worker_pools_healthy: bool
    details: Optional[Dict[str, Any]] = None