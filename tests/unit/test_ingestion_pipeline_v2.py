"""Unit tests for MVP v2 ingestion pipeline passes."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from pypdf import PdfWriter

import src_common.pass_b_logical_splitter as pass_b
import src_common.pass_c_extraction as pass_c
import src_common.pass_d_vector_enrichment as pass_d
import src_common.pass_e_graph_builder as pass_e
import src_common.pass_f_finalizer as pass_f
import src_common.pass_g_hgrn_consistency as pass_g
from services.ingest.pipeline import IngestionPipeline


class DummyConfigManager:
    """Minimal configuration stub for unit tests."""

    def __init__(self) -> None:
        self._threshold_mb = int(os.environ.get("PASS_B_SPLIT_THRESHOLD_MB", "10"))
        self._embed_dim = int(os.environ.get("PASS_D_EMBED_DIM", "8"))
        self._embed_model = os.environ.get("PASS_D_EMBEDDING_MODEL", "test-embedding")

    def get_processing_config(self) -> dict[str, int | bool]:
        return {
            "pass_b_split_threshold_mb": self._threshold_mb,
            "max_file_size_mb": 100,
            "max_concurrent_jobs": 3,
            "processing_timeout_seconds": 1800,
            "parallel_processing_enabled": True,
        }

    def get_config(self, key: str, default=None):
        overrides = {
            "PASS_D_EMBED_DIM": str(self._embed_dim),
            "PASS_D_EMBEDDING_MODEL": self._embed_model,
        }
        if key in overrides:
            return overrides[key]
        return os.environ.get(key, default)


@pytest.fixture(autouse=True)
def _configure_test_env(monkeypatch):
    monkeypatch.setenv("TARGET_ENV", "dev")
    monkeypatch.setenv("ALLOW_UNSTRUCTURED_FALLBACK", "true")
    monkeypatch.setenv("PASS_D_EMBED_DIM", "8")
    monkeypatch.setenv("PASS_D_EMBEDDING_MODEL", "unit-test-model")
    monkeypatch.setenv("PASS_B_SPLIT_THRESHOLD_MB", "1")

    monkeypatch.setattr(pass_b, "ConfigManager", DummyConfigManager)
    monkeypatch.setattr(pass_c, "ConfigManager", DummyConfigManager)
    monkeypatch.setattr(pass_d, "ConfigManager", DummyConfigManager)
    monkeypatch.setattr(pass_e, "ConfigManager", DummyConfigManager)
    monkeypatch.setattr(pass_f, "ConfigManager", DummyConfigManager, raising=False)

    Path("env/dev/artifacts").mkdir(parents=True, exist_ok=True)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    return pdf_path


@pytest.fixture
def job_dir(tmp_path: Path) -> Path:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    return job_dir


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def inject_dummy_reader(monkeypatch, text: str = "Sample text") -> None:
    class _DummyPage:
        def extract_text(self):
            return text

    class _DummyReader:
        def __init__(self, _):
            self.pages = [_DummyPage()]

    monkeypatch.setattr(pass_c, "PdfReader", _DummyReader)


def test_pass_b_respects_threshold(sample_pdf: Path, job_dir: Path):
    job_id = "job-b-threshold"

    with sample_pdf.open("ab") as handle:
        handle.write(b"0" * (2 * 1024 * 1024))

    result = pass_b.process_pass_b(sample_pdf, job_dir, job_id, "dev")

    assert result.success is True
    assert result.split_performed is True
    split_index = job_dir / "pass_b" / "split_index.json"
    data = read_json(split_index)
    assert data["split_performed"] is True
    assert data["parts"]

    os.environ["PASS_B_SPLIT_THRESHOLD_MB"] = "100"
    result_no_split = pass_b.process_pass_b(sample_pdf, job_dir, job_id + "-nosplit", "dev")
    assert result_no_split.split_performed is False


def test_pass_c_uses_fallback(sample_pdf: Path, job_dir: Path, monkeypatch):
    job_id = "job-pass-c"
    inject_dummy_reader(monkeypatch, text="Chunk text")

    result = pass_c.process_pass_c(sample_pdf, job_dir, job_id, "dev")

    assert result.success is True
    assert result.fallback_used is True
    assert result.chunks_extracted > 0

    chunks_path = job_dir / "pass_c" / f"{job_id}_pass_c_chunks.jsonl"
    assert chunks_path.exists()


def test_pass_d_generates_vectors(sample_pdf: Path, job_dir: Path, monkeypatch):
    job_id = "job-pass-d"
    inject_dummy_reader(monkeypatch, text="Vector text")

    pass_c.process_pass_c(sample_pdf, job_dir, job_id, "dev")
    result = pass_d.process_pass_d(job_dir, job_id, "dev")

    assert result.success is True
    assert result.fallback_used is True

    vectors_path = job_dir / "pass_d" / f"{job_id}_pass_d_vectors.jsonl"
    with vectors_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline()
    payload = json.loads(first_line)
    assert len(payload["embedding"]) == 8


def test_pass_e_builds_graph(sample_pdf: Path, job_dir: Path, monkeypatch):
    job_id = "job-pass-e"
    inject_dummy_reader(monkeypatch, text="Graph text")

    pass_c.process_pass_c(sample_pdf, job_dir, job_id, "dev")
    pass_d.process_pass_d(job_dir, job_id, "dev")
    result = pass_e.process_pass_e(job_dir, job_id, "dev")

    assert result.success is True
    assert (job_dir / "pass_e" / "graph.json").exists()
    assert (job_dir / "pass_e" / "graph_summary.json").exists()


def test_pass_f_finalizes(sample_pdf: Path, job_dir: Path, monkeypatch):
    job_id = "job-pass-f"
    inject_dummy_reader(monkeypatch, text="Finalize text")

    pass_c.process_pass_c(sample_pdf, job_dir, job_id, "dev")
    pass_d.process_pass_d(job_dir, job_id, "dev")
    pass_e.process_pass_e(job_dir, job_id, "dev")
    result = pass_f.process_pass_f(job_dir, job_id, "dev")

    assert result.success is True
    assert (job_dir / "pass_f" / "manifest.snapshot.json").exists()


def test_pass_g_detects_issues(sample_pdf: Path, job_dir: Path, monkeypatch):
    job_id = "job-pass-g"
    inject_dummy_reader(monkeypatch, text="Graph text")

    pass_c.process_pass_c(sample_pdf, job_dir, job_id, "dev")
    pass_d.process_pass_d(job_dir, job_id, "dev")
    pass_e.process_pass_e(job_dir, job_id, "dev")
    result = pass_g.run_hgrn_consistency_check(job_dir, "dev")

    assert result.success is True
    assert result.issues_found >= 1


@pytest.mark.parametrize("fixture_name", ["born_digital", "scanned"])
def test_pipeline_golden_expectations(fixture_name: str):
    pdf_path = Path("tests/regression/golden_masters/pdfs") / f"{fixture_name}.pdf"
    expected_path = Path("tests/regression/golden_masters/expected") / f"{fixture_name}_expected.json"
    expected = read_json(expected_path)

    env_root = Path("env/dev")
    job_id = f"golden-{fixture_name}"
    job_dir = env_root / "artifacts" / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)

    pipeline = IngestionPipeline(job_id, pdf_path, env_root)
    manifest = asyncio_run(pipeline.execute())

    for pass_name in expected["required_passes"]:
        assert manifest["passes"][pass_name]["status"] == "completed"

    artifact_paths = [item["path"] for item in manifest["artifacts"]]
    for prefix in expected["required_artifact_prefixes"]:
        assert any(path.startswith(prefix) for path in artifact_paths), f"Missing artifact prefix {prefix}"

    shutil.rmtree(job_dir, ignore_errors=True)


def test_pipeline_handles_duplicate_preflight(sample_pdf: Path, monkeypatch):
    class DuplicateResult:
        def __init__(self) -> None:
            self.should_skip = True
            self.reason = "duplicate"
            self.file_sha = "deadbeef"
            self.page_count = 1
            self.existing_job_id = "existing"

    env_root = Path("env/dev")
    source_copy = env_root / "code" / sample_pdf.name
    source_copy.parent.mkdir(parents=True, exist_ok=True)
    source_copy.write_bytes(sample_pdf.read_bytes())

    monkeypatch.setattr(
        "services.ingest.pipeline.run_preflight_checks",
        lambda _path: DuplicateResult(),
    )

    pipeline = IngestionPipeline("job-duplicate", source_copy, env_root)
    manifest = asyncio_run(pipeline.execute())

    assert manifest["status"] == "skipped"
    assert manifest.get("skip_reason") == "duplicate"
    assert manifest["passes"]["pass_0_preflight"]["status"] == "skipped"


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)

