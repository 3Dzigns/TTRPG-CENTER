#!/usr/bin/env python3
"""
Unit tests for FR-003 Log Review parser and aggregation.
"""

import json
import time
from pathlib import Path

from src_common.log_review import LogReviewService


def write_lines(p: Path, lines):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_scan_logs_parses_console_format(tmp_path: Path):
    env = "test"
    log = tmp_path / "env" / env / "logs" / "app.log"
    lines = [
        "2025-09-10 12:00:00 - ttrpg.module - INFO - Starting up",
        "2025-09-10 12:00:01 - ttrpg.pass_d_vector_enrichment - ERROR - Pass D failed for job job_12345: 'text'",
        "2025-09-10 12:00:02 - ttrpg.module - WARNING - Minor issue",
    ]
    write_lines(log, lines)

    svc = LogReviewService(base_dir=tmp_path)
    events = svc.scan_logs(env)
    assert len(events) == 1
    evt = events[0]
    assert evt.level == "ERROR"
    assert "pass_d" in evt.name.lower()
    assert "failed" in evt.message.lower()


def test_scan_logs_parses_json_format(tmp_path: Path):
    env = "test"
    log = tmp_path / "env" / env / "logs" / "json.log"
    line = {
        "timestamp": time.time(),
        "name": "ttrpg.bulk_ingest",
        "level": "ERROR",
        "message": "6-pass pipeline failed for X: reason",
    }
    write_lines(log, [json.dumps(line)])

    svc = LogReviewService(base_dir=tmp_path)
    events = svc.scan_logs(env)
    assert len(events) == 1
    assert events[0].name == "ttrpg.bulk_ingest"
    assert events[0].level == "ERROR"


def test_aggregate_candidates_groups_by_signature(tmp_path: Path):
    env = "test"
    log = tmp_path / "env" / env / "logs" / "app.log"
    lines = [
        "2025-09-10 12:00:01 - ttrpg.pass_d_vector_enrichment - ERROR - Pass D failed for job job_111: 'text'",
        "2025-09-10 12:00:02 - ttrpg.pass_d_vector_enrichment - ERROR - Pass D failed for job job_222: 'text'",
    ]
    write_lines(log, lines)

    svc = LogReviewService(base_dir=tmp_path)
    events = svc.scan_logs(env)
    cands = svc.aggregate_candidates(events)
    assert len(cands) == 1
    assert cands[0].count == 2
    assert cands[0].severity.name in ("HIGH", "CRITICAL")
