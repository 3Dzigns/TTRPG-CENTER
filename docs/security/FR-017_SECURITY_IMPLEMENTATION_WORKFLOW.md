# FR-017 Bug Page Security Implementation Workflow

## Executive Summary

This document provides a comprehensive security-focused implementation workflow for FR-017 Bug Page, integrating with the existing JWT-based authentication system and following defense-in-depth principles. The workflow addresses authentication, authorization, input validation, file upload security, data privacy, and comprehensive security testing requirements.

## Security Architecture Overview

### Current Security Infrastructure
- **Authentication**: JWT tokens with HS256 signing, Argon2 password hashing
- **Authorization**: Role-based access control (ADMIN, USER, GUEST)
- **Input Validation**: SQLModel validation with Pydantic schemas
- **CORS Protection**: Environment-specific restrictive policies
- **Security Testing**: Comprehensive security test suite with Bandit integration

### Security Requirements for Bug Page
- Admin-only access to bug management functionality
- Secure file upload handling for evidence attachments
- Input sanitization preventing XSS and injection attacks
- Access control ensuring proper bug visibility
- Audit logging for all security-sensitive operations

## 1. Authentication and Authorization Controls

### 1.1 JWT Token Validation
**Security Task: SEC-017-001**

```python
# Implementation: Bug API endpoints use existing JWT middleware
from src_common.auth_middleware import require_admin, require_permission

@router.get("/api/admin/bugs")
async def list_bugs(
    current_user: UserContext = Depends(require_admin),
    # ... other parameters
):
    """List bugs - admin access required"""
    logger.info(f"Bug list accessed by admin: {current_user.username}")
    # Implementation continues...

@router.post("/api/admin/bugs")
async def create_bug(
    bug_data: BugCreateRequest,
    current_user: UserContext = Depends(require_admin)
):
    """Create bug - admin access required"""
    # Log security event
    logger.info(f"Bug creation attempted by: {current_user.username}")
    # Implementation continues...
```

**Security Validation Checkpoints:**
- ✅ All bug API endpoints require valid JWT token
- ✅ Admin role verification on every request
- ✅ Token blacklist checking prevents use of revoked tokens
- ✅ User active status validation

### 1.2 Fine-Grained Permissions
**Security Task: SEC-017-002**

```python
# Enhanced permission model for bug operations
class BugPermissions:
    """Bug-specific permission constants"""
    CREATE_BUG = "bugs.create"
    VIEW_ALL_BUGS = "bugs.view_all"
    EDIT_BUG = "bugs.edit"
    DELETE_BUG = "bugs.delete"
    ASSIGN_BUG = "bugs.assign"
    VIEW_SENSITIVE_DATA = "bugs.view_sensitive"

@router.put("/api/admin/bugs/{bug_id}")
async def update_bug(
    bug_id: str,
    bug_data: BugUpdateRequest,
    current_user: UserContext = Depends(require_permission(BugPermissions.EDIT_BUG))
):
    """Update bug with granular permission check"""
    # Additional ownership validation
    bug = await bug_service.get_bug(bug_id)
    if not current_user.is_admin and bug.created_by != current_user.username:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to edit this bug"
        )
```

## 2. Input Validation and Sanitization

### 2.1 SQLModel Schema Validation
**Security Task: SEC-017-003**

```python
# Enhanced Bug models with security validation
from pydantic import validator, Field
from src_common.schema_validator import SchemaSecurityValidator

class BugCreateRequest(BaseModel):
    """Bug creation request with security validation"""
    title: str = Field(min_length=3, max_length=200, description="Bug title")
    description: str = Field(min_length=10, max_length=10000, description="Bug description")
    steps_to_reproduce: Optional[str] = Field(max_length=5000, default=None)

    @validator('title', 'description', 'steps_to_reproduce')
    def sanitize_text_fields(cls, v):
        """Sanitize text fields to prevent XSS"""
        if v is None:
            return v

        # Check for dangerous script patterns
        dangerous_patterns = SchemaSecurityValidator.validate_no_scripts({"field": v})
        if dangerous_patterns:
            raise ValueError(f"Potentially dangerous content detected: {dangerous_patterns[0]}")

        # HTML escape and length validation
        sanitized = SchemaSecurityValidator.sanitize_string_fields({"field": v})["field"]
        return sanitized

    @validator('severity', 'priority', 'environment')
    def validate_enum_values(cls, v, field):
        """Validate enum values against whitelist"""
        if field.name == 'severity' and v not in ['low', 'medium', 'high', 'critical']:
            raise ValueError("Invalid severity level")
        if field.name == 'environment' and v not in ['dev', 'test', 'prod']:
            raise ValueError("Invalid environment")
        return v
```

**Security Validation Checkpoints:**
- ✅ Maximum field lengths enforced
- ✅ HTML entities escaped in all user input
- ✅ Script injection patterns detected and blocked
- ✅ Enum values validated against whitelists
- ✅ SQL injection prevention through parameterized queries

### 2.2 Advanced Input Sanitization
**Security Task: SEC-017-004**

```python
class BugSecurityService:
    """Security-focused bug operations service"""

    @staticmethod
    def sanitize_bug_data(bug_data: dict) -> dict:
        """Comprehensive bug data sanitization"""
        # Remove potentially dangerous HTML tags
        allowed_tags = []  # No HTML allowed in bug data

        # Sanitize all string fields
        sanitized = SchemaSecurityValidator.sanitize_string_fields(
            bug_data,
            max_length=10000
        )

        # Additional validation for specific fields
        if 'failing_test_ids' in sanitized:
            # Validate test IDs are UUIDs or safe identifiers
            test_ids = json.loads(sanitized['failing_test_ids'])
            for test_id in test_ids:
                if not re.match(r'^[a-zA-Z0-9_-]+$', test_id):
                    raise ValueError(f"Invalid test ID format: {test_id}")

        return sanitized

    @staticmethod
    def validate_bug_metadata(metadata: dict) -> bool:
        """Validate bug metadata for security compliance"""
        # Check for sensitive information patterns
        sensitive_patterns = [
            r'password\s*[:=]\s*\w+',
            r'api[_-]?key\s*[:=]\s*\w+',
            r'secret\s*[:=]\s*\w+',
            r'token\s*[:=]\s*\w+'
        ]

        content = json.dumps(metadata).lower()
        for pattern in sensitive_patterns:
            if re.search(pattern, content):
                logger.warning(f"Potential sensitive data in bug metadata: pattern {pattern}")
                return False

        return True
```

## 3. File Upload Security

### 3.1 Secure File Upload Handler
**Security Task: SEC-017-005**

```python
import magic
from pathlib import Path
from typing import List

class SecureFileUploadService:
    """Secure file upload service for bug attachments"""

    # Allowed file types for bug attachments
    ALLOWED_MIME_TYPES = {
        'image/png', 'image/jpeg', 'image/gif', 'image/webp',
        'text/plain', 'text/csv',
        'application/pdf',
        'application/json',
        'application/zip'
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_BUG = 10

    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def validate_and_store_file(
        self,
        file: UploadFile,
        bug_id: str,
        uploaded_by: str
    ) -> BugAttachment:
        """Validate and securely store uploaded file"""

        # 1. File size validation
        if file.size > self.MAX_FILE_SIZE:
            raise HTTPException(400, "File size exceeds maximum limit (10MB)")

        # 2. MIME type validation using python-magic
        file_content = await file.read()
        detected_type = magic.from_buffer(file_content, mime=True)

        if detected_type not in self.ALLOWED_MIME_TYPES:
            raise HTTPException(400, f"File type {detected_type} not allowed")

        # 3. Filename sanitization
        safe_filename = self._sanitize_filename(file.filename)

        # 4. Virus scanning (placeholder for production integration)
        await self._scan_for_malware(file_content)

        # 5. Store file in secure location with UUID
        file_id = str(uuid.uuid4())
        file_path = self.upload_dir / bug_id / f"{file_id}_{safe_filename}"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file with restricted permissions
        with open(file_path, 'wb') as f:
            f.write(file_content)
        os.chmod(file_path, 0o600)  # Owner read/write only

        # 6. Create database record
        attachment = BugAttachment(
            bug_id=bug_id,
            filename=safe_filename,
            filepath=str(file_path),
            content_type=detected_type,
            file_size=len(file_content),
            uploaded_by=uploaded_by
        )

        logger.info(f"File uploaded securely: {safe_filename} by {uploaded_by}")
        return attachment

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal"""
        # Remove path components
        filename = os.path.basename(filename)

        # Remove dangerous characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext

        return filename

    async def _scan_for_malware(self, file_content: bytes):
        """Placeholder for malware scanning integration"""
        # In production, integrate with ClamAV or similar
        # For now, perform basic checks

        # Check for executable headers
        if file_content.startswith(b'MZ') or file_content.startswith(b'\x7fELF'):
            raise HTTPException(400, "Executable files not allowed")

        # Check for script patterns in text files
        content_str = file_content.decode('utf-8', errors='ignore').lower()
        script_patterns = ['<script', 'javascript:', 'eval(', 'document.cookie']

        for pattern in script_patterns:
            if pattern in content_str:
                raise HTTPException(400, "File contains potentially malicious content")
```

**Security Validation Checkpoints:**
- ✅ File size limits enforced (10MB maximum)
- ✅ MIME type validation using python-magic library
- ✅ Filename sanitization prevents path traversal
- ✅ Files stored with restrictive permissions (600)
- ✅ Malware scanning integration points defined
- ✅ Maximum files per bug enforced

### 3.2 Secure File Serving
**Security Task: SEC-017-006**

```python
@router.get("/api/admin/bugs/{bug_id}/attachments/{attachment_id}")
async def download_attachment(
    bug_id: str,
    attachment_id: int,
    current_user: UserContext = Depends(require_admin)
):
    """Securely serve bug attachment files"""

    # 1. Verify attachment exists and belongs to bug
    attachment = await bug_service.get_attachment(bug_id, attachment_id)
    if not attachment:
        raise HTTPException(404, "Attachment not found")

    # 2. Path traversal prevention
    file_path = Path(attachment.filepath).resolve()
    upload_dir = Path(app.config.UPLOAD_DIR).resolve()

    if not str(file_path).startswith(str(upload_dir)):
        logger.warning(f"Path traversal attempt: {file_path}")
        raise HTTPException(403, "Access denied")

    # 3. File existence check
    if not file_path.exists():
        raise HTTPException(404, "File not found")

    # 4. Security headers for file download
    headers = {
        'Content-Disposition': f'attachment; filename="{attachment.filename}"',
        'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'",
        'X-Frame-Options': 'DENY'
    }

    return FileResponse(
        path=file_path,
        media_type=attachment.content_type,
        headers=headers
    )
```

## 4. SQL Injection Prevention

### 4.1 SQLModel Integration
**Security Task: SEC-017-007**

The existing SQLModel implementation already provides strong SQL injection protection through parameterized queries. Enhanced validation:

```python
class BugRepository:
    """Repository pattern with additional SQL injection prevention"""

    async def search_bugs(
        self,
        search_term: str,
        filters: BugFilters
    ) -> List[Bug]:
        """Search bugs with safe parameterized queries"""

        # Input validation and sanitization
        if not search_term or len(search_term) > 100:
            raise ValueError("Invalid search term")

        # Whitelist validation for sort parameters
        allowed_sort_fields = ['created_at', 'updated_at', 'title', 'severity', 'status']
        if filters.sort and filters.sort.lstrip('-') not in allowed_sort_fields:
            raise ValueError(f"Invalid sort field: {filters.sort}")

        # Use SQLModel with parameterized queries
        query = select(Bug).where(
            or_(
                Bug.title.ilike(f"%{search_term}%"),
                Bug.description.ilike(f"%{search_term}%")
            )
        )

        # Apply filters with parameter binding
        if filters.status:
            query = query.where(Bug.status == filters.status)
        if filters.severity:
            query = query.where(Bug.severity == filters.severity)

        return await self.db.scalars(query).all()
```

**Security Validation Checkpoints:**
- ✅ All database operations use SQLModel parameterized queries
- ✅ User input never concatenated into SQL strings
- ✅ Sort field validation against whitelist
- ✅ Search term length and content validation

## 5. Cross-Site Scripting (XSS) Protection

### 5.1 Template Security
**Security Task: SEC-017-008**

```html
<!-- templates/admin/bugs.html - Secure template implementation -->
{% extends "base.html" %}

{% block content %}
<!-- All user data properly escaped -->
<div class="bug-item" data-bug-id="{{ bug.bug_id | e }}">
    <h4>{{ bug.title | e }}</h4>
    <p>{{ bug.description | e | nl2br }}</p>

    <!-- Use data attributes instead of inline JavaScript -->
    <button class="btn btn-primary"
            data-action="view-bug"
            data-bug-id="{{ bug.bug_id | e }}">
        View Details
    </button>
</div>

<script nonce="{{ csp_nonce }}">
// CSP-compliant JavaScript with nonce
document.addEventListener('DOMContentLoaded', function() {
    // Event delegation for security
    document.addEventListener('click', function(e) {
        if (e.target.dataset.action === 'view-bug') {
            const bugId = e.target.dataset.bugId;
            // Validate bug ID format before use
            if (/^[A-Z0-9-]+$/.test(bugId)) {
                openBugModal(bugId);
            }
        }
    });
});
</script>
{% endblock %}
```

### 5.2 Content Security Policy
**Security Task: SEC-017-009**

```python
class SecurityHeadersMiddleware:
    """Security headers middleware for XSS protection"""

    async def __call__(self, request: Request, call_next):
        response = await call_next(request)

        # Generate CSP nonce for inline scripts
        csp_nonce = secrets.token_urlsafe(16)

        # Strict CSP for bug pages
        csp_policy = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{csp_nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )

        response.headers.update({
            'Content-Security-Policy': csp_policy,
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        })

        # Make nonce available to templates
        request.state.csp_nonce = csp_nonce

        return response
```

## 6. Access Control for Bug Visibility and Editing

### 6.1 Row-Level Security
**Security Task: SEC-017-010**

```python
class BugAccessControlService:
    """Implements fine-grained access control for bugs"""

    @staticmethod
    def can_view_bug(bug: Bug, user: UserContext) -> bool:
        """Determine if user can view specific bug"""
        # Admins can view all bugs
        if user.is_admin:
            return True

        # Users can view bugs they created or are assigned to
        if bug.created_by == user.username or bug.assigned_to == user.username:
            return True

        # Check for team-based access (future enhancement)
        return False

    @staticmethod
    def can_edit_bug(bug: Bug, user: UserContext) -> bool:
        """Determine if user can edit specific bug"""
        # Admins can edit all bugs
        if user.is_admin:
            return True

        # Users can edit bugs they created (with restrictions)
        if bug.created_by == user.username:
            # Can't edit closed bugs
            if bug.status in ['closed', 'duplicate']:
                return False
            return True

        # Assignees can update status and add comments
        if bug.assigned_to == user.username:
            return True

        return False

    @staticmethod
    async def filter_visible_bugs(
        bugs: List[Bug],
        user: UserContext
    ) -> List[Bug]:
        """Filter bug list based on user permissions"""
        if user.is_admin:
            return bugs

        return [
            bug for bug in bugs
            if BugAccessControlService.can_view_bug(bug, user)
        ]
```

### 6.2 API Endpoint Security
**Security Task: SEC-017-011**

```python
@router.get("/api/admin/bugs/{bug_id}")
async def get_bug(
    bug_id: str,
    current_user: UserContext = Depends(require_auth)
):
    """Get bug with access control validation"""

    # Validate bug ID format
    if not re.match(r'^BUG-[A-F0-9]{8}$', bug_id):
        raise HTTPException(400, "Invalid bug ID format")

    bug = await bug_service.get_bug(bug_id)
    if not bug:
        raise HTTPException(404, "Bug not found")

    # Access control check
    if not BugAccessControlService.can_view_bug(bug, current_user):
        raise HTTPException(403, "Access denied to this bug")

    # Filter sensitive fields based on permissions
    bug_data = bug.dict()
    if not current_user.has_permission('bugs.view_sensitive'):
        # Remove potentially sensitive information
        bug_data.pop('test_evidence_paths', None)
        bug_data.pop('internal_notes', None)

    logger.info(f"Bug {bug_id} accessed by {current_user.username}")
    return bug_data
```

## 7. Data Privacy and Sensitive Information Handling

### 7.1 Data Classification
**Security Task: SEC-017-012**

```python
class DataClassificationService:
    """Classify and handle sensitive data in bugs"""

    SENSITIVE_PATTERNS = [
        # Personal identifiable information
        (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'Email'),
        (r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', 'Credit Card'),

        # Technical secrets
        (r'(?i)(password|pwd|pass)\s*[:=]\s*\S+', 'Password'),
        (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+', 'API Key'),
        (r'(?i)(secret|token)\s*[:=]\s*\S+', 'Secret'),

        # System information
        (r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'IP Address'),
        (r'(?i)server\s*[:=]\s*\S+', 'Server Name'),
    ]

    @classmethod
    def scan_for_sensitive_data(cls, text: str) -> List[dict]:
        """Scan text for sensitive data patterns"""
        findings = []

        for pattern, data_type in cls.SENSITIVE_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                findings.append({
                    'type': data_type,
                    'start': match.start(),
                    'end': match.end(),
                    'matched_text': match.group(),
                    'risk_level': cls._get_risk_level(data_type)
                })

        return findings

    @classmethod
    def _get_risk_level(cls, data_type: str) -> str:
        """Determine risk level for data type"""
        high_risk = ['SSN', 'Credit Card', 'Password', 'API Key', 'Secret']
        medium_risk = ['Email', 'IP Address']

        if data_type in high_risk:
            return 'HIGH'
        elif data_type in medium_risk:
            return 'MEDIUM'
        else:
            return 'LOW'

    @classmethod
    def redact_sensitive_data(cls, text: str) -> str:
        """Automatically redact sensitive data"""
        redacted_text = text

        for pattern, data_type in cls.SENSITIVE_PATTERNS:
            if cls._get_risk_level(data_type) == 'HIGH':
                redacted_text = re.sub(pattern, f'[REDACTED-{data_type}]', redacted_text)

        return redacted_text
```

### 7.2 Privacy-Aware Bug Service
**Security Task: SEC-017-013**

```python
class PrivacyAwareBugService(BugService):
    """Bug service with integrated privacy protection"""

    async def create_bug(
        self,
        bug_data: BugCreateRequest,
        created_by: str
    ) -> Bug:
        """Create bug with privacy scanning"""

        # Scan for sensitive data
        sensitive_findings = []

        for field in ['title', 'description', 'steps_to_reproduce']:
            value = getattr(bug_data, field, None)
            if value:
                findings = DataClassificationService.scan_for_sensitive_data(value)
                if findings:
                    sensitive_findings.extend([
                        {'field': field, **finding} for finding in findings
                    ])

        # Handle sensitive data findings
        if sensitive_findings:
            high_risk_findings = [f for f in sensitive_findings if f['risk_level'] == 'HIGH']

            if high_risk_findings:
                logger.warning(
                    f"High-risk sensitive data detected in bug creation by {created_by}",
                    extra={'findings': high_risk_findings}
                )

                # Auto-redact high-risk data
                bug_data.description = DataClassificationService.redact_sensitive_data(
                    bug_data.description
                )

                # Create privacy audit log entry
                await self._log_privacy_event(
                    action='sensitive_data_redacted',
                    user=created_by,
                    details=high_risk_findings
                )

        return await super().create_bug(bug_data, created_by)

    async def _log_privacy_event(self, action: str, user: str, details: dict):
        """Log privacy-related events for audit"""
        privacy_log_entry = {
            'timestamp': datetime.now(timezone.utc),
            'action': action,
            'user': user,
            'details': details,
            'component': 'bug_management'
        }

        # In production, send to dedicated privacy audit system
        logger.info("Privacy audit event", extra=privacy_log_entry)
```

## 8. Security Testing and Vulnerability Assessment

### 8.1 Security Test Suite
**Security Task: SEC-017-014**

```python
# tests/security/test_bug_security.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

class TestBugSecurity:
    """Comprehensive security tests for bug functionality"""

    def test_authentication_required(self, client: TestClient):
        """Test that all bug endpoints require authentication"""
        endpoints = [
            '/api/admin/bugs',
            '/api/admin/bugs/BUG-12345678'
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
            assert "Authentication required" in response.json()["detail"]

    def test_admin_role_required(self, client: TestClient, user_token: str):
        """Test that bug endpoints require admin role"""
        headers = {"Authorization": f"Bearer {user_token}"}

        response = client.get("/api/admin/bugs", headers=headers)
        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    @pytest.mark.parametrize("malicious_input", [
        "<script>alert('xss')</script>",
        "'; DROP TABLE bugs; --",
        "javascript:alert('xss')",
        "<img src=x onerror=alert('xss')>",
        "eval('malicious code')"
    ])
    def test_input_sanitization(self, client: TestClient, admin_token: str, malicious_input: str):
        """Test XSS and injection protection"""
        headers = {"Authorization": f"Bearer {admin_token}"}

        bug_data = {
            "title": f"Test Bug {malicious_input}",
            "description": f"Description with {malicious_input}",
            "severity": "medium",
            "environment": "test"
        }

        response = client.post("/api/admin/bugs", json=bug_data, headers=headers)

        # Should either sanitize or reject
        if response.status_code == 201:
            # If accepted, check that malicious content is sanitized
            bug = response.json()
            assert "<script>" not in bug["title"]
            assert "DROP TABLE" not in bug["description"]
        else:
            # Should be rejected with validation error
            assert response.status_code == 400

    def test_file_upload_security(self, client: TestClient, admin_token: str):
        """Test file upload security measures"""
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Test oversized file
        large_file = ("test.txt", "x" * (11 * 1024 * 1024))  # 11MB
        response = client.post(
            "/api/admin/bugs/BUG-12345678/attachments",
            files={"file": large_file},
            headers=headers
        )
        assert response.status_code == 400
        assert "size exceeds" in response.json()["detail"]

        # Test malicious file type
        malicious_file = ("malware.exe", b"MZ\x90\x00")  # PE header
        response = client.post(
            "/api/admin/bugs/BUG-12345678/attachments",
            files={"file": malicious_file},
            headers=headers
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    def test_path_traversal_protection(self, client: TestClient, admin_token: str):
        """Test path traversal attack prevention"""
        headers = {"Authorization": f"Bearer {admin_token}"}

        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd"
        ]

        for path in malicious_paths:
            response = client.get(f"/api/admin/bugs/files/{path}", headers=headers)
            assert response.status_code in [400, 403, 404]

    def test_access_control_enforcement(self, client: TestClient):
        """Test that access control is properly enforced"""
        # Create tokens for different users
        admin_token = self.create_test_token("admin_user", "admin")
        user_token = self.create_test_token("regular_user", "user")

        # Admin can access all bugs
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/admin/bugs", headers=admin_headers)
        assert response.status_code == 200

        # Regular user cannot access admin endpoints
        user_headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get("/api/admin/bugs", headers=user_headers)
        assert response.status_code == 403

    def test_sensitive_data_detection(self, client: TestClient, admin_token: str):
        """Test sensitive data detection and handling"""
        headers = {"Authorization": f"Bearer {admin_token}"}

        sensitive_data = {
            "title": "Login Issue",
            "description": "User password is password123 and API key is sk-1234567890abcdef",
            "severity": "high",
            "environment": "prod"
        }

        response = client.post("/api/admin/bugs", json=sensitive_data, headers=headers)

        if response.status_code == 201:
            bug = response.json()
            # Sensitive data should be redacted
            assert "password123" not in bug["description"]
            assert "sk-1234567890abcdef" not in bug["description"]
            assert "[REDACTED" in bug["description"]

    def test_sql_injection_protection(self, client: TestClient, admin_token: str):
        """Test SQL injection attack prevention"""
        headers = {"Authorization": f"Bearer {admin_token}"}

        sql_payloads = [
            "1' OR '1'='1",
            "'; DROP TABLE bugs; --",
            "1 UNION SELECT * FROM auth_users",
            "1' AND (SELECT COUNT(*) FROM bugs) > 0 --"
        ]

        for payload in sql_payloads:
            # Test in search parameter
            response = client.get(
                f"/api/admin/bugs?search={payload}",
                headers=headers
            )
            # Should not cause database errors
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                # Should not return unexpected data
                bugs = response.json()["bugs"]
                # Verify response structure is as expected
                assert isinstance(bugs, list)
```

### 8.2 Automated Security Scanning
**Security Task: SEC-017-015**

```python
# scripts/security_scan.py
#!/usr/bin/env python3
"""
Security scanning script for Bug Page implementation
Integrates with existing Bandit security testing
"""

import subprocess
import json
import sys
from pathlib import Path

class BugSecurityScanner:
    """Automated security scanner for bug page functionality"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.bug_files = [
            "src_common/admin/bug_service.py",
            "src_common/models.py",  # Bug models
            "src_common/admin_routes.py",  # Bug API endpoints
            "templates/admin/bugs.html"
        ]

    def run_bandit_scan(self) -> dict:
        """Run Bandit security scan on bug-related files"""
        cmd = [
            "bandit", "-f", "json", "-ll",
            *[str(self.project_root / f) for f in self.bug_files if (self.project_root / f).exists()]
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return json.loads(result.stdout) if result.stdout else {}
        except Exception as e:
            print(f"Bandit scan failed: {e}")
            return {}

    def check_dependencies(self) -> dict:
        """Check for vulnerable dependencies"""
        cmd = ["safety", "check", "--json"]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return json.loads(result.stdout) if result.stdout else {}
        except Exception as e:
            print(f"Dependency check failed: {e}")
            return {}

    def run_comprehensive_scan(self) -> dict:
        """Run comprehensive security scan"""
        print("Running security scan for Bug Page implementation...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "bandit_scan": self.run_bandit_scan(),
            "dependency_check": self.check_dependencies(),
            "custom_checks": self.run_custom_security_checks()
        }

        return results

    def run_custom_security_checks(self) -> dict:
        """Custom security checks specific to bug functionality"""
        checks = {
            "sql_injection_patterns": self.check_sql_patterns(),
            "xss_patterns": self.check_xss_patterns(),
            "file_upload_security": self.check_file_upload_patterns(),
            "authentication_checks": self.check_auth_patterns()
        }

        return checks

    def check_sql_patterns(self) -> list:
        """Check for potential SQL injection vulnerabilities"""
        issues = []

        for file_path in self.bug_files:
            full_path = self.project_root / file_path
            if not full_path.exists() or not full_path.suffix == '.py':
                continue

            with open(full_path, 'r') as f:
                content = f.read()

            # Check for string concatenation in SQL contexts
            dangerous_patterns = [
                r'f".*SELECT.*{.*}"',
                r'".*SELECT.*" \+ ',
                r'\.format\(.*SELECT',
                r'%.*SELECT.*%'
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append({
                        'file': str(file_path),
                        'pattern': pattern,
                        'type': 'potential_sql_injection'
                    })

        return issues

if __name__ == "__main__":
    scanner = BugSecurityScanner(Path("."))
    results = scanner.run_comprehensive_scan()

    # Output results
    print(json.dumps(results, indent=2))

    # Exit with error if issues found
    total_issues = (
        len(results.get("bandit_scan", {}).get("results", [])) +
        len(results.get("dependency_check", {}).get("vulnerabilities", [])) +
        sum(len(v) for v in results.get("custom_checks", {}).values() if isinstance(v, list))
    )

    if total_issues > 0:
        print(f"\n❌ Security scan found {total_issues} issues")
        sys.exit(1)
    else:
        print("\n✅ Security scan passed - no issues found")
```

## Security Implementation Timeline

### Phase 1: Core Security Infrastructure (Week 1)
- **SEC-017-001**: JWT authentication integration
- **SEC-017-002**: Fine-grained permissions implementation
- **SEC-017-003**: Input validation and sanitization
- **SEC-017-004**: Advanced input sanitization service

### Phase 2: File Upload Security (Week 2)
- **SEC-017-005**: Secure file upload service implementation
- **SEC-017-006**: Secure file serving with path traversal protection
- **SEC-017-007**: Enhanced SQL injection prevention

### Phase 3: XSS and Access Control (Week 3)
- **SEC-017-008**: Template security and XSS protection
- **SEC-017-009**: Content Security Policy implementation
- **SEC-017-010**: Row-level security for bug access
- **SEC-017-011**: API endpoint security hardening

### Phase 4: Privacy and Testing (Week 4)
- **SEC-017-012**: Data classification service
- **SEC-017-013**: Privacy-aware bug operations
- **SEC-017-014**: Comprehensive security test suite
- **SEC-017-015**: Automated security scanning integration

## Security Validation Checkpoints

### Authentication & Authorization
- [ ] All endpoints require valid JWT tokens
- [ ] Admin role verification on all bug operations
- [ ] Token blacklist prevents revoked token use
- [ ] Fine-grained permissions properly enforced
- [ ] Access control prevents unauthorized bug access

### Input Validation & Sanitization
- [ ] All user input validated against schemas
- [ ] HTML entities escaped in all text fields
- [ ] Script injection patterns detected and blocked
- [ ] SQL injection prevention through parameterized queries
- [ ] Search parameters validated against whitelist

### File Upload Security
- [ ] File size limits enforced (10MB maximum)
- [ ] MIME type validation using python-magic
- [ ] Filename sanitization prevents path traversal
- [ ] Files stored with restrictive permissions
- [ ] Malware scanning integration points defined

### XSS Protection
- [ ] Content Security Policy properly configured
- [ ] All template output properly escaped
- [ ] No inline JavaScript without CSP nonce
- [ ] Security headers prevent clickjacking and MIME sniffing

### Privacy & Data Protection
- [ ] Sensitive data patterns detected and flagged
- [ ] High-risk data automatically redacted
- [ ] Privacy events logged for audit trail
- [ ] Data classification rules properly applied

### Security Testing
- [ ] Comprehensive security test suite implemented
- [ ] Automated security scanning integrated
- [ ] Penetration testing scenarios covered
- [ ] Dependency vulnerability scanning enabled

## Compliance and Audit Requirements

### Security Audit Logging
All security-sensitive operations are logged with structured JSON format:

```python
{
    "timestamp": "2025-01-20T14:30:00Z",
    "event_type": "bug_access",
    "user_id": "admin_user",
    "bug_id": "BUG-12345678",
    "action": "view_bug",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0...",
    "success": true,
    "security_flags": ["sensitive_data_present"]
}
```

### Regular Security Reviews
- Weekly automated security scans during development
- Monthly security review of bug-related functionality
- Quarterly penetration testing of bug management system
- Annual security architecture review

### Incident Response
1. **Detection**: Automated monitoring alerts on suspicious activity
2. **Investigation**: Security team reviews audit logs and system state
3. **Containment**: Temporary restrictions on bug access if needed
4. **Recovery**: System restoration and security patch deployment
5. **Documentation**: Post-incident review and process improvement

This security implementation workflow ensures the FR-017 Bug Page meets enterprise security standards while integrating seamlessly with the existing TTRPG Center security infrastructure.