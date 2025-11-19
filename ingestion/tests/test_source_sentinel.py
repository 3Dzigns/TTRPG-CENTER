import importlib
from pathlib import Path

import pytest

from ingestion.core.job_registry import JobRegistry


@pytest.fixture(autouse=True)
def configure_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("JOB_REGISTRY_BACKEND", "memory")
    monkeypatch.setenv("DICTIONARY_BACKEND", "memory")
    transfer_root = tmp_path / "ts"
    monkeypatch.setenv("TRANSFER_STATION_ROOT", str(transfer_root))
    JobRegistry.reset_global()
    yield
    JobRegistry.reset_global()


def test_source_scan_queues_job(tmp_path, monkeypatch):
    import ingestion.config.settings as settings_module
    settings_module = importlib.reload(settings_module)

    import ingestion.config as config_package
    importlib.reload(config_package)

    from ingestion.core import job_registry as job_registry_module
    job_registry_module = importlib.reload(job_registry_module)
    globals()["JobRegistry"] = job_registry_module.JobRegistry
    JobRegistry.reset_global()

    from ingestion.workers import ingestion_engine
    importlib.reload(ingestion_engine.tasks)

    from ingestion.workers.source_sentinel import tasks as sentinel_tasks
    sentinel_tasks = importlib.reload(sentinel_tasks)

    queued = []

    class DummyDispatcher:
        @staticmethod
        def delay(job_id: str) -> None:
            queued.append(job_id)

    monkeypatch.setattr(sentinel_tasks, "orchestrate_passes", DummyDispatcher)

    transfer_root = Path(settings_module.Settings().transfer_root)
    source_file = transfer_root / "sources" / "sample.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("dummy", encoding="utf-8")

    sentinel_tasks.source_scan(None)

    registry = JobRegistry.global_instance()
    jobs = list(registry.list())
    assert jobs, "Expected job to be registered"
    job = jobs[0]
    assert job.source_path == str(source_file)
    assert job.state is job_registry_module.JobState.QUEUED
    assert queued, "Expected orchestration to be queued"
