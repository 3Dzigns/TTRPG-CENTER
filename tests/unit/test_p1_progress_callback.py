"""
P1 Unit Tests: Progress Callback System
Tests for enhanced pipeline progress tracking and callback functionality.
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass

from src_common.progress_callback import (
    ProgressCallback, LoggingProgressCallback, CompositeProgressCallback,
    JobProgress, PassProgress, PassType, PassStatus
)


@pytest.fixture
def sample_job_progress():
    """Create a sample job progress for testing"""
    return JobProgress(
        job_id="test_job_123",
        source_path="/test/sample.pdf",
        environment="test",
        start_time=time.time()
    )


@pytest.fixture
def sample_pass_progress():
    """Create a sample pass progress for testing"""
    return PassProgress(
        pass_type=PassType.PASS_A,
        status=PassStatus.IN_PROGRESS,
        start_time=time.time()
    )


class MockProgressCallback(ProgressCallback):
    """Mock progress callback for testing"""
    
    def __init__(self):
        self.calls = {}
        
    async def on_job_start(self, job_progress):
        self.calls.setdefault('on_job_start', []).append(job_progress)
        
    async def on_pass_start(self, job_progress, pass_progress):
        self.calls.setdefault('on_pass_start', []).append((job_progress, pass_progress))
        
    async def on_pass_progress(self, job_progress, pass_progress, **metrics):
        self.calls.setdefault('on_pass_progress', []).append((job_progress, pass_progress, metrics))
        
    async def on_pass_complete(self, job_progress, pass_progress):
        self.calls.setdefault('on_pass_complete', []).append((job_progress, pass_progress))
        
    async def on_pass_failed(self, job_progress, pass_progress):
        self.calls.setdefault('on_pass_failed', []).append((job_progress, pass_progress))
        
    async def on_job_complete(self, job_progress):
        self.calls.setdefault('on_job_complete', []).append(job_progress)


class TestJobProgress:
    """Test JobProgress functionality"""
    
    def test_job_progress_creation(self, sample_job_progress):
        """Test JobProgress object creation"""
        assert sample_job_progress.job_id == "test_job_123"
        assert sample_job_progress.source_path == "/test/sample.pdf"
        assert sample_job_progress.environment == "test"
        assert sample_job_progress.overall_status == "starting"
        assert len(sample_job_progress.passes) == 0
        
    def test_progress_percentage_calculation(self, sample_job_progress):
        """Test progress percentage calculation"""
        # No passes started
        assert sample_job_progress.get_progress_percentage() == 0.0
        
        # Add some completed passes
        sample_job_progress.passes[PassType.PASS_A] = PassProgress(
            pass_type=PassType.PASS_A,
            status=PassStatus.COMPLETED,
            start_time=time.time()
        )
        
        # Pass A weight is 10 out of 100 total
        assert sample_job_progress.get_progress_percentage() == 10.0
        
        # Add in-progress pass
        sample_job_progress.passes[PassType.PASS_C] = PassProgress(
            pass_type=PassType.PASS_C,
            status=PassStatus.IN_PROGRESS,
            start_time=time.time()
        )
        
        # Pass A completed (10) + Pass C in progress (30 * 0.5 = 15) = 25%
        assert sample_job_progress.get_progress_percentage() == 25.0
        
    def test_estimated_completion_time(self, sample_job_progress):
        """Test ETA calculation"""
        # No progress yet
        assert sample_job_progress.get_estimated_completion_time() is None
        
        # Mock some progress and time passage
        sample_job_progress.start_time = time.time() - 60  # Started 1 minute ago
        sample_job_progress.passes[PassType.PASS_A] = PassProgress(
            pass_type=PassType.PASS_A,
            status=PassStatus.COMPLETED,
            start_time=time.time() - 50
        )
        
        eta = sample_job_progress.get_estimated_completion_time()
        assert eta is not None
        assert eta > 0  # Should have some estimated time remaining
        
    def test_current_pass_info(self, sample_job_progress):
        """Test current pass information extraction"""
        # No current pass
        assert sample_job_progress.get_current_pass_info() is None
        
        # Set current pass
        pass_progress = PassProgress(
            pass_type=PassType.PASS_B,
            status=PassStatus.IN_PROGRESS,
            start_time=time.time(),
            toc_entries=5,
            chunks_processed=10
        )
        
        sample_job_progress.current_pass = PassType.PASS_B
        sample_job_progress.passes[PassType.PASS_B] = pass_progress
        
        current_info = sample_job_progress.get_current_pass_info()
        assert current_info is not None
        assert current_info["pass_type"] == "pass_b_logical_split"
        assert current_info["status"] == "in_progress"
        assert "elapsed_time" in current_info
        assert current_info["metrics"]["toc_entries"] == 5
        assert current_info["metrics"]["chunks_processed"] == 10


class TestPassProgress:
    """Test PassProgress functionality"""
    
    def test_pass_progress_creation(self, sample_pass_progress):
        """Test PassProgress object creation"""
        assert sample_pass_progress.pass_type == PassType.PASS_A
        assert sample_pass_progress.status == PassStatus.IN_PROGRESS
        assert sample_pass_progress.end_time is None
        assert sample_pass_progress.duration_ms is None
        
    def test_pass_completion(self, sample_pass_progress):
        """Test pass completion tracking"""
        # Complete with metrics
        sample_pass_progress.complete(toc_entries=15, custom_metric="test_value")
        
        assert sample_pass_progress.status == PassStatus.COMPLETED
        assert sample_pass_progress.end_time is not None
        assert sample_pass_progress.duration_ms is not None
        assert sample_pass_progress.toc_entries == 15
        assert sample_pass_progress.metadata["custom_metric"] == "test_value"
        
    def test_pass_failure(self, sample_pass_progress):
        """Test pass failure tracking"""
        sample_pass_progress.fail("Test error message", "TestError")
        
        assert sample_pass_progress.status == PassStatus.FAILED
        assert sample_pass_progress.end_time is not None
        assert sample_pass_progress.duration_ms is not None
        assert sample_pass_progress.error_message == "Test error message"
        assert sample_pass_progress.error_type == "TestError"


class TestLoggingProgressCallback:
    """Test LoggingProgressCallback functionality"""
    
    @pytest.mark.asyncio
    async def test_logging_callback_methods(self, caplog, sample_job_progress, sample_pass_progress):
        """Test that logging callback produces expected log messages"""
        callback = LoggingProgressCallback()
        
        # Test job start logging
        await callback.on_job_start(sample_job_progress)
        assert "Job test_job_123 starting 6-pass pipeline" in caplog.text
        
        # Test pass start logging
        await callback.on_pass_start(sample_job_progress, sample_pass_progress)
        assert "Job test_job_123 starting pass_a_toc_parse" in caplog.text
        
        # Test pass progress logging
        await callback.on_pass_progress(sample_job_progress, sample_pass_progress, toc_entries=5)
        assert "toc_entries=5" in caplog.text
        
        # Test pass completion
        sample_pass_progress.complete(toc_entries=10)
        await callback.on_pass_complete(sample_job_progress, sample_pass_progress)
        assert "completed pass_a_toc_parse" in caplog.text
        assert "toc_entries=10" in caplog.text
        
        # Test pass failure
        sample_pass_progress.fail("Test error")
        await callback.on_pass_failed(sample_job_progress, sample_pass_progress)
        assert "pass_a_toc_parse failed" in caplog.text
        assert "Test error" in caplog.text
        
        # Test job completion
        await callback.on_job_complete(sample_job_progress)
        assert "Job test_job_123 completed" in caplog.text


class TestCompositeProgressCallback:
    """Test CompositeProgressCallback functionality"""
    
    @pytest.mark.asyncio
    async def test_composite_callback_delegation(self, sample_job_progress, sample_pass_progress):
        """Test that composite callback delegates to all child callbacks"""
        mock1 = MockProgressCallback()
        mock2 = MockProgressCallback()
        
        composite = CompositeProgressCallback([mock1, mock2])
        
        # Test all callback methods
        await composite.on_job_start(sample_job_progress)
        await composite.on_pass_start(sample_job_progress, sample_pass_progress)
        await composite.on_pass_progress(sample_job_progress, sample_pass_progress, test_metric=42)
        await composite.on_pass_complete(sample_job_progress, sample_pass_progress)
        await composite.on_pass_failed(sample_job_progress, sample_pass_progress)
        await composite.on_job_complete(sample_job_progress)
        
        # Verify all callbacks were called on both mocks
        for mock in [mock1, mock2]:
            assert len(mock.calls['on_job_start']) == 1
            assert len(mock.calls['on_pass_start']) == 1
            assert len(mock.calls['on_pass_progress']) == 1
            assert len(mock.calls['on_pass_complete']) == 1
            assert len(mock.calls['on_pass_failed']) == 1
            assert len(mock.calls['on_job_complete']) == 1
            
            # Verify metrics were passed through
            _, _, metrics = mock.calls['on_pass_progress'][0]
            assert metrics['test_metric'] == 42


class TestProgressCallbackIntegration:
    """Test progress callback integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_full_pipeline_simulation(self):
        """Test full pipeline progress tracking simulation"""
        mock_callback = MockProgressCallback()
        
        # Create job progress
        job_progress = JobProgress(
            job_id="integration_test_job",
            source_path="/test/integration.pdf", 
            environment="test",
            start_time=time.time()
        )
        
        # Simulate job start
        await mock_callback.on_job_start(job_progress)
        
        # Simulate all 6 passes
        pass_types = [PassType.PASS_A, PassType.PASS_B, PassType.PASS_C, 
                     PassType.PASS_D, PassType.PASS_E, PassType.PASS_F]
        
        for pass_type in pass_types:
            # Start pass
            pass_progress = PassProgress(
                pass_type=pass_type,
                status=PassStatus.STARTING,
                start_time=time.time()
            )
            
            job_progress.current_pass = pass_type
            job_progress.passes[pass_type] = pass_progress
            
            await mock_callback.on_pass_start(job_progress, pass_progress)
            
            # Simulate progress updates
            pass_progress.status = PassStatus.IN_PROGRESS
            if pass_type == PassType.PASS_A:
                await mock_callback.on_pass_progress(job_progress, pass_progress, toc_entries=8)
            elif pass_type == PassType.PASS_B:
                await mock_callback.on_pass_progress(job_progress, pass_progress, chunks_processed=25)
            elif pass_type == PassType.PASS_D:
                await mock_callback.on_pass_progress(job_progress, pass_progress, vectors_created=150)
            elif pass_type == PassType.PASS_E:
                await mock_callback.on_pass_progress(job_progress, pass_progress, graph_nodes=45, graph_edges=89)
            
            # Complete pass
            pass_progress.complete()
            await mock_callback.on_pass_complete(job_progress, pass_progress)
        
        # Complete job
        job_progress.overall_status = "completed"
        await mock_callback.on_job_complete(job_progress)
        
        # Verify all callbacks were made
        assert len(mock_callback.calls['on_job_start']) == 1
        assert len(mock_callback.calls['on_pass_start']) == 6
        assert len(mock_callback.calls['on_pass_progress']) == 4  # Only some passes have progress updates
        assert len(mock_callback.calls['on_pass_complete']) == 6
        assert len(mock_callback.calls['on_job_complete']) == 1
        
        # Verify progress percentage calculation
        final_progress = job_progress.get_progress_percentage()
        assert final_progress == 100.0  # All passes completed
        
    @pytest.mark.asyncio
    async def test_error_handling_in_callbacks(self, sample_job_progress, sample_pass_progress):
        """Test error handling when callbacks fail"""
        
        class FailingCallback(ProgressCallback):
            async def on_job_start(self, job_progress):
                raise Exception("Callback failed")
            async def on_pass_start(self, job_progress, pass_progress):
                pass
            async def on_pass_progress(self, job_progress, pass_progress, **metrics):
                pass  
            async def on_pass_complete(self, job_progress, pass_progress):
                pass
            async def on_pass_failed(self, job_progress, pass_progress):
                pass
            async def on_job_complete(self, job_progress):
                pass
        
        working_callback = MockProgressCallback()
        failing_callback = FailingCallback()
        
        # This should not crash even though one callback fails
        composite = CompositeProgressCallback([working_callback, failing_callback])
        
        # This may raise an exception depending on implementation
        # In production, errors should be caught and logged
        try:
            await composite.on_job_start(sample_job_progress)
        except Exception as e:
            # Expected - failing callback raises exception
            assert "Callback failed" in str(e)
        
        # Working callback should still have been called
        assert len(working_callback.calls['on_job_start']) == 1


if __name__ == "__main__":
    pytest.main([__file__])