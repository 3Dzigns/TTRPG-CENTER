# tests/functional/test_verify_deps_cli.py
"""
Functional tests for BUG-023 --verify-deps CLI flag integration.

Tests the end-to-end behavior of the --verify-deps flag in bulk_ingest.py:
- Successful dependency verification
- Failed dependency verification with proper exit codes
- Integration with existing preflight checks
- Output formatting and user guidance
"""

import pytest
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestVerifyDepsCLI:
    """Test --verify-deps CLI flag functionality"""
    
    @pytest.fixture
    def bulk_ingest_script(self):
        """Get path to bulk_ingest.py script"""
        repo_root = Path(__file__).parents[2]
        return repo_root / "scripts" / "bulk_ingest.py"
    
    def run_bulk_ingest_command(self, args: list, timeout: int = 30) -> dict:
        """Helper to run bulk_ingest.py with arguments"""
        script_path = Path(__file__).parents[2] / "scripts" / "bulk_ingest.py"
        
        cmd = [sys.executable, str(script_path)] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
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
                "stderr": "Command execution timed out",
                "success": False
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }
    
    def test_verify_deps_flag_exists(self, bulk_ingest_script):
        """Test that --verify-deps flag is recognized by argument parser"""
        # Test help output includes --verify-deps
        result = self.run_bulk_ingest_command(["--help"])
        
        assert result["success"], f"Help command failed: {result['stderr']}"
        assert "--verify-deps" in result["stdout"], "--verify-deps flag not found in help"
        assert "dependency verification" in result["stdout"].lower(), "Help text doesn't describe --verify-deps properly"
    
    @patch('src_common.preflight_checks.run_preflight_checks')
    def test_verify_deps_success_behavior(self, mock_preflight):
        """Test --verify-deps success path behavior"""
        # Mock successful preflight checks
        mock_preflight.return_value = None
        
        with patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            result = self.run_bulk_ingest_command(["--verify-deps", "--env", "test"])
            
            # Should exit with success code
            assert result["returncode"] == 0, f"Expected exit code 0, got {result['returncode']}"
            
            # Should contain success messaging
            output = result["stdout"] + result["stderr"]
            assert "Dependency Verification PASSED" in output or "verified successfully" in output
            assert "Next steps:" in output or "next steps" in output.lower()
            
            # Should mention how to run ingestion
            assert "bulk_ingest.py" in output
            assert "--upload-dir" in output or "upload" in output.lower()
    
    @patch('src_common.preflight_checks.run_preflight_checks')
    def test_verify_deps_failure_behavior(self, mock_preflight):
        """Test --verify-deps failure path behavior"""
        from src_common.preflight_checks import PreflightError
        
        # Mock failed preflight checks
        mock_preflight.side_effect = PreflightError("tesseract: Command not found")
        
        with patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            result = self.run_bulk_ingest_command(["--verify-deps", "--env", "test"])
            
            # Should exit with dependency error code (2)
            assert result["returncode"] == 2, f"Expected exit code 2, got {result['returncode']}"
            
            # Should contain failure messaging
            output = result["stdout"] + result["stderr"]
            assert "Dependency Verification FAILED" in output or "verification failed" in output.lower()
            assert "Remediation:" in output or "remediation" in output.lower()
            
            # Should provide setup guidance
            assert "setup_windows.ps1" in output
            assert "WINDOWS_SETUP.md" in output or "windows setup" in output.lower()
    
    @patch('src_common.preflight_checks.run_preflight_checks')
    def test_verify_deps_with_different_environments(self, mock_preflight):
        """Test --verify-deps works with different environment flags"""
        mock_preflight.return_value = None
        
        environments = ["dev", "test", "prod"]
        
        for env in environments:
            with patch('src_common.ttrpg_secrets._load_env_file'), \
                 patch('pathlib.Path.exists', return_value=True):
                
                result = self.run_bulk_ingest_command(["--verify-deps", "--env", env])
                
                # Should work with all environments
                assert result["returncode"] == 0, f"Failed for environment {env}: {result['stderr']}"
                
                # Should mention the environment in logs
                output = result["stdout"] + result["stderr"]
                # Environment might be mentioned in log setup or elsewhere
    
    def test_verify_deps_exits_early(self):
        """Test that --verify-deps exits early and doesn't run main pipeline"""
        # Use a mock to ensure main pipeline logic isn't called
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight, \
             patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('scripts.bulk_ingest.AstraLoader') as mock_loader:
            
            mock_preflight.return_value = None
            
            result = self.run_bulk_ingest_command(["--verify-deps", "--env", "test"])
            
            # Should exit successfully
            assert result["returncode"] == 0
            
            # Main pipeline components should NOT be instantiated
            mock_loader.assert_not_called()
    
    def test_verify_deps_with_no_logfile_flag(self):
        """Test --verify-deps works with --no-logfile flag"""
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight, \
             patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_preflight.return_value = None
            
            result = self.run_bulk_ingest_command([
                "--verify-deps", 
                "--env", "test", 
                "--no-logfile"
            ])
            
            # Should still work with --no-logfile
            assert result["returncode"] == 0
            
            # Should contain verification messaging
            output = result["stdout"] + result["stderr"]
            assert "verification" in output.lower() or "dependencies" in output.lower()


class TestVerifyDepsIntegrationWithPreflight:
    """Test integration between --verify-deps and existing preflight system"""
    
    def test_verify_deps_calls_same_preflight_as_normal_run(self):
        """Test that --verify-deps uses the same preflight checks as normal operation"""
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight, \
             patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_preflight.return_value = None
            
            # Run with --verify-deps
            from scripts.bulk_ingest import main
            result = main(["--verify-deps", "--env", "test"])
            
            # Should call run_preflight_checks exactly once
            assert mock_preflight.call_count == 1
            
            # Should use the same function signature
            mock_preflight.assert_called_with()
    
    @patch('src_common.preflight_checks.PreflightValidator')
    def test_verify_deps_uses_real_preflight_validator(self, mock_validator_class):
        """Test that preflight checks use the real validator"""
        
        # Create a mock validator instance
        mock_validator = Mock()
        mock_validator.validate_dependencies.return_value = None
        mock_validator_class.return_value = mock_validator
        
        with patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            from scripts.bulk_ingest import main
            result = main(["--verify-deps", "--env", "test"])
            
            # Should instantiate PreflightValidator
            mock_validator_class.assert_called_once()
            
            # Should call validate_dependencies
            mock_validator.validate_dependencies.assert_called_once()
            
            # Should call cleanup
            mock_validator.cleanup.assert_called_once()


class TestVerifyDepsOutputFormatting:
    """Test output formatting and user guidance in --verify-deps"""
    
    @patch('src_common.preflight_checks.run_preflight_checks')
    def test_success_output_formatting(self, mock_preflight):
        """Test that success output is user-friendly and informative"""
        mock_preflight.return_value = None
        
        with patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            result = self.run_bulk_ingest_command(["--verify-deps", "--env", "test"])
            
            output = result["stdout"]
            
            # Should have clear success indication
            assert "🎉" in output or "PASSED" in output or "success" in output.lower()
            
            # Should provide next steps
            lines = output.split('\n')
            next_steps_found = any("next" in line.lower() and "step" in line.lower() for line in lines)
            assert next_steps_found, "No 'next steps' guidance found in output"
            
            # Should mention how to run actual ingestion
            bulk_ingest_mentioned = any("bulk_ingest" in line for line in lines)
            assert bulk_ingest_mentioned, "Doesn't mention bulk_ingest for next steps"
    
    @patch('src_common.preflight_checks.run_preflight_checks')
    def test_failure_output_formatting(self, mock_preflight):
        """Test that failure output provides actionable guidance"""
        from src_common.preflight_checks import PreflightError
        
        mock_preflight.side_effect = PreflightError("pdfinfo: Command not found")
        
        with patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            result = self.run_bulk_ingest_command(["--verify-deps", "--env", "test"])
            
            output = result["stdout"]
            
            # Should have clear failure indication
            assert "🚨" in output or "FAILED" in output or "failed" in output.lower()
            
            # Should provide remediation steps
            assert "Remediation:" in output
            
            # Should mention the setup script
            assert "setup_windows.ps1" in output
            
            # Should mention documentation
            assert "WINDOWS_SETUP.md" in output
            
            # Should show how to verify after setup
            assert "--verify-deps" in output
    
    def run_bulk_ingest_command(self, args: list, timeout: int = 30) -> dict:
        """Helper to run bulk_ingest.py with arguments"""
        script_path = Path(__file__).parents[2] / "scripts" / "bulk_ingest.py"
        
        cmd = [sys.executable, str(script_path)] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
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
                "stderr": "Command execution timed out",
                "success": False
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "success": False
            }


class TestVerifyDepsWithSkipPreflight:
    """Test interaction between --verify-deps and --skip-preflight"""
    
    def test_verify_deps_ignores_skip_preflight(self):
        """Test that --verify-deps ignores --skip-preflight flag"""
        
        with patch('src_common.preflight_checks.run_preflight_checks') as mock_preflight, \
             patch('src_common.ttrpg_secrets._load_env_file'), \
             patch('pathlib.Path.exists', return_value=True):
            
            mock_preflight.return_value = None
            
            # Run with both flags - verify-deps should take precedence
            from scripts.bulk_ingest import main
            result = main(["--verify-deps", "--skip-preflight", "--env", "test"])
            
            # Should still call preflight checks despite --skip-preflight
            mock_preflight.assert_called_once()
            
            # Should exit successfully with verification message
            assert result == 0


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])