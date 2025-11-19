import json
import time
from pathlib import Path

import psycopg
import pytest


SAMPLE_PDF_BYTES = (
    b"%PDF-1.1\n"
    b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>\n"
    b"endobj\n"
    b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
    b"endobj\n"
    b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>\n"
    b"endobj\n"
    b"4 0 obj<< /Length 44 >>\n"
    b"stream\n"
    b"BT /F1 24 Tf 72 120 Td (Integration Test) Tj ET\n"
    b"endstream\n"
    b"endobj\n"
    b"trailer<< /Root 1 0 R >>\n"
    b"%%EOF\n"
)


def _write_sample_pdf(path: Path) -> None:
    path.write_bytes(SAMPLE_PDF_BYTES)


def _wait_for_job(job_id: str, *, state, timeout: float = 180.0, stage: str | None = None):
    from ingestion.core.job_registry import JobRegistry

    registry = JobRegistry.global_instance()
    deadline = time.time() + timeout
    last_record = None
    while time.time() < deadline:
        record = registry.get(job_id)
        if record:
            last_record = record
            if record.state == state and (stage is None or record.stage == stage):
                return record
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for job {job_id} to reach state {state}; last record={last_record}")


def _wait_for_condition(condition, timeout: float = 180.0):
    deadline = time.time() + timeout
    result = None
    while time.time() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(1)
    raise AssertionError("Timed out waiting for condition")


def _count_dictionary_rows(dsn: str, job_id: str) -> int:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ingestion_dictionary WHERE source_id = %s", (job_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0


def _delete_dictionary_rows(dsn: str, job_id: str) -> None:
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ingestion_dictionary WHERE source_id = %s", (job_id,))


def _fetch_cassandra_rows(cluster, keyspace: str, job_id: str):
    session = cluster.connect(keyspace)
    rows = list(session.execute("SELECT * FROM embeddings WHERE document_id = %s", (job_id,)))
    session.shutdown()
    return rows


def _delete_cassandra_rows(cluster, keyspace: str, job_id: str) -> None:
    session = cluster.connect(keyspace)
    session.execute("DELETE FROM embeddings WHERE document_id = %s", (job_id,))
    session.shutdown()


def _graph_document_exists(driver, job_id: str) -> bool:
    with driver.session() as session:
        record = session.run("MATCH (d:Document {document_id: $doc}) RETURN d LIMIT 1", doc=job_id).single()
        return record is not None


def _graph_document_count(driver, job_id: str) -> int:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (d:Document {document_id: $doc})-[:CONTAINS]->(c:Chunk)
            RETURN count(c) AS chunks
            """,
            doc=job_id,
        ).single()
        return int(result["chunks"]) if result else 0


def _graph_remove_document(driver, job_id: str) -> None:
    with driver.session() as session:
        session.run("MATCH (d:Document {document_id: $doc}) DETACH DELETE d", doc=job_id)


def _load_embeddings_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.integration
def test_happy_path_ingestion(
    integration_env,
    prepared_datastores,
    worker_factory,
    celery_app_fixture,
):
    from ingestion.core.pipeline import deterministic_job_id
    from ingestion.core.job_registry import JobState

    proc, _ = worker_factory()
    try:
        transfer_root = integration_env["transfer_root"]
        sources_dir = transfer_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        source_file = sources_dir / "happy.pdf"
        _write_sample_pdf(source_file)

        app = celery_app_fixture
        async_result = app.send_task("source_sentinel.scan")
        async_result.get(timeout=60)

        job_id = deterministic_job_id(source_file)
        record = _wait_for_job(job_id, state=JobState.COMPLETED)

        stack = prepared_datastores
        cassandra_rows = _fetch_cassandra_rows(stack["cassandra_cluster"], stack["cassandra_keyspace"], job_id)
        assert len(cassandra_rows) == record.expected_count
        dictionary_count = _count_dictionary_rows(stack["postgres_dsn"], job_id)
        assert dictionary_count == record.expected_count
        assert _graph_document_exists(stack["neo4j_driver"], job_id)
        assert _graph_document_count(stack["neo4j_driver"], job_id) == record.expected_count

        job_dir = transfer_root / "artifacts" / job_id
        assert (job_dir / "finalized.marker").is_file()
        chunks_path = job_dir / "embeddings" / "chunks_with_vectors.json"
        assert chunks_path.is_file()
        payload = _load_embeddings_manifest(job_dir / "embeddings" / "manifest.json")
        assert payload["chunk_count"] == record.expected_count
    finally:
        proc.terminate()
        proc.wait(timeout=20)


@pytest.mark.integration
def test_refresh_path_reingests_with_same_checksum(
    integration_env,
    prepared_datastores,
    worker_factory,
    celery_app_fixture,
):
    from ingestion.core.pipeline import deterministic_job_id
    from ingestion.core.job_registry import JobRecord, JobRegistry, JobState

    proc, _ = worker_factory()
    try:
        transfer_root = integration_env["transfer_root"]
        sources_dir = transfer_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        source_file = sources_dir / "refresh.pdf"
        _write_sample_pdf(source_file)

        app = celery_app_fixture
        app.send_task("source_sentinel.scan").get(timeout=60)
        job_id = deterministic_job_id(source_file)
        original = _wait_for_job(job_id, state=JobState.COMPLETED)
        first_checksum = original.expected_checksum
        stack = prepared_datastores
        assert first_checksum

        _delete_cassandra_rows(stack["cassandra_cluster"], stack["cassandra_keyspace"], job_id)
        _delete_dictionary_rows(stack["postgres_dsn"], job_id)
        _graph_remove_document(stack["neo4j_driver"], job_id)

        app.send_task("health_verifier.verify").get(timeout=120)

        registry = JobRegistry.global_instance()

        def _refresh_done() -> JobRecord | None:
            jobs = {item.job_id: item for item in registry.list()}
            for record in jobs.values():
                if record.refresh and record.stage == "housekeeping" and record.state == JobState.COMPLETED:
                    return record
            return None

        refresh_record = _wait_for_condition(_refresh_done, timeout=240)
        assert refresh_record.expected_checksum == first_checksum
        refreshed_rows = _fetch_cassandra_rows(stack["cassandra_cluster"], stack["cassandra_keyspace"], refresh_record.job_id)
        assert len(refreshed_rows) == refresh_record.expected_count
        dictionary_count = _count_dictionary_rows(stack["postgres_dsn"], refresh_record.job_id)
        assert dictionary_count == refresh_record.expected_count
        assert _graph_document_exists(stack["neo4j_driver"], refresh_record.job_id)
    finally:
        proc.terminate()
        proc.wait(timeout=20)


@pytest.mark.integration
def test_removal_path_purges_all_artifacts(
    integration_env,
    prepared_datastores,
    worker_factory,
    celery_app_fixture,
):
    from ingestion.core.job_registry import JobRegistry, JobState, new_record
    from ingestion.core.pipeline import deterministic_job_id

    proc, _ = worker_factory()
    try:
        transfer_root = integration_env["transfer_root"]
        sources_dir = transfer_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        source_file = sources_dir / "removal.pdf"
        _write_sample_pdf(source_file)

        app = celery_app_fixture
        app.send_task("source_sentinel.scan").get(timeout=60)
        job_id = deterministic_job_id(source_file)
        _wait_for_job(job_id, state=JobState.COMPLETED)

        removal_job_id = f"{job_id}-remove-test"
        registry = JobRegistry.global_instance()
        registry.upsert(
            new_record(
                job_id=removal_job_id,
                source_path=str(source_file),
                state=JobState.QUEUED,
                refresh=False,
                stage="housekeeping",
                message="Removal test job",
            )
        )

        app.send_task("housekeeping.remove_source", args=[removal_job_id, str(source_file)]).get(timeout=120)
        removal_record = _wait_for_job(removal_job_id, state=JobState.REMOVED, timeout=180)
        assert removal_record.state == JobState.REMOVED
        stack = prepared_datastores
        assert _count_dictionary_rows(stack["postgres_dsn"], job_id) == 0
        assert not _fetch_cassandra_rows(stack["cassandra_cluster"], stack["cassandra_keyspace"], job_id)
        assert not _graph_document_exists(stack["neo4j_driver"], job_id)
        job_dir = transfer_root / "artifacts" / job_id
        assert not job_dir.exists()
    finally:
        proc.terminate()
        proc.wait(timeout=20)


@pytest.mark.integration
@pytest.mark.chaos
def test_cassandra_worker_kill_retries_idempotently(
    integration_env,
    prepared_datastores,
    worker_factory,
    celery_app_fixture,
):
    from ingestion.core.pipeline import deterministic_job_id
    from ingestion.core.job_registry import JobRecord, JobRegistry, JobState

    chaos_env = {"CHAOS_CASSANDRA_UPSERT_SLEEP": "8"}
    proc, _ = worker_factory(env=chaos_env, log_name="worker-chaos")
    transfer_root = integration_env["transfer_root"]
    try:
        sources_dir = transfer_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        source_file = sources_dir / "chaos.pdf"
        _write_sample_pdf(source_file)
        app = celery_app_fixture
        app.send_task("source_sentinel.scan").get(timeout=60)
        job_id = deterministic_job_id(source_file)
        registry = JobRegistry.global_instance()

        def _in_cassandra_stage() -> JobRecord | None:
            record = registry.get(job_id)
            if record and record.stage == "cassandra_upsert":
                return record
            return None

        _wait_for_condition(_in_cassandra_stage, timeout=180)
        proc.terminate()
        proc.wait(timeout=20)

        recovery_worker, _ = worker_factory()
        try:
            _wait_for_job(job_id, state=JobState.COMPLETED, timeout=240)
        finally:
            recovery_worker.terminate()
            recovery_worker.wait(timeout=20)

        stack = prepared_datastores
        rows = _fetch_cassandra_rows(stack["cassandra_cluster"], stack["cassandra_keyspace"], job_id)
        chunk_ids = {row.chunk_id for row in rows}
        assert len(chunk_ids) == len(rows) == 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=20)


@pytest.mark.integration
@pytest.mark.chaos
def test_embedding_provider_retries_on_429(
    integration_env,
    prepared_datastores,
    worker_factory,
    celery_app_fixture,
    monkeypatch,
    tmp_path,
):
    from ingestion.core.pipeline import deterministic_job_id
    from ingestion.core.job_registry import JobRegistry, JobState

    attempts_log = tmp_path / "embedding_attempts.log"
    monkeypatch.setenv("CHAOS_EMBEDDING_FAILURES", "2")
    monkeypatch.setenv("CHAOS_EMBEDDING_LOG", str(attempts_log))
    monkeypatch.setenv("CHAOS_EMBEDDING_FAILURE_STATUS", "429")

    proc, _ = worker_factory(
        env={
            "CHAOS_EMBEDDING_FAILURES": "2",
            "CHAOS_EMBEDDING_LOG": str(attempts_log),
            "CHAOS_EMBEDDING_FAILURE_STATUS": "429",
        },
        log_name="worker-429",
    )
    try:
        transfer_root = integration_env["transfer_root"]
        sources_dir = transfer_root / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        source_file = sources_dir / "retry.pdf"
        _write_sample_pdf(source_file)
        app = celery_app_fixture
        app.send_task("source_sentinel.scan").get(timeout=60)
        job_id = deterministic_job_id(source_file)
        _wait_for_job(job_id, state=JobState.COMPLETED, timeout=240)
        attempts = attempts_log.read_text(encoding="utf-8").strip().splitlines()
        assert attempts.count("failure") == 2
        assert attempts[-1] == "success"
        stack = prepared_datastores
        assert _count_dictionary_rows(stack["postgres_dsn"], job_id) >= 1
        assert _fetch_cassandra_rows(stack["cassandra_cluster"], stack["cassandra_keyspace"], job_id)
    finally:
        proc.terminate()
        proc.wait(timeout=20)
