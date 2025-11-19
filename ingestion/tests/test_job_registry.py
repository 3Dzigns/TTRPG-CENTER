import pytest

from ingestion.core.job_registry import JobRegistry, JobState, new_record


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch):
    monkeypatch.setenv("JOB_REGISTRY_BACKEND", "memory")
    monkeypatch.setenv("DICTIONARY_BACKEND", "memory")
    JobRegistry.reset_global()
    yield
    JobRegistry.reset_global()


def test_global_instance_shares_state():
    registry_a = JobRegistry.global_instance()
    registry_b = JobRegistry.global_instance()

    job = new_record(
        job_id="job-1",
        source_path="/Transfer_Station/sources/sample.pdf",
        state=JobState.NEW,
        refresh=False,
        stage="test",
    )
    registry_a.upsert(job)

    fetched = registry_b.get("job-1")
    assert fetched is not None
    assert fetched.job_id == "job-1"
    assert fetched.state is JobState.NEW
