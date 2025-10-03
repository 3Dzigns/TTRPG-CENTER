"""
Configuration management for pipeline-worker microservice.
"""

import os
from typing import Dict
from pydantic import BaseModel


class PipelineWorkerConfig(BaseModel):
    """Service configuration with environment awareness."""

    # Service identity
    service_name: str = "pipeline-worker"
    service_version: str = "1.0.0"
    port: int = 8006

    # Environment
    target_env: str = os.getenv("TARGET_ENV", "dev")

    # Worker pool configuration
    default_pool_size: int = 2
    worker_pools: Dict[str, int] = {
        "pass_0": 2,
        "pass_a": 2,
        "pass_b": 2,
        "pass_c": 2,
        "pass_d": 2,
        "pass_e": 2,
        "pass_f": 2,
        "pass_g": 2,
    }

    # Job queue configuration
    max_queue_size: int = 100
    job_timeout_seconds: int = 3600  # 1 hour

    # Pipeline paths
    base_path: str = os.getenv("BASE_PATH", "/app")
    upload_path_template: str = "{base_path}/env/{env}/uploads"
    artifacts_path_template: str = "{base_path}/artifacts/ingest/{env}/{job_id}"

    # Pass execution configuration
    pass_0_enabled: bool = True
    pass_a_enabled: bool = True
    pass_b_enabled: bool = True
    pass_c_enabled: bool = True
    pass_d_enabled: bool = True
    pass_e_enabled: bool = True
    pass_f_enabled: bool = True
    pass_g_enabled: bool = True

    # Monitoring and metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    websocket_enabled: bool = True

    # Health check configuration
    health_check_interval_seconds: int = 30

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    structured_logging: bool = True

    model_config = {"arbitrary_types_allowed": True}

    def get_upload_path(self, env: str = None) -> str:
        """Get upload directory path for environment."""
        env = env or self.target_env
        return self.upload_path_template.format(
            base_path=self.base_path,
            env=env
        )

    def get_artifacts_path(self, env: str, job_id: str) -> str:
        """Get artifacts directory path for job."""
        return self.artifacts_path_template.format(
            base_path=self.base_path,
            env=env,
            job_id=job_id
        )

    def get_pool_size(self, pass_type: str) -> int:
        """Get worker pool size for pass type."""
        return self.worker_pools.get(pass_type, self.default_pool_size)

    def is_pass_enabled(self, pass_type: str) -> bool:
        """Check if pass is enabled."""
        attr_name = f"{pass_type}_enabled"
        return getattr(self, attr_name, False)


# Global configuration instance
config = PipelineWorkerConfig()