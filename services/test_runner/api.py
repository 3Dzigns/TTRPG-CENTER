"""
External Test Runner Service API

MVP v2 External Test Execution Architecture
Provides isolated test execution environment with API interface.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config

logger = get_logger(__name__)

# Test execution models
class TestRequest(BaseModel):
    """Test execution request."""
    test_suite: str = Field(..., description="Test suite to execute (unit|functional|regression|security)")
    test_filter: Optional[str] = Field(None, description="Optional test filter pattern")
    environment: str = Field("test", description="Target environment (dev|test|prod)")
    timeout_seconds: int = Field(300, ge=30, le=3600, description="Test execution timeout")
    parallel: bool = Field(True, description="Enable parallel test execution")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Additional test metadata")

class TestResult(BaseModel):
    """Test execution result."""
    test_id: str
    status: str = Field(..., description="Test status: queued|running|completed|failed|timeout")
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    artifacts: List[str] = Field(default_factory=list)

class TestStatus(BaseModel):
    """Test execution status."""
    test_id: str
    status: str
    progress: float = Field(0.0, ge=0.0, le=1.0)
    current_phase: Optional[str] = None
    estimated_remaining_seconds: Optional[int] = None
    logs_available: bool = False

# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - External Test Runner",
    description="MVP v2 External Test Execution Service",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global test storage (in production, this would be a database)
_test_storage: Dict[str, TestResult] = {}
_active_tests: Dict[str, subprocess.Popen] = {}

@app.on_event("startup")
async def startup_event():
    """Initialize test runner service on startup."""
    logger.info("Starting External Test Runner Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Ensure test directories exist
    env_name = config.get("environment", "test")
    test_dirs = [
        f"env/{env_name}/logs/tests",
        f"env/{env_name}/artifacts/tests",
        "test_reports"
    ]

    for test_dir in test_dirs:
        Path(test_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured test directory exists: {test_dir}")

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "test-runner",
            "version": "2.0.0",
            "environment": os.getenv("TARGET_ENV", "test"),
            "active_tests": len(_active_tests)
        }
    )

@app.post("/tests/execute", response_model=TestResult)
async def execute_tests(
    request: TestRequest,
    background_tasks: BackgroundTasks
):
    """Execute test suite in external test runner."""

    try:
        # Generate unique test ID
        test_id = str(uuid.uuid4())
        logger.info(f"Starting test execution {test_id} for suite: {request.test_suite}")

        # Validate test suite
        valid_suites = ["unit", "functional", "regression", "security", "integration", "e2e"]
        if request.test_suite not in valid_suites:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid test suite. Must be one of: {', '.join(valid_suites)}"
            )

        # Create test result
        test_result = TestResult(
            test_id=test_id,
            status="queued",
            started_at=datetime.utcnow().isoformat()
        )

        _test_storage[test_id] = test_result

        # Start test execution in background
        background_tasks.add_task(
            run_test_suite_async,
            test_id,
            request
        )

        logger.info(f"Test execution {test_id} queued successfully")
        return test_result

    except Exception as e:
        logger.error(f"Error starting test execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start test execution: {str(e)}"
        )

@app.get("/tests/{test_id}", response_model=TestResult)
async def get_test_result(test_id: str):
    """Get test execution result."""

    if test_id not in _test_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test {test_id} not found"
        )

    return _test_storage[test_id]

@app.get("/tests/{test_id}/status", response_model=TestStatus)
async def get_test_status(test_id: str):
    """Get test execution status."""

    if test_id not in _test_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test {test_id} not found"
        )

    result = _test_storage[test_id]

    # Calculate progress based on status
    progress_map = {
        "queued": 0.0,
        "running": 0.5,  # Will be updated with real progress if available
        "completed": 1.0,
        "failed": 1.0,
        "timeout": 1.0
    }

    return TestStatus(
        test_id=test_id,
        status=result.status,
        progress=progress_map.get(result.status, 0.0),
        current_phase=f"Executing {result.summary.get('current_test', 'tests')}" if result.summary else None,
        logs_available=bool(result.stdout or result.stderr)
    )

@app.get("/tests/{test_id}/logs")
async def get_test_logs(test_id: str):
    """Get test execution logs."""

    if test_id not in _test_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test {test_id} not found"
        )

    result = _test_storage[test_id]

    return {
        "test_id": test_id,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
        "status": result.status,
        "updated_at": datetime.utcnow().isoformat()
    }

@app.get("/tests", response_model=List[TestResult])
async def list_tests():
    """List all test executions."""
    return list(_test_storage.values())

@app.delete("/tests/{test_id}")
async def cancel_test(test_id: str):
    """Cancel running test execution."""

    if test_id not in _test_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test {test_id} not found"
        )

    # Cancel running process if active
    if test_id in _active_tests:
        process = _active_tests[test_id]
        if process.poll() is None:  # Still running
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

        del _active_tests[test_id]

    # Update status
    if test_id in _test_storage:
        _test_storage[test_id].status = "cancelled"
        _test_storage[test_id].completed_at = datetime.utcnow().isoformat()

    logger.info(f"Test execution {test_id} cancelled")
    return {"message": f"Test {test_id} cancelled successfully"}

async def run_test_suite_async(test_id: str, request: TestRequest):
    """Run test suite asynchronously."""

    try:
        logger.info(f"Starting test execution {test_id}")

        # Update status to running
        test_result = _test_storage[test_id]
        test_result.status = "running"
        test_result.started_at = datetime.utcnow().isoformat()

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test suite path
        test_paths = {
            "unit": "tests/unit",
            "functional": "tests/functional",
            "regression": "tests/regression",
            "security": "tests/security",
            "integration": "tests/integration",
            "e2e": "tests/e2e"
        }

        test_path = test_paths.get(request.test_suite, f"tests/{request.test_suite}")
        cmd.append(test_path)

        # Add test filter if specified
        if request.test_filter:
            cmd.extend(["-k", request.test_filter])

        # Add parallel execution
        if request.parallel:
            cmd.extend(["-n", "auto"])  # pytest-xdist for parallel execution

        # Add output options
        cmd.extend([
            "-v",  # Verbose output
            "--tb=short",  # Short traceback format
            "--junit-xml=test_reports/junit.xml",  # JUnit XML report
            "--json-report",  # JSON report
            "--json-report-file=test_reports/report.json"
        ])

        logger.info(f"Executing command: {' '.join(cmd)}")

        # Execute test command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/app"
        )

        _active_tests[test_id] = process

        # Wait for completion with timeout
        try:
            stdout, stderr = process.communicate(timeout=request.timeout_seconds)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            exit_code = -1
            test_result.status = "timeout"

        # Remove from active tests
        if test_id in _active_tests:
            del _active_tests[test_id]

        # Update test result
        test_result.completed_at = datetime.utcnow().isoformat()
        test_result.exit_code = exit_code
        test_result.stdout = stdout
        test_result.stderr = stderr

        # Calculate duration
        if test_result.started_at and test_result.completed_at:
            start_time = datetime.fromisoformat(test_result.started_at.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(test_result.completed_at.replace('Z', '+00:00'))
            test_result.duration_seconds = (end_time - start_time).total_seconds()

        # Parse test results summary
        try:
            summary = parse_test_output(stdout, stderr)
            test_result.summary = summary
        except Exception as e:
            logger.warning(f"Failed to parse test output: {e}")

        # Determine final status
        if test_result.status != "timeout":
            test_result.status = "completed" if exit_code == 0 else "failed"

        # Save artifacts
        test_result.artifacts = save_test_artifacts(test_id)

        logger.info(f"Test execution {test_id} completed with status: {test_result.status}")

    except Exception as e:
        logger.error(f"Error executing test {test_id}: {str(e)}")
        test_result.status = "failed"
        test_result.completed_at = datetime.utcnow().isoformat()
        test_result.stderr = str(e)

def parse_test_output(stdout: str, stderr: str) -> Dict[str, Any]:
    """Parse test output to extract summary information."""

    summary = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration": 0.0
    }

    # Parse pytest summary line
    lines = stdout.split('\n')
    for line in lines:
        if "passed" in line and ("failed" in line or "error" in line or "skipped" in line):
            # Parse line like: "=== 5 failed, 10 passed, 2 skipped in 1.23s ==="
            parts = line.split()
            for i, part in enumerate(parts):
                if part.isdigit():
                    count = int(part)
                    if i + 1 < len(parts):
                        status = parts[i + 1].rstrip(',')
                        if status in summary:
                            summary[status] = count
                        summary["total_tests"] += count

            # Extract duration
            if "in" in parts and "s" in parts:
                try:
                    duration_idx = parts.index("in") + 1
                    duration_str = parts[duration_idx].rstrip('s')
                    summary["duration"] = float(duration_str)
                except (ValueError, IndexError):
                    pass

    return summary

def save_test_artifacts(test_id: str) -> List[str]:
    """Save test artifacts and return list of artifact paths."""

    artifacts = []

    # Check for standard test artifacts
    artifact_patterns = [
        "test_reports/junit.xml",
        "test_reports/report.json",
        "test_reports/*.html",
        "test_reports/*.log",
        "test_reports/*.xml"
    ]

    for pattern in artifact_patterns:
        artifact_path = Path(pattern)
        if artifact_path.exists():
            # Copy to test-specific directory
            test_artifact_dir = Path(f"env/test/artifacts/tests/{test_id}")
            test_artifact_dir.mkdir(parents=True, exist_ok=True)

            destination = test_artifact_dir / artifact_path.name
            try:
                import shutil
                shutil.copy2(artifact_path, destination)
                artifacts.append(str(destination))
                logger.info(f"Saved test artifact: {destination}")
            except Exception as e:
                logger.warning(f"Failed to save artifact {artifact_path}: {e}")

    return artifacts

if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    port = int(os.getenv("TEST_RUNNER_PORT", "8195"))

    uvicorn.run(
        "services.test_runner.api:app",
        host="0.0.0.0",
        port=port,
        reload=config.get("environment") == "dev"
    )