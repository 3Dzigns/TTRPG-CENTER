"""
Configuration Management with Environment Isolation

Provides centralized configuration management with strict environment isolation.
MVP v2 Environment Isolation Requirements.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from .environment_isolation import (
    get_environment_validator,
    validate_path_access,
    EnvironmentIsolationError
)
from .logging import get_logger


logger = get_logger(__name__)


class ConfigManager:
    """Configuration manager with environment isolation."""

    def __init__(self):
        """Initialize configuration manager."""
        self.env_validator = get_environment_validator()
        self.current_env = self.env_validator.current_env
        self._config_cache: Optional[Dict[str, Any]] = None

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with environment validation.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Configuration value.
        """
        # Load config if not cached
        if self._config_cache is None:
            self._load_environment_config()

        return self._config_cache.get(key, default)

    def get_environment_config(self) -> Dict[str, Any]:
        """
        Get complete environment configuration.

        Returns:
            Dictionary with environment configuration.
        """
        if self._config_cache is None:
            self._load_environment_config()

        return self._config_cache.copy()

    def validate_path(self, path: str) -> str:
        """
        Validate and resolve path with environment isolation.

        Args:
            path: Path to validate.

        Returns:
            Validated path.

        Raises:
            EnvironmentIsolationError: If path validation fails.
        """
        if not validate_path_access(path):
            raise EnvironmentIsolationError(f"Path access denied: {path}")

        # Resolve relative paths to environment-specific paths
        if path.startswith("./"):
            base_path = f"env/{self.current_env}"
            resolved_path = Path(base_path) / path[2:]
            return str(resolved_path)

        return path

    def get_service_url(self, service: str) -> str:
        """
        Get service URL for current environment.

        Args:
            service: Service name (orchestrator, admin_api, user_api, ingest).

        Returns:
            Service URL.
        """
        env_config = self.env_validator.get_environment_config()

        service_url_map = {
            "orchestrator": env_config["orchestrator_url"],
            "admin_api": env_config["admin_api_url"],
            "user_api": env_config["user_api_url"],
            "ingest": env_config["ingest_service_url"],
            "main_app": env_config.get("admin_api_url"),
            "test_runner": env_config.get("test_runner_url"),
        }

        if service not in service_url_map:
            raise ValueError(f"Unknown service: {service}")

        return service_url_map[service]

    def get_database_config(self) -> Dict[str, str]:
        """
        Get database configuration for current environment.

        Returns:
            Database configuration dict.
        """
        config = {}

        # AstraDB/Cassandra configuration
        if self.get_config("ASTRA_DB_API_ENDPOINT"):
            config.update({
                "astradb_endpoint": self.get_config("ASTRA_DB_API_ENDPOINT"),
                "astradb_token": self.get_config("ASTRA_DB_APPLICATION_TOKEN"),
                "astradb_keyspace": self.get_config("ASTRA_DB_KEYSPACE"),
                "astradb_region": self.get_config("ASTRA_DB_REGION"),
            })
        else:
            config.update({
                "cassandra_hosts": self.get_config("CASSANDRA_CONTACT_POINTS"),
                "cassandra_port": self.get_config("CASSANDRA_PORT", 9042),
                "cassandra_keyspace": self.get_config("CASSANDRA_KEYSPACE"),
                "cassandra_username": self.get_config("CASSANDRA_USERNAME"),
                "cassandra_password": self.get_config("CASSANDRA_PASSWORD"),
            })

        # Redis configuration
        config.update({
            "redis_url": self.get_config("REDIS_URL"),
            "redis_password": self.get_config("REDIS_PASSWORD"),
        })

        # MongoDB configuration
        config.update({
            "mongo_uri": self.get_config("MONGO_URI"),
            "mongo_username": self.get_config("MONGO_USERNAME"),
            "mongo_password": self.get_config("MONGO_PASSWORD"),
        })

        # Validate all database configs are environment-specific
        for key, value in config.items():
            if value and isinstance(value, str):
                if not any(env in value for env in ["dev", "test", "prod"]):
                    logger.warning(f"Database config {key} may not be environment-specific: {value}")

        return config

    def get_ai_model_config(self) -> Dict[str, str]:
        """
        Get AI model configuration.

        Returns:
            AI model configuration dict.
        """
        return {
            "openai_api_key": self.get_config("OPENAI_API_KEY"),
            "anthropic_api_key": self.get_config("ANTHROPIC_API_KEY"),
            "model_endpoint_base": self.get_config("MODEL_ENDPOINT_BASE", "https://api.openai.com/v1"),
        }

    def get_processing_config(self) -> Dict[str, Any]:
        """
        Get processing configuration.

        Returns:
            Processing configuration dict.
        """
        return {
            "pass_b_split_threshold_mb": int(self.get_config("PASS_B_SPLIT_THRESHOLD_MB", 10)),
            "max_file_size_mb": int(self.get_config("MAX_FILE_SIZE_MB", 100)),
            "max_concurrent_jobs": int(self.get_config("MAX_CONCURRENT_JOBS", 3)),
            "processing_timeout_seconds": int(self.get_config("PROCESSING_TIMEOUT_SECONDS", 1800)),
            "parallel_processing_enabled": self.get_config("PARALLEL_PROCESSING_ENABLED", "true").lower() == "true",
        }

    def _load_environment_config(self) -> None:
        """Load environment configuration from .env file."""
        try:
            # Ensure environment directories exist
            self.env_validator.ensure_environment_directories()

            # Load .env file for current environment
            env_file = Path(f"env/{self.current_env}/config/.env")

            if not env_file.exists():
                logger.warning(f"Environment config file not found: {env_file}")
                self._config_cache = {}
                return

            # Validate path access
            validate_path_access(str(env_file))

            # Load environment variables from file
            config = {}
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            config[key] = value

            # Add runtime environment config
            runtime_config = self.env_validator.get_environment_config()
            config.update(runtime_config)

            # Cache the configuration
            self._config_cache = config

            logger.info(f"Loaded configuration for environment: {self.current_env}")

        except Exception as e:
            logger.error(f"Failed to load environment config: {str(e)}")
            self._config_cache = {}


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """Get configuration value."""
    return get_config_manager().get_config(key, default)


def get_environment_config() -> Dict[str, Any]:
    """Get complete environment configuration."""
    return get_config_manager().get_environment_config()


def get_service_url(service: str) -> str:
    """Get service URL for current environment."""
    return get_config_manager().get_service_url(service)


def get_database_config() -> Dict[str, str]:
    """Get database configuration."""
    return get_config_manager().get_database_config()


def validate_config_path(path: str) -> str:
    """Validate and resolve configuration path."""
    return get_config_manager().validate_path(path)