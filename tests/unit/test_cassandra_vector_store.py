import json
from datetime import datetime

import pytest

from src_common.pass_d_vector_enrichment import SourceMetadata, VectorEnricher, VectorRecord
from src_common.vector_store.cassandra import CassandraVectorStore, _json_default_serializer


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


def test_json_default_serializer_datetime():
    """Test that _json_default_serializer correctly handles datetime objects"""
    dt = datetime(2025, 10, 4, 11, 40, 0)
    result = _json_default_serializer(dt)
    assert result == "2025-10-04T11:40:00"
    assert isinstance(result, str)


def test_json_default_serializer_with_microseconds():
    """Test datetime serialization includes microseconds in ISO format"""
    dt = datetime(2025, 10, 4, 11, 40, 30, 123456)
    result = _json_default_serializer(dt)
    assert result == "2025-10-04T11:40:30.123456"
    assert "T" in result  # ISO 8601 format


def test_json_default_serializer_fallback():
    """Test that non-datetime objects fallback to str() conversion"""
    # Integer
    assert _json_default_serializer(42) == "42"

    # Float
    assert _json_default_serializer(3.14) == "3.14"

    # Dict
    result = _json_default_serializer({"key": "value"})
    assert "key" in result
    assert isinstance(result, str)

    # List
    result = _json_default_serializer([1, 2, 3])
    assert "[" in result


def test_helpers_exposed_on_cassandra_vector_store():
    """Test that helper methods are available on CassandraVectorStore"""
    chunk_id = CassandraVectorStore._fallback_chunk_id()
    assert isinstance(chunk_id, str)
    assert chunk_id.startswith("chunk_")


def test_normalise_document_no_attribute_error_on_datetime():
    """
    Critical test for BUG-035: Verify that normalizing a document with datetime
    in metadata doesn't raise AttributeError on _json_default
    """
    store = _make_store()
    timestamp = datetime.utcnow()

    document = {
        "doc_id": "test_doc_123",
        "chunk_id": "chunk_456",
        "content": "Test content with datetime",
        "metadata": {
            "source_hash": "abc123",
            "environment": "dev",
            "doc_id": "test_doc_123",
            "created_at": timestamp,  # This triggers JSON serialization
            "processed_at": datetime(2025, 10, 5, 12, 0, 0),
        },
        "embedding": [0.1, 0.2, 0.3],
        "source_file": "test.pdf",
        "environment": "dev",
    }

    # This should NOT raise AttributeError: 'CassandraVectorStore' object has no attribute '_json_default'
    result = store._normalise_document(document)

    # Verify the result is valid
    assert result is not None
    assert len(result) == 12  # Tuple with 12 elements

    # Verify JSON payload was serialized correctly
    payload = result[5]  # payload is at index 5
    payload_obj = json.loads(payload)
    assert payload_obj["metadata"]["created_at"] == timestamp.isoformat()
    assert payload_obj["metadata"]["processed_at"] == "2025-10-05T12:00:00"


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
