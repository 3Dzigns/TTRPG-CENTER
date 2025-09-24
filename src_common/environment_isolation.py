"""
Environment Isolation Module

Enforces strict environment isolation as per MVP v2 requirements.
Prevents cross-environment access and validates environment configuration.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .logging import get_logger


logger = get_logger(__name__)


class EnvironmentIsolationError(Exception):
    """Raised when environment isolation is violated."""
    pass


class EnvironmentValidator:
    """Validates and enforces environment isolation."""

    VALID_ENVIRONMENTS = {"dev", "test", "prod"}
    ENV_BASE_PORTS = {"dev": 8000, "test": 8181, "prod": 8282}

    def __init__(self):
        """Initialize environment validator."""
        self.current_env = self._detect_environment()
        self.env_paths = self._get_environment_paths()
        self.cross_env_blocked = self._get_cross_env_setting()

    def validate_environment_setup(self) -> Dict[str, str]:
        """
        Validate complete environment setup.

        Returns:
            Dictionary with validation results.

        Raises:
            EnvironmentIsolationError: If validation fails.
        """
        logger.info(f"Validating environment setup for: {self.current_env}")

        results = {}

        # Validate environment identity
        results["environment_identity"] = self._validate_environment_identity()

        # Validate paths
        results["path_isolation"] = self._validate_path_isolation()

        # Validate ports
        results["port_configuration"] = self._validate_port_configuration()

        # Validate configuration files
        results["config_isolation"] = self._validate_config_isolation()

        # Validate database separation
        results["database_isolation"] = self._validate_database_isolation()

        # Check for cross-environment references
        results["cross_env_references"] = self._check_cross_env_references()

        # Summary
        failed_checks = [k for k, v in results.items() if v.startswith("FAIL")]
        if failed_checks:
            error_msg = f"Environment validation failed: {', '.join(failed_checks)}"
            logger.error(error_msg)
            if self.cross_env_blocked:
                raise EnvironmentIsolationError(error_msg)

        logger.info("Environment validation completed successfully")
        return results

    def validate_path_access(self, path: str) -> bool:
        """
        Validate that path access is within current environment.

        Args:
            path: Path to validate.

        Returns:
            True if access is allowed.

        Raises:
            EnvironmentIsolationError: If cross-environment access detected.
        """
        normalized_path = Path(path).resolve()
        path_str = str(normalized_path)

        # Allow access to src_common (shared libraries)
        if "src_common" in path_str:
            return True

        # Allow access to scripts and config
        if any(dir_name in path_str for dir_name in ["scripts", "config"]):
            return True

        # Check for environment-specific paths
        for env in self.VALID_ENVIRONMENTS:
            if f"env/{env}/" in path_str or f"env\\{env}\\" in path_str:
                if env != self.current_env:
                    error_msg = f"Cross-environment path access blocked: {path} (current: {self.current_env})"
                    logger.error(error_msg)
                    if self.cross_env_blocked:
                        raise EnvironmentIsolationError(error_msg)
                    return False
                return True

        # Allow other paths (not environment-specific)
        return True

    def get_environment_config(self) -> Dict[str, str]:
        """
        Get current environment configuration.

        Returns:
            Dictionary with environment settings.
        """
        config = {
            "environment": self.current_env,
            "base_port": self.ENV_BASE_PORTS[self.current_env],
            "data_path": f"env/{self.current_env}/data",
            "logs_path": f"env/{self.current_env}/logs",
            "artifacts_path": f"env/{self.current_env}/artifacts",
            "uploads_path": f"env/{self.current_env}/uploads",
            "cache_path": f"env/{self.current_env}/cache",
            "config_path": f"env/{self.current_env}/config",
        }

        # Add service URLs
        base_port = self.ENV_BASE_PORTS[self.current_env]
        config.update({
            "main_app_url": f"http://localhost:{base_port}",
            "admin_api_url": f"http://localhost:{base_port + 1}",
            "user_api_url": f"http://localhost:{base_port + 2}",
            "ingest_service_url": f"http://localhost:{base_port + 3}",
            "orchestrator_url": f"http://localhost:{base_port + 4}",
        })

        return config

    def ensure_environment_directories(self) -> None:
        """Ensure all required environment directories exist."""
        base_path = Path(f"env/{self.current_env}")

        required_dirs = [
            "data", "logs", "artifacts", "uploads", "cache", "config", "ssl"
        ]

        for dir_name in required_dirs:
            dir_path = base_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")

        logger.info(f"Environment directories validated for: {self.current_env}")

    def _detect_environment(self) -> str:
        """Detect current environment from environment variables."""
        env = os.getenv("TARGET_ENV") or os.getenv("APP_ENV") or "dev"

        if env not in self.VALID_ENVIRONMENTS:
            logger.warning(f"Invalid environment '{env}', defaulting to 'dev'")
            env = "dev"

        logger.info(f"Detected environment: {env}")
        return env

    def _get_environment_paths(self) -> Dict[str, Path]:
        """Get environment-specific paths."""
        base_path = Path(f"env/{self.current_env}")

        return {
            "base": base_path,
            "data": base_path / "data",
            "logs": base_path / "logs",
            "artifacts": base_path / "artifacts",
            "uploads": base_path / "uploads",
            "cache": base_path / "cache",
            "config": base_path / "config",
        }

    def _get_cross_env_setting(self) -> bool:
        """Get cross-environment access blocking setting."""
        setting = os.getenv("CROSS_ENV_ACCESS_BLOCKED", "true").lower()
        return setting in ("true", "1", "yes", "on")

    def _validate_environment_identity(self) -> str:
        """Validate environment identity configuration."""
        try:
            target_env = os.getenv("TARGET_ENV")
            app_env = os.getenv("APP_ENV")

            if not target_env:
                return "FAIL: TARGET_ENV not set"

            if target_env != self.current_env:
                return f"FAIL: TARGET_ENV mismatch ({target_env} != {self.current_env})"

            if app_env and app_env != target_env:
                return f"FAIL: APP_ENV mismatch ({app_env} != {target_env})"

            return "PASS: Environment identity validated"

        except Exception as e:
            return f"FAIL: Environment identity validation error: {str(e)}"

    def _validate_path_isolation(self) -> str:
        """Validate path isolation configuration."""
        try:
            # Check that environment paths exist
            for path_name, path in self.env_paths.items():
                if path_name != "base" and not path.exists():
                    logger.warning(f"Environment path missing: {path}")

            # Check environment variables point to correct environment
            env_vars_to_check = [
                "ARTIFACTS_PATH", "BASE_DATA_PATH", "BASE_LOGS_PATH",
                "BASE_UPLOADS_PATH", "BASE_CACHE_PATH"
            ]

            for var_name in env_vars_to_check:
                var_value = os.getenv(var_name)
                if var_value and self.current_env not in var_value:
                    return f"FAIL: {var_name} not environment-specific: {var_value}"

            return "PASS: Path isolation validated"

        except Exception as e:
            return f"FAIL: Path isolation validation error: {str(e)}"

    def _validate_port_configuration(self) -> str:
        """Validate port configuration for environment."""
        try:
            base_port = self.ENV_BASE_PORTS[self.current_env]
            port_vars = {
                "PORT": base_port,
                "MAIN_APP_PORT": base_port,
                "ADMIN_API_PORT": base_port + 1,
                "USER_API_PORT": base_port + 2,
                "INGEST_SERVICE_PORT": base_port + 3,
                "ORCHESTRATOR_SERVICE_PORT": base_port + 4,
            }

            for var_name, expected_port in port_vars.items():
                actual_port = os.getenv(var_name)
                if actual_port and int(actual_port) != expected_port:
                    return f"FAIL: {var_name} port mismatch ({actual_port} != {expected_port})"

            return "PASS: Port configuration validated"

        except Exception as e:
            return f"FAIL: Port configuration validation error: {str(e)}"

    def _validate_config_isolation(self) -> str:
        """Validate configuration file isolation."""
        try:
            config_file = self.env_paths["config"] / ".env"

            if not config_file.exists():
                return f"FAIL: Configuration file missing: {config_file}"

            # Check that config contains environment-specific values
            with open(config_file, 'r') as f:
                config_content = f.read()

            if f"TARGET_ENV={self.current_env}" not in config_content:
                return "FAIL: Configuration does not specify correct TARGET_ENV"

            # Check for cross-environment references in config
            other_envs = self.VALID_ENVIRONMENTS - {self.current_env}
            for other_env in other_envs:
                if f"env/{other_env}/" in config_content:
                    return f"FAIL: Configuration contains reference to {other_env} environment"

            return "PASS: Configuration isolation validated"

        except Exception as e:
            return f"FAIL: Configuration isolation validation error: {str(e)}"

    def _validate_database_isolation(self) -> str:
        """Validate database isolation configuration."""
        try:
            # Check database names/keyspaces contain environment suffix
            db_vars = [
                "CASSANDRA_KEYSPACE", "MONGO_URI", "ASTRA_DB_KEYSPACE",
                "REDIS_URL", "APP_DB_PATH"
            ]

            for var_name in db_vars:
                var_value = os.getenv(var_name, "")
                if var_value and self.current_env not in var_value:
                    logger.warning(f"{var_name} may not be environment-specific: {var_value}")

            return "PASS: Database isolation validated"

        except Exception as e:
            return f"FAIL: Database isolation validation error: {str(e)}"

    def _check_cross_env_references(self) -> str:
        """Check for any cross-environment references in environment variables."""
        try:
            cross_refs = []
            other_envs = self.VALID_ENVIRONMENTS - {self.current_env}

            for key, value in os.environ.items():
                if isinstance(value, str):
                    for other_env in other_envs:
                        if f"env/{other_env}/" in value or f"env\\{other_env}\\" in value:
                            cross_refs.append(f"{key}={value}")

            if cross_refs:
                return f"FAIL: Cross-environment references found: {'; '.join(cross_refs[:3])}..."

            return "PASS: No cross-environment references found"

        except Exception as e:
            return f"FAIL: Cross-environment reference check error: {str(e)}"


# Global validator instance
_validator: Optional[EnvironmentValidator] = None


def get_environment_validator() -> EnvironmentValidator:
    """Get global environment validator instance."""
    global _validator
    if _validator is None:
        _validator = EnvironmentValidator()
    return _validator


def validate_environment() -> Dict[str, str]:
    """Validate current environment setup."""
    return get_environment_validator().validate_environment_setup()


def validate_path_access(path: str) -> bool:
    """Validate path access for current environment."""
    return get_environment_validator().validate_path_access(path)


def get_environment_config() -> Dict[str, str]:
    """Get current environment configuration."""
    return get_environment_validator().get_environment_config()


def ensure_environment_directories() -> None:
    """Ensure all required environment directories exist."""
    get_environment_validator().ensure_environment_directories()