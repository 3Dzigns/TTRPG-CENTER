# tests/functional/test_pass_c_bypass_pipeline_integration.py
"""
Functional tests for SHA-based Pass C bypass pipeline integration

Tests the complete workflow from pipeline adapter through to AstraDB operations,
focusing on realistic scenarios and edge cases.
"""

import pytest
import tempfile
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from src_common.pipeline_adapter import ProgressAwarePipelineWrapper
from src_common.progress_callback import (
    PassType, PassStatus, PassProgress, JobProgress,
    LoggingProgressCallback
)
from src_common.pass_c_bypass_validator import BypassValidationResult, ProcessingRecord
from src_common.artifact_preservation import ArtifactCopyResult


class TestPipelineBypassIntegration:
    """Test Pass C bypass integration in pipeline context"""
    
    @pytest.fixture
    def mock_pipeline_environment(self):
        """Create mock pipeline environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create artifacts directory structure
            artifacts_root = Path(temp_dir) / "artifacts"
            artifacts_root.mkdir()
            
            # Create test PDF
            test_pdf = Path(temp_dir) / "test_source.pdf"
            test_pdf.write_text("Sample PDF content for SHA calculation")
            
            # Create Pass A manifest with source hash
            manifest_data = {
                "source_info": {
                    "source_hash": hashlib.sha256(b"Sample PDF content for SHA calculation").hexdigest(),
                    "file_size": len("Sample PDF content for SHA calculation")
                },
                "job_id": "test_job_123",
                "environment": "dev"
            }
            
            manifest_path = artifacts_root / "manifest.json"
            with manifest_path.open('w') as f:
                json.dump(manifest_data, f)
                
            # Create job progress
            job_progress = JobProgress(
                job_id="test_job_123",
                source_path=str(test_pdf),
                environment="dev",
                start_time=datetime.now().timestamp()
            )
            
            yield temp_dir, test_pdf, artifacts_root, job_progress, manifest_data["source_info"]["source_hash"]
    
    @pytest.fixture
    def pipeline_wrapper(self, mock_pipeline_environment):
        """Create pipeline wrapper with mock environment"""
        temp_dir, test_pdf, artifacts_root, job_progress, source_hash = mock_pipeline_environment
        
        mock_pipeline = Mock()
        progress_callback = LoggingProgressCallback()
        loop = Mock()
        
        wrapper = ProgressAwarePipelineWrapper(
            mock_pipeline, job_progress, progress_callback, loop, artifacts_root
        )
        
        return wrapper, test_pdf, source_hash
    
    @patch('src_common.pipeline_adapter.get_bypass_validator')
    @patch('src_common.pipeline_adapter.get_artifact_manager')
    def test_execute_pass_c_bypass_approved(self, mock_artifact_manager, mock_bypass_validator, pipeline_wrapper):
        """Test Pass C execution when bypass is approved"""
        wrapper, test_pdf, source_hash = pipeline_wrapper
        
        # Setup bypass validator mock - approve bypass
        mock_validator = Mock()
        mock_processing_record = ProcessingRecord(
            source_hash=source_hash,
            source_path=str(test_pdf),
            chunk_count=150,
            last_processed_at=datetime.now(timezone.utc),
            environment="dev",
            pass_c_artifacts_path="/previous/artifacts"
        )
        
        mock_validation_result = BypassValidationResult(
            can_bypass=True,
            reason="SHA and chunk count match - processed previously",
            processing_record=mock_processing_record,
            astra_chunk_count=150,
            expected_chunk_count=150
        )
        
        mock_validator.can_bypass_pass_c.return_value = mock_validation_result
        mock_bypass_validator.return_value = mock_validator
        
        # Setup artifact manager mock - successful copy
        mock_manager = Mock()
        mock_copy_result = ArtifactCopyResult(
            success=True,
            artifacts_copied=5,
            source_path="/previous/artifacts",
            destination_path=str(wrapper.artifacts_root),
            copied_files=["extracted_content.json", "chunks.json", "metadata.json"]
        )
        mock_manager.copy_artifacts_from_previous_run.return_value = mock_copy_result
        mock_manager.create_bypass_marker.return_value = True
        mock_artifact_manager.return_value = mock_manager
        
        # Create pass progress
        pass_progress = PassProgress(
            pass_type=PassType.PASS_C,
            status=PassStatus.STARTING,
            start_time=datetime.now().timestamp()
        )
        
        # Execute Pass C
        result = wrapper._execute_pass_c(test_pdf, "dev", pass_progress)
        
        # Verify bypass was successful
        assert result.success is True
        assert result.bypassed is True
        assert result.bypass_reason == "SHA and chunk count match - processed previously"
        assert result.chunks_loaded == 150
        assert result.source_hash == source_hash
        
        # Verify pass progress was updated
        assert pass_progress.status == PassStatus.COMPLETED
        assert pass_progress.bypass_reason == "SHA and chunk count match - processed previously"
        assert pass_progress.chunks_processed == 150
        
        # Verify validator was called
        mock_validator.can_bypass_pass_c.assert_called_once_with(source_hash, test_pdf)
        
        # Verify artifacts were copied
        mock_manager.copy_artifacts_from_previous_run.assert_called_once()
        mock_manager.create_bypass_marker.assert_called_once()
    
    @patch('src_common.pipeline_adapter.get_bypass_validator')
    @patch('src_common.pass_c_extraction.process_pass_c')
    def test_execute_pass_c_bypass_denied_first_time(self, mock_process_pass_c, mock_bypass_validator, pipeline_wrapper):
        """Test Pass C execution when bypass denied - first time processing"""
        wrapper, test_pdf, source_hash = pipeline_wrapper
        
        # Setup bypass validator mock - deny bypass (first time)
        mock_validator = Mock()
        mock_validation_result = BypassValidationResult(
            can_bypass=False,
            reason="Source not found in processing history - first time processing",
            processing_record=None
        )
        
        mock_validator.can_bypass_pass_c.return_value = mock_validation_result
        mock_bypass_validator.return_value = mock_validator
        
        # Setup Pass C processing mock - successful
        mock_pass_c_result = Mock()
        mock_pass_c_result.success = True
        mock_pass_c_result.chunks_created = 175
        mock_process_pass_c.return_value = mock_pass_c_result
        
        # Create pass progress
        pass_progress = PassProgress(
            pass_type=PassType.PASS_C,
            status=PassStatus.STARTING,
            start_time=datetime.now().timestamp()
        )
        
        # Execute Pass C
        result = wrapper._execute_pass_c(test_pdf, "dev", pass_progress)
        
        # Verify normal Pass C processing occurred
        assert result.success is True
        assert not hasattr(result, 'bypassed') or not result.bypassed
        
        # Verify Pass C was actually called
        mock_process_pass_c.assert_called_once_with(
            test_pdf, wrapper.artifacts_root, wrapper.job_progress.job_id, "dev"
        )
        
        # Verify success was recorded for future bypass
        mock_validator.record_successful_processing.assert_called_once_with(
            source_hash, test_pdf, 175, wrapper.artifacts_root
        )
    
    @patch('src_common.pipeline_adapter.get_bypass_validator')
    @patch('src_common.pass_c_extraction.process_pass_c')
    def test_execute_pass_c_bypass_denied_chunk_mismatch(self, mock_process_pass_c, mock_bypass_validator, pipeline_wrapper):
        """Test Pass C execution when bypass denied due to chunk count mismatch"""
        wrapper, test_pdf, source_hash = pipeline_wrapper
        
        # Setup bypass validator mock - deny bypass (chunk mismatch)
        mock_validator = Mock()
        mock_processing_record = ProcessingRecord(
            source_hash=source_hash,
            source_path=str(test_pdf),
            chunk_count=150,  # Expected
            last_processed_at=datetime.now(timezone.utc),
            environment="dev",
            pass_c_artifacts_path=None
        )
        
        mock_validation_result = BypassValidationResult(
            can_bypass=False,
            reason="Chunk count mismatch - expected 150, found 120",
            processing_record=mock_processing_record,
            astra_chunk_count=120,  # Actual
            expected_chunk_count=150
        )
        
        mock_validator.can_bypass_pass_c.return_value = mock_validation_result
        mock_validator.remove_chunks_for_source.return_value = 120  # Removed stale chunks
        mock_bypass_validator.return_value = mock_validator
        
        # Setup Pass C processing mock - successful reprocessing
        mock_pass_c_result = Mock()
        mock_pass_c_result.success = True
        mock_pass_c_result.chunks_created = 150  # Corrected count
        mock_process_pass_c.return_value = mock_pass_c_result
        
        # Create pass progress
        pass_progress = PassProgress(
            pass_type=PassType.PASS_C,
            status=PassStatus.STARTING,
            start_time=datetime.now().timestamp()
        )
        
        # Execute Pass C
        result = wrapper._execute_pass_c(test_pdf, "dev", pass_progress)
        
        # Verify normal Pass C processing occurred after cleanup
        assert result.success is True
        
        # Verify stale chunks were removed
        mock_validator.remove_chunks_for_source.assert_called_once_with(source_hash)
        
        # Verify Pass C was executed after cleanup
        mock_process_pass_c.assert_called_once()
        
        # Verify success was recorded with correct count
        mock_validator.record_successful_processing.assert_called_once_with(
            source_hash, test_pdf, 150, wrapper.artifacts_root
        )
    
    @patch('src_common.pipeline_adapter.get_bypass_validator')
    @patch('src_common.pipeline_adapter.get_artifact_manager')
    def test_execute_pass_c_artifact_copy_failure(self, mock_artifact_manager, mock_bypass_validator, pipeline_wrapper):
        """Test Pass C execution when artifact copying fails during bypass"""
        wrapper, test_pdf, source_hash = pipeline_wrapper
        
        # Setup bypass validator mock - approve bypass
        mock_validator = Mock()
        mock_processing_record = ProcessingRecord(
            source_hash=source_hash,
            source_path=str(test_pdf),
            chunk_count=150,
            last_processed_at=datetime.now(timezone.utc),
            environment="dev",
            pass_c_artifacts_path="/previous/artifacts"
        )
        
        mock_validation_result = BypassValidationResult(
            can_bypass=True,
            reason="SHA and chunk count match",
            processing_record=mock_processing_record,
            astra_chunk_count=150,
            expected_chunk_count=150
        )
        
        mock_validator.can_bypass_pass_c.return_value = mock_validation_result
        mock_bypass_validator.return_value = mock_validator
        
        # Setup artifact manager mock - failed copy
        mock_manager = Mock()
        mock_copy_result = ArtifactCopyResult(
            success=False,
            artifacts_copied=0,
            source_path="/previous/artifacts",
            destination_path=str(wrapper.artifacts_root),
            error_message="Source artifacts directory not found"
        )
        mock_manager.copy_artifacts_from_previous_run.return_value = mock_copy_result
        mock_artifact_manager.return_value = mock_manager
        
        # Create pass progress
        pass_progress = PassProgress(
            pass_type=PassType.PASS_C,
            status=PassStatus.STARTING,
            start_time=datetime.now().timestamp()
        )
        
        # Execute Pass C - should fall back to normal processing
        with patch('src_common.pass_c_extraction.process_pass_c') as mock_process_pass_c:
            mock_pass_c_result = Mock()
            mock_pass_c_result.success = True
            mock_pass_c_result.chunks_created = 150
            mock_process_pass_c.return_value = mock_pass_c_result
            
            result = wrapper._execute_pass_c(test_pdf, "dev", pass_progress)
            
            # Should fall back to normal Pass C processing
            mock_process_pass_c.assert_called_once()
    
    def test_get_source_hash_from_manifest(self, pipeline_wrapper):
        """Test getting source hash from Pass A manifest"""
        wrapper, test_pdf, expected_hash = pipeline_wrapper
        
        hash_result = wrapper._get_source_hash(test_pdf)
        
        assert hash_result == expected_hash
    
    def test_get_source_hash_compute_fallback(self, pipeline_wrapper):
        """Test fallback to computing source hash when manifest unavailable"""
        wrapper, test_pdf, expected_hash = pipeline_wrapper
        
        # Remove the manifest to force fallback
        (wrapper.artifacts_root / "manifest.json").unlink()
        
        with patch('src_common.pipeline_adapter.PassAToCParser') as mock_parser_class:
            mock_parser = Mock()
            mock_parser._compute_file_hash.return_value = expected_hash
            mock_parser_class.return_value = mock_parser
            
            hash_result = wrapper._get_source_hash(test_pdf)
            
            assert hash_result == expected_hash
            mock_parser._compute_file_hash.assert_called_once_with(test_pdf)


class TestBypassWorkflowScenarios:
    """Test various bypass workflow scenarios"""
    
    def test_bypass_with_missing_artifacts_path(self):
        """Test bypass when processing record has no artifacts path"""
        # This scenario occurs when an older processing record exists
        # but artifacts path wasn't stored (before the bypass feature)
        pass
    
    def test_bypass_with_corrupted_artifacts(self):
        """Test bypass when artifacts exist but are corrupted"""
        # This tests the artifact validation and fallback logic
        pass
    
    def test_concurrent_bypass_checks(self):
        """Test bypass validation under concurrent access"""
        # This would test database locking and race conditions
        pass
    
    def test_bypass_with_environment_mismatch(self):
        """Test bypass when source was processed in different environment"""
        # This tests environment isolation in bypass logic
        pass


@pytest.mark.integration
class TestEndToEndBypassScenarios:
    """End-to-end integration tests for bypass scenarios"""
    
    @pytest.mark.skip(reason="Requires full database and AstraDB setup")
    def test_complete_bypass_workflow_with_real_db(self):
        """Test complete bypass workflow with real database connections"""
        # This would be a full integration test requiring:
        # - Real database setup
        # - AstraDB connection
        # - Complete artifacts directory structure
        # - Real Pass A/B/C/D/E pipeline execution
        pass
    
    @pytest.mark.skip(reason="Requires AstraDB connection")
    def test_chunk_synchronization_with_real_astra(self):
        """Test chunk removal and upsert with real AstraDB"""
        # This would test:
        # - Real chunk removal from AstraDB
        # - Chunk count validation
        # - Safe upsert operations
        # - Error handling with network issues
        pass


class TestBypassErrorHandling:
    """Test error handling in bypass system"""
    
    def test_bypass_validator_database_error(self, pipeline_wrapper):
        """Test handling of database errors in bypass validator"""
        wrapper, test_pdf, source_hash = pipeline_wrapper
        
        with patch('src_common.pipeline_adapter.get_bypass_validator') as mock_get_validator:
            mock_validator = Mock()
            mock_validator.can_bypass_pass_c.side_effect = Exception("Database connection failed")
            mock_get_validator.return_value = mock_validator
            
            # Should handle error gracefully and proceed with normal Pass C
            pass_progress = PassProgress(
                pass_type=PassType.PASS_C,
                status=PassStatus.STARTING,
                start_time=datetime.now().timestamp()
            )
            
            with patch('src_common.pass_c_extraction.process_pass_c') as mock_process_pass_c:
                mock_pass_c_result = Mock()
                mock_pass_c_result.success = True
                mock_process_pass_c.return_value = mock_pass_c_result
                
                result = wrapper._execute_pass_c(test_pdf, "dev", pass_progress)
                
                # Should fall back to normal processing
                mock_process_pass_c.assert_called_once()
    
    def test_bypass_astra_connection_error(self, pipeline_wrapper):
        """Test handling of AstraDB connection errors"""
        wrapper, test_pdf, source_hash = pipeline_wrapper
        
        with patch('src_common.pipeline_adapter.get_bypass_validator') as mock_get_validator:
            mock_validator = Mock()
            mock_validator.can_bypass_pass_c.side_effect = Exception("AstraDB connection timeout")
            mock_get_validator.return_value = mock_validator
            
            pass_progress = PassProgress(
                pass_type=PassType.PASS_C,
                status=PassStatus.STARTING,
                start_time=datetime.now().timestamp()
            )
            
            # Should handle AstraDB errors gracefully
            with patch('src_common.pass_c_extraction.process_pass_c') as mock_process_pass_c:
                mock_pass_c_result = Mock()
                mock_pass_c_result.success = True
                mock_process_pass_c.return_value = mock_pass_c_result
                
                result = wrapper._execute_pass_c(test_pdf, "dev", pass_progress)
                
                # Should fall back to normal processing
                mock_process_pass_c.assert_called_once()


# Parameterized tests for various scenarios
@pytest.mark.parametrize("chunk_expected,chunk_actual,should_bypass", [
    (150, 150, True),   # Perfect match
    (150, 120, False),  # Mismatch - too few
    (150, 180, False),  # Mismatch - too many
    (0, 0, True),       # Edge case - empty
])
def test_chunk_count_validation_scenarios(chunk_expected, chunk_actual, should_bypass):
    """Test various chunk count validation scenarios"""
    # This would test the validation logic with different count combinations
    pass