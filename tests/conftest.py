# tests/conftest.py
"""
Pytest configuration and shared fixtures for TTRPG Center tests.
"""

import asyncio
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Generator, Dict, Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
import uvicorn

import sys
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src_common.app import app, TTRPGApp
from src_common.logging import setup_logging, get_logger
from src_common.environment_isolation import get_environment_validator

logger = get_logger(__name__)


# Configure pytest for async tests
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def target_environment() -> str:
    """Get target environment for test execution."""
    env = os.getenv("TARGET_ENV", "dev")
    logger.info(f"Target environment: {env}")
    return env


@pytest.fixture(scope="session")
def environment_validator(target_environment: str):
    """Get environment validator instance."""
    validator = get_environment_validator()
    validator.current_env = target_environment
    return validator


@pytest.fixture(scope="session")
def test_environment_config(target_environment: str) -> Dict[str, Any]:
    """Get test environment configuration."""
    env_configs = {
        "dev": {
            "base_port": 8000,
            "code_path": "env/dev/code",
            "data_path": "env/dev/data",
            "logs_path": "env/dev/logs",
            "artifacts_path": "env/dev/artifacts",
            "cache_path": "env/dev/cache",
            "uploads_path": "env/dev/uploads",
            "ssl_path": "env/dev/ssl",
            "admin_api_url": "http://localhost:8001",
            "user_api_url": "http://localhost:8002",
            "ingest_service_url": "http://localhost:8003",
            "orchestrator_url": "http://localhost:8004",
            "test_runner_url": "http://localhost:8095",
            "main_app_url": "http://localhost:8001",
        },
        "test": {
            "base_port": 8181,
            "code_path": "env/test/code",
            "data_path": "env/test/data",
            "logs_path": "env/test/logs",
            "artifacts_path": "env/test/artifacts",
            "cache_path": "env/test/cache",
            "uploads_path": "env/test/uploads",
            "ssl_path": "env/test/ssl",
            "admin_api_url": "http://localhost:8182",
            "user_api_url": "http://localhost:8181",
            "ingest_service_url": "http://localhost:8184",
            "orchestrator_url": "http://localhost:8185",
            "test_runner_url": "http://localhost:8195",
            "main_app_url": "http://localhost:8182",
        },
        "prod": {
            "base_port": 8282,
            "code_path": "env/prod/code",
            "data_path": "env/prod/data",
            "logs_path": "env/prod/logs",
            "artifacts_path": "env/prod/artifacts",
            "cache_path": "env/prod/cache",
            "uploads_path": "env/prod/uploads",
            "ssl_path": "env/prod/ssl",
            "admin_api_url": "http://localhost:8283",
            "user_api_url": "http://localhost:8284",
            "ingest_service_url": "http://localhost:8285",
            "orchestrator_url": "http://localhost:8286",
            "test_runner_url": "http://localhost:8295",
            "main_app_url": "http://localhost:8283",
        }
    }
    return env_configs.get(target_environment, env_configs["dev"])


@pytest.fixture(scope="function")
def external_test_mode() -> bool:
    """Check if running in external test mode via Test Console."""
    return os.getenv("EXTERNAL_TEST_MODE", "false").lower() == "true"


@pytest.fixture(scope="function")
def test_output_path(target_environment: str) -> Path:
    """Get test output directory path."""
    output_dir = repo_root / "env" / target_environment / "logs" / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def temp_env_root(tmp_path: Path) -> Path:
    """Create a temporary environment root directory structure."""
    env_root = tmp_path / "env" / "test"
    
    # Create directory structure
    for subdir in ("code", "config", "data", "logs"):
        (env_root / subdir).mkdir(parents=True)
    
    # Create ports.json
    ports_config = {
        "http_port": 8181,
        "websocket_port": 9181,
        "name": "test"
    }
    (env_root / "config" / "ports.json").write_text(json.dumps(ports_config))
    
    # Create .env file
    env_content = """APP_ENV=test
PORT=8181
LOG_LEVEL=INFO
ARTIFACTS_PATH=./artifacts/test
CACHE_TTL_SECONDS=5
"""
    (env_root / "config" / ".env").write_text(env_content)
    
    # Create logging.json
    logging_config = {
        "version": 1,
        "formatters": {
            "json": {
                "format": "%(timestamp)s %(name)s %(levelname)s %(message)s",
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "level": "INFO"
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"]
        }
    }
    (env_root / "config" / "logging.json").write_text(json.dumps(logging_config, indent=2))
    
    return env_root


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for FastAPI application."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncClient:
    """Create an async test client for FastAPI application."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_environment(monkeypatch, temp_env_root: Path):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PORT", "8181")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("CACHE_TTL_SECONDS", "5")
    
    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(temp_env_root.parent.parent)  # Go to the temp root
    
    yield temp_env_root
    
    # Restore original directory
    os.chdir(original_cwd)


@pytest.fixture
def local_server():
    """Start a local server for functional testing."""
    class ServerFixture:
        def __init__(self):
            self.server = None
            self.thread = None
            self.port = None
            self.host = "127.0.0.1"
    
    fixture = ServerFixture()
    
    # Find available port
    import socket
    sock = socket.socket()
    sock.bind(('', 0))
    fixture.port = sock.getsockname()[1]
    sock.close()
    
    # Configure server
    config = uvicorn.Config(
        app,
        host=fixture.host,
        port=fixture.port,
        log_level="error",  # Minimize test output
        access_log=False
    )
    fixture.server = uvicorn.Server(config)
    
    # Start server in thread
    def run_server():
        asyncio.run(fixture.server.serve())
    
    fixture.thread = threading.Thread(target=run_server, daemon=True)
    fixture.thread.start()
    
    # Wait for server to start
    time.sleep(0.5)
    
    yield fixture
    
    # Cleanup
    if fixture.server:
        fixture.server.should_exit = True
    if fixture.thread and fixture.thread.is_alive():
        fixture.thread.join(timeout=1)


@pytest.fixture
def sample_job_data() -> Dict[str, Any]:
    """Sample job data for ingestion testing."""
    return {
        "job_id": "test-job-001",
        "source_file": "sample_ttrpg_manual.pdf",
        "expected_chunks": 5,
        "expected_phases": ["parse_chunk", "enrich", "graph_compile"],
        "timeout_seconds": 10
    }


@pytest.fixture
def artifacts_directory(tmp_path: Path) -> Path:
    """Create artifacts directory for test jobs."""
    artifacts_dir = tmp_path / "artifacts" / "test"
    artifacts_dir.mkdir(parents=True)
    return artifacts_dir


@pytest.fixture
def websocket_messages():
    """Collect WebSocket messages during tests."""
    messages = []
    
    def collect_message(message):
        messages.append({
            "timestamp": time.time(),
            "message": message
        })
    
    return messages, collect_message


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """Configure logging for test runs."""
    # Set up minimal logging for tests
    os.environ["LOG_LEVEL"] = "ERROR"  # Minimize test output
    logger = setup_logging()
    return logger


@pytest.fixture
def isolated_environment(tmp_path: Path, monkeypatch):
    """
    Create completely isolated environment for testing environment isolation.
    This fixture validates that environments don't cross-contaminate.
    """
    # Create multiple environment directories
    envs = {}
    for env_name in ("dev", "test", "prod"):
        env_root = tmp_path / "env" / env_name
        for subdir in ("code", "config", "data", "logs"):
            (env_root / subdir).mkdir(parents=True)
        
        # Create unique ports and configs
        ports = {"dev": 8000, "test": 8181, "prod": 8282}
        port_config = {
            "http_port": ports[env_name],
            "websocket_port": ports[env_name] + 1000,
            "name": env_name
        }
        (env_root / "config" / "ports.json").write_text(json.dumps(port_config))
        
        envs[env_name] = env_root
    
    # Change to temp directory
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    
    yield envs
    
    os.chdir(original_cwd)


class MockWebSocketBroadcast:
    """Mock WebSocket broadcast for testing."""
    
    def __init__(self):
        self.messages = []
    
    async def __call__(self, message: Dict[str, Any]):
        """Mock broadcast function that captures messages."""
        self.messages.append({
            "timestamp": time.time(),
            "message": message
        })
    
    def get_messages(self) -> list:
        """Get all captured messages."""
        return self.messages
    
    def clear(self):
        """Clear captured messages."""
        self.messages.clear()


@pytest.fixture
def mock_websocket_broadcast():
    """Provide mock WebSocket broadcast for testing."""
    return MockWebSocketBroadcast()


# Performance measurement fixtures
@pytest.fixture
def performance_monitor():
    """Monitor performance during tests."""
    class PerformanceMonitor:
        def __init__(self):
            self.timings = {}
            self.start_times = {}
        
        def start(self, operation: str):
            self.start_times[operation] = time.time()
        
        def end(self, operation: str) -> float:
            if operation in self.start_times:
                duration = time.time() - self.start_times[operation]
                self.timings[operation] = duration
                del self.start_times[operation]
                return duration
            return 0.0
        
        def get_timing(self, operation: str) -> float:
            return self.timings.get(operation, 0.0)
        
        def assert_under_threshold(self, operation: str, threshold_ms: float):
            """Assert that operation completed under threshold."""
            duration_ms = self.timings.get(operation, 0) * 1000
            assert duration_ms < threshold_ms, f"{operation} took {duration_ms}ms, expected < {threshold_ms}ms"
    
    return PerformanceMonitor()


# Cleanup fixture
@pytest.fixture(autouse=True)
def cleanup_environment():
    """Automatically clean up environment after each test."""
    yield
    
    # Clean up any temporary environment variables that might have been set
    test_env_vars = [k for k in os.environ.keys() if k.startswith('TEST_')]
    for var in test_env_vars:
        if var in os.environ:
            del os.environ[var]


# External test execution hooks for Test Console integration
def pytest_configure(config):
    """Configure pytest for external test execution."""
    target_env = os.getenv("TARGET_ENV", "dev")

    # Configure logging for external execution
    if os.getenv("EXTERNAL_TEST_MODE") == "true":
        config.option.log_cli = True
        config.option.log_cli_level = "INFO"

    # Set environment-specific pytest options
    if hasattr(config.option, 'json_report_file'):
        env_logs = repo_root / "env" / target_env / "logs"
        env_logs.mkdir(parents=True, exist_ok=True)
        config.option.json_report_file = str(env_logs / "pytest_report.json")

    logger.info(f"Pytest configured for {target_env} environment")


def pytest_collection_modifyitems(config, items):
    """Modify test collection for external execution."""
    target_env = os.getenv("TARGET_ENV", "dev")

    # Skip tests not compatible with current environment
    skip_markers = {
        "dev": [],  # Dev can run all tests
        "test": ["slow"],  # Test environment skips slow tests
        "prod": ["slow", "integration"]  # Prod skips slow and integration tests
    }

    skip_list = skip_markers.get(target_env, [])

    for item in items:
        for marker in skip_list:
            if marker in [m.name for m in item.iter_markers()]:
                skip_reason = f"Skipped in {target_env} environment"
                item.add_marker(pytest.mark.skip(reason=skip_reason))


def pytest_runtest_setup(item):
    """Setup for individual test execution."""
    if os.getenv("EXTERNAL_TEST_MODE") == "true":
        logger.info(f"Starting test: {item.nodeid}")


def pytest_runtest_teardown(item):
    """Teardown for individual test execution."""
    if os.getenv("EXTERNAL_TEST_MODE") == "true":
        logger.info(f"Completed test: {item.nodeid}")


def pytest_exception_interact(node, call, report):
    """Handle test exceptions for external monitoring."""
    if os.getenv("EXTERNAL_TEST_MODE") == "true" and report.failed:
        logger.error(f"Test failed: {node.nodeid} - {call.excinfo.value}")
