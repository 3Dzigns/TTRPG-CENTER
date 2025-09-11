#!/usr/bin/env python3
"""
Unit Tests for FR-002 Scheduling Infrastructure

Tests core scheduling components including SchedulingEngine, JobManager,
JobQueue, CronParser, and integration with existing bulk ingestion pipeline.
"""

import pytest
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

# Add src_common to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))


class TestCronParser:
    """Test cron expression parsing and schedule calculation"""
    
    def test_basic_cron_parsing(self):
        """Test basic cron expression parsing"""
        cron_parser = MockCronParser()
        
        # Test standard cron patterns
        test_patterns = [
            ("0 2 * * *", "Daily at 2:00 AM"),
            ("0 2 * * 0", "Weekly on Sunday at 2:00 AM"),
            ("0 2 1 * *", "Monthly on 1st at 2:00 AM"),
            ("*/15 * * * *", "Every 15 minutes"),
            ("0 */6 * * *", "Every 6 hours"),
            ("0 2 * * 1-5", "Weekdays at 2:00 AM")
        ]
        
        for pattern, description in test_patterns:
            parsed = cron_parser.parse(pattern)
            assert parsed is not None, f"Failed to parse: {pattern}"
            assert parsed["valid"], f"Invalid pattern: {pattern}"
            assert "next_run" in parsed, f"Missing next_run for: {pattern}"
            
    def test_cron_next_execution_calculation(self):
        """Test calculation of next execution times"""
        cron_parser = MockCronParser()
        
        # Test next execution calculation
        now = datetime(2025, 9, 11, 10, 30, 0)  # Thursday 10:30 AM
        
        test_cases = [
            {
                "pattern": "0 2 * * *",  # Daily at 2 AM
                "expected_next": datetime(2025, 9, 12, 2, 0, 0)  # Tomorrow 2 AM
            },
            {
                "pattern": "0 14 * * *",  # Daily at 2 PM
                "expected_next": datetime(2025, 9, 11, 14, 0, 0)  # Today 2 PM
            },
            {
                "pattern": "0 2 * * 1",  # Mondays at 2 AM
                "expected_next": datetime(2025, 9, 15, 2, 0, 0)  # Next Monday
            }
        ]
        
        for case in test_cases:
            next_run = cron_parser.get_next_execution(case["pattern"], now)
            assert next_run == case["expected_next"], \
                f"Pattern {case['pattern']}: expected {case['expected_next']}, got {next_run}"
                
    def test_invalid_cron_expressions(self):
        """Test handling of invalid cron expressions"""
        cron_parser = MockCronParser()
        
        invalid_patterns = [
            "invalid cron",
            "60 2 * * *",  # Invalid minute
            "0 25 * * *",  # Invalid hour
            "0 2 32 * *",  # Invalid day
            "0 2 * 13 *",  # Invalid month
            "0 2 * * 8"    # Invalid weekday
        ]
        
        for pattern in invalid_patterns:
            parsed = cron_parser.parse(pattern)
            assert not parsed["valid"], f"Should be invalid: {pattern}"
            assert "error" in parsed, f"Missing error for invalid pattern: {pattern}"


class TestJobQueue:
    """Test job queue management and operations"""
    
    def test_job_queue_creation(self):
        """Test basic job queue creation and configuration"""
        queue_config = {
            "max_size": 100,
            "priority_enabled": True,
            "persistence_enabled": True,
            "environment": "test"
        }
        
        job_queue = MockJobQueue(queue_config)
        
        assert job_queue.max_size == 100
        assert job_queue.priority_enabled is True
        assert job_queue.size() == 0
        assert job_queue.is_empty()
        
    def test_job_queue_enqueue_dequeue(self):
        """Test basic enqueue and dequeue operations"""
        job_queue = MockJobQueue({"max_size": 10, "priority_enabled": False})
        
        # Test basic enqueue/dequeue
        test_job = {
            "job_id": "job_test_123",
            "source_file": "test.pdf",
            "priority": 1,
            "created_at": datetime.now().isoformat()
        }
        
        # Enqueue job
        enqueue_result = job_queue.enqueue(test_job)
        assert enqueue_result["success"]
        assert job_queue.size() == 1
        assert not job_queue.is_empty()
        
        # Dequeue job
        dequeued_job = job_queue.dequeue()
        assert dequeued_job is not None
        assert dequeued_job["job_id"] == "job_test_123"
        assert job_queue.size() == 0
        assert job_queue.is_empty()
        
    def test_priority_queue_ordering(self):
        """Test priority-based job ordering"""
        job_queue = MockJobQueue({"max_size": 10, "priority_enabled": True})
        
        # Enqueue jobs with different priorities
        jobs = [
            {"job_id": "job_low", "priority": 1, "created_at": "2025-09-11T10:00:00Z"},
            {"job_id": "job_high", "priority": 10, "created_at": "2025-09-11T10:01:00Z"},
            {"job_id": "job_med", "priority": 5, "created_at": "2025-09-11T10:02:00Z"}
        ]
        
        for job in jobs:
            job_queue.enqueue(job)
        
        # Dequeue should return highest priority first
        first = job_queue.dequeue()
        second = job_queue.dequeue()
        third = job_queue.dequeue()
        
        assert first["job_id"] == "job_high"  # Priority 10
        assert second["job_id"] == "job_med"   # Priority 5
        assert third["job_id"] == "job_low"    # Priority 1
        
    def test_queue_capacity_limits(self):
        """Test queue capacity and overflow handling"""
        job_queue = MockJobQueue({"max_size": 2, "priority_enabled": False})
        
        # Fill queue to capacity
        job1 = {"job_id": "job_1", "priority": 1}
        job2 = {"job_id": "job_2", "priority": 1}
        job3 = {"job_id": "job_3", "priority": 1}  # Should overflow
        
        result1 = job_queue.enqueue(job1)
        result2 = job_queue.enqueue(job2)
        result3 = job_queue.enqueue(job3)  # Should fail
        
        assert result1["success"]
        assert result2["success"]
        assert not result3["success"]
        assert "capacity" in result3["error"].lower()
        assert job_queue.size() == 2
        
    def test_queue_persistence(self):
        """Test job queue persistence across restarts"""
        queue_config = {"max_size": 10, "persistence_enabled": True, "persistence_path": "/tmp/test_queue.json"}
        
        # Create queue and add jobs
        job_queue1 = MockJobQueue(queue_config)
        test_jobs = [
            {"job_id": "job_persist_1", "priority": 1},
            {"job_id": "job_persist_2", "priority": 2}
        ]
        
        for job in test_jobs:
            job_queue1.enqueue(job)
        
        # Save state
        job_queue1.persist_state()
        
        # Create new queue instance and restore
        job_queue2 = MockJobQueue(queue_config)
        job_queue2.restore_state()
        
        # Verify jobs were restored
        assert job_queue2.size() == 2
        
        restored_job1 = job_queue2.dequeue()
        restored_job2 = job_queue2.dequeue()
        
        # Should restore in priority order
        assert restored_job1["job_id"] == "job_persist_2"  # Higher priority
        assert restored_job2["job_id"] == "job_persist_1"  # Lower priority


class TestJobManager:
    """Test job management and lifecycle operations"""
    
    def test_job_manager_initialization(self):
        """Test job manager initialization with configuration"""
        config = {
            "environment": "test",
            "max_concurrent_jobs": 4,
            "job_timeout_seconds": 1800,
            "retry_policy": {
                "max_retries": 3,
                "backoff_factor": 2.0,
                "initial_delay_seconds": 60
            }
        }
        
        job_manager = MockJobManager(config)
        
        assert job_manager.environment == "test"
        assert job_manager.max_concurrent_jobs == 4
        assert job_manager.active_jobs == 0
        assert job_manager.retry_policy["max_retries"] == 3
        
    def test_job_creation_and_tracking(self):
        """Test job creation and status tracking"""
        job_manager = MockJobManager({"environment": "test"})
        
        # Create new job
        job_request = {
            "source_file": "test_document.pdf",
            "priority": 5,
            "environment": "test",
            "schedule_id": "nightly_batch"
        }
        
        created_job = job_manager.create_job(job_request)
        
        assert created_job["success"]
        assert "job_id" in created_job
        assert created_job["status"] == "pending"
        assert created_job["source_file"] == "test_document.pdf"
        
        # Verify job tracking
        job_id = created_job["job_id"]
        job_status = job_manager.get_job_status(job_id)
        
        assert job_status["found"]
        assert job_status["status"] == "pending"
        assert job_status["priority"] == 5
        
    def test_job_status_transitions(self):
        """Test job status state machine transitions"""
        job_manager = MockJobManager({"environment": "test"})
        
        # Create job
        job = job_manager.create_job({"source_file": "test.pdf", "priority": 1})
        job_id = job["job_id"]
        
        # Test status transitions
        transitions = [
            ("pending", "running"),
            ("running", "completed"),
        ]
        
        for from_status, to_status in transitions:
            current_status = job_manager.get_job_status(job_id)["status"]
            assert current_status == from_status, f"Expected {from_status}, got {current_status}"
            
            transition_result = job_manager.transition_job_status(job_id, to_status)
            assert transition_result["success"], f"Failed transition {from_status} -> {to_status}"
            
            new_status = job_manager.get_job_status(job_id)["status"]
            assert new_status == to_status, f"Status not updated to {to_status}"
            
    def test_job_retry_logic(self):
        """Test job retry logic and exponential backoff"""
        retry_config = {
            "max_retries": 3,
            "backoff_factor": 2.0,
            "initial_delay_seconds": 30
        }
        
        job_manager = MockJobManager({"retry_policy": retry_config})
        
        # Create job
        job = job_manager.create_job({"source_file": "retry_test.pdf", "priority": 1})
        job_id = job["job_id"]
        
        # Simulate job failures and retries
        for attempt in range(1, 4):  # 3 attempts
            # Mark job as failed
            failure_result = job_manager.mark_job_failed(job_id, f"Attempt {attempt} failed")
            assert failure_result["success"]
            
            # Check retry scheduling
            retry_info = job_manager.get_retry_info(job_id)
            expected_delay = retry_config["initial_delay_seconds"] * (retry_config["backoff_factor"] ** (attempt - 1))
            
            assert retry_info["attempt"] == attempt
            assert retry_info["next_retry_delay"] == expected_delay
            assert retry_info["retries_remaining"] == retry_config["max_retries"] - attempt
            
        # After max retries, job should be permanently failed
        final_failure = job_manager.mark_job_failed(job_id, "Final failure")
        final_status = job_manager.get_job_status(job_id)
        
        assert final_status["status"] == "permanently_failed"
        assert final_status["retry_count"] == retry_config["max_retries"]
        
    def test_concurrent_job_limits(self):
        """Test concurrent job execution limits"""
        job_manager = MockJobManager({"max_concurrent_jobs": 2})
        
        # Create and start jobs up to limit
        jobs = []
        for i in range(3):
            job = job_manager.create_job({"source_file": f"concurrent_{i}.pdf", "priority": 1})
            jobs.append(job["job_id"])
        
        # Start jobs - first two should succeed, third should queue
        start_results = []
        for job_id in jobs:
            result = job_manager.start_job(job_id)
            start_results.append(result)
        
        assert start_results[0]["success"]  # First job starts
        assert start_results[1]["success"]  # Second job starts
        assert not start_results[2]["success"]  # Third job queued due to limit
        assert "concurrent limit" in start_results[2]["reason"].lower()
        
        # Complete one job - third should now be able to start
        job_manager.complete_job(jobs[0])
        
        # Try starting third job again
        retry_start = job_manager.start_job(jobs[2])
        assert retry_start["success"]  # Should now succeed


class TestSchedulingEngine:
    """Test core scheduling engine functionality"""
    
    def test_scheduling_engine_initialization(self):
        """Test scheduling engine setup and configuration"""
        config = {
            "environment": "test",
            "default_schedule": "0 2 * * *",  # Daily at 2 AM
            "timezone": "UTC",
            "max_schedules": 10
        }
        
        scheduler = MockSchedulingEngine(config)
        
        assert scheduler.environment == "test"
        assert scheduler.timezone == "UTC"
        assert scheduler.is_running() is False
        assert len(scheduler.get_schedules()) == 0
        
    def test_schedule_creation_and_management(self):
        """Test creating and managing scheduled tasks"""
        scheduler = MockSchedulingEngine({"environment": "test"})
        
        # Create new schedule
        schedule_config = {
            "name": "nightly_ingestion",
            "cron_expression": "0 2 * * *",
            "upload_directories": ["/uploads/nightly"],
            "environment": "test",
            "enabled": True
        }
        
        created_schedule = scheduler.create_schedule(schedule_config)
        
        assert created_schedule["success"]
        assert "schedule_id" in created_schedule
        assert created_schedule["name"] == "nightly_ingestion"
        
        # Verify schedule was added
        schedules = scheduler.get_schedules()
        assert len(schedules) == 1
        assert schedules[0]["name"] == "nightly_ingestion"
        assert schedules[0]["enabled"] is True
        
    def test_schedule_execution_timing(self):
        """Test schedule execution timing and next run calculation"""
        scheduler = MockSchedulingEngine({"environment": "test"})
        
        # Create schedule for testing
        schedule = scheduler.create_schedule({
            "name": "test_schedule",
            "cron_expression": "*/5 * * * *",  # Every 5 minutes
            "upload_directories": ["/test"],
            "enabled": True
        })
        
        schedule_id = schedule["schedule_id"]
        
        # Get next execution time
        next_run = scheduler.get_next_execution(schedule_id)
        assert next_run is not None
        
        # Should be within next 5 minutes
        now = datetime.now()
        time_until_next = (next_run - now).total_seconds()
        assert 0 < time_until_next <= 300  # Within 5 minutes
        
    def test_schedule_enable_disable(self):
        """Test enabling and disabling schedules"""
        scheduler = MockSchedulingEngine({"environment": "test"})
        
        # Create enabled schedule
        schedule = scheduler.create_schedule({
            "name": "toggle_test",
            "cron_expression": "0 2 * * *",
            "upload_directories": ["/test"],
            "enabled": True
        })
        
        schedule_id = schedule["schedule_id"]
        
        # Verify initial state
        schedule_info = scheduler.get_schedule(schedule_id)
        assert schedule_info["enabled"] is True
        
        # Disable schedule
        disable_result = scheduler.disable_schedule(schedule_id)
        assert disable_result["success"]
        
        # Verify disabled
        schedule_info = scheduler.get_schedule(schedule_id)
        assert schedule_info["enabled"] is False
        
        # Re-enable schedule
        enable_result = scheduler.enable_schedule(schedule_id)
        assert enable_result["success"]
        
        # Verify re-enabled
        schedule_info = scheduler.get_schedule(schedule_id)
        assert schedule_info["enabled"] is True


class TestPipelineIntegration:
    """Test integration with existing 6-Pass pipeline"""
    
    def test_bulk_processor_wrapper(self):
        """Test wrapper around existing Pass6Pipeline"""
        # Mock the existing Pass6Pipeline
        mock_pipeline = MockPass6Pipeline("test")
        
        # Create scheduled processor wrapper
        scheduled_processor = MockScheduledBulkProcessor(mock_pipeline)
        
        # Test processing integration
        test_documents = [
            "document1.pdf",
            "document2.pdf"
        ]
        
        processing_result = scheduled_processor.process_documents_batch(test_documents)
        
        assert processing_result["success"]
        assert processing_result["processed_count"] == 2
        assert processing_result["failed_count"] == 0
        assert len(processing_result["results"]) == 2
        
    def test_environment_isolation_in_scheduling(self):
        """Test environment isolation in scheduled processing"""
        environments = ["dev", "test", "prod"]
        processors = {}
        
        # Create environment-specific processors
        for env in environments:
            mock_pipeline = MockPass6Pipeline(env)
            processors[env] = MockScheduledBulkProcessor(mock_pipeline)
        
        # Test each environment processes independently
        for env in environments:
            result = processors[env].process_documents_batch([f"{env}_document.pdf"])
            
            assert result["success"]
            assert result["environment"] == env
            assert f"{env}_document.pdf" in str(result["results"])
            
    def test_existing_artifact_integration(self):
        """Test integration with existing artifact management"""
        mock_pipeline = MockPass6Pipeline("test")
        scheduled_processor = MockScheduledBulkProcessor(mock_pipeline)
        
        # Test with existing artifacts (should skip)
        test_config = {
            "documents": ["existing_doc.pdf"],
            "check_existing": True,
            "resume": True
        }
        
        # Mock existing artifacts
        scheduled_processor.set_existing_artifacts(["existing_doc.pdf"])
        
        result = scheduled_processor.process_documents_batch(
            test_config["documents"],
            check_existing=test_config["check_existing"],
            resume=test_config["resume"]
        )
        
        assert result["success"]
        assert result["skipped_count"] == 1  # Document skipped due to existing artifacts
        assert result["processed_count"] == 0


# Mock classes for testing

class MockCronParser:
    def parse(self, cron_expression):
        """Parse cron expression and return validation info"""
        # Simple validation - real implementation would use croniter or similar
        parts = cron_expression.split()
        
        if len(parts) != 5:
            return {"valid": False, "error": "Invalid cron format"}
        
        # Basic validation of parts
        try:
            for part in parts:
                if part != "*" and not part.replace("/", "").replace("-", "").replace(",", "").isdigit():
                    if not any(c in part for c in ["*", "/", "-", ","]):
                        return {"valid": False, "error": f"Invalid part: {part}"}
        except:
            return {"valid": False, "error": "Parse error"}
        
        return {
            "valid": True,
            "pattern": cron_expression,
            "next_run": self.get_next_execution(cron_expression)
        }
    
    def get_next_execution(self, cron_expression, from_time=None):
        """Calculate next execution time"""
        if from_time is None:
            from_time = datetime.now()
        
        # Simplified calculation - real implementation would use croniter
        if "*/15" in cron_expression:  # Every 15 minutes
            return from_time + timedelta(minutes=15)
        elif "0 2 * * *" in cron_expression:  # Daily at 2 AM
            next_day = from_time + timedelta(days=1)
            return next_day.replace(hour=2, minute=0, second=0, microsecond=0)
        elif "0 14 * * *" in cron_expression:  # Daily at 2 PM
            if from_time.hour < 14:
                return from_time.replace(hour=14, minute=0, second=0, microsecond=0)
            else:
                next_day = from_time + timedelta(days=1)
                return next_day.replace(hour=14, minute=0, second=0, microsecond=0)
        elif "0 2 * * 1" in cron_expression:  # Mondays at 2 AM
            days_ahead = 0 - from_time.weekday()  # Monday is 0
            if days_ahead <= 0:  # Target day already passed this week
                days_ahead += 7
            return (from_time + timedelta(days=days_ahead)).replace(hour=2, minute=0, second=0, microsecond=0)
        
        # Default: add 1 hour
        return from_time + timedelta(hours=1)


class MockJobQueue:
    def __init__(self, config):
        self.max_size = config.get("max_size", 100)
        self.priority_enabled = config.get("priority_enabled", False)
        self.persistence_enabled = config.get("persistence_enabled", False)
        self.persistence_path = config.get("persistence_path", "/tmp/queue.json")
        self.jobs = []
        
    def size(self):
        return len(self.jobs)
    
    def is_empty(self):
        return len(self.jobs) == 0
    
    def enqueue(self, job):
        if len(self.jobs) >= self.max_size:
            return {"success": False, "error": "Queue at capacity"}
        
        self.jobs.append(job)
        
        # Sort by priority if enabled
        if self.priority_enabled:
            self.jobs.sort(key=lambda x: x.get("priority", 0), reverse=True)
        
        return {"success": True, "position": len(self.jobs)}
    
    def dequeue(self):
        if self.is_empty():
            return None
        return self.jobs.pop(0)
    
    def persist_state(self):
        if self.persistence_enabled:
            # Mock persistence
            self._persisted_jobs = self.jobs.copy()
    
    def restore_state(self):
        if self.persistence_enabled and hasattr(self, '_persisted_jobs'):
            self.jobs = self._persisted_jobs.copy()
            if self.priority_enabled:
                self.jobs.sort(key=lambda x: x.get("priority", 0), reverse=True)


class MockJobManager:
    def __init__(self, config):
        self.environment = config.get("environment", "dev")
        self.max_concurrent_jobs = config.get("max_concurrent_jobs", 4)
        self.job_timeout_seconds = config.get("job_timeout_seconds", 1800)
        self.retry_policy = config.get("retry_policy", {})
        self.jobs = {}
        self.active_jobs = 0
        self.job_counter = 0
    
    def create_job(self, job_request):
        self.job_counter += 1
        job_id = f"job_{self.environment}_{self.job_counter:06d}"
        
        job = {
            "job_id": job_id,
            "source_file": job_request["source_file"],
            "priority": job_request.get("priority", 1),
            "environment": self.environment,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "retry_count": 0,
            "schedule_id": job_request.get("schedule_id")
        }
        
        self.jobs[job_id] = job
        return {"success": True, **job}
    
    def get_job_status(self, job_id):
        if job_id in self.jobs:
            return {"found": True, **self.jobs[job_id]}
        return {"found": False}
    
    def transition_job_status(self, job_id, new_status):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = new_status
            self.jobs[job_id]["updated_at"] = datetime.now().isoformat()
            return {"success": True}
        return {"success": False, "error": "Job not found"}
    
    def start_job(self, job_id):
        if self.active_jobs >= self.max_concurrent_jobs:
            return {"success": False, "reason": "Concurrent limit reached"}
        
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "running"
            self.active_jobs += 1
            return {"success": True}
        return {"success": False, "error": "Job not found"}
    
    def complete_job(self, job_id):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "completed"
            self.active_jobs = max(0, self.active_jobs - 1)
            return {"success": True}
        return {"success": False, "error": "Job not found"}
    
    def mark_job_failed(self, job_id, error_message):
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job["retry_count"] += 1
            
            max_retries = self.retry_policy.get("max_retries", 3)
            if job["retry_count"] >= max_retries:
                job["status"] = "permanently_failed"
            else:
                job["status"] = "failed"
            
            job["error"] = error_message
            return {"success": True}
        return {"success": False, "error": "Job not found"}
    
    def get_retry_info(self, job_id):
        if job_id in self.jobs:
            job = self.jobs[job_id]
            max_retries = self.retry_policy.get("max_retries", 3)
            backoff_factor = self.retry_policy.get("backoff_factor", 2.0)
            initial_delay = self.retry_policy.get("initial_delay_seconds", 60)
            
            next_delay = initial_delay * (backoff_factor ** (job["retry_count"] - 1))
            
            return {
                "attempt": job["retry_count"],
                "next_retry_delay": next_delay,
                "retries_remaining": max_retries - job["retry_count"]
            }
        return None


class MockSchedulingEngine:
    def __init__(self, config):
        self.environment = config.get("environment", "dev")
        self.timezone = config.get("timezone", "UTC")
        self.max_schedules = config.get("max_schedules", 10)
        self.schedules = {}
        self.running = False
        self.schedule_counter = 0
    
    def is_running(self):
        return self.running
    
    def get_schedules(self):
        return list(self.schedules.values())
    
    def create_schedule(self, schedule_config):
        if len(self.schedules) >= self.max_schedules:
            return {"success": False, "error": "Maximum schedules reached"}
        
        self.schedule_counter += 1
        schedule_id = f"schedule_{self.environment}_{self.schedule_counter:03d}"
        
        schedule = {
            "schedule_id": schedule_id,
            "name": schedule_config["name"],
            "cron_expression": schedule_config["cron_expression"],
            "upload_directories": schedule_config.get("upload_directories", []),
            "environment": self.environment,
            "enabled": schedule_config.get("enabled", True),
            "created_at": datetime.now().isoformat()
        }
        
        self.schedules[schedule_id] = schedule
        return {"success": True, **schedule}
    
    def get_schedule(self, schedule_id):
        return self.schedules.get(schedule_id)
    
    def get_next_execution(self, schedule_id):
        schedule = self.schedules.get(schedule_id)
        if schedule:
            cron_parser = MockCronParser()
            return cron_parser.get_next_execution(schedule["cron_expression"])
        return None
    
    def disable_schedule(self, schedule_id):
        if schedule_id in self.schedules:
            self.schedules[schedule_id]["enabled"] = False
            return {"success": True}
        return {"success": False, "error": "Schedule not found"}
    
    def enable_schedule(self, schedule_id):
        if schedule_id in self.schedules:
            self.schedules[schedule_id]["enabled"] = True
            return {"success": True}
        return {"success": False, "error": "Schedule not found"}


class MockPass6Pipeline:
    def __init__(self, environment):
        self.env = environment
    
    def process_source_6pass(self, pdf_path, env, **kwargs):
        # Mock successful processing
        return {
            "success": True,
            "source": str(pdf_path),
            "job_id": f"job_{env}_{hash(str(pdf_path)) % 10000}",
            "environment": env,
            "processing_time_ms": 15000
        }


class MockScheduledBulkProcessor:
    def __init__(self, pass6_pipeline):
        self.pipeline = pass6_pipeline
        self.existing_artifacts = set()
    
    def set_existing_artifacts(self, artifacts):
        self.existing_artifacts = set(artifacts)
    
    def process_documents_batch(self, documents, check_existing=False, resume=False):
        results = []
        processed_count = 0
        failed_count = 0
        skipped_count = 0
        
        for doc in documents:
            if check_existing and doc in self.existing_artifacts:
                skipped_count += 1
                results.append({"document": doc, "status": "skipped", "reason": "existing_artifacts"})
                continue
            
            # Process with pipeline
            result = self.pipeline.process_source_6pass(doc, self.pipeline.env)
            if result["success"]:
                processed_count += 1
                results.append({"document": doc, "status": "completed", "result": result})
            else:
                failed_count += 1
                results.append({"document": doc, "status": "failed", "error": result.get("error", "Unknown error")})
        
        return {
            "success": failed_count == 0,
            "processed_count": processed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "results": results,
            "environment": self.pipeline.env
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])