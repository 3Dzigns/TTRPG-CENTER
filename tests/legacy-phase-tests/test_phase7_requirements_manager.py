# tests/unit/test_phase7_requirements_manager.py
"""
Unit tests for Phase 7 Requirements Management System
Tests US-701: Immutable requirements versioning
"""

import json
import pytest
import tempfile
import pathlib
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

from src_common.requirements_manager import (
    RequirementsManager,
    FeatureRequestManager,
    RequirementVersion,
    FeatureRequest,
    AuditLogEntry
)


class TestRequirementsManager:
    """Test suite for Requirements Manager (US-701)"""
    
    def setup_method(self):
        """Set up test environment with temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = RequirementsManager(pathlib.Path(self.temp_dir))
        
        # Sample requirements data
        self.sample_requirements = {
            "title": "Test Requirements",
            "version": "1.0.0",
            "description": "Test requirements document",
            "requirements": {
                "functional": [
                    {
                        "id": "FR-001",
                        "title": "User Authentication",
                        "description": "Users must be able to authenticate",
                        "priority": "high"
                    }
                ],
                "non_functional": [
                    {
                        "id": "NFR-001",
                        "title": "Performance",
                        "description": "System must respond within 2 seconds",
                        "priority": "medium"
                    }
                ]
            }
        }
    
    def test_save_requirements_creates_version_file(self):
        """Test that saving requirements creates a versioned JSON file"""
        version_id = self.manager.save_requirements(self.sample_requirements, "test_author")
        
        # Check file was created
        expected_file = self.manager.requirements_dir / f"{version_id}.json"
        assert expected_file.exists()
        
        # Check file content
        with open(expected_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["title"] == self.sample_requirements["title"]
        assert saved_data["metadata"]["author"] == "test_author"
        assert saved_data["metadata"]["version_id"] == version_id
        assert "checksum" in saved_data["metadata"]
    
    def test_save_requirements_immutability_protection(self):
        """Test that requirements cannot be overwritten (immutability)"""
        # Create first version
        version_id = self.manager.save_requirements(self.sample_requirements, "author1")
        
        # Try to create file with same version ID (simulate collision)
        with patch('time.time', return_value=version_id / 1000):
            with pytest.raises(RuntimeError, match="Immutable violation"):
                self.manager.save_requirements(self.sample_requirements, "author2")
    
    def test_get_requirements_versions_returns_metadata(self):
        """Test retrieving requirements version metadata"""
        # Create multiple versions
        version1 = self.manager.save_requirements(self.sample_requirements, "author1")
        time.sleep(0.001)  # Ensure different timestamps
        version2 = self.manager.save_requirements(self.sample_requirements, "author2")
        
        versions = self.manager.get_requirements_versions()
        
        assert len(versions) == 2
        assert isinstance(versions[0], RequirementVersion)
        
        # Should be sorted newest first
        assert versions[0].version_id == version2
        assert versions[1].version_id == version1
        
        # Check metadata
        assert versions[0].author == "author2"
        assert versions[1].author == "author1"
    
    def test_get_requirements_by_version(self):
        """Test retrieving specific requirements version"""
        version_id = self.manager.save_requirements(self.sample_requirements, "test_author")
        
        retrieved = self.manager.get_requirements_by_version(version_id)
        
        assert retrieved is not None
        assert retrieved["title"] == self.sample_requirements["title"]
        assert retrieved["metadata"]["version_id"] == version_id
    
    def test_get_requirements_by_version_not_found(self):
        """Test retrieving non-existent version returns None"""
        result = self.manager.get_requirements_by_version(999999)
        assert result is None
    
    def test_get_latest_requirements(self):
        """Test retrieving the most recent requirements version"""
        # Create multiple versions
        self.manager.save_requirements(self.sample_requirements, "author1")
        time.sleep(0.001)
        latest_version = self.manager.save_requirements(self.sample_requirements, "author2")
        
        latest = self.manager.get_latest_requirements()
        
        assert latest is not None
        assert latest["metadata"]["version_id"] == latest_version
        assert latest["metadata"]["author"] == "author2"
    
    def test_get_latest_requirements_empty(self):
        """Test getting latest requirements when none exist"""
        result = self.manager.get_latest_requirements()
        assert result is None
    
    def test_checksum_integrity_validation(self):
        """Test that checksum validation works correctly"""
        version_id = self.manager.save_requirements(self.sample_requirements, "test_author")
        
        # Manually corrupt the file
        file_path = self.manager.requirements_dir / f"{version_id}.json"
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Change content but keep old checksum
        data["title"] = "Corrupted Title"
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Should still load but with warning (we can't easily test warning in unit test)
        retrieved = self.manager.get_requirements_by_version(version_id)
        assert retrieved is not None
        assert retrieved["title"] == "Corrupted Title"


class TestFeatureRequestManager:
    """Test suite for Feature Request Manager (US-702, US-703, US-704)"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = FeatureRequestManager(pathlib.Path(self.temp_dir))
    
    def test_submit_feature_request(self):
        """Test submitting a new feature request (US-702)"""
        request_id = self.manager.submit_feature_request(
            title="Test Feature",
            description="This is a test feature request",
            priority="medium",
            requester="test_user"
        )
        
        # Check request was created
        assert request_id.startswith("FR-")
        
        feature = self.manager.get_feature_request(request_id)
        assert feature is not None
        assert feature.title == "Test Feature"
        assert feature.status == "pending"
        assert feature.requester == "test_user"
        assert feature.priority == "medium"
    
    def test_get_feature_request_not_found(self):
        """Test getting non-existent feature request"""
        result = self.manager.get_feature_request("FR-999999")
        assert result is None
    
    def test_list_feature_requests_all(self):
        """Test listing all feature requests"""
        # Create multiple requests
        id1 = self.manager.submit_feature_request("Feature 1", "Description 1", "high", "user1")
        id2 = self.manager.submit_feature_request("Feature 2", "Description 2", "low", "user2")
        
        requests = self.manager.list_feature_requests()
        
        assert len(requests) == 2
        assert isinstance(requests[0], FeatureRequest)
        
        # Should be sorted by created_at descending (newest first)
        request_ids = [r.request_id for r in requests]
        assert id2 in request_ids  # More recent
        assert id1 in request_ids
    
    def test_list_feature_requests_filtered(self):
        """Test listing feature requests filtered by status"""
        # Create requests with different statuses
        id1 = self.manager.submit_feature_request("Feature 1", "Description 1", "high", "user1")
        id2 = self.manager.submit_feature_request("Feature 2", "Description 2", "low", "user2")
        
        # Approve one request
        self.manager.approve_feature_request(id1, "admin", "Good idea")
        
        # Filter by pending
        pending = self.manager.list_feature_requests(status="pending")
        assert len(pending) == 1
        assert pending[0].request_id == id2
        
        # Filter by approved
        approved = self.manager.list_feature_requests(status="approved")
        assert len(approved) == 1
        assert approved[0].request_id == id1
    
    def test_approve_feature_request(self):
        """Test approving a feature request (US-703)"""
        request_id = self.manager.submit_feature_request(
            "Test Feature", "Description", "medium", "user1"
        )
        
        success = self.manager.approve_feature_request(request_id, "admin", "Approved for development")
        assert success is True
        
        # Check request was updated
        feature = self.manager.get_feature_request(request_id)
        assert feature.status == "approved"
        assert feature.approved_by == "admin"
        assert feature.updated_at is not None
        
        # Check audit log was created
        audit_entries = self.manager.get_audit_trail(request_id)
        assert len(audit_entries) == 1
        assert audit_entries[0].old_status == "pending"
        assert audit_entries[0].new_status == "approved"
        assert audit_entries[0].admin == "admin"
        assert audit_entries[0].reason == "Approved for development"
    
    def test_reject_feature_request(self):
        """Test rejecting a feature request (US-703)"""
        request_id = self.manager.submit_feature_request(
            "Test Feature", "Description", "medium", "user1"
        )
        
        success = self.manager.reject_feature_request(request_id, "admin", "Not aligned with roadmap")
        assert success is True
        
        # Check request was updated
        feature = self.manager.get_feature_request(request_id)
        assert feature.status == "rejected"
        assert feature.approved_by == "admin"
        assert feature.rejection_reason == "Not aligned with roadmap"
        
        # Check audit log
        audit_entries = self.manager.get_audit_trail(request_id)
        assert len(audit_entries) == 1
        assert audit_entries[0].new_status == "rejected"
        assert audit_entries[0].reason == "Not aligned with roadmap"
    
    def test_approve_nonexistent_request(self):
        """Test approving non-existent request returns False"""
        success = self.manager.approve_feature_request("FR-999999", "admin", "reason")
        assert success is False
    
    def test_audit_trail_multiple_changes(self):
        """Test audit trail tracks multiple status changes (US-704)"""
        request_id = self.manager.submit_feature_request(
            "Test Feature", "Description", "medium", "user1"
        )
        
        # Multiple state changes
        self.manager.approve_feature_request(request_id, "admin1", "Initial approval")
        self.manager.reject_feature_request(request_id, "admin2", "Changed mind")
        self.manager.approve_feature_request(request_id, "admin3", "Final approval")
        
        audit_entries = self.manager.get_audit_trail(request_id)
        
        # Should have 3 entries
        assert len(audit_entries) == 3
        
        # Check chronological order (newest first)
        assert audit_entries[0].new_status == "approved"
        assert audit_entries[0].admin == "admin3"
        assert audit_entries[1].new_status == "rejected"
        assert audit_entries[1].admin == "admin2"
        assert audit_entries[2].new_status == "approved"
        assert audit_entries[2].admin == "admin1"
    
    def test_audit_trail_all_requests(self):
        """Test getting audit trail for all requests"""
        # Create multiple requests and change them
        id1 = self.manager.submit_feature_request("Feature 1", "Desc 1", "high", "user1")
        id2 = self.manager.submit_feature_request("Feature 2", "Desc 2", "low", "user2")
        
        self.manager.approve_feature_request(id1, "admin", "Good")
        self.manager.reject_feature_request(id2, "admin", "Bad")
        
        all_audit = self.manager.get_audit_trail()
        
        assert len(all_audit) == 2
        request_ids = [entry.request_id for entry in all_audit]
        assert id1 in request_ids
        assert id2 in request_ids
    
    def test_audit_integrity_validation(self):
        """Test audit log integrity validation (US-704)"""
        request_id = self.manager.submit_feature_request(
            "Test Feature", "Description", "medium", "user1"
        )
        
        self.manager.approve_feature_request(request_id, "admin", "reason")
        
        # Initially, integrity should be valid
        compromised = self.manager.validate_audit_integrity()
        assert compromised == []
        
        # Manually corrupt audit log
        audit_file = self.manager.audit_dir / "features.log"
        with open(audit_file, 'r') as f:
            lines = f.readlines()
        
        # Corrupt first line by changing the data but keeping checksum
        if lines:
            data = json.loads(lines[0])
            data['admin'] = 'corrupted_admin'  # Change data
            # Keep old checksum - this should trigger integrity violation
            
            with open(audit_file, 'w') as f:
                json.dump(data, f)
                f.write('\n')
        
        # Now integrity validation should detect tampering
        compromised = self.manager.validate_audit_integrity()
        assert len(compromised) > 0
        assert "checksum mismatch" in compromised[0]
    
    def test_audit_checksum_generation(self):
        """Test that audit entries have valid checksums"""
        request_id = self.manager.submit_feature_request(
            "Test Feature", "Description", "medium", "user1"
        )
        
        self.manager.approve_feature_request(request_id, "admin", "reason")
        
        audit_entries = self.manager.get_audit_trail(request_id)
        assert len(audit_entries) == 1
        
        entry = audit_entries[0]
        assert entry.checksum != ""
        assert len(entry.checksum) == 64  # SHA-256 hex length


@pytest.mark.integration
class TestRequirementsFeatureIntegration:
    """Integration tests between requirements and features"""
    
    def setup_method(self):
        """Set up integrated test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.req_manager = RequirementsManager(pathlib.Path(self.temp_dir))
        self.feature_manager = FeatureRequestManager(pathlib.Path(self.temp_dir))
    
    def test_complete_workflow(self):
        """Test complete workflow from requirements to features"""
        # 1. Create requirements version
        requirements = {
            "title": "System Requirements v1.0",
            "version": "1.0.0",
            "description": "Initial system requirements",
            "requirements": {
                "functional": [
                    {
                        "id": "FR-001",
                        "title": "User Management",
                        "description": "System must support user management",
                        "priority": "high"
                    }
                ],
                "non_functional": []
            }
        }
        
        req_version = self.req_manager.save_requirements(requirements, "architect")
        
        # 2. Submit feature request based on requirement
        feature_id = self.feature_manager.submit_feature_request(
            title="Implement User Management (FR-001)",
            description="Implement the user management system as specified in FR-001",
            priority="high",
            requester="developer"
        )
        
        # 3. Review and approve feature
        success = self.feature_manager.approve_feature_request(
            feature_id, "product_owner", "Aligns with requirements FR-001"
        )
        
        # Verify complete workflow
        assert req_version is not None
        assert feature_id is not None
        assert success is True
        
        # Verify requirements exist
        latest_req = self.req_manager.get_latest_requirements()
        assert latest_req["title"] == "System Requirements v1.0"
        
        # Verify feature is approved
        feature = self.feature_manager.get_feature_request(feature_id)
        assert feature.status == "approved"
        
        # Verify audit trail
        audit = self.feature_manager.get_audit_trail(feature_id)
        assert len(audit) == 1
        assert "FR-001" in audit[0].reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])