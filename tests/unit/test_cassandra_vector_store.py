import json
from datetime import datetime

import pytest

from src_common.pass_d_vector_enrichment import SourceMetadata, VectorEnricher, VectorRecord
from src_common.vector_store.cassandra import CassandraVectorStore


def _make_store(env: str = "dev") -> CassandraVectorStore:
    store = object.__new__(CassandraVectorStore)
    store.env = env
    return store


def test_normalise_document_serializes_metadata_with_doc_id():
    store = _make_store()
    timestamp = datetime(2025, 10, 4, 12, 30, 0)
    document = {
        "chunk_id": "chunk-001",
        "content": "Vector content",
        "stage": "pass_d",
        "metadata": {
            "source_hash": "source-abc",
            "environment": "dev",
            "doc_id": "job_123",
            "custom_dt": timestamp,
        },
        "source_file": "Cyberpunk.pdf",
        "embedding": [0.1, 0.2, 0.3],
        "embedding_model": "text-embedding-3-small",
        "vector_id": "vec-123",
        "updated_at": timestamp,
    }

    params = store._normalise_document(document)

    assert params[0] == "source-abc"
    assert params[1] == "dev"
    assert params[2] == "chunk-001"
    assert params[3] == "pass_d"
    payload = params[5]
    payload_obj = json.loads(payload)
    assert payload_obj["metadata"]["doc_id"] == "job_123"
    assert payload_obj["metadata"]["custom_dt"] == timestamp.isoformat()
    assert payload_obj["doc_id"] == "job_123"

    embedding_blob = params[7]
    assert isinstance(embedding_blob, (bytes, bytearray))
    assert len(embedding_blob) == len(document["embedding"]) * 4

    updated_at = params[10]
    loaded_at = params[11]
    assert updated_at == timestamp
    assert loaded_at == timestamp


def test_normalise_document_missing_doc_id_raises():
    store = _make_store()
    document = {
        "chunk_id": "chunk-002",
        "content": "Missing doc id",
        "metadata": {
            "source_hash": "source-xyz",
            "environment": "dev",
        },
        "source_file": "book.pdf",
    }

    with pytest.raises(ValueError, match="doc_id"):
        store._normalise_document(document)


def test_helpers_exposed_on_cassandra_vector_store():
    assert hasattr(CassandraVectorStore, "_json_default")
    iso = CassandraVectorStore._json_default(datetime(2025, 10, 4, 11, 40, 0))
    assert iso == "2025-10-04T11:40:00"

    chunk_id = CassandraVectorStore._fallback_chunk_id()
    assert isinstance(chunk_id, str)
    assert chunk_id.startswith("chunk_")


def test_build_vector_documents_includes_identity_and_metadata():
    enricher = object.__new__(VectorEnricher)
    enve = "dev"
    enricher.job_id = "job_123"
    enricher.env = enve

    vector = VectorRecord(
        doc_id="job_123",
        part_id="part_01",
        section_id="section_1",
        chunk_id="chunk_010",
        embedding_model="text-embedding-3-small",
        embedding=[0.5, 0.6],
        checksum_sha256="abc123",
        metadata={"existing": "meta"},
        content="Sample chunk",
        chunk_metadata={"page": 5},
    )
    source = SourceMetadata(
        source_hash="source-hash",
        source_file="Cyberpunk.pdf",
        environment=enve,
        job_id="job_123",
    )

    documents = enricher._build_vector_documents([vector], source)
    assert len(documents) == 1
    doc = documents[0]

    assert doc["doc_id"] == "job_123"
    assert doc["metadata"]["doc_id"] == "job_123"
    assert doc["metadata"]["part_id"] == "part_01"
    assert doc["metadata"]["page"] == "5"
    assert doc["metadata"]["source_hash"] == "source-hash"
    assert doc["metadata"]["environment"] == enve
    assert doc["metadata"]["job_id"] == "job_123"
    assert doc["environment"] == enve
    assert doc["source_hash"] == "source-hash"

    assert vector.metadata == {"existing": "meta"}

    # Original metadata should remain unchanged
    assert "job_id" not in vector.metadata
