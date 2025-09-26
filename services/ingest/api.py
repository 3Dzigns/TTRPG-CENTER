"""
Ingest Service API

FastAPI service for document ingestion and processing pipeline.
MVP v2 Microservices Architecture
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config
from src_common.auth_models import UserContext
from src_common.security import bootstrap_app_security, record_audit_event, require_roles
from .pipeline import run_ingestion_pipeline, PipelineError


logger = get_logger(__name__)


class JobStatus(BaseModel):
    """Job status response model."""

    job_id: str
    status: str = Field(..., description="Job status: queued, processing, completed, failed")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress percentage")
    current_pass: Optional[str] = Field(None, description="Current processing pass")
    created_at: str
    updated_at: str
    error_message: Optional[str] = None
    artifacts_available: bool = False


class IngestJobRequest(BaseModel):
    """Ingest job creation request."""

    filename: str
    content_type: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    priority: int = Field(1, ge=1, le=5, description="Job priority (1=highest, 5=lowest)")


class IngestResponse(BaseModel):
    """Ingest job creation response."""

    job_id: str
    status: str
    message: str
    estimated_duration_seconds: Optional[int] = None


# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Ingest Service",
    description="Pass 0→G pipeline and tools adapters for PDF processing",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

bootstrap_app_security(app, service_name="ingest")

# Global job storage (in production, this would be a database)
_job_storage: Dict[str, JobStatus] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Ingest Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Ensure required directories exist
    env_name = config.get("environment", "dev")
    base_path = Path(f"env/{env_name}")

    for directory in ["data/ingest", "logs/ingest", "artifacts"]:
        dir_path = base_path / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "ingest",
            "version": "2.0.0",
            "environment": os.getenv("TARGET_ENV", "dev")
        }
    )


@app.post("/ingest/upload", response_model=IngestResponse, dependencies=[Depends(require_roles("admin"))])
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    metadata: Optional[str] = None,
):
    """Upload document for processing through the ingestion pipeline."""

    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        logger.info(f"Starting ingestion job {job_id} for file: {file.filename}")

        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )

        # Check file size (basic validation)
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)

        if file_size_mb > 100:  # 100MB limit
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 100MB limit"
            )

        # Create job status
        import datetime
        now = datetime.datetime.utcnow().isoformat()

        job_status = JobStatus(
            job_id=job_id,
            status="queued",
            progress=0.0,
            created_at=now,
            updated_at=now
        )

        _job_storage[job_id] = job_status

        # Save file to processing directory
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        upload_dir = Path(f"env/{env_name}/data/ingest/{job_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved uploaded file to: {file_path}")

        # Start MVP v2 Pass 0→G pipeline asynchronously
        asyncio.create_task(process_document_mvp_v2(job_id, file_path))

        # Estimate duration based on file size
        estimated_duration = max(60, int(file_size_mb * 30))  # ~30 seconds per MB

        await record_audit_event(
            request,
            {
                "event": "ingest.upload",
                "job_id": job_id,
                "filename": file.filename,
                "size_mb": round(file_size_mb, 2),
            },
        )

        return IngestResponse(
            job_id=job_id,
            status="queued",
            message=f"Document {file.filename} queued for processing",
            estimated_duration_seconds=estimated_duration
        )

    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )


@app.get("/ingest/jobs/{job_id}", response_model=JobStatus, dependencies=[Depends(require_roles("admin"))])
async def get_job_status(job_id: str):
    """Get job status and progress."""

    if job_id not in _job_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    return _job_storage[job_id]


@app.get("/ingest/jobs", response_model=List[JobStatus], dependencies=[Depends(require_roles("admin"))])
async def list_jobs():
    """List all ingestion jobs."""
    return list(_job_storage.values())


@app.get("/ingest/jobs/{job_id}/artifacts")
async def get_job_artifacts(job_id: str):
    """Get job artifacts manifest."""

    if job_id not in _job_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    job_status = _job_storage[job_id]

    if not job_status.artifacts_available:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifacts not yet available for job {job_id}"
        )

    # Load manifest.json if available
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    artifacts_dir = Path(f"env/{env_name}/artifacts/{job_id}")
    manifest_path = artifacts_dir / "manifest.json"

    if manifest_path.exists():
        import json
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        return manifest
    else:
        return {"error": "Manifest not found", "job_id": job_id}


async def process_document_mvp_v2(job_id: str, file_path: Path):
    """Process document through MVP v2 Pass 0→G pipeline."""

    try:
        job_status = _job_storage[job_id]

        # Update status to processing
        job_status.status = "processing"
        job_status.current_pass = "Pass 0 - Preflight & De-dup"
        job_status.progress = 0.0
        import datetime
        job_status.updated_at = datetime.datetime.utcnow().isoformat()

        logger.info(f"Starting Pass 0→G pipeline for job {job_id}")

        # Run the complete MVP v2 pipeline
        manifest = await run_ingestion_pipeline(job_id, file_path)

        # Update job status based on pipeline result
        if manifest.get("status") == "skipped":
            job_status.status = "skipped"
            job_status.current_pass = None
            job_status.progress = 1.0
            job_status.updated_at = datetime.datetime.utcnow().isoformat()
            logger.info(f"Job {job_id} skipped: {manifest.get('reason')}")

        elif manifest.get("status") == "completed":
            job_status.status = "completed"
            job_status.current_pass = None
            job_status.progress = 1.0
            job_status.artifacts_available = True
            job_status.updated_at = datetime.datetime.utcnow().isoformat()
            logger.info(f"Job {job_id} completed successfully")

        else:
            # Pipeline failed
            job_status.status = "failed"
            job_status.current_pass = manifest.get("failed_pass", "unknown")
            job_status.error_message = manifest.get("error", "Pipeline execution failed")
            job_status.updated_at = datetime.datetime.utcnow().isoformat()
            logger.error(f"Job {job_id} failed: {job_status.error_message}")

    except PipelineError as e:
        logger.error(f"Pipeline error for job {job_id}: {str(e)}")
        job_status.status = "failed"
        job_status.error_message = str(e)
        job_status.updated_at = datetime.datetime.utcnow().isoformat()

    except Exception as e:
        logger.error(f"Unexpected error processing job {job_id}: {str(e)}")
        job_status.status = "failed"
        job_status.error_message = f"Unexpected error: {str(e)}"
        job_status.updated_at = datetime.datetime.utcnow().isoformat()


# Legacy function kept for compatibility
async def process_document(job_id: str, file_path: str):
    """Legacy process function - delegates to MVP v2 implementation."""
    return await process_document_mvp_v2(job_id, Path(file_path))


async def create_job_manifest(job_id: str, file_path: str):
    """Create job artifacts manifest."""

    config = get_environment_config()
    env_name = config.get("environment", "dev")

    artifacts_dir = Path(f"env/{env_name}/artifacts/{job_id}")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "job_id": job_id,
        "status": "completed",
        "input_file": str(file_path),
        "passes": {
            "pass_a": {"status": "completed", "output": "parsed_content.json"},
            "pass_b": {"status": "completed", "output": "logical_chunks.json", "threshold_mb": 10},
            "pass_c": {"status": "completed", "output": "extracted_content.json"}
        },
        "created_at": datetime.datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }

    manifest_path = artifacts_dir / "manifest.json"

    import json
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Created manifest for job {job_id}: {manifest_path}")


if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    port_map = {"dev": 8003, "test": 8184, "prod": 8285}
    port = port_map.get(env_name, 8003)

    uvicorn.run(
        "services.ingest.api:app",
        host="0.0.0.0",
        port=port,
        reload=env_name == "dev"
    )
