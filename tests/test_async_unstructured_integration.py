import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

from ingestion import submit_unstructured_job
from ingestion import wait_for_job
from ingestion.wait_for_job import (
    check_job_status,
    is_job_complete,
    is_job_failed,
    wait_for_completion,
    JobFailedError,
    JobTimeoutError,
)


@pytest.fixture
def temp_env(tmp_path):
    """Provide isolated directories for job queue, sources, and outputs."""
    jobs_root = tmp_path / "jobs" / "unstructured"
    jobs_root.mkdir(parents=True)

    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    document_path = sources_dir / "test.pdf"
    document_path.write_text("dummy pdf content")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    return {
        "jobs_root": jobs_root,
        "document_path": document_path,
        "output_dir": output_dir,
    }


def _job_dir(job_id: str, jobs_root: Path) -> Path:
    return jobs_root / job_id


def _update_status(job_dir: Path, **overrides) -> None:
    status_path = job_dir / "status.json"
    status = json.loads(status_path.read_text())
    status.update(overrides)
    status_path.write_text(json.dumps(status, indent=2))


def test_create_job_basic(temp_env):
    env = temp_env
    job_id = submit_unstructured_job.create_job(
        document_path=str(env["document_path"]),
        output_dir=str(env["output_dir"]),
        jobs_root=str(env["jobs_root"]),
    )

    job_dir = _job_dir(job_id, env["jobs_root"])
    manifest = json.loads((job_dir / "manifest.json").read_text())
    status = json.loads((job_dir / "status.json").read_text())

    assert job_dir.exists()
    assert manifest["document_path"] == str(env["document_path"])
    assert status["state"] == "queued"
    assert (job_dir / "queued.marker").exists()

    assert check_job_status(job_id, jobs_root=str(env["jobs_root"]))["state"] == "queued"
    assert not is_job_complete(job_id, jobs_root=str(env["jobs_root"]))
    assert not is_job_failed(job_id, jobs_root=str(env["jobs_root"]))


def test_status_helpers_reflect_updates(temp_env):
    env = temp_env
    job_id = submit_unstructured_job.create_job(
        document_path=str(env["document_path"]),
        output_dir=str(env["output_dir"]),
        jobs_root=str(env["jobs_root"]),
    )

    job_dir = _job_dir(job_id, env["jobs_root"])
    _update_status(job_dir, state="completed", output_path="/tmp/output.json")

    assert is_job_complete(job_id, jobs_root=str(env["jobs_root"]))
    assert not is_job_failed(job_id, jobs_root=str(env["jobs_root"]))

    _update_status(job_dir, state="failed", errors=["boom"])
    assert is_job_failed(job_id, jobs_root=str(env["jobs_root"]))


def test_wait_for_completion_success(temp_env):
    env = temp_env
    job_id = submit_unstructured_job.create_job(
        document_path=str(env["document_path"]),
        output_dir=str(env["output_dir"]),
        jobs_root=str(env["jobs_root"]),
    )

    job_dir = _job_dir(job_id, env["jobs_root"])
    _update_status(job_dir, state="completed", output_path=str(env["output_dir"] / "result.json"))

    result = wait_for_completion(
        job_id,
        timeout=5,
        poll_interval=0,
        jobs_root=str(env["jobs_root"]),
    )

    assert result["job_id"] == job_id
    assert result["output_path"] == str(env["output_dir"] / "result.json")


def test_wait_for_completion_failure(temp_env):
    env = temp_env
    job_id = submit_unstructured_job.create_job(
        document_path=str(env["document_path"]),
        output_dir=str(env["output_dir"]),
        jobs_root=str(env["jobs_root"]),
    )

    job_dir = _job_dir(job_id, env["jobs_root"])
    _update_status(job_dir, state="failed", errors=["test failure"])

    with pytest.raises(JobFailedError):
        wait_for_completion(
            job_id,
            timeout=5,
            poll_interval=0,
            jobs_root=str(env["jobs_root"]),
        )


def test_wait_for_completion_timeout(temp_env, monkeypatch):
    env = temp_env
    job_id = submit_unstructured_job.create_job(
        document_path=str(env["document_path"]),
        output_dir=str(env["output_dir"]),
        jobs_root=str(env["jobs_root"]),
    )

    class FakeTime:
        def __init__(self):
            self.current = 0.0

        def time(self):
            self.current += 0.6
            return self.current

        def sleep(self, seconds):
            self.current += seconds

    fake_time = FakeTime()
    monkeypatch.setattr(wait_for_job, "time", fake_time)

    with pytest.raises(JobTimeoutError):
        wait_for_completion(
            job_id,
            timeout=1,
            poll_interval=0.1,
            jobs_root=str(env["jobs_root"]),
        )
