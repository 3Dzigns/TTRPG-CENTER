"""
External Test Runner for MVP v2 Test Console

Executes test suites externally against target environments and provides
real-time streaming output. Core component for Admin UI Test Console.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, AsyncGenerator, Any

from src_common.logging import get_logger
from src_common.environment_isolation import get_environment_validator


logger = get_logger(__name__)


class TestExecutionError(Exception):
    """Raised when test execution fails."""
    pass


class ExternalTestRunner:
    """
    External test runner for MVP v2 Test Console.

    Executes test suites against target environments and provides
    streaming output for real-time monitoring.
    """

    VALID_SUITES = {
        "unit": {
            "name": "Unit Tests",
            "description": "Fast, isolated component tests",
            "command": ["python", "-m", "pytest", "tests/unit", "-v"],
            "timeout": 600,
            "markers": ["unit"]
        },
        "functional": {
            "name": "Functional Tests",
            "description": "API and UI workflow tests",
            "command": ["python", "-m", "pytest", "tests/functional", "-v"],
            "timeout": 1800,
            "markers": ["functional"]
        },
        "security": {
            "name": "Security Tests",
            "description": "SAST/DAST and vulnerability scans",
            "command": ["python", "-m", "pytest", "tests/security", "-v"],
            "timeout": 900,
            "markers": ["security"]
        },
        "regression": {
            "name": "Regression Tests",
            "description": "Golden snapshots and eval sets",
            "command": ["python", "-m", "pytest", "tests/regression", "-v"],
            "timeout": 2400,
            "markers": ["regression"]
        },
        "perf": {
            "name": "Performance Tests",
            "description": "Load testing and benchmarks",
            "command": ["python", "-m", "pytest", "tests/perf", "-v"],
            "timeout": 3600,
            "markers": ["perf"]
        }
    }

    def __init__(self):
        """Initialize test runner."""
        self.env_validator = get_environment_validator()
        self.current_env = self.env_validator.current_env
        self._active_processes: Dict[str, subprocess.Popen] = {}

    async def execute_test_suite(
        self,
        execution_id: str,
        suite_type: str,
        target_environment: str,
        test_filter: Optional[str] = None,
        timeout_minutes: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute test suite and yield streaming results.

        Args:
            execution_id: Unique execution identifier
            suite_type: Type of test suite to run
            target_environment: Target environment (dev/test/prod)
            test_filter: Optional test filter pattern
            timeout_minutes: Optional timeout override

        Yields:
            Dictionary with streaming results and progress updates

        Raises:
            TestExecutionError: If execution fails
        """
        logger.info(f"Starting test execution {execution_id}: {suite_type} on {target_environment}")

        # Validate inputs
        if suite_type not in self.VALID_SUITES:
            raise TestExecutionError(f"Invalid suite type: {suite_type}")

        if target_environment not in {"dev", "test", "prod"}:
            raise TestExecutionError(f"Invalid target environment: {target_environment}")

        suite_config = self.VALID_SUITES[suite_type]
        timeout_seconds = (timeout_minutes or suite_config["timeout"] // 60) * 60

        # Prepare execution environment
        env_vars = self._prepare_test_environment(target_environment)
        command = self._build_test_command(suite_config, test_filter, target_environment)

        # Start execution
        start_time = time.time()
        yield {
            "status": "starting",
            "message": f"Starting {suite_config['name']} on {target_environment}",
            "progress": 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            # Execute tests with streaming output
            async for result in self._execute_with_streaming(
                execution_id, command, env_vars, timeout_seconds
            ):
                # Add execution metadata
                result.update({
                    "execution_id": execution_id,
                    "suite_type": suite_type,
                    "target_environment": target_environment,
                    "elapsed_seconds": time.time() - start_time
                })
                yield result

        except asyncio.TimeoutError:
            logger.error(f"Test execution {execution_id} timed out after {timeout_seconds}s")
            yield {
                "status": "failed",
                "error": f"Execution timed out after {timeout_seconds} seconds",
                "progress": 0.0,
                "timestamp": datetime.utcnow().isoformat()
            }
            raise TestExecutionError(f"Test execution timed out after {timeout_seconds} seconds")

        except Exception as e:
            logger.error(f"Test execution {execution_id} failed: {str(e)}")
            yield {
                "status": "failed",
                "error": str(e),
                "progress": 0.0,
                "timestamp": datetime.utcnow().isoformat()
            }
            raise TestExecutionError(f"Test execution failed: {str(e)}")

        finally:
            # Cleanup
            if execution_id in self._active_processes:
                process = self._active_processes[execution_id]
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                del self._active_processes[execution_id]

    async def stop_execution(self, execution_id: str) -> bool:
        """
        Stop running test execution.

        Args:
            execution_id: Execution to stop

        Returns:
            True if stopped successfully
        """
        if execution_id not in self._active_processes:
            return False

        try:
            process = self._active_processes[execution_id]
            process.terminate()

            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

            del self._active_processes[execution_id]
            logger.info(f"Stopped test execution {execution_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop execution {execution_id}: {str(e)}")
            return False

    def get_available_suites(self) -> List[Dict[str, str]]:
        """Get list of available test suites."""
        return [
            {
                "value": key,
                "name": config["name"],
                "description": config["description"]
            }
            for key, config in self.VALID_SUITES.items()
        ]

    def _prepare_test_environment(self, target_environment: str) -> Dict[str, str]:
        """Prepare environment variables for test execution."""
        env_vars = os.environ.copy()

        # Set target environment
        env_vars["TARGET_ENV"] = target_environment
        env_vars["TEST_ENV"] = target_environment

        # Set environment-specific configuration
        env_base_ports = {"dev": 8000, "test": 8181, "prod": 8282}
        base_port = env_base_ports[target_environment]

        env_vars.update({
            "MAIN_APP_PORT": str(base_port),
            "ADMIN_API_PORT": str(base_port + 1),
            "USER_API_PORT": str(base_port + 2),
            "INGEST_SERVICE_PORT": str(base_port + 3),
            "ORCHESTRATOR_SERVICE_PORT": str(base_port + 4),
        })

        # Set service URLs
        env_vars.update({
            "MAIN_APP_URL": f"http://localhost:{base_port}",
            "ADMIN_API_URL": f"http://localhost:{base_port + 1}",
            "USER_API_URL": f"http://localhost:{base_port + 2}",
            "INGEST_SERVICE_URL": f"http://localhost:{base_port + 3}",
            "ORCHESTRATOR_URL": f"http://localhost:{base_port + 4}",
        })

        # Add test execution flags
        env_vars.update({
            "PYTEST_CURRENT_TEST": "external_execution",
            "CI": "true",
            "EXTERNAL_TEST_MODE": "true"
        })

        logger.debug(f"Prepared environment for {target_environment}: {list(env_vars.keys())}")
        return env_vars

    def _build_test_command(
        self,
        suite_config: Dict[str, Any],
        test_filter: Optional[str],
        target_environment: str
    ) -> List[str]:
        """Build test execution command."""
        command = suite_config["command"].copy()

        # Add markers
        if suite_config["markers"]:
            markers = " or ".join(suite_config["markers"])
            command.extend(["-m", markers])

        # Add test filter
        if test_filter:
            command.extend(["-k", test_filter])

        # Add output formatting
        command.extend([
            "--tb=short",
            "--no-header",
            "--quiet",
            "-x",  # Stop on first failure for faster feedback
        ])

        # Add environment-specific test directory
        env_test_dir = f"tests/{target_environment}"
        if Path(env_test_dir).exists():
            # Replace generic test path with environment-specific one
            for i, part in enumerate(command):
                if part.startswith("tests/") and not part.startswith(f"tests/{target_environment}"):
                    command[i] = part.replace("tests/", f"tests/{target_environment}/")

        # Add JSON output for parsing
        json_output_file = f"test-results-{target_environment}-{int(time.time())}.json"
        command.extend(["--json-report", f"--json-report-file={json_output_file}"])

        logger.info(f"Built test command: {' '.join(command)}")
        return command

    async def _execute_with_streaming(
        self,
        execution_id: str,
        command: List[str],
        env_vars: Dict[str, str],
        timeout_seconds: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute command and stream output in real-time."""

        process = None
        try:
            # Start process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,  # Line buffered
                env=env_vars
            )

            self._active_processes[execution_id] = process

            # Stream output
            test_count = 0
            passed_count = 0
            failed_count = 0
            current_test = None

            yield {
                "status": "running",
                "message": "Test execution started",
                "progress": 0.1,
                "current_test": None,
                "timestamp": datetime.utcnow().isoformat()
            }

            start_time = time.time()

            while True:
                # Check timeout
                if time.time() - start_time > timeout_seconds:
                    process.terminate()
                    raise asyncio.TimeoutError()

                # Read line with timeout
                try:
                    line = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, process.stdout.readline
                        ),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Check if process is still running
                    if process.poll() is not None:
                        break
                    continue

                if not line:
                    # Process finished
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse test progress
                progress_data = self._parse_test_output(
                    line, test_count, passed_count, failed_count, current_test
                )

                if progress_data:
                    test_count = progress_data.get("total_tests", test_count)
                    passed_count = progress_data.get("passed_tests", passed_count)
                    failed_count = progress_data.get("failed_tests", failed_count)
                    current_test = progress_data.get("current_test", current_test)

                # Calculate progress
                if test_count > 0:
                    progress = min(0.9, (passed_count + failed_count) / test_count)
                else:
                    progress = 0.3

                # Yield streaming result
                yield {
                    "status": "running",
                    "line": line,
                    "progress": progress,
                    "current_test": current_test,
                    "tests_total": test_count,
                    "tests_passed": passed_count,
                    "tests_failed": failed_count,
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Get final exit code
            exit_code = process.poll()

            # Final result
            if exit_code == 0:
                yield {
                    "status": "completed",
                    "message": f"All tests passed ({passed_count} passed)",
                    "progress": 1.0,
                    "tests_total": test_count,
                    "tests_passed": passed_count,
                    "tests_failed": failed_count,
                    "exit_code": exit_code,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                yield {
                    "status": "failed",
                    "message": f"Tests failed ({failed_count} failed, {passed_count} passed)",
                    "progress": 1.0,
                    "tests_total": test_count,
                    "tests_passed": passed_count,
                    "tests_failed": failed_count,
                    "exit_code": exit_code,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            if process:
                process.terminate()
            raise

    def _parse_test_output(
        self,
        line: str,
        current_test_count: int,
        current_passed: int,
        current_failed: int,
        current_test: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Parse pytest output to extract progress information."""

        result = {}

        # Parse test result lines
        if " PASSED " in line or " FAILED " in line or " SKIPPED " in line:
            # Extract test name
            if "::" in line:
                test_name = line.split("::")[-1].split(" ")[0]
                result["current_test"] = test_name

            if " PASSED " in line:
                result["passed_tests"] = current_passed + 1
            elif " FAILED " in line:
                result["failed_tests"] = current_failed + 1

            result["total_tests"] = current_test_count + 1

        # Parse collection phase
        elif "collected" in line and "items" in line:
            try:
                # Extract number from "collected X items"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "collected" and i + 1 < len(parts):
                        count = int(parts[i + 1])
                        result["total_tests"] = count
                        break
            except (ValueError, IndexError):
                pass

        # Parse running test
        elif line.startswith("tests/") and "::" in line:
            test_name = line.split("::")[-1]
            result["current_test"] = test_name

        return result if result else None


# Global test runner instance
_test_runner: Optional[ExternalTestRunner] = None


def get_test_runner() -> ExternalTestRunner:
    """Get global test runner instance."""
    global _test_runner
    if _test_runner is None:
        _test_runner = ExternalTestRunner()
    return _test_runner


async def execute_test_suite_stream(
    suite_type: str,
    target_environment: str,
    test_filter: Optional[str] = None,
    timeout_minutes: Optional[int] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """Execute test suite with streaming output."""
    execution_id = str(uuid.uuid4())
    runner = get_test_runner()

    async for result in runner.execute_test_suite(
        execution_id, suite_type, target_environment, test_filter, timeout_minutes
    ):
        yield result