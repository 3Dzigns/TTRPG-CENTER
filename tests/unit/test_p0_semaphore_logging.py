"""
P0.1 Unit Tests: Enhanced Semaphore Logging
Tests for semaphore wait/acquire/release logging in ScheduledBulkProcessor.
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from typing import Dict, Any

from src_common.scheduled_processor import ScheduledBulkProcessor


@dataclass
class MockJob:
    """Mock job for testing"""
    id: str
    source_path: str
    environment: str


class MockPipeline:
    """Mock pipeline for testing"""
    
    async def process_source(self, source_path: str, environment: str, artifacts_dir: str = None) -> Dict[str, Any]:
        """Simulate pipeline processing"""
        await asyncio.sleep(0.1)  # Simulate work
        return {
            "job_id": f"test_{int(time.time())}",
            "status": "completed",
            "processing_time": 0.1,
        }


class TestSemaphoreLogging:
    """Test enhanced semaphore logging functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = {
            "max_concurrent_jobs": 2,
            "artifacts_base": "/tmp/test_artifacts"
        }
        self.mock_pipeline = MockPipeline()
        
    @pytest.mark.asyncio
    async def test_semaphore_wait_logging(self, caplog):
        """Test logging when jobs wait for semaphore slots"""
        processor = ScheduledBulkProcessor(
            config=self.config,
            pipeline=self.mock_pipeline,
            max_concurrent_jobs=1  # Force waiting
        )
        
        # Create multiple jobs to force waiting
        jobs = [
            MockJob(id="job_001", source_path="/test/doc1.pdf", environment="test"),
            MockJob(id="job_002", source_path="/test/doc2.pdf", environment="test"),
            MockJob(id="job_003", source_path="/test/doc3.pdf", environment="test"),
        ]
        
        # Execute jobs concurrently
        tasks = [processor.execute_job(job) for job in jobs]
        results = await asyncio.gather(*tasks)
        
        # Verify all jobs completed
        assert len(results) == 3
        assert all(r["status"] == "completed" for r in results)
        
        # Check semaphore logging messages
        log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        
        # Should see waiting messages
        waiting_logs = [msg for msg in log_messages if "waiting for execution slot" in msg]
        assert len(waiting_logs) >= 2, f"Expected waiting logs, got: {waiting_logs}"
        
        # Should see acquisition messages
        acquire_logs = [msg for msg in log_messages if "acquired execution slot" in msg]
        assert len(acquire_logs) == 3, f"Expected 3 acquire logs, got: {acquire_logs}"
        
        # Should see release messages
        release_logs = [msg for msg in log_messages if "releasing execution slot" in msg]
        assert len(release_logs) == 3, f"Expected 3 release logs, got: {release_logs}"
        
    @pytest.mark.asyncio
    async def test_semaphore_slot_tracking(self, caplog):
        """Test accurate slot usage tracking in logs"""
        processor = ScheduledBulkProcessor(
            config=self.config,
            pipeline=self.mock_pipeline,
            max_concurrent_jobs=2
        )
        
        jobs = [
            MockJob(id="job_A", source_path="/test/docA.pdf", environment="test"),
            MockJob(id="job_B", source_path="/test/docB.pdf", environment="test"),
        ]
        
        # Execute jobs
        results = await asyncio.gather(*[processor.execute_job(job) for job in jobs])
        
        # Check slot tracking in logs
        log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        
        # Find acquisition messages and verify slot numbers
        acquire_logs = [msg for msg in log_messages if "acquired execution slot" in msg]
        
        # Should show proper slot allocation
        assert any("slot 1/2" in msg for msg in acquire_logs), f"Missing slot 1/2 in: {acquire_logs}"
        assert any("slot 2/2" in msg for msg in acquire_logs), f"Missing slot 2/2 in: {acquire_logs}"
        
        # Check release messages show proper count down
        release_logs = [msg for msg in log_messages if "releasing execution slot" in msg]
        assert any("active slots now: 1/2" in msg for msg in release_logs), f"Missing countdown in: {release_logs}"
        
    @pytest.mark.asyncio
    async def test_timing_metrics_logging(self, caplog):
        """Test wait time and execution time logging accuracy"""
        
        # Create slow pipeline to test timing
        class SlowPipeline:
            async def process_source(self, source_path: str, environment: str, artifacts_dir: str = None):
                await asyncio.sleep(0.2)  # Simulate longer work
                return {"job_id": "slow_job", "status": "completed", "processing_time": 0.2}
        
        processor = ScheduledBulkProcessor(
            config=self.config,
            pipeline=SlowPipeline(),
            max_concurrent_jobs=1
        )
        
        job = MockJob(id="timing_job", source_path="/test/timing.pdf", environment="test")
        result = await processor.execute_job(job)
        
        # Verify timing data in result
        assert "total_time" in result
        assert "wait_time" in result
        assert result["total_time"] > result["wait_time"]
        assert result["total_time"] > 0.15  # Should be at least processing time
        
        # Check timing in logs
        log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        
        # Should see wait time in acquisition message
        acquire_logs = [msg for msg in log_messages if "acquired execution slot after" in msg]
        assert len(acquire_logs) == 1, f"Expected 1 timing log, got: {acquire_logs}"
        assert "wait time" in acquire_logs[0]
        
    @pytest.mark.asyncio
    async def test_error_handling_with_logging(self, caplog):
        """Test error handling maintains proper logging"""
        
        # Create failing pipeline
        class FailingPipeline:
            async def process_source(self, source_path: str, environment: str, artifacts_dir: str = None):
                raise ValueError("Test pipeline failure")
        
        processor = ScheduledBulkProcessor(
            config=self.config,
            pipeline=FailingPipeline(),
            max_retry_attempts=2
        )
        
        job = MockJob(id="fail_job", source_path="/test/fail.pdf", environment="test")
        result = await processor.execute_job(job)
        
        # Should return failed result
        assert result["status"] == "failed"
        assert "Test pipeline failure" in result["error_message"]
        
        # Check error logging
        log_messages = [record.message for record in caplog.records]
        
        # Should see retry messages
        warning_logs = [record.message for record in caplog.records if record.levelname == "WARNING"]
        assert len(warning_logs) >= 2, f"Expected retry warnings, got: {warning_logs}"
        
        # Should see final error
        error_logs = [record.message for record in caplog.records if record.levelname == "ERROR"]
        assert len(error_logs) >= 1, f"Expected final error log, got: {error_logs}"
        
        # Should still see proper release logging
        release_logs = [msg for msg in log_messages if "releasing execution slot" in msg]
        assert len(release_logs) == 1, f"Expected release log even on failure, got: {release_logs}"
        
    @pytest.mark.asyncio
    async def test_concurrent_slot_accuracy(self, caplog):
        """Test slot counting accuracy under high concurrency"""
        processor = ScheduledBulkProcessor(
            config={"max_concurrent_jobs": 3, "artifacts_base": "/tmp/test"},
            pipeline=self.mock_pipeline,
            max_concurrent_jobs=3
        )
        
        # Create many concurrent jobs
        jobs = [MockJob(id=f"concurrent_{i}", source_path=f"/test/doc_{i}.pdf", environment="test") 
                for i in range(10)]
        
        # Execute all concurrently
        results = await asyncio.gather(*[processor.execute_job(job) for job in jobs])
        
        # All should complete successfully
        assert len(results) == 10
        assert all(r["status"] == "completed" for r in results)
        
        # Check that we never exceed max concurrent jobs
        log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
        
        acquire_logs = [msg for msg in log_messages if "acquired execution slot" in msg]
        
        # Should see proper slot allocation (1/3, 2/3, 3/3, then cycling)
        slot_counts = []
        for msg in acquire_logs:
            if "slot" in msg:
                # Extract slot count like "slot 2/3"
                parts = msg.split("slot ")[1].split(")")[0]
                current, max_slots = parts.split("/")
                slot_counts.append(int(current))
        
        # No slot count should exceed 3
        assert all(count <= 3 for count in slot_counts), f"Slot counts exceeded limit: {slot_counts}"
        assert max(slot_counts) == 3, f"Expected max slot usage of 3, got max: {max(slot_counts)}"
        
        
if __name__ == "__main__":
    pytest.main([__file__])