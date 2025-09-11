#!/usr/bin/env python3
"""
Functional test for FR-003: Log Review & Automatic Bug Bundle Creation.
"""

import json
from pathlib import Path

import pytest

from src_common.log_review import LogReviewService


@pytest.mark.asyncio
async def test_auto_bug_bundle_creation(mock_environment):
    """Write error logs and verify bug bundle + registry are created."""
    env_root: Path = mock_environment  # env/test root
    env = "test"

    logs_dir = env_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    # Produce a couple of error lines across files
    (logs_dir / "bulk.log").write_text(
        "\n".join(
            [
                "2025-09-10 12:00:00 - ttrpg.bulk_ingest - INFO - Start",
                "2025-09-10 12:00:01 - ttrpg.pass_d_vector_enrichment - ERROR - Pass D failed for job job_123: 'text'",
                "2025-09-10 12:00:02 - ttrpg.bulk_ingest - ERROR - 6-pass pipeline failed for Foo.pdf: Pass D failed: 'text'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    svc = LogReviewService(base_dir=Path("."))
    summary = await svc.auto_create_bug_bundles(environment=env, hours=48, max_bundles=3)

    # Validate bug registry updated
    bugs_file = env_root / "data" / "bug_bundles.json"
    assert bugs_file.exists()
    data = json.loads(bugs_file.read_text(encoding="utf-8"))
    assert data.get("environment") == env
    assert len(data.get("bugs", [])) >= 1
    titles = [b.get("title", "") for b in data.get("bugs", [])]
    assert any(t.startswith("Auto: ") for t in titles)

    # Validate artifact directory exists
    # Use the last bug's ID
    last_bug = data["bugs"][-1]
    bug_dir = env_root / "artifacts" / "bug_bundles" / last_bug["bug_id"]
    assert (bug_dir / "manifest.json").exists()
    assert (bug_dir / "error_snippets.json").exists()
