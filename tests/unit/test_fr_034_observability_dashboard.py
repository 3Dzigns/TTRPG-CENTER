"""
Test for FR-034: Ingestion Process Observability Dashboard

This test suite validates the real-time metrics emission, WebSocket streaming,
and observability dashboard functionality.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import shutil
from dataclasses import asdict

from src_common.admin.ingestion import (
    AdminIngestionService,
    IngestionMetrics,
    PhaseProgress
)


class TestFR034ObservabilityDashboard:
    """Test FR-034 observability dashboard functionality"""

    @pytest.fixture
    def ingestion_service(self):
        return AdminIngestionService()

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_metrics_dataclass_structure(self):
        """Test that IngestionMetrics dataclass has correct structure"""
        metrics = IngestionMetrics(
            job_id="test_job",
            environment="dev",
            timestamp=time.time(),
            phase="parse",
            status="progress",
            total_sources=5,
            processed_sources=2,
            current_source="test_doc.pdf",
            records_processed=150,
            records_failed=2,
            processing_rate=25.5,
            estimated_completion=time.time() + 60
        )

        # Verify all required fields are present
        assert metrics.job_id == "test_job"
        assert metrics.environment == "dev"
        assert metrics.phase == "parse"
        assert metrics.status == "progress"
        assert metrics.total_sources == 5
        assert metrics.processed_sources == 2
        assert metrics.current_source == "test_doc.pdf"
        assert metrics.records_processed == 150
        assert metrics.records_failed == 2
        assert metrics.processing_rate == 25.5
        assert metrics.estimated_completion is not None

        # Verify dataclass can be converted to dict
        metrics_dict = asdict(metrics)
        assert isinstance(metrics_dict, dict)
        assert metrics_dict["job_id"] == "test_job"

    @pytest.mark.asyncio
    async def test_phase_progress_tracking(self):
        """Test PhaseProgress tracking and calculations"""
        start_time = time.time()
        progress = PhaseProgress(
            phase="enrich",
            status="progress",
            start_time=start_time,
            current_time=start_time + 30,
            total_items=10,
            completed_items=7,
            failed_items=1,
            current_item="doc3.pdf",
            processing_rate=0.23,
            estimated_completion=start_time + 50
        )

        # Test property calculations
        assert progress.progress_percent == 70.0  # 7/10 * 100
        assert progress.duration_seconds == 30.0

        # Test edge case with zero total items
        empty_progress = PhaseProgress(
            phase="parse",
            status="started",
            start_time=start_time,
            current_time=start_time,
            total_items=0,
            completed_items=0,
            failed_items=0,
            current_item=None,
            processing_rate=0.0,
            estimated_completion=None
        )
        assert empty_progress.progress_percent == 0.0

    @pytest.mark.asyncio
    async def test_metrics_callback_registration(self, ingestion_service):
        """Test metrics callback registration and unregistration"""
        callback_called = False
        received_metrics = None

        def test_callback(metrics):
            nonlocal callback_called, received_metrics
            callback_called = True
            received_metrics = metrics

        # Test registration
        ingestion_service.register_metrics_callback(test_callback)
        assert test_callback in ingestion_service._metrics_callbacks

        # Test metrics emission
        test_metrics = IngestionMetrics(
            job_id="test_emission",
            environment="dev",
            timestamp=time.time(),
            phase="compile",
            status="completed",
            total_sources=1,
            processed_sources=1,
            current_source=None,
            records_processed=100,
            records_failed=0,
            processing_rate=10.0,
            estimated_completion=None
        )

        await ingestion_service._emit_metrics(test_metrics)

        # Verify callback was called
        assert callback_called is True
        assert received_metrics == test_metrics

        # Test unregistration
        ingestion_service.unregister_metrics_callback(test_callback)
        assert test_callback not in ingestion_service._metrics_callbacks

    @pytest.mark.asyncio
    async def test_real_time_metrics_emission_during_pipeline(self, ingestion_service, temp_artifacts_dir):
        """Test that metrics are emitted during pipeline execution"""
        emitted_metrics = []

        def metrics_collector(metrics):
            emitted_metrics.append(metrics)

        ingestion_service.register_metrics_callback(metrics_collector)

        job_path = temp_artifacts_dir / "metrics_test"
        job_path.mkdir(parents=True, exist_ok=True)
        log_file_path = job_path / "job.log"

        manifest = {
            "job_id": "metrics_test_job",
            "environment": "dev",
            "job_type": "ad_hoc",
            "source_file": "test_doc.pdf",
            "selected_sources": None
        }

        await ingestion_service.execute_lane_a_pipeline(
            job_id="metrics_test_job",
            environment="dev",
            manifest=manifest,
            job_path=job_path,
            log_file_path=log_file_path
        )

        # Verify metrics were emitted for each phase
        assert len(emitted_metrics) > 0

        # Check for phase start and completion metrics
        phase_starts = [m for m in emitted_metrics if m.status == "started"]
        phase_completions = [m for m in emitted_metrics if m.status == "completed"]

        assert len(phase_starts) == 3  # parse, enrich, compile
        assert len(phase_completions) == 3

        # Verify metric progression
        for metrics in emitted_metrics:
            assert metrics.job_id == "metrics_test_job"
            assert metrics.environment == "dev"
            assert metrics.phase in ["parse", "enrich", "compile"]

    @pytest.mark.asyncio
    async def test_processing_rate_calculation(self, ingestion_service):
        """Test processing rate calculations"""
        # Test normal case
        rate = ingestion_service._calculate_processing_rate(100, 50)
        assert rate == 2.0  # 100 items / 50 seconds

        # Test edge cases
        assert ingestion_service._calculate_processing_rate(0, 10) == 0.0
        assert ingestion_service._calculate_processing_rate(10, 0) == 0.0
        assert ingestion_service._calculate_processing_rate(50, -5) == 0.0

    @pytest.mark.asyncio
    async def test_completion_time_estimation(self, ingestion_service):
        """Test completion time estimation logic"""
        current_time = time.time()

        # Test normal case
        estimated_time = ingestion_service._estimate_completion_time(100, 25, 5.0)
        assert estimated_time is not None
        # Should estimate 75 remaining items / 5 per second = 15 seconds from now
        assert abs(estimated_time - (current_time + 15)) < 2  # Allow 2 second tolerance

        # Test edge cases
        assert ingestion_service._estimate_completion_time(100, 100, 5.0) is None  # Already complete
        assert ingestion_service._estimate_completion_time(100, 25, 0.0) is None   # No processing rate
        assert ingestion_service._estimate_completion_time(100, 25, -1.0) is None  # Negative rate

    @pytest.mark.asyncio
    async def test_get_job_metrics(self, ingestion_service):
        """Test getting current job metrics"""
        job_id = "test_metrics_job"

        # Test job not found
        metrics = await ingestion_service.get_job_metrics(job_id)
        assert metrics["status"] == "not_found"

        # Setup mock job progress
        start_time = time.time()
        ingestion_service._job_progress[job_id] = {
            "parse": PhaseProgress(
                phase="parse",
                status="completed",
                start_time=start_time,
                current_time=start_time + 10,
                total_items=5,
                completed_items=5,
                failed_items=0,
                current_item=None,
                processing_rate=0.5,
                estimated_completion=None
            ),
            "enrich": PhaseProgress(
                phase="enrich",
                status="progress",
                start_time=start_time + 10,
                current_time=start_time + 25,
                total_items=5,
                completed_items=3,
                failed_items=0,
                current_item="doc3.pdf",
                processing_rate=0.2,
                estimated_completion=start_time + 40
            )
        }

        # Test job with progress
        metrics = await ingestion_service.get_job_metrics(job_id)
        assert metrics["job_id"] == job_id
        assert metrics["status"] == "running"  # Has in-progress phase
        assert metrics["current_phase"] == "enrich"
        assert metrics["overall_progress"]["total_items"] == 10
        assert metrics["overall_progress"]["completed_items"] == 8
        assert len(metrics["phases"]) == 2

        # Verify phase details
        parse_metrics = metrics["phases"]["parse"]
        assert parse_metrics["status"] == "completed"
        assert parse_metrics["progress_percent"] == 100.0

        enrich_metrics = metrics["phases"]["enrich"]
        assert enrich_metrics["status"] == "progress"
        assert enrich_metrics["progress_percent"] == 60.0
        assert enrich_metrics["current_item"] == "doc3.pdf"

    @pytest.mark.asyncio
    async def test_historical_job_metrics(self, ingestion_service, temp_artifacts_dir):
        """Test historical job metrics extraction from manifest files"""
        environment = "dev"
        artifacts_path = temp_artifacts_dir / f"artifacts/{environment}"
        artifacts_path.mkdir(parents=True, exist_ok=True)

        # Create mock job directories with manifests
        jobs = [
            {
                "job_id": "job_1_dev",
                "job_type": "ad_hoc",
                "environment": "dev",
                "created_at": time.time() - 7200,  # 2 hours ago
                "completed_at": time.time() - 7000,  # 1h 56m ago
                "status": "completed",
                "source_count": 1,
                "parse_result": {
                    "processed_count": 15,
                    "artifact_count": 1,
                    "duration_seconds": 45.2,
                    "status": "completed"
                },
                "enrich_result": {
                    "processed_count": 15,
                    "artifact_count": 1,
                    "duration_seconds": 67.8,
                    "status": "completed"
                },
                "compile_result": {
                    "processed_count": 15,
                    "artifact_count": 1,
                    "duration_seconds": 23.1,
                    "status": "completed"
                }
            },
            {
                "job_id": "job_2_dev",
                "job_type": "selective",
                "environment": "dev",
                "created_at": time.time() - 3600,  # 1 hour ago
                "completed_at": time.time() - 3400,  # 56m ago
                "status": "completed",
                "source_count": 3,
                "parse_result": {
                    "processed_count": 45,
                    "artifact_count": 3,
                    "duration_seconds": 120.5,
                    "status": "completed"
                }
            }
        ]

        # Create manifest files
        for job in jobs:
            job_dir = artifacts_path / job["job_id"]
            job_dir.mkdir(parents=True, exist_ok=True)

            manifest_file = job_dir / "manifest.json"
            with open(manifest_file, 'w', encoding='utf-8') as f:
                json.dump(job, f, indent=2)

        # Mock the artifacts path
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'iterdir') as mock_iterdir:
                mock_iterdir.return_value = [
                    artifacts_path / "job_1_dev",
                    artifacts_path / "job_2_dev"
                ]

                # Test historical metrics retrieval
                historical_metrics = await ingestion_service.get_historical_job_metrics(environment, limit=10)

                assert len(historical_metrics) == 2

                # Verify job 1 metrics
                job1_metrics = next(m for m in historical_metrics if m["job_id"] == "job_1_dev")
                assert job1_metrics["job_type"] == "ad_hoc"
                assert job1_metrics["status"] == "completed"
                assert job1_metrics["source_count"] == 1
                assert len(job1_metrics["phases"]) == 3

                # Verify job 2 metrics
                job2_metrics = next(m for m in historical_metrics if m["job_id"] == "job_2_dev")
                assert job2_metrics["job_type"] == "selective"
                assert job2_metrics["source_count"] == 3
                assert len(job2_metrics["phases"]) == 1  # Only parse phase

    @pytest.mark.asyncio
    async def test_async_metrics_callback(self, ingestion_service):
        """Test that async callbacks are properly handled"""
        async_callback_called = False
        received_metrics = None

        async def async_test_callback(metrics):
            nonlocal async_callback_called, received_metrics
            async_callback_called = True
            received_metrics = metrics
            await asyncio.sleep(0.01)  # Simulate async work

        # Register async callback
        ingestion_service.register_metrics_callback(async_test_callback)

        # Emit metrics
        test_metrics = IngestionMetrics(
            job_id="async_test",
            environment="dev",
            timestamp=time.time(),
            phase="parse",
            status="started",
            total_sources=1,
            processed_sources=0,
            current_source="test.pdf",
            records_processed=0,
            records_failed=0,
            processing_rate=0.0,
            estimated_completion=None
        )

        await ingestion_service._emit_metrics(test_metrics)

        # Verify async callback was called
        assert async_callback_called is True
        assert received_metrics == test_metrics

    @pytest.mark.asyncio
    async def test_error_handling_in_metrics_emission(self, ingestion_service):
        """Test error handling when metrics callbacks fail"""
        def failing_callback(metrics):
            raise Exception("Callback failed!")

        def working_callback(metrics):
            working_callback.called = True

        working_callback.called = False

        # Register both callbacks
        ingestion_service.register_metrics_callback(failing_callback)
        ingestion_service.register_metrics_callback(working_callback)

        # Emit metrics - should not fail even with failing callback
        test_metrics = IngestionMetrics(
            job_id="error_test",
            environment="dev",
            timestamp=time.time(),
            phase="compile",
            status="completed",
            total_sources=1,
            processed_sources=1,
            current_source=None,
            records_processed=50,
            records_failed=0,
            processing_rate=5.0,
            estimated_completion=None
        )

        # This should not raise an exception
        await ingestion_service._emit_metrics(test_metrics)

        # Working callback should still have been called
        assert working_callback.called is True

    @pytest.mark.asyncio
    async def test_progress_metrics_during_source_processing(self, ingestion_service, temp_artifacts_dir):
        """Test that progress metrics are emitted during source processing"""
        emitted_metrics = []

        def progress_collector(metrics):
            if metrics.status == "progress":
                emitted_metrics.append(metrics)

        ingestion_service.register_metrics_callback(progress_collector)

        # Setup job with multiple sources
        job_path = temp_artifacts_dir / "progress_test"
        job_path.mkdir(parents=True, exist_ok=True)

        sources_to_process = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
        manifest = {"job_id": "progress_test", "environment": "dev"}

        # Execute phase with multiple sources
        await ingestion_service._execute_phase_unified(
            phase="parse",
            job_path=job_path,
            manifest=manifest,
            job_id="progress_test",
            sources_to_process=sources_to_process,
            log_file_path=job_path / "test.log"
        )

        # Verify progress metrics were emitted
        assert len(emitted_metrics) >= len(sources_to_process)

        # Check progression
        for i, metrics in enumerate(emitted_metrics):
            assert metrics.job_id == "progress_test"
            assert metrics.phase == "parse"
            assert metrics.status == "progress"
            assert metrics.total_sources == len(sources_to_process)
            assert metrics.processed_sources == i


if __name__ == "__main__":
    pytest.main([__file__, "-v"])