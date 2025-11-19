"""Configuration management for ingestion pipeline."""
from pathlib import Path
from typing import Optional, List
import os

class IngestionConfig:
    """Centralized configuration for ingestion pipeline."""

    # Unstructured API settings (supports multiple containers)
    UNSTRUCTURED_API_URLS: List[str] = [
        os.getenv(
            "UNSTRUCTURED_API_URL",
            "http://ttrpg_unstructured:8000/general/v0/general"
        ),
        os.getenv(
            "UNSTRUCTURED_API_URL_2",
            "http://ttrpg_unstructured_2:8000/general/v0/general"
        )
    ]

    # Container limit (how many containers to use for load balancing)
    UNSTRUCTURED_CONTAINER_LIMIT: int = int(os.getenv("UNSTRUCTURED_CONTAINER_LIMIT", "1"))

    # Timeout settings (in seconds)
    UNSTRUCTURED_TIMEOUT: int = int(os.getenv("UNSTRUCTURED_TIMEOUT", "900"))  # 15 minutes default
    UNSTRUCTURED_MAX_RETRIES: int = int(os.getenv("UNSTRUCTURED_MAX_RETRIES", "3"))
    UNSTRUCTURED_RETRY_BACKOFF: float = float(os.getenv("UNSTRUCTURED_RETRY_BACKOFF", "2.0"))  # Exponential base
    UNSTRUCTURED_INITIAL_WAIT: int = int(os.getenv("UNSTRUCTURED_INITIAL_WAIT", "30"))  # Initial wait in seconds

    # Local processing toggle (bypass HTTP API inside container)
    UNSTRUCTURED_USE_LOCAL_PIPELINE: bool = os.getenv("UNSTRUCTURED_USE_LOCAL_PIPELINE", "false").lower() in {"1", "true", "yes"}

    # Strategy parameters
    HI_RES_STRATEGY: bool = os.getenv("HI_RES_STRATEGY", "true").lower() == "true"
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "20"))  # Pages per chunk
    UNSTRUCTURED_USE_TOC_SPLIT: bool = os.getenv("UNSTRUCTURED_USE_TOC_SPLIT", "false").lower() == "true"
    UNSTRUCTURED_SINGLE_CHUNK: bool = os.getenv("UNSTRUCTURED_SINGLE_CHUNK", "true").lower() not in {"false", "0", "no"}

    # Async job settings
    _async_toggle = os.getenv("ASYNC_UNSTRUCTURED")
    if _async_toggle is not None:
        UNSTRUCTURED_ASYNC_ENABLED: bool = _async_toggle.strip().lower() not in {"0", "false", "no"}
    else:
        UNSTRUCTURED_ASYNC_ENABLED: bool = os.getenv("UNSTRUCTURED_ASYNC_ENABLED", "true").lower() == "true"
    UNSTRUCTURED_JOB_POLL_INTERVAL: int = int(os.getenv("UNSTRUCTURED_JOB_POLL_INTERVAL", "5"))
    UNSTRUCTURED_JOB_TIMEOUT: int = int(os.getenv("UNSTRUCTURED_JOB_TIMEOUT", "3600"))

    # Pipeline state
    STATE_DIR: Path = Path(os.getenv("PIPELINE_STATE_DIR", "ingestion/state"))

    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        # Unstructured is local service, no API key required
        return True

    @classmethod
    def get_api_url(cls, index: int = 0) -> str:
        """
        Get API URL for specified container index (round-robin).

        Args:
            index: Container index for round-robin selection

        Returns:
            API URL string for the selected container
        """
        container_limit = min(cls.UNSTRUCTURED_CONTAINER_LIMIT, len(cls.UNSTRUCTURED_API_URLS))
        urls = cls.UNSTRUCTURED_API_URLS[:container_limit]
        return urls[index % len(urls)] if urls else cls.UNSTRUCTURED_API_URLS[0]

    @classmethod
    def get_retry_config(cls) -> dict:
        """Get retry configuration as dict."""
        return {
            "timeout": cls.UNSTRUCTURED_TIMEOUT,
            "max_retries": cls.UNSTRUCTURED_MAX_RETRIES,
            "backoff": cls.UNSTRUCTURED_RETRY_BACKOFF,
            "initial_wait": cls.UNSTRUCTURED_INITIAL_WAIT
        }
