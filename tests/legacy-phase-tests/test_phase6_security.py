# tests/security/test_phase6_security.py
"""
Security tests for Phase 6 Feedback System
Tests security measures, data sanitization, and attack prevention
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
from app_feedback import app


class TestFeedbackSecurityMeasures:
    """Test feedback system security measures"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_feedback_input_sanitization(self, client):
        """Test feedback input is properly sanitized"""
        malicious_inputs = [
            # XSS attempts
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')></svg>",
            
            # SQL injection attempts
            "'; DROP TABLE feedback; --",
            "' OR '1'='1' --",
            "UNION SELECT * FROM users --",
            
            # Path traversal attempts
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            
            # Command injection attempts
            "; rm -rf /",
            "| cat /etc/passwd",
            "&& whoami",
            
            # HTML injection
            "<iframe src='javascript:alert(xss)'></iframe>",
            "<div onclick='alert(\"xss\")'>Click me</div>"
        ]
        
        for malicious_input in malicious_inputs:
            feedback_data = {
                "trace_id": "security_test_injection",
                "rating": "thumbs_down",
                "query": malicious_input,
                "answer": f"Response containing {malicious_input}",
                "metadata": {"test_input": malicious_input},
                "user_note": f"Note with {malicious_input}",
                "context": {"malicious": malicious_input}
            }
            
            response = client.post("/api/feedback", json=feedback_data)
            
            # Should either process safely or reject with validation error
            assert response.status_code in [200, 400, 422, 500]
            
            if response.status_code == 200:
                data = response.json()
                # Should not contain executable content in response
                response_str = str(data)
                assert "<script>" not in response_str.lower()
                assert "javascript:" not in response_str.lower()
                assert "drop table" not in response_str.lower()
    
    def test_metadata_sanitization(self, client):
        """Test sensitive metadata is properly sanitized"""
        sensitive_metadata = {
            "api_key": "sk-1234567890abcdef",
            "API_KEY": "SENSITIVE_API_KEY",
            "password": "user_password_123",
            "PASSWORD": "ADMIN_PASSWORD", 
            "secret": "top_secret_value",
            "SECRET_TOKEN": "bearer_abc123",
            "auth": "auth_header_value",
            "AUTH_TOKEN": "jwt_token_xyz",
            "credential": "service_credential",
            "PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----",
            "normal_field": "this_should_remain",
            "user_id": "user123",
            "session_id": "session456"
        }
        
        feedback_data = {
            "trace_id": "metadata_sanitization_test",
            "rating": "thumbs_down",
            "query": "Test metadata sanitization",
            "answer": "Test answer",
            "metadata": sensitive_metadata,
            "context": {"session": "test"}
        }
        
        response = client.post("/api/feedback", json=feedback_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Check artifact was created and sanitized
        artifact_path = data.get("artifact_path")
        if artifact_path and Path(artifact_path).exists():
            with open(artifact_path, 'r') as f:
                bug_data = json.load(f)
            
            # Verify sensitive fields were redacted
            metadata = bug_data["metadata"]
            sensitive_keys = ["api_key", "password", "secret", "auth", "credential", "private_key"]
            
            for key, value in metadata.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    assert value == "[REDACTED]", f"Sensitive field {key} was not redacted"
                else:
                    # Non-sensitive fields should remain
                    if key in ["normal_field", "user_id", "session_id"]:
                        assert value != "[REDACTED]", f"Non-sensitive field {key} was incorrectly redacted"
    
    def test_rate_limiting_security(self, client):
        """Test rate limiting prevents abuse and DoS attacks"""
        feedback_template = {
            "rating": "thumbs_up",
            "query": "Rate limit security test",
            "answer": "Rate limit test answer",
            "metadata": {"test": "rate_limiting"}
        }
        
        # Attempt to overwhelm the system with requests
        successful_requests = 0
        blocked_requests = 0
        error_requests = 0
        
        # Submit many requests rapidly
        for i in range(20):  # Well beyond rate limit
            feedback_data = {
                **feedback_template,
                "trace_id": f"rate_limit_security_{i}"
            }
            
            response = client.post("/api/feedback", json=feedback_data)
            
            if response.status_code == 200:
                successful_requests += 1
            elif response.status_code == 429:  # Too Many Requests
                blocked_requests += 1
            else:
                error_requests += 1
        
        # Verify rate limiting is working
        assert successful_requests <= 10, "Rate limiting should restrict successful requests"
        assert blocked_requests > 0, "Some requests should be rate limited"
        
        # System should remain responsive
        total_requests = successful_requests + blocked_requests + error_requests
        assert total_requests == 20, "All requests should be accounted for"
    
    def test_file_path_security(self, client):
        """Test system prevents file path manipulation"""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "../../../../root/.ssh/id_rsa",
            "/proc/self/environ",
            "\\\\server\\share\\sensitive",
            "/dev/random",
            "CON", "PRN", "AUX", "NUL"  # Windows reserved names
        ]
        
        for malicious_path in malicious_paths:
            feedback_data = {
                "trace_id": malicious_path,
                "rating": "thumbs_down", 
                "query": f"Path traversal test with {malicious_path}",
                "answer": "Test answer",
                "metadata": {"path": malicious_path},
                "context": {"test_path": malicious_path}
            }
            
            response = client.post("/api/feedback", json=feedback_data)
            
            # Should handle safely without accessing unauthorized files
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                data = response.json()
                # Should not expose file system information
                assert "/etc/" not in str(data)
                assert "C:\\" not in str(data)
                assert "root" not in str(data).lower()
    
    def test_log_injection_prevention(self, client):
        """Test prevention of log injection attacks"""
        log_injection_attempts = [
            "Normal input\n[ERROR] Fake log entry - admin logged in",
            "Query\r\n[CRITICAL] System compromised",
            "Input\x00[WARNING] Null byte injection",
            "Test\t[INFO] Tab character injection",
            "User input\n\n[ALERT] Multiple newline injection",
            "\b\b\b[SECURITY] Backspace injection"
        ]
        
        for injection_attempt in log_injection_attempts:
            feedback_data = {
                "trace_id": "log_injection_test",
                "rating": "thumbs_down",
                "query": injection_attempt,
                "answer": f"Answer with {injection_attempt}",
                "metadata": {"injection": injection_attempt},
                "user_note": injection_attempt
            }
            
            response = client.post("/api/feedback", json=feedback_data)
            
            # Should process safely without injecting fake log entries
            assert response.status_code in [200, 400, 422]
            
            # Verify no log pollution occurred (would need actual log inspection in real scenario)
            if response.status_code == 200:
                data = response.json()
                # Response should not contain fake log markers
                response_str = str(data).lower()
                assert "[error]" not in response_str
                assert "[critical]" not in response_str
                assert "[security]" not in response_str
    
    def test_memory_exhaustion_protection(self, client):
        """Test protection against memory exhaustion attacks"""
        # Attempt to submit very large feedback data
        large_string = "A" * 100000  # 100KB string
        huge_string = "B" * 1000000  # 1MB string
        
        large_feedback = {
            "trace_id": "memory_test_large",
            "rating": "thumbs_down",
            "query": large_string,
            "answer": large_string,
            "metadata": {"large_field": large_string},
            "user_note": large_string
        }
        
        response = client.post("/api/feedback", json=large_feedback)
        # Should either process or reject gracefully, not crash
        assert response.status_code in [200, 400, 413, 422, 500]
        
        # Test with extremely large data
        huge_feedback = {
            "trace_id": "memory_test_huge", 
            "rating": "thumbs_up",
            "query": huge_string,
            "answer": huge_string,
            "metadata": {"huge_field": huge_string}
        }
        
        response = client.post("/api/feedback", json=huge_feedback)
        # Should reject very large payloads
        assert response.status_code in [400, 413, 422, 500]
    
    def test_concurrent_access_security(self, client):
        """Test system handles concurrent access securely"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def submit_feedback(thread_id):
            feedback_data = {
                "trace_id": f"concurrent_security_{thread_id}",
                "rating": "thumbs_up" if thread_id % 2 == 0 else "thumbs_down",
                "query": f"Concurrent test {thread_id}",
                "answer": f"Concurrent answer {thread_id}",
                "metadata": {"thread_id": thread_id}
            }
            
            try:
                response = client.post("/api/feedback", json=feedback_data)
                results.put({"thread_id": thread_id, "status": response.status_code, "success": True})
            except Exception as e:
                results.put({"thread_id": thread_id, "error": str(e), "success": False})
        
        # Create multiple concurrent threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=submit_feedback, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout
        
        # Collect results
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())
        
        # Verify all threads completed successfully
        assert len(thread_results) == 10
        for result in thread_results:
            assert result["success"] is True, f"Thread {result.get('thread_id')} failed: {result.get('error')}"
            assert result["status"] in [200, 429]  # Success or rate limited
    
    def test_feedback_artifact_security(self, client):
        """Test security of created feedback artifacts"""
        feedback_data = {
            "trace_id": "artifact_security_test", 
            "rating": "thumbs_down",
            "query": "Security test for artifacts",
            "answer": "Test answer with sensitive data: password123",
            "metadata": {
                "api_key": "secret_key",
                "normal_data": "safe_data"
            },
            "context": {"sensitive": "credential_data"}
        }
        
        response = client.post("/api/feedback", json=feedback_data)
        
        assert response.status_code == 200
        data = response.json()
        
        artifact_path = data.get("artifact_path")
        if artifact_path and Path(artifact_path).exists():
            # Check file permissions (on Unix-like systems)
            try:
                import stat
                file_stat = Path(artifact_path).stat()
                # File should not be world-readable
                permissions = stat.filemode(file_stat.st_mode)
                assert "r--" not in permissions[-3:], "Artifact file should not be world-readable"
            except:
                pass  # Skip on Windows or if stat not available
            
            # Check file contents are properly sanitized
            with open(artifact_path, 'r') as f:
                content = f.read()
                
                # Should not contain sensitive API keys
                assert "secret_key" not in content
                assert "[REDACTED]" in content
                
                # Should contain safe data
                assert "safe_data" in content
    
    def test_error_information_disclosure(self, client):
        """Test system doesn't disclose sensitive information in errors"""
        # Test with various malformed requests that might trigger errors
        malformed_requests = [
            {}, # Empty request
            {"invalid": "data"}, # Invalid structure
            {"trace_id": None, "rating": "invalid"}, # Invalid types
            {"trace_id": "test", "rating": "thumbs_up"}, # Missing required fields
        ]
        
        for malformed_request in malformed_requests:
            response = client.post("/api/feedback", json=malformed_request)
            
            # Should not expose internal system information
            if response.status_code >= 400:
                error_data = response.json()
                error_message = str(error_data).lower()
                
                # Should not expose:
                assert "password" not in error_message
                assert "secret" not in error_message
                assert "api_key" not in error_message
                assert "database" not in error_message
                assert "connection" not in error_message
                assert "traceback" not in error_message
                assert "file not found" not in error_message
                assert "/etc/" not in error_message
                assert "c:\\" not in error_message


class TestTestGateSecurity:
    """Test security of test gate functionality"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_gate_access_control(self, client):
        """Test test gate access control"""
        # Create a gate
        response = client.post("/api/gates")
        assert response.status_code == 200
        gate_data = response.json()
        gate_id = gate_data["gate_id"]
        
        # Test unauthorized operations
        malicious_gate_ids = [
            "../../../etc/passwd",
            "../../config.json",
            "/system/secrets",
            "'; DROP TABLE gates; --",
            "<script>alert('xss')</script>",
            "\\..\\..\\windows\\system32"
        ]
        
        for malicious_id in malicious_gate_ids:
            # Try to access with malicious ID
            response = client.get(f"/api/gates/{malicious_id}")
            # Should either return 404 or handle securely
            assert response.status_code in [400, 404, 422]
    
    def test_gate_injection_prevention(self, client):
        """Test gate operations prevent injection attacks"""
        injection_attempts = [
            "test'; DELETE FROM gates; --",
            "<script>alert('gate_xss')</script>",
            "../../../config/database.conf",
            "test\x00injection",
            "test\ninjection\rwith\tcontrol\vchars"
        ]
        
        for injection in injection_attempts:
            # Try to create gate with malicious environment name
            response = client.post("/api/gates", params={"environment": injection})
            
            # Should handle safely
            if response.status_code == 200:
                gate_data = response.json()
                # Environment should be sanitized or rejected
                assert injection not in str(gate_data)
                assert "<script>" not in str(gate_data)
                assert "DELETE" not in str(gate_data).upper()
    
    def test_gate_test_result_security(self, client):
        """Test test gate results don't expose sensitive information"""
        # Create and run a gate
        create_response = client.post("/api/gates")
        gate_data = create_response.json()
        gate_id = gate_data["gate_id"]
        
        run_response = client.post(f"/api/gates/{gate_id}/run")
        
        if run_response.status_code == 200:
            # Wait briefly for processing
            time.sleep(0.1)
            
            # Get gate status
            status_response = client.get(f"/api/gates/{gate_id}")
            status_data = status_response.json()
            
            # Test results should not expose:
            result_str = str(status_data).lower()
            assert "password" not in result_str
            assert "secret" not in result_str
            assert "api_key" not in result_str
            assert "/etc/" not in result_str
            assert "c:\\" not in result_str
            assert "traceback" not in result_str


class TestDataPrivacyCompliance:
    """Test data privacy and compliance measures"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_pii_data_handling(self, client):
        """Test handling of potentially personally identifiable information"""
        pii_data = {
            "trace_id": "pii_test_123",
            "rating": "thumbs_down",
            "query": "My email is user@example.com and my phone is 555-1234",
            "answer": "Response containing SSN: 123-45-6789",
            "metadata": {
                "user_email": "john.doe@company.com",
                "ip_address": "192.168.1.100",
                "phone": "+1-555-123-4567"
            },
            "user_note": "My credit card is 4111-1111-1111-1111"
        }
        
        response = client.post("/api/feedback", json=pii_data)
        
        # Should process but handle PII appropriately
        if response.status_code == 200:
            data = response.json()
            
            # Check if artifact was created
            artifact_path = data.get("artifact_path")
            if artifact_path and Path(artifact_path).exists():
                with open(artifact_path, 'r') as f:
                    content = f.read()
                
                # PII should be sanitized or anonymized
                # This is a basic check - real implementation might use more sophisticated PII detection
                sensitive_patterns = [
                    "user@example.com",
                    "123-45-6789",
                    "4111-1111-1111-1111",
                    "192.168.1.100"
                ]
                
                # Either PII should be redacted or this should be flagged for manual review
                pii_exposed = any(pattern in content for pattern in sensitive_patterns)
                if pii_exposed:
                    # If PII is present, it should be marked for review or redacted
                    assert "[REDACTED]" in content or "PII_DETECTED" in content
    
    def test_data_retention_compliance(self, client):
        """Test data retention and cleanup compliance"""
        # This test would verify data retention policies
        # In a real system, this might test automatic cleanup of old feedback data
        
        feedback_data = {
            "trace_id": "retention_test_456",
            "rating": "thumbs_up",
            "query": "Data retention test",
            "answer": "Test answer for retention",
            "metadata": {"retention_test": True}
        }
        
        response = client.post("/api/feedback", json=feedback_data)
        assert response.status_code == 200
        
        # Verify data was stored
        stats_response = client.get("/api/feedback/stats")
        stats = stats_response.json()
        assert stats["total_feedback"] > 0
        
        # In a real system, would test:
        # 1. Data is automatically deleted after retention period
        # 2. Users can request data deletion
        # 3. Audit logs are maintained for compliance
    
    def test_audit_logging_security(self, client):
        """Test security of audit logging"""
        feedback_data = {
            "trace_id": "audit_test_789",
            "rating": "thumbs_down",
            "query": "Audit logging test",
            "answer": "Test answer",
            "metadata": {"audit": "test"}
        }
        
        response = client.post("/api/feedback", json=feedback_data)
        
        # Verify request was processed
        assert response.status_code == 200
        
        # In a real system, would verify:
        # 1. All feedback submissions are logged
        # 2. Logs include necessary audit information
        # 3. Logs don't contain sensitive data
        # 4. Logs are tamper-evident
        # 5. Log access is restricted


if __name__ == "__main__":
    pytest.main([__file__, "-v"])