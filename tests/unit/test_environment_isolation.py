"""
Unit tests for environment isolation functionality.

Tests MVP v2 environment isolation requirements and validation.
"""

import os
import pytest
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile

# Test imports
from src_common.environment_isolation import (
    EnvironmentValidator,
    EnvironmentIsolationError,
    validate_environment,
    validate_path_access,
    get_environment_config
)
from src_common.config import ConfigManager


class TestEnvironmentValidator:
    """Test EnvironmentValidator class."""

    def test_valid_environments(self):
        """Test that valid environments are recognized."""
        validator = EnvironmentValidator()

        assert "dev" in validator.VALID_ENVIRONMENTS
        assert "test" in validator.VALID_ENVIRONMENTS
        assert "prod" in validator.VALID_ENVIRONMENTS
        assert len(validator.VALID_ENVIRONMENTS) == 3

    def test_env_base_ports(self):
        """Test environment base port configuration."""
        validator = EnvironmentValidator()

        assert validator.ENV_BASE_PORTS["dev"] == 8000
        assert validator.ENV_BASE_PORTS["test"] == 8181
        assert validator.ENV_BASE_PORTS["prod"] == 8282

    @patch.dict(os.environ, {"TARGET_ENV": "test"})
    def test_detect_environment_target_env(self):
        """Test environment detection from TARGET_ENV."""
        validator = EnvironmentValidator()
        assert validator.current_env == "test"

    @patch.dict(os.environ, {"APP_ENV": "prod", "TARGET_ENV": ""}, clear=True)
    def test_detect_environment_app_env(self):
        """Test environment detection from APP_ENV."""
        validator = EnvironmentValidator()
        assert validator.current_env == "prod"

    @patch.dict(os.environ, {}, clear=True)
    def test_detect_environment_default(self):
        """Test environment detection defaults to dev."""
        validator = EnvironmentValidator()
        assert validator.current_env == "dev"

    @patch.dict(os.environ, {"TARGET_ENV": "invalid"})
    def test_detect_environment_invalid(self):
        """Test invalid environment defaults to dev."""
        validator = EnvironmentValidator()
        assert validator.current_env == "dev"

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_get_environment_config(self):
        """Test getting environment configuration."""
        validator = EnvironmentValidator()
        config = validator.get_environment_config()

        assert config["environment"] == "dev"
        assert config["base_port"] == 8000
        assert config["data_path"] == "env/dev/data"
        assert config["logs_path"] == "env/dev/logs"
        assert config["artifacts_path"] == "env/dev/artifacts"
        assert config["main_app_url"] == "http://localhost:8000"
        assert config["admin_api_url"] == "http://localhost:8001"

    @patch.dict(os.environ, {"TARGET_ENV": "test"})
    def test_get_environment_config_test(self):
        """Test getting test environment configuration."""
        validator = EnvironmentValidator()
        config = validator.get_environment_config()

        assert config["environment"] == "test"
        assert config["base_port"] == 8181
        assert config["main_app_url"] == "http://localhost:8181"
        assert config["admin_api_url"] == "http://localhost:8182"


class TestPathValidation:
    """Test path validation and access control."""

    @patch.dict(os.environ, {"TARGET_ENV": "dev", "CROSS_ENV_ACCESS_BLOCKED": "true"})
    def test_validate_path_access_same_environment(self):
        """Test path access within same environment is allowed."""
        validator = EnvironmentValidator()

        # Same environment paths should be allowed
        assert validator.validate_path_access("env/dev/data/test.txt") is True
        assert validator.validate_path_access("env/dev/logs/app.log") is True

    @patch.dict(os.environ, {"TARGET_ENV": "dev", "CROSS_ENV_ACCESS_BLOCKED": "true"})
    def test_validate_path_access_cross_environment_blocked(self):
        """Test cross-environment path access is blocked."""
        validator = EnvironmentValidator()

        # Cross-environment access should raise exception when blocked
        with pytest.raises(EnvironmentIsolationError):
            validator.validate_path_access("env/test/data/test.txt")

        with pytest.raises(EnvironmentIsolationError):
            validator.validate_path_access("env/prod/artifacts/job123")

    @patch.dict(os.environ, {"TARGET_ENV": "dev", "CROSS_ENV_ACCESS_BLOCKED": "false"})
    def test_validate_path_access_cross_environment_allowed(self):
        """Test cross-environment access when not blocked."""
        validator = EnvironmentValidator()

        # Cross-environment access should return False but not raise exception
        assert validator.validate_path_access("env/test/data/test.txt") is False
        assert validator.validate_path_access("env/prod/artifacts/job123") is False

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_validate_path_access_shared_paths(self):
        """Test shared paths are always allowed."""
        validator = EnvironmentValidator()

        # Shared paths should always be allowed
        assert validator.validate_path_access("src_common/config.py") is True
        assert validator.validate_path_access("scripts/validate-environment.py") is True
        assert validator.validate_path_access("config/policies.yaml") is True

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_validate_path_access_non_environment_paths(self):
        """Test non-environment-specific paths are allowed."""
        validator = EnvironmentValidator()

        # Non-environment paths should be allowed
        assert validator.validate_path_access("/tmp/temp_file.txt") is True
        assert validator.validate_path_access("./local_file.txt") is True


class TestEnvironmentValidation:
    """Test complete environment validation."""

    @patch.dict(os.environ, {"TARGET_ENV": "dev", "APP_ENV": "dev", "PORT": "8000"})
    def test_validate_environment_identity_success(self):
        """Test successful environment identity validation."""
        validator = EnvironmentValidator()
        result = validator._validate_environment_identity()

        assert result.startswith("PASS")

    @patch.dict(os.environ, {"APP_ENV": "dev"}, clear=True)
    def test_validate_environment_identity_missing_target(self):
        """Test environment validation with missing TARGET_ENV."""
        validator = EnvironmentValidator()
        result = validator._validate_environment_identity()

        assert result.startswith("FAIL")
        assert "TARGET_ENV not set" in result

    @patch.dict(os.environ, {"TARGET_ENV": "dev", "APP_ENV": "test"})
    def test_validate_environment_identity_mismatch(self):
        """Test environment validation with mismatched environments."""
        validator = EnvironmentValidator()
        result = validator._validate_environment_identity()

        assert result.startswith("FAIL")
        assert "mismatch" in result

    @patch.dict(os.environ, {
        "TARGET_ENV": "dev",
        "PORT": "8000",
        "ADMIN_API_PORT": "8001",
        "USER_API_PORT": "8002"
    })
    def test_validate_port_configuration_success(self):
        """Test successful port configuration validation."""
        validator = EnvironmentValidator()
        result = validator._validate_port_configuration()

        assert result.startswith("PASS")

    @patch.dict(os.environ, {
        "TARGET_ENV": "dev",
        "PORT": "9999",  # Wrong port for dev
        "ADMIN_API_PORT": "8001"
    })
    def test_validate_port_configuration_mismatch(self):
        """Test port configuration validation with wrong ports."""
        validator = EnvironmentValidator()
        result = validator._validate_port_configuration()

        assert result.startswith("FAIL")
        assert "port mismatch" in result


class TestConfigManager:
    """Test ConfigManager integration with environment isolation."""

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_config_manager_initialization(self):
        """Test ConfigManager initializes with environment validator."""
        config_manager = ConfigManager()

        assert config_manager.current_env == "dev"
        assert config_manager.env_validator is not None

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_get_service_url(self):
        """Test getting service URLs."""
        config_manager = ConfigManager()

        orchestrator_url = config_manager.get_service_url("orchestrator")
        assert orchestrator_url == "http://localhost:8004"

        admin_api_url = config_manager.get_service_url("admin_api")
        assert admin_api_url == "http://localhost:8001"

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_get_service_url_invalid(self):
        """Test getting invalid service URL raises error."""
        config_manager = ConfigManager()

        with pytest.raises(ValueError, match="Unknown service"):
            config_manager.get_service_url("invalid_service")

    @patch.dict(os.environ, {"TARGET_ENV": "dev", "CROSS_ENV_ACCESS_BLOCKED": "true"})
    def test_validate_path_with_isolation_error(self):
        """Test path validation with isolation error."""
        config_manager = ConfigManager()

        with pytest.raises(EnvironmentIsolationError):
            config_manager.validate_path("env/test/data/test.txt")

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_validate_path_relative_resolution(self):
        """Test relative path resolution."""
        config_manager = ConfigManager()

        resolved_path = config_manager.validate_path("./data/test.txt")
        assert "env/dev/data/test.txt" in resolved_path


class TestDatabaseConfigValidation:
    """Test database configuration validation."""

    @patch.dict(os.environ, {
        "TARGET_ENV": "dev",
        "CASSANDRA_KEYSPACE": "ttrpg_dev",
        "MONGO_URI": "mongodb://mongo-dev:27017/ttrpg_dev",
        "REDIS_URL": "redis://redis-dev:6379/0"
    })
    def test_database_config_environment_specific(self):
        """Test database configuration contains environment identifiers."""
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()

        assert "dev" in db_config.get("cassandra_keyspace", "")
        assert "dev" in db_config.get("mongo_uri", "")
        assert "dev" in db_config.get("redis_url", "")

    @patch.dict(os.environ, {
        "TARGET_ENV": "test",
        "CASSANDRA_KEYSPACE": "ttrpg_test",
        "MONGO_URI": "mongodb://mongo-test:27017/ttrpg_test",
        "REDIS_URL": "redis://redis-test:6379/1"
    })
    def test_database_config_test_environment(self):
        """Test test environment database configuration."""
        config_manager = ConfigManager()
        db_config = config_manager.get_database_config()

        assert "test" in db_config.get("cassandra_keyspace", "")
        assert "test" in db_config.get("mongo_uri", "")
        assert "test" in db_config.get("redis_url", "")


class TestProcessingConfig:
    """Test processing configuration."""

    @patch.dict(os.environ, {
        "TARGET_ENV": "dev",
        "PASS_B_SPLIT_THRESHOLD_MB": "10",
        "MAX_CONCURRENT_JOBS": "3",
        "PARALLEL_PROCESSING_ENABLED": "true"
    })
    def test_processing_config(self):
        """Test processing configuration retrieval."""
        config_manager = ConfigManager()
        processing_config = config_manager.get_processing_config()

        assert processing_config["pass_b_split_threshold_mb"] == 10
        assert processing_config["max_concurrent_jobs"] == 3
        assert processing_config["parallel_processing_enabled"] is True

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_processing_config_defaults(self):
        """Test processing configuration defaults."""
        config_manager = ConfigManager()
        processing_config = config_manager.get_processing_config()

        # Should use defaults when environment variables not set
        assert processing_config["pass_b_split_threshold_mb"] == 10  # MVP v2 default
        assert processing_config["max_file_size_mb"] == 100
        assert processing_config["max_concurrent_jobs"] == 3


# Integration tests
class TestEnvironmentIsolationIntegration:
    """Integration tests for environment isolation."""

    @patch.dict(os.environ, {"TARGET_ENV": "dev"})
    def test_full_validation_dev_environment(self):
        """Test full validation for dev environment."""
        # This test would normally create temporary environment structure
        # For unit tests, we'll mock the file system checks

        with patch('pathlib.Path.exists', return_value=True):
            results = validate_environment()

            # Should have validation results for all checks
            assert "environment_identity" in results
            assert "path_isolation" in results
            assert "port_configuration" in results

    def test_module_functions(self):
        """Test module-level functions."""
        # Test module-level functions work
        config = get_environment_config()
        assert isinstance(config, dict)
        assert "environment" in config

        # Test path validation function
        is_valid = validate_path_access("src_common/config.py")
        assert is_valid is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])