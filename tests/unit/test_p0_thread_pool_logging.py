"""
P0.2 Unit Tests: Thread Pool Visibility
Tests for thread pool execution logging in Pass6PipelineAdapter.
"""

import asyncio
import pytest
import threading
import time
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from pathlib import Path

from src_common.pipeline_adapter import Pass6PipelineAdapter


class MockPass6Pipeline:
    """Mock 6-pass pipeline for testing"""
    
    def __init__(self, environment: str):
        self.environment = environment
        
    def process_source_6pass(self, pdf_path: Path, environment: str):
        """Mock 6-pass processing"""
        time.sleep(0.1)  # Simulate processing time
        
        # Mock result object
        result = MagicMock()
        result.job_id = f"mock_job_{int(time.time())}"
        result.success = True
        result.error_message = ""
        
        return result


class FailingMockPipeline:
    """Mock pipeline that fails for testing error handling"""
    
    def __init__(self, environment: str):
        self.environment = environment
        
    def process_source_6pass(self, pdf_path: Path, environment: str):
        """Mock pipeline that raises an exception"""
        time.sleep(0.05)  # Brief processing time before failure
        raise RuntimeError("Mock pipeline failure for testing")


class TestThreadPoolLogging:
    """Test thread pool execution visibility and logging"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.test_env = "test"
        
    @pytest.mark.asyncio
    async def test_thread_pool_entry_logging(self, caplog):
        """Test logging when entering thread pool execution"""
        
        with patch('src_common.pipeline_adapter.Pass6Pipeline', MockPass6Pipeline):
            adapter = Pass6PipelineAdapter(self.test_env)
            
            result = await adapter.process_source(
                source_path="/test/documents/sample.pdf",
                environment=self.test_env
            )
            
            # Verify result structure
            assert result["status"] == "completed"
            assert "job_id" in result
            assert result["processing_time"] > 0
            
            # Check logging messages
            log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
            
            # Should see thread pool entry message
            entry_logs = [msg for msg in log_messages if "entering thread pool execution" in msg]
            assert len(entry_logs) == 1, f"Expected thread pool entry log, got: {entry_logs}"
            assert "sample.pdf" in entry_logs[0]
            
            # Should see thread execution start
            start_logs = [msg for msg in log_messages if "starting 6-pass pipeline execution" in msg]
            assert len(start_logs) == 1, f"Expected pipeline start log, got: {start_logs}"
            
            # Should see completion
            complete_logs = [msg for msg in log_messages if "completed 6-pass pipeline" in msg]
            assert len(complete_logs) == 1, f"Expected completion log, got: {complete_logs}"
            
    @pytest.mark.asyncio
    async def test_thread_name_logging(self, caplog):
        """Test that thread names are properly logged"""
        
        with patch('src_common.pipeline_adapter.Pass6Pipeline', MockPass6Pipeline):
            adapter = Pass6PipelineAdapter(self.test_env)
            
            await adapter.process_source(
                source_path="/test/thread_test.pdf",
                environment=self.test_env
            )
            
            # Check that thread names appear in logs
            log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
            
            # Should see thread names in execution logs
            thread_logs = [msg for msg in log_messages if "Thread Thread" in msg]
            assert len(thread_logs) >= 1, f"Expected thread name in logs, got: {log_messages}"
            
            # Verify thread name is in result
            # This requires checking the actual result structure
            # (Thread name should be included in the return value)
            
    @pytest.mark.asyncio
    async def test_execution_timing_logging(self, caplog):
        """Test accurate execution time logging"""
        
        class TimedMockPipeline:
            def __init__(self, environment: str):
                self.environment = environment
                
            def process_source_6pass(self, pdf_path: Path, environment: str):
                time.sleep(0.2)  # Known processing time
                result = MagicMock()
                result.job_id = "timed_job"
                result.success = True
                result.error_message = ""
                return result
        
        with patch('src_common.pipeline_adapter.Pass6Pipeline', TimedMockPipeline):
            adapter = Pass6PipelineAdapter(self.test_env)
            
            start_time = time.time()
            result = await adapter.process_source(
                source_path="/test/timing_test.pdf",
                environment=self.test_env
            )
            total_time = time.time() - start_time
            
            # Check result timing
            assert result["processing_time"] >= 0.15  # Should reflect actual processing time
            assert result["processing_time"] <= total_time  # Should be less than total time
            
            # Check timing in logs
            log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
            
            timing_logs = [msg for msg in log_messages if "execution time:" in msg]
            assert len(timing_logs) >= 1, f"Expected timing logs, got: {timing_logs}"
            
            # Should show reasonable timing values
            for log in timing_logs:
                # Extract timing from log message
                if "execution time: " in log:
                    time_part = log.split("execution time: ")[1].split("s")[0]
                    logged_time = float(time_part)
                    assert logged_time >= 0.15, f"Logged time too short: {logged_time}"
                    assert logged_time <= total_time, f"Logged time too long: {logged_time}"
                    
    @pytest.mark.asyncio
    async def test_thread_pool_error_handling(self, caplog):
        """Test error handling and logging in thread pool"""
        
        with patch('src_common.pipeline_adapter.Pass6Pipeline', FailingMockPipeline):
            adapter = Pass6PipelineAdapter(self.test_env)
            
            result = await adapter.process_source(
                source_path="/test/failing_doc.pdf",
                environment=self.test_env
            )
            
            # Should return failed result
            assert result["status"] == "failed"
            assert "Mock pipeline failure" in result["error_message"]
            assert result["exception_type"] == "RuntimeError"
            
            # Check error logging
            error_logs = [record.message for record in caplog.records if record.levelname == "ERROR"]
            assert len(error_logs) >= 1, f"Expected error logs, got: {error_logs}"
            
            # Should see thread exception message
            thread_error_logs = [msg for msg in error_logs if "exception during 6-pass pipeline" in msg]
            assert len(thread_error_logs) == 1, f"Expected thread error log, got: {thread_error_logs}"
            assert "failing_doc.pdf" in thread_error_logs[0]
            
    @pytest.mark.asyncio
    async def test_concurrent_thread_logging(self, caplog):
        """Test logging with multiple concurrent thread executions"""
        
        with patch('src_common.pipeline_adapter.Pass6Pipeline', MockPass6Pipeline):
            adapter = Pass6PipelineAdapter(self.test_env)
            
            # Execute multiple jobs concurrently
            tasks = []
            for i in range(5):
                task = adapter.process_source(
                    source_path=f"/test/concurrent_{i}.pdf",
                    environment=self.test_env
                )
                tasks.append(task)
                
            results = await asyncio.gather(*tasks)
            
            # All should complete successfully
            assert len(results) == 5
            assert all(r["status"] == "completed" for r in results)
            
            # Check that we see logs from different threads
            log_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
            
            # Should see entry logs for all jobs
            entry_logs = [msg for msg in log_messages if "entering thread pool execution" in msg]
            assert len(entry_logs) == 5, f"Expected 5 entry logs, got: {len(entry_logs)}"
            
            # Should see completion logs for all jobs
            completion_logs = [msg for msg in log_messages if "completed thread pool execution" in msg]
            assert len(completion_logs) == 5, f"Expected 5 completion logs, got: {len(completion_logs)}"
            
            # Verify each concurrent job is logged
            for i in range(5):
                concurrent_logs = [msg for msg in log_messages if f"concurrent_{i}.pdf" in msg]
                assert len(concurrent_logs) >= 2, f"Expected logs for concurrent_{i}.pdf, got: {concurrent_logs}"
                
    @pytest.mark.asyncio
    async def test_thread_pool_exception_recovery(self, caplog):
        """Test thread pool level exception handling"""
        
        # Create adapter that will have thread pool issues
        class BadAdapter(Pass6PipelineAdapter):
            async def process_source(self, source_path: str, environment: str, artifacts_dir: str = None):
                # Force a thread pool level exception
                loop = asyncio.get_running_loop()
                
                def _failing_run():
                    raise Exception("Thread pool level failure")
                    
                # This should trigger the outer exception handler
                return await loop.run_in_executor(None, _failing_run)
        
        adapter = BadAdapter(self.test_env)
        
        result = await adapter.process_source(
            source_path="/test/pool_error.pdf",
            environment=self.test_env
        )
        
        # Should handle gracefully
        assert result["status"] == "failed"
        assert "Thread pool error" in result["error_message"]
        assert result["thread_name"] == "pool_error"
        
        # Check thread pool error logging
        error_logs = [record.message for record in caplog.records if record.levelname == "ERROR"]
        pool_error_logs = [msg for msg in error_logs if "Thread pool execution failed" in msg]
        assert len(pool_error_logs) == 1, f"Expected pool error log, got: {pool_error_logs}"
        
    @pytest.mark.asyncio
    async def test_result_structure_completeness(self):
        """Test that thread pool results include all expected fields"""
        
        with patch('src_common.pipeline_adapter.Pass6Pipeline', MockPass6Pipeline):
            adapter = Pass6PipelineAdapter(self.test_env)
            
            result = await adapter.process_source(
                source_path="/test/structure_test.pdf",
                environment=self.test_env
            )
            
            # Verify all expected fields are present
            required_fields = [
                "job_id", "status", "processing_time", "environment", 
                "artifacts_path", "thread_name"
            ]
            
            for field in required_fields:
                assert field in result, f"Missing required field: {field}"
                
            # Verify field types and values
            assert isinstance(result["processing_time"], float)
            assert result["processing_time"] > 0
            assert result["status"] in ["completed", "failed"]
            assert result["environment"] == self.test_env
            assert "thread_name" in result
            
            # For successful jobs, error_message should be None
            if result["status"] == "completed":
                assert result.get("error_message") is None
                

if __name__ == "__main__":
    pytest.main([__file__])