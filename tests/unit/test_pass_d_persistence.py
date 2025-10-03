import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src_common.pass_d_vector_enrichment import VectorEnricher, VectorRecord


def _write_pass_a_manifest(job_dir: Path, job_id: str, source_hash: str = "hash123", source_file: str = "doc.pdf", environment: str = "dev") -> None:
    pass_a_dir = job_dir / "pass_a"
    pass_a_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = pass_a_dir / f"{job_id}_pass_a_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "source_file": source_file,
                "environment": environment,
                "source_info": {"source_hash": source_hash},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _vector_record(job_id: str) -> VectorRecord:
    return VectorRecord(
        doc_id=job_id,
        part_id="part-1",
        section_id="section-1",
        chunk_id="chunk-1",
        embedding_model="test-model",
        embedding=[0.1, 0.2, 0.3],
        checksum_sha256="checksum123",
        metadata={"page_number": "1"},
        content="Sample chunk text",
        chunk_metadata={"chunk_id": "chunk-1", "doc_id": job_id, "page_number": 1},
    )


@pytest.fixture
def mock_vector_store(monkeypatch):
    store = Mock()
    store.upsert_documents.side_effect = lambda docs: len(docs)
    store.count_documents_for_source.return_value = 1
    store.close = Mock()
    monkeypatch.setattr("src_common.pass_d_vector_enrichment.make_vector_store", lambda env: store)
    return store


def test_persist_vectors_success(tmp_path, mock_vector_store):
    job_id = "job123"
    job_dir = tmp_path / job_id
    job_dir.mkdir()
    _write_pass_a_manifest(job_dir, job_id)

    enricher = VectorEnricher(job_id=job_id, env="dev")

    rows = enricher._persist_vectors(job_dir, [_vector_record(job_id)])

    assert rows == 1
    mock_vector_store.upsert_documents.assert_called_once()
    docs = mock_vector_store.upsert_documents.call_args[0][0]
    assert docs[0]["source_hash"] == "hash123"
    assert docs[0]["environment"] == "dev"
    assert docs[0]["stage"] == "pass_d"
    mock_vector_store.count_documents_for_source.assert_called_once_with("hash123", "dev")
    mock_vector_store.close.assert_called_once()


def test_persist_vectors_verification_failure(tmp_path, monkeypatch):
    job_id = "job123"
    job_dir = tmp_path / job_id
    job_dir.mkdir()
    _write_pass_a_manifest(job_dir, job_id)

    store = Mock()
    store.upsert_documents.side_effect = lambda docs: len(docs)
    store.count_documents_for_source.return_value = 0
    store.close = Mock()
    monkeypatch.setattr("src_common.pass_d_vector_enrichment.make_vector_store", lambda env: store)

    enricher = VectorEnricher(job_id=job_id, env="dev")

    with pytest.raises(RuntimeError):
        enricher._persist_vectors(job_dir, [_vector_record(job_id)])

    store.count_documents_for_source.assert_called_once_with("hash123", "dev")
