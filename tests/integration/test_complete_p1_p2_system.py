"""
End-to-End Integration Test: Complete P1/P2 System
Tests the full pipeline progress tracking and job status system integration.
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from src_common.progress_callback import (
    JobProgress, PassProgress, PassType, PassStatus, CompositeProgressCallback
)
from src_common.job_status_store import JobStatusStore
from src_common.job_status_api import JobStatusProgressCallback
from src_common.pipeline_adapter import Pass6PipelineAdapter, ProgressAwarePipelineWrapper


class MockPass6Pipeline:
    """Mock 6-pass pipeline for testing"""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.should_fail = False
        self.pass_delay = 0.01  # Small delay to simulate work
        
    def process_source_6pass(self, pdf_path: Path, environment: str):
        """Mock 6-pass processing that simulates real pipeline behavior"""
        if self.should_fail:
            result = MagicMock()
            result.success = False
            result.error_message = "Mock pipeline failure"
            result.job_id = f"mock_failed_{int(time.time())}"
            return result
            
        # Simulate successful processing
        time.sleep(self.pass_delay * 6)  # Simulate all 6 passes
        
        result = MagicMock()
        result.success = True
        result.job_id = f"mock_success_{int(time.time())}"
        result.error_message = ""
        return result


@pytest.fixture
def temp_job_store(tmp_path):
    """Create temporary job store for testing"""
    return JobStatusStore(storage_dir=tmp_path)


class TestCompleteP1P2System:
    """Test complete P1/P2 system integration"""
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_progress_flow(self, temp_job_store):
        """Test complete flow from job creation to completion with progress tracking"""
        
        # Create job progress tracking
        job_progress = JobProgress(
            job_id="e2e_test_job_001",
            source_path="/test/e2e_test.pdf",
            environment="test",
            start_time=time.time()
        )
        
        # Create composite callback with store integration
        job_status_callback = JobStatusProgressCallback(temp_job_store)
        callbacks = [job_status_callback]
        composite_callback = CompositeProgressCallback(callbacks)
        
        # Simulate job start
        await composite_callback.on_job_start(job_progress)
        
        # Verify job was created in store
        job_record = temp_job_store.get_job_status("e2e_test_job_001")
        assert job_record is not None
        assert job_record.status == "starting"
        
        # Simulate all 6 passes
        pass_types = [PassType.PASS_A, PassType.PASS_B, PassType.PASS_C,
                     PassType.PASS_D, PassType.PASS_E, PassType.PASS_F]
        
        for i, pass_type in enumerate(pass_types):
            # Start pass
            pass_progress = PassProgress(
                pass_type=pass_type,
                status=PassStatus.STARTING,
                start_time=time.time()
            )
            
            job_progress.current_pass = pass_type
            job_progress.passes[pass_type] = pass_progress
            
            await composite_callback.on_pass_start(job_progress, pass_progress)
            
            # Verify store was updated
            updated_record = temp_job_store.get_job_status("e2e_test_job_001")
            assert updated_record.current_pass == pass_type.value
            
            # Simulate pass progress
            pass_progress.status = PassStatus.IN_PROGRESS
            
            # Add pass-specific metrics
            if pass_type == PassType.PASS_A:
                await composite_callback.on_pass_progress(job_progress, pass_progress, toc_entries=12)
            elif pass_type == PassType.PASS_B:
                await composite_callback.on_pass_progress(job_progress, pass_progress, chunks_processed=45)
            elif pass_type == PassType.PASS_D:
                await composite_callback.on_pass_progress(job_progress, pass_progress, vectors_created=230)
            elif pass_type == PassType.PASS_E:
                await composite_callback.on_pass_progress(job_progress, pass_progress, 
                                                        graph_nodes=67, graph_edges=134)
            
            # Complete pass
            pass_progress.complete()
            await composite_callback.on_pass_complete(job_progress, pass_progress)
            
            # Verify progress percentage increased
            progress_record = temp_job_store.get_job_status("e2e_test_job_001")
            expected_progress = job_progress.get_progress_percentage()
            assert progress_record.progress_percentage == expected_progress
            assert expected_progress > (i * 10)  # Progress should increase with each pass
        
        # Complete job
        job_progress.overall_status = "completed"
        await composite_callback.on_job_complete(job_progress)
        
        # Verify final state
        final_record = temp_job_store.get_job_status("e2e_test_job_001")
        assert final_record.progress_percentage == 100.0
        assert len(final_record.passes) == 6
        
        # Verify pass-specific metrics were captured
        passes = final_record.passes
        assert passes["pass_a_toc_parse"]["toc_entries"] == 12
        assert passes["pass_b_logical_split"]["chunks_processed"] == 45
        assert passes["pass_d_haystack"]["vectors_created"] == 230
        assert passes["pass_e_llamaindex"]["graph_nodes"] == 67
        assert passes["pass_e_llamaindex"]["graph_edges"] == 134
    
    @pytest.mark.asyncio
    async def test_pipeline_adapter_integration(self, temp_job_store):
        """Test pipeline adapter with progress tracking integration"""
        
        # Mock the pipeline import to avoid heavy dependencies
        with pytest.mock.patch('scripts.bulk_ingest.Pass6Pipeline', MockPass6Pipeline):
            
            # Create pipeline adapter with job status integration
            job_status_callback = JobStatusProgressCallback(temp_job_store)
            adapter = Pass6PipelineAdapter("test", progress_callback=job_status_callback)
            
            # Override the job store in adapter
            adapter._job_store = temp_job_store
            
            # Execute pipeline
            result = await adapter.process_source(
                source_path="/test/adapter_test.pdf",
                environment="test"
            )
            
            # Verify result structure
            assert result["status"] == "completed"
            assert "job_id" in result
            assert result["processing_time"] > 0
            assert "thread_name" in result
            
            # Verify job was tracked in store
            job_id = result["job_id"]
            job_record = temp_job_store.get_job_status(job_id)
            assert job_record is not None
    
    @pytest.mark.asyncio 
    async def test_failed_job_tracking(self, temp_job_store):
        """Test tracking of failed jobs through complete system"""
        
        job_progress = JobProgress(
            job_id="failed_job_test",
            source_path="/test/failing.pdf",
            environment="test",
            start_time=time.time()
        )
        
        # Create callback system
        job_status_callback = JobStatusProgressCallback(temp_job_store)
        composite_callback = CompositeProgressCallback([job_status_callback])
        
        # Start job
        await composite_callback.on_job_start(job_progress)
        
        # Start first pass
        pass_a = PassProgress(
            pass_type=PassType.PASS_A,
            status=PassStatus.STARTING,
            start_time=time.time()
        )
        
        job_progress.current_pass = PassType.PASS_A
        job_progress.passes[PassType.PASS_A] = pass_a
        
        await composite_callback.on_pass_start(job_progress, pass_a)
        
        # Fail the pass
        pass_a.fail("Mock test failure", "TestError")
        await composite_callback.on_pass_failed(job_progress, pass_a)
        
        # Complete job as failed
        job_progress.overall_status = "failed"
        await composite_callback.on_job_complete(job_progress)
        
        # Verify failure tracking
        failed_record = temp_job_store.get_job_status("failed_job_test")
        assert failed_record is not None
        assert failed_record.status == "failed"
        assert "pass_a_toc_parse" in failed_record.passes
        assert failed_record.passes["pass_a_toc_parse"]["status"] == "failed"
        assert failed_record.passes["pass_a_toc_parse"]["error_message"] == "Mock test failure"
        assert failed_record.passes["pass_a_toc_parse"]["error_type"] == "TestError"
    
    @pytest.mark.asyncio
    async def test_concurrent_job_tracking(self, temp_job_store):
        """Test tracking multiple concurrent jobs"""
        
        async def process_job(job_num: int):
            """Process a single job with progress tracking"""
            job_progress = JobProgress(
                job_id=f"concurrent_job_{job_num}",
                source_path=f"/test/concurrent_{job_num}.pdf",
                environment="test",
                start_time=time.time()
            )
            
            job_status_callback = JobStatusProgressCallback(temp_job_store)
            
            await job_status_callback.on_job_start(job_progress)
            
            # Simulate some passes
            for pass_type in [PassType.PASS_A, PassType.PASS_B]:
                pass_progress = PassProgress(
                    pass_type=pass_type,
                    status=PassStatus.STARTING,
                    start_time=time.time()
                )
                
                job_progress.current_pass = pass_type
                job_progress.passes[pass_type] = pass_progress
                
                await job_status_callback.on_pass_start(job_progress, pass_progress)
                pass_progress.complete()
                await job_status_callback.on_pass_complete(job_progress, pass_progress)
            
            job_progress.overall_status = "completed"
            await job_status_callback.on_job_complete(job_progress)
            
            return job_progress.job_id
        
        # Process 5 concurrent jobs
        tasks = [process_job(i) for i in range(5)]
        job_ids = await asyncio.gather(*tasks)
        
        # Verify all jobs were tracked
        assert len(job_ids) == 5
        for job_id in job_ids:
            record = temp_job_store.get_job_status(job_id)
            assert record is not None
            assert record.status == "starting"  # In memory, not persisted as completed
        
        # Verify store statistics
        stats = temp_job_store.get_job_statistics()
        assert stats["active_jobs"] == 5  # All jobs created but not moved to completed
    
    @pytest.mark.asyncio
    async def test_progress_percentage_accuracy(self, temp_job_store):
        """Test accuracy of progress percentage calculations"""
        
        job_progress = JobProgress(
            job_id="progress_test",
            source_path="/test/progress.pdf",
            environment="test",
            start_time=time.time()
        )
        
        job_status_callback = JobStatusProgressCallback(temp_job_store)
        await job_status_callback.on_job_start(job_progress)
        
        # Expected progress percentages based on pass weights
        # PASS_A: 10%, PASS_B: 15%, PASS_C: 30%, PASS_D: 25%, PASS_E: 15%, PASS_F: 5%
        expected_progress = [10.0, 25.0, 55.0, 80.0, 95.0, 100.0]
        
        for i, pass_type in enumerate([PassType.PASS_A, PassType.PASS_B, PassType.PASS_C,
                                     PassType.PASS_D, PassType.PASS_E, PassType.PASS_F]):
            
            pass_progress = PassProgress(
                pass_type=pass_type,
                status=PassStatus.COMPLETED,
                start_time=time.time()
            )
            pass_progress.complete()
            
            job_progress.passes[pass_type] = pass_progress
            job_progress.current_pass = pass_type
            
            await job_status_callback.on_pass_complete(job_progress, pass_progress)
            
            # Check progress percentage
            calculated_progress = job_progress.get_progress_percentage()
            assert abs(calculated_progress - expected_progress[i]) < 0.1  # Allow small floating point errors
            
            # Verify store has correct percentage
            record = temp_job_store.get_job_status("progress_test")
            assert abs(record.progress_percentage - expected_progress[i]) < 0.1
    
    def test_job_store_statistics_accuracy(self, temp_job_store):
        """Test job statistics calculation accuracy"""
        
        # Create various job types
        jobs_data = [
            ("stats_success_1", "completed", 30.0, None),
            ("stats_success_2", "completed", 45.0, None),
            ("stats_failed_1", "failed", 15.0, "Test error 1"),
            ("stats_failed_2", "failed", 20.0, "Test error 2"),
            ("stats_success_3", "completed", 60.0, None),
        ]
        
        for job_id, status, processing_time, error_msg in jobs_data:
            temp_job_store.create_job(job_id, f"/test/{job_id}.pdf", "test")
            result = {
                "status": status,
                "processing_time": processing_time,
                "error_message": error_msg
            }
            temp_job_store.complete_job(job_id, result)
        
        # Get statistics
        stats = temp_job_store.get_job_statistics()
        
        assert stats["active_jobs"] == 0
        assert stats["total_completed"] == 5
        assert stats["successful"] == 3
        assert stats["failed"] == 2
        assert abs(stats["success_rate"] - 60.0) < 0.1  # 3/5 = 60%
        
        # Average of successful jobs: (30 + 45 + 60) / 3 = 45.0
        assert abs(stats["average_processing_time"] - 45.0) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])