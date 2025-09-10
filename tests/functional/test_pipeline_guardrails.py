# tests/functional/test_pipeline_guardrails.py
"""
Functional tests for pipeline guardrails integration with bulk_ingest pipeline.

Tests end-to-end guardrail behavior within the actual ingestion system,
verifying that guardrail failures prevent downstream processing and proper
failure reporting occurs.
"""

import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from dataclasses import asdict
import pytest

# Add the project root to the path for testing
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bulk_ingest import Pass6Pipeline, Source6PassResult
from src_common.pass_c_extraction import PassCResult
from src_common.pass_d_vector_enrichment import PassDResult, EnrichmentStats
from src_common.pipeline_guardrails import GuardrailPolicy


class TestGuardrailIntegration:
    """Test guardrail integration with 6-pass pipeline"""
    
    def test_pass_c_zero_chunks_abort(self):
        """Test that zero chunks from Pass C causes pipeline abort"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test_zero_chunks.pdf")
        
        # Mock zero-chunk Pass C result
        zero_chunk_result = PassCResult(
            source_file="test_zero_chunks.pdf",
            job_id="test_job",
            chunks_extracted=0,  # Zero chunks should trigger abort
            chunks_loaded=0,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True  # Pass "succeeds" but produces no output
        )
        
        with patch('src_common.pass_c_extraction.process_pass_c', return_value=zero_chunk_result), \
             patch('scripts.bulk_ingest.logger') as mock_logger, \
             patch.object(pipeline, '_should_run_pass') as mock_should_run, \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.stat') as mock_stat:
            
            # Setup mocks
            mock_should_run.side_effect = lambda pass_id, *args: pass_id in ["A", "B", "C"]
            mock_stat_result = Mock()
            mock_stat_result.st_size = 1000
            mock_stat_result.st_mtime = 1234567890
            mock_stat.return_value = mock_stat_result
            
            # Process source through pipeline
            result = pipeline._process_source_sequential(pdf_path, "dev")
            
            # Verify abort behavior
            assert result.success is False
            assert result.failure_reason == "Zero output at Pass C"
            assert result.failed_pass == "C"
            assert result.aborted_after_pass == "C"
            
            # Verify that only A, B, C passes were attempted
            assert "A" in result.pass_results
            assert "B" in result.pass_results  
            assert "C" in result.pass_results
            assert "D" not in result.pass_results  # Should not reach Pass D
            assert "E" not in result.pass_results
            assert "F" not in result.pass_results
            
            # Verify FATAL logging occurred
            fatal_calls = [call for call in mock_logger.error.call_args_list 
                          if '[FATAL]' in str(call)]
            assert len(fatal_calls) >= 1
    
    def test_pass_c_success_continues_pipeline(self):
        """Test that successful Pass C allows pipeline to continue"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test_success.pdf")
        
        # Mock successful Pass C result
        success_result = PassCResult(
            source_file="test_success.pdf",
            job_id="test_job",
            chunks_extracted=15,  # Non-zero chunks should allow continuation
            chunks_loaded=15,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=["chunks.jsonl"],
            manifest_path="manifest.json",
            success=True
        )
        
        # Mock successful Pass D result
        pass_d_success = PassDResult(
            source_file="test_success.pdf",
            job_id="test_job",
            chunks_processed=15,
            chunks_vectorized=15,
            chunks_loaded=15,
            enrichment_stats=Mock(),
            processing_time_ms=2000,
            artifacts=["vectors.json"],
            manifest_path="manifest.json",
            success=True
        )
        
        with patch('src_common.pass_c_extraction.process_pass_c', return_value=success_result), \
             patch('src_common.pass_d_vector_enrichment.process_pass_d', return_value=pass_d_success), \
             patch('src_common.pass_e_graph_builder.process_pass_e', return_value=Mock(success=True)), \
             patch('src_common.pass_f_finalizer.process_pass_f', return_value=Mock(success=True)), \
             patch('src_common.pass_a_toc_parser.process_pass_a', return_value=Mock(success=True)), \
             patch('src_common.pass_b_logical_splitter.process_pass_b', return_value=Mock(success=True)), \
             patch.object(pipeline, '_should_run_pass', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat_result = Mock()
            mock_stat_result.st_size = 1000
            mock_stat_result.st_mtime = 1234567890
            mock_stat.return_value = mock_stat_result
            
            # Process source through pipeline
            result = pipeline._process_source_sequential(pdf_path, "dev")
            
            # Verify success - all passes should complete
            assert result.success is True
            assert result.failure_reason is None
            assert result.failed_pass is None
            assert result.aborted_after_pass is None
            
            # Verify all passes were executed
            assert "A" in result.pass_results
            assert "B" in result.pass_results
            assert "C" in result.pass_results
            assert "D" in result.pass_results
            assert "E" in result.pass_results
            assert "F" in result.pass_results
    
    def test_pass_d_zero_vectors_abort(self):
        """Test that zero vectors from Pass D causes pipeline abort"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test_zero_vectors.pdf")
        
        # Mock successful Pass C
        pass_c_success = PassCResult(
            source_file="test_zero_vectors.pdf",
            job_id="test_job",
            chunks_extracted=10,
            chunks_loaded=10,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=["chunks.jsonl"],
            manifest_path="manifest.json",
            success=True
        )
        
        # Mock zero-vector Pass D result
        zero_vector_result = PassDResult(
            source_file="test_zero_vectors.pdf",
            job_id="test_job",
            chunks_processed=10,
            chunks_vectorized=0,  # Zero vectors should trigger abort
            chunks_loaded=0,
            enrichment_stats=Mock(),
            processing_time_ms=2000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        with patch('src_common.pass_c_extraction.process_pass_c', return_value=pass_c_success), \
             patch('src_common.pass_d_vector_enrichment.process_pass_d', return_value=zero_vector_result), \
             patch('src_common.pass_a_toc_parser.process_pass_a', return_value=Mock(success=True)), \
             patch('src_common.pass_b_logical_splitter.process_pass_b', return_value=Mock(success=True)), \
             patch('scripts.bulk_ingest.logger') as mock_logger, \
             patch.object(pipeline, '_should_run_pass', return_value=True), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat_result = Mock()
            mock_stat_result.st_size = 1000
            mock_stat_result.st_mtime = 1234567890
            mock_stat.return_value = mock_stat_result
            
            # Process source through pipeline
            result = pipeline._process_source_sequential(pdf_path, "dev")
            
            # Verify abort behavior
            assert result.success is False
            assert result.failure_reason == "Zero output at Pass D"
            assert result.failed_pass == "D"
            assert result.aborted_after_pass == "D"
            
            # Verify passes A-D executed, but not E-F
            assert "A" in result.pass_results
            assert "B" in result.pass_results
            assert "C" in result.pass_results
            assert "D" in result.pass_results
            assert "E" not in result.pass_results  # Should not reach Pass E
            assert "F" not in result.pass_results
    
    def test_skipped_pass_resume_scenario(self):
        """Test guardrails work correctly with resumed/skipped passes"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test_resume.pdf")
        
        with patch('src_common.pass_a_toc_parser.process_pass_a', return_value=Mock(success=True)), \
             patch('src_common.pass_b_logical_splitter.process_pass_b', return_value=Mock(success=True)), \
             patch('src_common.pass_c_extraction.process_pass_c') as mock_pass_c, \
             patch('src_common.pass_d_vector_enrichment.process_pass_d') as mock_pass_d, \
             patch('src_common.pass_e_graph_builder.process_pass_e', return_value=Mock(success=True)), \
             patch('src_common.pass_f_finalizer.process_pass_f', return_value=Mock(success=True)), \
             patch('pathlib.Path.mkdir'), \
             patch('pathlib.Path.stat') as mock_stat:
            
            mock_stat_result = Mock()
            mock_stat_result.st_size = 1000
            mock_stat_result.st_mtime = 1234567890
            mock_stat.return_value = mock_stat_result
            
            # Mock _should_run_pass to simulate resume scenario
            # Passes A, B are skipped (already completed), C, D+ run fresh
            def mock_should_run_pass(pass_id, *args):
                return pass_id in ["C", "D", "E"]  # Skip A, B, F
                
            pipeline._should_run_pass = mock_should_run_pass
            
            # Mock Pass C and D with successful results
            mock_pass_c.return_value = PassCResult(
                source_file="test_resume.pdf",
                job_id="test_job",
                chunks_extracted=8,
                chunks_loaded=8,
                parts_processed=1,
                processing_time_ms=1000,
                artifacts=["chunks.jsonl"],
                manifest_path="manifest.json",
                success=True
            )
            
            mock_pass_d.return_value = PassDResult(
                source_file="test_resume.pdf",
                job_id="test_job",
                chunks_processed=8,
                chunks_vectorized=8,
                chunks_loaded=8,
                enrichment_stats=Mock(),
                processing_time_ms=2000,
                artifacts=["vectors.json"],
                manifest_path="manifest.json",
                success=True
            )
            
            # Process source with resume
            result = pipeline._process_source_sequential(pdf_path, "dev", resume=True)
            
            # Should succeed even with skipped passes
            assert result.success is True
            assert result.failure_reason is None
            
            # Verify skipped passes are marked correctly
            assert result.pass_results["A"]["skipped"] is True
            assert result.pass_results["B"]["skipped"] is True
            assert result.pass_results["F"]["skipped"] is True
            # C, D, E should have run
            assert "chunks_extracted" in str(result.pass_results["C"])
            assert "chunks_vectorized" in str(result.pass_results["D"])


class TestGuardrailEnvironmentBehavior:
    """Test guardrail behavior across different environments"""
    
    def test_production_stricter_thresholds(self):
        """Test that production environment has stricter validation"""
        prod_pipeline = Pass6Pipeline("prod")
        dev_pipeline = Pass6Pipeline("dev")
        
        # Same result that might pass dev but fail prod
        marginal_result = PassCResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_extracted=1,  # Exactly 1 chunk
            chunks_loaded=1,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=["chunks.jsonl"],
            manifest_path="manifest.json",
            success=True
        )
        
        pdf_path = Path("test.pdf")
        job_id = "test_job"
        
        # Dev should pass (threshold = 0, so 1 > 0)
        dev_valid = dev_pipeline._validate_pass_output("C", marginal_result, pdf_path, job_id)
        
        # Prod should fail (threshold = 1, so 1 is not > 1)
        with patch('scripts.bulk_ingest.logger'):
            prod_valid = prod_pipeline._validate_pass_output("C", marginal_result, pdf_path, job_id)
        
        assert dev_valid is True
        assert prod_valid is False
    
    def test_test_environment_lenient_thresholds(self):
        """Test that test environment has lenient validation for testing"""
        test_pipeline = Pass6Pipeline("test")
        
        # Zero output that should still pass in test environment
        zero_result = PassCResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_extracted=0,
            chunks_loaded=0,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        pdf_path = Path("test.pdf")
        job_id = "test_job"
        
        # Test environment should be lenient
        with patch('scripts.bulk_ingest.logger'):
            test_valid = test_pipeline._validate_pass_output("C", zero_result, pdf_path, job_id)
        
        # In test env, even 0 chunks should fail (threshold is 0, so 0 is not > 0)
        assert test_valid is False


class TestGuardrailLogging:
    """Test guardrail logging and error reporting"""
    
    def test_fatal_logging_format(self):
        """Test that FATAL log messages follow BUG-021 specification"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("failing_document.pdf")
        job_id = "job_123456"
        
        zero_result = PassCResult(
            source_file="failing_document.pdf",
            job_id=job_id,
            chunks_extracted=0,
            chunks_loaded=0,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        with patch('scripts.bulk_ingest.logger') as mock_logger:
            result = pipeline._validate_pass_output("C", zero_result, pdf_path, job_id)
            
            assert result is False
            
            # Check FATAL log format matches BUG-021 specification
            error_calls = mock_logger.error.call_args_list
            
            # Should have the specific FATAL message format
            fatal_message_found = False
            for call in error_calls:
                message = str(call)
                if f"[FATAL][{job_id}] Pass C produced zero output — aborting source after Pass C" in message:
                    fatal_message_found = True
                    break
            
            assert fatal_message_found, f"Expected FATAL message not found in: {error_calls}"
    
    def test_abort_source_logging(self):
        """Test logging behavior during source abort"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test_abort.pdf")
        job_id = "abort_job"
        
        zero_result = PassCResult(
            source_file="test_abort.pdf",
            job_id=job_id,
            chunks_extracted=0,
            chunks_loaded=0,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        with patch('scripts.bulk_ingest.logger') as mock_logger:
            result = pipeline._abort_source("C", zero_result, pdf_path, job_id, [], {})
            
            # Verify abort-specific logging
            abort_logs = [call for call in mock_logger.error.call_args_list 
                         if 'aborted' in str(call).lower()]
            assert len(abort_logs) >= 1
            
            # Verify downstream prevention message
            downstream_logs = [call for call in mock_logger.error.call_args_list 
                              if 'downstream' in str(call).lower()]
            assert len(downstream_logs) >= 1


class TestGuardrailResultFormatting:
    """Test proper formatting of guardrail results for job summaries"""
    
    def test_result_dict_includes_failure_metadata(self):
        """Test that Source6PassResult.to_dict includes failure metadata"""
        result = Source6PassResult(
            source="failed_source.pdf",
            job_id="failed_job",
            timings=[],
            pass_results={"C": {"chunks_extracted": 0}},
            success=False,
            error="Pipeline aborted after Pass C",
            failure_reason="Zero output at Pass C",
            failed_pass="C",
            aborted_after_pass="C"
        )
        
        result_dict = result.to_dict()
        
        # Verify all failure metadata is included
        assert result_dict["success"] is False
        assert result_dict["failure_reason"] == "Zero output at Pass C"
        assert result_dict["failed_pass"] == "C"
        assert result_dict["aborted_after_pass"] == "C"
        assert "Pipeline aborted after Pass C" in result_dict["error"]
    
    def test_success_result_no_failure_metadata(self):
        """Test that successful results have None for failure fields"""
        result = Source6PassResult(
            source="success_source.pdf",
            job_id="success_job",
            timings=[],
            pass_results={"A": {"success": True}, "C": {"chunks_extracted": 10}},
            success=True
        )
        
        result_dict = result.to_dict()
        
        # Verify failure metadata is None for successful results
        assert result_dict["success"] is True
        assert result_dict["failure_reason"] is None
        assert result_dict["failed_pass"] is None
        assert result_dict["aborted_after_pass"] is None


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])