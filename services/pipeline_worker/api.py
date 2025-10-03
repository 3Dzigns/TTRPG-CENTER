"""
FastAPI application for pipeline-worker microservice.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    PassType, PassExecutionRequest, PipelineExecutionRequest,
    JobResult, HealthResponse, PipelineStatus, JobPriority,
    TriggerMode
)
from .config import config
from .worker_pools import WorkerPoolManager
from .job_queue import PriorityJobQueue, JobTracker
from .pipeline_orchestrator import PipelineOrchestrator
from .pass_executor import PassExecutor
from .logging import get_logger
from src_common.ttrpg_logging import setup_logging as setup_ttrpg_logging

# Setup TTRPG logging for src_common modules
setup_ttrpg_logging()

logger = get_logger(__name__)

# Global instances
pool_manager: Optional[WorkerPoolManager] = None
job_queue: Optional[PriorityJobQueue] = None
job_tracker: Optional[JobTracker] = None
orchestrator: Optional[PipelineOrchestrator] = None
service_start_time: datetime = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global pool_manager, job_queue, job_tracker, orchestrator, service_start_time

    logger.info("Starting pipeline-worker service")
    service_start_time = datetime.utcnow()

    # Initialize components
    job_queue = PriorityJobQueue(max_size=config.max_queue_size)
    job_tracker = JobTracker()
    pool_manager = WorkerPoolManager()

    # Initialize worker pools with executors
    executor = PassExecutor(config.target_env)
    await pool_manager.initialize(executor.get_executor_map())

    # Create orchestrator
    orchestrator = PipelineOrchestrator(pool_manager, job_queue, job_tracker)

    logger.info(f"Pipeline-worker service started on port {config.port}")

    yield

    # Shutdown
    logger.info("Shutting down pipeline-worker service")
    if pool_manager:
        await pool_manager.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Pipeline Worker Service",
    description="Microservice for managing ingestion pipeline with worker pools",
    version=config.service_version,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Service health check."""
    healthy = pool_manager and pool_manager.is_ready()

    return HealthResponse(
        service="pipeline-worker",
        status="healthy" if healthy else "unhealthy",
        version=config.service_version,
        worker_pools_healthy=healthy,
        details={
            "target_env": config.target_env,
            "port": config.port,
            "uptime_seconds": (datetime.utcnow() - service_start_time).total_seconds()
        }
    )


# Pipeline status endpoint
@app.get("/pipeline/status", response_model=PipelineStatus)
async def get_pipeline_status():
    """Get overall pipeline status."""
    if not pool_manager or not job_queue or not job_tracker:
        raise HTTPException(status_code=503, detail="Service not initialized")

    worker_pools = pool_manager.get_all_pool_status()
    job_counts = await job_tracker.get_job_count()
    queue_size = await job_queue.size()

    total_completed = sum(pool.total_jobs_completed for pool in worker_pools)
    total_failed = sum(pool.total_jobs_failed for pool in worker_pools)

    return PipelineStatus(
        service_healthy=pool_manager.is_ready(),
        worker_pools=worker_pools,
        active_jobs=job_counts["active"],
        queued_jobs=queue_size,
        total_jobs_completed=total_completed,
        total_jobs_failed=total_failed,
        uptime_seconds=(datetime.utcnow() - service_start_time).total_seconds()
    )


# Independent pass execution
@app.post("/pipeline/pass/{pass_type}", response_model=JobResult)
async def execute_pass(
    pass_type: PassType,
    request: PassExecutionRequest
):
    """Execute a single pass independently."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    logger.info(f"Independent pass execution requested: {pass_type.value}")

    # Create pipeline request for single pass
    pipeline_request = PipelineExecutionRequest(
        trigger_mode=TriggerMode.INDEPENDENT,
        source_files=[request.source_file],
        env=request.env,
        job_id=request.job_id,
        priority=request.priority,
        start_pass=pass_type,
        end_pass=pass_type,
        context=request.context
    )

    result = await orchestrator.trigger_pipeline(pipeline_request)

    if result.status == "failed":
        raise HTTPException(status_code=500, detail=result.error or "Pass execution failed")

    return result


# Full pipeline execution - Nightly
@app.post("/pipeline/trigger/nightly", response_model=JobResult)
async def trigger_nightly():
    """Trigger nightly pipeline run for all sources in upload folder."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    logger.info("Nightly pipeline trigger requested")

    # Get all files from upload directory
    upload_path = Path(config.get_upload_path())
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Upload directory not found")

    source_files = [
        str(f) for f in upload_path.glob("*.pdf")
        if f.is_file()
    ]

    if not source_files:
        return JSONResponse(
            status_code=200,
            content={"message": "No files to process", "source_files": []}
        )

    logger.info(f"Nightly run: {len(source_files)} files found")

    request = PipelineExecutionRequest(
        trigger_mode=TriggerMode.NIGHTLY,
        source_files=source_files,
        env=config.target_env,
        priority=JobPriority.NORMAL
    )

    result = await orchestrator.trigger_pipeline(request)
    return result


# Full pipeline execution - Ad-hoc
@app.post("/pipeline/trigger/ad-hoc", response_model=JobResult)
async def trigger_ad_hoc():
    """Trigger ad-hoc pipeline run for all sources in upload folder."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    logger.info("Ad-hoc pipeline trigger requested")

    # Get all files from upload directory
    upload_path = Path(config.get_upload_path())
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Upload directory not found")

    source_files = [
        str(f) for f in upload_path.glob("*.pdf")
        if f.is_file()
    ]

    if not source_files:
        return JSONResponse(
            status_code=200,
            content={"message": "No files to process", "source_files": []}
        )

    logger.info(f"Ad-hoc run: {len(source_files)} files found")

    request = PipelineExecutionRequest(
        trigger_mode=TriggerMode.AD_HOC,
        source_files=source_files,
        env=config.target_env,
        priority=JobPriority.HIGH
    )

    result = await orchestrator.trigger_pipeline(request)
    return result


# Full pipeline execution - Selective
@app.post("/pipeline/trigger/selective", response_model=JobResult)
async def trigger_selective(
    source_files: List[str] = Query(..., description="List of source file paths")
):
    """Trigger selective pipeline run for specific sources."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if not source_files:
        raise HTTPException(status_code=400, detail="No source files provided")

    logger.info(f"Selective pipeline trigger requested: {len(source_files)} files")

    # Validate files exist
    invalid_files = []
    for file_path in source_files:
        if not Path(file_path).exists():
            invalid_files.append(file_path)

    if invalid_files:
        raise HTTPException(
            status_code=404,
            detail=f"Files not found: {invalid_files}"
        )

    request = PipelineExecutionRequest(
        trigger_mode=TriggerMode.SELECTIVE,
        source_files=source_files,
        env=config.target_env,
        priority=JobPriority.HIGH
    )

    result = await orchestrator.trigger_pipeline(request)
    return result


# Job management endpoints
@app.get("/pipeline/jobs/{job_id}", response_model=JobResult)
async def get_job_status(job_id: str):
    """Get status of a specific job."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    result = await orchestrator.get_job_status(job_id)

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    return result


@app.delete("/pipeline/jobs/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not initialized")

    cancelled = await orchestrator.cancel_job(job_id)

    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found or already completed")

    return {"message": f"Job {job_id} cancelled", "job_id": job_id}


@app.get("/pipeline/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status: active, completed"),
    limit: int = Query(100, ge=1, le=500)
):
    """List jobs."""
    if not job_tracker:
        raise HTTPException(status_code=503, detail="Service not initialized")

    if status == "active":
        jobs = await job_tracker.list_active_jobs()
    elif status == "completed":
        jobs = await job_tracker.list_completed_jobs(limit=limit)
    else:
        active = await job_tracker.list_active_jobs()
        completed = await job_tracker.list_completed_jobs(limit=limit)
        jobs = active + completed

    return {"jobs": jobs, "count": len(jobs)}


# Worker pool management
@app.get("/pipeline/pools/{pass_type}")
async def get_pool_status(pass_type: PassType):
    """Get status of a specific worker pool."""
    if not pool_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    status = pool_manager.get_pool_status(pass_type)

    if not status:
        raise HTTPException(status_code=404, detail="Worker pool not found")

    return status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=config.port,
        reload=True
    )