"""
Security test configuration for TTRPG Center.
SAST/DAST and vulnerability scanning tests.
"""

import pytest


# Security test specific fixtures
@pytest.fixture
def security_test_config():
    """Configuration specific to security tests."""
    return {
        "test_type": "security",
        "timeout": 180,  # 3 minutes max per test
        "parallel_safe": True,
        "external_services": False,
        "sensitive_data": True
    }


@pytest.fixture
def security_scanner():
    """Security scanning tools fixture."""
    # This could integrate with tools like Bandit, Safety, etc.
    return {
        "bandit_available": True,
        "safety_available": True,
        "semgrep_available": False
    }


@pytest.fixture
def vulnerability_database():
    """Mock vulnerability database for testing."""
    return {
        "known_vulnerabilities": [],
        "severity_levels": ["low", "medium", "high", "critical"]
    }


# Automatically mark all tests in this directory as security tests
pytestmark = pytest.mark.security