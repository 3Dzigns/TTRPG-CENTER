import importlib
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("celery")

from ingestion.core.tasks import BaseTask


def test_base_task_on_failure_routes_to_dlq():
    sent: dict = {}

    class DummyTask(BaseTask):
        name = "tests.dummy"

    task = DummyTask()
    task.request = SimpleNamespace(retries=5)
    task.retry_kwargs = {"max_retries": 5}

    def send_task(name, args=None, queue=None):
        sent["name"] = name
        sent["args"] = args or []
        sent["queue"] = queue

    task.app = SimpleNamespace(send_task=send_task)

    task.on_failure(Exception("boom"), "task-id", ("job-123",), {}, None)

    assert sent["name"] == "dlq.record_failure"
    assert sent["queue"] == "dlq"
    payload = sent["args"][0]
    assert payload["job_id"] == "job-123"
    assert payload["task"] == "tests.dummy"
    assert payload["retries"] == 5


def test_dlq_record_failure_writes_file(tmp_path, monkeypatch):
    transfer_root = tmp_path / "ts"
    monkeypatch.setenv("TRANSFER_STATION_ROOT", str(transfer_root))

    import ingestion.workers.dlq.tasks as dlq_tasks

    dlq_tasks = importlib.reload(dlq_tasks)

    payload = {
        "task": "tests.dummy",
        "task_id": "task-1",
        "job_id": "job-456",
        "args": [],
        "kwargs": {},
        "message": "failure",
        "retries": 5,
        "max_retries": 5,
    }

    dlq_tasks.record_failure(None, payload)

    dlq_file = transfer_root / "jobs" / "dlq.jsonl"
    assert dlq_file.is_file()

    lines = [line for line in dlq_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "Expected DLQ entries"
    entry = json.loads(lines[-1])
    assert entry["task_id"] == "task-1"
    assert entry["job_id"] == "job-456"
