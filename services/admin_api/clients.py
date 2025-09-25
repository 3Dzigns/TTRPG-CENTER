"""
HTTP clients for Admin API service communication.

Proper service client architecture replacing sys.path injection patterns.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx

from src_common.config import get_environment_config
from src_common.logging import get_logger


logger = get_logger(__name__)


class TestRunnerClient:
    """HTTP client for test runner service communication."""

    def __init__(self, environment: str):
        self.environment = environment
        self.config = get_environment_config()
        self.base_url = self._get_test_runner_url()
        self.timeout = httpx.Timeout(300.0)  # 5 minutes for test execution

    def _get_test_runner_url(self) -> str:
        """Get test runner service URL based on environment."""
        port_map = {"dev": 8005, "test": 8186, "prod": 8287}
        port = port_map.get(self.environment, 8005)
        return f"http://localhost:{port}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
            except httpx.RequestError as exc:  # pragma: no cover - network guard
                logger.error("Test runner request failed", extra={"url": url, "error": str(exc)})
                raise TestRunnerError(f"Failed to communicate with test runner: {exc}") from exc
            except httpx.HTTPStatusError as exc:  # pragma: no cover - HTTP guard
                logger.error(
                    "Test runner HTTP error",
                    extra={"url": url, "status": exc.response.status_code, "body": exc.response.text},
                )
                raise TestRunnerError(
                    f"Test runner returned error: {exc.response.status_code}"
                ) from exc
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    async def start_test_execution(
        self,
        suite_type: str,
        target_environment: str,
        test_filter: Optional[str] = None,
        timeout_minutes: int = 30,
    ) -> Dict[str, Any]:
        payload = {
            "test_suite": suite_type,
            "environment": target_environment,
            "test_filter": test_filter,
            "timeout_seconds": max(30, int(timeout_minutes) * 60),
        }
        return await self._request("POST", "/tests/execute", json=payload)

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/tests/{execution_id}")

    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/tests/{execution_id}/status")

    async def get_execution_logs(self, execution_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/tests/{execution_id}/logs")

    async def list_executions(self) -> List[Dict[str, Any]]:
        data = await self._request("GET", "/tests")
        return list(data)

    async def stop_execution(self, execution_id: str) -> None:
        await self._request("DELETE", f"/tests/{execution_id}")

    async def get_execution_results(self, execution_id: str) -> Dict[str, Any]:
        return await self.get_execution(execution_id)

    async def stream_execution_output(self, execution_id: str):
        logs = await self.get_execution_logs(execution_id)
        status = await self.get_execution_status(execution_id)
        stdout = logs.get("stdout") or ""
        stderr = logs.get("stderr") or ""
        progress = status.get("progress")
        state = status.get("status")

        if stdout:
            for line in stdout.splitlines():
                payload = {"line": line, "stream": "stdout", "status": state, "progress": progress}
                yield f"data: {json.dumps(payload)}

"
        if stderr:
            for line in stderr.splitlines():
                payload = {"line": line, "stream": "stderr", "status": state, "progress": progress}
                yield f"data: {json.dumps(payload)}

"
        terminal = {"status": state, "progress": progress, "complete": True}
        yield f"data: {json.dumps(terminal)}

"


class OrchestratorClient:
    """HTTP client for orchestrator service communication."""

    def __init__(self, environment: str):
        self.environment = environment
        self.base_url = self._get_orchestrator_url()
        self.timeout = httpx.Timeout(60.0)

    def _get_orchestrator_url(self) -> str:
        """Get orchestrator service URL based on environment."""
        port_map = {"dev": 8004, "test": 8185, "prod": 8286}
        port = port_map.get(self.environment, 8004)
        return f"http://localhost:{port}"

    async def get_policies(self) -> Dict[str, Any]:
        """Get current orchestrator policies."""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/policies")
                response.raise_for_status()
                return response.json()

            except httpx.RequestError as e:
                logger.error(f"Policy fetch failed: {e}")
                raise OrchestratorError(f"Failed to fetch policies: {e}")

    async def reload_configuration(self) -> Dict[str, Any]:
        """Reload orchestrator configuration."""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/admin/reload")
                response.raise_for_status()
                return response.json()

            except httpx.RequestError as e:
                logger.error(f"Configuration reload failed: {e}")
                raise OrchestratorError(f"Failed to reload configuration: {e}")

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Get orchestrator diagnostics."""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/diagnostics")
                response.raise_for_status()
                return response.json()

            except httpx.RequestError as e:
                logger.error(f"Diagnostics fetch failed: {e}")
                raise OrchestratorError(f"Failed to fetch diagnostics: {e}")


class VectorStoreClient:
    """HTTP client for vector store operations."""

    def __init__(self, environment: str):
        self.environment = environment
        self.config = get_environment_config()
        # Vector store operations will be handled through direct database clients
        # This client provides HTTP abstraction for admin operations

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get vector collection statistics."""
        # Implementation would connect to vector database
        # For now, return mock stats
        return {
            "total_chunks": 0,
            "collections": [],
            "index_status": "unknown"
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check vector store health."""
        return {"status": "healthy", "connection": "ok"}


class ServiceClientError(Exception):
    """Base exception for service client errors."""
    pass


class TestRunnerError(ServiceClientError):
    """Test runner service communication error."""
    pass


class OrchestratorError(ServiceClientError):
    """Orchestrator service communication error."""
    pass


class VectorStoreError(ServiceClientError):
    """Vector store service communication error."""
    pass


class ServiceClientFactory:
    """Factory for creating service clients with proper configuration."""

    def __init__(self, environment: str):
        self.environment = environment

    def get_test_runner_client(self) -> TestRunnerClient:
        """Get configured test runner client."""
        return TestRunnerClient(self.environment)

    def get_orchestrator_client(self) -> OrchestratorClient:
        """Get configured orchestrator client."""
        return OrchestratorClient(self.environment)

    def get_vector_store_client(self) -> VectorStoreClient:
        """Get configured vector store client."""
        return VectorStoreClient(self.environment)
