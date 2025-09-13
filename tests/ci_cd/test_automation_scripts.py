"""
Automation Scripts Testing

Tests for PowerShell automation scripts used in the CI/CD pipeline.
These tests validate script functionality, error handling, and integration.
"""

import pytest
import os
import subprocess
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open


class TestVersionScript:
    """Test version.ps1 script functionality."""
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_version_get_command(self):
        """Test version get command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/version.ps1", "get"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Version get failed: {result.stderr}"
        version_output = result.stdout.strip()
        assert len(version_output) > 0, "Version get should return a version"
        
        # Validate version format
        import re
        assert re.match(r'^\d+\.\d+\.\d+$', version_output), f"Invalid version format: {version_output}"
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_version_validate_command(self):
        """Test version validate command."""
        # Test valid version
        result = subprocess.run(
            ["powershell", "-File", "scripts/version.ps1", "validate", "-Version", "1.2.3"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Version validation failed: {result.stderr}"
        assert "valid" in result.stdout.lower(), "Should indicate version is valid"
        
        # Test invalid version
        result = subprocess.run(
            ["powershell", "-File", "scripts/version.ps1", "validate", "-Version", "invalid"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 1, "Should fail for invalid version"
        assert "invalid" in result.stdout.lower(), "Should indicate version is invalid"
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_version_help_command(self):
        """Test version help command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/version.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Version help failed: {result.stderr}"
        help_output = result.stdout
        assert "USAGE:" in help_output, "Help should contain usage information"
        assert "EXAMPLES:" in help_output, "Help should contain examples"
    
    def test_version_script_structure(self):
        """Test version script structure and functions."""
        script_path = Path("scripts/version.ps1")
        content = script_path.read_text()
        
        # Check required functions
        required_functions = [
            "Show-Help",
            "Get-CurrentVersion", 
            "Test-VersionFormat",
            "Set-Version",
            "Invoke-BumpVersion"
        ]
        
        for function in required_functions:
            assert f"function {function}" in content, f"Missing function: {function}"
        
        # Check parameter validation
        assert "ValidateSet" in content, "Should have parameter validation"
        assert "ErrorActionPreference" in content, "Should set error handling"


class TestReleaseScript:
    """Test release.ps1 script functionality."""
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_release_help_command(self):
        """Test release help command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/release.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Release help failed: {result.stderr}"
        help_output = result.stdout
        assert "USAGE:" in help_output, "Help should contain usage information"
        assert "BumpType" in help_output, "Help should document BumpType parameter"
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_release_dry_run(self):
        """Test release dry run mode."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/release.ps1", "-DryRun"],
            capture_output=True, text=True, cwd="."
        )
        
        # Dry run should succeed even without Docker
        assert "DRY RUN" in result.stdout, "Should indicate dry run mode"
        assert "would" in result.stdout.lower(), "Should indicate simulated actions"
    
    def test_release_script_structure(self):
        """Test release script structure and safety features."""
        script_path = Path("scripts/release.ps1")
        content = script_path.read_text()
        
        # Check required functions
        required_functions = [
            "Show-Help",
            "Test-Prerequisites",
            "Get-ReleaseVersion",
            "New-ReleaseTag",
            "Invoke-ImageBuild"
        ]
        
        for function in required_functions:
            assert f"function {function}" in content, f"Missing function: {function}"
        
        # Check safety features
        assert "DryRun" in content, "Should support dry run mode"
        assert "ErrorActionPreference" in content, "Should set error handling"
        assert "git status" in content, "Should check git status"


class TestPromoteScript:
    """Test promote.ps1 script functionality."""
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_promote_help_command(self):
        """Test promote help command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/promote.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Promote help failed: {result.stderr}"
        help_output = result.stdout
        assert "USAGE:" in help_output, "Help should contain usage information"
        assert "PromotionType" in help_output, "Help should document PromotionType parameter"
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_promote_parameter_validation(self):
        """Test promote script parameter validation."""
        # Test missing required parameters
        result = subprocess.run(
            ["powershell", "-File", "scripts/promote.ps1"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode != 0, "Should fail without required parameters"
        
        # Test invalid promotion type
        result = subprocess.run(
            ["powershell", "-File", "scripts/promote.ps1", "-PromotionType", "invalid", "-Version", "1.0.0"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode != 0, "Should fail with invalid promotion type"
    
    def test_promote_script_approval_logic(self):
        """Test promote script approval and validation logic."""
        script_path = Path("scripts/promote.ps1")
        content = script_path.read_text()
        
        # Check approval functions
        assert "Request-PromotionApproval" in content, "Should have approval request function"
        assert "Test-PromotionPrerequisites" in content, "Should validate prerequisites"
        assert "Test-SourceEnvironmentHealth" in content, "Should check source environment"
        
        # Check safety features
        assert "Read-Host" in content, "Should prompt for user confirmation"
        assert "DryRun" in content, "Should support dry run mode"


class TestRollbackScript:
    """Test rollback.ps1 script functionality."""
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_rollback_help_command(self):
        """Test rollback help command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/rollback.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Rollback help failed: {result.stderr}"
        help_output = result.stdout
        assert "USAGE:" in help_output, "Help should contain usage information"
        assert "Environment" in help_output, "Help should document Environment parameter"
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_rollback_parameter_validation(self):
        """Test rollback script parameter validation."""
        # Test missing required parameters
        result = subprocess.run(
            ["powershell", "-File", "scripts/rollback.ps1"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode != 0, "Should fail without required parameters"
    
    def test_rollback_script_safety_features(self):
        """Test rollback script safety and confirmation features."""
        script_path = Path("scripts/rollback.ps1")
        content = script_path.read_text()
        
        # Check safety functions
        assert "Confirm-RollbackOperation" in content, "Should have confirmation function"
        assert "New-DeploymentBackup" in content, "Should backup current state"
        assert "Test-PostRollbackHealth" in content, "Should validate after rollback"
        
        # Check confirmation logic
        assert "WARNING" in content, "Should display warnings"
        assert "Force" in content, "Should have force option for emergencies"


class TestQualityGateScript:
    """Test quality-gate.ps1 script functionality."""
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_quality_gate_help_command(self):
        """Test quality gate help command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/quality-gate.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Quality gate help failed: {result.stderr}"
        help_output = result.stdout
        assert "USAGE:" in help_output, "Help should contain usage information"
        assert "Environment" in help_output, "Help should document Environment parameter"
    
    def test_quality_gate_thresholds_configuration(self):
        """Test quality gate thresholds configuration."""
        script_path = Path("scripts/quality-gate.ps1")
        content = script_path.read_text()
        
        # Check threshold definitions
        assert "QualityThresholds" in content, "Should define quality thresholds"
        assert "test_coverage_min" in content, "Should define minimum test coverage"
        assert "security_critical_max" in content, "Should define max critical issues"
        assert "performance_response_max" in content, "Should define max response time"
        
        # Check environment-specific thresholds
        assert '"dev"' in content, "Should have DEV environment thresholds"
        assert '"test"' in content, "Should have TEST environment thresholds"
        assert '"prod"' in content, "Should have PROD environment thresholds"
    
    def test_quality_gate_validation_functions(self):
        """Test quality gate validation functions."""
        script_path = Path("scripts/quality-gate.ps1")
        content = script_path.read_text()
        
        # Check validation functions
        required_functions = [
            "Test-CodeQuality",
            "Test-SecurityCompliance", 
            "Test-FunctionalCompliance",
            "Test-PerformanceCompliance",
            "Test-OperationalCompliance"
        ]
        
        for function in required_functions:
            assert f"function {function}" in content, f"Missing validation function: {function}"


class TestSecurityScanScript:
    """Test security-scan.ps1 script functionality."""
    
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_security_scan_help_command(self):
        """Test security scan help command."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/security-scan.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Security scan help failed: {result.stderr}"
        help_output = result.stdout
        assert "USAGE:" in help_output, "Help should contain usage information"
        assert "ScanType" in help_output, "Help should document ScanType parameter"
    
    def test_security_scan_tool_integration(self):
        """Test security scan tool integration."""
        script_path = Path("scripts/security-scan.ps1")
        content = script_path.read_text()
        
        # Check tool integration functions
        required_functions = [
            "Test-ScanningTools",
            "Install-SecurityTools",
            "Invoke-CodeScan",
            "Invoke-DependencyScan",
            "Invoke-ContainerScan"
        ]
        
        for function in required_functions:
            assert f"function {function}" in content, f"Missing tool function: {function}"
        
        # Check tool references
        assert "bandit" in content.lower(), "Should reference Bandit tool"
        assert "safety" in content.lower(), "Should reference Safety tool"
        assert "trivy" in content.lower(), "Should reference Trivy tool"
    
    def test_security_scan_output_formats(self):
        """Test security scan output format support."""
        script_path = Path("scripts/security-scan.ps1")
        content = script_path.read_text()
        
        # Check output format support
        assert "json" in content.lower(), "Should support JSON output"
        assert "sarif" in content.lower(), "Should support SARIF output"
        assert "OutputFormat" in content, "Should have output format parameter"


class TestScriptErrorHandling:
    """Test error handling across all automation scripts."""
    
    def test_all_scripts_have_error_handling(self):
        """Test that all scripts have proper error handling."""
        script_paths = [
            "scripts/version.ps1",
            "scripts/release.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1",
            "scripts/security-scan.ps1"
        ]
        
        for script_path in script_paths:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                
                # Check error handling configuration
                assert "ErrorActionPreference" in content, f"Script {script_path} must set error handling"
                assert '"Stop"' in content, f"Script {script_path} should stop on errors"
                
                # Check try/catch blocks
                has_try_catch = "try {" in content and "catch {" in content
                has_error_handling = "$LASTEXITCODE" in content or "throw" in content
                
                assert has_try_catch or has_error_handling, f"Script {script_path} must have error handling"
    
    def test_scripts_have_exit_codes(self):
        """Test that scripts properly set exit codes."""
        script_paths = [
            "scripts/release.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1"
        ]
        
        for script_path in script_paths:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                
                # Check for explicit exit codes
                assert "exit 0" in content or "exit 1" in content, f"Script {script_path} should set exit codes"


class TestScriptIntegration:
    """Test integration between automation scripts."""
    
    def test_script_cross_references(self):
        """Test that scripts properly reference each other."""
        # Test that promote script references deploy script
        promote_script = Path("scripts/promote.ps1")
        if promote_script.exists():
            content = promote_script.read_text()
            assert "deploy.ps1" in content, "Promote script should reference deploy script"
        
        # Test that rollback script references deploy script
        rollback_script = Path("scripts/rollback.ps1")
        if rollback_script.exists():
            content = rollback_script.read_text()
            assert "deploy.ps1" in content, "Rollback script should reference deploy script"
    
    def test_script_parameter_consistency(self):
        """Test parameter consistency across scripts."""
        scripts_with_environment = [
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1"
        ]
        
        for script_path in scripts_with_environment:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                
                # Check environment parameter validation
                assert 'ValidateSet("dev", "test"' in content or 'ValidateSet("dev", "test", "prod"' in content, \
                    f"Script {script_path} should validate environment parameter"
    
    def test_script_registry_configuration(self):
        """Test that scripts use consistent registry configuration."""
        scripts_with_registry = [
            "scripts/release.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1"
        ]
        
        registry_values = set()
        
        for script_path in scripts_with_registry:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                
                # Extract registry default values
                if 'Registry = "' in content:
                    import re
                    matches = re.findall(r'Registry = "([^"]+)"', content)
                    registry_values.update(matches)
        
        # All scripts should use the same default registry
        assert len(registry_values) <= 1, f"Inconsistent registry configuration: {registry_values}"


class TestScriptDocumentation:
    """Test script documentation and help content."""
    
    def test_all_scripts_have_help(self):
        """Test that all major scripts have help documentation."""
        script_paths = [
            "scripts/version.ps1",
            "scripts/release.ps1", 
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1",
            "scripts/security-scan.ps1"
        ]
        
        for script_path in script_paths:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                
                # Check for help function
                assert "Show-Help" in content, f"Script {script_path} must have Show-Help function"
                assert "-Help" in content, f"Script {script_path} must accept -Help parameter"
                
                # Check help content
                assert "USAGE:" in content, f"Script {script_path} help must include usage"
                assert "EXAMPLES:" in content, f"Script {script_path} help must include examples"
    
    def test_help_content_quality(self):
        """Test quality of help content in scripts."""
        script_paths = [
            "scripts/release.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1"
        ]
        
        for script_path in script_paths:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                
                # Check for comprehensive help content
                assert "PREREQUISITES:" in content or "REQUIREMENTS:" in content, \
                    f"Script {script_path} should document prerequisites"
                assert "OPTIONS:" in content, f"Script {script_path} should document options"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])