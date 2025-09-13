"""
Deployment Integration Tests

Integration tests for CI/CD deployment processes, environment promotion,
and end-to-end pipeline validation.
"""

import pytest
import requests
import time
import subprocess
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestEnvironmentDeployment:
    """Test deployment to different environments."""
    
    @pytest.fixture
    def deployment_config(self):
        """Configuration for deployment tests."""
        return {
            "dev": {
                "port": 8000,
                "url": "http://localhost:8000",
                "timeout": 60
            },
            "test": {
                "port": 8181, 
                "url": "http://localhost:8181",
                "timeout": 90
            }
        }
    
    @pytest.mark.integration
    def test_dev_environment_health(self, deployment_config):
        """Test DEV environment deployment and health."""
        config = deployment_config["dev"]
        health_url = f"{config['url']}/healthz"
        
        # Allow time for environment to be ready
        max_retries = 6
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                response = requests.get(health_url, timeout=30)
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Validate health response structure
                    assert "status" in health_data, "Health response must include status"
                    assert health_data["status"] == "healthy", f"Environment not healthy: {health_data}"
                    
                    # Check service health if available
                    if "services" in health_data:
                        for service_name, service_info in health_data["services"].items():
                            assert service_info.get("status") in ["healthy", "unknown"], \
                                f"Service {service_name} not healthy: {service_info}"
                    
                    return  # Test passed
                    
            except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                if attempt == max_retries - 1:
                    pytest.skip(f"DEV environment not available at {health_url}")
                time.sleep(retry_delay)
        
        pytest.fail(f"DEV environment health check failed after {max_retries} attempts")
    
    @pytest.mark.integration
    def test_test_environment_health(self, deployment_config):
        """Test TEST environment deployment and health."""
        config = deployment_config["test"]
        health_url = f"{config['url']}/healthz"
        
        # Allow time for environment to be ready
        max_retries = 6
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                response = requests.get(health_url, timeout=30)
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Validate health response
                    assert "status" in health_data, "Health response must include status"
                    assert health_data["status"] == "healthy", f"TEST environment not healthy: {health_data}"
                    
                    # Verify environment identification
                    if "environment" in health_data:
                        assert health_data["environment"] == "test", "Should identify as TEST environment"
                    
                    return  # Test passed
                    
            except (requests.exceptions.RequestException, requests.exceptions.Timeout):
                if attempt == max_retries - 1:
                    pytest.skip(f"TEST environment not available at {health_url}")
                time.sleep(retry_delay)
        
        pytest.fail(f"TEST environment health check failed after {max_retries} attempts")
    
    @pytest.mark.integration
    def test_environment_isolation(self, deployment_config):
        """Test that DEV and TEST environments are properly isolated."""
        dev_config = deployment_config["dev"]
        test_config = deployment_config["test"]
        
        # Both environments should be accessible on different ports
        try:
            dev_response = requests.get(f"{dev_config['url']}/healthz", timeout=10)
            test_response = requests.get(f"{test_config['url']}/healthz", timeout=10)
            
            dev_healthy = dev_response.status_code == 200
            test_healthy = test_response.status_code == 200
            
            if dev_healthy and test_healthy:
                dev_data = dev_response.json()
                test_data = test_response.json()
                
                # Environments should have different configurations
                if "environment" in dev_data and "environment" in test_data:
                    assert dev_data["environment"] != test_data["environment"], \
                        "Environments should have different identifiers"
                
                # Different ports should be used
                assert dev_config["port"] != test_config["port"], \
                    "Environments should use different ports"
            
        except requests.exceptions.RequestException:
            pytest.skip("Environment isolation test requires both environments running")


class TestVersioningIntegration:
    """Test version management integration across the pipeline."""
    
    def test_version_file_integration(self):
        """Test VERSION file integration with pipeline."""
        version_file = Path("VERSION")
        assert version_file.exists(), "VERSION file must exist"
        
        version = version_file.read_text().strip()
        
        # Validate version format
        import re
        assert re.match(r'^\d+\.\d+\.\d+$', version), f"Invalid version format: {version}"
        
        # Check version is referenced in workflows
        workflow_files = [
            ".github/workflows/release.yml",
            ".github/workflows/promote.yml"
        ]
        
        for workflow_file in workflow_files:
            if Path(workflow_file).exists():
                content = Path(workflow_file).read_text()
                assert "VERSION" in content, f"Workflow {workflow_file} should reference VERSION"
    
    @pytest.mark.integration
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_version_script_integration(self):
        """Test version script integration with git."""
        # Test version script can read current version
        result = subprocess.run(
            ["powershell", "-File", "scripts/version.ps1", "get"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Version script failed: {result.stderr}"
        
        script_version = result.stdout.strip()
        file_version = Path("VERSION").read_text().strip()
        
        assert script_version == file_version, \
            f"Script version ({script_version}) doesn't match file version ({file_version})"
    
    def test_docker_image_versioning(self):
        """Test Docker image versioning configuration."""
        compose_files = ["docker-compose.dev.yml", "docker-compose.test.yml"]
        
        for compose_file in compose_files:
            if Path(compose_file).exists():
                import yaml
                with open(compose_file) as f:
                    compose_config = yaml.safe_load(f)
                
                services = compose_config.get("services", {})
                for service_name, service_config in services.items():
                    if "image" in service_config:
                        image = service_config["image"]
                        # Check for version placeholder or latest tag
                        assert "latest" in image or "${" in image, \
                            f"Service {service_name} should use versioned or parameterized image"


class TestSecurityIntegration:
    """Test security scanning integration."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_security_scan_integration(self):
        """Test security scanning script integration."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/security-scan.ps1", "-ScanType", "code", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        # Help should work even if tools aren't installed
        assert result.returncode == 0, f"Security scan help failed: {result.stderr}"
        assert "USAGE:" in result.stdout, "Security scan should provide usage information"
    
    def test_ci_workflow_security_steps(self):
        """Test CI workflow includes security scanning steps."""
        ci_workflow = Path(".github/workflows/ci.yml")
        if ci_workflow.exists():
            import yaml
            with open(ci_workflow) as f:
                workflow = yaml.safe_load(f)
            
            # Check for security-related jobs or steps
            workflow_content = str(workflow)
            security_tools = ["bandit", "safety", "trivy"]
            
            found_tools = [tool for tool in security_tools if tool in workflow_content.lower()]
            assert len(found_tools) > 0, f"CI workflow should include security tools: {security_tools}"
    
    def test_security_reporting_integration(self):
        """Test security reporting and artifact handling."""
        ci_workflow = Path(".github/workflows/ci.yml")
        if ci_workflow.exists():
            content = ci_workflow.read_text()
            
            # Check for artifact upload of security reports
            assert "upload-artifact" in content, "CI should upload security report artifacts"
            assert "security" in content.lower(), "CI should handle security-related artifacts"


class TestQualityGateIntegration:
    """Test quality gate integration across environments."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_quality_gate_integration(self):
        """Test quality gate script integration."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/quality-gate.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Quality gate help failed: {result.stderr}"
        assert "Environment" in result.stdout, "Quality gate should support environment parameter"
    
    def test_quality_thresholds_consistency(self):
        """Test quality thresholds are consistently defined."""
        quality_script = Path("scripts/quality-gate.ps1")
        if quality_script.exists():
            content = quality_script.read_text()
            
            # Check all environments have thresholds
            environments = ["dev", "test", "prod"]
            for env in environments:
                assert f'"{env}"' in content, f"Quality thresholds missing for {env} environment"
            
            # Check required threshold types
            threshold_types = [
                "test_coverage_min",
                "security_critical_max", 
                "security_high_max",
                "performance_response_max"
            ]
            
            for threshold in threshold_types:
                assert threshold in content, f"Missing quality threshold: {threshold}"


class TestPipelineEndToEnd:
    """End-to-end pipeline integration tests."""
    
    def test_pipeline_file_consistency(self):
        """Test consistency across pipeline configuration files."""
        # Check container registry consistency
        files_with_registry = [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml", 
            ".github/workflows/promote.yml"
        ]
        
        registries = set()
        
        for file_path in files_with_registry:
            if Path(file_path).exists():
                content = Path(file_path).read_text()
                if "ghcr.io" in content:
                    registries.add("ghcr.io")
                if "docker.io" in content:
                    registries.add("docker.io")
        
        # Should have consistent registry usage
        assert len(registries) <= 1, f"Inconsistent container registries: {registries}"
    
    def test_environment_configuration_consistency(self):
        """Test environment configuration consistency."""
        # Check port consistency between compose files and documentation
        compose_configs = {}
        
        compose_files = [
            ("dev", "docker-compose.dev.yml"),
            ("test", "docker-compose.test.yml")
        ]
        
        for env, compose_file in compose_files:
            if Path(compose_file).exists():
                import yaml
                with open(compose_file) as f:
                    config = yaml.safe_load(f)
                
                compose_configs[env] = config
        
        # Verify different ports for different environments
        if "dev" in compose_configs and "test" in compose_configs:
            dev_services = compose_configs["dev"].get("services", {})
            test_services = compose_configs["test"].get("services", {})
            
            dev_ports = set()
            test_ports = set()
            
            for service in dev_services.values():
                if "ports" in service:
                    for port_mapping in service["ports"]:
                        external_port = port_mapping.split(":")[0]
                        dev_ports.add(external_port)
            
            for service in test_services.values():
                if "ports" in service:
                    for port_mapping in service["ports"]:
                        external_port = port_mapping.split(":")[0]
                        test_ports.add(external_port)
            
            # DEV and TEST should use different external ports
            port_overlap = dev_ports.intersection(test_ports)
            assert len(port_overlap) == 0, f"Port conflict between environments: {port_overlap}"
    
    @pytest.mark.integration
    def test_workflow_trigger_consistency(self):
        """Test workflow trigger consistency and dependencies."""
        workflow_files = [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".github/workflows/rollback.yml",
            ".github/workflows/promote.yml"
        ]
        
        workflows = {}
        
        for workflow_file in workflow_files:
            if Path(workflow_file).exists():
                import yaml
                with open(workflow_file) as f:
                    workflow = yaml.safe_load(f)
                workflows[workflow_file] = workflow
        
        # CI should trigger on push and PR
        if ".github/workflows/ci.yml" in workflows:
            ci_triggers = workflows[".github/workflows/ci.yml"].get("on", {})
            assert "push" in ci_triggers or "pull_request" in ci_triggers, \
                "CI workflow should trigger on push or PR"
        
        # Release should trigger on push to main
        if ".github/workflows/release.yml" in workflows:
            release_triggers = workflows[".github/workflows/release.yml"].get("on", {})
            assert "push" in release_triggers or "workflow_dispatch" in release_triggers, \
                "Release workflow should trigger on push to main or manual dispatch"
        
        # Rollback and promote should be manual only
        manual_workflows = [".github/workflows/rollback.yml", ".github/workflows/promote.yml"]
        for workflow_file in manual_workflows:
            if workflow_file in workflows:
                triggers = workflows[workflow_file].get("on", {})
                assert "workflow_dispatch" in triggers, \
                    f"Workflow {workflow_file} should only trigger manually"


class TestRollbackIntegration:
    """Test rollback functionality integration."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows") 
    def test_rollback_script_integration(self):
        """Test rollback script integration with environments."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/rollback.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Rollback help failed: {result.stderr}"
        help_output = result.stdout
        
        # Check for environment support
        assert "Environment" in help_output, "Rollback should support environment parameter"
        assert "dev" in help_output, "Rollback should support dev environment"
        assert "test" in help_output, "Rollback should support test environment"
    
    def test_rollback_workflow_configuration(self):
        """Test rollback workflow configuration."""
        rollback_workflow = Path(".github/workflows/rollback.yml")
        if rollback_workflow.exists():
            import yaml
            with open(rollback_workflow) as f:
                workflow = yaml.safe_load(f)
            
            # Check for required inputs
            workflow_inputs = workflow.get("on", {}).get("workflow_dispatch", {}).get("inputs", {})
            
            required_inputs = ["environment", "version", "reason"]
            for input_name in required_inputs:
                assert input_name in workflow_inputs, f"Rollback workflow missing input: {input_name}"
            
            # Check for environment validation
            env_input = workflow_inputs.get("environment", {})
            if "options" in env_input:
                options = env_input["options"]
                assert "dev" in options, "Rollback should support dev environment"
                assert "test" in options, "Rollback should support test environment"


class TestPromotionIntegration:
    """Test environment promotion integration."""
    
    def test_promotion_workflow_configuration(self):
        """Test promotion workflow configuration."""
        promote_workflow = Path(".github/workflows/promote.yml")
        if promote_workflow.exists():
            import yaml
            with open(promote_workflow) as f:
                workflow = yaml.safe_load(f)
            
            # Check for approval environment
            jobs = workflow.get("jobs", {})
            approval_jobs = [job for job_name, job in jobs.items() 
                           if "environment" in job and "approval" in str(job["environment"])]
            
            assert len(approval_jobs) > 0, "Promotion workflow should have approval gates"
    
    @pytest.mark.integration
    @pytest.mark.skipif(os.name != 'nt', reason="PowerShell scripts only on Windows")
    def test_promotion_script_integration(self):
        """Test promotion script integration."""
        result = subprocess.run(
            ["powershell", "-File", "scripts/promote.ps1", "-Help"],
            capture_output=True, text=True, cwd="."
        )
        
        assert result.returncode == 0, f"Promote help failed: {result.stderr}"
        help_output = result.stdout
        
        # Check for promotion types
        assert "PromotionType" in help_output, "Promote should support promotion types"
        assert "dev-to-test" in help_output, "Should support dev-to-test promotion"


class TestMonitoringIntegration:
    """Test monitoring and observability integration."""
    
    @pytest.mark.integration
    def test_health_endpoint_comprehensive(self):
        """Test comprehensive health endpoint across environments."""
        environments = [
            ("dev", "http://localhost:8000"),
            ("test", "http://localhost:8181")
        ]
        
        for env_name, base_url in environments:
            health_url = f"{base_url}/healthz"
            
            try:
                response = requests.get(health_url, timeout=10)
                if response.status_code == 200:
                    health_data = response.json()
                    
                    # Validate comprehensive health data
                    required_fields = ["status", "timestamp"]
                    for field in required_fields:
                        assert field in health_data, f"Health endpoint missing {field} in {env_name}"
                    
                    # Check for service-specific health if available
                    if "services" in health_data:
                        services = health_data["services"]
                        assert isinstance(services, dict), "Services should be a dict"
                        
                        # Common services that should be monitored
                        expected_services = ["database", "cache"]  # Add more as needed
                        for service in expected_services:
                            if service in services:
                                service_health = services[service]
                                assert "status" in service_health, f"Service {service} missing status"
                    
            except requests.exceptions.RequestException:
                # Environment not running, skip this test
                pytest.skip(f"{env_name} environment not available for health check")
    
    def test_logging_integration(self):
        """Test logging configuration integration."""
        # Check for log configuration in compose files
        compose_files = ["docker-compose.dev.yml", "docker-compose.test.yml"]
        
        for compose_file in compose_files:
            if Path(compose_file).exists():
                import yaml
                with open(compose_file) as f:
                    config = yaml.safe_load(f)
                
                # Check for log volume mounts
                services = config.get("services", {})
                app_services = [svc for name, svc in services.items() if "app" in name]
                
                for service in app_services:
                    volumes = service.get("volumes", [])
                    log_volumes = [vol for vol in volumes if "log" in vol]
                    assert len(log_volumes) > 0, f"App service should have log volume mounts in {compose_file}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])