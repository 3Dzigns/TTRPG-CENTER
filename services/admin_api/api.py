"""
Admin API Service

FastAPI service for administrative operations and external test execution.
MVP v2 Microservices Architecture - Critical component for Admin UI Test Console
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config

# Import external test execution components
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests" / "external"))
from test_executor import get_test_executor


logger = get_logger(__name__)


class ArtifactInfo(BaseModel):
    """Artifact information model."""

    job_id: str
    created_at: str
    size_bytes: int
    manifest_available: bool
    files: List[str]


class JobInfo(BaseModel):
    """Job information model."""

    job_id: str
    status: str
    created_at: str
    updated_at: str
    artifacts_size_bytes: Optional[int] = None


class TestSuiteRequest(BaseModel):
    """External test suite execution request."""

    suite_type: str = Field(..., description="Test suite: unit, functional, security, regression, perf")
    target_environment: str = Field(..., description="Target environment: dev, test, prod")
    test_filter: Optional[str] = Field(None, description="Optional test filter pattern")
    timeout_minutes: Optional[int] = Field(30, ge=1, le=120, description="Test timeout in minutes")


class TestExecution(BaseModel):
    """Test execution status."""

    execution_id: str
    suite_type: str
    target_environment: str
    status: str  # queued, running, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0
    current_test: Optional[str] = None
    results_available: bool = False


class DictionaryEntry(BaseModel):
    """Dictionary entry model."""

    term: str
    definition: str
    category: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)


# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Admin API",
    description="Administrative operations and external test execution",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global test execution storage
_test_executions: Dict[str, TestExecution] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Admin API Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Verify test runner capabilities
    _verify_test_runner_setup()


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "admin_api",
            "version": "2.0.0",
            "environment": os.getenv("TARGET_ENV", "dev"),
            "test_runner_ready": True
        }
    )


# =============================================================================
# Artifacts Management
# =============================================================================

@app.get("/artifacts", response_model=List[ArtifactInfo])
async def list_artifacts():
    """List all available job artifacts."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        artifacts_dir = Path(f"env/{env_name}/artifacts")

        if not artifacts_dir.exists():
            return []

        artifacts = []
        for job_dir in artifacts_dir.iterdir():
            if job_dir.is_dir():
                try:
                    manifest_path = job_dir / "manifest.json"
                    files = [f.name for f in job_dir.iterdir() if f.is_file()]

                    # Calculate total size
                    total_size = sum(f.stat().st_size for f in job_dir.iterdir() if f.is_file())

                    # Get creation time from manifest or directory
                    created_at = None
                    if manifest_path.exists():
                        with open(manifest_path, 'r') as f:
                            manifest = json.load(f)
                            created_at = manifest.get('created_at')

                    if not created_at:
                        import datetime
                        stat = job_dir.stat()
                        created_at = datetime.datetime.fromtimestamp(stat.st_ctime).isoformat()

                    artifacts.append(ArtifactInfo(
                        job_id=job_dir.name,
                        created_at=created_at,
                        size_bytes=total_size,
                        manifest_available=manifest_path.exists(),
                        files=files
                    ))

                except Exception as e:
                    logger.warning(f"Error processing artifact {job_dir.name}: {str(e)}")
                    continue

        return sorted(artifacts, key=lambda x: x.created_at, reverse=True)

    except Exception as e:
        logger.error(f"Error listing artifacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list artifacts: {str(e)}"
        )


@app.get("/artifacts/{job_id}")
async def get_job_artifacts(job_id: str):
    """Get detailed artifacts for a specific job."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        artifacts_dir = Path(f"env/{env_name}/artifacts/{job_id}")

        if not artifacts_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifacts not found for job {job_id}"
            )

        manifest_path = artifacts_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            manifest = {"error": "Manifest not found", "job_id": job_id}

        # Add file listing
        files = []
        for file_path in artifacts_dir.iterdir():
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "modified_at": file_path.stat().st_mtime
                })

        manifest["files"] = files
        return manifest

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job artifacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job artifacts: {str(e)}"
        )


@app.delete("/artifacts/{job_id}")
async def cleanup_job_artifacts(job_id: str):
    """Clean up artifacts for a specific job."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        artifacts_dir = Path(f"env/{env_name}/artifacts/{job_id}")

        if not artifacts_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifacts not found for job {job_id}"
            )

        # Remove all files in the job directory
        import shutil
        shutil.rmtree(artifacts_dir)

        logger.info(f"Cleaned up artifacts for job {job_id}")

        return {"message": f"Artifacts cleaned up for job {job_id}", "job_id": job_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up artifacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup artifacts: {str(e)}"
        )


# =============================================================================
# External Test Execution (Admin UI Test Console)
# =============================================================================

@app.post("/test/execute", response_model=TestExecution)
async def execute_test_suite(request: TestSuiteRequest):
    """
    Execute external test suite - Core Admin UI Test Console functionality.

    This endpoint enables the Admin UI to run test suites against any environment
    and stream results back in real-time.
    """

    try:
        import uuid
        execution_id = str(uuid.uuid4())

        logger.info(f"Starting test execution {execution_id}: {request.suite_type} on {request.target_environment}")

        # Validate suite type
        valid_suites = ["unit", "functional", "security", "regression", "perf"]
        if request.suite_type not in valid_suites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid suite type. Must be one of: {valid_suites}"
            )

        # Validate target environment
        valid_envs = ["dev", "test", "prod"]
        if request.target_environment not in valid_envs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid target environment. Must be one of: {valid_envs}"
            )

        # Create test execution using external test executor
        test_executor = get_test_executor()
        execution_result = await test_executor.start_test_execution(
            suite_type=request.suite_type,
            target_environment=request.target_environment,
            test_filter=request.test_filter,
            timeout_minutes=request.timeout_minutes
        )

        # Convert to our TestExecution model
        test_execution = TestExecution(
            execution_id=execution_result["execution_id"],
            suite_type=execution_result["suite_type"],
            target_environment=execution_result["target_environment"],
            status=execution_result["status"],
            started_at=execution_result["started_at"],
            progress=execution_result["progress"],
            current_test=execution_result.get("current_test"),
            results_available=execution_result["results_available"]
        )

        _test_executions[execution_result["execution_id"]] = test_execution
        return test_execution

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start test execution: {str(e)}"
        )


@app.get("/test/executions/{execution_id}", response_model=TestExecution)
async def get_test_execution_status(execution_id: str):
    """Get status of a test execution."""

    try:
        test_executor = get_test_executor()
        execution_data = await test_executor.get_execution_status(execution_id)

        # Update local cache and return
        test_execution = TestExecution(
            execution_id=execution_data["execution_id"],
            suite_type=execution_data["suite_type"],
            target_environment=execution_data["target_environment"],
            status=execution_data["status"],
            started_at=execution_data.get("started_at"),
            completed_at=execution_data.get("completed_at"),
            progress=execution_data["progress"],
            current_test=execution_data.get("current_test"),
            results_available=execution_data["results_available"]
        )

        _test_executions[execution_id] = test_execution
        return test_execution

    except Exception as e:
        logger.error(f"Error getting execution status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test execution {execution_id} not found"
        )


@app.get("/test/executions", response_model=List[TestExecution])
async def list_test_executions():
    """List all test executions."""
    try:
        test_executor = get_test_executor()
        executions_data = await test_executor.list_executions()

        # Convert to our TestExecution models
        test_executions = []
        for execution_data in executions_data:
            test_execution = TestExecution(
                execution_id=execution_data["execution_id"],
                suite_type=execution_data["suite_type"],
                target_environment=execution_data["target_environment"],
                status=execution_data["status"],
                started_at=execution_data.get("started_at"),
                completed_at=execution_data.get("completed_at"),
                progress=execution_data["progress"],
                current_test=execution_data.get("current_test"),
                results_available=execution_data["results_available"]
            )
            test_executions.append(test_execution)
            _test_executions[execution_data["execution_id"]] = test_execution

        return test_executions

    except Exception as e:
        logger.error(f"Error listing executions: {str(e)}")
        return list(_test_executions.values())


@app.get("/test/executions/{execution_id}/stream")
async def stream_test_output(execution_id: str):
    """Stream test execution output in real-time."""

    try:
        test_executor = get_test_executor()

        async def generate_stream():
            """Generate real test output stream using external test executor."""
            try:
                async for output in test_executor.stream_execution_output(execution_id):
                    yield output
            except Exception as e:
                error_msg = f"data: {json.dumps({'error': str(e), 'status': 'failed'})}\n\n"
                yield error_msg

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"Error setting up stream for execution {execution_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test execution {execution_id} not found"
        )


@app.post("/test/executions/{execution_id}/stop")
async def stop_test_execution(execution_id: str):
    """Stop a running test execution."""

    try:
        test_executor = get_test_executor()
        success = await test_executor.stop_execution(execution_id)

        if success:
            return {"status": "stopped", "execution_id": execution_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test execution {execution_id} not found or already stopped"
            )

    except Exception as e:
        logger.error(f"Error stopping execution {execution_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop test execution: {str(e)}"
        )


@app.get("/test/executions/{execution_id}/results")
async def download_test_results(execution_id: str):
    """Download test execution results."""

    try:
        test_executor = get_test_executor()
        results = await test_executor.get_execution_results(execution_id)

        # Return results as JSON response with appropriate headers for download
        return JSONResponse(
            content=results,
            headers={
                "Content-Disposition": f"attachment; filename=test_results_{execution_id}.json"
            }
        )

    except Exception as e:
        logger.error(f"Error getting results for execution {execution_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test results for execution {execution_id} not found"
        )


# Mock function removed - now using real external test executor


def _verify_test_runner_setup():
    """Verify that external test runner is properly configured."""

    try:
        # Verify external test executor is available
        test_executor = get_test_executor()
        logger.info("External test executor initialized successfully")

        # Check if pytest is available
        result = subprocess.run(["pytest", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Test runner verified: {result.stdout.strip()}")
        else:
            logger.warning("pytest not available - external test execution may fail")

    except ImportError as e:
        logger.error(f"Failed to import external test executor: {str(e)}")
    except FileNotFoundError:
        logger.warning("pytest not found - external test execution may fail")
    except Exception as e:
        logger.error(f"Error verifying test runner setup: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    port_map = {"dev": 8001, "test": 8182, "prod": 8283}
    port = port_map.get(env_name, 8001)

    uvicorn.run(
        "services.admin_api.api:app",
        host="0.0.0.0",
        port=port,
        reload=env_name == "dev"
    )