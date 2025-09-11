#!/usr/bin/env python3
"""
Integration tests for FR-002 environment-specific scheduling functionality.

Tests the complete integration of scheduling system across different environments:
- Environment isolation and configuration management
- Cross-environment job scheduling and coordination  
- Environment-specific resource limits and policies
- Configuration inheritance and override patterns
- Multi-environment deployment and promotion workflows
- Environment-specific monitoring and alerting
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from typing import Dict, List, Optional, Any

# Test framework imports
from tests.conftest import BaseTestCase, TestEnvironment, MockPipeline
from src_common.logging import get_logger

# Import scheduler components (to be implemented)
try:
    from src_common.scheduler_engine import SchedulingEngine, CronParser
    from src_common.job_manager import JobManager, JobQueue, Job, JobStatus
    from src_common.scheduled_processor import ScheduledBulkProcessor
    from src_common.environment_manager import EnvironmentManager
    from src_common.config_manager import ConfigManager
except ImportError:
    # Mock imports for testing before implementation
    SchedulingEngine = Mock
    CronParser = Mock
    JobManager = Mock
    JobQueue = Mock
    Job = Mock
    JobStatus = Mock
    ScheduledBulkProcessor = Mock
    EnvironmentManager = Mock
    ConfigManager = Mock

logger = get_logger(__name__)


class TestEnvironmentSpecificScheduling(BaseTestCase):
    """Test environment-specific scheduling configurations and isolation."""
    
    @pytest.fixture(autouse=True)
    def setup_multi_environment_testing(self, temp_env_dir):
        """Set up multi-environment testing infrastructure."""
        self.base_env_dir = temp_env_dir
        
        # Create environment-specific directories
        self.environments = ["dev", "test", "prod"]
        self.env_dirs = {}
        self.env_configs = {}
        
        for env in self.environments:
            env_dir = self.base_env_dir / f"env_{env}"
            env_dir.mkdir(parents=True, exist_ok=True)
            self.env_dirs[env] = env_dir
            
            # Create environment-specific subdirectories
            (env_dir / "config").mkdir(exist_ok=True)
            (env_dir / "data").mkdir(exist_ok=True)
            (env_dir / "logs").mkdir(exist_ok=True)
            (env_dir / "artifacts" / "ingest" / env).mkdir(parents=True, exist_ok=True)
            (env_dir / "uploads").mkdir(exist_ok=True)
            (env_dir / "queue_state").mkdir(exist_ok=True)
            
            # Create environment-specific configuration
            self.env_configs[env] = self.create_environment_config(env, env_dir)
            
            # Write configuration file
            config_file = env_dir / "config" / ".env"
            self.write_environment_config(config_file, self.env_configs[env])
    
    def create_environment_config(self, env: str, env_dir: Path) -> Dict[str, Any]:
        """Create environment-specific configuration."""
        base_config = {
            "ENVIRONMENT": env,
            "ENV_DIR": str(env_dir),
            "UPLOAD_DIRECTORIES": str(env_dir / "uploads"),
            "ARTIFACTS_BASE": str(env_dir / "artifacts" / "ingest" / env),
            "QUEUE_STATE_DIR": str(env_dir / "queue_state"),
            "LOG_LEVEL": "DEBUG" if env == "dev" else "INFO",
            "DATABASE_URL": f"astradb://localhost/{env}_keyspace",
            "API_RATE_LIMIT": 100 if env == "dev" else 50,
            "JOB_TIMEOUT_SECONDS": 600 if env == "dev" else 300,
            "RETRY_ATTEMPTS": 5 if env == "dev" else 3,
            "ENABLE_DEBUG_MODE": str(env == "dev").lower(),
        }
        
        # Environment-specific overrides
        if env == "dev":
            base_config.update({
                "PORT": 8000,
                "MAX_CONCURRENT_JOBS": 4,
                "SCAN_INTERVAL_SECONDS": 10,
                "SCHEDULE_DEFAULT": "*/15 * * * *",  # Every 15 minutes for testing
                "ENABLE_HOT_RELOAD": "true",
                "CACHE_TTL_SECONDS": 5
            })
        elif env == "test":
            base_config.update({
                "PORT": 8181,
                "MAX_CONCURRENT_JOBS": 2,
                "SCAN_INTERVAL_SECONDS": 30,
                "SCHEDULE_DEFAULT": "0 1 * * *",  # 1 AM daily
                "ENABLE_MOCK_SERVICES": "true",
                "CACHE_TTL_SECONDS": 60
            })
        elif env == "prod":
            base_config.update({
                "PORT": 8282,
                "MAX_CONCURRENT_JOBS": 8,
                "SCAN_INTERVAL_SECONDS": 60,
                "SCHEDULE_DEFAULT": "0 2 * * *",  # 2 AM daily
                "ENABLE_STRICT_VALIDATION": "true",
                "CACHE_TTL_SECONDS": 300
            })
        
        return base_config
    
    def write_environment_config(self, config_file: Path, config: Dict[str, Any]):
        """Write environment configuration to .env file."""
        with open(config_file, 'w') as f:
            for key, value in config.items():
                f.write(f"{key}={value}\n")


class TestEnvironmentIsolation(TestEnvironmentSpecificScheduling):
    """Test proper isolation between different environments."""
    
    @pytest.mark.asyncio
    async def test_complete_environment_isolation(self):
        """Test that environments are completely isolated from each other."""
        # Create scheduler instances for each environment
        schedulers = {}
        job_managers = {}
        
        for env in self.environments:
            config = self.env_configs[env].copy()
            
            schedulers[env] = SchedulingEngine(config=config)
            job_managers[env] = JobManager(
                config=config,
                pipeline=self.create_mock_pipeline(env)
            )
        
        # Create jobs in each environment
        job_ids = {}
        for env in self.environments:
            job_id = job_managers[env].create_job(
                name=f"{env}_isolation_test_job",
                job_type="bulk_ingestion",
                source_path=str(self.env_dirs[env] / "uploads" / "test_document.pdf"),
                environment=env,
                priority=1
            )
            job_ids[env] = job_id
        
        # Verify job isolation - each manager should only see its own jobs
        for env in self.environments:
            env_jobs = job_managers[env].get_all_jobs()
            assert len(env_jobs) == 1
            assert env_jobs[0].id == job_ids[env]
            assert env_jobs[0].environment == env
            
            # Verify job is not visible in other environments
            for other_env in self.environments:
                if other_env != env:
                    other_jobs = job_managers[other_env].get_all_jobs()
                    other_job_ids = [job.id for job in other_jobs]
                    assert job_ids[env] not in other_job_ids
    
    @pytest.mark.asyncio
    async def test_environment_specific_directory_isolation(self):
        """Test that each environment uses its own directories and file paths."""
        processors = {}
        
        for env in self.environments:
            config = self.env_configs[env].copy()
            processors[env] = ScheduledBulkProcessor(
                config=config,
                pipeline=self.create_mock_pipeline(env)
            )
        
        # Track directory usage for each environment
        directory_usage = {env: set() for env in self.environments}
        
        def track_directory_usage(env):
            def mock_process(*args, **kwargs):
                # Extract directory paths from arguments
                for arg in args:
                    if isinstance(arg, str) and "env_" in arg:
                        directory_usage[env].add(arg)
                
                for key, value in kwargs.items():
                    if isinstance(value, str) and "env_" in value:
                        directory_usage[env].add(value)
                
                return {
                    "job_id": f"{env}_directory_test",
                    "status": "completed",
                    "environment": env,
                    "directories_used": list(directory_usage[env])
                }
            return mock_process
        
        # Create test documents in each environment
        for env in self.environments:
            test_doc = self.env_dirs[env] / "uploads" / "directory_test.pdf"
            test_doc.write_bytes(b"%PDF-1.4\nTest content\n%%EOF")
            
            # Mock pipeline to track directory usage
            processors[env].pipeline.process_source.side_effect = track_directory_usage(env)
        
        # Execute jobs in each environment
        jobs = {}
        for env in self.environments:
            job = Job(
                id=f"{env}_directory_isolation_job",
                name=f"{env}_directory_test",
                job_type="bulk_ingestion",
                source_path=str(self.env_dirs[env] / "uploads" / "directory_test.pdf"),
                environment=env,
                priority=1,
                created_at=datetime.now(),
                status=JobStatus.PENDING
            )
            jobs[env] = job
        
        # Execute all jobs
        results = {}
        for env in self.environments:
            results[env] = await processors[env].execute_job(jobs[env])
        
        # Verify directory isolation
        for env in self.environments:
            env_directories = directory_usage[env]
            
            # Each environment should only access its own directories
            for directory in env_directories:
                assert f"env_{env}" in directory
                
                # Verify other environments' directories are not accessed
                for other_env in self.environments:
                    if other_env != env:
                        assert f"env_{other_env}" not in directory
    
    @pytest.mark.asyncio
    async def test_environment_specific_resource_limits(self):
        """Test that each environment respects its own resource limits."""
        # Create multiple jobs to test concurrency limits
        test_jobs = []
        for env in self.environments:
            max_concurrent = int(self.env_configs[env]["MAX_CONCURRENT_JOBS"])
            
            # Create more jobs than the concurrency limit
            for i in range(max_concurrent + 2):
                job = Job(
                    id=f"{env}_concurrent_job_{i}",
                    name=f"{env}_concurrency_test_{i}",
                    job_type="bulk_ingestion",
                    source_path=str(self.env_dirs[env] / "uploads" / f"test_{i}.pdf"),
                    environment=env,
                    priority=1,
                    created_at=datetime.now(),
                    status=JobStatus.PENDING
                )
                test_jobs.append((env, job))
        
        # Track concurrent execution per environment
        concurrent_executions = {env: 0 for env in self.environments}
        max_concurrent_reached = {env: 0 for env in self.environments}
        
        async def track_concurrent_execution(env):
            concurrent_executions[env] += 1
            max_concurrent_reached[env] = max(max_concurrent_reached[env], concurrent_executions[env])
            
            # Simulate processing time
            await asyncio.sleep(0.2)
            
            concurrent_executions[env] -= 1
            
            return {
                "job_id": f"{env}_concurrency_test",
                "status": "completed",
                "environment": env,
                "concurrent_count": max_concurrent_reached[env]
            }
        
        # Create processors with environment-specific limits
        processors = {}
        for env in self.environments:
            config = self.env_configs[env].copy()
            processors[env] = ScheduledBulkProcessor(
                config=config,
                pipeline=self.create_mock_pipeline(env),
                max_concurrent_jobs=int(config["MAX_CONCURRENT_JOBS"])
            )
            
            # Mock pipeline to track concurrency
            processors[env].pipeline.process_source = lambda *args, **kwargs: track_concurrent_execution(env)
        
        # Execute jobs for each environment
        tasks = []
        for env, job in test_jobs:
            task = processors[env].execute_job(job)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify resource limits were respected
        for env in self.environments:
            max_allowed = int(self.env_configs[env]["MAX_CONCURRENT_JOBS"])
            actual_max = max_concurrent_reached[env]
            assert actual_max <= max_allowed, f"{env} exceeded concurrency limit: {actual_max} > {max_allowed}"


class TestConfigurationInheritance(TestEnvironmentSpecificScheduling):
    """Test configuration inheritance and override patterns across environments."""
    
    @pytest.mark.asyncio
    async def test_configuration_inheritance_chain(self):
        """Test that configurations properly inherit from base with environment overrides."""
        config_manager = ConfigManager(base_config_dir=self.base_env_dir)
        
        # Define base configuration
        base_config = {
            "JOB_TIMEOUT_SECONDS": 300,
            "RETRY_ATTEMPTS": 3,
            "SCAN_INTERVAL_SECONDS": 60,
            "LOG_LEVEL": "INFO",
            "ENABLE_DEBUG_MODE": False
        }
        
        # Define environment-specific overrides
        env_overrides = {
            "dev": {
                "JOB_TIMEOUT_SECONDS": 600,  # Override: longer timeout for dev
                "LOG_LEVEL": "DEBUG",         # Override: debug logging for dev
                "ENABLE_DEBUG_MODE": True,    # Override: enable debug mode
                # RETRY_ATTEMPTS and SCAN_INTERVAL_SECONDS inherit from base
            },
            "test": {
                "RETRY_ATTEMPTS": 2,          # Override: fewer retries for test
                "ENABLE_MOCK_SERVICES": True, # Override: test-specific setting
                # Other settings inherit from base
            },
            "prod": {
                "JOB_TIMEOUT_SECONDS": 180,   # Override: shorter timeout for prod
                "RETRY_ATTEMPTS": 5,          # Override: more retries for prod
                "ENABLE_STRICT_VALIDATION": True, # Override: prod-specific setting
                # Other settings inherit from base
            }
        }
        
        # Test configuration resolution for each environment
        for env in self.environments:
            resolved_config = config_manager.resolve_configuration(
                base_config=base_config,
                environment=env,
                overrides=env_overrides.get(env, {})
            )
            
            # Verify inheritance and overrides
            if env == "dev":
                assert resolved_config["JOB_TIMEOUT_SECONDS"] == 600  # Overridden
                assert resolved_config["LOG_LEVEL"] == "DEBUG"        # Overridden
                assert resolved_config["ENABLE_DEBUG_MODE"] is True   # Overridden
                assert resolved_config["RETRY_ATTEMPTS"] == 3         # Inherited
                assert resolved_config["SCAN_INTERVAL_SECONDS"] == 60 # Inherited
            elif env == "test":
                assert resolved_config["RETRY_ATTEMPTS"] == 2         # Overridden
                assert resolved_config["ENABLE_MOCK_SERVICES"] is True # Overridden
                assert resolved_config["JOB_TIMEOUT_SECONDS"] == 300  # Inherited
                assert resolved_config["LOG_LEVEL"] == "INFO"         # Inherited
                assert resolved_config["SCAN_INTERVAL_SECONDS"] == 60 # Inherited
            elif env == "prod":
                assert resolved_config["JOB_TIMEOUT_SECONDS"] == 180  # Overridden
                assert resolved_config["RETRY_ATTEMPTS"] == 5         # Overridden
                assert resolved_config["ENABLE_STRICT_VALIDATION"] is True # Overridden
                assert resolved_config["LOG_LEVEL"] == "INFO"         # Inherited
                assert resolved_config["SCAN_INTERVAL_SECONDS"] == 60 # Inherited
    
    @pytest.mark.asyncio
    async def test_dynamic_configuration_updates(self):
        """Test dynamic configuration updates without service restart."""
        config_manager = ConfigManager(base_config_dir=self.base_env_dir)
        
        # Create scheduler with initial configuration
        initial_config = self.env_configs["dev"].copy()
        scheduler = SchedulingEngine(config=initial_config)
        
        # Get initial configuration values
        initial_scan_interval = scheduler.get_config_value("SCAN_INTERVAL_SECONDS")
        initial_job_timeout = scheduler.get_config_value("JOB_TIMEOUT_SECONDS")
        
        # Update configuration dynamically
        updated_config = {
            "SCAN_INTERVAL_SECONDS": 5,   # Reduced from 10
            "JOB_TIMEOUT_SECONDS": 900,   # Increased from 600
            "NEW_SETTING": "dynamic_value"
        }
        
        config_update_result = scheduler.update_configuration(updated_config)
        
        # Verify configuration updates
        assert config_update_result["status"] == "success"
        assert scheduler.get_config_value("SCAN_INTERVAL_SECONDS") == 5
        assert scheduler.get_config_value("JOB_TIMEOUT_SECONDS") == 900
        assert scheduler.get_config_value("NEW_SETTING") == "dynamic_value"
        
        # Verify old values are no longer active
        assert scheduler.get_config_value("SCAN_INTERVAL_SECONDS") != initial_scan_interval
        assert scheduler.get_config_value("JOB_TIMEOUT_SECONDS") != initial_job_timeout
        
        # Verify configuration persistence
        persisted_config = scheduler.get_full_configuration()
        assert persisted_config["SCAN_INTERVAL_SECONDS"] == 5
        assert persisted_config["JOB_TIMEOUT_SECONDS"] == 900
        assert persisted_config["NEW_SETTING"] == "dynamic_value"
    
    @pytest.mark.asyncio
    async def test_configuration_validation_and_constraints(self):
        """Test configuration validation and constraint enforcement."""
        config_manager = ConfigManager(base_config_dir=self.base_env_dir)
        
        # Test valid configurations
        valid_configs = [
            {"MAX_CONCURRENT_JOBS": 4, "JOB_TIMEOUT_SECONDS": 300},
            {"RETRY_ATTEMPTS": 5, "SCAN_INTERVAL_SECONDS": 60},
            {"LOG_LEVEL": "DEBUG", "ENABLE_DEBUG_MODE": True}
        ]
        
        for config in valid_configs:
            validation_result = config_manager.validate_configuration(config, environment="dev")
            assert validation_result["valid"] is True
            assert len(validation_result["errors"]) == 0
        
        # Test invalid configurations
        invalid_configs = [
            {"MAX_CONCURRENT_JOBS": -1},          # Negative value
            {"JOB_TIMEOUT_SECONDS": 0},           # Zero timeout
            {"RETRY_ATTEMPTS": 100},              # Too many retries
            {"SCAN_INTERVAL_SECONDS": -5},        # Negative interval
            {"LOG_LEVEL": "INVALID_LEVEL"},       # Invalid log level
            {"PORT": "not_a_number"},             # Invalid type
        ]
        
        for config in invalid_configs:
            validation_result = config_manager.validate_configuration(config, environment="dev")
            assert validation_result["valid"] is False
            assert len(validation_result["errors"]) > 0
            
            # Verify specific error messages
            if "MAX_CONCURRENT_JOBS" in config and config["MAX_CONCURRENT_JOBS"] < 1:
                assert any("MAX_CONCURRENT_JOBS must be positive" in error for error in validation_result["errors"])
            if "JOB_TIMEOUT_SECONDS" in config and config["JOB_TIMEOUT_SECONDS"] <= 0:
                assert any("JOB_TIMEOUT_SECONDS must be positive" in error for error in validation_result["errors"])


class TestMultiEnvironmentDeployment(TestEnvironmentSpecificScheduling):
    """Test multi-environment deployment and promotion workflows."""
    
    @pytest.mark.asyncio
    async def test_environment_promotion_workflow(self):
        """Test promoting configuration and jobs from dev → test → prod."""
        config_manager = ConfigManager(base_config_dir=self.base_env_dir)
        
        # Start with dev environment configuration
        dev_scheduler = SchedulingEngine(config=self.env_configs["dev"])
        dev_job_manager = JobManager(config=self.env_configs["dev"], pipeline=self.create_mock_pipeline("dev"))
        
        # Create and validate jobs in dev
        dev_job_id = dev_job_manager.create_job(
            name="promotion_test_job",
            job_type="bulk_ingestion",
            source_path=str(self.env_dirs["dev"] / "uploads" / "test_document.pdf"),
            environment="dev",
            priority=1
        )
        
        # Execute job successfully in dev
        dev_job = dev_job_manager.get_job(dev_job_id)
        await dev_job_manager.start_job(dev_job_id)
        await dev_job_manager.complete_job(dev_job_id, {"status": "completed", "test_passed": True})
        
        # Export dev configuration and job definitions for promotion
        promotion_package = dev_scheduler.export_promotion_package(
            include_jobs=True,
            include_schedules=True,
            include_config=True
        )
        
        assert promotion_package["source_environment"] == "dev"
        assert "jobs" in promotion_package
        assert "schedules" in promotion_package
        assert "configuration" in promotion_package
        
        # Promote to test environment
        test_scheduler = SchedulingEngine(config=self.env_configs["test"])
        test_promotion_result = test_scheduler.import_promotion_package(
            promotion_package,
            target_environment="test",
            validate_compatibility=True
        )
        
        assert test_promotion_result["status"] == "success"
        assert test_promotion_result["target_environment"] == "test"
        assert len(test_promotion_result["imported_jobs"]) >= 1
        
        # Verify promotion to test environment
        test_job_manager = JobManager(config=self.env_configs["test"], pipeline=self.create_mock_pipeline("test"))
        test_jobs = test_job_manager.get_all_jobs()
        
        # Should have promoted job with test environment specifics
        promoted_job = next((job for job in test_jobs if job.name == "promotion_test_job"), None)
        assert promoted_job is not None
        assert promoted_job.environment == "test"
        assert promoted_job.status == JobStatus.PENDING  # Reset for new environment
        
        # Test successful execution in test environment
        await test_job_manager.start_job(promoted_job.id)
        await test_job_manager.complete_job(promoted_job.id, {"status": "completed", "test_passed": True})
        
        # Promote to production environment
        test_promotion_package = test_scheduler.export_promotion_package(
            include_jobs=True,
            include_schedules=True,
            include_config=True
        )
        
        prod_scheduler = SchedulingEngine(config=self.env_configs["prod"])
        prod_promotion_result = prod_scheduler.import_promotion_package(
            test_promotion_package,
            target_environment="prod",
            validate_compatibility=True
        )
        
        assert prod_promotion_result["status"] == "success"
        assert prod_promotion_result["target_environment"] == "prod"
    
    @pytest.mark.asyncio
    async def test_environment_specific_schedule_coordination(self):
        """Test that different environments can have different scheduling patterns."""
        schedulers = {}
        schedules = {}
        
        # Create schedulers for each environment with different schedules
        schedule_patterns = {
            "dev": "*/5 * * * *",      # Every 5 minutes for development testing
            "test": "0 */2 * * *",     # Every 2 hours for integration testing  
            "prod": "0 2 * * *"        # Daily at 2 AM for production
        }
        
        for env in self.environments:
            schedulers[env] = SchedulingEngine(config=self.env_configs[env])
            
            # Schedule environment-specific job
            schedule_id = schedulers[env].schedule_job(
                name=f"{env}_environment_scheduled_job",
                cron_schedule=schedule_patterns[env],
                job_type="bulk_ingestion",
                priority=1,
                environment_specific=True
            )
            schedules[env] = schedule_id
        
        # Verify each environment has correct schedule pattern
        for env in self.environments:
            env_schedules = schedulers[env].get_scheduled_jobs()
            assert len(env_schedules) == 1
            
            env_schedule = env_schedules[0]
            assert env_schedule["cron_schedule"] == schedule_patterns[env]
            assert env_schedule["environment"] == env
        
        # Test schedule execution timing for each environment
        with patch('src_common.scheduler_engine.datetime') as mock_datetime:
            base_time = datetime(2025, 1, 15, 1, 55, 0)  # 1:55 AM
            mock_datetime.now.return_value = base_time
            mock_datetime.strptime = datetime.strptime
            
            # Check next execution times
            for env in self.environments:
                cron_parser = CronParser(schedule_patterns[env])
                next_execution = cron_parser.get_next_execution_time(base_time)
                
                if env == "dev":
                    # Should execute at 2:00 AM (next 5-minute boundary)
                    assert next_execution.hour == 2
                    assert next_execution.minute == 0
                elif env == "test":  
                    # Should execute at 2:00 AM (next 2-hour boundary)
                    assert next_execution.hour == 2
                    assert next_execution.minute == 0
                elif env == "prod":
                    # Should execute at 2:00 AM (daily schedule)
                    assert next_execution.hour == 2
                    assert next_execution.minute == 0
    
    @pytest.mark.asyncio
    async def test_cross_environment_job_coordination(self):
        """Test coordination between jobs running in different environments."""
        # Create coordination manager to handle cross-environment dependencies
        coordination_config = {
            "environments": self.environments,
            "coordination_mode": "sequential",  # dev → test → prod
            "failure_policy": "stop_chain",
            "notification_channels": ["logs", "webhook"]
        }
        
        env_manager = EnvironmentManager(
            environments=self.env_dirs,
            coordination_config=coordination_config
        )
        
        # Create coordinated job chain
        job_chain_id = env_manager.create_job_chain(
            name="coordinated_deployment_chain",
            jobs=[
                {"environment": "dev", "job_type": "bulk_ingestion", "validation": "unit_tests"},
                {"environment": "test", "job_type": "bulk_ingestion", "validation": "integration_tests"},
                {"environment": "prod", "job_type": "bulk_ingestion", "validation": "smoke_tests"}
            ],
            dependencies="sequential"
        )
        
        # Execute coordinated job chain
        execution_results = await env_manager.execute_job_chain(job_chain_id)
        
        # Verify coordination
        assert execution_results["chain_id"] == job_chain_id
        assert execution_results["status"] == "completed"
        assert len(execution_results["environment_results"]) == 3
        
        # Verify execution order (dev → test → prod)
        env_execution_order = [result["environment"] for result in execution_results["environment_results"]]
        assert env_execution_order == ["dev", "test", "prod"]
        
        # Verify each environment executed successfully
        for env_result in execution_results["environment_results"]:
            assert env_result["status"] == "completed"
            assert env_result["validation_passed"] is True


class TestEnvironmentSpecificMonitoring(TestEnvironmentSpecificScheduling):
    """Test environment-specific monitoring and alerting configurations."""
    
    @pytest.mark.asyncio
    async def test_environment_specific_alert_thresholds(self):
        """Test that each environment has appropriate alert thresholds."""
        alert_configs = {
            "dev": {
                "job_failure_threshold": 5,        # Higher tolerance for dev failures
                "response_time_threshold_ms": 5000, # Relaxed response time limits
                "disk_usage_threshold_percent": 90, # Higher disk usage tolerance
                "alert_channels": ["logs"],         # Only log alerts in dev
                "alert_frequency": "immediate"
            },
            "test": {
                "job_failure_threshold": 3,        # Moderate failure tolerance
                "response_time_threshold_ms": 2000, # Stricter response time
                "disk_usage_threshold_percent": 80, # Moderate disk usage threshold
                "alert_channels": ["logs", "email"], # Log and email alerts
                "alert_frequency": "batched"
            },
            "prod": {
                "job_failure_threshold": 1,        # Low failure tolerance
                "response_time_threshold_ms": 1000, # Strict response time requirements
                "disk_usage_threshold_percent": 70, # Conservative disk usage
                "alert_channels": ["logs", "email", "webhook", "sms"], # All alert channels
                "alert_frequency": "immediate"
            }
        }
        
        # Create monitoring for each environment
        monitors = {}
        for env in self.environments:
            from src_common.scheduler_monitor import SchedulerHealthMonitor
            
            monitors[env] = SchedulerHealthMonitor(
                config=self.env_configs[env],
                alert_config=alert_configs[env]
            )
        
        # Simulate different alert conditions in each environment
        for env in self.environments:
            monitor = monitors[env]
            config = alert_configs[env]
            
            # Test job failure threshold
            for i in range(config["job_failure_threshold"] + 1):
                alert_result = monitor.record_job_failure(f"test_job_{i}", "Test failure")
                
                if i < config["job_failure_threshold"]:
                    # Should not trigger alert yet
                    assert alert_result["alert_triggered"] is False
                else:
                    # Should trigger alert when threshold reached
                    assert alert_result["alert_triggered"] is True
                    assert alert_result["alert_level"] == "warning" if env != "prod" else "critical"
            
            # Test response time threshold
            slow_response_time = config["response_time_threshold_ms"] + 500
            response_alert = monitor.record_response_time("test_endpoint", slow_response_time)
            
            assert response_alert["alert_triggered"] is True
            assert response_alert["response_time"] == slow_response_time
            assert response_alert["threshold_exceeded"] is True
            
            # Verify environment-specific alert channels
            if "alert_channels" in config:
                assert set(response_alert["channels"]) == set(config["alert_channels"])
    
    @pytest.mark.asyncio
    async def test_environment_specific_metrics_collection(self):
        """Test that each environment collects appropriate metrics."""
        metrics_configs = {
            "dev": {
                "collection_interval_seconds": 10,
                "metrics_retention_days": 7,
                "detailed_tracing": True,
                "performance_profiling": True,
                "debug_metrics": True
            },
            "test": {
                "collection_interval_seconds": 30,
                "metrics_retention_days": 14,
                "detailed_tracing": False,
                "performance_profiling": True, 
                "debug_metrics": False
            },
            "prod": {
                "collection_interval_seconds": 60,
                "metrics_retention_days": 90,
                "detailed_tracing": False,
                "performance_profiling": False,
                "debug_metrics": False
            }
        }
        
        # Create metrics collectors for each environment
        collectors = {}
        for env in self.environments:
            from src_common.operational_metrics import OperationalMetricsCollector
            
            collectors[env] = OperationalMetricsCollector(
                config=self.env_configs[env],
                metrics_config=metrics_configs[env]
            )
        
        # Simulate metric collection in each environment
        for env in self.environments:
            collector = collectors[env]
            config = metrics_configs[env]
            
            # Start metric collection
            collector.start_collection()
            
            # Simulate some activity
            await asyncio.sleep(0.1)
            
            # Collect metrics
            metrics = collector.collect_metrics()
            
            # Verify environment-specific metric collection
            assert metrics["environment"] == env
            assert metrics["collection_interval"] == config["collection_interval_seconds"]
            
            # Verify debug metrics are only collected in dev
            if config["debug_metrics"]:
                assert "debug_info" in metrics
                assert "memory_usage_detailed" in metrics
                assert "thread_pool_stats" in metrics
            else:
                assert "debug_info" not in metrics
                
            # Verify performance profiling
            if config["performance_profiling"]:
                assert "performance_profile" in metrics
                assert "execution_times" in metrics
            else:
                assert "performance_profile" not in metrics
            
            collector.stop_collection()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])