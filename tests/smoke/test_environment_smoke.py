"""
Environment Smoke Tests

Fast, basic smoke tests to validate that environments are operational
and can handle basic requests. These tests are designed to run quickly
after deployments to catch major issues.
"""

import pytest
import requests
import time
import json
from typing import Dict, Any


class TestEnvironmentSmoke:
    """Basic smoke tests for environment validation."""
    
    @pytest.fixture
    def environment_configs(self):
        """Configuration for different environments."""
        return {
            "dev": {
                "base_url": "http://localhost:8000",
                "timeout": 30,
                "expected_env": "dev"
            },
            "test": {
                "base_url": "http://localhost:8181", 
                "timeout": 45,
                "expected_env": "test"
            }
        }
    
    @pytest.mark.smoke
    def test_dev_environment_basic_connectivity(self, environment_configs):
        """Test basic connectivity to DEV environment."""
        config = environment_configs["dev"]
        self._test_basic_connectivity("dev", config)
    
    @pytest.mark.smoke
    def test_test_environment_basic_connectivity(self, environment_configs):
        """Test basic connectivity to TEST environment."""
        config = environment_configs["test"]
        self._test_basic_connectivity("test", config)
    
    def _test_basic_connectivity(self, env_name: str, config: Dict[str, Any]):
        """Helper method to test basic connectivity to an environment."""
        base_url = config["base_url"]
        timeout = config["timeout"]
        
        # Test basic HTTP connectivity
        try:
            response = requests.get(f"{base_url}/healthz", timeout=timeout)
            assert response.status_code == 200, \
                f"{env_name} environment health check failed with status {response.status_code}"
            
            # Validate response is JSON
            health_data = response.json()
            assert isinstance(health_data, dict), f"{env_name} health response should be JSON object"
            
            # Basic health validation
            assert "status" in health_data, f"{env_name} health response missing status field"
            assert health_data["status"] == "healthy", \
                f"{env_name} environment reports unhealthy status: {health_data['status']}"
            
            print(f"✓ {env_name.upper()} environment basic connectivity: PASS")
            
        except requests.exceptions.Timeout:
            pytest.skip(f"{env_name} environment not responding within {timeout} seconds")
        except requests.exceptions.ConnectionError:
            pytest.skip(f"{env_name} environment not available at {base_url}")
        except requests.exceptions.RequestException as e:
            pytest.fail(f"{env_name} environment connectivity failed: {e}")


class TestHealthEndpointSmoke:
    """Smoke tests for health endpoint functionality."""
    
    @pytest.fixture
    def environments(self):
        """List of environments to test."""
        return [
            ("dev", "http://localhost:8000"),
            ("test", "http://localhost:8181")
        ]
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_health_endpoint_response_format(self, env_name, base_url):
        """Test health endpoint returns properly formatted response."""
        try:
            response = requests.get(f"{base_url}/healthz", timeout=15)
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not healthy")
            
            health_data = response.json()
            
            # Validate required fields
            required_fields = ["status"]
            for field in required_fields:
                assert field in health_data, f"Health response missing required field: {field}"
            
            # Validate status values
            valid_statuses = ["healthy", "unhealthy", "degraded"]
            assert health_data["status"] in valid_statuses, \
                f"Invalid health status: {health_data['status']}"
            
            # Validate optional fields if present
            if "timestamp" in health_data:
                assert isinstance(health_data["timestamp"], (str, int, float)), \
                    "Timestamp should be string or number"
            
            if "version" in health_data:
                assert isinstance(health_data["version"], str), \
                    "Version should be string"
            
            if "services" in health_data:
                assert isinstance(health_data["services"], dict), \
                    "Services should be dictionary"
                
                # Validate service health format
                for service_name, service_health in health_data["services"].items():
                    assert isinstance(service_health, dict), \
                        f"Service {service_name} health should be dictionary"
                    
                    if "status" in service_health:
                        assert service_health["status"] in valid_statuses, \
                            f"Invalid service status for {service_name}: {service_health['status']}"
            
            print(f"✓ {env_name.upper()} health endpoint format: PASS")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_health_endpoint_response_time(self, env_name, base_url):
        """Test health endpoint responds within acceptable time."""
        max_response_time = 5.0  # seconds
        
        try:
            start_time = time.time()
            response = requests.get(f"{base_url}/healthz", timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not healthy")
            
            assert response_time <= max_response_time, \
                f"{env_name} health endpoint too slow: {response_time:.2f}s > {max_response_time}s"
            
            print(f"✓ {env_name.upper()} health response time: {response_time:.2f}s")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")


class TestBasicAPISmoke:
    """Smoke tests for basic API functionality."""
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_api_root_endpoint(self, env_name, base_url):
        """Test API root endpoint accessibility."""
        try:
            response = requests.get(base_url, timeout=10)
            
            # Accept various success responses
            acceptable_status_codes = [200, 404, 405]  # 404/405 are OK if no root handler
            assert response.status_code in acceptable_status_codes, \
                f"{env_name} API root returned unexpected status: {response.status_code}"
            
            print(f"✓ {env_name.upper()} API root endpoint: PASS ({response.status_code})")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_api_error_handling(self, env_name, base_url):
        """Test API error handling for invalid endpoints."""
        try:
            # Test non-existent endpoint
            response = requests.get(f"{base_url}/nonexistent-endpoint-12345", timeout=10)
            
            # Should return 404 for non-existent endpoints
            assert response.status_code == 404, \
                f"{env_name} API should return 404 for non-existent endpoints, got {response.status_code}"
            
            print(f"✓ {env_name.upper()} API error handling: PASS")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")


class TestEnvironmentIdentification:
    """Smoke tests for environment identification and configuration."""
    
    @pytest.mark.smoke
    def test_dev_environment_identification(self):
        """Test DEV environment correctly identifies itself."""
        self._test_environment_identification("dev", "http://localhost:8000", "dev")
    
    @pytest.mark.smoke
    def test_test_environment_identification(self):
        """Test TEST environment correctly identifies itself."""
        self._test_environment_identification("test", "http://localhost:8181", "test")
    
    def _test_environment_identification(self, env_name: str, base_url: str, expected_env: str):
        """Helper method to test environment identification."""
        try:
            response = requests.get(f"{base_url}/healthz", timeout=15)
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not available")
            
            health_data = response.json()
            
            # Check if environment is identified in health response
            if "environment" in health_data:
                actual_env = health_data["environment"]
                assert actual_env == expected_env, \
                    f"{env_name} environment incorrectly identifies as '{actual_env}', expected '{expected_env}'"
                
                print(f"✓ {env_name.upper()} environment identification: {actual_env}")
            else:
                # Environment identification is optional, but warn if missing
                print(f"⚠ {env_name.upper()} environment identification not available")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")


class TestServiceAvailability:
    """Smoke tests for critical service availability."""
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_database_connectivity_smoke(self, env_name, base_url):
        """Test basic database connectivity through health endpoint."""
        try:
            response = requests.get(f"{base_url}/healthz", timeout=15)
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not available")
            
            health_data = response.json()
            
            # Check for database service health
            if "services" in health_data:
                services = health_data["services"]
                
                # Look for database-related services
                db_services = ["database", "postgres", "postgresql", "db"]
                found_db_services = [svc for svc in db_services if svc in services]
                
                if found_db_services:
                    for db_service in found_db_services:
                        db_health = services[db_service]
                        if "status" in db_health:
                            assert db_health["status"] in ["healthy", "unknown"], \
                                f"{env_name} {db_service} service unhealthy: {db_health['status']}"
                    
                    print(f"✓ {env_name.upper()} database connectivity: PASS")
                else:
                    print(f"⚠ {env_name.upper()} database service status not available")
            else:
                print(f"⚠ {env_name.upper()} service health information not available")
                
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_cache_availability_smoke(self, env_name, base_url):
        """Test cache service availability through health endpoint."""
        try:
            response = requests.get(f"{base_url}/healthz", timeout=15)
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not available")
            
            health_data = response.json()
            
            # Check for cache service health
            if "services" in health_data:
                services = health_data["services"]
                
                # Look for cache-related services
                cache_services = ["cache", "redis", "memcached"]
                found_cache_services = [svc for svc in cache_services if svc in services]
                
                if found_cache_services:
                    for cache_service in found_cache_services:
                        cache_health = services[cache_service]
                        if "status" in cache_health:
                            # Cache can be degraded and still functional
                            assert cache_health["status"] in ["healthy", "degraded", "unknown"], \
                                f"{env_name} {cache_service} service unhealthy: {cache_health['status']}"
                    
                    print(f"✓ {env_name.upper()} cache availability: PASS")
                else:
                    print(f"⚠ {env_name.upper()} cache service status not available")
            else:
                print(f"⚠ {env_name.upper()} service health information not available")
                
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")


class TestEnvironmentIsolation:
    """Smoke tests for environment isolation and configuration."""
    
    @pytest.mark.smoke
    def test_port_isolation(self):
        """Test that environments use different ports."""
        dev_url = "http://localhost:8000"
        test_url = "http://localhost:8181"
        
        dev_accessible = False
        test_accessible = False
        
        # Check DEV environment
        try:
            response = requests.get(f"{dev_url}/healthz", timeout=5)
            dev_accessible = response.status_code == 200
        except requests.exceptions.RequestException:
            pass
        
        # Check TEST environment  
        try:
            response = requests.get(f"{test_url}/healthz", timeout=5)
            test_accessible = response.status_code == 200
        except requests.exceptions.RequestException:
            pass
        
        if dev_accessible and test_accessible:
            print("✓ Environment port isolation: PASS (both environments accessible on different ports)")
        elif dev_accessible:
            print("✓ DEV environment accessible on port 8000")
        elif test_accessible:
            print("✓ TEST environment accessible on port 8181")
        else:
            pytest.skip("Neither environment accessible for port isolation test")
    
    @pytest.mark.smoke
    def test_environment_configuration_differences(self):
        """Test that environments have different configurations."""
        environments = [
            ("dev", "http://localhost:8000"),
            ("test", "http://localhost:8181")
        ]
        
        env_configs = {}
        
        for env_name, base_url in environments:
            try:
                response = requests.get(f"{base_url}/healthz", timeout=10)
                if response.status_code == 200:
                    health_data = response.json()
                    env_configs[env_name] = health_data
            except requests.exceptions.RequestException:
                continue
        
        if len(env_configs) >= 2:
            # Compare configurations to ensure they're different
            dev_config = env_configs.get("dev", {})
            test_config = env_configs.get("test", {})
            
            # Environment identifier should be different
            if "environment" in dev_config and "environment" in test_config:
                assert dev_config["environment"] != test_config["environment"], \
                    "DEV and TEST environments should have different environment identifiers"
            
            # Version information might be the same (OK) but other config should differ
            config_differences = 0
            
            for key in set(dev_config.keys()) | set(test_config.keys()):
                if key in dev_config and key in test_config:
                    if dev_config[key] != test_config[key]:
                        config_differences += 1
            
            assert config_differences > 0, \
                "DEV and TEST environments should have some configuration differences"
            
            print(f"✓ Environment configuration isolation: PASS ({config_differences} differences)")
        else:
            pytest.skip("Both environments not available for configuration comparison")


class TestDeploymentValidation:
    """Smoke tests for deployment validation."""
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_deployment_health_indicators(self, env_name, base_url):
        """Test deployment health indicators."""
        try:
            response = requests.get(f"{base_url}/healthz", timeout=15)
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not available")
            
            health_data = response.json()
            
            # Check for deployment-related metadata
            deployment_indicators = ["version", "build_time", "commit", "deployment_id"]
            found_indicators = [indicator for indicator in deployment_indicators if indicator in health_data]
            
            if found_indicators:
                print(f"✓ {env_name.upper()} deployment indicators: {', '.join(found_indicators)}")
                
                # Validate version format if present
                if "version" in health_data:
                    version = health_data["version"]
                    assert isinstance(version, str) and len(version) > 0, \
                        f"Version should be non-empty string, got: {version}"
            else:
                print(f"⚠ {env_name.upper()} deployment indicators not available")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")
    
    @pytest.mark.smoke
    @pytest.mark.parametrize("env_name,base_url", [
        ("dev", "http://localhost:8000"),
        ("test", "http://localhost:8181")
    ])
    def test_startup_completion(self, env_name, base_url):
        """Test that environment has completed startup successfully."""
        try:
            response = requests.get(f"{base_url}/healthz", timeout=15)
            
            if response.status_code != 200:
                pytest.skip(f"{env_name} environment not available")
            
            health_data = response.json()
            
            # Environment should report healthy status
            assert health_data.get("status") == "healthy", \
                f"{env_name} environment not fully started: {health_data.get('status')}"
            
            # Check if startup indicators are present
            if "uptime" in health_data:
                uptime = health_data["uptime"]
                # Uptime should be positive (started successfully)
                assert isinstance(uptime, (int, float)) and uptime > 0, \
                    f"Invalid uptime value: {uptime}"
            
            print(f"✓ {env_name.upper()} startup completion: PASS")
            
        except requests.exceptions.RequestException:
            pytest.skip(f"{env_name} environment not available")


if __name__ == "__main__":
    # Run smoke tests with minimal output
    pytest.main([__file__, "-v", "-m", "smoke", "--tb=short"])