# tests/functional/test_bug022_mixed_batch_scenarios.py
"""
Functional tests for BUG-022 mixed batch scenarios.

Tests end-to-end behavior with mixed success/failure batches to ensure:
- Correct exit code propagation (non-zero when any source fails integrity)
- Proper status reporting in logs and CLI output
- Accurate failure table generation
- Summary artifact integrity validation metadata
"""

import pytest
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from scripts.bulk_ingest import (
    main, 
    Source6PassResult, 
    StepTiming,
    validate_source_success_criteria,
    print_failure_table
)


class TestMixedBatchScenarios:
    """Test mixed batch scenarios for BUG-022"""
    
    @pytest.fixture
    def temp_upload_dir(self):
        """Create temporary upload directory with test PDFs"""
        temp_dir = tempfile.mkdtemp()
        upload_dir = Path(temp_dir) / "uploads"
        upload_dir.mkdir()
        
        # Create dummy PDF files
        (upload_dir / "good_source.pdf").write_bytes(b"%PDF-1.4 dummy content")
        (upload_dir / "bad_source.pdf").write_bytes(b"%PDF-1.4 dummy content")
        
        yield upload_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def create_good_result(self, source: str) -> Source6PassResult:
        """Create a successful source result meeting all criteria"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True, "skipped": False},
            "C": {"chunks_extracted": 10, "success": True, "skipped": False},
            "D": {"chunks_vectorized": 8, "success": True, "skipped": False}
        }
        return Source6PassResult(
            source=source,
            job_id="good_job",
            timings=[StepTiming("total", 0, 2000)],
            pass_results=pass_results,
            success=True
        )
    
    def create_integrity_failed_result(self, source: str) -> Source6PassResult:
        """Create a result that fails integrity validation"""
        pass_results = {
            "A": {"toc_entries": 0, "success": True, "skipped": False},  # Fail: zero ToC
            "C": {"chunks_extracted": 0, "success": True, "skipped": False},  # Fail: zero chunks
            "D": {"chunks_vectorized": 0, "success": True, "skipped": False}  # Fail: zero vectors
        }
        return Source6PassResult(
            source=source,
            job_id="bad_job",
            timings=[StepTiming("total", 0, 1000)],
            pass_results=pass_results,
            success=True  # Initially marked as successful by pipeline
        )
    
    def create_guardrail_failed_result(self, source: str) -> Source6PassResult:
        """Create a result that failed during pipeline guardrails"""
        return Source6PassResult(
            source=source,
            job_id="guard_job",
            timings=[StepTiming("total", 0, 500)],
            pass_results={"A": {"success": True}},  # Only got through Pass A
            success=False,
            error="Guardrail failure",
            failed_pass="C",
            failure_reason="Zero output at Pass C"
        )
    
    @patch('scripts.bulk_ingest.Pass6Pipeline')
    @patch('scripts.bulk_ingest.check_chunk_dictionary_consistency')
    def test_mixed_batch_one_good_one_bad_integrity(self, mock_consistency, mock_pipeline_class):
        """Test batch with 1 good source and 1 integrity-failed source"""
        # Setup mock pipeline
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock results: one good, one bad integrity
        good_result = self.create_good_result("good_source.pdf")
        bad_result = self.create_integrity_failed_result("bad_source.pdf")
        
        mock_pipeline.process_source_6pass.side_effect = [good_result, bad_result]
        
        # Mock consistency report
        mock_consistency.return_value = {
            "chunk_count": 10,
            "dictionary_count": 20,
            "chunk_to_dict_ratio": 0.5,
            "warnings": []
        }
        
        # Test arguments
        test_args = [
            "--env", "test",
            "--upload-dir", "dummy_path",
            "--no-cleanup"
        ]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.glob', return_value=[Path("good_source.pdf"), Path("bad_source.pdf")]), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', create=True), \
             patch('json.dump'), \
             patch('scripts.bulk_ingest.logger') as mock_logger, \
             patch('scripts.bulk_ingest.print_failure_table') as mock_print_table:
            
            exit_code = main(test_args)
            
            # Verify exit code is non-zero (failure)
            assert exit_code == 1
            
            # Verify integrity validation was applied
            assert bad_result.integrity_failed is True
            assert bad_result.success is False  # Should be overridden
            assert "Integrity validation failed" in str(bad_result.error)
            
            # Verify failure table was printed
            mock_print_table.assert_called_once()
            
            # Verify integrity failure logging
            error_calls = [call for call in mock_logger.error.call_args_list 
                          if '[INTEGRITY FAILURE]' in str(call)]
            assert len(error_calls) > 0
    
    @patch('scripts.bulk_ingest.Pass6Pipeline')
    @patch('scripts.bulk_ingest.check_chunk_dictionary_consistency')
    def test_mixed_batch_guardrail_and_integrity_failures(self, mock_consistency, mock_pipeline_class):
        """Test batch with both guardrail and integrity failures"""
        # Setup mock pipeline
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock results: guardrail failure and integrity failure
        guardrail_result = self.create_guardrail_failed_result("guardrail_fail.pdf")
        integrity_result = self.create_integrity_failed_result("integrity_fail.pdf")
        
        mock_pipeline.process_source_6pass.side_effect = [guardrail_result, integrity_result]
        
        # Mock consistency report
        mock_consistency.return_value = {
            "chunk_count": 0,
            "dictionary_count": 10,
            "chunk_to_dict_ratio": 0.0,  # Critical failure
            "warnings": ["CRITICAL: chunk-to-dictionary ratio (0.000) < 0.05"]
        }
        
        test_args = [
            "--env", "test",
            "--upload-dir", "dummy_path",
            "--no-cleanup"
        ]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.glob', return_value=[Path("guardrail_fail.pdf"), Path("integrity_fail.pdf")]), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', create=True), \
             patch('json.dump'), \
             patch('scripts.bulk_ingest.logger') as mock_logger, \
             patch('scripts.bulk_ingest.print_failure_table') as mock_print_table:
            
            exit_code = main(test_args)
            
            # Should return 1 (failure) because all sources failed
            assert exit_code == 1
            
            # Verify both failure types are handled
            mock_print_table.assert_called_once()
            
            # Verify integrity validation was attempted on integrity_result
            assert integrity_result.integrity_failed is True
    
    @patch('scripts.bulk_ingest.Pass6Pipeline')
    @patch('scripts.bulk_ingest.check_chunk_dictionary_consistency')
    def test_all_sources_succeed_integrity_validation(self, mock_consistency, mock_pipeline_class):
        """Test batch where all sources pass integrity validation"""
        # Setup mock pipeline
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Mock results: all good
        good_result_1 = self.create_good_result("good1.pdf") 
        good_result_2 = self.create_good_result("good2.pdf")
        
        mock_pipeline.process_source_6pass.side_effect = [good_result_1, good_result_2]
        
        # Mock consistency report - good ratio
        mock_consistency.return_value = {
            "chunk_count": 20,
            "dictionary_count": 30,
            "chunk_to_dict_ratio": 0.67,
            "warnings": []
        }
        
        test_args = [
            "--env", "test", 
            "--upload-dir", "dummy_path",
            "--no-cleanup"
        ]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.glob', return_value=[Path("good1.pdf"), Path("good2.pdf")]), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', create=True), \
             patch('json.dump'), \
             patch('scripts.bulk_ingest.logger'), \
             patch('scripts.bulk_ingest.print_failure_table') as mock_print_table:
            
            exit_code = main(test_args)
            
            # Should return 0 (success) because all sources passed
            assert exit_code == 0
            
            # Verify both sources still marked as successful
            assert good_result_1.success is True
            assert good_result_2.success is True
            assert good_result_1.integrity_failed is False
            assert good_result_2.integrity_failed is False
            
            # Failure table should still be called but with empty results
            mock_print_table.assert_called_once()
    
    def test_success_criteria_validation_integration(self):
        """Test success criteria validation function directly"""
        # Test good case
        good_result = self.create_good_result("test.pdf")
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(good_result, consistency_report)
        
        assert validation["passed"] is True
        assert validation["toc_entries"] == 5
        assert validation["raw_chunks"] == 10
        assert validation["vectors"] == 8
        assert len(validation["failures"]) == 0
        
        # Test bad case
        bad_result = self.create_integrity_failed_result("test.pdf")
        bad_consistency = {"chunk_to_dict_ratio": 0.02}  # Critical failure
        
        bad_validation = validate_source_success_criteria(bad_result, bad_consistency)
        
        assert bad_validation["passed"] is False
        assert len(bad_validation["failures"]) == 4  # ToC, chunks, vectors, ratio
        assert "ToC entries < 1" in str(bad_validation["failures"])
        assert "Raw chunks < 1" in str(bad_validation["failures"])
        assert "Vectors < 1" in str(bad_validation["failures"])
        assert "chunk_to_dict_ratio 0.020 < 0.05" in str(bad_validation["failures"])
    
    @patch('builtins.print')
    def test_failure_table_mixed_failure_types(self, mock_print):
        """Test failure table with mixed failure types"""
        # Create results with different failure types
        integrity_fail = self.create_integrity_failed_result("integrity.pdf")
        integrity_fail.integrity_failed = True
        integrity_fail.integrity_failures = ["Raw chunks < 1 (Pass C incomplete)"]
        integrity_fail.success = False
        
        guardrail_fail = self.create_guardrail_failed_result("guardrail.pdf") 
        
        generic_fail = Source6PassResult(
            source="generic.pdf",
            job_id="job",
            timings=[],
            pass_results={},
            success=False,
            error="File parsing error"
        )
        
        results = [integrity_fail, guardrail_fail, generic_fail]
        
        print_failure_table(results)
        
        # Verify all failure types are represented in output
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        table_content = " ".join(print_calls)
        
        assert "integrity" in table_content.lower()
        assert "guardrail" in table_content.lower() 
        assert "generic" in table_content.lower()
        assert "C (Extract)" in table_content
        assert "C (Guard)" in table_content
        assert "Pipeline" in table_content


class TestSummaryArtifactIntegration:
    """Test that summary artifacts include integrity validation metadata"""
    
    @patch('scripts.bulk_ingest.Pass6Pipeline')
    @patch('scripts.bulk_ingest.check_chunk_dictionary_consistency')
    @patch('builtins.open', new_callable=Mock)
    @patch('json.dump')
    def test_summary_includes_integrity_metadata(self, mock_json_dump, mock_open, mock_consistency, mock_pipeline_class):
        """Test that summary artifacts include integrity validation fields"""
        # Setup mocks
        mock_pipeline = Mock()
        mock_pipeline_class.return_value = mock_pipeline
        
        # Create result with integrity failure
        bad_result = Source6PassResult(
            source="bad.pdf",
            job_id="job", 
            timings=[StepTiming("total", 0, 1000)],
            pass_results={"A": {"toc_entries": 0}},  # Will fail validation
            success=True
        )
        
        mock_pipeline.process_source_6pass.return_value = bad_result
        mock_consistency.return_value = {"chunk_to_dict_ratio": 0.02, "warnings": []}
        
        test_args = ["--env", "test", "--upload-dir", "dummy", "--no-cleanup"]
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.glob', return_value=[Path("bad.pdf")]), \
             patch('pathlib.Path.mkdir'), \
             patch('scripts.bulk_ingest.logger'), \
             patch('scripts.bulk_ingest.print_failure_table'):
            
            main(test_args)
            
            # Verify json.dump was called with integrity metadata
            assert mock_json_dump.called
            summary_data = mock_json_dump.call_args[0][0]
            
            # Check that sources include integrity fields
            sources = summary_data["sources"]
            assert len(sources) == 1
            source_data = sources[0]
            
            assert "integrity_failed" in source_data
            assert "integrity_failures" in source_data
            assert "toc_entries" in source_data
            assert "raw_chunks" in source_data
            assert "vectors" in source_data
            
            # Verify integrity failure was detected
            assert source_data["integrity_failed"] is True
            assert len(source_data["integrity_failures"]) > 0


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])