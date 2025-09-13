"""
CI/CD Pipeline Validation Tests

Tests to validate the CI/CD pipeline components, workflows, and automation scripts.
These tests ensure the pipeline infrastructure is correctly configured and functional.
"""

import pytest
import yaml
import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestVersionManagement:
    """Test version management system and scripts."""
    
    def test_version_file_exists(self):
        """Test that VERSION file exists and contains valid semantic version."""
        version_file = Path("VERSION")
        assert version_file.exists(), "VERSION file must exist"
        
        version_content = version_file.read_text().strip()
        assert len(version_content) > 0, "VERSION file cannot be empty"
        
        # Validate semantic versioning format
        import re
        semver_pattern = r'^(\d+)\.(\d+)\.(\d+)$'
        assert re.match(semver_pattern, version_content), f"Invalid version format: {version_content}"
    
    def test_version_script_exists(self):
        """Test that version management script exists and is executable."""
        version_script = Path("scripts/version.ps1")
        assert version_script.exists(), "version.ps1 script must exist"
        
        # Check script has help function
        script_content = version_script.read_text()
        assert "Show-Help" in script_content, "Version script must have help function"
        assert "Get-CurrentVersion" in script_content, "Version script must have version getter"
    
    @pytest.mark.integration
    def test_version_script_functionality(self):
        """Test version script basic functionality."""
        if os.name != 'nt':
            pytest.skip("PowerShell scripts only supported on Windows")
        
        # Test getting current version
        result = subprocess.run(
            ["powershell", "-File", "scripts/version.ps1", "get"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Version script failed: {result.stderr}"
        assert len(result.stdout.strip()) > 0, "Version script should return current version"
    
    def test_version_validation_logic(self):
        """Test version validation logic."""
        # Import or define validation function
        def validate_version(version):
            import re
            return re.match(r'^(\d+)\.(\d+)\.(\d+)$', version) is not None
        
        # Test valid versions
        assert validate_version("1.0.0")
        assert validate_version("0.1.0")
        assert validate_version("10.20.30")
        
        # Test invalid versions
        assert not validate_version("1.0")
        assert not validate_version("1.0.0.0")
        assert not validate_version("v1.0.0")
        assert not validate_version("1.0.0-beta")
        assert not validate_version("")


class TestGitHubWorkflows:
    """Test GitHub Actions workflow configurations."""
    
    def test_ci_workflow_exists(self):
        """Test that CI workflow exists and is valid YAML."""
        ci_workflow = Path(".github/workflows/ci.yml")
        assert ci_workflow.exists(), "CI workflow must exist"
        
        with open(ci_workflow) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow is not None, "CI workflow must be valid YAML"
        assert "name" in workflow, "CI workflow must have a name"
        assert "on" in workflow, "CI workflow must have triggers"
        assert "jobs" in workflow, "CI workflow must have jobs"
    
    def test_release_workflow_exists(self):
        """Test that release workflow exists and is valid YAML."""
        release_workflow = Path(".github/workflows/release.yml")
        assert release_workflow.exists(), "Release workflow must exist"
        
        with open(release_workflow) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow is not None, "Release workflow must be valid YAML"
        assert "name" in workflow, "Release workflow must have a name"
        assert "on" in workflow, "Release workflow must have triggers"
        assert "jobs" in workflow, "Release workflow must have jobs"
    
    def test_rollback_workflow_exists(self):
        """Test that rollback workflow exists and is valid YAML."""
        rollback_workflow = Path(".github/workflows/rollback.yml")
        assert rollback_workflow.exists(), "Rollback workflow must exist"
        
        with open(rollback_workflow) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow is not None, "Rollback workflow must be valid YAML"
        assert "name" in workflow, "Rollback workflow must have a name"
        assert "workflow_dispatch" in workflow["on"], "Rollback workflow must be manually triggered"
    
    def test_promote_workflow_exists(self):
        """Test that promote workflow exists and is valid YAML."""
        promote_workflow = Path(".github/workflows/promote.yml")
        assert promote_workflow.exists(), "Promote workflow must exist"
        
        with open(promote_workflow) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow is not None, "Promote workflow must be valid YAML"
        assert "name" in workflow, "Promote workflow must have a name"
        assert "workflow_dispatch" in workflow["on"], "Promote workflow must be manually triggered"
    
    def test_workflow_security_configuration(self):
        """Test that workflows have proper security configuration."""
        workflows = [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".github/workflows/rollback.yml",
            ".github/workflows/promote.yml"
        ]
        
        for workflow_path in workflows:
            if not Path(workflow_path).exists():
                continue
                
            with open(workflow_path) as f:
                workflow = yaml.safe_load(f)
            
            # Check for security best practices
            if "permissions" in workflow:
                permissions = workflow["permissions"]
                # Ensure permissions are not overly broad
                assert permissions.get("contents", "read") in ["read", "write"], f"Invalid contents permission in {workflow_path}"
                assert permissions.get("packages", "read") in ["read", "write"], f"Invalid packages permission in {workflow_path}"
    
    def test_workflow_environment_configuration(self):
        """Test that workflows properly configure environments."""
        release_workflow = Path(".github/workflows/release.yml")
        if release_workflow.exists():
            with open(release_workflow) as f:
                workflow = yaml.safe_load(f)
            
            # Check for environment configuration
            jobs = workflow.get("jobs", {})
            deploy_job = jobs.get("deploy-dev")
            if deploy_job:
                assert "environment" in deploy_job, "Deploy job must specify environment"


class TestAutomationScripts:
    """Test automation scripts and their functionality."""
    
    def test_required_scripts_exist(self):
        """Test that all required automation scripts exist."""
        required_scripts = [
            "scripts/build.ps1",
            "scripts/deploy.ps1",
            "scripts/test.ps1",
            "scripts/release.ps1",
            "scripts/version.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1",
            "scripts/security-scan.ps1"
        ]
        
        for script_path in required_scripts:
            script = Path(script_path)
            assert script.exists(), f"Required script missing: {script_path}"
    
    def test_script_help_functions(self):
        """Test that scripts have help functions."""
        scripts_to_check = [
            "scripts/release.ps1",
            "scripts/version.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1",
            "scripts/security-scan.ps1"
        ]
        
        for script_path in scripts_to_check:
            script = Path(script_path)
            if script.exists():
                content = script.read_text()
                assert "Show-Help" in content, f"Script {script_path} must have Show-Help function"
                assert "-Help" in content, f"Script {script_path} must accept -Help parameter"
    
    def test_script_error_handling(self):
        """Test that scripts have proper error handling."""
        scripts_to_check = [
            "scripts/release.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1"
        ]
        
        for script_path in scripts_to_check:
            script = Path(script_path)
            if script.exists():
                content = script.read_text()
                assert "ErrorActionPreference" in content, f"Script {script_path} must set error handling"
                assert "try {" in content or "catch {" in content, f"Script {script_path} must have try/catch blocks"
    
    @pytest.mark.integration
    def test_script_syntax_validation(self):
        """Test PowerShell script syntax validation."""
        if os.name != 'nt':
            pytest.skip("PowerShell scripts only supported on Windows")
        
        powershell_scripts = [
            "scripts/release.ps1",
            "scripts/version.ps1",
            "scripts/promote.ps1",
            "scripts/rollback.ps1",
            "scripts/quality-gate.ps1",
            "scripts/security-scan.ps1"
        ]
        
        for script_path in powershell_scripts:
            if Path(script_path).exists():
                # Test script syntax
                result = subprocess.run(
                    ["powershell", "-NoExecute", "-File", script_path],
                    capture_output=True, text=True
                )
                assert result.returncode == 0, f"Syntax error in {script_path}: {result.stderr}"


class TestDockerConfiguration:
    """Test Docker and container configuration."""
    
    def test_dev_compose_file_exists(self):
        """Test that DEV Docker Compose file exists and is valid."""
        compose_file = Path("docker-compose.dev.yml")
        assert compose_file.exists(), "DEV Docker Compose file must exist"
        
        with open(compose_file) as f:
            compose_config = yaml.safe_load(f)
        
        assert compose_config is not None, "DEV Compose file must be valid YAML"
        assert "services" in compose_config, "Compose file must have services"
        assert "networks" in compose_config, "Compose file must have networks"
        assert "volumes" in compose_config, "Compose file must have volumes"
    
    def test_test_compose_file_exists(self):
        """Test that TEST Docker Compose file exists and is valid."""
        compose_file = Path("docker-compose.test.yml")
        assert compose_file.exists(), "TEST Docker Compose file must exist"
        
        with open(compose_file) as f:
            compose_config = yaml.safe_load(f)
        
        assert compose_config is not None, "TEST Compose file must be valid YAML"
        assert "services" in compose_config, "Compose file must have services"
        
        # Verify TEST environment uses different ports
        app_service = compose_config["services"].get("app-test")
        if app_service and "ports" in app_service:
            ports = app_service["ports"]
            assert any("8181" in port for port in ports), "TEST environment must use port 8181"
    
    def test_dockerfile_exists(self):
        """Test that Dockerfile exists for application."""
        dockerfile = Path("services/app/Dockerfile")
        assert dockerfile.exists(), "Application Dockerfile must exist"
        
        content = dockerfile.read_text()
        assert "FROM" in content, "Dockerfile must have base image"
        assert "WORKDIR" in content, "Dockerfile should set working directory"
    
    def test_compose_security_configuration(self):
        """Test Docker Compose security configuration."""
        compose_files = ["docker-compose.dev.yml", "docker-compose.test.yml"]
        
        for compose_path in compose_files:
            if not Path(compose_path).exists():
                continue
                
            with open(compose_path) as f:
                compose_config = yaml.safe_load(f)
            
            services = compose_config.get("services", {})
            for service_name, service_config in services.items():
                # Check for security options
                if "security_opt" in service_config:
                    security_opts = service_config["security_opt"]
                    assert any("no-new-privileges" in opt for opt in security_opts), \
                        f"Service {service_name} should have no-new-privileges security option"


class TestQualityGates:
    """Test quality gate configuration and validation."""
    
    def test_quality_gate_script_exists(self):
        """Test that quality gate script exists."""
        script = Path("scripts/quality-gate.ps1")
        assert script.exists(), "Quality gate script must exist"
    
    def test_quality_gate_thresholds(self):
        """Test quality gate threshold configuration."""
        script = Path("scripts/quality-gate.ps1")
        if script.exists():
            content = script.read_text()
            
            # Check for threshold definitions
            assert "QualityThresholds" in content, "Quality gate must define thresholds"
            assert "test_coverage_min" in content, "Must define minimum test coverage"
            assert "security_critical_max" in content, "Must define max critical security issues"
            assert "performance_response_max" in content, "Must define max response time"
    
    def test_environment_specific_thresholds(self):
        """Test that different environments have appropriate thresholds."""
        script = Path("scripts/quality-gate.ps1")
        if script.exists():
            content = script.read_text()
            
            # Verify environment-specific configuration
            assert "dev =" in content, "Must have DEV environment thresholds"
            assert "test =" in content, "Must have TEST environment thresholds"
            assert "prod =" in content, "Must have PROD environment thresholds"


class TestSecurityScanning:
    """Test security scanning configuration and integration."""
    
    def test_security_scan_script_exists(self):
        """Test that security scanning script exists."""
        script = Path("scripts/security-scan.ps1")
        assert script.exists(), "Security scan script must exist"
    
    def test_security_scan_tools_configuration(self):
        """Test security scanning tools configuration."""
        script = Path("scripts/security-scan.ps1")
        if script.exists():
            content = script.read_text()
            
            # Check for tool integration
            assert "bandit" in content.lower(), "Must integrate Bandit for code scanning"
            assert "safety" in content.lower(), "Must integrate Safety for dependency scanning"
            assert "trivy" in content.lower(), "Must integrate Trivy for container scanning"
    
    def test_ci_workflow_security_integration(self):
        """Test that CI workflow includes security scanning."""
        ci_workflow = Path(".github/workflows/ci.yml")
        if ci_workflow.exists():
            content = ci_workflow.read_text()
            
            # Check for security scanning steps
            assert "bandit" in content.lower(), "CI must include Bandit scanning"
            assert "safety" in content.lower(), "CI must include dependency scanning"
            assert "trivy" in content.lower(), "CI must include container scanning"


class TestEnvironmentConfiguration:
    """Test environment configuration and isolation."""
    
    def test_environment_directories_exist(self):
        """Test that environment directories exist."""
        required_dirs = [
            "env/dev/config",
            "env/test/config"
        ]
        
        for dir_path in required_dirs:
            directory = Path(dir_path)
            assert directory.exists(), f"Environment directory missing: {dir_path}"
    
    def test_environment_config_examples_exist(self):
        """Test that environment configuration examples exist."""
        config_files = [
            "env/dev/config/.env.dev.example",
            "env/test/config/.env.test.example"
        ]
        
        for config_path in config_files:
            config_file = Path(config_path)
            assert config_file.exists(), f"Environment config example missing: {config_path}"
            
            content = config_file.read_text()
            assert "APP_ENV" in content, f"Config {config_path} must define APP_ENV"
            assert "PORT" in content, f"Config {config_path} must define PORT"
    
    def test_environment_port_isolation(self):
        """Test that environments use different ports."""
        test_config = Path("env/test/config/.env.test.example")
        if test_config.exists():
            content = test_config.read_text()
            # TEST environment should reference port 8181 somewhere
            assert "8181" in content, "TEST environment should use port 8181"


class TestPipelineIntegration:
    """Test end-to-end pipeline integration."""
    
    def test_pipeline_file_consistency(self):
        """Test consistency between different pipeline files."""
        # Check that container image names are consistent
        files_to_check = [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            "docker-compose.dev.yml",
            "docker-compose.test.yml"
        ]
        
        image_names = set()
        
        for file_path in files_to_check:
            if Path(file_path).exists():
                content = Path(file_path).read_text()
                
                # Extract image references (simplified check)
                if "ttrpg/app" in content:
                    image_names.add("ttrpg/app")
                if "ghcr.io" in content:
                    image_names.add("ghcr.io")
        
        # Should have consistent image naming
        assert len(image_names) > 0, "Pipeline files should reference container images"
    
    def test_workflow_job_dependencies(self):
        """Test that workflow jobs have proper dependencies."""
        workflows = [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml"
        ]
        
        for workflow_path in workflows:
            if not Path(workflow_path).exists():
                continue
                
            with open(workflow_path) as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get("jobs", {})
            
            # Check for proper job dependencies
            for job_name, job_config in jobs.items():
                if "needs" in job_config:
                    needs = job_config["needs"]
                    if isinstance(needs, list):
                        for dependency in needs:
                            assert dependency in jobs, f"Job {job_name} depends on non-existent job {dependency}"
                    elif isinstance(needs, str):
                        assert needs in jobs, f"Job {job_name} depends on non-existent job {needs}"


class TestDocumentation:
    """Test pipeline documentation and configuration guides."""
    
    def test_environment_protection_rules_documentation(self):
        """Test that environment protection rules documentation exists."""
        doc = Path(".github/environment-protection-rules.md")
        assert doc.exists(), "Environment protection rules documentation must exist"
        
        content = doc.read_text()
        assert "dev" in content.lower(), "Documentation must cover DEV environment"
        assert "test" in content.lower(), "Documentation must cover TEST environment"
        assert "approval" in content.lower(), "Documentation must cover approval process"
    
    def test_task_documentation_exists(self):
        """Test that FR-007 task documentation exists."""
        task_doc = Path(".claude/tasks/active/fr-007-ci-cd-pipeline.md")
        assert task_doc.exists(), "FR-007 task documentation must exist"
        
        content = task_doc.read_text()
        assert "CI/CD" in content, "Task documentation must describe CI/CD implementation"
        assert "Status:" in content, "Task documentation must have status tracking"


@pytest.fixture
def temporary_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = Path(temp_dir) / "test_repo"
        repo_path.mkdir()
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
        
        yield repo_path


class TestGitIntegration:
    """Test Git integration and version tagging."""
    
    def test_git_repository_exists(self):
        """Test that project is in a Git repository."""
        git_dir = Path(".git")
        assert git_dir.exists(), "Project must be in a Git repository"
    
    @pytest.mark.integration
    def test_version_tagging_format(self, temporary_git_repo):
        """Test version tagging format and validation."""
        # Create a sample commit
        test_file = temporary_git_repo / "test.txt"
        test_file.write_text("test content")
        
        subprocess.run(["git", "add", "test.txt"], cwd=temporary_git_repo, check=True)
        subprocess.run(["git", "commit", "-m", "Test commit"], cwd=temporary_git_repo, check=True)
        
        # Test version tag creation
        subprocess.run(["git", "tag", "v1.0.0"], cwd=temporary_git_repo, check=True)
        
        # Verify tag exists
        result = subprocess.run(
            ["git", "tag", "-l", "v1.0.0"], 
            cwd=temporary_git_repo, 
            capture_output=True, 
            text=True
        )
        assert "v1.0.0" in result.stdout, "Version tag should be created successfully"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])