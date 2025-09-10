# tests/unit/test_pipeline_guardrails.py
"""
Unit tests for pipeline guardrails system.

Tests the pipeline_guardrails module's ability to validate pass outputs
and implement fail-fast behavior when critical passes produce zero output.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict
from unittest.mock import Mock, patch, MagicMock

from src_common.pipeline_guardrails import (
    GuardrailPolicy, 
    GuardrailResult, 
    get_guardrail_policy
)
from src_common.pass_c_extraction import PassCResult
from src_common.pass_d_vector_enrichment import PassDResult, EnrichmentStats
from scripts.bulk_ingest import Pass6Pipeline, Source6PassResult, StepTiming


class TestGuardrailResult:
    """Test GuardrailResult data structure"""
    
    def test_guardrail_result_creation(self):
        """Test basic GuardrailResult creation"""
        result = GuardrailResult(
            passed=True,
            pass_name="C",
            threshold_name="chunks_extracted",
            actual_value=10,
            threshold_value=0
        )
        
        assert result.passed is True
        assert result.pass_name == "C"
        assert result.threshold_name == "chunks_extracted"
        assert result.actual_value == 10
        assert result.threshold_value == 0
        assert result.failure_reason is None
    
    def test_failure_message_success(self):
        """Test failure message for successful validation"""
        result = GuardrailResult(
            passed=True,
            pass_name="C",
            threshold_name="chunks_extracted",
            actual_value=10,
            threshold_value=0
        )
        
        assert result.failure_message == ""
    
    def test_failure_message_failure(self):
        """Test failure message for failed validation"""
        result = GuardrailResult(
            passed=False,
            pass_name="C",
            threshold_name="chunks_extracted",
            actual_value=0,
            threshold_value=0,
            failure_reason="Zero output at Pass C"
        )
        
        expected = "Pass C failed guardrail: chunks_extracted (actual: 0, required: >0)"
        assert result.failure_message == expected


class TestGuardrailPolicy:
    """Test GuardrailPolicy configuration and validation logic"""
    
    def test_policy_initialization_dev(self):
        """Test guardrail policy initialization for dev environment"""
        policy = GuardrailPolicy("dev")
        
        assert policy.env == "dev"
        assert "C" in policy.critical_thresholds
        assert "D" in policy.critical_thresholds
        assert policy.critical_thresholds["C"]["chunks_extracted"] == 0
        assert policy.critical_thresholds["D"]["chunks_vectorized"] == 0
    
    def test_policy_initialization_prod(self):
        """Test guardrail policy initialization for production environment"""
        policy = GuardrailPolicy("prod")
        
        assert policy.env == "prod"
        assert policy.critical_thresholds["C"]["chunks_extracted"] == 1
        assert policy.critical_thresholds["D"]["chunks_vectorized"] == 1
    
    def test_policy_initialization_test(self):
        """Test guardrail policy initialization for test environment"""
        policy = GuardrailPolicy("test")
        
        assert policy.env == "test"
        assert policy.critical_thresholds["C"]["chunks_extracted"] == 0
        assert policy.critical_thresholds["D"]["chunks_vectorized"] == 0
    
    def test_validate_skipped_pass(self):
        """Test validation of skipped pass (resume scenario)"""
        policy = GuardrailPolicy("dev")
        pass_result = {"skipped": True}
        
        result = policy.validate_pass_output("C", pass_result)
        
        assert result.passed is True
        assert result.threshold_name == "skipped"
    
    def test_validate_pass_c_success(self):
        """Test successful Pass C validation"""
        policy = GuardrailPolicy("dev")
        pass_c_result = PassCResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_extracted=15,
            chunks_loaded=15,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=["chunks.jsonl"],
            manifest_path="manifest.json",
            success=True
        )
        
        result = policy.validate_pass_output("C", pass_c_result)
        
        assert result.passed is True
        assert result.pass_name == "C"
        assert result.actual_value == 15
        assert result.threshold_value == 0
        assert result.failure_reason is None
    
    def test_validate_pass_c_failure(self):
        """Test failed Pass C validation (zero chunks)"""
        policy = GuardrailPolicy("dev")
        pass_c_result = PassCResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_extracted=0,  # Zero chunks should fail
            chunks_loaded=0,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        result = policy.validate_pass_output("C", pass_c_result)
        
        assert result.passed is False
        assert result.pass_name == "C"
        assert result.actual_value == 0
        assert result.threshold_value == 0
        assert result.failure_reason == "Zero output at Pass C"
    
    def test_validate_pass_c_dict_format(self):
        """Test Pass C validation with dict format (serialized result)"""
        policy = GuardrailPolicy("dev")
        pass_result_dict = {
            "chunks_extracted": 5,
            "chunks_loaded": 5,
            "success": True
        }
        
        result = policy.validate_pass_output("C", pass_result_dict)
        
        assert result.passed is True
        assert result.actual_value == 5
    
    def test_validate_pass_d_success(self):
        """Test successful Pass D validation"""
        policy = GuardrailPolicy("dev")
        
        # Create mock EnrichmentStats
        mock_stats = Mock()
        mock_stats.total_chunks = 10
        
        pass_d_result = PassDResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_processed=10,
            chunks_vectorized=10,  # Non-zero should pass
            chunks_loaded=10,
            enrichment_stats=mock_stats,
            processing_time_ms=2000,
            artifacts=["vectors.json"],
            manifest_path="manifest.json",
            success=True
        )
        
        result = policy.validate_pass_output("D", pass_d_result)
        
        assert result.passed is True
        assert result.pass_name == "D"
        assert result.actual_value == 10
        assert result.threshold_value == 0
    
    def test_validate_pass_d_failure(self):
        """Test failed Pass D validation (zero vectors)"""
        policy = GuardrailPolicy("dev")
        
        # Create mock EnrichmentStats
        mock_stats = Mock()
        mock_stats.total_chunks = 10
        
        pass_d_result = PassDResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_processed=10,
            chunks_vectorized=0,  # Zero vectors should fail
            chunks_loaded=0,
            enrichment_stats=mock_stats,
            processing_time_ms=2000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        result = policy.validate_pass_output("D", pass_d_result)
        
        assert result.passed is False
        assert result.pass_name == "D"
        assert result.actual_value == 0
        assert result.failure_reason == "Zero output at Pass D"
    
    def test_validate_unknown_pass(self):
        """Test validation of unknown pass (should succeed)"""
        policy = GuardrailPolicy("dev")
        pass_result = {"some_data": "value"}
        
        result = policy.validate_pass_output("X", pass_result)
        
        assert result.passed is True
        assert result.pass_name == "X"
        assert result.threshold_name == "default"
    
    def test_should_abort_source_critical_failure(self):
        """Test abort decision for critical pass failure"""
        policy = GuardrailPolicy("dev")
        pass_c_result = PassCResult(
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
        
        should_abort = policy.should_abort_source("C", pass_c_result)
        
        assert should_abort is True
    
    def test_should_abort_source_success(self):
        """Test abort decision for successful pass"""
        policy = GuardrailPolicy("dev")
        pass_c_result = PassCResult(
            source_file="test.pdf",
            job_id="test_job",
            chunks_extracted=10,
            chunks_loaded=10,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=["chunks.jsonl"],
            manifest_path="manifest.json",
            success=True
        )
        
        should_abort = policy.should_abort_source("C", pass_c_result)
        
        assert should_abort is False
    
    def test_should_abort_source_warning_pass(self):
        """Test abort decision for warning pass (should not abort)"""
        policy = GuardrailPolicy("dev")
        pass_result = {"some_metric": 0}  # Zero output in warning pass
        
        should_abort = policy.should_abort_source("E", pass_result)
        
        assert should_abort is False  # Warning passes don't cause aborts
    
    def test_get_failure_summary(self):
        """Test failure summary generation"""
        policy = GuardrailPolicy("dev")
        pass_c_result = PassCResult(
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
        
        summary = policy.get_failure_summary("C", pass_c_result)
        
        assert summary["failed"] is True
        assert summary["failed_pass"] == "C"
        assert summary["failure_reason"] == "Zero output at Pass C"
        assert summary["actual_value"] == 0
        assert summary["threshold_value"] == 0
        assert "Raw chunk extraction" in summary["description"]


class TestGuardrailPolicyFactory:
    """Test guardrail policy factory function"""
    
    def test_get_guardrail_policy_dev(self):
        """Test factory function for dev environment"""
        policy = get_guardrail_policy("dev")
        
        assert isinstance(policy, GuardrailPolicy)
        assert policy.env == "dev"
    
    def test_get_guardrail_policy_default(self):
        """Test factory function with default environment"""
        policy = get_guardrail_policy()
        
        assert isinstance(policy, GuardrailPolicy)
        assert policy.env == "dev"


class TestPipelineIntegration:
    """Test integration of guardrails with Pass6Pipeline"""
    
    def test_pipeline_initialization_with_guardrails(self):
        """Test that Pass6Pipeline initializes with guardrail policy"""
        pipeline = Pass6Pipeline("dev")
        
        assert hasattr(pipeline, 'guardrail_policy')
        assert isinstance(pipeline.guardrail_policy, GuardrailPolicy)
        assert pipeline.guardrail_policy.env == "dev"
    
    def test_validate_pass_output_success(self):
        """Test pipeline pass validation method for success case"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test.pdf")
        job_id = "test_job"
        
        pass_c_result = PassCResult(
            source_file="test.pdf",
            job_id=job_id,
            chunks_extracted=10,
            chunks_loaded=10,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=["chunks.jsonl"],
            manifest_path="manifest.json",
            success=True
        )
        
        with patch('src_common.pipeline_guardrails.logger') as mock_logger:
            result = pipeline._validate_pass_output("C", pass_c_result, pdf_path, job_id)
            
            assert result is True
            mock_logger.error.assert_not_called()
    
    def test_validate_pass_output_failure(self):
        """Test pipeline pass validation method for failure case"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test.pdf")
        job_id = "test_job"
        
        pass_c_result = PassCResult(
            source_file="test.pdf",
            job_id=job_id,
            chunks_extracted=0,  # Should cause failure
            chunks_loaded=0,
            parts_processed=1,
            processing_time_ms=1000,
            artifacts=[],
            manifest_path="manifest.json",
            success=True
        )
        
        with patch('scripts.bulk_ingest.logger') as mock_logger:
            result = pipeline._validate_pass_output("C", pass_c_result, pdf_path, job_id)
            
            assert result is False
            # Check that FATAL log messages were created
            mock_logger.error.assert_called()
            fatal_calls = [call for call in mock_logger.error.call_args_list 
                          if '[FATAL]' in str(call)]
            assert len(fatal_calls) >= 2  # Should have multiple FATAL log lines
    
    def test_abort_source_metadata(self):
        """Test abort source method creates proper failure metadata"""
        pipeline = Pass6Pipeline("dev")
        pdf_path = Path("test.pdf")
        job_id = "test_job"
        timings = [StepTiming("test", 0, 1000)]
        pass_results = {"A": {"success": True}, "B": {"success": True}}
        
        pass_c_result = PassCResult(
            source_file="test.pdf",
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
            result = pipeline._abort_source("C", pass_c_result, pdf_path, job_id, timings, pass_results)
            
            assert isinstance(result, Source6PassResult)
            assert result.success is False
            assert result.failure_reason == "Zero output at Pass C"
            assert result.failed_pass == "C"
            assert result.aborted_after_pass == "C"
            assert "Pipeline aborted after Pass C" in result.error
            
            # Verify logging
            mock_logger.error.assert_called()


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_invalid_pass_result_type(self):
        """Test handling of invalid pass result types"""
        policy = GuardrailPolicy("dev")
        
        # Test with invalid object type
        invalid_result = "not a valid result"
        
        result = policy.validate_pass_output("C", invalid_result)
        
        # Should handle gracefully and treat as zero output
        assert result.passed is False
        assert result.actual_value == 0
    
    def test_missing_pass_result_fields(self):
        """Test handling of pass results missing expected fields"""
        policy = GuardrailPolicy("dev")
        
        # Dict missing chunks_extracted field
        incomplete_result = {"source_file": "test.pdf", "success": True}
        
        result = policy.validate_pass_output("C", incomplete_result)
        
        # Should default to 0 and fail validation
        assert result.passed is False
        assert result.actual_value == 0
    
    def test_production_stricter_thresholds(self):
        """Test that production environment has stricter thresholds"""
        dev_policy = GuardrailPolicy("dev")
        prod_policy = GuardrailPolicy("prod")
        
        # Dev allows 0, prod requires > 0
        assert dev_policy.critical_thresholds["C"]["chunks_extracted"] == 0
        assert prod_policy.critical_thresholds["C"]["chunks_extracted"] == 1
        
        # Test with 1 chunk - should pass dev but fail prod with strict threshold
        pass_result = {"chunks_extracted": 1}
        
        dev_result = dev_policy.validate_pass_output("C", pass_result)
        prod_result = prod_policy.validate_pass_output("C", pass_result)
        
        assert dev_result.passed is True
        assert prod_result.passed is False  # Prod requires > 1


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])