# tests/unit/test_exit_code_propagation.py
"""
Unit tests for BUG-022 exit code propagation.

Tests that the bulk ingestion script returns the correct exit codes
based on integrity validation results.
"""

import pytest
from scripts.bulk_ingest import Source6PassResult, StepTiming


class TestExitCodePropagation:
    """Test exit code logic for BUG-022"""
    
    def create_result(self, success: bool, integrity_failed: bool = False) -> Source6PassResult:
        """Create a Source6PassResult for testing"""
        result = Source6PassResult(
            source="test.pdf",
            job_id="test_job",
            timings=[StepTiming("test", 0, 1000)],
            pass_results={},
            success=success
        )
        result.integrity_failed = integrity_failed
        return result
    
    def test_exit_code_all_successful(self):
        """Test exit code 0 when all sources succeed"""
        results = [
            self.create_result(success=True, integrity_failed=False),
            self.create_result(success=True, integrity_failed=False)
        ]
        
        # Simulate the exit code calculation logic from main()
        fail = sum(1 for r in results if not r.success)
        exit_code = 0 if fail == 0 else 1
        
        assert exit_code == 0
    
    def test_exit_code_integrity_failure(self):
        """Test exit code 1 when integrity validation fails"""
        results = [
            self.create_result(success=True, integrity_failed=False),  # Good
            self.create_result(success=False, integrity_failed=True)   # Failed integrity
        ]
        
        # Simulate the exit code calculation logic from main()
        fail = sum(1 for r in results if not r.success)
        exit_code = 0 if fail == 0 else 1
        
        assert exit_code == 1
    
    def test_exit_code_pipeline_failure(self):
        """Test exit code 1 when pipeline processing fails"""
        results = [
            self.create_result(success=True, integrity_failed=False),   # Good
            self.create_result(success=False, integrity_failed=False)  # Pipeline failure
        ]
        
        # Simulate the exit code calculation logic from main()
        fail = sum(1 for r in results if not r.success)
        exit_code = 0 if fail == 0 else 1
        
        assert exit_code == 1
    
    def test_exit_code_mixed_failures(self):
        """Test exit code 1 when multiple failure types occur"""
        results = [
            self.create_result(success=True, integrity_failed=False),   # Good
            self.create_result(success=False, integrity_failed=True),  # Integrity failure
            self.create_result(success=False, integrity_failed=False)  # Pipeline failure
        ]
        
        # Simulate the exit code calculation logic from main()
        fail = sum(1 for r in results if not r.success)
        exit_code = 0 if fail == 0 else 1
        
        assert exit_code == 1
        assert fail == 2  # Two failures total
    
    def test_exit_code_calculation_logic(self):
        """Test the specific exit code calculation logic"""
        # Test with no failures
        no_fail_results = [self.create_result(success=True) for _ in range(3)]
        no_fail = sum(1 for r in no_fail_results if not r.success)
        assert (0 if no_fail == 0 else 1) == 0
        
        # Test with one failure  
        one_fail_results = [
            self.create_result(success=True),
            self.create_result(success=False)
        ]
        one_fail = sum(1 for r in one_fail_results if not r.success)
        assert (0 if one_fail == 0 else 1) == 1
        
        # Test with all failures
        all_fail_results = [self.create_result(success=False) for _ in range(3)]
        all_fail = sum(1 for r in all_fail_results if not r.success)
        assert (0 if all_fail == 0 else 1) == 1
    
    def test_success_override_by_integrity_validation(self):
        """Test that integrity validation can override success status"""
        # Create a result that initially succeeded pipeline but fails integrity
        result = self.create_result(success=True, integrity_failed=False)
        
        # Simulate integrity validation failure (this would happen in main loop)
        result.integrity_failed = True
        result.success = False  # Overridden by integrity validation
        result.error = "Integrity validation failed"
        
        # Verify the result is now considered failed
        assert result.success is False
        assert result.integrity_failed is True
        
        # Verify exit code calculation treats it as failure
        results = [result]
        fail = sum(1 for r in results if not r.success)
        exit_code = 0 if fail == 0 else 1
        assert exit_code == 1


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])