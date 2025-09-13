# tests/container/conftest.py
"""
FR-006: Container Test Configuration
Shared fixtures and configuration for container tests
"""

import pytest
import os
import subprocess
import time
import requests
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def ensure_test_environment():
    """Ensure we're running in a test environment with containers"""
    # Check that this is actually a test environment
    app_env = os.getenv("APP_ENV", "unknown")
    
    if app_env not in ["dev", "test"]:
        pytest.skip("Container tests require dev or test environment")
    
    # Check that Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("Docker not available for container tests")
    
    # Check that containers are running
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=ttrpg", "--format", "{{.Names}}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0 or not result.stdout.strip():
        pytest.skip("TTRPG containers not running - start with: scripts/deploy.ps1 -Action up")


@pytest.fixture(scope="session")
def wait_for_stack_ready():
    """Wait for the entire stack to be ready before running tests"""
    max_wait = 300  # 5 minutes
    start_time = time.time()
    
    print("\nWaiting for stack to be ready...")
    
    while time.time() - start_time < max_wait:
        try:
            # Check health endpoint
            response = requests.get("http://localhost:8000/healthz", timeout=10)
            if response.status_code == 200:
                health = response.json()
                if health.get("status") in ["healthy", "degraded"]:
                    print(f"Stack ready with status: {health['status']}")
                    return health
                else:
                    print(f"Stack status: {health.get('status', 'unknown')}")
        except requests.exceptions.RequestException as e:
            print(f"Health check failed: {e}")
        
        time.sleep(10)
    
    pytest.fail("Stack failed to become ready within timeout")


@pytest.fixture(scope="session")
def container_info():
    """Get information about running containers"""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=ttrpg", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        return {}
    
    containers = {}
    for line in result.stdout.strip().split('\n'):
        if line:
            parts = line.split('\t')
            if len(parts) >= 3:
                name, status, ports = parts[0], parts[1], parts[2]
                containers[name] = {
                    "status": status,
                    "ports": ports
                }
    
    return containers


@pytest.fixture
def test_database_credentials():
    """Get test database credentials"""
    return {
        "postgres": {
            "host": "localhost",
            "port": 5432,
            "database": "ttrpg_dev",
            "user": "ttrpg_user", 
            "password": "ttrpg_dev_pass"
        },
        "mongodb": {
            "uri": "mongodb://localhost:27017/ttrpg_dev"
        },
        "neo4j": {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "dev_password"
        },
        "redis": {
            "url": "redis://localhost:6379/0"
        }
    }


@pytest.fixture
def api_base_url():
    """Base URL for API testing"""
    return "http://localhost:8000"


@pytest.fixture
def cleanup_test_data():
    """Fixture to cleanup test data after tests"""
    # This runs after the test
    yield
    
    # Cleanup logic here if needed
    # For now, we'll let the tests clean up their own data
    pass


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content for testing uploads"""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000204 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
297
%%EOF"""


@pytest.fixture
def temp_test_files():
    """Create temporary test files for testing"""
    import tempfile
    import shutil
    
    temp_dir = Path(tempfile.mkdtemp())
    
    # Create some test files
    test_files = {
        "sample.txt": "This is a sample text file for testing",
        "sample.pdf": "Fake PDF content for testing",
        "sample.json": '{"test": true, "data": [1, 2, 3]}'
    }
    
    created_files = {}
    for filename, content in test_files.items():
        file_path = temp_dir / filename
        file_path.write_text(content)
        created_files[filename] = file_path
    
    yield created_files
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def isolated_test_environment():
    """Provide an isolated environment for tests that need clean state"""
    # This could be used to backup and restore database state
    # For now, we'll just provide a marker that tests can use
    return {
        "test_id": f"test_{int(time.time())}",
        "timestamp": time.time()
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest for container testing"""
    # Add custom markers
    config.addinivalue_line(
        "markers", "container: mark test as requiring running containers"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    # Mark all tests in this directory as container tests
    for item in items:
        if "container" in str(item.fspath):
            item.add_marker(pytest.mark.container)
            
            # Mark database integration tests
            if "database_integration" in str(item.fspath):
                item.add_marker(pytest.mark.integration)
            
            # Mark scheduler tests as potentially slow
            if "scheduler" in str(item.fspath):
                item.add_marker(pytest.mark.slow)