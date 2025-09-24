"""
Unit test configuration for TTRPG Center.
Fast, isolated component tests.
"""

import pytest


# Unit test specific fixtures
@pytest.fixture
def unit_test_config():
    """Configuration specific to unit tests."""
    return {
        "test_type": "unit",
        "timeout": 30,  # 30 seconds max per test
        "parallel_safe": True,
        "external_services": False
    }


@pytest.fixture
def mock_all_external():
    """Mock all external dependencies for unit tests."""
    # This fixture can be used to automatically mock external services
    # like databases, APIs, file systems, etc.
    pass


# Automatically mark all tests in this directory as unit tests
pytestmark = pytest.mark.unit