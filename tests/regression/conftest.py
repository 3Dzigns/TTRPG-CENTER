"""
Regression test configuration for TTRPG Center.
Golden snapshots and evaluation set tests.
"""

import pytest
from pathlib import Path


# Regression test specific fixtures
@pytest.fixture
def regression_test_config():
    """Configuration specific to regression tests."""
    return {
        "test_type": "regression",
        "timeout": 600,  # 10 minutes max per test
        "parallel_safe": False,
        "external_services": True,
        "snapshot_comparison": True
    }


@pytest.fixture
def golden_snapshots_path(target_environment: str):
    """Path to golden snapshots for regression testing."""
    return Path(__file__).parent / "snapshots" / target_environment


@pytest.fixture
def evaluation_datasets():
    """Evaluation datasets for regression testing."""
    return {
        "query_classification": "tests/regression/data/qic_eval_set.json",
        "retrieval_quality": "tests/regression/data/retrieval_eval_set.json",
        "e2e_workflows": "tests/regression/data/e2e_eval_set.json"
    }


@pytest.fixture
def performance_baselines():
    """Performance baselines for regression testing."""
    return {
        "qic_p95_ms": 150,  # Query Intent Classification p95 latency
        "retrieval_p95_ms": 500,
        "ingestion_chunks_per_sec": 10
    }


# Automatically mark all tests in this directory as regression tests
pytestmark = [pytest.mark.regression, pytest.mark.slow]