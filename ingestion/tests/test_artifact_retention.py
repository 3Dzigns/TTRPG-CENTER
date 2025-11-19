import importlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _setup_environment(tmp_path, monkeypatch, *, retention_days: int):
    transfer_root = tmp_path / "ts"
    monkeypatch.setenv("TRANSFER_STATION_ROOT", str(transfer_root))
    monkeypatch.setenv("JOB_REGISTRY_BACKEND", "memory")
    monkeypatch.setenv("DICTIONARY_BACKEND", "memory")
    monkeypatch.setenv("CASSANDRA_BACKEND", "memory")
    monkeypatch.setenv("NEO4J_BACKEND", "memory")
    monkeypatch.setenv("ARTIFACT_RETENTION_DAYS", str(retention_days))

    import ingestion.config.settings as settings_module

    settings_module = importlib.reload(settings_module)
    settings = settings_module.Settings()

    import ingestion.core.job_registry as job_registry_module

    job_registry_module = importlib.reload(job_registry_module)
    job_registry_module.JobRegistry.reset_global()
    registry = job_registry_module.JobRegistry.global_instance(settings=settings)
    JobState = job_registry_module.JobState
    new_record = job_registry_module.new_record

    import ingestion.workers.housekeeping.retention as retention_module

    retention_module = importlib.reload(retention_module)
    return transfer_root, settings, registry, JobState, new_record, retention_module


def _write_finalized_marker(path: Path, *, job_id: str, source_path: Path, finalized_at: datetime) -> None:
    payload = {
        "job_id": job_id,
        "source_path": str(source_path),
        "finalized": True,
        "finalized_at": finalized_at.isoformat(),
        "expected_checksum": "checksum",
        "expected_count": 1,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_retention_prunes_to_minimal_set(tmp_path, monkeypatch):
    transfer_root, settings, registry, JobState, new_record, retention = _setup_environment(
        tmp_path, monkeypatch, retention_days=14
    )
    job_id = "job-prune"
    source_path = transfer_root / "sources" / "sample.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("content", encoding="utf-8")

    job_dir = transfer_root / "artifacts" / job_id
    (job_dir / "unstructured").mkdir(parents=True, exist_ok=True)
    (job_dir / "metadata").mkdir(exist_ok=True)
    (job_dir / "embeddings").mkdir(exist_ok=True)
    (job_dir / "llamaindex").mkdir(exist_ok=True)
    (job_dir / "unstructured" / "elements.json").write_text("{}", encoding="utf-8")
    (job_dir / "metadata" / "temp.txt").write_text("temp", encoding="utf-8")
    (job_dir / "embeddings" / "embeddings.json").write_text("{}", encoding="utf-8")
    (job_dir / "embeddings" / "manifest.json").write_text("{}", encoding="utf-8")
    (job_dir / "embeddings" / "ready.marker").write_text(json.dumps({"rows": 1}), encoding="utf-8")
    (job_dir / "llamaindex" / "nodes.json").write_text("{}", encoding="utf-8")

    finalized_at = datetime.now(tz=timezone.utc) - timedelta(days=1)
    _write_finalized_marker(job_dir / "finalized.marker", job_id=job_id, source_path=source_path, finalized_at=finalized_at)

    status_path = transfer_root / "jobs" / f"{job_id}.status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("{}", encoding="utf-8")

    registry.upsert(
        new_record(
            job_id=job_id,
            source_path=str(source_path),
            state=JobState.COMPLETED,
            refresh=False,
            stage="housekeeping",
            expected_checksum="checksum",
            expected_count=1,
        )
    )

    now = finalized_at + timedelta(hours=6)
    stats = retention.enforce_retention(settings, registry, now=now)

    assert stats["pruned"] == 1
    assert stats["expired"] == 0
    assert stats["files_removed"] > 0
    assert not (job_dir / "metadata" / "temp.txt").exists()
    assert not (job_dir / "embeddings" / "manifest.json").exists()
    assert not (job_dir / "llamaindex").exists()
    assert (job_dir / "unstructured" / "elements.json").exists()
    assert (job_dir / "embeddings" / "embeddings.json").exists()
    assert (job_dir / "embeddings" / "ready.marker").exists()
    assert (job_dir / "finalized.marker").exists()
    assert status_path.exists()

    log_path = transfer_root / "logs" / "artifact_retention.jsonl"
    assert log_path.is_file()
    log_entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert log_entries[0]["action"] == "pruned"
    assert log_entries[0]["job_id"] == job_id


def test_retention_expires_after_window(tmp_path, monkeypatch):
    transfer_root, settings, registry, JobState, new_record, retention = _setup_environment(
        tmp_path, monkeypatch, retention_days=1
    )
    job_id = "job-expire"
    source_path = transfer_root / "sources" / "sample.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("content", encoding="utf-8")

    job_dir = transfer_root / "artifacts" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "unstructured").mkdir(exist_ok=True)
    (job_dir / "unstructured" / "elements.json").write_text("{}", encoding="utf-8")

    finalized_at = datetime.now(tz=timezone.utc) - timedelta(days=3)
    _write_finalized_marker(job_dir / "finalized.marker", job_id=job_id, source_path=source_path, finalized_at=finalized_at)

    status_path = transfer_root / "jobs" / f"{job_id}.status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("{}", encoding="utf-8")

    registry.upsert(
        new_record(
            job_id=job_id,
            source_path=str(source_path),
            state=JobState.COMPLETED,
            refresh=False,
            stage="housekeeping",
            expected_checksum="checksum",
            expected_count=1,
        )
    )

    now = datetime.now(tz=timezone.utc)
    stats = retention.enforce_retention(settings, registry, now=now)

    assert stats["expired"] == 1
    assert not job_dir.exists()
    assert not status_path.exists()
    log_path = transfer_root / "logs" / "artifact_retention.jsonl"
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(entry["action"] == "expired" for entry in entries)


def test_retention_skips_inflight_refresh(tmp_path, monkeypatch):
    transfer_root, settings, registry, JobState, new_record, retention = _setup_environment(
        tmp_path, monkeypatch, retention_days=2
    )
    job_id = "job-refresh-base"
    refresh_job_id = f"{job_id}-refresh"
    source_path = transfer_root / "sources" / "sample.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("content", encoding="utf-8")

    job_dir = transfer_root / "artifacts" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "unstructured").mkdir(exist_ok=True)
    (job_dir / "unstructured" / "elements.json").write_text("{}", encoding="utf-8")
    (job_dir / "metadata").mkdir(exist_ok=True)
    (job_dir / "metadata" / "temp.txt").write_text("temp", encoding="utf-8")

    finalized_at = datetime.now(tz=timezone.utc) - timedelta(hours=6)
    _write_finalized_marker(job_dir / "finalized.marker", job_id=job_id, source_path=source_path, finalized_at=finalized_at)

    registry.upsert(
        new_record(
            job_id=job_id,
            source_path=str(source_path),
            state=JobState.COMPLETED,
            refresh=False,
            stage="housekeeping",
            expected_checksum="checksum",
            expected_count=1,
        )
    )
    registry.upsert(
        new_record(
            job_id=refresh_job_id,
            source_path=str(source_path),
            state=JobState.RUNNING,
            refresh=True,
            stage="ingestion_engine",
            expected_checksum=None,
            expected_count=None,
        )
    )

    now = datetime.now(tz=timezone.utc)
    stats = retention.enforce_retention(settings, registry, now=now)

    assert stats["pruned"] == 0
    assert stats["skipped"] >= 1
    assert (job_dir / "metadata" / "temp.txt").exists()
    log_path = transfer_root / "logs" / "artifact_retention.jsonl"
    assert not log_path.exists()
