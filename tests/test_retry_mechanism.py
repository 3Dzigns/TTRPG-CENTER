import json
from pathlib import Path
from typing import List
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

from ingestion import pass_a_unstructured as pass_a
from ingestion.pass_a_unstructured import UnstructuredProcessorError


@pytest.fixture(autouse=True)
def configure_ingestion(monkeypatch):
    """Force remote pipeline configuration for deterministic tests."""
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_USE_LOCAL_PIPELINE", False)
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_TIMEOUT", 5)
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_MAX_RETRIES", 3)
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_INITIAL_WAIT", 1)
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_RETRY_BACKOFF", 2.0)
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_CONTAINER_LIMIT", 1)
    monkeypatch.setattr(pass_a.IngestionConfig, "UNSTRUCTURED_API_URLS", ["http://example.com/general/v0/general"])
    monkeypatch.setattr(pass_a, "_container_index", 0)
    monkeypatch.setattr(pass_a, "check_unstructured_health", lambda _: True)


@pytest.fixture
def sample_document(tmp_path):
    doc = tmp_path / "doc.pdf"
    doc.write_text("sample")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    return doc, output_dir


class DummyResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_retry_on_timeout_success_second_attempt(monkeypatch, sample_document):
    doc, out_dir = sample_document
    attempts: List[str] = []

    def fake_post(*args, **kwargs):
        attempts.append("attempt")
        if len(attempts) == 1:
            raise pass_a.requests.Timeout("temporary timeout")
        return DummyResponse([{"type": "Title"}])

    monkeypatch.setattr(pass_a.requests, "post", fake_post)

    result = pass_a.process_document_with_retry(doc, out_dir, max_retries=2)

    assert result["element_count"] == 1
    assert len(attempts) == 2
    assert Path(result["output_file"]).exists()


def test_retry_exhaustion_raises_timeout(monkeypatch, sample_document):
    doc, out_dir = sample_document

    def always_timeout(*args, **kwargs):
        raise pass_a.requests.Timeout("boom")

    monkeypatch.setattr(pass_a.requests, "post", always_timeout)

    with pytest.raises(UnstructuredProcessorError) as excinfo:
        pass_a.process_document_with_retry(doc, out_dir, max_retries=2)

    assert "timeout" in str(excinfo.value).lower()


def test_exponential_backoff_timing(monkeypatch, sample_document):
    doc, out_dir = sample_document
    sleep_calls: List[float] = []

    def fake_post(*args, **kwargs):
        raise pass_a.requests.Timeout("still failing")

    class FakeTime:
        def __init__(self):
            self.current = 0.0

        def sleep(self, seconds):
            sleep_calls.append(seconds)

    fake_time = FakeTime()
    monkeypatch.setattr(pass_a.requests, "post", fake_post)
    monkeypatch.setattr(pass_a.time, "sleep", fake_time.sleep)

    with pytest.raises(UnstructuredProcessorError):
        pass_a.process_document_with_retry(doc, out_dir, max_retries=3)

    assert sleep_calls == [1, 2]  # 1 * 2^0, 1 * 2^1


def test_config_override_applies(monkeypatch, sample_document):
    doc, out_dir = sample_document
    captured_timeouts: List[int] = []

    def fake_post(*args, **kwargs):
        captured_timeouts.append(kwargs["timeout"])
        return DummyResponse([{"type": "Paragraph"}])

    monkeypatch.setattr(pass_a.requests, "post", fake_post)

    result = pass_a.process_document_with_retry(
        doc,
        out_dir,
        timeout=123,
        max_retries=1,
        strategy=pass_a.STRATEGY_TOC,
        max_pages=5,
    )

    assert captured_timeouts == [123]
    manifest = json.loads(Path(result["output_file"]).read_text())
    assert manifest == [{"type": "Paragraph"}]
