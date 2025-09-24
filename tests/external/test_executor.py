"""
Test Executor Service Integration

Integrates external test runner with Admin API service to enable
real test execution through the Test Console.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import HTTPException
try:
    from .test_runner import get_test_runner, TestExecutionError
except ImportError:
    # Handle case when module is imported directly
    from test_runner import get_test_runner, TestExecutionError
from src_common.logging import get_logger


logger = get_logger(__name__)


class TestExecutor:
    """Coordinates test execution between Admin API and external test runner."""

    def __init__(self):
        """Initialize test executor."""
        self.test_runner = get_test_runner()
        self.active_executions: Dict[str, Dict[str, Any]] = {}
        self.execution_results: Dict[str, Dict[str, Any]] = {}

    async def start_test_execution(
        self,
        suite_type: str,
        target_environment: str,
        test_filter: Optional[str] = None,
        timeout_minutes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Start test execution and return execution metadata.

        Args:
            suite_type: Type of test suite to run
            target_environment: Target environment
            test_filter: Optional test filter pattern
            timeout_minutes: Optional timeout override

        Returns:
            Execution metadata dictionary

        Raises:
            HTTPException: If execution cannot be started
        """
        try:
            execution_id = str(uuid.uuid4())

            # Validate inputs
            if suite_type not in self.test_runner.VALID_SUITES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid suite type: {suite_type}"
                )

            if target_environment not in {"dev", "test", "prod"}:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid target environment: {target_environment}"
                )

            # Create execution record
            execution = {
                "execution_id": execution_id,
                "suite_type": suite_type,
                "target_environment": target_environment,
                "status": "queued",
                "progress": 0.0,
                "started_at": datetime.utcnow().isoformat(),
                "test_filter": test_filter,
                "timeout_minutes": timeout_minutes,
                "current_test": None,
                "tests_total": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "results_available": False
            }

            self.active_executions[execution_id] = execution

            # Start execution in background
            asyncio.create_task(self._execute_test_suite(execution_id))

            logger.info(f"Started test execution {execution_id}: {suite_type} on {target_environment}")
            return execution

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to start test execution: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start test execution: {str(e)}"
            )

    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status."""
        if execution_id not in self.active_executions:
            raise HTTPException(
                status_code=404,
                detail=f"Execution {execution_id} not found"
            )

        return self.active_executions[execution_id].copy()

    async def list_executions(self) -> List[Dict[str, Any]]:
        """List all executions."""
        return list(self.active_executions.values())

    async def stop_execution(self, execution_id: str) -> bool:
        """Stop running execution."""
        if execution_id not in self.active_executions:
            return False

        try:
            success = await self.test_runner.stop_execution(execution_id)
            if success:
                execution = self.active_executions[execution_id]
                execution["status"] = "cancelled"
                execution["completed_at"] = datetime.utcnow().isoformat()
                logger.info(f"Stopped execution {execution_id}")
            return success

        except Exception as e:
            logger.error(f"Failed to stop execution {execution_id}: {str(e)}")
            return False

    async def get_execution_results(self, execution_id: str) -> Dict[str, Any]:
        """Get execution results."""
        if execution_id not in self.execution_results:
            raise HTTPException(
                status_code=404,
                detail=f"Results not found for execution {execution_id}"
            )

        return self.execution_results[execution_id]

    async def stream_execution_output(self, execution_id: str):
        """Stream execution output for Server-Sent Events."""
        if execution_id not in self.active_executions:
            raise HTTPException(
                status_code=404,
                detail=f"Execution {execution_id} not found"
            )

        execution = self.active_executions[execution_id]

        # If execution is completed, return final status
        if execution["status"] in ["completed", "failed", "cancelled"]:
            yield f"data: {json.dumps(execution)}\n\n"
            return

        # Stream live updates (would be implemented with actual streaming mechanism)
        # For now, return periodic status updates
        for i in range(10):
            await asyncio.sleep(1)
            execution = self.active_executions.get(execution_id)
            if not execution:
                break

            yield f"data: {json.dumps(execution)}\n\n"

            if execution["status"] in ["completed", "failed", "cancelled"]:
                break

    async def _execute_test_suite(self, execution_id: str):
        """Execute test suite in background."""
        execution = self.active_executions[execution_id]

        try:
            # Update status to running
            execution["status"] = "running"

            # Execute tests with streaming
            results = []
            async for result in self.test_runner.execute_test_suite(
                execution_id,
                execution["suite_type"],
                execution["target_environment"],
                execution["test_filter"],
                execution["timeout_minutes"]
            ):
                # Update execution with progress
                execution.update({
                    "status": result.get("status", execution["status"]),
                    "progress": result.get("progress", execution["progress"]),
                    "current_test": result.get("current_test"),
                    "tests_total": result.get("tests_total", execution["tests_total"]),
                    "tests_passed": result.get("tests_passed", execution["tests_passed"]),
                    "tests_failed": result.get("tests_failed", execution["tests_failed"])
                })

                # Store result for streaming
                results.append(result)

            # Mark as completed
            final_status = results[-1]["status"] if results else "failed"
            execution["status"] = final_status
            execution["progress"] = 1.0
            execution["completed_at"] = datetime.utcnow().isoformat()
            execution["results_available"] = True

            # Store results
            self.execution_results[execution_id] = {
                "execution_id": execution_id,
                "results": results,
                "summary": {
                    "total_tests": execution["tests_total"],
                    "passed_tests": execution["tests_passed"],
                    "failed_tests": execution["tests_failed"],
                    "status": final_status,
                    "duration_seconds": self._calculate_duration(execution)
                },
                "generated_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Completed execution {execution_id}: {final_status}")

        except TestExecutionError as e:
            logger.error(f"Test execution {execution_id} failed: {str(e)}")
            execution["status"] = "failed"
            execution["error"] = str(e)
            execution["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            logger.error(f"Unexpected error in execution {execution_id}: {str(e)}")
            execution["status"] = "failed"
            execution["error"] = f"Unexpected error: {str(e)}"
            execution["completed_at"] = datetime.utcnow().isoformat()

    def _calculate_duration(self, execution: Dict[str, Any]) -> float:
        """Calculate execution duration in seconds."""
        try:
            start_time = datetime.fromisoformat(execution["started_at"])
            end_time = datetime.fromisoformat(execution.get("completed_at", datetime.utcnow().isoformat()))
            return (end_time - start_time).total_seconds()
        except Exception:
            return 0.0


# Global test executor instance
_test_executor: Optional[TestExecutor] = None


def get_test_executor() -> TestExecutor:
    """Get global test executor instance."""
    global _test_executor
    if _test_executor is None:
        _test_executor = TestExecutor()
    return _test_executor