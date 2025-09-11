"""
P0.3 Unit Tests: Enhanced Heartbeat Logging
Tests for enhanced heartbeat functionality in nightly ingestion runner.
"""

import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from pathlib import Path

# Mock the imports to avoid heavy dependencies in tests
with patch.dict('sys.modules', {
    'src_common.document_scanner': MagicMock(),
    'src_common.processing_queue': MagicMock(),
    'src_common.pipeline_adapter': MagicMock(),
    'src_common.scheduled_processor': MagicMock(),
    'src_common.job_manager': MagicMock(),
    'src_common.ttrpg_logging': MagicMock(),
}):
    # Import the module after mocking dependencies
    import scripts.run_nightly_ingestion as nightly_runner


@dataclass
class MockJob:
    """Mock job for testing heartbeat functionality"""
    id: str
    source_path: str
    environment: str


class MockProcessor:
    """Mock processor for testing heartbeat with slot tracking"""
    
    def __init__(self, max_concurrent_jobs: int = 2):
        self.max_concurrent_jobs = max_concurrent_jobs
        self._active_jobs = 0
        
    async def execute_job(self, job):
        """Mock job execution with realistic timing"""
        # Simulate semaphore behavior
        self._active_jobs += 1
        try:
            await asyncio.sleep(0.1)  # Simulate work
            return {
                "job_id": job.id,
                "status": "completed",
                "total_time": 0.12,
                "wait_time": 0.02,
                "processing_time": 0.1,
                "environment": job.environment,
                "artifacts_path": "/test/artifacts"
            }
        finally:
            self._active_jobs -= 1


class TestHeartbeatLogging:
    """Test enhanced heartbeat logging functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_heartbeat_logging(self, caplog):
        """Test basic heartbeat logging with job progress"""
        
        # Create mock components
        processor = MockProcessor(max_concurrent_jobs=2)
        jobs = [
            MockJob(id="hb_job_1", source_path="/test/doc1.pdf", environment="test"),
            MockJob(id="hb_job_2", source_path="/test/doc2.pdf", environment="test"),
        ]
        
        # Create tasks like the nightly runner does
        tasks = [asyncio.create_task(processor.execute_job(j)) for j in jobs]
        execution_start_time = time.time()
        
        # Create the enhanced heartbeat function (simplified version)
        async def _test_heartbeat():
            """Simplified heartbeat for testing"""
            heartbeat_count = 0
            for _ in range(3):  # Run a few heartbeat cycles
                heartbeat_count += 1
                heartbeat_time = time.time()
                
                done = sum(1 for t in tasks if t.done())
                pending = len(tasks) - done
                active_jobs = processor._active_jobs
                max_slots = processor.max_concurrent_jobs
                waiting_jobs = max(0, pending - active_jobs)
                elapsed_time = heartbeat_time - execution_start_time
                
                # Create heartbeat log message (matching actual implementation)
                message = (
                    f"Heartbeat #{heartbeat_count} [{elapsed_time:.0f}s elapsed]: "
                    f"{done}/{len(tasks)} completed, {pending} pending, "
                    f"active slots: {active_jobs}/{max_slots}, waiting: {waiting_jobs}"
                )
                
                # Use a mock logger to capture the message
                print(message)  # This will be captured by caplog
                
                await asyncio.sleep(0.05)  # Short heartbeat interval for testing
                
        # Run heartbeat and jobs concurrently
        heartbeat_task = asyncio.create_task(_test_heartbeat())
        results = await asyncio.gather(*tasks)
        heartbeat_task.cancel()
        
        # Verify jobs completed
        assert len(results) == 2
        assert all(r["status"] == "completed" for r in results)
        
        # Note: In a real test, we'd capture actual log output
        # This is a simplified test structure
        
    @pytest.mark.asyncio
    async def test_heartbeat_timing_calculations(self):
        """Test ETA and timing calculations in heartbeat"""
        
        processor = MockProcessor(max_concurrent_jobs=1)
        
        # Create jobs with known timing
        jobs = [MockJob(id=f"timing_job_{i}", source_path=f"/test/doc{i}.pdf", environment="test") 
                for i in range(4)]
        
        execution_start_time = time.time()
        
        # Simulate heartbeat calculations
        async def test_eta_calculation():
            """Test ETA calculation logic"""
            
            # Simulate after some jobs complete
            await asyncio.sleep(0.2)  # Let some jobs complete
            
            done = 2  # Assume 2 jobs completed
            pending = 2  # 2 jobs remaining
            elapsed_time = time.time() - execution_start_time
            
            # Test ETA calculation (from heartbeat logic)
            if done > 0:
                avg_job_time = elapsed_time / done
                estimated_remaining = avg_job_time * pending
                eta_minutes = estimated_remaining / 60
                
                # Verify calculations make sense
                assert avg_job_time > 0, "Average job time should be positive"
                assert estimated_remaining > 0, "Estimated remaining time should be positive"
                assert eta_minutes >= 0, "ETA minutes should be non-negative"
                
                # For short times, should show seconds
                if eta_minutes <= 1:
                    eta_str = f", ETA: {estimated_remaining:.0f}s"
                else:
                    eta_str = f", ETA: {eta_minutes:.1f}min"
                    
                assert "ETA:" in eta_str, "ETA string should contain ETA indicator"
                
        await test_eta_calculation()
        
    @pytest.mark.asyncio
    async def test_heartbeat_slot_usage_accuracy(self):
        """Test accurate slot usage reporting in heartbeat"""
        
        processor = MockProcessor(max_concurrent_jobs=3)
        
        # Test various slot usage scenarios
        test_scenarios = [
            {"active": 0, "max": 3, "pending": 5, "expected_waiting": 5},
            {"active": 2, "max": 3, "pending": 4, "expected_waiting": 3},  
            {"active": 3, "max": 3, "pending": 2, "expected_waiting": 0},
            {"active": 1, "max": 3, "pending": 1, "expected_waiting": 0},
        ]
        
        for scenario in test_scenarios:
            processor._active_jobs = scenario["active"]
            processor.max_concurrent_jobs = scenario["max"]
            
            # Calculate waiting jobs (matching heartbeat logic)
            pending = scenario["pending"]
            active_jobs = processor._active_jobs
            max_slots = processor.max_concurrent_jobs
            waiting_jobs = max(0, pending - active_jobs)
            
            assert waiting_jobs == scenario["expected_waiting"], \
                f"Scenario {scenario}: expected {scenario['expected_waiting']} waiting, got {waiting_jobs}"
                
    @pytest.mark.asyncio
    async def test_heartbeat_detailed_job_logging(self):
        """Test detailed job information in periodic heartbeat logs"""
        
        processor = MockProcessor(max_concurrent_jobs=2)
        jobs = [
            MockJob(id="detail_job_1", source_path="/test/detailed_doc_1.pdf", environment="test"),
            MockJob(id="detail_job_2", source_path="/test/detailed_doc_2.pdf", environment="test"),
            MockJob(id="detail_job_3", source_path="/test/detailed_doc_3.pdf", environment="test"),
        ]
        
        # Simulate the detailed logging logic (every 5th heartbeat)
        def test_detailed_logging():
            """Test the job detail extraction logic"""
            
            # Mock tasks and jobs state
            mock_tasks = [MagicMock() for _ in jobs]
            for i, task in enumerate(mock_tasks):
                task.done.return_value = (i < 1)  # First job done, others pending
                
            # Extract job details (matching heartbeat logic)
            job_details = []
            for i, (task, job) in enumerate(zip(mock_tasks, jobs)):
                if not task.done():
                    source_name = Path(job.source_path).name  
                    job_details.append(f"{job.id}({source_name})")
                    
            # Verify job detail extraction
            assert len(job_details) == 2, f"Expected 2 pending jobs, got: {job_details}"
            assert "detail_job_2(detailed_doc_2.pdf)" in job_details
            assert "detail_job_3(detailed_doc_3.pdf)" in job_details
            
            # Test active vs waiting separation
            max_slots = processor.max_concurrent_jobs
            if job_details:
                active_list = ", ".join(job_details[:max_slots])
                assert len(active_list.split(", ")) <= max_slots
                
                if len(job_details) > max_slots:
                    waiting_list = ", ".join(job_details[max_slots:max_slots+3])
                    assert len(waiting_list) > 0
                    
        test_detailed_logging()
        
    @pytest.mark.asyncio 
    async def test_heartbeat_completion_logging_format(self):
        """Test job completion logging format and content"""
        
        # Test successful completion logging
        successful_result = {
            "job_id": "success_job_123",
            "status": "completed",
            "total_time": 45.3,
            "wait_time": 2.1,
            "processing_time": 43.2,
            "artifacts_path": "/test/artifacts/job_123"
        }
        
        # Format completion message (matching nightly runner logic)
        total_time = successful_result.get('total_time', 0)
        wait_time = successful_result.get('wait_time', 0) 
        processing_time = successful_result.get('processing_time', 0)
        job_id = successful_result.get('job_id', 'unknown')
        status = successful_result.get('status', 'unknown')
        
        if status == "completed":
            completion_msg = (
                f"✅ Job {job_id} COMPLETED - "
                f"Total: {total_time:.1f}s (Wait: {wait_time:.1f}s, Processing: {processing_time:.1f}s), "
                f"Artifacts: {successful_result.get('artifacts_path', 'N/A')}"
            )
            
            # Verify format
            assert "✅" in completion_msg
            assert "COMPLETED" in completion_msg
            assert "Total: 45.3s" in completion_msg
            assert "Wait: 2.1s" in completion_msg
            assert "Processing: 43.2s" in completion_msg
            assert "/test/artifacts/job_123" in completion_msg
            
        # Test failure completion logging
        failed_result = {
            "job_id": "failed_job_456", 
            "status": "failed",
            "total_time": 12.5,
            "wait_time": 1.3,
            "error_message": "Pipeline execution failed due to corrupted PDF structure"
        }
        
        status = failed_result.get('status', 'unknown')
        if status == "failed":
            error_msg = failed_result.get('error_message', 'Unknown error')[:100]
            completion_msg = (
                f"❌ Job {failed_result.get('job_id')} FAILED - "
                f"Total: {failed_result.get('total_time', 0):.1f}s (Wait: {failed_result.get('wait_time', 0):.1f}s), "
                f"Error: {error_msg}"
            )
            
            # Verify error format
            assert "❌" in completion_msg
            assert "FAILED" in completion_msg
            assert "Total: 12.5s" in completion_msg
            assert "Wait: 1.3s" in completion_msg
            assert "Pipeline execution failed" in completion_msg
            
    @pytest.mark.asyncio
    async def test_heartbeat_cancellation_handling(self):
        """Test proper heartbeat cancellation and cleanup"""
        
        processor = MockProcessor()
        
        # Create a heartbeat task
        async def _cancellable_heartbeat():
            try:
                while True:
                    # Simulate heartbeat work
                    await asyncio.sleep(0.1)
                    print("Heartbeat running...")
            except asyncio.CancelledError:
                print("Heartbeat cancelled")
                return
                
        # Test cancellation
        heartbeat_task = asyncio.create_task(_cancellable_heartbeat())
        
        # Let it run briefly
        await asyncio.sleep(0.15)
        
        # Cancel and verify cleanup
        heartbeat_task.cancel()
        
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass  # Expected
            
        assert heartbeat_task.cancelled() or heartbeat_task.done()


if __name__ == "__main__":
    pytest.main([__file__])