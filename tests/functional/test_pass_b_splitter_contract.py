"""Contract tests for Pass B logical splitter behavior."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest


@pytest.fixture()
def pass_b_contract_setup(monkeypatch, tmp_path):
    """Prepare a LogicalSplitter instance with lightweight stubs."""
    from src_common import pass_b_logical_splitter as module

    class DummyConfigManager:
        def get_processing_config(self) -> Dict[str, int]:
            return {
                "pass_b_split_threshold_mb": 100,
                "pass_b_max_pages_per_part": 8,
                "pass_b_min_pages_per_part": 1,
                "pass_b_target_pages_per_part": 4,
            }

    class DummyPdfReader:  # pragma: no cover - simple stub
        def __init__(self, _path: str) -> None:
            self.pages = [object() for _ in range(6)]

    class DummyPdfWriter:  # pragma: no cover - simple stub
        def __init__(self) -> None:
            self._pages: List[Any] = []

        def add_page(self, page: Any) -> None:
            self._pages.append(page)

        def write(self, handle) -> None:
            handle.write(b"FAKE-PDF-PART")

    def fake_log_to_job(*_args, **_kwargs) -> None:  # pragma: no cover - stub
        return None

    def fake_pass_start(*_args, **_kwargs) -> None:  # pragma: no cover - stub
        return None

    def fake_pass_complete(*_args, **_kwargs) -> None:  # pragma: no cover - stub
        return None

    def fake_heartbeat(
        _processed: int,
        _total: int,
        _label: str,
        _log_file,
        _phase: str,
        last_logged: float,
        *_args,
        **_kwargs,
    ) -> float:  # pragma: no cover - stub
        return last_logged

    monkeypatch.setattr(module, "ConfigManager", lambda: DummyConfigManager())
    monkeypatch.setattr(module, "PdfReader", DummyPdfReader)
    monkeypatch.setattr(module, "PdfWriter", DummyPdfWriter)
    monkeypatch.setattr(module, "log_to_job", fake_log_to_job)
    monkeypatch.setattr(module, "log_pass_start", fake_pass_start)
    monkeypatch.setattr(module, "log_pass_complete", fake_pass_complete)
    monkeypatch.setattr(module, "log_heartbeat", fake_heartbeat)

    catalog = [
        {"section_id": "chapter-1", "title": "Chapter 1", "page_start": 1, "page_end": 3, "level": 1},
        {"section_id": "chapter-2", "title": "Chapter 2", "page_start": 4, "page_end": 6, "level": 1},
    ]

    monkeypatch.setattr(
        module.LogicalSplitter,
        "_load_toc_entries",
        lambda self, _job_dir, _total_pages: catalog,
        raising=False,
    )

    monkeypatch.setattr(
        module.LogicalSplitter,
        "_log_job",
        lambda self, _message: None,
        raising=False,
    )

    job_dir = tmp_path / "job"
    job_dir.mkdir()

    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-FAKE")

    splitter = module.LogicalSplitter(job_id="job-test", env="dev", job_log_file=job_dir / "job.log")
    return module, splitter, pdf_path, job_dir


def test_pass_b_lightweight_plan(pass_b_contract_setup):
    module, splitter, pdf_path, job_dir = pass_b_contract_setup
    result = splitter.process(pdf_path, job_dir, lightweight=True)

    assert result.split_performed is True
    assert result.parts, "Expected at least one part in Pass B result"
    assert all(part.page_start <= part.page_end for part in result.parts)

    assert result.split_plan_path, "Split plan path should be recorded"
    plan_file = job_dir / result.split_plan_path
    assert plan_file.exists(), "Split plan artifact should be created"

    plan_data = json.loads(plan_file.read_text())
    assert plan_data["parts"], "Split plan should list the generated parts"

    parts_jsonl = job_dir / "pass_b" / f"{splitter.job_id}_passB.parts.jsonl"
    assert parts_jsonl.exists(), "JSONL summary should be generated"

    artifact_paths = {Path(artifact).as_posix() for artifact in result.artifacts}
    assert any(path.startswith("pass_b/") for path in artifact_paths)

def test_pass_b_toc_overflow_fallback(pass_b_contract_setup, monkeypatch, tmp_path):
    module, splitter, pdf_path, _ = pass_b_contract_setup

    large_catalog = [
        {
            "section_id": f"section-{i}",
            "title": f"Section {i}",
            "page_start": i,
            "page_end": i,
            "level": 1,
        }
        for i in range(1, 401)
    ]

    monkeypatch.setattr(
        module.LogicalSplitter,
        "_load_toc_entries",
        lambda self, _job_dir, _total_pages: large_catalog,
        raising=False,
    )

    overflow_dir = tmp_path / "overflow_job"
    overflow_dir.mkdir()

    overflow_splitter = module.LogicalSplitter(
        job_id="job-overflow",
        env="dev",
        job_log_file=overflow_dir / "job.log",
    )

    result = overflow_splitter.process(pdf_path, overflow_dir)

    assert len(result.parts) < len(large_catalog)
    assert result.split_performed is True
    plan_file = overflow_dir / result.split_plan_path
    assert plan_file.exists()


def test_pass_b_deduplication_contract(pass_b_contract_setup, monkeypatch, tmp_path):
    """Verify Pass B deduplicates identical page ranges and reports metrics.

    NOTE: DummyPdfWriter generates identical content (b"FAKE-PDF-PART") for all parts,
    so all parts will have the same checksum. This tests that deduplication works when
    multiple sections map to identical PDF content.
    """
    module, splitter, pdf_path, _ = pass_b_contract_setup

    # Create catalog with multiple sections (will all generate identical PDFs in test)
    duplicate_catalog = [
        {"section_id": "intro-1", "title": "Introduction", "page_start": 1, "page_end": 2, "level": 1},
        {"section_id": "intro-2", "title": "Introduction Copy", "page_start": 1, "page_end": 2, "level": 1},
        {"section_id": "chapter-1", "title": "Chapter 1", "page_start": 3, "page_end": 4, "level": 1},
        {"section_id": "chapter-1-dup", "title": "Chapter 1 Duplicate", "page_start": 3, "page_end": 4, "level": 1},
        {"section_id": "chapter-2", "title": "Chapter 2", "page_start": 5, "page_end": 6, "level": 1},
    ]

    monkeypatch.setattr(
        module.LogicalSplitter,
        "_load_toc_entries",
        lambda self, _job_dir, _total_pages: duplicate_catalog,
        raising=False,
    )

    dedupe_dir = tmp_path / "dedupe_job"
    dedupe_dir.mkdir()

    dedupe_splitter = module.LogicalSplitter(
        job_id="job-dedupe",
        env="dev",
        job_log_file=dedupe_dir / "job.log",
    )

    result = dedupe_splitter.process(pdf_path, dedupe_dir)

    # With DummyPdfWriter, all parts have identical content, so only 1 unique part is kept
    assert len(result.parts) == 1, f"Expected 1 unique part (dummy PDF), got {len(result.parts)}"

    # Verify split_index.json contains skipped_duplicates
    split_index_path = dedupe_dir / "pass_b" / "split_index.json"
    assert split_index_path.exists(), "split_index.json should exist"

    split_index_data = json.loads(split_index_path.read_text())
    assert "skipped_duplicates" in split_index_data, "split_index should track skipped duplicates"

    skipped = split_index_data["skipped_duplicates"]
    assert len(skipped) == 4, f"Expected 4 skipped duplicates, got {len(skipped)}"

    # Verify each skipped duplicate has required fields
    for dup in skipped:
        assert "part_id" in dup
        assert "duplicates_of" in dup
        assert "checksum_sha256" in dup
        assert "section_id" in dup
        assert "page_start" in dup
        assert "page_end" in dup
        assert dup["duplicates_of"] == "job-dedupe-part-01"  # All duplicates point to first part

    # Verify split_summary.json contains deduplication metrics
    summary_path = dedupe_dir / "pass_b" / "split_summary.json"
    assert summary_path.exists(), "split_summary.json should exist"

    summary_data = json.loads(summary_path.read_text())
    assert "deduplication" in summary_data, "Summary should include deduplication stats"

    dedupe_stats = summary_data["deduplication"]
    assert dedupe_stats["total_parts_generated"] == 5
    assert dedupe_stats["unique_parts"] == 1
    assert dedupe_stats["duplicate_parts_skipped"] == 4
    assert dedupe_stats["deduplication_rate_percent"] == 80.0  # 4/5 * 100

    # Verify duplicate PDF files were deleted (should only have 1 PDF)
    parts_dir = dedupe_dir / "pass_b" / "parts"
    pdf_files = list(parts_dir.glob("*.pdf"))
    assert len(pdf_files) == 1, f"Expected 1 PDF file after deduplication, found {len(pdf_files)}"
