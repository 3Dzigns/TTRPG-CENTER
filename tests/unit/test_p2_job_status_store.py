"""
P2.1 Unit Tests: Job Status Store
Tests for job status storage, retrieval, and API functionality.
"""

import asyncio
import pytest
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from src_common.job_status_store import (
    JobStatusStore, JobStatusRecord, get_job_store
)
from src_common.progress_callback import (
    JobProgress, PassProgress, PassType, PassStatus
)


@pytest.fixture
def temp_storage_dir():
    """Create temporary directory for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def job_store(temp_storage_dir):
    """Create job status store with temporary storage"""
    return JobStatusStore(storage_dir=temp_storage_dir)


@pytest.fixture
def sample_job_record():
    """Create sample job status record"""
    return JobStatusRecord(
        job_id="test_job_123",
        source_path="/test/sample.pdf",
        environment="test",
        status="running",
        queued_time=time.time() - 120,  # 2 minutes ago
        start_time=time.time() - 60,    # 1 minute ago
        current_pass="pass_b_logical_split",
        progress_percentage=25.0
    )


@pytest.fixture
def sample_job_progress():
    """Create sample JobProgress with pass data"""
    job_progress = JobProgress(
        job_id="progress_job_456",
        source_path="/test/progress.pdf",
        environment="dev",
        start_time=time.time() - 30
    )
    
    # Add some pass progress
    pass_a = PassProgress(
        pass_type=PassType.PASS_A,
        status=PassStatus.COMPLETED,
        start_time=time.time() - 25,
        toc_entries=8
    )
    pass_a.complete(toc_entries=8)
    
    pass_b = PassProgress(
        pass_type=PassType.PASS_B,
        status=PassStatus.IN_PROGRESS,
        start_time=time.time() - 10,
        chunks_processed=15
    )
    
    job_progress.passes[PassType.PASS_A] = pass_a
    job_progress.passes[PassType.PASS_B] = pass_b
    job_progress.current_pass = PassType.PASS_B
    job_progress.overall_status = "running"
    
    return job_progress


class TestJobStatusRecord:
    """Test JobStatusRecord functionality"""
    
    def test_job_status_record_creation(self, sample_job_record):
        """Test JobStatusRecord creation and attributes"""
        assert sample_job_record.job_id == "test_job_123"
        assert sample_job_record.status == "running"
        assert sample_job_record.progress_percentage == 25.0
        assert sample_job_record.passes == {}
        assert sample_job_record.created_at is not None
        
    def test_from_job_progress(self, sample_job_progress):
        """Test creating JobStatusRecord from JobProgress"""
        record = JobStatusRecord.from_job_progress(sample_job_progress)
        
        assert record.job_id == "progress_job_456"
        assert record.source_path == "/test/progress.pdf"
        assert record.environment == "dev"
        assert record.status == "running"
        assert record.current_pass == "pass_b_logical_split"
        assert record.progress_percentage > 0  # Should calculate based on completed passes
        
        # Check pass data conversion
        assert "pass_a_toc_parse" in record.passes
        assert "pass_b_logical_split" in record.passes
        assert record.passes["pass_a_toc_parse"]["status"] == "completed"
        assert record.passes["pass_a_toc_parse"]["toc_entries"] == 8
        assert record.passes["pass_b_logical_split"]["status"] == "in_progress"
        assert record.passes["pass_b_logical_split"]["chunks_processed"] == 15


class TestJobStatusStore:
    """Test JobStatusStore functionality"""
    
    def test_store_initialization(self, temp_storage_dir):
        """Test job store initialization"""
        store = JobStatusStore(storage_dir=temp_storage_dir)
        
        assert store.storage_dir == temp_storage_dir
        assert len(store._active_jobs) == 0
        assert len(store._completed_jobs) == 0
        
        # Storage directory should be created
        assert store.storage_dir.exists()
        
        # Files are created on first save, not initialization
        # Create a job to trigger file creation
        store.create_job("init_test", "/test/init.pdf", "test")
        
        # Now files should exist
        assert (temp_storage_dir / "active_jobs.json").exists()
        assert (temp_storage_dir / "completed_jobs.json").exists()
    
    def test_create_job(self, job_store):
        """Test job creation"""
        record = job_store.create_job(
            job_id="new_job_789",
            source_path="/test/new.pdf",
            environment="test"
        )
        
        assert record.job_id == "new_job_789"
        assert record.status == "queued"
        assert record.queued_time > 0
        assert record.start_time is None
        
        # Verify storage
        retrieved = job_store.get_job_status("new_job_789")
        assert retrieved is not None
        assert retrieved.job_id == "new_job_789"
    
    def test_update_job_from_progress(self, job_store, sample_job_progress):
        """Test updating job from JobProgress"""
        # Initial update - should create record
        job_store.update_job_from_progress(sample_job_progress)
        
        record = job_store.get_job_status("progress_job_456")
        assert record is not None
        assert record.status == "running"
        assert record.current_pass == "pass_b_logical_split"
        assert len(record.passes) == 2
        
        # Update with new progress
        sample_job_progress.overall_status = "completed"
        job_store.update_job_from_progress(sample_job_progress)
        
        updated_record = job_store.get_job_status("progress_job_456")
        assert updated_record.status == "completed"
    
    def test_complete_job(self, job_store):
        """Test job completion"""
        # Create job
        record = job_store.create_job("complete_job", "/test/complete.pdf", "test")
        
        # Complete job
        result = {
            "status": "completed",
            "processing_time": 45.2,
            "wait_time": 2.1,
            "artifacts_path": "/test/artifacts",
            "thread_name": "worker_1"
        }
        
        job_store.complete_job("complete_job", result)
        
        # Should no longer be in active jobs
        assert job_store.get_job_status("complete_job") is not None
        assert "complete_job" not in job_store._active_jobs
        assert "complete_job" in job_store._completed_jobs
        
        completed_record = job_store._completed_jobs["complete_job"]
        assert completed_record.status == "completed"
        assert completed_record.processing_time == 45.2
        assert completed_record.wait_time == 2.1
        assert completed_record.thread_name == "worker_1"
    
    def test_get_active_jobs(self, job_store):
        """Test retrieving active jobs"""
        # Create multiple jobs
        job_store.create_job("active_1", "/test/active1.pdf", "test")
        job_store.create_job("active_2", "/test/active2.pdf", "dev")
        
        active_jobs = job_store.get_active_jobs()
        assert len(active_jobs) == 2
        
        job_ids = [job.job_id for job in active_jobs]
        assert "active_1" in job_ids
        assert "active_2" in job_ids
    
    def test_get_job_history(self, job_store):
        """Test job history retrieval"""
        # Create and complete jobs
        for i in range(5):
            job_id = f"history_job_{i}"
            job_store.create_job(job_id, f"/test/history{i}.pdf", "test")
            job_store.complete_job(job_id, {"status": "completed", "processing_time": i * 10})
        
        # Get history
        history = job_store.get_job_history(limit=3)
        assert len(history) == 3
        
        # Should be sorted by completion time (most recent first)
        job_ids = [job.job_id for job in history]
        assert "history_job_4" in job_ids  # Most recent
    
    def test_get_job_statistics(self, job_store):
        """Test job statistics calculation"""
        # Create active jobs
        job_store.create_job("stats_active_1", "/test/active1.pdf", "test")
        job_store.create_job("stats_active_2", "/test/active2.pdf", "dev")
        
        # Create completed jobs
        job_store.create_job("stats_success_1", "/test/success1.pdf", "test")
        job_store.complete_job("stats_success_1", {"status": "completed", "processing_time": 30.0})
        
        job_store.create_job("stats_success_2", "/test/success2.pdf", "test") 
        job_store.complete_job("stats_success_2", {"status": "completed", "processing_time": 40.0})
        
        job_store.create_job("stats_failed_1", "/test/failed1.pdf", "test")
        job_store.complete_job("stats_failed_1", {"status": "failed", "error_message": "Test error"})
        
        # Get statistics
        stats = job_store.get_job_statistics()
        
        assert stats["active_jobs"] == 2
        assert stats["total_completed"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert abs(stats["success_rate"] - 66.67) < 0.1  # 2/3 = 66.67%
        assert stats["average_processing_time"] == 35.0  # (30 + 40) / 2
        
        # Test environment filtering
        test_stats = job_store.get_job_statistics(environment="test")
        assert test_stats["active_jobs"] == 1  # Only one test env active job
    
    def test_disk_persistence(self, temp_storage_dir):
        """Test that job data persists to disk"""
        # Create store and add job
        store1 = JobStatusStore(storage_dir=temp_storage_dir)
        store1.create_job("persist_job", "/test/persist.pdf", "test")
        
        # Create new store instance - should load from disk
        store2 = JobStatusStore(storage_dir=temp_storage_dir)
        
        # Should have the job from disk
        job = store2.get_job_status("persist_job")
        assert job is not None
        assert job.job_id == "persist_job"
    
    def test_completed_job_cleanup(self, job_store):
        """Test that old completed jobs are cleaned up"""
        # Create more than 100 completed jobs
        for i in range(105):
            job_id = f"cleanup_job_{i:03d}"
            job_store.create_job(job_id, f"/test/cleanup{i}.pdf", "test")
            # Stagger completion times
            result = {"status": "completed", "processing_time": 10.0}
            job_store.complete_job(job_id, result)
            job_store._completed_jobs[job_id].end_time = time.time() - (105 - i)
        
        # Should only keep the 100 most recent
        assert len(job_store._completed_jobs) == 100
        
        # Should have kept the most recent ones
        assert "cleanup_job_104" in job_store._completed_jobs
        assert "cleanup_job_004" not in job_store._completed_jobs


class TestJobStatusStoreAsync:
    """Test async functionality of job status store"""
    
    @pytest.mark.asyncio
    async def test_get_job_store_singleton(self):
        """Test that get_job_store returns singleton"""
        store1 = await get_job_store()
        store2 = await get_job_store()
        
        assert store1 is store2  # Same instance
        assert isinstance(store1, JobStatusStore)
    
    @pytest.mark.asyncio 
    async def test_concurrent_job_updates(self, temp_storage_dir):
        """Test concurrent job updates don't corrupt data"""
        store = JobStatusStore(storage_dir=temp_storage_dir)
        
        # Create initial job
        store.create_job("concurrent_job", "/test/concurrent.pdf", "test")
        
        async def update_job(update_id):
            """Simulate concurrent job updates"""
            job_progress = JobProgress(
                job_id="concurrent_job",
                source_path="/test/concurrent.pdf",
                environment="test",
                start_time=time.time()
            )
            job_progress.overall_status = f"status_{update_id}"
            
            for _ in range(10):  # Multiple updates
                store.update_job_from_progress(job_progress)
                await asyncio.sleep(0.001)  # Small delay
        
        # Run concurrent updates
        tasks = [update_job(i) for i in range(5)]
        await asyncio.gather(*tasks)
        
        # Job should still exist and be valid
        job = store.get_job_status("concurrent_job")
        assert job is not None
        assert job.job_id == "concurrent_job"
        assert job.status.startswith("status_")  # One of the update statuses
    
    @pytest.mark.asyncio
    async def test_store_performance(self, temp_storage_dir):
        """Test store performance with many jobs"""
        store = JobStatusStore(storage_dir=temp_storage_dir)
        
        start_time = time.time()
        
        # Create many jobs quickly
        for i in range(100):
            job_id = f"perf_job_{i:03d}"
            store.create_job(job_id, f"/test/perf{i}.pdf", "test")
            
            if i % 10 == 0:
                # Complete some jobs
                store.complete_job(job_id, {"status": "completed", "processing_time": 15.0})
        
        creation_time = time.time() - start_time
        
        # Should complete reasonably quickly
        assert creation_time < 2.0  # Less than 2 seconds for 100 jobs
        
        # Test retrieval performance
        start_time = time.time()
        
        active_jobs = store.get_active_jobs()
        history = store.get_job_history(limit=20)
        stats = store.get_job_statistics()
        
        retrieval_time = time.time() - start_time
        
        assert retrieval_time < 0.5  # Less than 500ms
        assert len(active_jobs) == 90  # 100 - 10 completed
        assert len(history) <= 20
        assert stats["active_jobs"] == 90


class TestJobStatusStoreErrorHandling:
    """Test error handling in job status store"""
    
    def test_invalid_storage_directory(self):
        """Test handling of invalid storage directory"""
        # Should create directory if it doesn't exist
        invalid_path = Path("/nonexistent/path/that/cannot/be/created")
        
        # This might fail depending on permissions, but shouldn't crash
        try:
            store = JobStatusStore(storage_dir=invalid_path)
            # If it succeeds, verify basic functionality
            assert isinstance(store, JobStatusStore)
        except (PermissionError, OSError):
            # Expected on some systems
            pass
    
    def test_corrupted_disk_data(self, temp_storage_dir):
        """Test handling of corrupted disk data"""
        # Create corrupted data files
        active_file = temp_storage_dir / "active_jobs.json"
        completed_file = temp_storage_dir / "completed_jobs.json"
        
        active_file.write_text("invalid json content")
        completed_file.write_text('{"incomplete": json}')
        
        # Should handle gracefully and start with empty state
        store = JobStatusStore(storage_dir=temp_storage_dir)
        
        assert len(store._active_jobs) == 0
        assert len(store._completed_jobs) == 0
    
    def test_unknown_job_completion(self, job_store):
        """Test completing unknown job"""
        # Should handle gracefully without crashing
        job_store.complete_job("unknown_job", {"status": "completed"})
        
        # Job should not appear in completed jobs
        assert job_store.get_job_status("unknown_job") is None
    
    def test_get_statistics_empty_store(self, job_store):
        """Test statistics calculation with empty store"""
        stats = job_store.get_job_statistics()
        
        assert stats["active_jobs"] == 0
        assert stats["total_completed"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0
        assert stats["average_processing_time"] == 0


if __name__ == "__main__":
    pytest.main([__file__])