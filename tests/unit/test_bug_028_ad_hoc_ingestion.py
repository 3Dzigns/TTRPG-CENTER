"""
Test for BUG-028: Ad-Hoc Ingestion Job Not Executing Pipeline

This test reproduces the bug where ad-hoc ingestion jobs show as "running"
but never advance beyond the initial manifest header.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import shutil

from src_common.admin.ingestion import AdminIngestionService


class TestBug028AdHocIngestionPipeline:
    """Test BUG-028 specific bug fixes for ad-hoc ingestion jobs"""

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
    async def test_ad_hoc_job_should_fail_without_fix(self, ingestion_service, temp_artifacts_dir, caplog):
        """Test that demonstrates the original bug - pipeline doesn't execute"""
        # Create a broken service instance without the fix
        broken_service = AdminIngestionService()

        # Remove the _active_jobs and _pass_sequence attributes to simulate the original bug
        delattr(broken_service, '_active_jobs')
        delattr(broken_service, '_pass_sequence')

        # Mock the artifacts directory
        with patch('pathlib.Path') as mock_path:
            mock_path.return_value = temp_artifacts_dir

            # This should create the job but fail to start the pipeline (graceful error handling)
            job_id = await broken_service.start_ingestion_job(
                environment="dev",
                source_file="test.pdf",
                options={"test": True},
                job_type="ad_hoc"
            )

            # Verify job was created despite pipeline failure
            assert job_id.startswith("job_")

            # Verify that error was logged about failed pipeline start
            assert "Failed to start ingestion pipeline" in caplog.text
            assert "'AdminIngestionService' object has no attribute '_active_jobs'" in caplog.text

    @pytest.mark.asyncio
    async def test_ad_hoc_job_executes_full_pipeline_with_fix(self, ingestion_service, temp_artifacts_dir):
        """Test that ad-hoc jobs now execute the full pipeline"""
        # Set up temporary directory structure
        artifacts_dir = temp_artifacts_dir / "artifacts" / "dev"
        logs_dir = temp_artifacts_dir / "env" / "dev" / "logs"

        with patch('pathlib.Path') as mock_path_class:
            # Mock Path creation to use our temp directory
            def mock_path_init(path_str):
                if "artifacts/dev/" in str(path_str):
                    return artifacts_dir / str(path_str).split("artifacts/dev/")[-1]
                elif "env/dev/logs" in str(path_str):
                    return logs_dir
                return Path(str(path_str))

            mock_path_class.side_effect = mock_path_init

            # Patch file operations
            with patch('builtins.open', create=True) as mock_open:
                with patch('json.dump') as mock_json_dump:
                    # Start an ad-hoc ingestion job
                    job_id = await ingestion_service.start_ingestion_job(
                        environment="dev",
                        source_file="test_document.pdf",
                        options={"test_mode": True},
                        job_type="ad_hoc"
                    )

                    # Verify job ID format
                    assert job_id.startswith("job_")
                    assert "_dev" in job_id

                    # Verify that the manifest was created with proper structure
                    assert mock_json_dump.called
                    manifest = mock_json_dump.call_args[0][0]

                    assert manifest["job_id"] == job_id
                    assert manifest["environment"] == "dev"
                    assert manifest["source_file"] == "test_document.pdf"
                    assert manifest["status"] == "pending"
                    assert manifest["lane"] == "A"
                    assert "phases" in manifest
                    assert len(manifest["phases"]) == 4  # parse, enrich, compile, hgrn_validate

                    # Verify that a task was created for pipeline execution
                    assert job_id in ingestion_service._active_jobs

                    # Wait a moment for the async task to potentially start
                    await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_pipeline_creates_artifacts_for_each_phase(self, ingestion_service, temp_artifacts_dir):
        """Test that the pipeline creates the expected artifacts for each phase"""
        job_path = temp_artifacts_dir / "test_job"
        job_path.mkdir(parents=True, exist_ok=True)

        manifest = {
            "source_file": "test.pdf",
            "job_id": "test_job_123"
        }

        # Test Pass A (parse)
        await ingestion_service._execute_phase("parse", job_path, manifest, "test_job_123")
        chunks_file = job_path / "passA_chunks.json"
        assert chunks_file.exists()

        with open(chunks_file, 'r') as f:
            chunks_data = json.load(f)
        assert "chunks" in chunks_data
        assert len(chunks_data["chunks"]) == 15
        assert chunks_data["job_id"] == "test_job_123"

        # Test Pass B (enrich)
        await ingestion_service._execute_phase("enrich", job_path, manifest, "test_job_123")
        enriched_file = job_path / "passB_enriched.json"
        assert enriched_file.exists()

        with open(enriched_file, 'r') as f:
            enriched_data = json.load(f)
        assert "enrichment_results" in enriched_data
        assert "dictionary_updates" in enriched_data

        # Test Pass C (compile)
        await ingestion_service._execute_phase("compile", job_path, manifest, "test_job_123")
        graph_file = job_path / "passC_graph.json"
        assert graph_file.exists()

        with open(graph_file, 'r') as f:
            graph_data = json.load(f)
        assert "graph_structure" in graph_data
        assert graph_data["compilation_status"] == "completed"

    @pytest.mark.asyncio
    async def test_ingestion_service_has_required_attributes(self, ingestion_service):
        """Test that the service has the required attributes that were missing"""
        # Verify the fix: these attributes should exist
        assert hasattr(ingestion_service, '_active_jobs')
        assert hasattr(ingestion_service, '_pass_sequence')

        # Verify they have the right types and values
        assert isinstance(ingestion_service._active_jobs, dict)
        assert isinstance(ingestion_service._pass_sequence, list)
        assert ingestion_service._pass_sequence == ["parse", "enrich", "compile"]

    @pytest.mark.asyncio
    async def test_event_loop_handling(self, ingestion_service):
        """Test that the service properly handles event loop creation/retrieval"""
        # This tests the fix for event loop issues in the _start_ingestion_pipeline method

        job_path = Path("/tmp/test_job")
        manifest = {"job_id": "test", "status": "pending"}
        manifest_file = job_path / "manifest.json"
        log_file_path = job_path / "job.log"

        # Mock the async pipeline to avoid actual execution
        with patch.object(ingestion_service, '_run_ingestion_pipeline') as mock_pipeline:
            mock_pipeline.return_value = None

            # This should not raise an exception about event loops
            ingestion_service._start_ingestion_pipeline(
                job_id="test_job",
                environment="dev",
                job_path=job_path,
                manifest=manifest,
                manifest_file=manifest_file,
                log_file_path=log_file_path,
                lane="A",
                job_type="ad_hoc",
                options={}
            )

            # Verify the task was created and tracked
            assert "test_job" in ingestion_service._active_jobs

    @pytest.mark.asyncio
    async def test_pipeline_status_progression(self, ingestion_service, temp_artifacts_dir):
        """Test that job status progresses through the pipeline phases"""
        job_path = temp_artifacts_dir / "status_test_job"
        job_path.mkdir(parents=True, exist_ok=True)

        manifest_file = job_path / "manifest.json"
        log_file_path = job_path / "job.log"

        manifest = {
            "job_id": "status_test_job",
            "environment": "dev",
            "source_file": "test.pdf",
            "status": "pending",
            "created_at": time.time(),
            "phases": ["parse", "enrich", "compile"],
            "completed_phases": 0
        }

        # Run the pipeline
        await ingestion_service._run_ingestion_pipeline(
            job_id="status_test_job",
            environment="dev",
            manifest=manifest,
            manifest_file=manifest_file,
            log_file_path=log_file_path,
            lane="A",
            job_type="ad_hoc",
            options={}
        )

        # Verify final status
        assert manifest["status"] == "completed"
        assert manifest["completed_phases"] == 3
        assert manifest["current_phase"] is None
        assert "completed_at" in manifest

        # Verify artifacts were created
        assert (job_path / "passA_chunks.json").exists()
        assert (job_path / "passB_enriched.json").exists()
        assert (job_path / "passC_graph.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])