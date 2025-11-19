import importlib
from pathlib import Path

import pytest

import json

from ingestion.artifacts import load_elements_meta, load_embeddings_artifact
from ingestion.core.job_registry import JobRegistry
from ingestion.core.db.graph_store import get_graph_store, reset_graph_store


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch):
    monkeypatch.setenv("JOB_REGISTRY_BACKEND", "memory")
    monkeypatch.setenv("DICTIONARY_BACKEND", "memory")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("CASSANDRA_BACKEND", "memory")
    monkeypatch.setenv("NEO4J_BACKEND", "memory")
    JobRegistry.reset_global()
    from ingestion.core.db.dictionary import reset_dictionary_store
    from ingestion.core.db.cassandra_store import reset_cassandra_store
    from ingestion.core.embeddings import reset_embedding_provider

    reset_dictionary_store()
    reset_cassandra_store()
    reset_embedding_provider()
    reset_graph_store()
    yield
    JobRegistry.reset_global()
    reset_dictionary_store()
    reset_cassandra_store()
    reset_embedding_provider()
    reset_graph_store()


def test_kickoff_creates_artifacts(tmp_path, monkeypatch):
    transfer_root = tmp_path / "ts"
    monkeypatch.setenv("TRANSFER_STATION_ROOT", str(transfer_root))

    import ingestion.config.settings as settings_module
    settings_module = importlib.reload(settings_module)

    import ingestion.config as config_package
    config_package = importlib.reload(config_package)

    from ingestion.core import job_registry as job_registry_module
    job_registry_module = importlib.reload(job_registry_module)
    globals()["JobRegistry"] = job_registry_module.JobRegistry
    JobRegistry.reset_global()

    import ingestion.workers.unstructured.tasks as unstructured_tasks
    unstructured_tasks = importlib.reload(unstructured_tasks)
    assert str(unstructured_tasks._settings.transfer_root).startswith(str(transfer_root))

    import ingestion.workers.ingestion_engine.tasks as ie_tasks
    ie_tasks = importlib.reload(ie_tasks)

    import ingestion.workers.haystack.tasks as haystack_tasks
    haystack_tasks = importlib.reload(haystack_tasks)

    import ingestion.workers.cassandra_upsert.tasks as cassandra_tasks
    cassandra_tasks = importlib.reload(cassandra_tasks)

    import ingestion.workers.llamaindex.tasks as llamaindex_tasks
    llamaindex_tasks = importlib.reload(llamaindex_tasks)

    import ingestion.workers.graph_upsert.tasks as graph_upsert_tasks
    graph_upsert_tasks = importlib.reload(graph_upsert_tasks)

    import ingestion.core.pipeline as pipeline_module
    pipeline_module = importlib.reload(pipeline_module)

    source_file = transfer_root / "sources" / "sample.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("dummy", encoding="utf-8")

    job_id = pipeline_module.kickoff_ingestion(source_file)

    artifacts_root = transfer_root / "artifacts"
    metadata_file = artifacts_root / job_id / "metadata" / "elements_with_meta.json"
    elements_path = artifacts_root / job_id / "unstructured" / "elements.json"
    embeddings_path = artifacts_root / job_id / "embeddings" / "embeddings.json"
    embeddings_chunks_path = artifacts_root / job_id / "embeddings" / "chunks_with_vectors.json"
    embeddings_manifest = artifacts_root / job_id / "embeddings" / "manifest.json"
    assert elements_path.is_file()
    assert metadata_file.is_file()
    assert embeddings_path.is_file()
    assert embeddings_chunks_path.is_file()
    assert embeddings_manifest.is_file()

    metadata_artifact = load_elements_meta(metadata_file)
    metadata = [
        entry.model_dump() if hasattr(entry, "model_dump") else entry  # type: ignore[attr-defined]
        for entry in metadata_artifact.items
    ]
    embeddings_manifest_payload = json.loads(embeddings_manifest.read_text(encoding="utf-8"))
    assert embeddings_manifest_payload["chunk_count"] == len(metadata)
    assert metadata, "Expected metadata output"
    embeddings_artifact = load_embeddings_artifact(embeddings_chunks_path)
    assert len(embeddings_artifact.chunks) == len(metadata)

    registry = JobRegistry.global_instance()
    record = registry.get(job_id)
    assert record is not None
    assert record.stage in {"dictionary_upsert", "haystack", "cassandra_upsert", "graph_upsert"}
    assert record.expected_count == len(metadata)
    assert record.expected_checksum

    from ingestion.core.db.dictionary import get_dictionary_store
    from ingestion.core.db.cassandra_store import get_cassandra_store

    dictionary_store = get_dictionary_store(settings_module.Settings())
    assert dictionary_store.count_terms(job_id) == len(metadata)

    cassandra_store = get_cassandra_store(settings_module.Settings())
    rows = cassandra_store.fetch_source(job_id)
    assert len(rows) == len(metadata)
    assert all(len(row["embedding"]) == settings_module.Settings().embedding_dimension for row in rows)

    llama_dir = artifacts_root / job_id / "llamaindex"
    llama_nodes = llama_dir / "nodes.json"
    llama_similarity = llama_dir / "similarity.json"
    llama_manifest = llama_dir / "manifest.json"
    llama_ready = llama_dir / "ready.marker"
    assert llama_nodes.is_file()
    assert llama_similarity.is_file()
    assert llama_manifest.is_file()
    assert llama_ready.is_file()
    nodes_payload = json.loads(llama_nodes.read_text(encoding="utf-8"))
    assert len(nodes_payload["nodes"]) == len(metadata)
    similarity_payload = json.loads(llama_similarity.read_text(encoding="utf-8"))
    assert set(similarity_payload["entries"].keys()) == {node["id"] for node in nodes_payload["nodes"]}
    llama_manifest_payload = json.loads(llama_manifest.read_text(encoding="utf-8"))
    assert llama_manifest_payload["chunk_count"] == len(metadata)

    graph_manifest = artifacts_root / job_id / "graph" / "graph_manifest.json"
    graph_ready = artifacts_root / job_id / "graph" / "ready.marker"
    assert graph_manifest.is_file()
    assert graph_ready.is_file()
    manifest_payload = json.loads(graph_manifest.read_text(encoding="utf-8"))
    assert manifest_payload["chunks"] == len(metadata)
    graph_store = get_graph_store(settings_module.Settings())
    document_graph = graph_store.fetch_document(job_id)
    assert document_graph is not None
    assert len(document_graph["chunks"]) == len(metadata)

    status_file = transfer_root / "jobs" / f"{job_id}.status.json"
    assert status_file.is_file()
    status_payload = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_payload["job_id"] == job_id
    assert status_payload["state"] == record.state.value
    assert status_payload["counts"]["dictionary_terms"] is None or status_payload["counts"]["dictionary_terms"] >= 0
