"""
Centralized configuration model for the async ingestion pipeline.

Environment variables provide the primary configuration surface so containers
can be tuned independently while sharing the same codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list(value: str | None, *, default: List[str] | None = None) -> List[str]:
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    """Load configuration values from the environment."""

    # Shared paths
    transfer_root: Path = Path(
        os.getenv("TRANSFER_STATION_ROOT", "/Transfer_Station")
    )
    logs_dir: Path = field(init=False)
    artifacts_dir: Path = field(init=False)
    jobs_dir: Path = field(init=False)
    sources_dir: Path = field(init=False)

    # Messaging / Celery
    broker_url: str = os.getenv(
        "CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672//"
    )
    result_backend: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://redis:6379/0"
    )
    task_queues: List[str] = field(
        default_factory=lambda: _list(
            os.getenv(
                "CELERY_TASK_QUEUES",
                "source_sentinel,unstructured,ingestion_engine,"
                "haystack,llamaindex,cassandra_upsert,graph_upsert,housekeeping,health_verifier,dlq",
            )
        )
    )

    # Database connections
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        "postgresql://ttrpg:ttrpg@postgres:5432/ttrpg_ingestion",
    )
    cassandra_hosts: List[str] = field(
        default_factory=lambda: _list(os.getenv("CASSANDRA_CONTACT_POINTS", "cassandra"))
    )
    cassandra_port: int = int(os.getenv("CASSANDRA_PORT", "9042"))
    cassandra_keyspace: str = os.getenv("CASSANDRA_KEYSPACE", "ttrpg_vectors")
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    neo4j_backend: str = os.getenv("NEO4J_BACKEND", "neo4j")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "changeme")

    # Feature toggles
    enable_tracing: bool = field(
        default_factory=lambda: _bool(os.getenv("ENABLE_TRACING"), default=True)
    )
    enable_metrics: bool = field(
        default_factory=lambda: _bool(os.getenv("ENABLE_METRICS"), default=True)
    )
    job_registry_backend: str = os.getenv("JOB_REGISTRY_BACKEND", "postgres")
    dictionary_backend: str = os.getenv("DICTIONARY_BACKEND", "postgres")

    # Worker runtime tuning
    worker_prefetch_multiplier: int = int(os.getenv("WORKER_PREFETCH", "1"))
    task_soft_time_limit: int = int(os.getenv("TASK_SOFT_TIME_LIMIT", "900"))
    task_hard_time_limit: int = int(os.getenv("TASK_HARD_TIME_LIMIT", "1200"))
    retry_initial_wait: int = int(os.getenv("TASK_RETRY_INITIAL_WAIT", "30"))
    retry_backoff: float = float(os.getenv("TASK_RETRY_BACKOFF", "2.0"))
    retry_max_wait: int = int(os.getenv("TASK_RETRY_MAX_WAIT", "900"))
    retry_jitter: int = int(os.getenv("TASK_RETRY_JITTER", "15"))
    retry_max_retries: int = int(os.getenv("TASK_MAX_RETRIES", "5"))

    # Unstructured processing
    unstructured_languages: List[str] = field(
        default_factory=lambda: _list(os.getenv("UNSTRUCTURED_LANGUAGES", "eng"))
    )
    unstructured_hi_res_model: str = os.getenv(
        "UNSTRUCTURED_HI_RES_MODEL", "yolox"
    )

    # Embedding model
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "text-embedding-3-small"
    )
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "openai")
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "64"))
    # Source Sentinel scan frequency (seconds); default to 10 minutes
    source_scan_interval: int = int(os.getenv("SOURCE_SCAN_INTERVAL", "600"))
    cassandra_backend: str = os.getenv("CASSANDRA_BACKEND", "cassandra")
    cassandra_username: str | None = os.getenv("CASSANDRA_USERNAME")
    cassandra_password: str | None = os.getenv("CASSANDRA_PASSWORD")
    cassandra_consistency: str = os.getenv("CASSANDRA_CONSISTENCY", "LOCAL_QUORUM")
    metrics_host: str = os.getenv("METRICS_HOST", "0.0.0.0")
    metrics_port: int = int(os.getenv("METRICS_PORT", "0"))
    artifact_retention_days: int = int(os.getenv("ARTIFACT_RETENTION_DAYS", "14"))

    def __post_init__(self) -> None:
        self.logs_dir = self.transfer_root / "logs"
        self.artifacts_dir = self.transfer_root / "artifacts"
        self.jobs_dir = self.transfer_root / "jobs"
        self.sources_dir = self.transfer_root / "sources"

    def as_dict(self) -> dict[str, str | int | bool | List[str]]:
        """Expose settings in a serializable dictionary form."""
        return {
            "transfer_root": str(self.transfer_root),
            "logs_dir": str(self.logs_dir),
            "artifacts_dir": str(self.artifacts_dir),
            "jobs_dir": str(self.jobs_dir),
            "sources_dir": str(self.sources_dir),
            "broker_url": self.broker_url,
            "result_backend": self.result_backend,
            "task_queues": list(self.task_queues),
            "postgres_dsn": self.postgres_dsn,
            "cassandra_hosts": list(self.cassandra_hosts),
            "cassandra_port": self.cassandra_port,
            "cassandra_keyspace": self.cassandra_keyspace,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_database": self.neo4j_database,
            "neo4j_backend": self.neo4j_backend,
            "neo4j_user": self.neo4j_user,
            "neo4j_password": "***",
            "enable_tracing": self.enable_tracing,
            "enable_metrics": self.enable_metrics,
            "job_registry_backend": self.job_registry_backend,
            "dictionary_backend": self.dictionary_backend,
            "worker_prefetch_multiplier": self.worker_prefetch_multiplier,
            "task_soft_time_limit": self.task_soft_time_limit,
            "task_hard_time_limit": self.task_hard_time_limit,
            "retry_initial_wait": self.retry_initial_wait,
            "retry_backoff": self.retry_backoff,
            "retry_max_wait": self.retry_max_wait,
            "retry_jitter": self.retry_jitter,
            "retry_max_retries": self.retry_max_retries,
            "unstructured_languages": list(self.unstructured_languages),
            "unstructured_hi_res_model": self.unstructured_hi_res_model,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "embedding_provider": self.embedding_provider,
            "embedding_batch_size": self.embedding_batch_size,
            "cassandra_backend": self.cassandra_backend,
            "cassandra_username": self.cassandra_username or "",
            "cassandra_consistency": self.cassandra_consistency,
            "metrics_host": self.metrics_host,
            "metrics_port": self.metrics_port,
            "artifact_retention_days": self.artifact_retention_days,
        }

