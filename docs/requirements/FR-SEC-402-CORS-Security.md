# FR-SEC-402: CORS Security Configuration

**Epic:** E4.1 - Authentication & Authorization Security  
**Priority:** 🔴 CRITICAL  
**Status:** Not Started  
**Estimated Effort:** 3 days  
**Team:** 1 Security Engineer + 1 Backend Developer  

## User Story

**As a** Security Engineer  
**I want** to configure CORS policies properly for each environment  
**So that** only authorized domains can access our APIs and prevent cross-site attacks

## Business Context

The current system uses wildcard CORS configuration (`allow_origins=["*"]`) across all environments, creating a critical security vulnerability that enables cross-site request forgery (CSRF) attacks and data exfiltration.

**Risk Level:** CRITICAL - Cross-site attacks and data theft possible  
**Business Impact:** Security compliance failure, potential data breach liability  

## Technical Context

**Current State:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows any origin - SECURITY RISK
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

**Affected Files:**
- `app_admin.py:47`
- `app_user.py:43` 
- `app_feedback.py:50`
- `app_requirements.py:49`

**Target State:** Environment-specific, restrictive CORS policies with proper security headers

## Functional Requirements

### FR-402.1: Environment-Specific CORS Configuration
- **Requirement:** Configure allowed origins per deployment environment
- **Details:**
  - Development: localhost origins only
  - Test: test domain origins only  
  - Production: production domain origins only
- **Acceptance Criteria:**
  - [ ] No wildcard origins in any environment
  - [ ] Environment-specific origin validation
  - [ ] Configuration loaded from environment variables
  - [ ] Invalid origins properly rejected with 403 status

### FR-402.2: Secure CORS Headers Configuration
- **Requirement:** Configure restrictive CORS headers for security
- **Details:**
  - Limit allowed methods to required HTTP verbs only
  - Restrict allowed headers to necessary authentication and content headers
  - Configure appropriate preflight response caching
- **Acceptance Criteria:**
  - [ ] Only required HTTP methods allowed (GET, POST, PUT, DELETE)
  - [ ] Only necessary headers allowed (Authorization, Content-Type, X-Requested-With)
  - [ ] Preflight cache configured with reasonable TTL (3600 seconds)
  - [ ] Credentials only allowed for trusted origins

### FR-402.3: CORS Request Monitoring
- **Requirement:** Log and monitor blocked CORS requests
- **Details:**
  - Log all blocked CORS requests with origin and attempted operation
  - Alert on suspicious CORS activity patterns
  - Provide metrics for CORS policy effectiveness
- **Acceptance Criteria:**
  - [ ] Blocked CORS requests logged with structured data
  - [ ] Metrics collected for allowed vs blocked CORS requests
  - [ ] Alerting configured for repeated CORS violations
  - [ ] Dashboard visibility into CORS policy effectiveness

### FR-402.4: CORS Configuration Validation
- **Requirement:** Validate CORS configuration on application startup
- **Details:**
  - Verify no wildcard origins in production environments
  - Validate all configured origins are reachable
  - Ensure secure defaults for all CORS parameters
- **Acceptance Criteria:**
  - [ ] Application fails to start with invalid CORS configuration
  - [ ] Startup validation checks for security anti-patterns
  - [ ] Configuration schema validation enforced
  - [ ] Health check endpoint reports CORS configuration status

## Technical Requirements

### TR-402.1: Environment Configuration Schema
```python
# CORS configuration per environment
CORS_CONFIG = {
    "dev": {
        "allow_origins": [
            "http://localhost:3000",
            "http://localhost:8080", 
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080"
        ],
        "allow_credentials": True,
        "max_age": 300  # 5 minutes for dev
    },
    "test": {
        "allow_origins": [
            "https://test.ttrpg-center.com",
            "https://test-admin.ttrpg-center.com"
        ],
        "allow_credentials": True,
        "max_age": 1800  # 30 minutes for test
    },
    "prod": {
        "allow_origins": [
            "https://ttrpg-center.com",
            "https://app.ttrpg-center.com",
            "https://admin.ttrpg-center.com"
        ],
        "allow_credentials": True,
        "max_age": 3600  # 1 hour for prod
    }
}

# Security headers configuration
SECURITY_HEADERS = {
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Authorization",
        "Content-Type", 
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Admin-User"  # Temporary during auth transition
    ],
    "expose_headers": [
        "X-Total-Count",
        "X-Rate-Limit-Remaining",
        "X-Rate-Limit-Reset"
    ]
}
```

### TR-402.2: Configuration Management
```python
# Environment-aware CORS configuration loader
class CORSConfigLoader:
    def __init__(self, environment: str):
        self.environment = environment
        self._validate_environment()
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Load CORS configuration for current environment"""
        config = CORS_CONFIG.get(self.environment)
        if not config:
            raise ValueError(f"No CORS config for environment: {self.environment}")
        
        # Security validation
        self._validate_cors_config(config)
        return config
    
    def _validate_cors_config(self, config: Dict[str, Any]) -> None:
        """Validate CORS configuration for security compliance"""
        # No wildcards allowed
        if "*" in config.get("allow_origins", []):
            raise ValueError("Wildcard origins not allowed")
        
        # Production must use HTTPS
        if self.environment == "prod":
            for origin in config["allow_origins"]:
                if not origin.startswith("https://"):
                    raise ValueError(f"Production origin must use HTTPS: {origin}")
```

### TR-402.3: CORS Monitoring Integration
```python
# CORS monitoring middleware
class CORSMonitoringMiddleware:
    def __init__(self, app, logger):
        self.app = app
        self.logger = logger
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request_origin = self._get_origin(scope)
            if request_origin and not self._is_allowed_origin(request_origin):
                # Log blocked CORS request
                self.logger.warning(
                    "CORS request blocked",
                    extra={
                        "origin": request_origin,
                        "path": scope["path"],
                        "method": scope["method"],
                        "client_ip": self._get_client_ip(scope)
                    }
                )
                # Update metrics
                CORS_BLOCKED_COUNTER.inc(labels={"origin": request_origin})
        
        await self.app(scope, receive, send)
```

## Implementation Plan

### Phase 1: Configuration Framework (Day 1)
**Duration:** 1 day  
**Dependencies:** Environment configuration system  

**Tasks:**
1. **Morning:** CORS configuration schema design
   - Define environment-specific CORS policies
   - Create configuration validation framework
   - Implement secure defaults enforcement

2. **Afternoon:** Configuration loader implementation
   - Environment-aware configuration loading
   - Startup validation with security checks
   - Error handling for invalid configurations

### Phase 2: Application Integration (Day 2)
**Duration:** 1 day  
**Dependencies:** Phase 1 completion  

**Tasks:**
1. **Morning:** Remove wildcard CORS from all applications
   - Update app_admin.py CORS configuration
   - Update app_user.py CORS configuration
   - Update app_feedback.py CORS configuration
   - Update app_requirements.py CORS configuration

2. **Afternoon:** Environment-specific implementation
   - Integrate configuration loader in all applications
   - Test CORS policies in dev environment
   - Validate configuration loading and validation

### Phase 3: Monitoring & Testing (Day 3)
**Duration:** 1 day  
**Dependencies:** Phase 2 completion  

**Tasks:**
1. **Morning:** CORS monitoring implementation
   - Add CORS request logging
   - Implement metrics collection
   - Configure alerting for CORS violations

2. **Afternoon:** Testing and validation
   - Comprehensive CORS policy testing
   - Security testing for CORS bypasses
   - Performance impact assessment

## Acceptance Criteria

### AC-402.1: Security Compliance
- [ ] No wildcard CORS origins in any environment
- [ ] Production uses HTTPS-only origins
- [ ] Only required HTTP methods allowed
- [ ] Only necessary headers permitted
- [ ] Credentials restricted to trusted origins only

### AC-402.2: Environment Isolation
- [ ] Development environment only allows localhost origins
- [ ] Test environment only allows test domain origins
- [ ] Production environment only allows production domain origins
- [ ] Cross-environment origin access properly blocked

### AC-402.3: Monitoring & Observability
- [ ] Blocked CORS requests logged with structured data
- [ ] CORS metrics available in monitoring dashboard
- [ ] Alerting configured for CORS policy violations
- [ ] CORS configuration status visible in health checks

### AC-402.4: Operational Excellence
- [ ] Application startup validates CORS configuration
- [ ] Invalid CORS configuration prevents application startup
- [ ] CORS policy changes deployable without code changes
- [ ] Documentation available for CORS configuration management

## Testing Strategy

### Unit Tests
```python
class TestCORSConfiguration:
    def test_dev_environment_allows_localhost()
    def test_prod_environment_rejects_http_origins()
    def test_wildcard_origins_rejected()
    def test_invalid_environment_raises_error()

class TestCORSValidation:
    def test_startup_validation_fails_with_wildcards()
    def test_https_requirement_enforced_in_production()
    def test_allowed_methods_restricted()
    def test_allowed_headers_restricted()
```

### Integration Tests
```python
class TestCORSIntegration:
    def test_allowed_origin_request_succeeds()
    def test_blocked_origin_request_fails_with_403()
    def test_preflight_requests_handled_correctly()
    def test_credentials_allowed_for_trusted_origins()
```

### Security Tests
```python
class TestCORSSecurityl:
    def test_cross_site_request_forgery_prevention()
    def test_data_exfiltration_attack_blocked()
    def test_origin_spoofing_attempts_blocked()
    def test_cors_policy_bypasses_prevented()
```

## Risk Management

### High-Risk Areas
1. **Configuration Errors:** Incorrect CORS policy could break legitimate clients
2. **Environment Mismatch:** Wrong environment configuration could expose security holes
3. **Header Injection:** Malicious headers could bypass CORS controls
4. **Origin Spoofing:** Attackers may attempt to bypass origin restrictions

### Mitigation Strategies
- **Gradual Rollout:** Deploy to dev → test → production with validation at each stage
- **Monitoring:** Extensive logging and alerting for CORS-related activity
- **Testing:** Comprehensive security testing including penetration testing
- **Documentation:** Clear procedures for CORS configuration management

## Success Metrics

- **Security:** Zero successful CORS bypass attempts
- **Functionality:** <1% increase in legitimate request failures
- **Performance:** <5ms overhead for CORS validation
- **Monitoring:** 100% visibility into CORS policy effectiveness

## Documentation Requirements

- [ ] CORS configuration guide for deployment teams
- [ ] Environment-specific setup procedures
- [ ] Troubleshooting guide for CORS-related issues
- [ ] Security incident response procedures for CORS attacks
- [ ] CORS policy change management procedures

## Follow-up Work

- **Content Security Policy (CSP):** Enhanced browser-side security headers
- **Origin Validation Enhancement:** Dynamic origin validation based on user authentication
- **Advanced Monitoring:** Machine learning-based anomaly detection for CORS attacks
- **Compliance Reporting:** Automated CORS policy compliance reporting