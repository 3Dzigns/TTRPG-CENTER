"""
Functional test configuration for TTRPG Center.
API and UI workflow tests.
"""

import pytest


# Functional test specific fixtures
@pytest.fixture
def functional_test_config():
    """Configuration specific to functional tests."""
    return {
        "test_type": "functional",
        "timeout": 120,  # 2 minutes max per test
        "parallel_safe": False,
        "external_services": True
    }


@pytest.fixture
def api_client(test_environment_config):
    """HTTP client for API testing."""
    import httpx

    base_url = test_environment_config["admin_api_url"]
    return httpx.Client(base_url=base_url, timeout=30.0)


@pytest.fixture
def integration_services():
    """Fixture to ensure services are available for functional tests."""
    # This can check that required services are running
    # and skip tests if they're not available
    pass


# Automatically mark all tests in this directory as functional tests
pytestmark = pytest.mark.functional