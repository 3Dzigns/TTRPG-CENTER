"""
Test for FR-033: Unify Ad-Hoc & Selective Ingestion to Full Lane A Pipeline

This test suite validates the unified ingestion pipeline and selective source processing.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import tempfile
import shutil

from src_common.admin.ingestion import AdminIngestionService


class TestFR033UnifiedIngestionPipeline:
    """Test FR-033 unified ingestion pipeline and selective source processing"""

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
    async def test_unified_pipeline_initialization(self, ingestion_service):
        """Test that the unified pipeline has all required attributes"""
        # Verify unified pipeline attributes exist
        assert hasattr(ingestion_service, 'execute_lane_a_pipeline')
        assert hasattr(ingestion_service, 'get_available_sources')
        assert hasattr(ingestion_service, 'start_selective_ingestion_job')
        assert hasattr(ingestion_service, '_execute_phase_unified')
        assert hasattr(ingestion_service, '_execute_phase_for_source')

        # Verify pipeline sequence is still intact
        assert ingestion_service._pass_sequence == ["parse", "enrich", "compile"]

    @pytest.mark.asyncio
    async def test_selective_job_type_support(self, ingestion_service, temp_artifacts_dir):
        """Test that selective job type is properly supported"""
        selected_sources = ["test_doc1.pdf", "test_doc2.pdf"]

        with patch('pathlib.Path') as mock_path:
            mock_path.return_value = temp_artifacts_dir

            with patch('builtins.open', create=True) as mock_open:
                with patch('json.dump') as mock_json_dump:
                    job_id = await ingestion_service.start_ingestion_job(
                        environment="dev",
                        source_file="selective:test_doc1.pdf,test_doc2.pdf",
                        options={"selected_sources": selected_sources},
                        job_type="selective"
                    )

                    # Verify job ID format for selective jobs
                    assert job_id.startswith("selective_")
                    assert "_dev" in job_id

                    # Verify manifest contains selective job information
                    manifest = mock_json_dump.call_args[0][0]
                    assert manifest["job_type"] == "selective"
                    assert manifest["selected_sources"] == selected_sources
                    assert manifest["source_count"] == 2
                    assert manifest["pipeline_version"] == "unified_v1"

    @pytest.mark.asyncio
    async def test_unified_lane_a_pipeline_execution(self, ingestion_service, temp_artifacts_dir):
        """Test the unified Lane A pipeline execution for all job types"""
        job_path = temp_artifacts_dir / "test_job"
        job_path.mkdir(parents=True, exist_ok=True)
        log_file_path = job_path / "job.log"

        # Test with ad-hoc job (single source)
        manifest_ad_hoc = {
            "job_id": "test_job_ad_hoc",
            "environment": "dev",
            "job_type": "ad_hoc",
            "source_file": "single_doc.pdf",
            "selected_sources": None
        }

        await ingestion_service.execute_lane_a_pipeline(
            job_id="test_job_ad_hoc",
            environment="dev",
            manifest=manifest_ad_hoc,
            job_path=job_path,
            log_file_path=log_file_path
        )

        # Verify phase results were added to manifest
        assert "parse_result" in manifest_ad_hoc
        assert "enrich_result" in manifest_ad_hoc
        assert "compile_result" in manifest_ad_hoc
        assert manifest_ad_hoc["completed_phases"] == 3

        # Verify phase result structure
        parse_result = manifest_ad_hoc["parse_result"]
        assert parse_result["phase"] == "parse"
        assert parse_result["processed_count"] == 1
        assert parse_result["status"] == "completed"
        assert "checksum" in parse_result

    @pytest.mark.asyncio
    async def test_selective_source_processing(self, ingestion_service, temp_artifacts_dir):
        """Test selective source processing with multiple sources"""
        job_path = temp_artifacts_dir / "selective_job"
        job_path.mkdir(parents=True, exist_ok=True)
        log_file_path = job_path / "job.log"

        selected_sources = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
        manifest_selective = {
            "job_id": "test_job_selective",
            "environment": "dev",
            "job_type": "selective",
            "source_file": "selective:doc1.pdf,doc2.pdf,doc3.pdf",
            "selected_sources": selected_sources
        }

        await ingestion_service.execute_lane_a_pipeline(
            job_id="test_job_selective",
            environment="dev",
            manifest=manifest_selective,
            job_path=job_path,
            log_file_path=log_file_path
        )

        # Verify all selected sources were processed
        assert manifest_selective["completed_phases"] == 3

        # Check that phase results reflect multiple sources
        parse_result = manifest_selective["parse_result"]
        assert parse_result["processed_count"] == 3  # All 3 sources

        # Verify source-specific artifacts were created
        for source in selected_sources:
            source_safe = source.replace('/', '_').replace('\\', '_').replace(':', '_').replace('.', '_')
            assert (job_path / f"passA_chunks_{source_safe}.json").exists()
            assert (job_path / f"passB_enriched_{source_safe}.json").exists()
            assert (job_path / f"passC_graph_{source_safe}.json").exists()

    @pytest.mark.asyncio
    async def test_phase_progress_tracking(self, ingestion_service, temp_artifacts_dir):
        """Test enhanced phase progress tracking with counts and checksums"""
        job_path = temp_artifacts_dir / "progress_test"
        job_path.mkdir(parents=True, exist_ok=True)

        # Test phase execution for single source
        phase_result = await ingestion_service._execute_phase_unified(
            phase="parse",
            job_path=job_path,
            manifest={"job_id": "test_progress", "job_type": "ad_hoc"},
            job_id="test_progress",
            sources_to_process=["test_doc.pdf"],
            log_file_path=job_path / "test.log"
        )

        # Verify enhanced tracking information
        assert phase_result["phase"] == "parse"
        assert phase_result["processed_count"] == 1
        assert phase_result["artifact_count"] == 1
        assert "duration_seconds" in phase_result
        assert "checksum" in phase_result
        assert phase_result["status"] == "completed"
        assert len(phase_result["checksum"]) == 64  # SHA256 hash

        # Verify phase results file was created
        phase_file = job_path / "phase_parse_results.json"
        assert phase_file.exists()

        with open(phase_file, 'r') as f:
            phase_data = json.load(f)
            assert phase_data["phase"] == "parse"
            assert phase_data["total_sources"] == 1
            assert len(phase_data["sources"]) == 1

    @pytest.mark.asyncio
    async def test_source_specific_artifact_generation(self, ingestion_service, temp_artifacts_dir):
        """Test that artifacts are generated per source with realistic variation"""
        job_path = temp_artifacts_dir / "artifact_test"
        job_path.mkdir(parents=True, exist_ok=True)

        sources = ["doc1.pdf", "doc2.pdf"]

        for source in sources:
            # Test each phase for each source
            for phase in ["parse", "enrich", "compile"]:
                result = await ingestion_service._execute_phase_for_source(
                    phase=phase,
                    source=source,
                    job_path=job_path,
                    manifest={"job_id": "test_artifacts"},
                    job_id="test_artifacts"
                )

                assert result["source"] == source
                assert result["artifact_count"] == 1
                assert len(result["artifacts"]) == 1

        # Verify different sources produce different content
        doc1_chunks_file = job_path / "passA_chunks_doc1_pdf.json"
        doc2_chunks_file = job_path / "passA_chunks_doc2_pdf.json"

        assert doc1_chunks_file.exists()
        assert doc2_chunks_file.exists()

        with open(doc1_chunks_file, 'r') as f:
            doc1_data = json.load(f)
        with open(doc2_chunks_file, 'r') as f:
            doc2_data = json.load(f)

        # Verify different sources have different content
        assert doc1_data["source_file"] == "doc1.pdf"
        assert doc2_data["source_file"] == "doc2.pdf"
        assert doc1_data["chunk_count"] != doc2_data["chunk_count"]  # Should vary by source

    @pytest.mark.asyncio
    async def test_get_available_sources(self, ingestion_service):
        """Test source discovery for selective ingestion"""
        with patch.object(ingestion_service, '_get_local_sources') as mock_local:
            with patch.object(ingestion_service, '_get_astradb_sources') as mock_astradb:
                # Mock local sources
                mock_local.return_value = [
                    {
                        "id": "local_doc1",
                        "source_file": "local_doc1.pdf",
                        "health": "green",
                        "last_modified": 1000000
                    }
                ]

                # Mock AstraDB sources
                mock_astradb.return_value = [
                    {
                        "id": "astra_doc1",
                        "source_file": "astra_doc1.pdf",
                        "health": "green",
                        "chunk_count": 25,
                        "last_modified": 2000000
                    }
                ]

                sources = await ingestion_service.get_available_sources("dev")

                # Verify sources were combined and processed
                assert len(sources) == 2

                # Check that local source has reingestion flag
                local_source = next(s for s in sources if s["source_file"] == "local_doc1.pdf")
                assert local_source["available_for_reingestion"] is True

                # Check that AstraDB source without local artifacts cannot be reingested
                astra_source = next(s for s in sources if s["source_file"] == "astra_doc1.pdf")
                assert astra_source["available_for_reingestion"] is False

    @pytest.mark.asyncio
    async def test_start_selective_ingestion_job(self, ingestion_service):
        """Test the selective ingestion job creation workflow"""
        selected_sources = ["test_doc1.pdf", "test_doc2.pdf"]

        # Mock source availability check
        mock_available_sources = [
            {
                "source_file": "test_doc1.pdf",
                "available_for_reingestion": True,
                "health": "green"
            },
            {
                "source_file": "test_doc2.pdf",
                "available_for_reingestion": True,
                "health": "yellow"
            }
        ]

        with patch.object(ingestion_service, 'get_available_sources') as mock_get_sources:
            with patch.object(ingestion_service, 'start_ingestion_job') as mock_start_job:
                mock_get_sources.return_value = mock_available_sources
                mock_start_job.return_value = "selective_12345_dev"

                job_id = await ingestion_service.start_selective_ingestion_job(
                    environment="dev",
                    selected_sources=selected_sources,
                    options={"test_option": "value"}
                )

                # Verify job was created with correct parameters
                assert job_id == "selective_12345_dev"
                mock_start_job.assert_called_once()

                call_args = mock_start_job.call_args
                assert call_args[1]["environment"] == "dev"
                assert call_args[1]["job_type"] == "selective"
                assert call_args[1]["options"]["selected_sources"] == selected_sources

    @pytest.mark.asyncio
    async def test_selective_job_validation(self, ingestion_service):
        """Test validation for selective ingestion jobs"""
        # Test empty source list
        with pytest.raises(ValueError, match="At least one source must be selected"):
            await ingestion_service.start_selective_ingestion_job(
                environment="dev",
                selected_sources=[],
                options={}
            )

        # Test invalid sources
        invalid_sources = ["nonexistent_doc.pdf"]
        mock_available_sources = [
            {
                "source_file": "valid_doc.pdf",
                "available_for_reingestion": True
            }
        ]

        with patch.object(ingestion_service, 'get_available_sources') as mock_get_sources:
            mock_get_sources.return_value = mock_available_sources

            with pytest.raises(ValueError, match="Sources not available for reingestion"):
                await ingestion_service.start_selective_ingestion_job(
                    environment="dev",
                    selected_sources=invalid_sources,
                    options={}
                )

    @pytest.mark.asyncio
    async def test_job_manifest_schema_enhancements(self, ingestion_service, temp_artifacts_dir):
        """Test that job manifests contain all new FR-033 fields"""
        selected_sources = ["doc1.pdf", "doc2.pdf"]

        with patch('pathlib.Path') as mock_path:
            mock_path.return_value = temp_artifacts_dir

            with patch('builtins.open', create=True) as mock_open:
                with patch('json.dump') as mock_json_dump:
                    await ingestion_service.start_ingestion_job(
                        environment="dev",
                        source_file="selective:doc1.pdf,doc2.pdf",
                        options={"selected_sources": selected_sources},
                        job_type="selective"
                    )

                    manifest = mock_json_dump.call_args[0][0]

                    # Verify all new FR-033 manifest fields
                    assert "selected_sources" in manifest
                    assert "source_count" in manifest
                    assert "pipeline_version" in manifest
                    assert manifest["selected_sources"] == selected_sources
                    assert manifest["source_count"] == 2
                    assert manifest["pipeline_version"] == "unified_v1"

    @pytest.mark.asyncio
    async def test_backward_compatibility(self, ingestion_service, temp_artifacts_dir):
        """Test that existing ad-hoc and nightly jobs still work with unified pipeline"""
        job_path = temp_artifacts_dir / "compat_test"
        job_path.mkdir(parents=True, exist_ok=True)
        log_file_path = job_path / "job.log"

        # Test ad-hoc job compatibility
        manifest_ad_hoc = {
            "job_id": "test_ad_hoc_compat",
            "environment": "dev",
            "job_type": "ad_hoc",
            "source_file": "legacy_doc.pdf",
            "selected_sources": None
        }

        await ingestion_service.execute_lane_a_pipeline(
            job_id="test_ad_hoc_compat",
            environment="dev",
            manifest=manifest_ad_hoc,
            job_path=job_path,
            log_file_path=log_file_path
        )

        # Verify legacy job still completes successfully
        assert manifest_ad_hoc["completed_phases"] == 3
        assert "parse_result" in manifest_ad_hoc

        # Test nightly job compatibility
        manifest_nightly = {
            "job_id": "test_nightly_compat",
            "environment": "dev",
            "job_type": "nightly",
            "source_file": "nightly_run",
            "selected_sources": None
        }

        await ingestion_service.execute_lane_a_pipeline(
            job_id="test_nightly_compat",
            environment="dev",
            manifest=manifest_nightly,
            job_path=job_path,
            log_file_path=log_file_path
        )

        # Verify nightly job still completes successfully
        assert manifest_nightly["completed_phases"] == 3
        assert "parse_result" in manifest_nightly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])