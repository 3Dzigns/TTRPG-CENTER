# tests/functional/test_isolation.py
"""
Functional tests for environment isolation.
"""

import json
import os
from pathlib import Path

import pytest


def test_dev_run_writes_only_dev_logs(isolated_environment):
    """Test that running in dev environment only writes to dev logs."""
    envs = isolated_environment
    
    dev_logs = envs["dev"] / "logs"
    test_logs = envs["test"] / "logs"
    prod_logs = envs["prod"] / "logs"
    
    # Simulate dev environment run
    dev_log_file = dev_logs / "run.log"
    dev_log_file.write_text("DEV: Application started successfully\n")
    
    # Verify dev log exists and has correct content
    assert dev_log_file.exists()
    content = dev_log_file.read_text()
    assert "DEV:" in content
    assert "Application started" in content
    
    # Verify other environment logs are not affected
    test_files = list(test_logs.iterdir())
    prod_files = list(prod_logs.iterdir())
    
    assert len(test_files) == 0, f"Test logs contaminated: {test_files}"
    assert len(prod_files) == 0, f"Prod logs contaminated: {prod_files}"


def test_test_run_writes_only_test_logs(isolated_environment):
    """Test that running in test environment only writes to test logs."""
    envs = isolated_environment
    
    dev_logs = envs["dev"] / "logs"
    test_logs = envs["test"] / "logs"
    prod_logs = envs["prod"] / "logs"
    
    # Simulate test environment run
    test_log_file = test_logs / "run.log"
    test_log_file.write_text("TEST: Unit tests completed\n")
    
    # Verify test log exists
    assert test_log_file.exists()
    content = test_log_file.read_text()
    assert "TEST:" in content
    
    # Verify isolation
    dev_files = list(dev_logs.iterdir())
    prod_files = list(prod_logs.iterdir())
    
    assert len(dev_files) == 0
    assert len(prod_files) == 0


def test_environment_data_isolation(isolated_environment):
    """Test that data written in one environment doesn't appear in others."""
    envs = isolated_environment
    
    # Write unique data to each environment
    for env_name, env_root in envs.items():
        data_file = env_root / "data" / "application.json"
        data = {
            "environment": env_name,
            "timestamp": "2024-01-01T00:00:00Z",
            "unique_id": f"{env_name}_12345"
        }
        data_file.write_text(json.dumps(data, indent=2))
    
    # Verify each environment has only its own data
    for env_name, env_root in envs.items():
        data_file = env_root / "data" / "application.json"
        assert data_file.exists()
        
        data = json.loads(data_file.read_text())
        assert data["environment"] == env_name
        assert data["unique_id"] == f"{env_name}_12345"
        
        # Verify it doesn't contain data from other environments
        for other_env in envs.keys():
            if other_env != env_name:
                assert data["unique_id"] != f"{other_env}_12345"


def test_artifacts_isolation_by_environment(tmp_path):
    """Test that artifacts are properly isolated by environment."""
    # Set up artifacts directory structure
    artifacts_root = tmp_path / "artifacts"
    
    environments = ["dev", "test", "prod"]
    job_ids = ["job-001", "job-002", "job-003"]
    
    # Create artifacts for each environment
    for env in environments:
        env_artifacts = artifacts_root / env
        env_artifacts.mkdir(parents=True)
        
        for job_id in job_ids:
            job_dir = env_artifacts / job_id
            job_dir.mkdir()
            
            # Create environment-specific manifest
            manifest = {
                "job_id": job_id,
                "environment": env,
                "status": "completed",
                "artifacts": [f"{env}_{job_id}_chunk.json"]
            }
            (job_dir / "manifest.json").write_text(json.dumps(manifest))
            
            # Create environment-specific artifact
            artifact_data = {
                "environment": env,
                "job_id": job_id,
                "chunks": [f"chunk from {env} environment"]
            }
            (job_dir / f"{env}_{job_id}_chunk.json").write_text(json.dumps(artifact_data))
    
    # Verify isolation: each environment should only see its own artifacts
    for env in environments:
        env_artifacts = artifacts_root / env
        
        for job_id in job_ids:
            job_dir = env_artifacts / job_id
            manifest_file = job_dir / "manifest.json"
            
            assert manifest_file.exists()
            manifest = json.loads(manifest_file.read_text())
            
            # Verify environment isolation
            assert manifest["environment"] == env
            assert manifest["job_id"] == job_id
            
            # Verify artifact file exists and contains correct environment data
            artifact_file = job_dir / f"{env}_{job_id}_chunk.json"
            assert artifact_file.exists()
            
            artifact_data = json.loads(artifact_file.read_text())
            assert artifact_data["environment"] == env
            
            # Verify no cross-contamination from other environments
            for other_env in environments:
                if other_env != env:
                    wrong_artifact = job_dir / f"{other_env}_{job_id}_chunk.json"
                    assert not wrong_artifact.exists(), f"Found {other_env} artifact in {env} environment"


def test_config_isolation_prevents_cross_talk(isolated_environment):
    """Test that configuration in one environment doesn't affect others."""
    envs = isolated_environment
    
    # Set different configurations for each environment
    configs = {
        "dev": {"debug": True, "log_level": "DEBUG", "cache_ttl": 0},
        "test": {"debug": False, "log_level": "INFO", "cache_ttl": 5},
        "prod": {"debug": False, "log_level": "WARNING", "cache_ttl": 300}
    }
    
    # Write configs
    for env_name, config in configs.items():
        config_file = envs[env_name] / "config" / "app_config.json"
        config_file.write_text(json.dumps(config))
    
    # Verify each environment has correct config
    for env_name, expected_config in configs.items():
        config_file = envs[env_name] / "config" / "app_config.json"
        actual_config = json.loads(config_file.read_text())
        
        assert actual_config == expected_config
        
        # Verify config doesn't leak to other environments
        for other_env_name, other_env_root in envs.items():
            if other_env_name != env_name:
                other_config_file = other_env_root / "config" / "app_config.json"
                if other_config_file.exists():
                    other_config = json.loads(other_config_file.read_text())
                    assert other_config != actual_config


class TestConcurrentEnvironmentOperations:
    """Test concurrent operations across environments."""
    
    def test_simultaneous_writes_to_different_environments(self, isolated_environment):
        """Test that simultaneous writes to different environments don't interfere."""
        import threading
        import time
        
        envs = isolated_environment
        results = {}
        errors = []
        
        def write_to_env(env_name, env_root):
            try:
                # Write multiple files quickly
                for i in range(10):
                    data_file = env_root / "data" / f"concurrent_{i}.json"
                    data = {"env": env_name, "iteration": i, "timestamp": time.time()}
                    data_file.write_text(json.dumps(data))
                    time.sleep(0.001)  # Tiny delay
                
                results[env_name] = "success"
            except Exception as e:
                errors.append(f"Error in {env_name}: {str(e)}")
        
        # Start threads for each environment
        threads = []
        for env_name, env_root in envs.items():
            thread = threading.Thread(target=write_to_env, args=(env_name, env_root))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrent write errors: {errors}"
        assert len(results) == 3  # All environments should succeed
        
        # Verify all files were written correctly
        for env_name, env_root in envs.items():
            for i in range(10):
                data_file = env_root / "data" / f"concurrent_{i}.json"
                assert data_file.exists()
                
                data = json.loads(data_file.read_text())
                assert data["env"] == env_name
                assert data["iteration"] == i
    
    def test_environment_specific_job_processing(self, isolated_environment):
        """Test that job processing is correctly isolated per environment."""
        envs = isolated_environment
        
        # Simulate running the same job ID in different environments
        job_id = "isolation-test-001"
        
        for env_name, env_root in envs.items():
            # Create job directory
            job_dir = env_root / "data" / "jobs" / job_id
            job_dir.mkdir(parents=True)
            
            # Create job status file
            status = {
                "job_id": job_id,
                "environment": env_name,
                "status": "running",
                "phase": f"{env_name}_processing"
            }
            (job_dir / "status.json").write_text(json.dumps(status))
            
            # Create job log
            (job_dir / "job.log").write_text(f"[{env_name}] Job {job_id} processing\n")
        
        # Verify each environment has isolated job data
        for env_name, env_root in envs.items():
            job_dir = env_root / "data" / "jobs" / job_id
            
            # Check status file
            status_file = job_dir / "status.json"
            assert status_file.exists()
            
            status = json.loads(status_file.read_text())
            assert status["environment"] == env_name
            assert status["phase"] == f"{env_name}_processing"
            
            # Check log file
            log_file = job_dir / "job.log"
            log_content = log_file.read_text()
            assert f"[{env_name}]" in log_content
            
            # Verify no cross-contamination
            for other_env in envs.keys():
                if other_env != env_name:
                    assert f"[{other_env}]" not in log_content