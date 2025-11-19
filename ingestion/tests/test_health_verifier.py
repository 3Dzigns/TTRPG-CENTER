import importlib
from pathlib import Path

import pytest

from ingestion.core.job_registry import JobRegistry, JobState
from ingestion.core.db.graph_store import get_graph_store


@pytest.fixture(autouse=True)
def reset_env(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_REGISTRY_BACKEND", "memory")
    monkeypatch.setenv("DICTIONARY_BACKEND", "memory")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("CASSANDRA_BACKEND", "memory")
    monkeypatch.setenv("NEO4J_BACKEND", "memory")
    transfer_root = tmp_path / "ts"
    monkeypatch.setenv("TRANSFER_STATION_ROOT", str(transfer_root))
    JobRegistry.reset_global()
    from ingestion.core.db.dictionary import reset_dictionary_store
    from ingestion.core.db.cassandra_store import reset_cassandra_store
    from ingestion.core.embeddings import reset_embedding_provider
    from ingestion.core.db.graph_store import reset_graph_store

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


def _prepare_pipeline(tmp_path, monkeypatch):
    import ingestion.config.settings as settings_module
    settings_module = importlib.reload(settings_module)

    import ingestion.config as config_package
    config_package = importlib.reload(config_package)

    from ingestion.core import job_registry as job_registry_module
    job_registry_module = importlib.reload(job_registry_module)
    globals()["JobRegistry"] = job_registry_module.JobRegistry
    globals()["JobState"] = job_registry_module.JobState
    JobRegistry.reset_global()

    import ingestion.workers.unstructured.tasks as unstructured_tasks
    unstructured_tasks = importlib.reload(unstructured_tasks)

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

    transfer_root = Path(settings_module.Settings().transfer_root)
    source_file = transfer_root / "sources" / "sample.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("dummy", encoding="utf-8")

    job_id = pipeline_module.kickoff_ingestion(source_file)
    registry = JobRegistry.global_instance()
    return job_id, registry, source_file


def test_health_verifier_enqueues_refresh(tmp_path, monkeypatch):
    job_id, registry, source_file = _prepare_pipeline(tmp_path, monkeypatch)

    registry.update_state(
        job_id,
        state=JobState.COMPLETED,
        stage="test",
        message="Force completion",
        expected_checksum="invalid",
        expected_count=999,
    )

    import ingestion.workers.health_verifier.tasks as hv_tasks
    hv_tasks = importlib.reload(hv_tasks)

    stats = hv_tasks.verify(None)
    assert stats["refresh"] >= 1

    jobs = list(registry.list())
    assert any(j.job_id.startswith(job_id + "-refresh") for j in jobs)


def test_health_verifier_enqueues_removal(tmp_path, monkeypatch):
    job_id, registry, source_file = _prepare_pipeline(tmp_path, monkeypatch)

    source_file.unlink()

    record = registry.get(job_id)
    registry.update_state(
        job_id,
        state=JobState.COMPLETED,
        stage="test",
        message="Force completion",
        expected_checksum=record.expected_checksum,
        expected_count=record.expected_count,
    )

    import ingestion.config.settings as settings_module

    settings_module = importlib.reload(settings_module)
    settings = settings_module.Settings()
    from ingestion.core.db.dictionary import get_dictionary_store
    from ingestion.core.db.cassandra_store import get_cassandra_store

    dictionary_store = get_dictionary_store(settings)
    cassandra_store = get_cassandra_store(settings)
    assert dictionary_store.count_terms(job_id) > 0
    assert cassandra_store.fetch_source(job_id)
    graph_store = get_graph_store(settings)
    assert graph_store.fetch_document(job_id) is not None

    import ingestion.workers.health_verifier.tasks as hv_tasks
    hv_tasks = importlib.reload(hv_tasks)

    stats = hv_tasks.verify(None)
    assert stats["removal"] >= 1

    jobs = list(registry.list())
    removal_job = next(j for j in jobs if j.job_id.startswith(job_id + "-remove"))
    original = registry.get(job_id)
    assert original.state == JobState.REMOVED

    import ingestion.workers.housekeeping.tasks as housekeeping_tasks

    housekeeping_tasks = importlib.reload(housekeeping_tasks)
    result = housekeeping_tasks.remove_source(None, removal_job.job_id, str(source_file))
    assert result == "removal-complete"

    assert dictionary_store.count_terms(job_id) == 0
    assert cassandra_store.fetch_source(job_id) == []
    assert graph_store.fetch_document(job_id) is None
