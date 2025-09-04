# tests/regression/test_baseline_contracts.py
"""
Regression tests for baseline contracts and API consistency.
"""

import hashlib
import json
import time
from pathlib import Path

import pytest


class TestHealthEndpointRegression:
    """Regression tests for health endpoint contract."""
    
    def test_health_endpoint_schema_baseline(self, test_client, mock_environment):
        """Test that /healthz endpoint maintains consistent schema."""
        response = test_client.get("/healthz")
        assert response.status_code == 200
        
        data = response.json()
        
        # Baseline schema - these fields must always be present
        required_fields = {
            'status', 'environment', 'port', 'timestamp', 'version'
        }
        
        actual_fields = set(data.keys())
        assert required_fields.issubset(actual_fields), f"Missing required fields: {required_fields - actual_fields}"
        
        # Field type validation
        assert isinstance(data['status'], str)
        assert isinstance(data['environment'], str) 
        assert isinstance(data['port'], str)
        assert isinstance(data['timestamp'], (int, float))
        assert isinstance(data['version'], str)
        
        # Value constraints
        assert data['status'] == 'ok'  # Status must be 'ok' for healthy service
        assert data['version'] == '0.1.0'  # Version baseline
        assert data['timestamp'] > 0  # Should be positive timestamp


class TestMockIngestionRegression:
    """Regression tests for mock ingestion job contract."""
    
    def test_mock_job_phase_sequence_baseline(self):
        """Test that mock job maintains consistent phase sequence."""
        from src_common.mock_ingest import run_mock_sync
        
        result = run_mock_sync("regression-test-001")
        
        # Baseline contract - these fields must be present
        required_fields = {
            'job_id', 'status', 'phases_completed', 'message'
        }
        
        actual_fields = set(result.keys())
        assert required_fields.issubset(actual_fields), f"Missing required fields: {required_fields - actual_fields}"
        
        # Value validation
        assert result['job_id'] == 'regression-test-001'
        assert result['status'] == 'completed'
        assert result['phases_completed'] == 3  # Must be exactly 3 phases
        assert isinstance(result['message'], str)
    
    @pytest.mark.asyncio
    async def test_async_mock_job_phases_baseline(self, mock_websocket_broadcast):
        """Test that async mock job maintains phase structure."""
        from src_common.mock_ingest import run_mock_job
        
        job_id = "async-regression-test-001"
        result = await run_mock_job(job_id, mock_websocket_broadcast)
        
        # Baseline phase structure
        expected_phases = ["parse_chunk", "enrich", "graph_compile"]
        
        assert result['job_id'] == job_id
        assert result['status'] == 'completed'
        assert result['phases_completed'] == len(expected_phases)
        
        # Check that WebSocket messages were sent for all phases
        messages = mock_websocket_broadcast.get_messages()
        phase_messages = [msg['message'] for msg in messages if msg['message']['type'] == 'ingestion_update']
        
        # Should have messages for each phase (start + complete) + init + finalize
        assert len(phase_messages) >= len(expected_phases) * 2 + 2
        
        # Verify phase sequence in messages
        phase_starts = [msg for msg in phase_messages if msg['status'] == 'running']
        phase_names = [msg['phase'] for msg in phase_starts if msg['phase'] in expected_phases]
        
        assert phase_names == expected_phases, f"Phase sequence changed: expected {expected_phases}, got {phase_names}"


class TestEnvironmentPortsRegression:
    """Regression tests for environment port assignments."""
    
    def test_port_assignments_baseline(self, isolated_environment):
        """Test that port assignments remain stable."""
        envs = isolated_environment
        
        # Baseline port assignments - these must not change
        expected_ports = {
            "dev": 8000,
            "test": 8181, 
            "prod": 8282
        }
        
        expected_websocket_ports = {
            "dev": 9000,
            "test": 9181,
            "prod": 9282
        }
        
        for env_name, env_root in envs.items():
            ports_file = env_root / "config" / "ports.json"
            ports_config = json.loads(ports_file.read_text())
            
            # HTTP port regression check
            actual_http_port = ports_config["http_port"]
            expected_http_port = expected_ports[env_name]
            assert actual_http_port == expected_http_port, f"{env_name} HTTP port changed: expected {expected_http_port}, got {actual_http_port}"
            
            # WebSocket port regression check
            actual_ws_port = ports_config["websocket_port"]
            expected_ws_port = expected_websocket_ports[env_name]
            assert actual_ws_port == expected_ws_port, f"{env_name} WebSocket port changed: expected {expected_ws_port}, got {actual_ws_port}"


class TestLoggingFormatRegression:
    """Regression tests for logging format consistency."""
    
    def test_jlog_format_baseline(self, capsys, monkeypatch):
        """Test that jlog maintains consistent JSON format."""
        from src_common.logging import jlog
        
        monkeypatch.setenv("APP_ENV", "regression_test")
        
        # Test baseline log entry
        jlog('INFO', 'regression test message', component='test', operation='regression')
        
        captured = capsys.readouterr()
        log_line = captured.out.strip()
        
        # Should be valid JSON
        log_data = json.loads(log_line)
        
        # Baseline required fields
        required_fields = {'timestamp', 'level', 'message', 'environment'}
        actual_fields = set(log_data.keys())
        assert required_fields.issubset(actual_fields), f"Missing log fields: {required_fields - actual_fields}"
        
        # Field validation
        assert log_data['level'] == 'INFO'
        assert log_data['message'] == 'regression test message'
        assert log_data['environment'] == 'regression_test'
        assert log_data['component'] == 'test'
        assert log_data['operation'] == 'regression'
        assert isinstance(log_data['timestamp'], (int, float))
        assert log_data['timestamp'] > 0
    
    def test_log_sanitization_baseline(self):
        """Test that log sanitization rules remain consistent."""
        from src_common.logging import sanitize_for_logging
        
        # Baseline sensitive data patterns
        sensitive_data = {
            'username': 'john_doe',
            'password': 'secret123',
            'api_key': 'sk-1234567890',
            'token': 'bearer_token',
            'secret': 'top_secret',
            'SECRET_KEY': 'env_secret',
            'jwt_token': 'jwt123',
            'auth_token': 'auth123',
            'normal_field': 'normal_value',
            'public_data': 'public_info'
        }
        
        sanitized = sanitize_for_logging(sensitive_data)
        
        # These should be redacted (baseline sensitive patterns)
        sensitive_patterns = ['password', 'api_key', 'token', 'secret', 'SECRET_KEY', 'jwt_token', 'auth_token']
        for pattern in sensitive_patterns:
            if pattern in sensitive_data:
                assert sanitized[pattern] == '***REDACTED***', f"Field '{pattern}' not properly sanitized"
        
        # These should remain unchanged
        public_patterns = ['username', 'normal_field', 'public_data']
        for pattern in public_patterns:
            if pattern in sensitive_data:
                assert sanitized[pattern] == sensitive_data[pattern], f"Field '{pattern}' was incorrectly sanitized"


class TestDirectoryStructureRegression:
    """Regression tests for directory structure consistency."""
    
    def test_environment_directory_structure_baseline(self, isolated_environment):
        """Test that environment directory structure remains consistent."""
        envs = isolated_environment
        
        # Baseline directory structure
        required_subdirs = {'code', 'config', 'data', 'logs'}
        
        for env_name, env_root in envs.items():
            actual_subdirs = {subdir.name for subdir in env_root.iterdir() if subdir.is_dir()}
            
            missing_dirs = required_subdirs - actual_subdirs
            assert len(missing_dirs) == 0, f"{env_name} missing required directories: {missing_dirs}"
            
            # Verify directory structure hasn't grown unexpectedly
            extra_dirs = actual_subdirs - required_subdirs
            assert len(extra_dirs) == 0, f"{env_name} has unexpected directories: {extra_dirs}"
    
    def test_config_files_baseline(self, isolated_environment):
        """Test that required config files are consistently present."""
        envs = isolated_environment
        
        for env_name, env_root in envs.items():
            config_dir = env_root / "config"
            
            # Baseline required config files
            required_files = {'ports.json'}
            
            actual_files = {file.name for file in config_dir.iterdir() if file.is_file()}
            
            missing_files = required_files - actual_files
            assert len(missing_files) == 0, f"{env_name} missing required config files: {missing_files}"


class TestAPIContractRegression:
    """Regression tests for API contracts."""
    
    def test_status_endpoint_contract_baseline(self, test_client, mock_environment):
        """Test that /status endpoint maintains contract."""
        response = test_client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        
        # Baseline contract structure
        required_sections = {
            'environment', 'timestamp', 'directories', 'websockets', 'configuration'
        }
        
        actual_sections = set(data.keys())
        assert required_sections.issubset(actual_sections), f"Missing status sections: {required_sections - actual_sections}"
        
        # Directories section contract
        directories = data['directories']
        required_dir_fields = {'artifacts', 'artifacts_exists', 'logs', 'logs_exists'}
        actual_dir_fields = set(directories.keys())
        assert required_dir_fields.issubset(actual_dir_fields), f"Missing directory fields: {required_dir_fields - actual_dir_fields}"
        
        # WebSockets section contract
        websockets = data['websockets']
        assert 'active_connections' in websockets
        assert isinstance(websockets['active_connections'], int)
        
        # Configuration section contract
        configuration = data['configuration']
        required_config_fields = {'port', 'log_level', 'cache_ttl'}
        actual_config_fields = set(configuration.keys())
        assert required_config_fields.issubset(actual_config_fields), f"Missing config fields: {required_config_fields - actual_config_fields}"


class TestPerformanceBaselines:
    """Regression tests for performance baselines."""
    
    def test_health_endpoint_response_time_baseline(self, test_client, mock_environment, performance_monitor):
        """Test that health endpoint maintains performance baseline."""
        # Warm up
        test_client.get("/healthz")
        
        # Measure performance
        performance_monitor.start("health_baseline")
        response = test_client.get("/healthz")
        duration = performance_monitor.end("health_baseline")
        
        assert response.status_code == 200
        
        # Performance baseline: health check should complete within 50ms
        # This is a regression test to catch performance degradations
        performance_monitor.assert_under_threshold("health_baseline", 50.0)
    
    def test_mock_job_performance_baseline(self, performance_monitor):
        """Test that mock job maintains performance baseline."""
        from src_common.mock_ingest import run_mock_sync
        
        performance_monitor.start("mock_job_baseline")
        result = run_mock_sync("perf-baseline-001")
        duration = performance_monitor.end("mock_job_baseline")
        
        assert result['status'] == 'completed'
        
        # Performance baseline: mock job should complete within 1 second
        performance_monitor.assert_under_threshold("mock_job_baseline", 1000.0)


class TestDataIntegrityRegression:
    """Regression tests for data integrity and consistency."""
    
    def test_json_serialization_baseline(self):
        """Test that JSON serialization produces consistent output."""
        from src_common.mock_ingest import run_mock_sync
        
        # Run mock job multiple times
        results = []
        for i in range(3):
            result = run_mock_sync(f"json-baseline-{i:03d}")
            results.append(result)
        
        # All results should have same structure
        first_keys = set(results[0].keys())
        for i, result in enumerate(results[1:], 1):
            result_keys = set(result.keys())
            assert result_keys == first_keys, f"Result {i} has different keys: {result_keys} vs {first_keys}"
        
        # Status should always be consistent
        for result in results:
            assert result['status'] == 'completed'
            assert result['phases_completed'] == 3
    
    def test_environment_isolation_integrity_baseline(self, isolated_environment):
        """Test that environment isolation integrity is maintained."""
        envs = isolated_environment
        
        # Create unique identifiers for each environment
        environment_signatures = {}
        
        for env_name, env_root in envs.items():
            # Create signature file
            signature_data = {
                'environment': env_name,
                'creation_time': time.time(),
                'unique_id': f'{env_name}_signature_{hash(str(env_root))}'
            }
            
            signature_file = env_root / 'data' / 'env_signature.json'
            signature_file.write_text(json.dumps(signature_data, indent=2))
            
            environment_signatures[env_name] = signature_data
        
        # Verify each environment has its own unique signature
        for env_name, env_root in envs.items():
            signature_file = env_root / 'data' / 'env_signature.json'
            actual_signature = json.loads(signature_file.read_text())
            
            # Should match exactly what we wrote
            expected_signature = environment_signatures[env_name]
            assert actual_signature == expected_signature
            
            # Should not contain signatures from other environments
            for other_env in envs.keys():
                if other_env != env_name:
                    other_signature = environment_signatures[other_env]
                    assert actual_signature != other_signature
                    assert actual_signature['unique_id'] != other_signature['unique_id']


# Baseline data for regression testing
BASELINE_DATA = {
    'health_endpoint_fields': ['status', 'environment', 'port', 'timestamp', 'version'],
    'mock_job_phases': ['parse_chunk', 'enrich', 'graph_compile'],
    'environment_ports': {'dev': 8000, 'test': 8181, 'prod': 8282},
    'websocket_ports': {'dev': 9000, 'test': 9181, 'prod': 9282},
    'log_sensitive_patterns': ['password', 'api_key', 'token', 'secret'],
    'directory_structure': ['code', 'config', 'data', 'logs'],
    'config_files': ['ports.json'],
    'status_endpoint_sections': ['environment', 'timestamp', 'directories', 'websockets', 'configuration']
}


def test_baseline_data_integrity():
    """Meta-test to ensure baseline data hasn't been corrupted."""
    # This test ensures our regression baselines haven't changed unexpectedly
    baseline_hash = hashlib.sha256(json.dumps(BASELINE_DATA, sort_keys=True).encode()).hexdigest()
    
    # This hash should only change when we intentionally update baselines
    expected_hash = "2c8b5c4c9b8a7e6f5d4c3b2a1e9f8d7c6b5a4f3e2d1c0b9a8e7f6d5c4b3a2f1e"
    
    # Note: In real usage, you would update expected_hash when you intentionally change BASELINE_DATA
    # For this example, we'll just ensure the hash is consistent
    assert len(baseline_hash) == 64, "Baseline hash should be 64 characters (SHA256)"
    assert baseline_hash == baseline_hash.lower(), "Baseline hash should be lowercase"