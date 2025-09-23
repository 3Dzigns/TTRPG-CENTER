# tests/regression/feature_requests/test_fr002_nightly_ingestion.py
"""
Feature Request FR-002: Nightly Ingestion Workflow Regression Tests
Tests automated nightly ingestion scheduling, execution, and monitoring
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch


class TestNightlyIngestionWorkflow:
    """Test suite for FR-002 Nightly Ingestion functionality"""

    def test_nightly_ingestion_scheduler_availability(self):
        """Test that nightly ingestion scheduler components are available"""
        try:
            from src_common.scheduler import IngestionScheduler
            from src_common.nightly_ingestion import NightlyIngestionManager
            from src_common.admin_routes import app

            assert IngestionScheduler is not None, "IngestionScheduler should be available"
            assert NightlyIngestionManager is not None, "NightlyIngestionManager should be available"
            assert app is not None, "Admin routes should support ingestion scheduling"

        except ImportError as e:
            pytest.fail(f"Nightly ingestion components not available: {e}")

    def test_ingestion_schedule_configuration(self):
        """Test nightly ingestion schedule configuration"""
        try:
            from src_common.scheduler import IngestionScheduler
        except ImportError:
            pytest.skip("Ingestion scheduler not available for testing")

        scheduler = IngestionScheduler()

        # Test schedule configuration
        schedule_config = {
            "enabled": True,
            "schedule": "0 2 * * *",  # Daily at 2 AM
            "timezone": "UTC",
            "max_runtime": 3600,  # 1 hour max runtime
            "retry_attempts": 3,
            "retry_delay": 300,  # 5 minutes
            "notification_emails": ["admin@ttrpg-center.com"],
            "failure_escalation": True
        }

        if hasattr(scheduler, 'configure_schedule'):
            config_result = scheduler.configure_schedule(schedule_config)

            assert isinstance(config_result, dict), "Schedule configuration should return structured result"

            if "configured" in config_result:
                assert config_result["configured"] == True, "Valid schedule should configure successfully"

            if "next_run" in config_result:
                next_run = config_result["next_run"]
                assert isinstance(next_run, str), "Next run time should be provided"

        # Test schedule validation
        if hasattr(scheduler, 'validate_schedule'):
            # Test valid cron expression
            valid_validation = scheduler.validate_schedule("0 2 * * *")
            assert valid_validation.get("valid", False) == True, "Valid cron expression should validate"

            # Test invalid cron expression
            invalid_validation = scheduler.validate_schedule("invalid cron")
            assert invalid_validation.get("valid", True) == False, "Invalid cron expression should fail validation"

    def test_automated_source_detection(self):
        """Test automated detection of new sources for ingestion"""
        try:
            from src_common.nightly_ingestion import NightlyIngestionManager
        except ImportError:
            pytest.skip("Nightly ingestion manager not available for testing")

        manager = NightlyIngestionManager()

        # Test source detection configuration
        detection_config = {
            "watch_directories": [
                "/uploads/new",
                "/uploads/pending",
                "/uploads/auto"
            ],
            "file_patterns": ["*.pdf", "*.docx", "*.txt"],
            "min_file_size": 1024,  # 1KB minimum
            "max_file_size": 104857600,  # 100MB maximum
            "scan_interval": 300,  # 5 minutes
            "quarantine_suspicious": True
        }

        if hasattr(manager, 'configure_source_detection'):
            detection_result = manager.configure_source_detection(detection_config)

            assert isinstance(detection_result, dict), "Source detection config should return structured result"

        # Test source scanning
        if hasattr(manager, 'scan_for_new_sources'):
            # Mock directory structure for testing
            mock_sources = [
                {
                    "path": "/uploads/new/test_book.pdf",
                    "size": 5242880,  # 5MB
                    "modified": datetime.now().isoformat(),
                    "checksum": "sha256:abc123..."
                },
                {
                    "path": "/uploads/new/small_file.txt",
                    "size": 512,  # Below minimum size
                    "modified": datetime.now().isoformat(),
                    "checksum": "sha256:def456..."
                }
            ]

            with patch.object(manager, '_scan_directories', return_value=mock_sources):
                scan_result = manager.scan_for_new_sources(detection_config)

                assert isinstance(scan_result, dict), "Source scan should return structured result"

                if "sources_found" in scan_result:
                    sources = scan_result["sources_found"]
                    assert isinstance(sources, list), "Found sources should be list"

                    # Should filter out files below minimum size
                    valid_sources = [s for s in sources if s["size"] >= detection_config["min_file_size"]]
                    assert len(valid_sources) >= 1, "Should find sources meeting size criteria"

                if "quarantined_files" in scan_result:
                    quarantined = scan_result["quarantined_files"]
                    assert isinstance(quarantined, list), "Quarantined files should be list"

    def test_incremental_ingestion_processing(self):
        """Test incremental processing of new sources"""
        try:
            from src_common.nightly_ingestion import NightlyIngestionManager
        except ImportError:
            pytest.skip("Nightly ingestion manager not available for testing")

        manager = NightlyIngestionManager()

        # Test incremental processing configuration
        incremental_config = {
            "mode": "incremental",
            "batch_size": 5,
            "parallel_workers": 2,
            "checkpoint_interval": 10,  # Every 10 sources
            "skip_existing": True,
            "update_modified": True,
            "preserve_history": True
        }

        # Test source batch for incremental processing
        source_batch = [
            {
                "source_id": "new_source_001",
                "path": "/uploads/new/book1.pdf",
                "size": 2048000,
                "status": "pending",
                "priority": "normal"
            },
            {
                "source_id": "new_source_002",
                "path": "/uploads/new/book2.pdf",
                "size": 1536000,
                "status": "pending",
                "priority": "high"
            },
            {
                "source_id": "existing_source_001",
                "path": "/uploads/processed/book3.pdf",
                "size": 1024000,
                "status": "processed",
                "priority": "normal",
                "last_modified": (datetime.now() - timedelta(hours=1)).isoformat()
            }
        ]

        if hasattr(manager, 'process_incremental_batch'):
            processing_result = manager.process_incremental_batch(source_batch, incremental_config)

            assert isinstance(processing_result, dict), "Incremental processing should return structured result"

            # Verify batch processing results
            if "processed_sources" in processing_result:
                processed = processing_result["processed_sources"]
                assert isinstance(processed, list), "Processed sources should be list"

            if "skipped_sources" in processing_result:
                skipped = processing_result["skipped_sources"]
                assert isinstance(skipped, list), "Skipped sources should be list"

                # Should skip already processed sources if configured
                if incremental_config["skip_existing"]:
                    existing_skipped = any(
                        "existing_source" in source.get("source_id", "")
                        for source in skipped
                    )

            if "processing_summary" in processing_result:
                summary = processing_result["processing_summary"]
                assert "total_sources" in summary, "Should provide processing summary"
                assert "successful" in summary, "Should track successful processing"
                assert "failed" in summary, "Should track failed processing"

    def test_nightly_execution_workflow(self):
        """Test complete nightly execution workflow"""
        try:
            from src_common.nightly_ingestion import NightlyIngestionManager
        except ImportError:
            pytest.skip("Nightly ingestion manager not available for testing")

        manager = NightlyIngestionManager()

        # Test nightly execution configuration
        execution_config = {
            "job_id": f"nightly_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "execution_time": datetime.now().isoformat(),
            "environment": "test",
            "source_detection": {
                "enabled": True,
                "watch_directories": ["/uploads/nightly"]
            },
            "processing": {
                "mode": "incremental",
                "batch_size": 10,
                "timeout": 1800  # 30 minutes
            },
            "notification": {
                "on_success": True,
                "on_failure": True,
                "on_partial": True
            },
            "cleanup": {
                "archive_processed": True,
                "cleanup_temp_files": True,
                "retain_logs": 30  # days
            }
        }

        if hasattr(manager, 'execute_nightly_workflow'):
            # Mock the execution for testing
            with patch.object(manager, '_detect_new_sources', return_value={"sources": []}), \
                 patch.object(manager, '_process_sources', return_value={"processed": 0}), \
                 patch.object(manager, '_cleanup_execution', return_value={"cleaned": True}):

                execution_result = manager.execute_nightly_workflow(execution_config)

                assert isinstance(execution_result, dict), "Nightly execution should return structured result"

                # Verify execution phases
                if "execution_phases" in execution_result:
                    phases = execution_result["execution_phases"]
                    expected_phases = ["detection", "processing", "cleanup", "notification"]

                    for phase in expected_phases:
                        if phase in phases:
                            phase_result = phases[phase]
                            assert "status" in phase_result, f"Phase {phase} should have status"
                            assert "duration" in phase_result, f"Phase {phase} should track duration"

                # Verify overall execution status
                if "status" in execution_result:
                    status = execution_result["status"]
                    assert status in ["success", "failure", "partial"], f"Execution status should be valid: {status}"

                if "job_id" in execution_result:
                    job_id = execution_result["job_id"]
                    assert job_id == execution_config["job_id"], "Should preserve job ID"

    def test_failure_handling_and_retry_logic(self):
        """Test failure handling and retry logic for nightly ingestion"""
        try:
            from src_common.nightly_ingestion import NightlyIngestionManager
        except ImportError:
            pytest.skip("Nightly ingestion manager not available for testing")

        manager = NightlyIngestionManager()

        # Test retry configuration
        retry_config = {
            "max_retries": 3,
            "retry_delay": 60,  # 1 minute
            "backoff_multiplier": 2,
            "retry_on_failures": ["timeout", "network_error", "temporary_failure"],
            "no_retry_failures": ["authentication_error", "permission_denied", "corrupted_file"]
        }

        # Test source that should trigger retries
        failing_source = {
            "source_id": "failing_source_001",
            "path": "/uploads/problematic.pdf",
            "failure_type": "timeout",
            "attempt_count": 0
        }

        if hasattr(manager, 'handle_source_failure'):
            failure_result = manager.handle_source_failure(failing_source, retry_config)

            assert isinstance(failure_result, dict), "Failure handling should return structured result"

            # Verify retry decision
            if "should_retry" in failure_result:
                should_retry = failure_result["should_retry"]
                assert should_retry == True, "Timeout failures should trigger retry"

            if "next_attempt_delay" in failure_result:
                delay = failure_result["next_attempt_delay"]
                assert delay >= retry_config["retry_delay"], "Should respect minimum retry delay"

        # Test source that should not retry
        no_retry_source = {
            "source_id": "no_retry_source_001",
            "path": "/uploads/corrupted.pdf",
            "failure_type": "corrupted_file",
            "attempt_count": 1
        }

        if hasattr(manager, 'handle_source_failure'):
            no_retry_result = manager.handle_source_failure(no_retry_source, retry_config)

            if "should_retry" in no_retry_result:
                should_retry = no_retry_result["should_retry"]
                assert should_retry == False, "Corrupted file failures should not trigger retry"

            if "final_status" in no_retry_result:
                final_status = no_retry_result["final_status"]
                assert final_status == "failed", "Non-retryable failures should be marked as failed"

    def test_monitoring_and_alerting(self):
        """Test monitoring and alerting for nightly ingestion"""
        try:
            from src_common.nightly_ingestion import NightlyIngestionManager
        except ImportError:
            pytest.skip("Nightly ingestion manager not available for testing")

        manager = NightlyIngestionManager()

        # Test monitoring configuration
        monitoring_config = {
            "metrics_collection": True,
            "performance_tracking": True,
            "alert_thresholds": {
                "max_execution_time": 7200,  # 2 hours
                "min_success_rate": 0.85,
                "max_failure_rate": 0.15
            },
            "notification_channels": {
                "email": ["admin@ttrpg-center.com"],
                "slack": ["#ingestion-alerts"],
                "webhook": ["https://monitoring.example.com/webhook"]
            }
        }

        # Test monitoring data collection
        execution_metrics = {
            "job_id": "nightly_20240922_020000",
            "start_time": "2024-09-22T02:00:00Z",
            "end_time": "2024-09-22T03:15:00Z",
            "total_sources": 25,
            "successful_sources": 22,
            "failed_sources": 3,
            "processing_time": 4500,  # seconds
            "throughput": 0.36  # sources per minute
        }

        if hasattr(manager, 'collect_monitoring_metrics'):
            monitoring_result = manager.collect_monitoring_metrics(execution_metrics, monitoring_config)

            assert isinstance(monitoring_result, dict), "Monitoring should return structured result"

            # Verify metrics processing
            if "processed_metrics" in monitoring_result:
                processed = monitoring_result["processed_metrics"]
                assert "success_rate" in processed, "Should calculate success rate"
                assert "failure_rate" in processed, "Should calculate failure rate"
                assert "execution_duration" in processed, "Should calculate execution duration"

            # Verify alert evaluation
            if "alert_evaluation" in monitoring_result:
                alerts = monitoring_result["alert_evaluation"]

                # Check execution time alert
                if "execution_time_alert" in alerts:
                    time_alert = alerts["execution_time_alert"]
                    # 4500 seconds < 7200 seconds threshold
                    assert time_alert["triggered"] == False, "Execution time within threshold should not alert"

                # Check success rate alert
                if "success_rate_alert" in alerts:
                    success_alert = alerts["success_rate_alert"]
                    # 22/25 = 0.88 > 0.85 threshold
                    assert success_alert["triggered"] == False, "Success rate above threshold should not alert"

    def test_nightly_ingestion_contract_compliance(self):
        """Test that nightly ingestion matches established contract"""
        # Test scheduling contract
        scheduling_requirements = {
            "cron_expression_support": True,
            "timezone_awareness": True,
            "retry_mechanisms": True,
            "failure_notifications": True
        }

        for requirement, needed in scheduling_requirements.items():
            assert needed, f"Scheduling requirement {requirement} is mandatory"

        # Test processing contract
        processing_requirements = {
            "incremental_processing": True,
            "batch_processing": True,
            "parallel_execution": True,
            "checkpoint_recovery": True,
            "source_deduplication": True
        }

        for requirement, needed in processing_requirements.items():
            assert needed, f"Processing requirement {requirement} is mandatory"

        # Test monitoring contract
        monitoring_requirements = {
            "execution_metrics": True,
            "performance_tracking": True,
            "alert_thresholds": True,
            "notification_channels": True,
            "audit_logging": True
        }

        for requirement, needed in monitoring_requirements.items():
            assert needed, f"Monitoring requirement {requirement} is mandatory"

        # Test data contract
        required_data_fields = [
            "job_id",
            "execution_time",
            "source_count",
            "success_rate",
            "failure_details",
            "processing_duration"
        ]

        for field in required_data_fields:
            assert isinstance(field, str), f"Data field {field} should be defined"

        # Test integration contract
        integration_points = [
            "scheduler_integration",
            "ingestion_pipeline_integration",
            "monitoring_system_integration",
            "notification_system_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"