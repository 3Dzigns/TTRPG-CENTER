import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    transfer_root = tmp_path / "ts"
    (transfer_root / "sources").mkdir(parents=True, exist_ok=True)
    (transfer_root / "logs").mkdir(parents=True, exist_ok=True)
    (transfer_root / "artifacts").mkdir(parents=True, exist_ok=True)
    (transfer_root / "jobs").mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("TRANSFER_STATION_ROOT", str(transfer_root))
    monkeypatch.setenv("JOB_REGISTRY_BACKEND", "memory")
    monkeypatch.setenv("DICTIONARY_BACKEND", "memory")
    monkeypatch.setenv("CASSANDRA_BACKEND", "memory")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("ENABLE_TRACING", "0")
    monkeypatch.setenv("ENABLE_METRICS", "0")

    import ingestion.config.settings as settings_module

    settings_module = importlib.reload(settings_module)
    import ingestion.config as config_package

    config_package = importlib.reload(config_package)

    from ingestion.core import job_registry as job_registry_module

    job_registry_module = importlib.reload(job_registry_module)
    JobRegistry = job_registry_module.JobRegistry
    JobRegistry.reset_global()

    from ingestion.core.db.dictionary import reset_dictionary_store
    from ingestion.core.db.cassandra_store import reset_cassandra_store
    from ingestion.core.embeddings import reset_embedding_provider
    from ingestion.core.tracing import reset_tracer

    reset_dictionary_store()
    reset_cassandra_store()
    reset_embedding_provider()
    reset_tracer()

    import ingestion.core.pipeline as pipeline_module

    pipeline_module = importlib.reload(pipeline_module)
    import ingestion.cli.job_management as job_management_module

    job_management_module = importlib.reload(job_management_module)
    import ingestion.cli.status_monitor as status_monitor_module

    status_monitor_module = importlib.reload(status_monitor_module)
    import ingestion.cli.log_monitor as log_monitor_module

    log_monitor_module = importlib.reload(log_monitor_module)

    namespace = SimpleNamespace(
        transfer_root=transfer_root,
        JobRegistry=JobRegistry,
        JobState=job_registry_module.JobState,
        new_record=job_registry_module.new_record,
        pipeline=pipeline_module,
        job_management=job_management_module,
        status_monitor=status_monitor_module,
        log_monitor=log_monitor_module,
        reset_dictionary_store=reset_dictionary_store,
        reset_cassandra_store=reset_cassandra_store,
        reset_embedding_provider=reset_embedding_provider,
        reset_tracer=reset_tracer,
    )

    yield namespace

    JobRegistry.reset_global()
    reset_dictionary_store()
    reset_cassandra_store()
    reset_embedding_provider()
    reset_tracer()


def test_job_management_start_requires_confirmation(cli_env, monkeypatch, capsys):
    source = cli_env.transfer_root / "sources" / "manual.pdf"
    source.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr("builtins.input", lambda _: "n")
    exit_code = cli_env.job_management.main(["start", "--file", str(source)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Operation cancelled." in captured.out
    registry = cli_env.JobRegistry.global_instance()
    assert not any(job.source_path == str(source) for job in registry.list())


def test_job_management_start_auto_yes_runs_pipeline(cli_env, capsys):
    source = cli_env.transfer_root / "sources" / "manual.pdf"
    source.write_text("dummy", encoding="utf-8")

    exit_code = cli_env.job_management.main(
        ["start", "--file", str(source), "--refresh", "--yes"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "auto-confirm" in captured.out
    registry = cli_env.JobRegistry.global_instance()
    jobs = [job for job in registry.list() if job.source_path == str(source)]
    assert jobs
    assert jobs[0].refresh is True


def test_job_management_mark_unhealthy(cli_env, capsys):
    source = cli_env.transfer_root / "sources" / "manual.pdf"
    job_id = "test-job"
    registry = cli_env.JobRegistry.global_instance()
    registry.upsert(
        cli_env.new_record(
            job_id=job_id,
            source_path=str(source),
            state=cli_env.JobState.RUNNING,
            refresh=False,
            stage="test",
            message="seed",
        )
    )

    exit_code = cli_env.job_management.main(
        ["mark-unhealthy", "--file", str(source), "--yes"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Marked" in captured.out
    updated = registry.get(job_id)
    assert updated.state == cli_env.JobState.FAILED
    assert updated.message == "Marked unhealthy via CLI"


def test_job_management_remove_enqueues_removal(cli_env, capsys):
    source = cli_env.transfer_root / "sources" / "manual.pdf"
    source.write_text("dummy", encoding="utf-8")
    cli_env.job_management.main(["start", "--file", str(source), "--yes"])
    capsys.readouterr()  # Clear previous output

    exit_code = cli_env.job_management.main(["remove", "--file", str(source), "--yes"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Removal job" in captured.out

    registry = cli_env.JobRegistry.global_instance()
    removal_jobs = [job for job in registry.list() if job.job_id.startswith("remove-")]
    assert removal_jobs
    assert removal_jobs[0].state == cli_env.JobState.REMOVED


def test_status_monitor_deep_json(cli_env, capsys):
    source = cli_env.transfer_root / "sources" / "manual.pdf"
    source.write_text("dummy", encoding="utf-8")
    cli_env.job_management.main(["start", "--file", str(source), "--yes"])
    capsys.readouterr()

    exit_code = cli_env.status_monitor.main(
        ["--file", str(source), "--deep", "--json"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    rows = json.loads(captured.out)
    assert rows
    row = rows[0]
    assert row["dictionary_terms"] is None or row["dictionary_terms"] >= 0
    assert row["cassandra_rows"] is None or row["cassandra_rows"] >= 0


def test_log_monitor_errors_filter(cli_env, capsys):
    log_path = cli_env.transfer_root / "logs" / "pipeline.log"
    lines = [
        "2024-01-01T00:00:00 INFO Startup complete\n",
        '{"level":"ERROR","message":"failure detected"}\n',
        "2024-01-01T00:00:01 WARNING Skipped\n",
    ]
    log_path.write_text("".join(lines), encoding="utf-8")

    exit_code = cli_env.log_monitor.main(["--file", str(log_path), "--errors"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "failure detected" in captured.out
    assert "Startup complete" not in captured.out


def test_log_monitor_list_logs(cli_env, capsys):
    log_dir = cli_env.transfer_root / "logs"
    (log_dir / "pipeline.log").write_text("", encoding="utf-8")
    (log_dir / "workers" / "loader").mkdir(parents=True, exist_ok=True)
    (log_dir / "workers" / "loader" / "worker.log").write_text("", encoding="utf-8")

    exit_code = cli_env.log_monitor.main(["--list"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "pipeline.log" in captured.out
    assert "worker.log" in captured.out


def test_log_monitor_aggregate_tail(cli_env, capsys):
    log_dir = cli_env.transfer_root / "logs"
    pipeline = log_dir / "pipeline.log"
    worker = log_dir / "worker.log"
    pipeline.write_text(
        "2024-01-01T00:00:00Z pipeline info\n2024-01-01T00:00:03Z pipeline done\n",
        encoding="utf-8",
    )
    worker.write_text(
        "2024-01-01T00:00:01Z worker start\n2024-01-01T00:00:02Z worker error\n",
        encoding="utf-8",
    )

    exit_code = cli_env.log_monitor.main(["--tail", "3"])
    captured = capsys.readouterr()
    assert exit_code == 0
    lines = [line for line in captured.out.strip().splitlines() if line]
    assert len(lines) == 3
    assert lines[-1].startswith("[pipeline.log]")
    assert any("worker error" in line for line in lines)


def test_log_monitor_aggregate_errors_only(cli_env, capsys):
    log_dir = cli_env.transfer_root / "logs"
    (log_dir / "pipeline.log").write_text(
        "2024-01-01T00:00:00Z pipeline info\n"
        '{"level":"ERROR","message":"fatal"}\n'
        "2024-01-01T00:00:02Z pipeline ok\n",
        encoding="utf-8",
    )

    exit_code = cli_env.log_monitor.main(["--tail", "5", "--errors"])
    captured = capsys.readouterr()
    assert exit_code == 0
    lines = [line for line in captured.out.strip().splitlines() if line]
    assert len(lines) == 1
    assert "fatal" in lines[0]


def _write_dlq_entries(root: Path, entries: list[dict]) -> Path:
    dlq_dir = root / "jobs"
    dlq_dir.mkdir(parents=True, exist_ok=True)
    dlq_file = dlq_dir / "dlq.jsonl"
    dlq_file.write_text(
        "\n".join(json.dumps(entry, ensure_ascii=False) for entry in entries) + "\n",
        encoding="utf-8",
    )
    return dlq_file


def test_job_management_dlq_inspect_json(cli_env, capsys):
    entries = [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "job_id": "job-1",
            "task": "tests.task",
            "message": "failure one",
            "retries": 3,
        },
        {
            "timestamp": "2024-01-01T00:00:01Z",
            "job_id": "job-2",
            "task": "tests.task",
            "message": "failure two",
            "retries": 5,
        },
    ]
    _write_dlq_entries(cli_env.transfer_root, entries)

    exit_code = cli_env.job_management.main(["dlq-inspect", "--limit", "1", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert len(payload) == 1
    assert payload[0]["job_id"] == "job-2"


def test_job_management_dlq_inspect_filters(cli_env, capsys):
    entries = [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "job_id": "job-1",
            "task": "tests.task",
            "message": "failure one",
            "retries": 3,
        },
        {
            "timestamp": "2024-01-01T00:00:01Z",
            "job_id": "job-2",
            "task": "tests.other",
            "message": "bad payload",
            "retries": 2,
        },
    ]
    _write_dlq_entries(cli_env.transfer_root, entries)
    exit_code = cli_env.job_management.main(
        ["dlq-inspect", "--limit", "5", "--job", "job-1", "--contains", "failure"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    lines = [line for line in captured.out.splitlines() if "job-1" in line]
    assert lines
    assert "bad payload" not in captured.out
