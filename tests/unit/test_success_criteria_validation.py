# tests/unit/test_success_criteria_validation.py
"""
Unit tests for BUG-022 success criteria validation system.

Tests the validate_source_success_criteria function's ability to 
properly validate pipeline integrity and prevent false "OK" status
when critical passes produce insufficient output.
"""

import pytest
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict
from unittest.mock import Mock, patch

from scripts.bulk_ingest import (
    Source6PassResult, 
    StepTiming, 
    validate_source_success_criteria,
    print_failure_table
)


class TestSuccessCriteriaValidation:
    """Test success criteria validation for BUG-022"""
    
    def create_mock_result(self, success: bool = True, pass_results: Dict = None) -> Source6PassResult:
        """Create a mock Source6PassResult for testing"""
        if pass_results is None:
            pass_results = {}
            
        return Source6PassResult(
            source="test.pdf",
            job_id="test_job",
            timings=[StepTiming("test", 0, 1000)],
            pass_results=pass_results,
            success=success,
            error=None if success else "Test error"
        )
    
    def test_validation_with_successful_pipeline(self):
        """Test validation of fully successful pipeline"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is True
        assert validation["toc_entries"] == 5
        assert validation["raw_chunks"] == 10
        assert validation["vectors"] == 8
        assert len(validation["failures"]) == 0
    
    def test_validation_with_failed_original_processing(self):
        """Test validation when original processing failed"""
        result = self.create_mock_result(False, {})
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert "Original processing failed" in validation["failures"][0]
    
    def test_validation_with_zero_toc_entries(self):
        """Test validation failure when Pass A produces zero ToC entries"""
        pass_results = {
            "A": {"toc_entries": 0, "success": True},  # Zero ToC entries should fail
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert "ToC entries < 1 (Pass A incomplete)" in validation["failures"]
        assert validation["toc_entries"] == 0
    
    def test_validation_with_zero_chunks_extracted(self):
        """Test validation failure when Pass C produces zero chunks"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 0, "success": True},  # Zero chunks should fail
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert "Raw chunks < 1 (Pass C incomplete)" in validation["failures"]
        assert validation["raw_chunks"] == 0
    
    def test_validation_with_zero_vectors(self):
        """Test validation failure when Pass D produces zero vectors"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 0, "success": True}  # Zero vectors should fail
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert "Vectors < 1 (Pass D incomplete)" in validation["failures"]
        assert validation["vectors"] == 0
    
    def test_validation_with_critical_ratio_failure(self):
        """Test validation failure when chunk-to-dict ratio is critically low"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.03}  # Below 0.05 critical threshold
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert "chunk_to_dict_ratio 0.030 < 0.05 (critical threshold)" in validation["failures"]
    
    def test_validation_with_warning_ratio(self):
        """Test validation passes with warning when ratio is below 0.20 but above 0.05"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.15}  # Between 0.05 and 0.20
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is True  # Should still pass
        assert "chunk_to_dict_ratio 0.150 < 0.20 (warning threshold)" in validation["failures"]
    
    def test_validation_with_multiple_failures(self):
        """Test validation with multiple simultaneous failures"""
        pass_results = {
            "A": {"toc_entries": 0, "success": True},  # Fail
            "C": {"chunks_extracted": 0, "success": True},  # Fail
            "D": {"chunks_vectorized": 0, "success": True}  # Fail
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.02}  # Also fail
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert len(validation["failures"]) == 4  # All four failures
        assert "ToC entries < 1" in str(validation["failures"])
        assert "Raw chunks < 1" in str(validation["failures"])
        assert "Vectors < 1" in str(validation["failures"])
        assert "chunk_to_dict_ratio 0.020 < 0.05" in str(validation["failures"])
    
    def test_validation_with_skipped_passes(self):
        """Test validation handles skipped passes correctly (resume scenario)"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "B": {"skipped": True},  # Skipped pass shouldn't affect validation
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is True
        assert len(validation["failures"]) == 0
    
    def test_validation_with_missing_pass_data(self):
        """Test validation handles missing pass data gracefully"""
        pass_results = {
            "A": {"success": True},  # Missing toc_entries field
            "C": {"success": True},  # Missing chunks_extracted field  
            "D": {"success": True}   # Missing chunks_vectorized field
        }
        result = self.create_mock_result(True, pass_results)
        consistency_report = {"chunk_to_dict_ratio": 0.5}
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        # Should fail because all metrics default to 0
        assert validation["passed"] is False
        assert validation["toc_entries"] == 0
        assert validation["raw_chunks"] == 0
        assert validation["vectors"] == 0
        assert len(validation["failures"]) == 3  # All three thresholds fail


class TestFailureTablePrinting:
    """Test failure table printing functionality"""
    
    def create_result_with_failure(self, source: str, integrity_failed: bool = False, 
                                 integrity_failures: List[str] = None,
                                 failed_pass: str = None, failure_reason: str = None,
                                 error: str = None) -> Source6PassResult:
        """Create a failed Source6PassResult for testing"""
        result = Source6PassResult(
            source=source,
            job_id="test_job", 
            timings=[StepTiming("test", 0, 1000)],
            pass_results={},
            success=False,
            error=error
        )
        result.integrity_failed = integrity_failed
        result.integrity_failures = integrity_failures or []
        result.failed_pass = failed_pass
        result.failure_reason = failure_reason
        return result
    
    @patch('builtins.print')
    def test_print_failure_table_no_failures(self, mock_print):
        """Test failure table printing with no failures"""
        results = [
            Source6PassResult("test1.pdf", "job1", [], {}, True),
            Source6PassResult("test2.pdf", "job2", [], {}, True)
        ]
        
        print_failure_table(results)
        
        # Should not print anything when all sources succeed
        mock_print.assert_not_called()
    
    @patch('builtins.print')
    def test_print_failure_table_with_integrity_failures(self, mock_print):
        """Test failure table printing with integrity failures"""
        results = [
            self.create_result_with_failure(
                "test1.pdf", 
                integrity_failed=True,
                integrity_failures=["Raw chunks < 1 (Pass C incomplete)"]
            ),
            self.create_result_with_failure(
                "test2.pdf",
                integrity_failed=True, 
                integrity_failures=["Vectors < 1 (Pass D incomplete)"]
            )
        ]
        
        print_failure_table(results)
        
        # Verify table structure is printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("FAILED SOURCES SUMMARY" in call for call in print_calls)
        assert any("test1" in call and "C (Extract)" in call for call in print_calls)
        assert any("test2" in call and "D (Vector)" in call for call in print_calls)
    
    @patch('builtins.print')  
    def test_print_failure_table_with_guardrail_failures(self, mock_print):
        """Test failure table printing with guardrail failures"""
        results = [
            self.create_result_with_failure(
                "test1.pdf",
                failed_pass="C",
                failure_reason="Zero output at Pass C"
            )
        ]
        
        print_failure_table(results)
        
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("test1" in call and "C (Guard)" in call for call in print_calls)
    
    @patch('builtins.print')
    def test_print_failure_table_with_generic_errors(self, mock_print):
        """Test failure table printing with generic pipeline errors"""
        results = [
            self.create_result_with_failure(
                "test1.pdf",
                error="File parsing error"
            )
        ]
        
        print_failure_table(results)
        
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("test1" in call and "Pipeline" in call for call in print_calls)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_validation_with_zero_ratio_denominator(self):
        """Test validation when consistency report has zero ratio"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = Source6PassResult("test.pdf", "job", [], pass_results, True)
        consistency_report = {"chunk_to_dict_ratio": 0.0}  # Zero ratio
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        assert validation["passed"] is False
        assert "chunk_to_dict_ratio 0.000 < 0.05 (critical threshold)" in validation["failures"]
    
    def test_validation_with_missing_consistency_report(self):
        """Test validation with missing or malformed consistency report"""
        pass_results = {
            "A": {"toc_entries": 5, "success": True},
            "C": {"chunks_extracted": 10, "success": True},
            "D": {"chunks_vectorized": 8, "success": True}
        }
        result = Source6PassResult("test.pdf", "job", [], pass_results, True)
        consistency_report = {}  # Missing chunk_to_dict_ratio
        
        validation = validate_source_success_criteria(result, consistency_report)
        
        # Should fail because ratio defaults to 0.0
        assert validation["passed"] is False
        assert "chunk_to_dict_ratio 0.000 < 0.05 (critical threshold)" in validation["failures"]


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])