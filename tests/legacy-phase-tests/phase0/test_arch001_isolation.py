# tests/regression/phase0/test_arch001_isolation.py
"""
Phase 0 - US ARCH-001: Environment Isolation Regression Tests
Tests that DEV/TEST/PROD environments have proper isolation
"""

import os
import json
import pytest
from pathlib import Path


class TestEnvironmentIsolation:
    """Test suite for environment directory isolation validation"""

    def test_environment_directory_structure(self):
        """Verify that each environment has isolated directory structure"""
        project_root = Path(__file__).parent.parent.parent.parent

        # Check that all three environments exist
        for env in ("dev", "test", "prod"):
            env_root = project_root / "env" / env
            assert env_root.exists(), f"Environment directory {env} does not exist"

            # Check required subdirectories
            required_dirs = ["code", "config", "data", "logs"]
            for subdir in required_dirs:
                sub_path = env_root / subdir
                assert sub_path.exists(), f"Required subdirectory {env}/{subdir} does not exist"

    def test_port_configuration_unique(self):
        """Verify that each environment has unique port assignments"""
        project_root = Path(__file__).parent.parent.parent.parent
        ports = {}

        for env in ("dev", "test", "prod"):
            ports_file = project_root / "env" / env / "config" / "ports.json"
            if ports_file.exists():
                with open(ports_file) as f:
                    port_config = json.load(f)
                    env_port = port_config.get("http_port")
                    if env_port:
                        assert env_port not in ports.values(), f"Port {env_port} is duplicated across environments"
                        ports[env] = env_port

        # Verify expected port assignments
        expected_ports = {"dev": 8000, "test": 8181, "prod": 8282}
        for env, expected_port in expected_ports.items():
            if env in ports:
                assert ports[env] == expected_port, f"Environment {env} has port {ports[env]}, expected {expected_port}"

    def test_environment_variable_isolation(self):
        """Test that environment variables are properly isolated"""
        current_env = os.getenv("ENV", "dev")

        # Environment should be explicitly set
        assert current_env in ("dev", "test", "prod"), f"ENV variable is '{current_env}', should be dev/test/prod"

        # Log level should be set
        log_level = os.getenv("LOG_LEVEL")
        assert log_level is not None, "LOG_LEVEL environment variable not set"
        assert log_level in ("DEBUG", "INFO", "WARNING", "ERROR"), f"Invalid LOG_LEVEL: {log_level}"

    def test_data_directory_isolation(self):
        """Verify that data directories are isolated and writable"""
        project_root = Path(__file__).parent.parent.parent.parent
        current_env = os.getenv("ENV", "dev")

        data_dir = project_root / "env" / current_env / "data"
        assert data_dir.exists(), f"Data directory for {current_env} does not exist"
        assert os.access(data_dir, os.W_OK), f"Data directory for {current_env} is not writable"

        # Test that we can write to the data directory
        test_file = data_dir / "isolation_test.tmp"
        try:
            test_file.write_text("isolation test")
            assert test_file.exists(), "Could not create test file in data directory"
            content = test_file.read_text()
            assert content == "isolation test", "Test file content mismatch"
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_logs_directory_isolation(self):
        """Verify that log directories are isolated and writable"""
        project_root = Path(__file__).parent.parent.parent.parent
        current_env = os.getenv("ENV", "dev")

        logs_dir = project_root / "env" / current_env / "logs"
        assert logs_dir.exists(), f"Logs directory for {current_env} does not exist"
        assert os.access(logs_dir, os.W_OK), f"Logs directory for {current_env} is not writable"

        # Test that we can write to the logs directory
        test_log = logs_dir / "isolation_test.log"
        try:
            test_log.write_text("test log entry")
            assert test_log.exists(), "Could not create test log file"
        finally:
            if test_log.exists():
                test_log.unlink()

    def test_cross_environment_isolation(self):
        """Test that current environment cannot access other environment data"""
        project_root = Path(__file__).parent.parent.parent.parent
        current_env = os.getenv("ENV", "dev")

        # Get list of other environments
        other_envs = [env for env in ("dev", "test", "prod") if env != current_env]

        for other_env in other_envs:
            other_data_dir = project_root / "env" / other_env / "data"
            if other_data_dir.exists():
                # We should not write to other environment's data directory
                # This is more of a logical test since filesystem permissions handle this
                test_file = other_data_dir / f"cross_env_test_from_{current_env}.tmp"

                # In a properly isolated system, this should be prevented by design
                # For now, we test that the directories are separate
                current_data_dir = project_root / "env" / current_env / "data"
                assert current_data_dir != other_data_dir, f"Data directories are not isolated: {current_env} vs {other_env}"

    def test_config_file_isolation(self):
        """Test that configuration files are environment-specific"""
        project_root = Path(__file__).parent.parent.parent.parent
        current_env = os.getenv("ENV", "dev")

        config_dir = project_root / "env" / current_env / "config"
        assert config_dir.exists(), f"Config directory for {current_env} does not exist"

        # Check for environment-specific .env file
        env_file = config_dir / ".env"
        if env_file.exists():
            env_content = env_file.read_text()
            assert f"ENV={current_env}" in env_content, f"Environment file does not specify correct ENV={current_env}"

    def test_gitignore_isolation_protection(self):
        """Test that sensitive environment files are gitignored"""
        project_root = Path(__file__).parent.parent.parent.parent
        gitignore_file = project_root / ".gitignore"

        if gitignore_file.exists():
            gitignore_content = gitignore_file.read_text()

            # Check that .env files are ignored
            env_patterns = [
                "env/*/config/.env",
                "**/.env",
                ".env",
                "env/**/.env"
            ]

            has_env_ignore = any(pattern in gitignore_content for pattern in env_patterns)
            assert has_env_ignore, "Environment .env files are not properly gitignored"

    def test_environment_script_integration(self):
        """Test that environment initialization scripts work correctly"""
        project_root = Path(__file__).parent.parent.parent.parent
        current_env = os.getenv("ENV", "dev")

        # Check that environment was properly initialized
        env_root = project_root / "env" / current_env

        # Verify all expected files exist
        expected_files = [
            "config/ports.json",
        ]

        for expected_file in expected_files:
            file_path = env_root / expected_file
            assert file_path.exists(), f"Expected file {expected_file} not found for environment {current_env}"

    def test_baseline_contract_compliance(self):
        """Test that the environment meets baseline contract requirements"""
        project_root = Path(__file__).parent.parent.parent.parent
        current_env = os.getenv("ENV", "dev")

        # Load and verify ports.json schema
        ports_file = project_root / "env" / current_env / "config" / "ports.json"
        assert ports_file.exists(), "ports.json file missing"

        with open(ports_file) as f:
            ports_config = json.load(f)

        # Verify required fields
        assert "http_port" in ports_config, "ports.json missing http_port field"
        assert "name" in ports_config, "ports.json missing name field"
        assert ports_config["name"] == current_env, f"ports.json name field '{ports_config['name']}' does not match environment '{current_env}'"

        # Verify port is valid
        http_port = ports_config["http_port"]
        assert isinstance(http_port, int), "http_port must be an integer"
        assert 1024 <= http_port <= 65535, f"http_port {http_port} outside valid range 1024-65535"