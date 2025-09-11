#!/usr/bin/env python3
"""
Functional tests for FR-002 end-to-end scheduled processing workflow.

Tests the complete nightly bulk ingestion scheduler workflow including:
- Scheduled job execution and timing
- Document discovery and queue processing
- Integration with existing 6-Pass pipeline
- Environment-specific processing isolation
- Job lifecycle management and status tracking
- Concurrent processing and resource management
- Error handling and recovery scenarios
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
    from src_common.document_scanner import DocumentScanner
    from src_common.processing_queue import ProcessingQueue
except ImportError:
    # Mock imports for testing before implementation
    SchedulingEngine = Mock
    CronParser = Mock
    JobManager = Mock
    JobQueue = Mock
    Job = Mock
    JobStatus = Mock
    ScheduledBulkProcessor = Mock
    DocumentScanner = Mock
    ProcessingQueue = Mock

logger = get_logger(__name__)


class TestScheduledProcessingWorkflow(BaseTestCase):
    """Test complete scheduled processing workflows."""
    
    @pytest.fixture(autouse=True)
    def setup_scheduler_environment(self, temp_env_dir):
        """Set up scheduler testing environment with temporary directories."""
        self.env_dir = temp_env_dir
        self.upload_dir = self.env_dir / "uploads"
        self.artifacts_dir = self.env_dir / "artifacts" / "ingest" / "dev"
        self.queue_state_dir = self.env_dir / "queue_state"
        
        # Create required directories
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.queue_state_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test PDF files
        self.create_test_pdf_files()
        
        # Initialize scheduler components
        self.scheduler_config = {
            "upload_directories": [str(self.upload_dir)],
            "artifacts_base": str(self.artifacts_dir),
            "queue_state_dir": str(self.queue_state_dir),
            "environment": "dev",
            "max_concurrent_jobs": 2,
            "job_timeout_seconds": 300,
            "scan_interval_seconds": 10,
            "retry_attempts": 3,
            "retry_delay_seconds": 5
        }
        
        # Mock pipeline for testing
        self.mock_pipeline = self.create_mock_pipeline()
        
    def create_test_pdf_files(self):
        """Create test PDF files for document discovery testing."""
        test_files = [
            "test_document_1.pdf",
            "test_document_2.pdf", 
            "priority_document.pdf",
            "large_document.pdf",
            "corrupted_document.pdf"
        ]
        
        for filename in test_files:
            test_file = self.upload_dir / filename
            # Create mock PDF content
            with open(test_file, 'wb') as f:
                if "corrupted" in filename:
                    f.write(b"Invalid PDF content")
                elif "large" in filename:
                    f.write(b"%PDF-1.4\n" + b"Large PDF content " * 1000)
                else:
                    f.write(b"%PDF-1.4\nTest PDF content\n%%EOF")
    
    def create_mock_pipeline(self):
        """Create mock 6-Pass pipeline for testing."""
        mock_pipeline = Mock()
        mock_pipeline.process_source = AsyncMock()
        mock_pipeline.validate_environment = Mock(return_value=True)
        mock_pipeline.cleanup_artifacts = Mock()
        
        # Mock successful processing results
        def mock_process_result(*args, **kwargs):
            return {
                "job_id": f"job_{int(time.time())}",
                "status": "completed",
                "passes_completed": 6,
                "artifacts_created": 15,
                "processing_time": 45.2,
                "errors": []
            }
        
        mock_pipeline.process_source.return_value = mock_process_result()
        return mock_pipeline


class TestNightlyScheduleExecution(TestScheduledProcessingWorkflow):
    """Test nightly schedule execution and timing."""
    
    @pytest.mark.asyncio
    async def test_nightly_schedule_triggers_at_correct_time(self):
        """Test that nightly schedule triggers jobs at the configured time."""
        # Configure nightly schedule (2:00 AM)
        cron_schedule = "0 2 * * *"
        
        with patch('src_common.scheduler_engine.datetime') as mock_datetime:
            # Mock current time as 1:59:59 AM
            mock_now = datetime(2025, 1, 15, 1, 59, 59)
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime = datetime.strptime
            
            scheduler = SchedulingEngine(config=self.scheduler_config)
            cron_parser = CronParser(cron_schedule)
            
            # Check that job is not triggered yet
            next_run = cron_parser.get_next_execution_time(mock_now)
            assert next_run.hour == 2
            assert next_run.minute == 0
            
            # Fast-forward to 2:00 AM
            mock_datetime.now.return_value = datetime(2025, 1, 15, 2, 0, 0)
            
            # Verify job triggers
            should_trigger = cron_parser.should_trigger(mock_datetime.now.return_value)
            assert should_trigger is True
    
    @pytest.mark.asyncio
    async def test_schedule_persistence_across_restarts(self):
        """Test that scheduled jobs persist across scheduler restarts."""
        schedule_state_file = self.queue_state_dir / "scheduler_state.json"
        
        # Create initial scheduler and add job
        scheduler1 = SchedulingEngine(config=self.scheduler_config)
        job_id = scheduler1.schedule_job(
            name="nightly_ingestion",
            cron_schedule="0 2 * * *",
            job_type="bulk_ingestion",
            priority=1
        )
        
        # Simulate scheduler shutdown
        scheduler1.save_state(schedule_state_file)
        del scheduler1
        
        # Create new scheduler instance and load state
        scheduler2 = SchedulingEngine(config=self.scheduler_config)
        scheduler2.load_state(schedule_state_file)
        
        # Verify job persisted
        scheduled_jobs = scheduler2.get_scheduled_jobs()
        assert len(scheduled_jobs) == 1
        assert scheduled_jobs[0]["id"] == job_id
        assert scheduled_jobs[0]["name"] == "nightly_ingestion"
    
    @pytest.mark.asyncio 
    async def test_multiple_schedule_coordination(self):
        """Test coordination of multiple scheduled jobs."""
        scheduler = SchedulingEngine(config=self.scheduler_config)
        
        # Schedule multiple jobs
        job1_id = scheduler.schedule_job(
            name="nightly_full_ingestion", 
            cron_schedule="0 2 * * *",
            job_type="bulk_ingestion",
            priority=1
        )
        
        job2_id = scheduler.schedule_job(
            name="hourly_incremental_scan",
            cron_schedule="0 * * * *", 
            job_type="document_scan",
            priority=2
        )
        
        job3_id = scheduler.schedule_job(
            name="weekly_cleanup",
            cron_schedule="0 3 * * 0",
            job_type="maintenance",
            priority=3
        )
        
        # Verify all jobs scheduled
        scheduled_jobs = scheduler.get_scheduled_jobs()
        assert len(scheduled_jobs) == 3
        
        job_ids = [job["id"] for job in scheduled_jobs]
        assert job1_id in job_ids
        assert job2_id in job_ids  
        assert job3_id in job_ids


class TestDocumentDiscoveryIntegration(TestScheduledProcessingWorkflow):
    """Test integration with document discovery and queue processing."""
    
    @pytest.mark.asyncio
    async def test_automatic_document_discovery_and_queueing(self):
        """Test automatic discovery of new documents and queue addition."""
        # Initialize document scanner
        scanner = DocumentScanner(
            scan_directories=[str(self.upload_dir)],
            supported_extensions=[".pdf"],
            scan_interval_seconds=1
        )
        
        # Initialize processing queue
        queue = ProcessingQueue(
            state_file=self.queue_state_dir / "processing_queue.json",
            max_size=100
        )
        
        # Start document scanning
        scanner.start_monitoring()
        
        # Add new document during monitoring
        new_doc = self.upload_dir / "new_test_document.pdf"
        with open(new_doc, 'wb') as f:
            f.write(b"%PDF-1.4\nNew document content\n%%EOF")
        
        # Wait for discovery
        await asyncio.sleep(2)
        
        # Verify document was discovered and queued
        discovered_docs = scanner.get_discovered_documents()
        assert len(discovered_docs) >= 1
        assert any("new_test_document.pdf" in doc["path"] for doc in discovered_docs)
        
        scanner.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_document_priority_assignment_and_queue_ordering(self):
        """Test document priority assignment and proper queue ordering."""
        queue = ProcessingQueue(
            state_file=self.queue_state_dir / "priority_queue.json",
            max_size=100
        )
        
        # Add documents with different priorities
        documents = [
            {"path": str(self.upload_dir / "large_document.pdf"), "priority": 3, "size_mb": 50},
            {"path": str(self.upload_dir / "priority_document.pdf"), "priority": 1, "size_mb": 5},
            {"path": str(self.upload_dir / "test_document_1.pdf"), "priority": 2, "size_mb": 10}
        ]
        
        for doc in documents:
            queue.add_document(
                doc["path"], 
                priority=doc["priority"],
                metadata={"size_mb": doc["size_mb"]}
            )
        
        # Verify queue ordering by priority (lower number = higher priority)
        next_doc = queue.get_next_document()
        assert "priority_document.pdf" in next_doc["path"]
        assert next_doc["priority"] == 1
        
        next_doc = queue.get_next_document()
        assert "test_document_1.pdf" in next_doc["path"]
        assert next_doc["priority"] == 2
        
        next_doc = queue.get_next_document()
        assert "large_document.pdf" in next_doc["path"]
        assert next_doc["priority"] == 3
    
    @pytest.mark.asyncio
    async def test_duplicate_document_detection(self):
        """Test detection and handling of duplicate documents."""
        queue = ProcessingQueue(
            state_file=self.queue_state_dir / "duplicate_queue.json",
            max_size=100
        )
        
        doc_path = str(self.upload_dir / "test_document_1.pdf")
        
        # Add document first time
        result1 = queue.add_document(doc_path, priority=1)
        assert result1["status"] == "added"
        
        # Attempt to add same document again
        result2 = queue.add_document(doc_path, priority=1)
        assert result2["status"] == "duplicate"
        assert result2["existing_job_id"] is not None
        
        # Verify only one instance in queue
        queue_status = queue.get_status()
        assert queue_status["total_documents"] == 1


class TestPipelineIntegration(TestScheduledProcessingWorkflow):
    """Test integration with existing 6-Pass pipeline."""
    
    @pytest.mark.asyncio
    async def test_scheduled_job_executes_6pass_pipeline(self):
        """Test that scheduled jobs properly execute the 6-Pass pipeline."""
        # Initialize scheduled processor
        processor = ScheduledBulkProcessor(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline
        )
        
        # Create test job
        job = Job(
            id="test_job_001",
            name="test_bulk_processing",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment="dev",
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute job
        result = await processor.execute_job(job)
        
        # Verify pipeline was called
        self.mock_pipeline.process_source.assert_called_once()
        
        # Verify job completion
        assert result["status"] == "completed"
        assert result["job_id"] == "test_job_001"
        assert "processing_time" in result
    
    @pytest.mark.asyncio
    async def test_concurrent_job_execution_with_resource_limits(self):
        """Test concurrent job execution respecting resource limits."""
        processor = ScheduledBulkProcessor(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline,
            max_concurrent_jobs=2
        )
        
        # Create multiple jobs
        jobs = []
        for i in range(4):
            job = Job(
                id=f"concurrent_job_{i:03d}",
                name=f"concurrent_processing_{i}",
                job_type="bulk_ingestion",
                source_path=str(self.upload_dir / f"test_document_{i % 2 + 1}.pdf"),
                environment="dev",
                priority=1,
                created_at=datetime.now(),
                status=JobStatus.PENDING
            )
            jobs.append(job)
        
        # Execute jobs concurrently
        start_time = time.time()
        
        # Mock pipeline to take some time
        async def slow_pipeline_process(*args, **kwargs):
            await asyncio.sleep(0.5)
            return {
                "job_id": args[0] if args else "unknown",
                "status": "completed",
                "processing_time": 0.5
            }
        
        self.mock_pipeline.process_source.side_effect = slow_pipeline_process
        
        # Execute all jobs
        tasks = [processor.execute_job(job) for job in jobs]
        results = await asyncio.gather(*tasks)
        
        execution_time = time.time() - start_time
        
        # Verify results
        assert len(results) == 4
        assert all(r["status"] == "completed" for r in results)
        
        # With max_concurrent_jobs=2, execution should take ~1 second (2 batches of 0.5s each)
        # allowing some tolerance for test execution overhead
        assert 0.8 <= execution_time <= 1.5
    
    @pytest.mark.asyncio
    async def test_job_failure_handling_and_retry_logic(self):
        """Test job failure handling and retry logic."""
        processor = ScheduledBulkProcessor(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline,
            max_retry_attempts=2,
            retry_delay_seconds=0.1
        )
        
        # Mock pipeline to fail initially then succeed
        call_count = 0
        async def failing_pipeline_process(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:  # Fail first 2 attempts
                raise Exception("Simulated pipeline failure")
            else:  # Succeed on 3rd attempt
                return {
                    "job_id": "retry_test_job",
                    "status": "completed",
                    "processing_time": 0.1,
                    "retry_count": call_count - 1
                }
        
        self.mock_pipeline.process_source.side_effect = failing_pipeline_process
        
        job = Job(
            id="retry_test_job",
            name="retry_test_processing",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment="dev",
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute job (should succeed after retries)
        result = await processor.execute_job(job)
        
        # Verify retry logic worked
        assert call_count == 3  # Initial attempt + 2 retries
        assert result["status"] == "completed"
        assert result["retry_count"] == 2


class TestEnvironmentIsolation(TestScheduledProcessingWorkflow):
    """Test environment-specific processing isolation."""
    
    @pytest.mark.parametrize("environment", ["dev", "test", "prod"])
    @pytest.mark.asyncio
    async def test_environment_specific_job_processing(self, environment):
        """Test job processing respects environment isolation."""
        env_config = self.scheduler_config.copy()
        env_config["environment"] = environment
        env_config["artifacts_base"] = str(self.env_dir / "artifacts" / "ingest" / environment)
        
        # Create environment-specific directories
        env_artifacts_dir = Path(env_config["artifacts_base"])
        env_artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        processor = ScheduledBulkProcessor(
            config=env_config,
            pipeline=self.mock_pipeline
        )
        
        # Mock pipeline to verify environment context
        def verify_environment_context(*args, **kwargs):
            # Verify environment is passed correctly
            assert "environment" in kwargs
            assert kwargs["environment"] == environment
            
            # Verify artifacts path is environment-specific
            if "artifacts_dir" in kwargs:
                assert environment in kwargs["artifacts_dir"]
            
            return {
                "job_id": f"{environment}_job",
                "status": "completed", 
                "environment": environment,
                "artifacts_path": str(env_artifacts_dir)
            }
        
        self.mock_pipeline.process_source.side_effect = verify_environment_context
        
        job = Job(
            id=f"{environment}_test_job",
            name=f"{environment}_processing",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment=environment,
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute job
        result = await processor.execute_job(job)
        
        # Verify environment-specific execution
        assert result["environment"] == environment
        assert environment in result["artifacts_path"]
    
    @pytest.mark.asyncio
    async def test_cross_environment_job_isolation(self):
        """Test that jobs from different environments don't interfere."""
        # Create processors for different environments
        dev_config = self.scheduler_config.copy()
        dev_config["environment"] = "dev"
        
        test_config = self.scheduler_config.copy()
        test_config["environment"] = "test"
        test_config["artifacts_base"] = str(self.env_dir / "artifacts" / "ingest" / "test")
        
        dev_processor = ScheduledBulkProcessor(config=dev_config, pipeline=self.mock_pipeline)
        test_processor = ScheduledBulkProcessor(config=test_config, pipeline=self.mock_pipeline)
        
        # Track environment calls
        environment_calls = []
        
        def track_environment_calls(*args, **kwargs):
            environment_calls.append(kwargs.get("environment", "unknown"))
            return {
                "job_id": f"job_{len(environment_calls)}",
                "status": "completed",
                "environment": kwargs.get("environment")
            }
        
        self.mock_pipeline.process_source.side_effect = track_environment_calls
        
        # Create jobs for different environments
        dev_job = Job(
            id="dev_isolation_job",
            environment="dev",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        test_job = Job(
            id="test_isolation_job", 
            environment="test",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_2.pdf"),
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute jobs simultaneously
        dev_result, test_result = await asyncio.gather(
            dev_processor.execute_job(dev_job),
            test_processor.execute_job(test_job)
        )
        
        # Verify isolation
        assert dev_result["environment"] == "dev"
        assert test_result["environment"] == "test"
        assert "dev" in environment_calls
        assert "test" in environment_calls
        assert len(set(environment_calls)) == 2  # Two distinct environments


class TestJobLifecycleManagement(TestScheduledProcessingWorkflow):
    """Test complete job lifecycle management and status tracking."""
    
    @pytest.mark.asyncio
    async def test_complete_job_lifecycle_workflow(self):
        """Test complete job lifecycle from creation to completion."""
        job_manager = JobManager(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline
        )
        
        # Track job status changes
        status_history = []
        
        def track_status_change(job_id, old_status, new_status):
            status_history.append({
                "job_id": job_id,
                "old_status": old_status,
                "new_status": new_status,
                "timestamp": datetime.now()
            })
        
        job_manager.on_status_change = track_status_change
        
        # Create job (PENDING status)
        job_id = job_manager.create_job(
            name="lifecycle_test_job",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment="dev",
            priority=1
        )
        
        # Start job execution (RUNNING status)
        await job_manager.start_job(job_id)
        
        # Simulate job completion (COMPLETED status) 
        await job_manager.complete_job(job_id, {
            "status": "completed",
            "processing_time": 30.5,
            "artifacts_created": 12
        })
        
        # Verify status progression
        job = job_manager.get_job(job_id)
        assert job.status == JobStatus.COMPLETED
        
        # Verify status history
        assert len(status_history) >= 2
        status_progression = [s["new_status"] for s in status_history]
        assert JobStatus.RUNNING in status_progression
        assert JobStatus.COMPLETED in status_progression
    
    @pytest.mark.asyncio
    async def test_job_cancellation_and_cleanup(self):
        """Test job cancellation and proper resource cleanup."""
        job_manager = JobManager(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline
        )
        
        # Mock long-running pipeline process
        async def long_running_process(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate long processing
            return {"status": "completed"}
        
        self.mock_pipeline.process_source.side_effect = long_running_process
        
        # Create and start job
        job_id = job_manager.create_job(
            name="cancellation_test_job",
            job_type="bulk_ingestion", 
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment="dev",
            priority=1
        )
        
        # Start job in background
        job_task = asyncio.create_task(job_manager.start_job(job_id))
        
        # Wait a bit then cancel
        await asyncio.sleep(0.1)
        cancel_result = await job_manager.cancel_job(job_id, reason="User requested cancellation")
        
        # Verify cancellation
        assert cancel_result["status"] == "cancelled"
        assert cancel_result["reason"] == "User requested cancellation"
        
        # Verify job status
        job = job_manager.get_job(job_id)
        assert job.status == JobStatus.CANCELLED
        
        # Cleanup background task
        job_task.cancel()
        try:
            await job_task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_job_status_persistence_and_recovery(self):
        """Test job status persistence across system restarts."""
        state_file = self.queue_state_dir / "job_manager_state.json"
        
        # Create initial job manager and jobs
        job_manager1 = JobManager(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline,
            state_file=state_file
        )
        
        job_id1 = job_manager1.create_job(
            name="persistence_test_job_1",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment="dev", 
            priority=1
        )
        
        job_id2 = job_manager1.create_job(
            name="persistence_test_job_2", 
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_2.pdf"),
            environment="dev",
            priority=2
        )
        
        # Mark one job as completed
        await job_manager1.complete_job(job_id1, {"status": "completed"})
        
        # Save state and simulate restart
        job_manager1.save_state()
        del job_manager1
        
        # Create new job manager instance and load state
        job_manager2 = JobManager(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline,
            state_file=state_file
        )
        job_manager2.load_state()
        
        # Verify job persistence
        job1 = job_manager2.get_job(job_id1)
        job2 = job_manager2.get_job(job_id2)
        
        assert job1 is not None
        assert job1.status == JobStatus.COMPLETED
        assert job2 is not None
        assert job2.status == JobStatus.PENDING


class TestErrorHandlingAndRecovery(TestScheduledProcessingWorkflow):
    """Test error handling and recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_corrupted_document_handling(self):
        """Test handling of corrupted or invalid documents."""
        processor = ScheduledBulkProcessor(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline
        )
        
        # Mock pipeline to detect corrupted document
        async def detect_corrupted_document(*args, **kwargs):
            source_path = kwargs.get("source_path", "")
            if "corrupted" in source_path:
                raise ValueError("Invalid PDF format: corrupted document")
            else:
                return {"status": "completed"}
        
        self.mock_pipeline.process_source.side_effect = detect_corrupted_document
        
        corrupted_job = Job(
            id="corrupted_doc_job",
            name="corrupted_document_processing",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "corrupted_document.pdf"),
            environment="dev",
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute job - should handle error gracefully
        result = await processor.execute_job(corrupted_job)
        
        # Verify error handling
        assert result["status"] == "failed"
        assert "corrupted document" in result["error_message"].lower()
        assert result["job_id"] == "corrupted_doc_job"
    
    @pytest.mark.asyncio
    async def test_system_resource_exhaustion_handling(self):
        """Test handling of system resource exhaustion scenarios."""
        # Configure processor with very low resource limits
        resource_config = self.scheduler_config.copy()
        resource_config["max_concurrent_jobs"] = 1
        resource_config["memory_limit_mb"] = 100
        resource_config["disk_space_limit_mb"] = 50
        
        processor = ScheduledBulkProcessor(
            config=resource_config,
            pipeline=self.mock_pipeline
        )
        
        # Mock resource exhaustion
        async def resource_exhaustion_simulation(*args, **kwargs):
            raise MemoryError("Insufficient memory for document processing")
        
        self.mock_pipeline.process_source.side_effect = resource_exhaustion_simulation
        
        job = Job(
            id="resource_exhaustion_job",
            name="resource_test_processing",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "large_document.pdf"),
            environment="dev",
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute job
        result = await processor.execute_job(job)
        
        # Verify resource exhaustion handling
        assert result["status"] == "failed"
        assert "memory" in result["error_message"].lower()
        assert result["requires_retry"] is True
    
    @pytest.mark.asyncio
    async def test_scheduler_service_recovery_after_crash(self):
        """Test scheduler service recovery after unexpected shutdown."""
        state_file = self.queue_state_dir / "crash_recovery_state.json"
        
        # Create scheduler with active jobs
        scheduler1 = SchedulingEngine(config=self.scheduler_config)
        job_manager1 = JobManager(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline,
            state_file=state_file
        )
        
        # Create jobs in various states
        pending_job_id = job_manager1.create_job(
            name="pending_recovery_job",
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_1.pdf"),
            environment="dev",
            priority=1
        )
        
        running_job_id = job_manager1.create_job(
            name="running_recovery_job", 
            job_type="bulk_ingestion",
            source_path=str(self.upload_dir / "test_document_2.pdf"),
            environment="dev",
            priority=1
        )
        
        # Simulate one job was running during crash
        await job_manager1.start_job(running_job_id)
        
        # Save state before "crash"
        job_manager1.save_state()
        
        # Simulate crash - destroy instances
        del scheduler1
        del job_manager1
        
        # Create new instances for recovery
        scheduler2 = SchedulingEngine(config=self.scheduler_config)
        job_manager2 = JobManager(
            config=self.scheduler_config,
            pipeline=self.mock_pipeline, 
            state_file=state_file
        )
        
        # Load state and perform recovery
        job_manager2.load_state()
        recovery_results = await job_manager2.recover_interrupted_jobs()
        
        # Verify recovery
        assert len(recovery_results) >= 1  # At least the running job should be recovered
        
        # Check job states after recovery
        pending_job = job_manager2.get_job(pending_job_id)
        running_job = job_manager2.get_job(running_job_id)
        
        assert pending_job.status == JobStatus.PENDING  # Should remain pending
        assert running_job.status in [JobStatus.PENDING, JobStatus.FAILED]  # Should be reset or marked failed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])