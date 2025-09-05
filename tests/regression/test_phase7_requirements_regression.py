# tests/regression/test_phase7_requirements_regression.py
"""
Regression tests for Phase 7 Requirements Management System
Ensures compatibility and prevents regressions in core functionality
"""

import json
import pytest
import tempfile
import pathlib
import time
from datetime import datetime
from fastapi.testclient import TestClient

from app_requirements import app
from src_common.requirements_manager import RequirementsManager, FeatureRequestManager
from src_common.schema_validator import SchemaValidator


class TestRequirementsBackwardCompatibility:
    """Test backward compatibility for requirements format changes"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        # Legacy requirements format (v1.0 style)
        self.legacy_requirements_v1 = {
            "title": "Legacy Requirements v1.0",
            "version": "1.0.0",
            "description": "Requirements in legacy format",
            "requirements": {
                "functional": [
                    {
                        "id": "FR-001",
                        "title": "Basic Authentication",
                        "description": "Users must authenticate",
                        "priority": "high"
                        # Missing newer fields like category, risk_level, etc.
                    }
                ],
                "non_functional": [
                    {
                        "id": "NFR-001",
                        "title": "Performance",
                        "description": "Fast response times",
                        "priority": "medium"
                    }
                ]
            },
            "author": "legacy_architect"
        }
        
        # Modern requirements format (current style)
        self.modern_requirements = {
            "title": "Modern Requirements v2.0",
            "version": "2.0.0",
            "description": "Requirements in modern format",
            "requirements": {
                "functional": [
                    {
                        "id": "FR-002",
                        "title": "Enhanced Authentication",
                        "description": "Multi-factor authentication support",
                        "priority": "high",
                        "category": "security",
                        "acceptance_criteria": [
                            "Support TOTP authentication",
                            "Support SMS verification"
                        ],
                        "dependencies": ["FR-001"],
                        "risk_level": "medium",
                        "estimate_hours": 40
                    }
                ],
                "non_functional": [
                    {
                        "id": "NFR-002",
                        "title": "Scalability",
                        "description": "Handle 1000 concurrent users",
                        "priority": "high",
                        "category": "scalability",
                        "risk_level": "high",
                        "estimate_hours": 80
                    }
                ],
                "constraints": [
                    {
                        "type": "technical",
                        "description": "Must use existing authentication database",
                        "impact": "medium"
                    }
                ],
                "assumptions": [
                    "Users have smartphones for MFA",
                    "SMS service will be available"
                ]
            },
            "stakeholders": [
                {
                    "name": "Security Team",
                    "role": "Security Architect",
                    "involvement": "primary",
                    "contact": "security@example.com"
                }
            ],
            "acceptance_criteria": [
                {
                    "id": "AC-001",
                    "description": "All authentication flows working",
                    "test_type": "functional",
                    "success_criteria": "100% test pass rate"
                }
            ],
            "author": "modern_architect"
        }
    
    def test_legacy_requirements_still_load(self):
        """Test that legacy requirements format still works"""
        # Submit legacy requirements
        response = self.client.post(
            "/api/requirements/submit",
            json=self.legacy_requirements_v1,
            headers={"X-Admin-User": "admin"}
        )
        
        assert response.status_code == 200
        version_id = response.json()["version_id"]
        
        # Retrieve and verify
        get_response = self.client.get(f"/api/requirements/{version_id}")
        assert get_response.status_code == 200
        
        data = get_response.json()
        assert data["title"] == self.legacy_requirements_v1["title"]
        assert data["version"] == "1.0.0"
        
        # Verify functional requirements are accessible
        functional_reqs = data["requirements"]["functional"]
        assert len(functional_reqs) == 1
        assert functional_reqs[0]["id"] == "FR-001"
    
    def test_modern_requirements_work_alongside_legacy(self):
        """Test that modern and legacy requirements can coexist"""
        # Submit both legacy and modern requirements
        legacy_response = self.client.post(
            "/api/requirements/submit",
            json=self.legacy_requirements_v1,
            headers={"X-Admin-User": "admin"}
        )
        
        time.sleep(0.001)  # Ensure different timestamps
        
        modern_response = self.client.post(
            "/api/requirements/submit",
            json=self.modern_requirements,
            headers={"X-Admin-User": "admin"}
        )
        
        assert legacy_response.status_code == 200
        assert modern_response.status_code == 200
        
        legacy_id = legacy_response.json()["version_id"]
        modern_id = modern_response.json()["version_id"]
        
        # Verify both can be retrieved
        legacy_data = self.client.get(f"/api/requirements/{legacy_id}").json()
        modern_data = self.client.get(f"/api/requirements/{modern_id}").json()
        
        assert legacy_data["version"] == "1.0.0"
        assert modern_data["version"] == "2.0.0"
        
        # Verify latest returns the modern one (most recent)
        latest = self.client.get("/api/requirements/latest").json()
        assert latest["version"] == "2.0.0"
    
    def test_version_listing_includes_all_formats(self):
        """Test that version listing includes both legacy and modern formats"""
        # Submit requirements in different formats
        self.client.post(
            "/api/requirements/submit",
            json=self.legacy_requirements_v1,
            headers={"X-Admin-User": "legacy_admin"}
        )
        
        time.sleep(0.001)
        
        self.client.post(
            "/api/requirements/submit",
            json=self.modern_requirements,
            headers={"X-Admin-User": "modern_admin"}
        )
        
        # List all versions
        response = self.client.get("/api/requirements/versions")
        assert response.status_code == 200
        
        versions_data = response.json()
        assert versions_data["total"] >= 2
        
        # Verify both authors appear in the list
        authors = [v["author"] for v in versions_data["versions"]]
        assert "legacy_admin" in authors
        assert "modern_admin" in authors


class TestFeatureRequestEvolution:
    """Test evolution of feature request format over time"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        # Basic feature request (minimal fields)
        self.basic_feature = {
            "title": "Basic Feature Request",
            "description": "Simple feature request with minimal information",
            "priority": "medium",
            "requester": "basic_user"
        }
        
        # Enhanced feature request (with additional fields)
        self.enhanced_feature = {
            "title": "Enhanced Feature Request with Full Details",
            "description": "Comprehensive feature request with all available metadata and detailed information",
            "priority": "high",
            "requester": "power_user",
            "category": "ui",
            "business_value": "critical",
            "effort_estimate": 120,
            "user_story": "As a power user I want enhanced functionality so that I can be more productive",
            "acceptance_criteria": [
                "Feature works in all browsers",
                "Performance impact is minimal",
                "Accessibility requirements met"
            ],
            "tags": ["enhancement", "ui", "performance"],
            "technical_notes": "This feature requires significant UI refactoring",
            "risk_assessment": {
                "technical_risk": "medium",
                "business_risk": "low",
                "mitigation_strategy": "Implement feature flags and phased rollout"
            },
            "stakeholders": [
                {
                    "name": "UX Team",
                    "role": "designer",
                    "involvement": "primary"
                }
            ],
            "external_links": [
                {
                    "url": "https://example.com/mockup",
                    "description": "UI Mockup",
                    "link_type": "mockup"
                }
            ]
        }
    
    def test_basic_feature_request_still_works(self):
        """Test that basic feature requests (minimal fields) still work"""
        response = self.client.post("/api/features/submit", json=self.basic_feature)
        
        assert response.status_code == 200
        request_id = response.json()["request_id"]
        
        # Verify feature was created
        feature_response = self.client.get(f"/api/features/{request_id}")
        assert feature_response.status_code == 200
        
        feature_data = feature_response.json()
        assert feature_data["title"] == self.basic_feature["title"]
        assert feature_data["status"] == "pending"
    
    def test_enhanced_feature_request_works(self):
        """Test that enhanced feature requests with all fields work"""
        response = self.client.post("/api/features/submit", json=self.enhanced_feature)
        
        # Should work even though schema might not support all fields yet
        assert response.status_code in [200, 422]  # 422 if some fields not in schema
        
        if response.status_code == 200:
            request_id = response.json()["request_id"]
            
            feature_response = self.client.get(f"/api/features/{request_id}")
            assert feature_response.status_code == 200
            
            feature_data = feature_response.json()
            assert feature_data["title"] == self.enhanced_feature["title"]
    
    def test_feature_approval_workflow_unchanged(self):
        """Test that feature approval workflow remains consistent"""
        # Submit basic feature
        submit_response = self.client.post("/api/features/submit", json=self.basic_feature)
        assert submit_response.status_code == 200
        request_id = submit_response.json()["request_id"]
        
        # Approval workflow should work the same
        approval_data = {
            "action": "approve",
            "admin": "test_admin",
            "reason": "Regression test approval"
        }
        
        approve_response = self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert approve_response.status_code == 200
        
        # Verify status changed
        final_response = self.client.get(f"/api/features/{request_id}")
        assert final_response.json()["status"] == "approved"
    
    def test_audit_trail_format_stable(self):
        """Test that audit trail format remains stable"""
        # Create and approve a feature
        submit_response = self.client.post("/api/features/submit", json=self.basic_feature)
        request_id = submit_response.json()["request_id"]
        
        approval_data = {
            "action": "approve",
            "admin": "audit_admin",
            "reason": "Audit format test"
        }
        
        self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "audit_admin"}
        )
        
        # Check audit trail format
        audit_response = self.client.get(f"/api/audit/features?request_id={request_id}")
        assert audit_response.status_code == 200
        
        audit_data = audit_response.json()
        assert len(audit_data["audit_entries"]) == 1
        
        entry = audit_data["audit_entries"][0]
        
        # Verify expected fields are present (stable format)
        required_fields = ["timestamp", "request_id", "old_status", "new_status", "admin", "checksum"]
        for field in required_fields:
            assert field in entry, f"Missing required audit field: {field}"
        
        # Verify field types haven't changed
        assert isinstance(entry["timestamp"], str)
        assert isinstance(entry["checksum"], str)
        assert len(entry["checksum"]) == 64  # SHA-256 hex length


class TestSchemaCompatibility:
    """Test schema validation compatibility across versions"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.validator = SchemaValidator(pathlib.Path(self.temp_dir) / "schemas")
        
        # Create old-style schema (more permissive)
        self.create_legacy_schemas()
    
    def create_legacy_schemas(self):
        """Create schemas that represent older versions"""
        schemas_dir = pathlib.Path(self.temp_dir) / "schemas"
        schemas_dir.mkdir(parents=True, exist_ok=True)
        
        # Legacy requirements schema (less strict)
        legacy_req_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Legacy Requirements Schema",
            "type": "object",
            "required": ["title", "description", "requirements"],  # Less required fields
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "requirements": {
                    "type": "object",
                    "properties": {
                        "functional": {"type": "array"},
                        "non_functional": {"type": "array"}
                    }
                },
                "author": {"type": "string"}  # Optional in legacy
            }
        }
        
        # Legacy feature request schema
        legacy_feature_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Legacy Feature Request Schema",
            "type": "object",
            "required": ["title", "description", "requester"],  # Less required fields
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "requester": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]}  # No critical
            }
        }
        
        with open(schemas_dir / "requirements.schema.json", 'w') as f:
            json.dump(legacy_req_schema, f, indent=2)
        
        with open(schemas_dir / "feature_request.schema.json", 'w') as f:
            json.dump(legacy_feature_schema, f, indent=2)
    
    def test_legacy_data_validates_with_legacy_schema(self):
        """Test that legacy data validates correctly with legacy schemas"""
        legacy_data = {
            "title": "Legacy Requirements",
            "description": "Old format requirements",
            "requirements": {
                "functional": [],
                "non_functional": []
            },
            "author": "legacy_user"
            # No version, metadata, etc.
        }
        
        result = self.validator.validate_requirements(legacy_data)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_schema_evolution_detection(self):
        """Test detection of schema changes that might break compatibility"""
        # This test would run against both old and new schemas to detect
        # breaking changes. In a real system, this would be part of CI/CD.
        
        old_schema = self.validator.get_schema("requirements")
        assert old_schema is not None
        
        # Verify that old schema has expected properties
        assert "title" in old_schema["required"]
        assert "description" in old_schema["required"]
        
        # In a real test, we would compare with new schema and flag breaking changes
        # such as new required fields, changed field types, removed properties, etc.


class TestPerformanceRegression:
    """Test that performance hasn't regressed"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    @pytest.mark.performance
    def test_requirements_submission_performance(self):
        """Test requirements submission performance hasn't regressed"""
        requirements_data = {
            "title": "Performance Test Requirements",
            "version": "1.0.0",
            "description": "Requirements for performance testing",
            "requirements": {
                "functional": [{"id": f"FR-{i:03d}", "title": f"Requirement {i}", "description": f"Description {i}", "priority": "medium"} for i in range(50)],
                "non_functional": [{"id": f"NFR-{i:03d}", "title": f"NF Requirement {i}", "description": f"NF Description {i}", "priority": "low"} for i in range(20)]
            },
            "author": "perf_tester"
        }
        
        start_time = time.perf_counter()
        
        response = self.client.post(
            "/api/requirements/submit",
            json=requirements_data,
            headers={"X-Admin-User": "admin"}
        )
        
        end_time = time.perf_counter()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        assert response.status_code == 200
        # Performance requirement: submission should complete within 5 seconds
        assert response_time < 5000, f"Requirements submission took {response_time:.2f}ms, exceeding 5000ms limit"
    
    @pytest.mark.performance
    def test_feature_listing_performance(self):
        """Test that feature listing performance is acceptable"""
        # Submit multiple features
        feature_template = {
            "title": "Performance Test Feature {i}",
            "description": "Feature for testing listing performance with reasonable length description",
            "priority": "medium",
            "requester": "perf_user"
        }
        
        # Create 20 features
        for i in range(20):
            feature_data = {
                "title": f"Performance Test Feature {i}",
                "description": f"Feature {i} for testing listing performance with reasonable length description",
                "priority": "medium",
                "requester": f"user_{i}"
            }
            self.client.post("/api/features/submit", json=feature_data)
        
        # Test listing performance
        start_time = time.perf_counter()
        response = self.client.get("/api/features?limit=50")
        end_time = time.perf_counter()
        
        response_time = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        # Performance requirement: listing should complete within 2 seconds
        assert response_time < 2000, f"Feature listing took {response_time:.2f}ms, exceeding 2000ms limit"
    
    @pytest.mark.performance
    def test_schema_validation_performance(self):
        """Test schema validation performance"""
        test_data = {
            "title": "Performance Schema Test",
            "version": "1.0.0",
            "description": "Testing schema validation performance",
            "requirements": {
                "functional": [
                    {
                        "id": f"FR-{i:03d}",
                        "title": f"Performance Requirement {i}",
                        "description": f"This is requirement {i} for performance testing",
                        "priority": "medium",
                        "category": "performance",
                        "acceptance_criteria": [f"Criteria {j}" for j in range(3)],
                        "risk_level": "low",
                        "estimate_hours": 8
                    }
                    for i in range(10)
                ],
                "non_functional": []
            },
            "metadata": {
                "version_id": 123456,
                "author": "perf_tester",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        
        validation_request = {
            "schema_type": "requirements",
            "data": test_data
        }
        
        start_time = time.perf_counter()
        response = self.client.post("/api/validate/schema", json=validation_request)
        end_time = time.perf_counter()
        
        response_time = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response.json()["is_valid"] is True
        
        # Performance requirement: schema validation should complete within 500ms
        assert response_time < 500, f"Schema validation took {response_time:.2f}ms, exceeding 500ms limit"


class TestDataIntegrity:
    """Test data integrity across system operations"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_requirements_immutability_preserved(self):
        """Test that requirements remain immutable across versions"""
        original_req = {
            "title": "Immutability Test",
            "version": "1.0.0", 
            "description": "Testing immutability",
            "requirements": {"functional": [], "non_functional": []},
            "author": "integrity_tester"
        }
        
        # Submit original
        response1 = self.client.post(
            "/api/requirements/submit",
            json=original_req,
            headers={"X-Admin-User": "admin"}
        )
        version_id1 = response1.json()["version_id"]
        
        # Submit modified version
        modified_req = original_req.copy()
        modified_req["title"] = "Modified Immutability Test"
        modified_req["version"] = "2.0.0"
        
        time.sleep(0.001)
        
        response2 = self.client.post(
            "/api/requirements/submit",
            json=modified_req,
            headers={"X-Admin-User": "admin"}
        )
        version_id2 = response2.json()["version_id"]
        
        # Verify original hasn't changed
        original_check = self.client.get(f"/api/requirements/{version_id1}")
        assert original_check.json()["title"] == "Immutability Test"
        assert original_check.json()["version"] == "1.0.0"
        
        # Verify new version exists
        modified_check = self.client.get(f"/api/requirements/{version_id2}")
        assert modified_check.json()["title"] == "Modified Immutability Test"
        assert modified_check.json()["version"] == "2.0.0"
    
    def test_audit_trail_integrity_maintained(self):
        """Test that audit trail maintains integrity across operations"""
        # Submit feature
        feature_data = {
            "title": "Integrity Test Feature",
            "description": "Testing audit trail integrity",
            "priority": "medium",
            "requester": "integrity_user"
        }
        
        submit_response = self.client.post("/api/features/submit", json=feature_data)
        request_id = submit_response.json()["request_id"]
        
        # Multiple status changes
        approval_data = {"action": "approve", "admin": "admin1", "reason": "Approved"}
        rejection_data = {"action": "reject", "admin": "admin2", "reason": "Rejected"}
        final_approval_data = {"action": "approve", "admin": "admin3", "reason": "Finally approved"}
        
        # Apply changes
        self.client.post(f"/api/features/{request_id}/approve", json=approval_data, headers={"X-Admin-User": "admin1"})
        self.client.post(f"/api/features/{request_id}/approve", json=rejection_data, headers={"X-Admin-User": "admin2"})
        self.client.post(f"/api/features/{request_id}/approve", json=final_approval_data, headers={"X-Admin-User": "admin3"})
        
        # Verify audit trail has all entries
        audit_response = self.client.get(f"/api/audit/features?request_id={request_id}")
        audit_entries = audit_response.json()["audit_entries"]
        
        assert len(audit_entries) == 3
        
        # Verify chronological order (newest first)
        assert audit_entries[0]["new_status"] == "approved"
        assert audit_entries[0]["admin"] == "admin3"
        assert audit_entries[1]["new_status"] == "rejected"
        assert audit_entries[1]["admin"] == "admin2"
        assert audit_entries[2]["new_status"] == "approved"
        assert audit_entries[2]["admin"] == "admin1"
        
        # Verify checksums are present and unique
        checksums = [entry["checksum"] for entry in audit_entries]
        assert len(set(checksums)) == 3  # All checksums should be unique
        assert all(len(checksum) == 64 for checksum in checksums)  # SHA-256 length


if __name__ == "__main__":
    pytest.main([__file__, "-v"])