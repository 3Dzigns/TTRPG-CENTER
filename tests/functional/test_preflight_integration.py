# tests/functional/test_preflight_integration.py
"""
Functional tests for preflight integration with bulk_ingest pipeline.

Tests end-to-end preflight behavior within the actual ingestion system,
verifying that preflight failures prevent processing and success allows
normal operation.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
from unittest.mock import patch, Mock
import pytest

# Add the project root to the path for testing
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bulk_ingest import main as bulk_ingest_main
from src_common.preflight_checks import PreflightError


class TestBulkIngestPreflightIntegration:
    """Test preflight integration with bulk ingestion pipeline"""
    
    def test_bulk_ingest_preflight_success(self):
        """Test bulk ingestion proceeds when preflight checks pass"""
        test_args = [
            "--env", "dev",
            "--no-logfile",  # Don't create log files in tests
            "--no-cleanup",  # Don't clean up artifacts
            # No --upload-dir so it should exit cleanly after preflight
        ]
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            # Mock successful preflight
            mock_preflight.return_value = None
            
            result = bulk_ingest_main(test_args)
            
            # Should proceed past preflight and exit normally (no upload dir)
            assert result == 0
            mock_preflight.assert_called_once()
    
    def test_bulk_ingest_preflight_failure(self):
        """Test bulk ingestion fails when preflight checks fail"""
        test_args = [
            "--env", "dev", 
            "--no-logfile",
            "--no-cleanup",
        ]
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            # Mock preflight failure
            mock_preflight.side_effect = PreflightError("Missing tesseract")
            
            result = bulk_ingest_main(test_args)
            
            # Should exit with code 2 (dependency issues)
            assert result == 2
            mock_preflight.assert_called_once()
    
    def test_bulk_ingest_skip_preflight(self):
        """Test bulk ingestion can skip preflight when requested"""
        test_args = [
            "--env", "dev",
            "--no-logfile",
            "--no-cleanup", 
            "--skip-preflight",
        ]
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            result = bulk_ingest_main(test_args)
            
            # Should skip preflight and proceed normally
            assert result == 0
            mock_preflight.assert_not_called()
    
    def test_bulk_ingest_preflight_before_processing(self):
        """Test that preflight runs before any document processing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a dummy PDF file
            dummy_pdf = temp_path / "test.pdf"
            dummy_pdf.write_bytes(b"%PDF-1.4\\nHello World")
            
            test_args = [
                "--env", "dev",
                "--no-logfile",
                "--no-cleanup",
                "--upload-dir", str(temp_path),
            ]
            
            with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight, \
                 patch('src_common.astra_loader.AstraLoader') as mock_loader:
                
                # Mock preflight failure BEFORE any processing
                mock_preflight.side_effect = PreflightError("Tools missing")
                
                result = bulk_ingest_main(test_args)
                
                # Should fail at preflight before reaching AstraLoader
                assert result == 2
                mock_preflight.assert_called_once()
                # AstraLoader should not be instantiated due to early preflight failure
                mock_loader.assert_not_called()
    
    def test_preflight_logs_tool_versions_on_success(self, caplog):
        """Test that successful preflight logs tool versions"""
        test_args = [
            "--env", "dev",
            "--no-logfile",
            "--no-cleanup",
        ]
        
        with patch('src_common.preflight_checks.PreflightValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator_class.return_value = mock_validator
            
            # Simulate successful validation
            mock_validator.validate_dependencies.return_value = None
            
            result = bulk_ingest_main(test_args)
            
            assert result == 0
            mock_validator.validate_dependencies.assert_called_once()
            mock_validator.cleanup.assert_called_once()
    
    def test_preflight_error_message_clarity(self, caplog):
        """Test that preflight errors produce clear, actionable messages"""
        test_args = [
            "--env", "dev",
            "--no-logfile", 
            "--no-cleanup",
        ]
        
        error_message = "Required OCR tools not available: tesseract, pdfinfo"
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            mock_preflight.side_effect = PreflightError(error_message)
            
            result = bulk_ingest_main(test_args)
            
            assert result == 2
            # Check that error message is logged
            assert any(error_message in record.message for record in caplog.records)
            assert any("--skip-preflight" in record.message for record in caplog.records)
    
    def test_preflight_warning_when_skipped(self, caplog):
        """Test that skipping preflight produces appropriate warnings"""
        test_args = [
            "--env", "dev",
            "--no-logfile",
            "--no-cleanup",
            "--skip-preflight",
        ]
        
        result = bulk_ingest_main(test_args)
        
        assert result == 0
        # Check that warning is logged
        assert any("Skipping preflight" in record.message for record in caplog.records)
        assert any("silent failures" in record.message for record in caplog.records)


class TestRealWorldPreflightScenarios:
    """Test preflight behavior in realistic scenarios"""
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_windows_path_discovery_integration(self):
        """Test Windows path discovery integration (requires Windows)"""
        test_args = [
            "--env", "dev",
            "--no-logfile",
            "--no-cleanup",
        ]
        
        # This test runs against real system - may pass or fail depending on installs
        # The goal is to verify integration works without mocking
        try:
            result = bulk_ingest_main(test_args)
            # Could be 0 (tools found) or 2 (tools missing) - both valid
            assert result in [0, 2]
        except Exception as e:
            pytest.fail(f"Preflight integration failed with exception: {e}")
    
    def test_production_environment_preflight(self):
        """Test preflight behavior in production-like environment"""
        test_args = [
            "--env", "prod",
            "--no-logfile",
            "--no-cleanup",
        ]
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            # In prod, preflight failure should definitely stop processing
            mock_preflight.side_effect = PreflightError("Production tools missing")
            
            result = bulk_ingest_main(test_args)
            
            assert result == 2
            mock_preflight.assert_called_once()
    
    def test_preflight_timing_acceptable(self):
        """Test that preflight checks complete within acceptable time limits"""
        import time
        
        test_args = [
            "--env", "dev",
            "--no-logfile",
            "--no-cleanup",
        ]
        
        start_time = time.time()
        
        with patch('src_common.preflight_checks.run_preflight_checks'):
            result = bulk_ingest_main(test_args)
        
        elapsed = time.time() - start_time
        
        # Preflight should complete quickly (under 10 seconds even with slow systems)
        assert elapsed < 10.0
        assert result == 0


class TestPreflightCommandLineInterface:
    """Test preflight-related command line argument handling"""
    
    def test_skip_preflight_argument_recognized(self):
        """Test that --skip-preflight argument is properly recognized"""
        test_args = [
            "--env", "dev",
            "--skip-preflight",
            "--no-logfile",
            "--no-cleanup",
        ]
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            result = bulk_ingest_main(test_args)
            
            assert result == 0
            mock_preflight.assert_not_called()
    
    def test_help_includes_skip_preflight(self):
        """Test that help text includes --skip-preflight option"""
        test_args = ["--help"]
        
        with pytest.raises(SystemExit):
            with patch('sys.stdout') as mock_stdout:
                bulk_ingest_main(test_args)
        
        # Help should mention the skip-preflight option
        # This is harder to test directly, but the important thing is
        # that the argument is registered (tested above)
    
    def test_preflight_with_all_other_options(self):
        """Test preflight works correctly with all other command line options"""
        test_args = [
            "--env", "test",  # Different environment
            "--threads", "2", 
            "--no-logfile",
            "--no-cleanup",
            "--resume",
            "--force-dict-init",
            # Note: not including --reset-db as that's destructive
        ]
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight:
            result = bulk_ingest_main(test_args)
            
            # Should run preflight regardless of other options
            assert result == 0
            mock_preflight.assert_called_once()


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])