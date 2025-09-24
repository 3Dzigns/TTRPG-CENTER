# tests/functional/test_phase7_requirements_api.py
"""
Functional tests for Phase 7 Requirements Management API
Tests complete workflows and API integration
"""

import json
import pytest
import tempfile
import pathlib
import time
from datetime import datetime
from httpx import AsyncClient
from fastapi.testclient import TestClient

# Import the FastAPI app
from app_requirements import app
from src_common.requirements_manager import RequirementsManager, FeatureRequestManager
from src_common.schema_validator import SchemaValidator


class TestRequirementsAPI:
    """Functional tests for Requirements Management API"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        # Create sample data for testing
        self.valid_requirements = {
            "title": "Test Requirements Document",
            "version": "1.0.0",
            "description": "Comprehensive test requirements for TTRPG Center",
            "requirements": {
                "functional": [
                    {
                        "id": "FR-001",
                        "title": "User Authentication",
                        "description": "Users must be able to authenticate securely",
                        "priority": "high",
                        "category": "security"
                    }
                ],
                "non_functional": [
                    {
                        "id": "NFR-001",
                        "title": "Response Time",
                        "description": "API responses must be under 2 seconds",
                        "priority": "medium",
                        "category": "performance"
                    }
                ]
            },
            "stakeholders": [
                {
                    "name": "Product Owner",
                    "role": "Requirements Owner",
                    "involvement": "primary"
                }
            ],
            "author": "test_architect"
        }
        
        self.valid_feature = {
            "title": "Enhanced User Profile Management",
            "description": "Users should be able to manage their profiles with advanced customization options including avatar upload, bio, and preferences",
            "priority": "medium",
            "requester": "product_team",
            "category": "ui",
            "business_value": "high",
            "user_story": "As a user I want to customize my profile so that I can personalize my experience"
        }
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "requirements"
        assert data["phase"] == "7"
    
    def test_requirements_dashboard_loads(self):
        """Test that requirements dashboard loads successfully"""
        response = self.client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        
        # Check for key dashboard elements in HTML
        content = response.text
        assert "Phase 7" in content
        assert "Requirements & Features" in content
        assert "TTRPG Center" in content
    
    def test_submit_requirements_valid(self):
        """Test submitting valid requirements (US-701)"""
        response = self.client.post(
            "/api/requirements/submit",
            json=self.valid_requirements,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "version_id" in data
        assert isinstance(data["version_id"], int)
        assert "saved successfully" in data["message"]
    
    def test_submit_requirements_unauthorized(self):
        """Test submitting requirements without admin permissions"""
        response = self.client.post(
            "/api/requirements/submit",
            json=self.valid_requirements
            # No X-Admin-User header
        )
        
        assert response.status_code == 401
        assert "Admin authentication required" in response.json()["detail"]
    
    def test_submit_requirements_invalid_schema(self):
        """Test submitting requirements with invalid schema"""
        invalid_requirements = self.valid_requirements.copy()
        invalid_requirements["version"] = "invalid-version"  # Invalid version format
        del invalid_requirements["requirements"]  # Remove required field
        
        response = self.client.post(
            "/api/requirements/submit",
            json=invalid_requirements,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert response.status_code == 400
        assert "Schema validation failed" in response.json()["detail"]
    
    def test_submit_requirements_xss_attempt(self):
        """Test submitting requirements with XSS attempt"""
        xss_requirements = self.valid_requirements.copy()
        xss_requirements["title"] = "<script>alert('xss')</script>"
        xss_requirements["description"] = "javascript:malicious_function()"
        
        response = self.client.post(
            "/api/requirements/submit",
            json=xss_requirements,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert response.status_code == 400
        assert "dangerous content detected" in response.json()["detail"]
    
    def test_list_requirements_versions(self):
        """Test listing requirements versions"""
        # First submit a requirements version
        self.client.post(
            "/api/requirements/submit",
            json=self.valid_requirements,
            headers={"X-Admin-User": "test_admin"}
        )
        
        response = self.client.get("/api/requirements/versions")
        
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert "total" in data
        assert data["total"] >= 1
        
        if data["versions"]:
            version = data["versions"][0]
            assert "version_id" in version
            assert "timestamp" in version
            assert "author" in version
            assert "checksum" in version
    
    def test_get_requirements_by_version(self):
        """Test retrieving specific requirements version"""
        # Submit requirements first
        submit_response = self.client.post(
            "/api/requirements/submit",
            json=self.valid_requirements,
            headers={"X-Admin-User": "test_admin"}
        )
        version_id = submit_response.json()["version_id"]
        
        # Retrieve the version
        response = self.client.get(f"/api/requirements/{version_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == self.valid_requirements["title"]
        assert data["version"] == self.valid_requirements["version"]
        assert data["metadata"]["version_id"] == version_id
        assert data["metadata"]["author"] == "test_admin"  # Should use header value
    
    def test_get_requirements_version_not_found(self):
        """Test retrieving non-existent requirements version"""
        response = self.client.get("/api/requirements/999999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_get_latest_requirements(self):
        """Test retrieving latest requirements version"""
        # Submit multiple versions
        req1 = self.valid_requirements.copy()
        req1["version"] = "1.0.0"
        
        req2 = self.valid_requirements.copy()
        req2["version"] = "2.0.0"
        req2["title"] = "Updated Requirements"
        
        self.client.post("/api/requirements/submit", json=req1, headers={"X-Admin-User": "admin1"})
        time.sleep(0.001)  # Ensure different timestamps
        self.client.post("/api/requirements/submit", json=req2, headers={"X-Admin-User": "admin2"})
        
        response = self.client.get("/api/requirements/latest")
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"
        assert data["title"] == "Updated Requirements"


class TestFeatureRequestAPI:
    """Functional tests for Feature Request API"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        self.valid_feature = {
            "title": "Enhanced User Profile Management",
            "description": "Users should be able to manage their profiles with advanced customization options including avatar upload, bio, and preferences",
            "priority": "medium",
            "requester": "product_team",
            "category": "ui",
            "business_value": "high",
            "user_story": "As a user I want to customize my profile so that I can personalize my experience"
        }
    
    def test_submit_feature_request_valid(self):
        """Test submitting valid feature request (US-702)"""
        response = self.client.post("/api/features/submit", json=self.valid_feature)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "request_id" in data
        assert data["request_id"].startswith("FR-")
        assert "submitted successfully" in data["message"]
    
    def test_submit_feature_request_invalid(self):
        """Test submitting invalid feature request"""
        invalid_feature = {
            "title": "Bad",  # Too short (min 5 chars)
            "description": "Short",  # Too short (min 10 chars)
            "priority": "invalid",  # Not in allowed enum
            "requester": "",  # Empty string
        }
        
        response = self.client.post("/api/features/submit", json=invalid_feature)
        
        assert response.status_code == 400
        assert "Schema validation failed" in response.json()["detail"]
    
    def test_submit_feature_request_xss(self):
        """Test submitting feature request with XSS content"""
        xss_feature = self.valid_feature.copy()
        xss_feature["title"] = "<script>alert('hack')</script>"
        xss_feature["description"] = "onclick=malicious() This is dangerous content"
        
        response = self.client.post("/api/features/submit", json=xss_feature)
        
        assert response.status_code == 400
        assert "dangerous content detected" in response.json()["detail"]
    
    def test_submit_feature_invalid_user_story(self):
        """Test submitting feature with invalid user story format"""
        invalid_story_feature = self.valid_feature.copy()
        invalid_story_feature["user_story"] = "This is not a proper user story format"
        
        response = self.client.post("/api/features/submit", json=invalid_story_feature)
        
        assert response.status_code == 422  # Pydantic validation error
        assert "User story must follow format" in str(response.json())
    
    def test_list_feature_requests_all(self):
        """Test listing all feature requests"""
        # Submit a feature request first
        self.client.post("/api/features/submit", json=self.valid_feature)
        
        response = self.client.get("/api/features")
        
        assert response.status_code == 200
        data = response.json()
        assert "features" in data
        assert "total" in data
        assert data["total"] >= 1
        
        if data["features"]:
            feature = data["features"][0]
            assert "request_id" in feature
            assert "title" in feature
            assert "status" in feature
            assert "priority" in feature
    
    def test_list_feature_requests_filtered(self):
        """Test listing feature requests filtered by status"""
        # Submit and approve a feature
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        approval_data = {
            "action": "approve",
            "admin": "test_admin",
            "reason": "Good idea"
        }
        self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "test_admin"}
        )
        
        # Test filtering by approved status
        response = self.client.get("/api/features?status=approved")
        
        assert response.status_code == 200
        data = response.json()
        assert data["filtered_by_status"] == "approved"
        
        # All returned features should have approved status
        for feature in data["features"]:
            assert feature["status"] == "approved"
    
    def test_get_feature_request_details(self):
        """Test retrieving specific feature request details"""
        # Submit feature first
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        response = self.client.get(f"/api/features/{request_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == request_id
        assert data["title"] == self.valid_feature["title"]
        assert data["status"] == "pending"
        assert data["requester"] == self.valid_feature["requester"]
    
    def test_get_feature_request_not_found(self):
        """Test retrieving non-existent feature request"""
        response = self.client.get("/api/features/FR-999999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_approve_feature_request(self):
        """Test approving feature request (US-703)"""
        # Submit feature first
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        # Approve the feature
        approval_data = {
            "action": "approve",
            "admin": "test_admin",
            "reason": "Aligns with product roadmap"
        }
        
        response = self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "approved successfully" in data["message"]
        
        # Verify feature status changed
        feature_response = self.client.get(f"/api/features/{request_id}")
        feature_data = feature_response.json()
        assert feature_data["status"] == "approved"
        assert feature_data["approved_by"] == "test_admin"
    
    def test_reject_feature_request(self):
        """Test rejecting feature request (US-703)"""
        # Submit feature first
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        # Reject the feature
        rejection_data = {
            "action": "reject",
            "admin": "test_admin",
            "reason": "Does not align with current priorities"
        }
        
        response = self.client.post(
            f"/api/features/{request_id}/approve",
            json=rejection_data,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "rejected successfully" in data["message"]
        
        # Verify feature status changed
        feature_response = self.client.get(f"/api/features/{request_id}")
        feature_data = feature_response.json()
        assert feature_data["status"] == "rejected"
        assert feature_data["rejection_reason"] == "Does not align with current priorities"
    
    def test_approve_feature_unauthorized(self):
        """Test approving feature without admin permissions"""
        # Submit feature first
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        approval_data = {
            "action": "approve",
            "admin": "test_admin",
            "reason": "Good idea"
        }
        
        response = self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data
            # No X-Admin-User header
        )
        
        assert response.status_code == 401
        assert "Admin authentication required" in response.json()["detail"]
    
    def test_approve_nonexistent_feature(self):
        """Test approving non-existent feature request"""
        approval_data = {
            "action": "approve",
            "admin": "test_admin",
            "reason": "Good idea"
        }
        
        response = self.client.post(
            "/api/features/FR-999999/approve",
            json=approval_data,
            headers={"X-Admin-User": "test_admin"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestAuditTrailAPI:
    """Functional tests for Audit Trail API"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
        
        self.valid_feature = {
            "title": "Test Feature for Audit",
            "description": "Feature request specifically for testing audit trail functionality",
            "priority": "medium",
            "requester": "test_user"
        }
    
    def test_get_audit_trail_empty(self):
        """Test getting audit trail when no entries exist"""
        response = self.client.get("/api/audit/features")
        
        assert response.status_code == 200
        data = response.json()
        assert "audit_entries" in data
        assert "total" in data
        assert data["total"] == 0
        assert data["audit_entries"] == []
    
    def test_get_audit_trail_with_entries(self):
        """Test getting audit trail with actual entries (US-704)"""
        # Submit and approve a feature to create audit entries
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        # Approve the feature
        approval_data = {
            "action": "approve",
            "admin": "admin1",
            "reason": "Initial approval"
        }
        self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "admin1"}
        )
        
        # Reject the feature (change of mind)
        rejection_data = {
            "action": "reject",
            "admin": "admin2",
            "reason": "Changed priorities"
        }
        self.client.post(
            f"/api/features/{request_id}/approve",
            json=rejection_data,
            headers={"X-Admin-User": "admin2"}
        )
        
        # Get audit trail
        response = self.client.get("/api/audit/features")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        
        # Check audit entries
        entries = data["audit_entries"]
        assert len(entries) >= 2
        
        # Check that entries contain expected fields
        for entry in entries:
            assert "timestamp" in entry
            assert "request_id" in entry
            assert "old_status" in entry
            assert "new_status" in entry
            assert "admin" in entry
            assert "checksum" in entry
        
        # Entries should be sorted by timestamp (newest first)
        if len(entries) >= 2:
            assert entries[0]["new_status"] == "rejected"  # Most recent
            assert entries[1]["new_status"] == "approved"  # Previous
    
    def test_get_audit_trail_filtered(self):
        """Test getting audit trail filtered by request ID"""
        # Submit two features
        feature1 = self.valid_feature.copy()
        feature1["title"] = "Feature 1"
        feature2 = self.valid_feature.copy()
        feature2["title"] = "Feature 2"
        
        response1 = self.client.post("/api/features/submit", json=feature1)
        response2 = self.client.post("/api/features/submit", json=feature2)
        
        request_id1 = response1.json()["request_id"]
        request_id2 = response2.json()["request_id"]
        
        # Approve both features
        approval_data = {"action": "approve", "admin": "admin", "reason": "Good"}
        self.client.post(
            f"/api/features/{request_id1}/approve",
            json=approval_data,
            headers={"X-Admin-User": "admin"}
        )
        self.client.post(
            f"/api/features/{request_id2}/approve",
            json=approval_data,
            headers={"X-Admin-User": "admin"}
        )
        
        # Get audit trail filtered by request_id1
        response = self.client.get(f"/api/audit/features?request_id={request_id1}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["filtered_by_request"] == request_id1
        
        # All entries should be for request_id1
        for entry in data["audit_entries"]:
            assert entry["request_id"] == request_id1
    
    def test_validate_audit_integrity(self):
        """Test audit integrity validation (US-704)"""
        # Create some audit entries first
        submit_response = self.client.post("/api/features/submit", json=self.valid_feature)
        request_id = submit_response.json()["request_id"]
        
        approval_data = {"action": "approve", "admin": "admin", "reason": "Test"}
        self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "admin"}
        )
        
        # Validate integrity
        response = self.client.get(
            "/api/audit/integrity",
            headers={"X-Admin-User": "admin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "integrity_valid" in data
        assert "compromised_entries" in data
        assert "total_compromised" in data
        assert "validation_timestamp" in data
        
        # Initially, integrity should be valid
        assert data["integrity_valid"] is True
        assert data["total_compromised"] == 0
    
    def test_validate_audit_integrity_unauthorized(self):
        """Test audit integrity validation without admin permissions"""
        response = self.client.get("/api/audit/integrity")
        
        assert response.status_code == 401
        assert "Admin authentication required" in response.json()["detail"]


class TestSchemaValidationAPI:
    """Functional tests for Schema Validation API"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_validate_requirements_schema_valid(self):
        """Test validating valid requirements data against schema (US-705)"""
        valid_data = {
            "title": "Test Requirements",
            "version": "1.0.0",
            "description": "Test description",
            "requirements": {
                "functional": [],
                "non_functional": []
            },
            "metadata": {
                "version_id": 123456,
                "author": "test_author",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        
        validation_request = {
            "schema_type": "requirements",
            "data": valid_data
        }
        
        response = self.client.post("/api/validate/schema", json=validation_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["errors"] == []
        assert data["schema_name"] == "requirements"
        assert data["validation_time_ms"] > 0
    
    def test_validate_requirements_schema_invalid(self):
        """Test validating invalid requirements data against schema"""
        invalid_data = {
            "title": "",  # Invalid - empty
            "version": "bad-version",  # Invalid format
            # Missing required fields
        }
        
        validation_request = {
            "schema_type": "requirements",
            "data": invalid_data
        }
        
        response = self.client.post("/api/validate/schema", json=validation_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0
        
        # Check error structure
        error = data["errors"][0]
        assert "field_path" in error
        assert "message" in error
        assert "invalid_value" in error
        assert "schema_path" in error
    
    def test_validate_feature_request_schema_valid(self):
        """Test validating valid feature request data against schema (US-706)"""
        valid_data = {
            "request_id": "FR-123456",
            "title": "Valid Feature Request",
            "description": "This is a valid feature request description",
            "priority": "medium",
            "requester": "test_user",
            "status": "pending",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        validation_request = {
            "schema_type": "feature_request",
            "data": valid_data
        }
        
        response = self.client.post("/api/validate/schema", json=validation_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["errors"] == []
        assert data["schema_name"] == "feature_request"
    
    def test_validate_invalid_schema_type(self):
        """Test validation with invalid schema type"""
        validation_request = {
            "schema_type": "invalid_schema",
            "data": {"test": "data"}
        }
        
        response = self.client.post("/api/validate/schema", json=validation_request)
        
        assert response.status_code == 400
        assert "Invalid schema type" in response.json()["detail"]
    
    def test_get_available_schemas(self):
        """Test getting list of available schemas"""
        response = self.client.get("/api/schemas")
        
        assert response.status_code == 200
        data = response.json()
        assert "schemas" in data
        assert "total" in data
        
        # Should have at least requirements and feature_request schemas
        schema_names = [schema["name"] for schema in data["schemas"]]
        assert "requirements" in schema_names
        assert "feature_request" in schema_names
        
        # Check schema structure
        for schema in data["schemas"]:
            assert "name" in schema
            assert "title" in schema
            assert "description" in schema
    
    def test_get_validation_report(self):
        """Test getting comprehensive validation report"""
        response = self.client.get(
            "/api/validation/report",
            headers={"X-Admin-User": "admin"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "requirements_validation" in data
        assert "features_validation" in data
        assert "overall_summary" in data
        
        # Check report structure
        req_report = data["requirements_validation"]
        assert "summary" in req_report
        assert "errors" in req_report
        assert "timestamp" in req_report
        
        # Check summary structure
        summary = req_report["summary"]
        assert "total_files" in summary
        assert "valid_files" in summary
        assert "invalid_files" in summary
        assert "validation_success_rate" in summary
    
    def test_get_validation_report_unauthorized(self):
        """Test getting validation report without admin permissions"""
        response = self.client.get("/api/validation/report")
        
        assert response.status_code == 401
        assert "Admin authentication required" in response.json()["detail"]


@pytest.mark.integration
class TestCompleteWorkflow:
    """Integration tests for complete requirements management workflow"""
    
    def setup_method(self):
        """Set up test environment"""
        self.client = TestClient(app)
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow from requirements to feature approval"""
        # 1. Submit requirements version
        requirements_data = {
            "title": "E2E Test Requirements",
            "version": "1.0.0",
            "description": "End-to-end test requirements document",
            "requirements": {
                "functional": [
                    {
                        "id": "FR-001",
                        "title": "Feature Management",
                        "description": "System must support feature request management",
                        "priority": "high"
                    }
                ],
                "non_functional": []
            },
            "author": "system_architect"
        }
        
        req_response = self.client.post(
            "/api/requirements/submit",
            json=requirements_data,
            headers={"X-Admin-User": "architect"}
        )
        assert req_response.status_code == 200
        version_id = req_response.json()["version_id"]
        
        # 2. Submit feature request based on requirement
        feature_data = {
            "title": "Implement Feature Management (FR-001)",
            "description": "Implement the feature request management system as specified in requirement FR-001",
            "priority": "high",
            "requester": "development_team",
            "user_story": "As a product owner I want to manage feature requests so that I can prioritize development work"
        }
        
        feature_response = self.client.post("/api/features/submit", json=feature_data)
        assert feature_response.status_code == 200
        request_id = feature_response.json()["request_id"]
        
        # 3. Review feature request
        feature_detail = self.client.get(f"/api/features/{request_id}")
        assert feature_detail.status_code == 200
        assert feature_detail.json()["status"] == "pending"
        
        # 4. Approve feature request
        approval_data = {
            "action": "approve",
            "admin": "product_owner",
            "reason": f"Aligns with requirement FR-001 from version {version_id}"
        }
        
        approval_response = self.client.post(
            f"/api/features/{request_id}/approve",
            json=approval_data,
            headers={"X-Admin-User": "product_owner"}
        )
        assert approval_response.status_code == 200
        
        # 5. Verify final state
        final_feature = self.client.get(f"/api/features/{request_id}")
        assert final_feature.json()["status"] == "approved"
        assert final_feature.json()["approved_by"] == "product_owner"
        
        # 6. Check audit trail
        audit_response = self.client.get(f"/api/audit/features?request_id={request_id}")
        audit_data = audit_response.json()
        assert len(audit_data["audit_entries"]) == 1
        assert audit_data["audit_entries"][0]["new_status"] == "approved"
        assert f"version {version_id}" in audit_data["audit_entries"][0]["reason"]
        
        # 7. Verify requirements still accessible
        final_req = self.client.get(f"/api/requirements/{version_id}")
        assert final_req.status_code == 200
        assert final_req.json()["title"] == "E2E Test Requirements"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])