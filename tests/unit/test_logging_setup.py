"""
Unit Tests for BUG-001 Fixes - Logging Setup Validation
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock

# Add src_common to path for testing
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))

from src_common.logging import setup_logging, get_logger


class TestLoggingSetup:
    """Test cases for logging setup fixes in BUG-001"""
    
    def test_setup_logging_with_logfile(self):
        """Test that setup_logging creates log file when log_file parameter is provided"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file_path = Path(temp_dir) / "test_bulk_ingest.log"
            
            # Setup logging with explicit log file
            logger = setup_logging(log_file=log_file_path)
            
            # Log a test message
            test_logger = get_logger("test_bulk_ingest")
            test_logger.info("Test log message for BUG-001 fix")
            
            # Verify log file was created and contains content
            assert log_file_path.exists(), "Log file should be created"
            assert log_file_path.stat().st_size > 0, "Log file should not be empty"
            
            # Verify log content
            with open(log_file_path, 'r') as f:
                log_content = f.read()
                assert "Test log message for BUG-001 fix" in log_content
                assert "test_bulk_ingest" in log_content
    
    def test_setup_logging_without_logfile(self):
        """Test that setup_logging works without log_file parameter (console only)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup logging without log file (should use console only)
            logger = setup_logging(log_file=None)
            
            # Should not crash and logger should work
            test_logger = get_logger("test_console")
            test_logger.info("Console only message")
            
            # This should work without creating any files in temp_dir
            files_created = list(Path(temp_dir).glob("*"))
            assert len(files_created) == 0, "No log files should be created in temp directory"
    
    def test_setup_logging_creates_parent_directories(self):
        """Test that setup_logging creates parent directories for log file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use nested directory path that doesn't exist yet
            log_file_path = Path(temp_dir) / "logs" / "nested" / "bulk_ingest.log"
            
            # Verify parent directories don't exist initially
            assert not log_file_path.parent.exists()
            
            # Setup logging should create parent directories
            logger = setup_logging(log_file=log_file_path)
            
            # Log a message to ensure file is created
            test_logger = get_logger("test_nested")
            test_logger.info("Test message in nested directory")
            
            # Verify parent directories were created
            assert log_file_path.parent.exists(), "Parent directories should be created"
            assert log_file_path.exists(), "Log file should be created"
    
    def test_bulk_ingest_logging_integration(self):
        """Test the specific logging pattern used in bulk_ingest.py"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate the exact pattern from bulk_ingest.py
            import time
            
            env = "test"
            env_dir = Path(temp_dir) / f"env/{env}"
            env_dir.mkdir(parents=True, exist_ok=True)
            logs_dir = env_dir / "logs"
            logs_dir.mkdir(exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            log_file = logs_dir / f"bulk_ingest_{timestamp}.log"
            
            # This is the fixed pattern from BUG-001
            logger = setup_logging(log_file=log_file)
            
            # Test logging
            bulk_logger = get_logger("bulk_ingest")
            bulk_logger.info(f"Starting 6-pass bulk ingestion - env: {env}")
            bulk_logger.info("Dictionary entries processed successfully")
            bulk_logger.warning("Consistency check: Low chunk-to-dictionary ratio")
            
            # Verify log file exists and has content
            assert log_file.exists(), f"Log file should exist at {log_file}"
            assert log_file.stat().st_size > 0, "Log file should not be empty"
            
            # Verify log content matches expected format
            with open(log_file, 'r') as f:
                log_content = f.read()
                assert "Starting 6-pass bulk ingestion" in log_content
                assert "Dictionary entries processed successfully" in log_content
                assert "Consistency check:" in log_content
                assert "bulk_ingest" in log_content  # Logger name should be included
    
    def test_no_logfile_flag_behavior(self):
        """Test behavior when --no-logfile flag is used (log_file=None)"""
        # This simulates the --no-logfile flag behavior
        log_file = None
        
        # Should work without creating any files
        logger = setup_logging(log_file=log_file)
        
        # Logger should still work for console output
        test_logger = get_logger("test_no_logfile")
        test_logger.info("This should only go to console")
        test_logger.error("Error message for console only")
        
        # This test verifies no exception is thrown and logging works
        assert logger is not None
    
    def test_logging_permissions_and_access(self):
        """Test that log file has appropriate permissions and is accessible"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file_path = Path(temp_dir) / "bulk_ingest_permissions.log"
            
            logger = setup_logging(log_file=log_file_path)
            test_logger = get_logger("test_permissions")
            test_logger.info("Testing file permissions")
            
            # Verify file exists and is readable
            assert log_file_path.exists()
            assert os.access(log_file_path, os.R_OK), "Log file should be readable"
            
            # On Unix-like systems, check that it's writable by owner
            if hasattr(os, 'stat') and hasattr(os.stat(log_file_path), 'st_mode'):
                file_mode = os.stat(log_file_path).st_mode
                # File should be writable by owner (at minimum)
                assert os.access(log_file_path, os.W_OK), "Log file should be writable"


if __name__ == "__main__":
    pytest.main([__file__])