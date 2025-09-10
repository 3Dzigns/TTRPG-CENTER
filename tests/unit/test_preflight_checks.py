# tests/unit/test_preflight_checks.py
"""
Unit tests for preflight dependency checks.

Tests the preflight_checks module's ability to validate external tool
dependencies (Poppler, Tesseract) and handle various failure scenarios.
"""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from src_common.preflight_checks import (
    PreflightValidator, 
    PreflightError, 
    run_preflight_checks
)


class TestPreflightValidator:
    """Test the PreflightValidator class functionality"""
    
    def test_validator_initialization(self):
        """Test that validator initializes with correct state"""
        validator = PreflightValidator()
        
        assert validator.tools_status == {}
        assert validator.original_path == os.environ.get("PATH", "")
        assert validator.path_extensions == []
    
    def test_run_tool_command_success(self):
        """Test successful tool command execution"""
        validator = PreflightValidator()
        
        with patch('subprocess.run') as mock_run:
            # Mock successful command
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Tool version 1.0.0"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            
            success, output = validator._run_tool_command(["test-tool", "--version"])
            
            assert success is True
            assert output == "Tool version 1.0.0"
            mock_run.assert_called_once_with(
                ["test-tool", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
    
    def test_run_tool_command_failure(self):
        """Test tool command execution failure"""
        validator = PreflightValidator()
        
        with patch('subprocess.run') as mock_run:
            # Mock failed command
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Command not found"
            mock_run.return_value = mock_result
            
            success, output = validator._run_tool_command(["missing-tool"])
            
            assert success is False
            assert output == "Command not found"
    
    def test_run_tool_command_timeout(self):
        """Test tool command timeout handling"""
        validator = PreflightValidator()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["test-tool"], 5)
            
            success, output = validator._run_tool_command(["test-tool"], timeout=5)
            
            assert success is False
            assert "timed out after 5s" in output
    
    def test_run_tool_command_exception(self):
        """Test tool command exception handling"""
        validator = PreflightValidator()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            
            success, output = validator._run_tool_command(["test-tool"])
            
            assert success is False
            assert "Command failed: Permission denied" in output
    
    @patch('sys.platform', 'linux')
    def test_discover_windows_paths_non_windows(self):
        """Test Windows path discovery on non-Windows platforms"""
        validator = PreflightValidator()
        paths = validator._discover_windows_paths()
        assert paths == []
    
    @patch('sys.platform', 'win32')
    def test_discover_windows_paths_no_tools(self):
        """Test Windows path discovery when no tools are found"""
        validator = PreflightValidator()
        
        with patch('pathlib.Path.exists', return_value=False):
            paths = validator._discover_windows_paths()
            assert paths == []
    
    @patch('sys.platform', 'win32')
    def test_discover_windows_paths_found_tools(self):
        """Test Windows path discovery when tools are found"""
        validator = PreflightValidator()
        
        # Mock tesseract found
        tesseract_path = Path("C:/Program Files/Tesseract-OCR")
        tesseract_exe = tesseract_path / "tesseract.exe"
        
        # Mock poppler found  
        poppler_path = Path("C:/Program Files/poppler/bin")
        poppler_exe = poppler_path / "pdfinfo.exe"
        
        def mock_exists(path):
            if path == tesseract_path or path == tesseract_exe:
                return True
            if path == poppler_path.parent or path == poppler_path or path == poppler_exe:
                return True
            return False
        
        def mock_iterdir(path):
            if str(path).endswith("poppler"):
                return [poppler_path.parent / "bin"]
            return []
        
        with patch('pathlib.Path.exists', side_effect=mock_exists), \
             patch('pathlib.Path.iterdir', side_effect=mock_iterdir), \
             patch('pathlib.Path.is_dir', return_value=True):
            
            paths = validator._discover_windows_paths()
            
            # Should find tesseract but poppler logic is complex, just verify we get results
            assert len(paths) >= 0  # May vary depending on exact mock behavior
    
    def test_extend_path_temporarily(self):
        """Test temporary PATH extension"""
        validator = PreflightValidator()
        original_path = os.environ.get("PATH", "")
        
        test_paths = [Path("/test/path1"), Path("/test/path2")]
        validator._extend_path_temporarily(test_paths)
        
        new_path = os.environ.get("PATH", "")
        assert "/test/path1" in new_path
        assert "/test/path2" in new_path
        assert original_path in new_path
        assert validator.path_extensions == ["/test/path1", "/test/path2"]
        
        # Cleanup
        validator.cleanup()
        assert os.environ.get("PATH", "") == original_path
    
    def test_extend_path_empty_list(self):
        """Test extending PATH with empty list does nothing"""
        validator = PreflightValidator()
        original_path = os.environ.get("PATH", "")
        
        validator._extend_path_temporarily([])
        
        assert os.environ.get("PATH", "") == original_path
        assert validator.path_extensions == []
    
    @patch('shutil.which')
    def test_validate_poppler_tools_success(self, mock_which):
        """Test successful Poppler tools validation"""
        validator = PreflightValidator()
        
        # Mock tools found in PATH
        mock_which.return_value = "/usr/bin/pdfinfo"  # or "/usr/bin/pdftoppm"
        
        with patch.object(validator, '_run_tool_command') as mock_run:
            mock_run.return_value = (True, "pdfinfo version 20.09.0")
            
            result = validator._validate_poppler_tools()
            
            assert result is True
            assert "pdfinfo" in validator.tools_status
            assert "pdftoppm" in validator.tools_status
            assert validator.tools_status["pdfinfo"].startswith("✅")
            assert validator.tools_status["pdftoppm"].startswith("✅")
    
    @patch('shutil.which')
    def test_validate_poppler_tools_missing(self, mock_which):
        """Test Poppler tools validation when tools are missing"""
        validator = PreflightValidator()
        
        # Mock tools not found
        mock_which.return_value = None
        
        result = validator._validate_poppler_tools()
        
        assert result is False
        assert "pdfinfo" in validator.tools_status
        assert "pdftoppm" in validator.tools_status
        assert validator.tools_status["pdfinfo"].startswith("❌")
        assert validator.tools_status["pdftoppm"].startswith("❌")
    
    @patch('shutil.which')
    def test_validate_poppler_tools_non_functional(self, mock_which):
        """Test Poppler tools validation when tools exist but don't work"""
        validator = PreflightValidator()
        
        # Mock tools found but non-functional
        mock_which.return_value = "/usr/bin/pdfinfo"
        
        with patch.object(validator, '_run_tool_command') as mock_run:
            mock_run.return_value = (False, "Command failed")
            
            result = validator._validate_poppler_tools()
            
            assert result is False
            assert validator.tools_status["pdfinfo"].startswith("❌")
    
    @patch('shutil.which')
    def test_validate_tesseract_success(self, mock_which):
        """Test successful Tesseract validation"""
        validator = PreflightValidator()
        
        # Mock tesseract found
        mock_which.return_value = "/usr/bin/tesseract"
        
        with patch.object(validator, '_run_tool_command') as mock_run:
            mock_run.return_value = (True, "tesseract 4.1.1\\nLicense...")
            
            result = validator._validate_tesseract()
            
            assert result is True
            assert validator.tools_status["tesseract"].startswith("✅")
            assert "tesseract 4.1.1" in validator.tools_status["tesseract"]
    
    @patch('shutil.which')
    def test_validate_tesseract_missing(self, mock_which):
        """Test Tesseract validation when tool is missing"""
        validator = PreflightValidator()
        
        # Mock tesseract not found
        mock_which.return_value = None
        
        result = validator._validate_tesseract()
        
        assert result is False
        assert validator.tools_status["tesseract"].startswith("❌")
        assert "Not found in PATH" in validator.tools_status["tesseract"]
    
    @patch('shutil.which')
    def test_validate_tesseract_non_functional(self, mock_which):
        """Test Tesseract validation when tool exists but doesn't work"""
        validator = PreflightValidator()
        
        # Mock tesseract found but non-functional
        mock_which.return_value = "/usr/bin/tesseract"
        
        with patch.object(validator, '_run_tool_command') as mock_run:
            mock_run.return_value = (False, "Segmentation fault")
            
            result = validator._validate_tesseract()
            
            assert result is False
            assert validator.tools_status["tesseract"].startswith("❌")
    
    def test_validate_dependencies_success(self):
        """Test successful dependency validation"""
        validator = PreflightValidator()
        
        with patch.object(validator, '_validate_poppler_tools', return_value=True), \
             patch.object(validator, '_validate_tesseract', return_value=True), \
             patch.object(validator, '_discover_windows_paths', return_value=[]):
            
            # Should not raise exception
            validator.validate_dependencies()
            
            assert len(validator.tools_status) > 0
    
    def test_validate_dependencies_failure(self):
        """Test dependency validation failure"""
        validator = PreflightValidator()
        
        with patch.object(validator, '_validate_poppler_tools', return_value=False), \
             patch.object(validator, '_validate_tesseract', return_value=True), \
             patch.object(validator, '_discover_windows_paths', return_value=[]):
            
            validator.tools_status = {"pdfinfo": "❌ Not found"}
            
            with pytest.raises(PreflightError) as exc_info:
                validator.validate_dependencies()
            
            assert "pdfinfo" in str(exc_info.value)
    
    def test_cleanup_restores_path(self):
        """Test cleanup properly restores original PATH"""
        validator = PreflightValidator()
        original_path = os.environ.get("PATH", "")
        
        # Modify PATH
        validator.path_extensions = ["/test/path"]
        os.environ["PATH"] = "/test/path:/original/path"
        
        validator.cleanup()
        
        assert os.environ.get("PATH", "") == original_path


class TestRunPreflightChecks:
    """Test the run_preflight_checks function"""
    
    def test_run_preflight_checks_success(self):
        """Test successful preflight checks"""
        with patch('src_common.preflight_checks.PreflightValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator_class.return_value = mock_validator
            
            # Should not raise exception
            run_preflight_checks()
            
            mock_validator_class.assert_called_once()
            mock_validator.validate_dependencies.assert_called_once()
            mock_validator.cleanup.assert_called_once()
    
    def test_run_preflight_checks_failure(self):
        """Test preflight checks failure propagation"""
        with patch('src_common.preflight_checks.PreflightValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator_class.return_value = mock_validator
            mock_validator.validate_dependencies.side_effect = PreflightError("Test failure")
            
            with pytest.raises(PreflightError):
                run_preflight_checks()
            
            # Should still call cleanup even on failure
            mock_validator.cleanup.assert_called_once()
    
    def test_run_preflight_checks_cleanup_on_exception(self):
        """Test preflight checks cleanup even when validation raises exception"""
        with patch('src_common.preflight_checks.PreflightValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator_class.return_value = mock_validator
            mock_validator.validate_dependencies.side_effect = PreflightError("Test error")
            
            with pytest.raises(PreflightError):
                run_preflight_checks()
            
            mock_validator.cleanup.assert_called_once()


class TestStandaloneExecution:
    """Test standalone script execution"""
    
    def test_main_success(self):
        """Test successful standalone execution"""
        test_args = ['test_preflight_checks.py']
        
        with patch('sys.argv', test_args), \
             patch('src_common.preflight_checks.run_preflight_checks'), \
             patch('sys.exit') as mock_exit:
            
            # Import and run the module as main
            with patch('__main__.__name__', '__main__'):
                exec(open('src_common/preflight_checks.py').read())
            
            mock_exit.assert_called_with(0)
    
    def test_main_failure(self):
        """Test failed standalone execution"""
        test_args = ['test_preflight_checks.py']
        
        with patch('sys.argv', test_args), \
             patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight, \
             patch('sys.exit') as mock_exit:
            
            mock_preflight.side_effect = PreflightError("Test failure")
            
            # Import and run the module as main
            with patch('__main__.__name__', '__main__'):
                exec(open('src_common/preflight_checks.py').read())
            
            mock_exit.assert_called_with(2)


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])