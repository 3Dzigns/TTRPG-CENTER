# src_common/requirements_manager.py
"""
Phase 7: Requirements Management Service
Immutable versioned requirements storage with schema validation
"""

import json
import time
import hashlib
import pathlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from src_common.ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class RequirementVersion:
    """Immutable requirement version metadata"""
    version_id: int
    timestamp: str
    author: str
    checksum: str
    file_path: str


@dataclass
class FeatureRequest:
    """Feature request data structure"""
    request_id: str
    title: str
    description: str
    priority: str  # high, medium, low
    requester: str
    status: str  # pending, approved, rejected
    created_at: str
    updated_at: Optional[str] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None


@dataclass
class AuditLogEntry:
    """Audit log entry for compliance tracking"""
    timestamp: str
    request_id: str
    old_status: str
    new_status: str
    admin: str
    reason: Optional[str] = None
    checksum: str = ""


class RequirementsManager:
    """Manages immutable requirements storage and versioning"""
    
    def __init__(self, base_path: pathlib.Path = None):
        self.base_path = base_path or pathlib.Path(".")
        self.requirements_dir = self.base_path / "requirements"
        self.features_dir = self.base_path / "features"
        self.audit_dir = self.base_path / "audit"
        self.schemas_dir = self.base_path / "schemas"
        
        # Ensure directories exist
        for dir_path in [self.requirements_dir, self.features_dir, self.audit_dir, self.schemas_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_checksum(self, data: str) -> str:
        """Generate SHA-256 checksum for data integrity"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def save_requirements(self, req: Dict[str, Any], author: str) -> int:
        """
        Save requirements as immutable versioned JSON (US-701)
        
        Args:
            req: Requirements data dictionary
            author: Author of the requirements
            
        Returns:
            version_id: Unique version identifier
            
        Raises:
            RuntimeError: If version already exists (immutability protection)
        """
        version_id = int(time.time() * 1000)  # Millisecond precision
        
        # Add version metadata
        req_with_metadata = req.copy()
        req_with_metadata["metadata"] = {
            "version_id": version_id,
            "author": author,
            "timestamp": datetime.now().isoformat(),
            "created_at": time.time()
        }
        
        # Generate file path
        file_path = self.requirements_dir / f"{version_id}.json"
        
        # Immutability check
        if file_path.exists():
            raise RuntimeError(f"Immutable violation: version {version_id} already exists")
        
        # Generate content and checksum
        content = json.dumps(req_with_metadata, indent=2)
        checksum = self._generate_checksum(content)
        req_with_metadata["metadata"]["checksum"] = checksum
        
        # Write final content with checksum
        final_content = json.dumps(req_with_metadata, indent=2)
        file_path.write_text(final_content, encoding='utf-8')
        
        logger.info(f"Saved requirements version {version_id} by {author}")
        return version_id
    
    def get_requirements_versions(self) -> List[RequirementVersion]:
        """Get all requirements versions with metadata"""
        versions = []
        
        for req_file in self.requirements_dir.glob("*.json"):
            try:
                content = req_file.read_text(encoding='utf-8')
                data = json.loads(content)
                metadata = data.get("metadata", {})
                
                version = RequirementVersion(
                    version_id=metadata.get("version_id", 0),
                    timestamp=metadata.get("timestamp", ""),
                    author=metadata.get("author", "unknown"),
                    checksum=metadata.get("checksum", ""),
                    file_path=str(req_file)
                )
                versions.append(version)
                
            except Exception as e:
                logger.error(f"Error reading requirements file {req_file}: {e}")
        
        # Sort by version_id descending (newest first)
        return sorted(versions, key=lambda x: x.version_id, reverse=True)
    
    def get_requirements_by_version(self, version_id: int) -> Optional[Dict[str, Any]]:
        """Load specific requirements version"""
        file_path = self.requirements_dir / f"{version_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            content = file_path.read_text(encoding='utf-8')
            data = json.loads(content)
            
            # Verify checksum integrity
            stored_checksum = data.get("metadata", {}).get("checksum", "")
            if stored_checksum:
                # Remove checksum for verification
                verify_data = data.copy()
                verify_data["metadata"].pop("checksum", None)
                verify_content = json.dumps(verify_data, indent=2)
                calculated_checksum = self._generate_checksum(verify_content)
                
                if stored_checksum != calculated_checksum:
                    logger.warning(f"Checksum mismatch for version {version_id}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading requirements version {version_id}: {e}")
            return None
    
    def get_latest_requirements(self) -> Optional[Dict[str, Any]]:
        """Get the most recent requirements version"""
        versions = self.get_requirements_versions()
        if not versions:
            return None
        
        latest = versions[0]  # Already sorted newest first
        return self.get_requirements_by_version(latest.version_id)


class FeatureRequestManager:
    """Manages feature request workflow with approval/rejection system"""
    
    def __init__(self, base_path: pathlib.Path = None):
        self.base_path = base_path or pathlib.Path(".")
        self.features_dir = self.base_path / "features"
        self.audit_dir = self.base_path / "audit"
        
        # Ensure directories exist
        for dir_path in [self.features_dir, self.audit_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        import random
        timestamp = str(int(time.time() * 1000))
        # Add random component to ensure uniqueness
        random_component = random.randint(1000, 9999)
        return f"FR-{timestamp}{random_component}"
    
    def submit_feature_request(self, title: str, description: str, 
                             priority: str, requester: str) -> str:
        """
        Submit new feature request (US-702)
        
        Args:
            title: Feature request title
            description: Detailed description
            priority: Priority level (high, medium, low)
            requester: Person submitting request
            
        Returns:
            request_id: Unique request identifier
        """
        request_id = self._generate_request_id()
        
        feature_request = FeatureRequest(
            request_id=request_id,
            title=title,
            description=description,
            priority=priority,
            requester=requester,
            status="pending",
            created_at=datetime.now().isoformat()
        )
        
        # Save to JSON file
        file_path = self.features_dir / f"{request_id}.json"
        content = json.dumps(asdict(feature_request), indent=2)
        file_path.write_text(content, encoding='utf-8')
        
        logger.info(f"Feature request {request_id} submitted by {requester}")
        return request_id
    
    def get_feature_request(self, request_id: str) -> Optional[FeatureRequest]:
        """Load specific feature request"""
        file_path = self.features_dir / f"{request_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            content = file_path.read_text(encoding='utf-8')
            data = json.loads(content)
            return FeatureRequest(**data)
        except Exception as e:
            logger.error(f"Error loading feature request {request_id}: {e}")
            return None
    
    def list_feature_requests(self, status: Optional[str] = None) -> List[FeatureRequest]:
        """List all feature requests, optionally filtered by status"""
        requests = []
        
        for req_file in self.features_dir.glob("FR-*.json"):
            try:
                content = req_file.read_text(encoding='utf-8')
                data = json.loads(content)
                feature_request = FeatureRequest(**data)
                
                if status is None or feature_request.status == status:
                    requests.append(feature_request)
                    
            except Exception as e:
                logger.error(f"Error reading feature request {req_file}: {e}")
        
        # Sort by created_at descending (newest first)
        return sorted(requests, key=lambda x: x.created_at, reverse=True)
    
    def approve_feature_request(self, request_id: str, admin: str, 
                               reason: Optional[str] = None) -> bool:
        """
        Approve feature request (US-703)
        
        Args:
            request_id: Request to approve
            admin: Admin making decision
            reason: Optional reason for approval
            
        Returns:
            bool: True if successful
        """
        return self._update_request_status(request_id, "approved", admin, reason)
    
    def reject_feature_request(self, request_id: str, admin: str, 
                              reason: Optional[str] = None) -> bool:
        """
        Reject feature request (US-703)
        
        Args:
            request_id: Request to reject
            admin: Admin making decision
            reason: Reason for rejection
            
        Returns:
            bool: True if successful
        """
        return self._update_request_status(request_id, "rejected", admin, reason)
    
    def _update_request_status(self, request_id: str, new_status: str, 
                             admin: str, reason: Optional[str] = None) -> bool:
        """Update request status with audit logging"""
        feature_request = self.get_feature_request(request_id)
        if not feature_request:
            return False
        
        old_status = feature_request.status
        
        # Update request
        feature_request.status = new_status
        feature_request.updated_at = datetime.now().isoformat()
        feature_request.approved_by = admin
        if reason:
            feature_request.rejection_reason = reason
        
        # Save updated request
        file_path = self.features_dir / f"{request_id}.json"
        content = json.dumps(asdict(feature_request), indent=2)
        file_path.write_text(content, encoding='utf-8')
        
        # Log audit entry
        self._log_audit_entry(request_id, old_status, new_status, admin, reason)
        
        logger.info(f"Feature request {request_id} status changed: {old_status} -> {new_status} by {admin}")
        return True
    
    def _log_audit_entry(self, request_id: str, old_status: str, 
                        new_status: str, admin: str, reason: Optional[str] = None):
        """Log audit entry for compliance (US-704)"""
        audit_entry = AuditLogEntry(
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            old_status=old_status,
            new_status=new_status,
            admin=admin,
            reason=reason
        )
        
        # Generate checksum for tamper detection
        entry_data = asdict(audit_entry)
        entry_data.pop("checksum")  # Remove checksum field
        entry_content = json.dumps(entry_data, sort_keys=True)
        audit_entry.checksum = hashlib.sha256(entry_content.encode()).hexdigest()
        
        # Append to audit log
        audit_file = self.audit_dir / "features.log"
        log_line = json.dumps(asdict(audit_entry)) + "\n"
        
        with open(audit_file, "a", encoding='utf-8') as f:
            f.write(log_line)
    
    def get_audit_trail(self, request_id: Optional[str] = None) -> List[AuditLogEntry]:
        """Get audit trail, optionally filtered by request_id"""
        audit_file = self.audit_dir / "features.log"
        
        if not audit_file.exists():
            return []
        
        entries = []
        try:
            with open(audit_file, "r", encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        entry = AuditLogEntry(**data)
                        
                        # Filter by request_id if specified
                        if request_id is None or entry.request_id == request_id:
                            entries.append(entry)
        except Exception as e:
            logger.error(f"Error reading audit trail: {e}")
        
        return sorted(entries, key=lambda x: x.timestamp, reverse=True)
    
    def validate_audit_integrity(self) -> List[str]:
        """Validate audit log integrity and return any tampered entries"""
        compromised_entries = []
        audit_file = self.audit_dir / "features.log"
        
        if not audit_file.exists():
            return compromised_entries
        
        try:
            with open(audit_file, "r", encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            stored_checksum = data.pop("checksum", "")
                            
                            # Recalculate checksum
                            content = json.dumps(data, sort_keys=True)
                            calculated_checksum = hashlib.sha256(content.encode()).hexdigest()
                            
                            if stored_checksum != calculated_checksum:
                                compromised_entries.append(f"Line {line_num}: checksum mismatch")
                                
                        except json.JSONDecodeError:
                            compromised_entries.append(f"Line {line_num}: invalid JSON")
                            
        except Exception as e:
            logger.error(f"Error validating audit integrity: {e}")
        
        return compromised_entries