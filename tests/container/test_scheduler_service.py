# tests/container/test_scheduler_service.py
"""
FR-006: Scheduler Service Tests
Tests for APScheduler integration and automated jobs
"""

import pytest
import asyncio
import os
import time
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_common.container_scheduler_service import (
    ContainerSchedulerService,
    get_scheduler_service,
    start_scheduler_service,
    stop_scheduler_service
)


class TestSchedulerService:
    """Test APScheduler service functionality"""
    
    @pytest.fixture
    async def scheduler_service(self):
        """Create a scheduler service instance for testing"""
        service = ContainerSchedulerService()
        yield service
        
        # Cleanup
        if service.is_running:
            await service.stop()
    
    @pytest.fixture
    def mock_environment(self):
        """Mock environment variables for testing"""
        with patch.dict(os.environ, {
            "SCHEDULER_ENABLED": "true",
            "INGESTION_CRON": "0 */6 * * *",
            "LOG_CLEANUP_CRON": "0 2 * * *",
            "LOG_CLEANUP_ENABLED": "true",
            "LOG_RETENTION_DAYS": "5",
            "UPLOAD_DIRECTORY": "/tmp/test_uploads",
            "LOG_DIRECTORY": "/tmp/test_logs"
        }):
            yield
    
    def test_scheduler_initialization(self, mock_environment):
        """Test scheduler service initialization"""
        service = ContainerSchedulerService()
        
        assert service.scheduler is not None
        assert service.upload_directory == "/tmp/test_uploads"
        assert service.log_directory == "/tmp/test_logs"
        assert not service.is_running
    
    async def test_scheduler_start_stop(self, scheduler_service, mock_environment):
        """Test starting and stopping the scheduler"""
        # Test start
        started = await scheduler_service.start()
        assert started
        assert scheduler_service.is_running
        
        # Test status
        status = scheduler_service.get_status()
        assert status["running"]
        assert status["enabled"]
        
        # Test stop
        await scheduler_service.stop()
        assert not scheduler_service.is_running
    
    async def test_scheduler_disabled(self, scheduler_service):
        """Test scheduler behavior when disabled"""
        with patch.dict(os.environ, {"SCHEDULER_ENABLED": "false"}):
            started = await scheduler_service.start()
            assert not started
            assert not scheduler_service.is_running
    
    async def test_default_jobs_creation(self, scheduler_service, mock_environment):
        """Test that default jobs are created on startup"""
        await scheduler_service.start()
        
        jobs = scheduler_service.get_jobs()
        job_ids = [job["id"] for job in jobs]
        
        assert "automated_ingestion" in job_ids
        assert "log_cleanup" in job_ids
        
        # Check job details
        ingestion_job = next(job for job in jobs if job["id"] == "automated_ingestion")
        assert "Automated File Ingestion" in ingestion_job["name"]
        
        cleanup_job = next(job for job in jobs if job["id"] == "log_cleanup")
        assert "Log File Cleanup" in cleanup_job["name"]
    
    async def test_custom_job_management(self, scheduler_service, mock_environment):
        """Test adding and removing custom jobs"""
        await scheduler_service.start()
        
        # Test adding a job
        async def test_job():
            pass
        
        added = await scheduler_service.add_job(
            func=test_job,
            trigger="interval",
            job_id="test_job",
            name="Test Job",
            seconds=60
        )
        
        assert added
        
        jobs = scheduler_service.get_jobs()
        job_ids = [job["id"] for job in jobs]
        assert "test_job" in job_ids
        
        # Test removing the job
        removed = scheduler_service.remove_job("test_job")
        assert removed
        
        jobs = scheduler_service.get_jobs()
        job_ids = [job["id"] for job in jobs]
        assert "test_job" not in job_ids
    
    def test_get_status(self, scheduler_service, mock_environment):
        """Test scheduler status reporting"""
        status = scheduler_service.get_status()
        
        assert "enabled" in status
        assert "running" in status
        assert "upload_directory" in status
        assert "log_directory" in status
        assert "job_count" in status
        
        assert status["upload_directory"] == "/tmp/test_uploads"
        assert status["log_directory"] == "/tmp/test_logs"


class TestIngestionJob:
    """Test automated ingestion job functionality"""
    
    @pytest.fixture
    def temp_upload_dir(self):
        """Create temporary upload directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = Path(temp_dir) / "uploads"
            upload_dir.mkdir()
            yield upload_dir
    
    @pytest.fixture
    async def scheduler_with_temp_dir(self, temp_upload_dir):
        """Scheduler service with temporary upload directory"""
        with patch.dict(os.environ, {
            "UPLOAD_DIRECTORY": str(temp_upload_dir),
            "SCHEDULER_ENABLED": "true"
        }):
            service = ContainerSchedulerService()
            yield service
            
            if service.is_running:
                await service.stop()
    
    async def test_ingestion_job_no_files(self, scheduler_with_temp_dir, temp_upload_dir):
        """Test ingestion job when no files are present"""
        # Mock the pipeline function to avoid import issues
        with patch('src_common.container_scheduler_service.run_ingestion_pipeline') as mock_pipeline:
            await scheduler_with_temp_dir._run_ingestion()
            
            # Should not call pipeline when no files
            mock_pipeline.assert_not_called()
    
    async def test_ingestion_job_with_files(self, scheduler_with_temp_dir, temp_upload_dir):
        """Test ingestion job with PDF files present"""
        # Create test PDF files
        test_pdf1 = temp_upload_dir / "test1.pdf"
        test_pdf2 = temp_upload_dir / "test2.pdf"
        
        test_pdf1.write_text("fake pdf content 1")
        test_pdf2.write_text("fake pdf content 2")
        
        # Mock the pipeline function
        with patch('src_common.container_scheduler_service.run_ingestion_pipeline') as mock_pipeline:
            mock_pipeline.return_value = {"success": True}
            
            await scheduler_with_temp_dir._run_ingestion()
            
            # Should call pipeline for each file
            assert mock_pipeline.call_count == 2
            
            # Check that files were processed (moved to archive)
            processed_dir = temp_upload_dir / "processed"
            assert processed_dir.exists()
            
            # Original files should be moved
            assert not test_pdf1.exists()
            assert not test_pdf2.exists()
            
            # Archived files should exist
            archived_files = list(processed_dir.glob("*.pdf"))
            assert len(archived_files) == 2
    
    async def test_ingestion_job_failure_handling(self, scheduler_with_temp_dir, temp_upload_dir):
        """Test ingestion job handles failures gracefully"""
        # Create test PDF file
        test_pdf = temp_upload_dir / "test.pdf"
        test_pdf.write_text("fake pdf content")
        
        # Mock pipeline to simulate failure
        with patch('src_common.container_scheduler_service.run_ingestion_pipeline') as mock_pipeline:
            mock_pipeline.return_value = {"success": False, "error": "Test error"}
            
            # Should not raise exception
            await scheduler_with_temp_dir._run_ingestion()
            
            mock_pipeline.assert_called_once()
            
            # File should still exist (not archived on failure)
            assert test_pdf.exists()


class TestLogCleanupJob:
    """Test log cleanup job functionality"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory with test files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "logs"
            log_dir.mkdir()
            
            # Create test log files with different ages
            current_time = time.time()
            
            # Current log file (should not be deleted)
            current_log = log_dir / "ttrpg_app.log"
            current_log.write_text("current log content")
            current_log.touch()
            
            # Recent log file (should not be deleted)
            recent_log = log_dir / "ttrpg_app.log.2024-01-15"
            recent_log.write_text("recent log content")
            recent_log.touch()
            os.utime(recent_log, (current_time - 86400 * 2, current_time - 86400 * 2))  # 2 days old
            
            # Old log file (should be deleted)
            old_log = log_dir / "ttrpg_app.log.2024-01-01"
            old_log.write_text("old log content")
            old_log.touch()
            os.utime(old_log, (current_time - 86400 * 10, current_time - 86400 * 10))  # 10 days old
            
            # Very old log file (should be deleted)
            very_old_log = log_dir / "ttrpg_error.log.2023-12-01"
            very_old_log.write_text("very old log content")
            very_old_log.touch()
            os.utime(very_old_log, (current_time - 86400 * 30, current_time - 86400 * 30))  # 30 days old
            
            yield log_dir
    
    @pytest.fixture
    async def scheduler_with_temp_log_dir(self, temp_log_dir):
        """Scheduler service with temporary log directory"""
        with patch.dict(os.environ, {
            "LOG_DIRECTORY": str(temp_log_dir),
            "LOG_RETENTION_DAYS": "5",
            "SCHEDULER_ENABLED": "true"
        }):
            service = ContainerSchedulerService()
            yield service
            
            if service.is_running:
                await service.stop()
    
    async def test_log_cleanup_job(self, scheduler_with_temp_log_dir, temp_log_dir):
        """Test log cleanup job removes old files"""
        # Check initial state
        log_files_before = list(temp_log_dir.glob("*.log*"))
        assert len(log_files_before) == 4
        
        # Run cleanup
        await scheduler_with_temp_log_dir._run_log_cleanup()
        
        # Check final state
        remaining_files = list(temp_log_dir.glob("*.log*"))
        
        # Should keep current log and recent log, remove old logs
        assert len(remaining_files) == 2
        
        remaining_names = [f.name for f in remaining_files]
        assert "ttrpg_app.log" in remaining_names  # Current log
        assert "ttrpg_app.log.2024-01-15" in remaining_names  # Recent log
        
        # Old logs should be gone
        assert "ttrpg_app.log.2024-01-01" not in remaining_names
        assert "ttrpg_error.log.2023-12-01" not in remaining_names
    
    async def test_log_cleanup_disabled(self, temp_log_dir):
        """Test log cleanup when disabled"""
        with patch.dict(os.environ, {
            "LOG_DIRECTORY": str(temp_log_dir),
            "LOG_CLEANUP_ENABLED": "false",
            "SCHEDULER_ENABLED": "true"
        }):
            service = ContainerSchedulerService()
            
            # Should not add cleanup job when disabled
            await service.start()
            
            jobs = service.get_jobs()
            job_ids = [job["id"] for job in jobs]
            
            assert "log_cleanup" not in job_ids
            
            await service.stop()
    
    async def test_log_cleanup_error_handling(self, scheduler_with_temp_log_dir, temp_log_dir):
        """Test log cleanup handles errors gracefully"""
        # Create a file that can't be deleted (simulate permission error)
        protected_file = temp_log_dir / "protected.log"
        protected_file.write_text("protected content")
        protected_file.touch()
        
        # Make file old
        old_time = time.time() - 86400 * 10
        os.utime(protected_file, (old_time, old_time))
        
        # Mock unlink to raise permission error for this file
        original_unlink = Path.unlink
        
        def mock_unlink(self):
            if self.name == "protected.log":
                raise PermissionError("Permission denied")
            return original_unlink(self)
        
        with patch.object(Path, 'unlink', mock_unlink):
            # Should not raise exception
            await scheduler_with_temp_log_dir._run_log_cleanup()
            
            # Protected file should still exist
            assert protected_file.exists()


class TestSchedulerIntegration:
    """Test scheduler integration with the application"""
    
    def test_global_scheduler_service(self):
        """Test global scheduler service management"""
        # Test getting service
        service1 = get_scheduler_service()
        service2 = get_scheduler_service()
        
        # Should return same instance
        assert service1 is service2
    
    async def test_start_stop_global_service(self):
        """Test starting and stopping global scheduler service"""
        # Mock environment to enable scheduler
        with patch.dict(os.environ, {"SCHEDULER_ENABLED": "true"}):
            # Test start
            started = await start_scheduler_service()
            assert started
            
            service = get_scheduler_service()
            assert service.is_running
            
            # Test stop
            await stop_scheduler_service()
            
            # Service should be reset
            new_service = get_scheduler_service()
            assert not new_service.is_running


if __name__ == "__main__":
    pytest.main([__file__, "-v"])