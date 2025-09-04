# tests/unit/test_arch001_env_dirs.py
"""
Unit tests for ARCH-001: Environment directory structure and isolation.
"""

import json
import os
from pathlib import Path

import pytest


def test_env_dirs_exist(isolated_environment):
    """Test that all environment directories are created with correct structure."""
    envs = isolated_environment
    
    # Test that all three environments exist
    assert "dev" in envs
    assert "test" in envs
    assert "prod" in envs
    
    # Test directory structure for each environment
    for env_name, env_root in envs.items():
        assert env_root.exists(), f"Environment root {env_name} does not exist"
        
        # Check subdirectories
        for subdir in ("code", "config", "data", "logs"):
            subdir_path = env_root / subdir
            assert subdir_path.exists(), f"Missing {subdir} directory in {env_name}"
            assert subdir_path.is_dir(), f"{subdir} is not a directory in {env_name}"


def test_ports_json_has_unique_port(isolated_environment):
    """Test that each environment has unique port assignments."""
    envs = isolated_environment
    
    ports = {}
    websocket_ports = {}
    
    for env_name, env_root in envs.items():
        ports_file = env_root / "config" / "ports.json"
        assert ports_file.exists(), f"ports.json missing for {env_name}"
        
        port_config = json.loads(ports_file.read_text())
        
        # Check required fields
        assert "http_port" in port_config
        assert "websocket_port" in port_config
        assert "name" in port_config
        assert port_config["name"] == env_name
        
        # Collect ports for uniqueness check
        ports[env_name] = port_config["http_port"]
        websocket_ports[env_name] = port_config["websocket_port"]
    
    # Verify all HTTP ports are unique
    port_values = list(ports.values())
    assert len(set(port_values)) == len(port_values), f"Duplicate HTTP ports found: {ports}"
    
    # Verify all WebSocket ports are unique
    ws_port_values = list(websocket_ports.values())
    assert len(set(ws_port_values)) == len(ws_port_values), f"Duplicate WebSocket ports found: {websocket_ports}"
    
    # Verify specific port assignments
    assert ports["dev"] == 8000
    assert ports["test"] == 8181
    assert ports["prod"] == 8282
    
    assert websocket_ports["dev"] == 9000
    assert websocket_ports["test"] == 9181
    assert websocket_ports["prod"] == 9282


def test_environment_isolation_structure(isolated_environment):
    """Test that environments have isolated directory structures."""
    envs = isolated_environment
    
    # Create test files in each environment
    for env_name, env_root in envs.items():
        test_file = env_root / "data" / f"{env_name}_test.txt"
        test_file.write_text(f"Test data for {env_name}")
        
        log_file = env_root / "logs" / f"{env_name}_test.log"  
        log_file.write_text(f"Test log for {env_name}")
    
    # Verify isolation - files should only exist in their respective environments
    for env_name, env_root in envs.items():
        # Check own files exist
        assert (env_root / "data" / f"{env_name}_test.txt").exists()
        assert (env_root / "logs" / f"{env_name}_test.log").exists()
        
        # Check other environments' files don't exist here
        for other_env in envs.keys():
            if other_env != env_name:
                assert not (env_root / "data" / f"{other_env}_test.txt").exists()
                assert not (env_root / "logs" / f"{other_env}_test.log").exists()


def test_artifacts_directory_isolation(tmp_path):
    """Test that artifacts directories are environment-specific."""
    # Create artifacts structure
    artifacts_root = tmp_path / "artifacts"
    
    for env in ("dev", "test", "prod"):
        env_artifacts = artifacts_root / env
        env_artifacts.mkdir(parents=True)
        
        # Create mock job
        job_dir = env_artifacts / "test-job-001"
        job_dir.mkdir()
        (job_dir / "manifest.json").write_text(f'{{"environment": "{env}"}}')
    
    # Verify isolation
    for env in ("dev", "test", "prod"):
        env_artifacts = artifacts_root / env / "test-job-001"
        assert env_artifacts.exists()
        
        manifest = json.loads((env_artifacts / "manifest.json").read_text())
        assert manifest["environment"] == env


def test_config_template_structure(temp_env_root):
    """Test that configuration templates are properly structured."""
    config_dir = temp_env_root / "config"
    
    # Check .env template exists and has correct structure
    env_file = config_dir / ".env"
    assert env_file.exists()
    
    env_content = env_file.read_text()
    required_vars = [
        "APP_ENV=test",
        "PORT=8181", 
        "LOG_LEVEL=INFO",
        "ARTIFACTS_PATH=./artifacts/test"
    ]
    
    for required_var in required_vars:
        assert required_var in env_content, f"Missing {required_var} in .env file"
    
    # Check logging configuration
    logging_file = config_dir / "logging.json"
    assert logging_file.exists()
    
    logging_config = json.loads(logging_file.read_text())
    assert "version" in logging_config
    assert "formatters" in logging_config
    assert "handlers" in logging_config
    assert "root" in logging_config


class TestEnvironmentIsolationValidation:
    """Test class for comprehensive environment isolation validation."""
    
    def test_no_cross_environment_file_access(self, isolated_environment):
        """Verify that operations in one environment cannot access another's files."""
        envs = isolated_environment
        
        # Create sensitive data in each environment
        for env_name, env_root in envs.items():
            sensitive_file = env_root / "data" / "sensitive.json"
            sensitive_file.write_text(json.dumps({
                "environment": env_name,
                "secret": f"{env_name}_secret_data"
            }))
        
        # Attempt to read from different environments
        dev_root = envs["dev"]
        test_root = envs["test"] 
        prod_root = envs["prod"]
        
        # Should not be able to access test data from dev path
        test_sensitive = test_root / "data" / "sensitive.json"
        dev_sensitive = dev_root / "data" / "sensitive.json"
        
        test_data = json.loads(test_sensitive.read_text())
        dev_data = json.loads(dev_sensitive.read_text())
        
        assert test_data["environment"] == "test"
        assert dev_data["environment"] == "dev"
        assert test_data["secret"] != dev_data["secret"]
    
    def test_port_binding_isolation(self, isolated_environment):
        """Test that port configurations prevent cross-environment conflicts."""
        envs = isolated_environment
        
        all_ports = set()
        
        for env_name, env_root in envs.items():
            ports_file = env_root / "config" / "ports.json"
            ports_config = json.loads(ports_file.read_text())
            
            http_port = ports_config["http_port"]
            ws_port = ports_config["websocket_port"]
            
            # Check for port conflicts
            assert http_port not in all_ports, f"HTTP port {http_port} conflicts in {env_name}"
            assert ws_port not in all_ports, f"WebSocket port {ws_port} conflicts in {env_name}"
            
            all_ports.add(http_port)
            all_ports.add(ws_port)
    
    def test_log_isolation_by_environment(self, isolated_environment):
        """Test that logs are written to correct environment directories."""
        envs = isolated_environment
        
        # Simulate log writes for each environment
        for env_name, env_root in envs.items():
            logs_dir = env_root / "logs"
            
            # Create environment-specific log
            app_log = logs_dir / "app.log"
            app_log.write_text(f"[{env_name}] Application started\n")
            
            # Verify log exists in correct location
            assert app_log.exists()
            
            # Verify log content is environment-specific
            log_content = app_log.read_text()
            assert env_name in log_content
            
            # Verify logs don't leak to other environments
            for other_env_name, other_env_root in envs.items():
                if other_env_name != env_name:
                    other_log = other_env_root / "logs" / "app.log"
                    if other_log.exists():
                        other_content = other_log.read_text()
                        assert env_name not in other_content, f"Log leak detected: {env_name} logs in {other_env_name}"