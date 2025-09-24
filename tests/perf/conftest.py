"""
Performance test configuration for TTRPG Center.
Load testing and benchmarking tests.
"""

import pytest
from pathlib import Path


# Performance test specific fixtures
@pytest.fixture
def perf_test_config():
    """Configuration specific to performance tests."""
    return {
        "test_type": "perf",
        "timeout": 1800,  # 30 minutes max per test
        "parallel_safe": False,
        "external_services": True,
        "load_generation": True
    }


@pytest.fixture
def load_test_scenarios():
    """Load testing scenarios configuration."""
    return {
        "light_load": {
            "concurrent_users": 10,
            "duration_seconds": 60,
            "ramp_up_seconds": 10
        },
        "normal_load": {
            "concurrent_users": 50,
            "duration_seconds": 300,
            "ramp_up_seconds": 30
        },
        "stress_load": {
            "concurrent_users": 200,
            "duration_seconds": 600,
            "ramp_up_seconds": 60
        }
    }


@pytest.fixture
def performance_thresholds():
    """Performance thresholds for testing."""
    return {
        "qic_p95_ms": 150,
        "qic_p99_ms": 300,
        "retrieval_p95_ms": 500,
        "retrieval_p99_ms": 1000,
        "ingestion_throughput_docs_per_min": 60,
        "cpu_usage_max_percent": 80,
        "memory_usage_max_mb": 2048
    }


@pytest.fixture
def benchmark_results_path(target_environment: str):
    """Path to store benchmark results."""
    results_dir = Path(__file__).parent / "results" / target_environment
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


# Automatically mark all tests in this directory as performance tests
pytestmark = [pytest.mark.perf, pytest.mark.slow]