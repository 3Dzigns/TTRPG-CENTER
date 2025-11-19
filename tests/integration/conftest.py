import importlib
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Optional

import psycopg
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("CASSANDRA_DRIVER_EVENT_LOOP", "asyncio")
os.environ.setdefault("CASSANDRA_DRIVER_NO_EXTENSIONS", "1")

from cassandra.cluster import Cluster
from cassandra.io.asyncioreactor import AsyncioConnection
from neo4j import GraphDatabase


COMPOSE_FILE = Path(__file__).parent / "docker-compose.yml"
BROKER_URL = "amqp://guest:guest@localhost:5679//"
RESULT_BACKEND = "redis://localhost:6381/0"
POSTGRES_DSN = "postgresql://ttrpg:ttrpg@localhost:55433/ttrpg_ingestion"
CASSANDRA_HOST = "127.0.0.1"
CASSANDRA_PORT = 39042
CASSANDRA_KEYSPACE = "ttrpg_vectors"
NEO4J_URI = "bolt://localhost:7769"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testing"

WORKER_MODULES: Iterable[str] = (
    "ingestion.workers.source_sentinel.tasks",
    "ingestion.workers.unstructured.tasks",
    "ingestion.workers.ingestion_engine.tasks",
    "ingestion.workers.haystack.tasks",
    "ingestion.workers.cassandra_upsert.tasks",
    "ingestion.workers.llamaindex.tasks",
    "ingestion.workers.graph_upsert.tasks",
    "ingestion.workers.housekeeping.tasks",
    "ingestion.workers.health_verifier.tasks",
    "ingestion.workers.dlq.tasks",
)

CORE_MODULES: Iterable[str] = (
    "ingestion.config.settings",
    "ingestion.config",
    "ingestion.core.status",
    "ingestion.core.pipeline",
    "ingestion.core.embeddings",
    "ingestion.core.idempotency",
    "ingestion.core.job_registry",
    "ingestion.core.db.postgres",
    "ingestion.core.db.dictionary",
    "ingestion.core.db.cassandra_store",
    "ingestion.core.db.graph_store",
    "ingestion.core.task_utils",
)


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), *args]
    return subprocess.run(cmd, check=check, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def _wait_for_port(host: str, port: int, *, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(1)
    raise TimeoutError(f"Timed out waiting for {host}:{port} to accept connections")


def _wait_for_postgres(dsn: str) -> None:
    deadline = time.monotonic() + 120.0
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return
        except psycopg.Error:
            time.sleep(1)
    raise TimeoutError("Postgres did not become ready in time")


def _wait_for_cassandra(host: str, port: int) -> Cluster:
    deadline = time.monotonic() + 90.0
    last_exc: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            cluster = Cluster(
                [host],
                port=port,
                connection_class=AsyncioConnection,
                connect_timeout=30,
                control_connection_timeout=30,
            )
            session = cluster.connect()
            session.execute(
                f"""
                CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
                WITH replication = {{'class':'SimpleStrategy','replication_factor':1}}
                """
            )
            session.set_keyspace(CASSANDRA_KEYSPACE)
            session.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    document_id TEXT,
                    element_id TEXT,
                    chunk_index INT,
                    text TEXT,
                    system TEXT,
                    source TEXT,
                    section TEXT,
                    tags SET<TEXT>,
                    page_number INT,
                    section_title TEXT,
                    text_hash TEXT,
                    metadata_hash TEXT,
                    vector_hash TEXT,
                    facets TEXT,
                    embedding LIST<FLOAT>,
                    PRIMARY KEY (document_id, element_id, chunk_index)
                )
                """
            )
            session.shutdown()
            return cluster
        except Exception as exc:  # pragma: no cover - waiting loop
            last_exc = exc
            try:
                cluster.shutdown()  # type: ignore[name-defined]
            except Exception:
                pass
            time.sleep(3)
    raise TimeoutError(f"Cassandra did not become ready: {last_exc}")  # pragma: no cover


def _wait_for_neo4j(uri: str, user: str, password: str):
    deadline = time.monotonic() + 180.0
    last_exc: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            with driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            return driver
        except Exception as exc:  # pragma: no cover - waiting loop
            last_exc = exc
            time.sleep(3)
    raise TimeoutError(f"Neo4j did not become ready: {last_exc}")  # pragma: no cover


@pytest.fixture(scope="session")
def integration_stack() -> Dict[str, object]:
    if not shutil.which("docker"):  # type: ignore[name-defined]
        pytest.skip("Docker CLI is not available; integration tests skipped")
    # Ensure docker module available
    _compose("down", "-v", check=False)
    result = _compose("up", "-d", "--remove-orphans")
    if result.returncode != 0:
        raise RuntimeError(f"Docker compose failed: {result.stdout}")

    try:
        _wait_for_port("localhost", 5679)
        _wait_for_port("localhost", 6381)
        _wait_for_postgres(POSTGRES_DSN)
        cassandra_cluster = _wait_for_cassandra(CASSANDRA_HOST, CASSANDRA_PORT)
        neo4j_driver = _wait_for_neo4j(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    except Exception as exc:
        _compose("logs", check=False)
        _compose("down", "-v", check=False)
        pytest.skip(f"Integration stack unavailable: {exc}")

    stack = {
        "broker_url": BROKER_URL,
        "result_backend": RESULT_BACKEND,
        "postgres_dsn": POSTGRES_DSN,
        "cassandra_cluster": cassandra_cluster,
        "cassandra_keyspace": CASSANDRA_KEYSPACE,
        "neo4j_driver": neo4j_driver,
    }

    yield stack

    try:
        neo4j_driver.close()
    finally:
        cassandra_cluster.shutdown()
        _compose("down", "-v", check=False)


def _cleanup_stores(stack: Dict[str, object]) -> None:
    with psycopg.connect(stack["postgres_dsn"]) as conn:  # type: ignore[arg-type]
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ingestion_dictionary")
            cur.execute("DELETE FROM ingestion_jobs_history")
            cur.execute("DELETE FROM ingestion_jobs")
    cluster: Cluster = stack["cassandra_cluster"]  # type: ignore[assignment]
    session = cluster.connect(stack["cassandra_keyspace"])  # type: ignore[index]
    session.execute("TRUNCATE embeddings")
    session.shutdown()
    driver = stack["neo4j_driver"]  # type: ignore[index]
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture
def prepared_datastores(integration_stack: Dict[str, object]):
    _cleanup_stores(integration_stack)
    yield integration_stack
    _cleanup_stores(integration_stack)


def _reload_modules() -> None:
    for name in CORE_MODULES:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    for name in WORKER_MODULES:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)


def _reset_singletons() -> None:
    from ingestion.core.job_registry import JobRegistry
    from ingestion.core.db.cassandra_store import reset_cassandra_store
    from ingestion.core.db.dictionary import reset_dictionary_store
    from ingestion.core.db.graph_store import reset_graph_store
    from ingestion.core.embeddings import reset_embedding_provider

    JobRegistry.reset_global()
    reset_dictionary_store()
    reset_cassandra_store()
    reset_graph_store()
    reset_embedding_provider()


@pytest.fixture
def integration_env(tmp_path, integration_stack: Dict[str, object], monkeypatch):
    transfer_root = tmp_path / "transfer_station"
    transfer_root.mkdir(parents=True, exist_ok=True)

    env_overrides = {
        "TRANSFER_STATION_ROOT": str(transfer_root),
        "CELERY_BROKER_URL": integration_stack["broker_url"],
        "CELERY_RESULT_BACKEND": integration_stack["result_backend"],
        "POSTGRES_DSN": integration_stack["postgres_dsn"],
        "JOB_REGISTRY_BACKEND": "postgres",
        "DICTIONARY_BACKEND": "postgres",
        "CASSANDRA_BACKEND": "cassandra",
        "CASSANDRA_CONTACT_POINTS": CASSANDRA_HOST,
        "CASSANDRA_PORT": str(CASSANDRA_PORT),
        "CASSANDRA_KEYSPACE": CASSANDRA_KEYSPACE,
        "CASSANDRA_TRANSLATED_ADDRESS": "127.0.0.1",
        "NEO4J_BACKEND": "neo4j",
        "NEO4J_URI": NEO4J_URI,
        "NEO4J_USER": NEO4J_USER,
        "NEO4J_PASSWORD": NEO4J_PASSWORD,
        "ENABLE_TRACING": "0",
        "ENABLE_METRICS": "0",
        "EMBEDDING_PROVIDER": "mock",
        "TASK_RETRY_INITIAL_WAIT": "1",
        "TASK_RETRY_BACKOFF": "2",
        "TASK_RETRY_MAX_WAIT": "5",
        "TASK_RETRY_JITTER": "0",
        "TASK_MAX_RETRIES": "5",
    }

    base_env = os.environ.copy()
    base_env.update(env_overrides)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    _reload_modules()
    _reset_singletons()

    from ingestion.config import Settings

    settings = Settings()
    default_queues = [
        "source_sentinel",
        "unstructured",
        "ingestion_engine",
        "haystack",
        "cassandra_upsert",
        "llamaindex",
        "graph_upsert",
        "housekeeping",
        "health_verifier",
        "dlq",
    ]
    return {
        "settings": settings,
        "transfer_root": transfer_root,
        "env": base_env,
        "default_queues": default_queues,
    }


@pytest.fixture
def worker_factory(integration_env):
    processes = []

    def _start_worker(*, queues: Optional[Iterable[str]] = None, env: Optional[Dict[str, str]] = None, log_name: str = "celery-worker"):
        worker_env = dict(integration_env["env"])
        if env:
            worker_env.update(env)
        queue_list = list(queues or integration_env["default_queues"])
        log_path = integration_env["transfer_root"].parent / f"{log_name}.log"
        log_file = open(log_path, "w", encoding="utf-8")
        cmd = [
            "celery",
            "-A",
            "ingestion.core.celery_app",
            "worker",
            "-P",
            "solo",
            "-l",
            "info",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
            "-Q",
            ",".join(queue_list),
        ]
        proc = subprocess.Popen(cmd, env=worker_env, stdout=log_file, stderr=subprocess.STDOUT)
        processes.append((proc, log_file))
        time.sleep(5)
        if proc.poll() is not None:
            log_file.close()
            raise RuntimeError("Celery worker failed to start; see log for details")
        return proc, log_path

    yield _start_worker

    for proc, handle in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
        handle.close()


@pytest.fixture
def celery_app_fixture(integration_env):
    from ingestion.core.celery_app import create_celery_app

    app = create_celery_app()
    yield app
    app.close()
