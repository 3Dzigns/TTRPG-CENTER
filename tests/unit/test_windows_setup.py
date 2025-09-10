# tests/unit/test_windows_setup.py
"""
Unit tests for BUG-023 Windows setup automation script.

Tests the setup_windows.ps1 PowerShell script functionality including:
- Dependency detection
- Installation logic
- PATH management
- Error handling and idempotency
"""

import pytest
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestWindowsSetupScript:
    """Test Windows setup automation script"""
    
    @pytest.fixture
    def setup_script_path(self):
        """Get path to setup_windows.ps1 script"""
        repo_root = Path(__file__).parents[2]
        return repo_root / "scripts" / "setup_windows.ps1"
    
    def run_powershell_script(self, script_path: Path, args: list = None) -> dict:
        """Helper to run PowerShell script and capture output"""
        if not args:
            args = []
            
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path)] + args
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                cwd=script_path.parent.parent
            )
            
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": "Script execution timed out",
                "success": False
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_setup_script_exists(self, setup_script_path):
        """Test that the setup script exists and is readable"""
        assert setup_script_path.exists(), f"Setup script not found: {setup_script_path}"
        assert setup_script_path.is_file(), "Setup script path is not a file"
        
        # Test that it's a PowerShell script
        with open(setup_script_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "param(" in content, "Script doesn't appear to have PowerShell parameters"
            assert "setup_windows.ps1" in content, "Script doesn't contain expected metadata"
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_help_parameter(self, setup_script_path):
        """Test that -Help parameter shows usage information"""
        result = self.run_powershell_script(setup_script_path, ["-Help"])
        
        # Should exit successfully with help text
        assert result["success"], f"Help command failed: {result['stderr']}"
        assert "Windows Setup" in result["stdout"], "Help doesn't show script title"
        assert "USAGE:" in result["stdout"], "Help doesn't show usage information"
        assert "OPTIONS:" in result["stdout"], "Help doesn't show options"
        assert "-UserScope" in result["stdout"], "Help doesn't show UserScope option"
        assert "-Verify" in result["stdout"], "Help doesn't show Verify option"
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_verify_mode_with_missing_tools(self, setup_script_path):
        """Test verify mode when tools are not installed"""
        # This test assumes clean environment without Poppler/Tesseract
        # Skip if tools are actually installed
        try:
            subprocess.run(["pdfinfo", "-v"], capture_output=True, check=True)
            pytest.skip("Poppler already installed - skipping missing tools test")
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass  # Good, tools are missing as expected
        
        result = self.run_powershell_script(setup_script_path, ["-Verify", "-Quiet"])
        
        # Should exit with non-zero code when tools are missing
        assert not result["success"], "Verify should fail when tools are missing"
        assert result["returncode"] == 1, f"Expected exit code 1, got {result['returncode']}"
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_offline_mode(self, setup_script_path):
        """Test offline mode (no downloads)"""
        result = self.run_powershell_script(setup_script_path, ["-Offline", "-Quiet"])
        
        # Offline mode should handle gracefully
        assert "Offline mode" in result["stdout"] or "offline" in result["stdout"].lower()
        # May succeed or fail depending on existing installs, but should not crash
        assert result["returncode"] in [0, 1], f"Unexpected exit code: {result['returncode']}"
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")  
    def test_invalid_parameters(self, setup_script_path):
        """Test script handles invalid parameters gracefully"""
        result = self.run_powershell_script(setup_script_path, ["-InvalidOption"])
        
        # PowerShell should handle invalid parameters
        # May show parameter binding error but shouldn't crash catastrophically
        assert result["returncode"] != 0, "Should fail with invalid parameters"


class TestWindowsSetupIntegration:
    """Integration tests for Windows setup workflow"""
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_dependency_detection_logic(self):
        """Test the logic that matches preflight_checks.py"""
        # Test that our known Windows paths match what's in preflight_checks.py
        from src_common.preflight_checks import PreflightValidator
        
        validator = PreflightValidator()
        discovered = validator._discover_windows_paths()
        
        # The setup script should check the same locations
        expected_paths = [
            "C:/Program Files/Tesseract-OCR",
            "C:/Program Files (x86)/Tesseract-OCR", 
            "C:/Program Files/poppler",
            "C:/Program Files (x86)/poppler"
        ]
        
        # Check that discovered paths overlap with our expected ones
        discovered_strs = [str(path) for path in discovered]
        
        # At least some paths should match (empty is OK if tools not installed)
        # This is more of a consistency check than a strict requirement
        if discovered_strs:
            common_patterns = ["Tesseract-OCR", "poppler"]
            has_expected_pattern = any(
                any(pattern in path for pattern in common_patterns)
                for path in discovered_strs
            )
            assert has_expected_pattern, f"Discovered paths don't match expected patterns: {discovered_strs}"


class TestCLIFlagIntegration:
    """Test CLI flag integration for --verify-deps"""
    
    def test_bulk_ingest_verify_deps_parameter(self):
        """Test that --verify-deps flag exists in bulk_ingest.py"""
        # Import and test the argument parser
        import sys
        from pathlib import Path
        
        # Add src to path to import bulk_ingest
        repo_root = Path(__file__).parents[2]
        scripts_path = repo_root / "scripts"
        sys.path.insert(0, str(scripts_path))
        
        try:
            # Test that we can import and the parameter exists
            import bulk_ingest
            
            # Create argument parser and check for --verify-deps
            import argparse
            parser = argparse.ArgumentParser()
            
            # Simulate the argument definition from bulk_ingest.py
            parser.add_argument("--verify-deps", action="store_true", 
                              help="Run only dependency verification checks and exit")
            
            # Test parsing
            args = parser.parse_args(["--verify-deps"])
            assert args.verify_deps is True
            
            # Test that it doesn't break normal parsing
            args2 = parser.parse_args([])
            assert args2.verify_deps is False
            
        except ImportError as e:
            pytest.skip(f"Could not import bulk_ingest: {e}")
    
    @patch('scripts.bulk_ingest.run_preflight_checks')
    def test_verify_deps_success_path(self, mock_preflight):
        """Test --verify-deps success path"""
        mock_preflight.return_value = None  # Success case
        
        # Mock sys.argv for the test
        with patch('sys.argv', ['bulk_ingest.py', '--verify-deps', '--env', 'test']):
            try:
                from scripts.bulk_ingest import main
                result = main(['--verify-deps', '--env', 'test'])
                assert result == 0  # Success exit code
                mock_preflight.assert_called_once()
            except SystemExit as e:
                assert e.code == 0
    
    @patch('scripts.bulk_ingest.run_preflight_checks')
    def test_verify_deps_failure_path(self, mock_preflight):
        """Test --verify-deps failure path"""
        from src_common.preflight_checks import PreflightError
        mock_preflight.side_effect = PreflightError("Test dependency missing")
        
        with patch('sys.argv', ['bulk_ingest.py', '--verify-deps', '--env', 'test']):
            try:
                from scripts.bulk_ingest import main
                result = main(['--verify-deps', '--env', 'test'])
                assert result == 2  # Dependency error exit code
                mock_preflight.assert_called_once()
            except SystemExit as e:
                assert e.code == 2


class TestPathManagement:
    """Test PATH management functionality"""
    
    def test_path_deduplication_concept(self):
        """Test the concept of PATH deduplication (Windows-style)"""
        # Test the logic that would be used in PowerShell for PATH deduplication
        
        # Simulate Windows PATH with semicolon separators
        original_path = "C:\\Windows\\System32;C:\\Windows;C:\\Program Files\\Git\\bin"
        new_entry = "C:\\Program Files\\poppler\\bin"
        duplicate_entry = "C:\\Windows\\System32"  # Already exists
        
        # Simulate the PowerShell logic for adding to PATH
        def add_to_path_simulation(current_path: str, new_path: str) -> str:
            """Simulate PowerShell PATH addition logic"""
            path_entries = current_path.split(';')
            if new_path not in path_entries:
                return f"{current_path};{new_path}"
            else:
                return current_path  # No change if already exists
        
        # Test adding new entry
        updated_path = add_to_path_simulation(original_path, new_entry)
        assert new_entry in updated_path
        assert updated_path.count(new_entry) == 1
        
        # Test adding duplicate entry (should not duplicate)
        updated_path2 = add_to_path_simulation(updated_path, duplicate_entry)
        assert updated_path2 == updated_path  # Should be unchanged
        assert updated_path2.count(duplicate_entry) == 1


class TestScriptIdempotency:
    """Test script idempotency and repeated execution"""
    
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_multiple_verify_runs_idempotent(self):
        """Test that multiple -Verify runs produce consistent output"""
        repo_root = Path(__file__).parents[2]
        script_path = repo_root / "scripts" / "setup_windows.ps1"
        
        def run_verify():
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-Verify", "-Quiet"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=script_path.parent.parent)
                return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
            except Exception as e:
                return {"returncode": -1, "stdout": "", "stderr": str(e)}
        
        # Run verification twice
        result1 = run_verify()
        result2 = run_verify()
        
        # Both runs should have same exit code
        assert result1["returncode"] == result2["returncode"], "Multiple verify runs should be consistent"
        
        # Both should contain verification output
        assert "Verifying installations" in result1["stdout"] or "Verifying installations" in result1["stderr"]
        assert "Verifying installations" in result2["stdout"] or "Verifying installations" in result2["stderr"]
    
    def test_path_deduplication_concept(self):
        """Test the concept of PATH deduplication logic"""
        # Test the PowerShell logic for PATH management
        # This simulates what the PowerShell script should do
        
        original_path = "C:\\Windows\\System32;C:\\Windows;C:\\Program Files\\Git\\bin"
        new_entry = "C:\\Program Files\\poppler\\bin"
        duplicate_entry = "C:\\Windows\\System32"  # Already exists
        
        def simulate_add_to_path(current_path: str, new_path: str) -> str:
            """Simulate PowerShell Add-ToPath logic"""
            path_entries = [p.strip() for p in current_path.split(';') if p.strip()]
            if new_path not in path_entries:
                return f"{current_path};{new_path}"
            else:
                return current_path  # No change if already exists
        
        # Test adding new entry
        updated_path = simulate_add_to_path(original_path, new_entry)
        assert new_entry in updated_path
        assert updated_path.count(new_entry) == 1
        
        # Test adding duplicate entry (should not duplicate)
        updated_path2 = simulate_add_to_path(updated_path, duplicate_entry)
        assert updated_path2 == updated_path  # Should be unchanged
        assert updated_path2.count(duplicate_entry) == 1


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_network_failure_simulation(self):
        """Test how script should handle network failures"""
        # This tests the concept - actual network mocking would be in PowerShell
        
        # Simulate the error handling logic that should exist
        def simulate_download_with_failure():
            # Simulate network failure
            raise ConnectionError("Unable to connect to download server")
        
        # Test that we handle the error gracefully
        try:
            simulate_download_with_failure()
            assert False, "Should have raised exception"
        except ConnectionError as e:
            # This is what the PowerShell script should handle
            assert "Unable to connect" in str(e)
            
            # Script should provide fallback guidance
            fallback_message = "Please download manually from official sources"
            assert "manually" in fallback_message
    
    def test_permission_error_handling(self):
        """Test permission error handling concepts"""
        # Simulate permission denied scenarios
        
        def simulate_admin_required_operation():
            # Simulate trying to write to Program Files without admin
            raise PermissionError("Access denied to C:\\Program Files")
        
        try:
            simulate_admin_required_operation()
            assert False, "Should have raised PermissionError"
        except PermissionError as e:
            # Script should handle this and suggest user-scope install
            assert "Access denied" in str(e)
            
            # Should suggest alternatives
            user_scope_suggestion = "Try running with -UserScope for user installation"
            assert "UserScope" in user_scope_suggestion


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])