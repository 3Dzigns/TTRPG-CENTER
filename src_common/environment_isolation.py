"""
Environment Isolation Module

Enforces strict environment isolation as per MVP v2 requirements.
Prevents cross-environment access and validates environment configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from .logging import get_logger


logger = get_logger(__name__)


class EnvironmentIsolationError(Exception):
    """Raised when environment isolation is violated."""
    pass


class EnvironmentValidator:
    """Validates and enforces environment isolation."""

    VALID_ENVIRONMENTS = {"dev", "test", "prod"}
    ENV_BASE_PORTS = {"dev": 8000, "test": 8181, "prod": 8282}
    TEST_RUNNER_PORTS = {"dev": 8095, "test": 8195, "prod": 8295}

    def __init__(self):
        """Initialize environment validator."""
        self.current_env = self._detect_environment()
        self.env_paths = self._get_environment_paths()
        self.cross_env_blocked = self._get_cross_env_setting()
        self.environment_name = self.current_env

    def validate_environment_setup(self) -> Dict[str, str]:
        """Validate complete environment setup."""
        logger.info(f"Validating environment setup for: {self.current_env}")

        results: Dict[str, str] = {}
        results["environment_identity"] = self._validate_environment_identity()
        results["path_isolation"] = self._validate_path_isolation()
        results["port_configuration"] = self._validate_port_configuration()
        results["config_isolation"] = self._validate_config_isolation()
        results["database_isolation"] = self._validate_database_isolation()
        results["cross_env_references"] = self._check_cross_env_references()

        failed_checks = [k for k, v in results.items() if v.startswith("FAIL")]
        if failed_checks:
            error_msg = f"Environment validation failed: {', '.join(failed_checks)}"
            logger.error(error_msg)
            if self.cross_env_blocked:
                raise EnvironmentIsolationError(error_msg)

        logger.info("Environment validation completed successfully")
        return results


    def validate_path_access(self, path: str) -> bool:
        """Validate that path access is within current environment."""
        normalized_path = Path(path).resolve()
        path_str = str(normalized_path)
        normalized_str = path_str.replace("\\", "/")

        if "src_common" in normalized_str:
            return True
        if any(dir_name in normalized_str for dir_name in ["scripts", "config"]):
            return True

        for env in self.VALID_ENVIRONMENTS:
            marker = f"env/{env}/"
            if marker in normalized_str:
                if env != self.current_env:
                    error_msg = f"Cross-environment path access blocked: {path} (current: {self.current_env})"
                    logger.error(error_msg)
                    if self.cross_env_blocked:
                        raise EnvironmentIsolationError(error_msg)
                    return False
                return True

        return True

    def get_environment_config(self) -> Dict[str, str]:
        """Get current environment configuration."""
        env_root = Path(f"env/{self.current_env}")
        base_port = self.ENV_BASE_PORTS[self.current_env]
        service_ports = {
            "main_app_port": base_port,
            "admin_api_port": base_port + 1,
            "user_api_port": base_port + 2,
            "ingest_service_port": base_port + 3,
            "orchestrator_service_port": base_port + 4,
            "test_runner_port": self.TEST_RUNNER_PORTS[self.current_env],
        }

        config: Dict[str, str] = {
            "environment": self.current_env,
            "base_port": base_port,
            "code_path": str(env_root / "code"),
            "data_path": str(env_root / "data"),
            "logs_path": str(env_root / "logs"),
            "artifacts_path": str(env_root / "artifacts"),
            "uploads_path": str(env_root / "uploads"),
            "cache_path": str(env_root / "cache"),
            "config_path": str(env_root / "config"),
            "ssl_path": str(env_root / "ssl"),
        }
        config.update(service_ports)
        config.update({
            "admin_api_url": f"http://localhost:{service_ports['admin_api_port']}",
            "user_api_url": f"http://localhost:{service_ports['user_api_port']}",
            "ingest_service_url": f"http://localhost:{service_ports['ingest_service_port']}",
            "orchestrator_url": f"http://localhost:{service_ports['orchestrator_service_port']}",
            "test_runner_url": f"http://localhost:{service_ports['test_runner_port']}",
        })
        config["main_app_url"] = config["admin_api_url"]
        return config

    def get_environment_root(self) -> str:
        """Return the filesystem root for the current environment."""
        return str(self.env_paths["base"])

    def ensure_environment_directories(self) -> None:
        """Ensure all required environment directories exist."""
        required_dirs = [
            "code",
            "config",
            "data",
            "logs",
            "artifacts",
            "cache",
            "uploads",
            "ssl",
        ]

        for dir_name in required_dirs:
            dir_path = self.env_paths["base"] / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {dir_path}")

        logger.info(f"Environment directories validated for: {self.current_env}")

    def _detect_environment(self) -> str:
        env = os.getenv("TARGET_ENV") or os.getenv("APP_ENV") or "dev"
        if env not in self.VALID_ENVIRONMENTS:
            logger.warning(f"Invalid environment '{env}', defaulting to 'dev'")
            env = "dev"
        logger.info(f"Detected environment: {env}")
        return env

    def _get_environment_paths(self) -> Dict[str, Path]:
        base_path = Path(f"env/{self.current_env}")
        return {
            "base": base_path,
            "code": base_path / "code",
            "data": base_path / "data",
            "logs": base_path / "logs",
            "artifacts": base_path / "artifacts",
            "uploads": base_path / "uploads",
            "cache": base_path / "cache",
            "config": base_path / "config",
            "ssl": base_path / "ssl",
        }

    def _get_cross_env_setting(self) -> bool:
        """Get cross-environment access blocked setting from environment variable."""
        setting = os.getenv("CROSS_ENV_ACCESS_BLOCKED", "true").lower()
        return setting in ("true", "1", "yes", "on")

    def set_environment(self, environment: str) -> None:
        """Explicitly set the active environment context."""
        if environment not in self.VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid environment: {environment}")
        if environment == self.current_env:
            return
        logger.info(f"Switching environment context from {self.current_env} to {environment}")
        self.current_env = environment
        self.environment_name = environment
        self.env_paths = self._get_environment_paths()
        self.cross_env_blocked = self._get_cross_env_setting()
        self.ensure_environment_directories()

    def get_environment_info(self) -> Dict[str, Dict[str, str]]:
        """Return structured environment metadata for callers expecting legacy payloads."""
        paths = {
            'base_path': str(self.env_paths['base']),
            'code_path': str(self.env_paths['code']),
            'data_path': str(self.env_paths['data']),
            'logs_path': str(self.env_paths['logs']),
            'artifacts_path': str(self.env_paths['artifacts']),
            'uploads_path': str(self.env_paths['uploads']),
            'cache_path': str(self.env_paths['cache']),
            'config_path': str(self.env_paths['config']),
            'ssl_path': str(self.env_paths['ssl']),
        }
        return {
            'environment': self.current_env,
            'paths': paths,
        }
    def _validate_environment_identity(self) -> str:
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
        except Exception as exc:
            return f"FAIL: Environment identity validation error: {exc}"

    def _validate_path_isolation(self) -> str:
        try:
            for path_name, path in self.env_paths.items():
                if path_name != "base" and not path.exists():
                    logger.warning(f"Environment path missing: {path}")

            env_vars_to_check = [
                "CODE_ROOT",
                "DATA_PATH",
                "LOGS_PATH",
                "ARTIFACTS_PATH",
                "UPLOADS_PATH",
                "CACHE_PATH",
                "SSL_PATH",
                # Backwards compatibility
                "BASE_DATA_PATH",
                "BASE_LOGS_PATH",
                "BASE_UPLOADS_PATH",
                "BASE_CACHE_PATH",
            ]

            for var_name in env_vars_to_check:
                var_value = os.getenv(var_name)
                if var_value and self.current_env not in var_value:
                    return f"FAIL: {var_name} not environment-specific: {var_value}"

            return "PASS: Path isolation validated"
        except Exception as exc:
            return f"FAIL: Path isolation validation error: {exc}"

    def _validate_port_configuration(self) -> str:
        try:
            base_port = self.ENV_BASE_PORTS[self.current_env]
            port_vars = {
                "PORT": base_port,
                "MAIN_APP_PORT": base_port,
                "ADMIN_API_PORT": base_port + 1,
                "USER_API_PORT": base_port + 2,
                "INGEST_SERVICE_PORT": base_port + 3,
                "ORCHESTRATOR_SERVICE_PORT": base_port + 4,
                "TEST_RUNNER_PORT": self.TEST_RUNNER_PORTS[self.current_env],
            }

            for var_name, expected_port in port_vars.items():
                actual_port = os.getenv(var_name)
                if actual_port and int(actual_port) != expected_port:
                    return f"FAIL: {var_name} port mismatch ({actual_port} != {expected_port})"

            return "PASS: Port configuration validated"
        except Exception as exc:
            return f"FAIL: Port configuration validation error: {exc}"

    def _validate_config_isolation(self) -> str:
        try:
            config_file = self.env_paths["config"] / ".env"
            if not config_file.exists():
                return f"FAIL: Configuration file missing: {config_file}"

            with open(config_file, "r", encoding="utf-8") as handle:
                config_content = handle.read()

            if f"TARGET_ENV={self.current_env}" not in config_content:
                return "FAIL: Configuration does not specify correct TARGET_ENV"

            other_envs = self.VALID_ENVIRONMENTS - {self.current_env}
            for other_env in other_envs:
                if f"env/{other_env}/" in config_content:
                    return f"FAIL: Configuration contains reference to {other_env} environment"

            return "PASS: Configuration isolation validated"
        except Exception as exc:
            return f"FAIL: Configuration isolation validation error: {exc}"

    def _validate_database_isolation(self) -> str:
        try:
            db_vars = [
                "CASSANDRA_KEYSPACE",
                "MONGO_URI",
                "ASTRA_DB_KEYSPACE",
                "REDIS_URL",
                "APP_DB_PATH",
            ]

            for var_name in db_vars:
                var_value = os.getenv(var_name, "")
                if var_value and self.current_env not in var_value:
                    logger.warning(f"{var_name} may not be environment-specific: {var_value}")

            return "PASS: Database isolation validated"
        except Exception as exc:
            return f"FAIL: Database isolation validation error: {exc}"

    def _check_cross_env_references(self) -> str:
        try:
            cross_refs: List[str] = []
            other_envs = self.VALID_ENVIRONMENTS - {self.current_env}

            for key, value in os.environ.items():
                if isinstance(value, str):
                    for other_env in other_envs:
                        if f"env/{other_env}/" in value or f"env\\{other_env}" in value:
                            cross_refs.append(f"{key}={value}")

            if cross_refs:
                return f"FAIL: Cross-environment references found: {'; '.join(cross_refs[:3])}..."

            return "PASS: No cross-environment references found"
        except Exception as exc:
            return f"FAIL: Cross-environment reference check error: {exc}"


_validator: Optional[EnvironmentValidator] = None


def get_environment_validator() -> EnvironmentValidator:
    global _validator
    requested_env = os.getenv("TARGET_ENV") or os.getenv("APP_ENV") or "dev"
    if _validator is None or _validator.current_env != requested_env:
        _validator = EnvironmentValidator()
    return _validator


def validate_environment() -> Dict[str, str]:
    return get_environment_validator().validate_environment_setup()


def validate_path_access(path: str) -> bool:
    return get_environment_validator().validate_path_access(path)


def get_environment_config() -> Dict[str, str]:
    return get_environment_validator().get_environment_config()


def get_environment_root() -> str:
    return get_environment_validator().get_environment_root()


def ensure_environment_directories() -> None:
    get_environment_validator().ensure_environment_directories()

