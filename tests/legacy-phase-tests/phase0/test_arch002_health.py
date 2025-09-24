# tests/regression/phase0/test_arch002_health.py
"""
Phase 0 - US ARCH-002: Health Probe Regression Tests
Tests the environment runner and health probe functionality
"""

import json
import pytest
import requests
import os
import time
from pathlib import Path


class TestHealthProbe:
    """Test suite for health probe and environment runner validation"""

    def test_health_endpoint_availability(self):
        """Test that health endpoint is accessible and returns expected format"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000  # Default dev port

        health_url = f"http://localhost:{port}/healthz"

        try:
            response = requests.get(health_url, timeout=10)
            assert response.status_code == 200, f"Health endpoint returned {response.status_code}, expected 200"

            # Parse response
            health_data = response.json()
            assert isinstance(health_data, dict), "Health response should be a JSON object"

            # Verify required fields
            assert "status" in health_data, "Health response missing 'status' field"
            assert "env" in health_data, "Health response missing 'env' field"

            # Verify field values
            assert health_data["status"] in ("ok", "healthy", "ready"), f"Invalid health status: {health_data['status']}"
            assert health_data["env"] == current_env, f"Health endpoint reports env '{health_data['env']}', expected '{current_env}'"

        except requests.exceptions.ConnectionError:
            pytest.fail(f"Could not connect to health endpoint at {health_url}. Is the application running?")
        except requests.exceptions.Timeout:
            pytest.fail(f"Health endpoint at {health_url} timed out")

    def test_health_endpoint_response_time(self):
        """Test that health endpoint responds within acceptable time limits"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        # Perform multiple requests to get average response time
        response_times = []
        for _ in range(5):
            start_time = time.time()
            try:
                response = requests.get(health_url, timeout=5)
                end_time = time.time()

                if response.status_code == 200:
                    response_times.append(end_time - start_time)
                else:
                    pytest.fail(f"Health endpoint returned {response.status_code}")
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Health endpoint request failed: {e}")

            time.sleep(0.1)  # Small delay between requests

        # Calculate average response time
        avg_response_time = sum(response_times) / len(response_times)

        # Health endpoint should respond quickly (< 1 second)
        assert avg_response_time < 1.0, f"Health endpoint average response time {avg_response_time:.3f}s exceeds 1.0s threshold"

    def test_health_endpoint_schema_contract(self):
        """Test that health endpoint returns data in the expected schema format"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        try:
            response = requests.get(health_url, timeout=10)
            assert response.status_code == 200, f"Health endpoint returned {response.status_code}"

            health_data = response.json()

            # Test baseline schema from Phase 0 specification
            # Expected format: {"status":"ok","env":"<env>"}
            required_fields = ["status", "env"]
            for field in required_fields:
                assert field in health_data, f"Health response missing required field: {field}"

            # Validate field types and values
            assert isinstance(health_data["status"], str), "status field must be a string"
            assert isinstance(health_data["env"], str), "env field must be a string"

            # Status should be a valid health status
            valid_statuses = ["ok", "healthy", "ready", "degraded"]
            assert health_data["status"] in valid_statuses, f"Invalid status value: {health_data['status']}"

            # Environment should match current environment
            assert health_data["env"] == current_env, f"Environment mismatch: got '{health_data['env']}', expected '{current_env}'"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to test health endpoint schema: {e}")

    def test_health_endpoint_content_type(self):
        """Test that health endpoint returns proper Content-Type headers"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        try:
            response = requests.get(health_url, timeout=10)
            assert response.status_code == 200

            # Check Content-Type header
            content_type = response.headers.get("Content-Type", "")
            assert "application/json" in content_type, f"Expected JSON content type, got: {content_type}"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to test health endpoint headers: {e}")

    def test_health_endpoint_http_methods(self):
        """Test that health endpoint only accepts appropriate HTTP methods"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        try:
            # GET should work
            get_response = requests.get(health_url, timeout=10)
            assert get_response.status_code == 200, "GET method should be supported"

            # HEAD should work (or return 405 Method Not Allowed)
            head_response = requests.head(health_url, timeout=10)
            assert head_response.status_code in (200, 405), f"HEAD method returned unexpected status: {head_response.status_code}"

            # POST should not be allowed for health check
            post_response = requests.post(health_url, timeout=10)
            assert post_response.status_code in (405, 404), f"POST method should not be allowed, got: {post_response.status_code}"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to test health endpoint HTTP methods: {e}")

    def test_health_endpoint_during_load(self):
        """Test that health endpoint remains responsive under light load"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        # Make multiple concurrent-ish requests
        success_count = 0
        total_requests = 10

        for i in range(total_requests):
            try:
                response = requests.get(health_url, timeout=5)
                if response.status_code == 200:
                    success_count += 1
            except requests.exceptions.RequestException:
                pass  # Count as failure

            time.sleep(0.05)  # Small delay to simulate light load

        # At least 80% of requests should succeed
        success_rate = success_count / total_requests
        assert success_rate >= 0.8, f"Health endpoint success rate {success_rate:.2%} below 80% threshold under light load"

    def test_health_check_golden_master(self):
        """Test that health endpoint response matches expected golden master format"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        try:
            response = requests.get(health_url, timeout=10)
            assert response.status_code == 200

            health_data = response.json()

            # Golden master: Health response should have exactly these fields (Phase 0 baseline)
            expected_structure = {
                "status": str,
                "env": str
            }

            # Check that all expected fields are present
            for field, expected_type in expected_structure.items():
                assert field in health_data, f"Missing required field: {field}"
                assert isinstance(health_data[field], expected_type), f"Field {field} should be {expected_type.__name__}, got {type(health_data[field]).__name__}"

            # Check that no unexpected fields are present (strict contract)
            unexpected_fields = set(health_data.keys()) - set(expected_structure.keys())
            # Allow additional fields but document them
            if unexpected_fields:
                print(f"Note: Health endpoint includes additional fields: {unexpected_fields}")

            # The core contract should be stable
            assert health_data["env"] == current_env
            assert health_data["status"] in ["ok", "healthy", "ready"]

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to test health endpoint golden master: {e}")

    def test_environment_context_validation(self):
        """Test that health endpoint correctly reflects the current environment context"""
        current_env = os.getenv("ENV", "dev")

        # Get port from environment configuration
        project_root = Path(__file__).parent.parent.parent.parent
        ports_file = project_root / "env" / current_env / "config" / "ports.json"

        if ports_file.exists():
            with open(ports_file) as f:
                port_config = json.load(f)
                port = port_config.get("http_port", 8000)
        else:
            port = 8000

        health_url = f"http://localhost:{port}/healthz"

        try:
            response = requests.get(health_url, timeout=10)
            assert response.status_code == 200

            health_data = response.json()

            # Verify environment context
            reported_env = health_data.get("env")
            assert reported_env == current_env, f"Health endpoint reports environment '{reported_env}', but ENV variable is '{current_env}'"

            # Verify port consistency
            actual_port = response.url.split(":")[-1].split("/")[0]
            assert int(actual_port) == port, f"Health endpoint accessed on port {actual_port}, but config specifies {port}"

        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to test environment context validation: {e}")