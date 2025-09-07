# FR-SEC-406: API Rate Limiting Implementation

**Epic:** E4.4 - API Security & Rate Limiting  
**Priority:** 🔴 CRITICAL  
**Status:** Not Started  
**Estimated Effort:** 1 week  
**Team:** 1 Security Engineer + 1 Backend Developer  

## User Story

**As a** System Administrator  
**I want** to implement rate limiting on all API endpoints  
**So that** the system is protected from DoS attacks and resource exhaustion

## Business Context

The current system has no rate limiting protection, making it vulnerable to Denial of Service (DoS) attacks, API abuse, and resource exhaustion. This represents a critical security vulnerability that prevents production deployment.

**Risk Level:** CRITICAL - Complete service disruption possible  
**Business Impact:** Service availability risk, increased infrastructure costs, security compliance failure  

## Technical Context

**Current State:**
- No rate limiting implemented on any endpoints
- All API endpoints accessible without throttling
- No protection against automated attacks or abuse
- No request monitoring or anomaly detection

**Target State:**
- Redis-based distributed rate limiting
- Endpoint-specific rate limit policies
- IP-based and user-based rate limiting
- Real-time rate limit monitoring and alerting

## Functional Requirements

### FR-406.1: Distributed Rate Limiting
- **Requirement:** Implement Redis-based distributed rate limiting system
- **Details:**
  - Sliding window rate limiting algorithm
  - Distributed state sharing across application instances
  - High-performance rate limit checking with minimal latency
- **Acceptance Criteria:**
  - [ ] Rate limiting state shared across all application instances
  - [ ] Sliding window algorithm provides accurate rate limiting
  - [ ] Rate limit checks complete in <5ms
  - [ ] Rate limiting works correctly during Redis failover
  - [ ] Rate limit state persists across application restarts

### FR-406.2: Endpoint-Specific Rate Limiting
- **Requirement:** Configure different rate limits for different endpoint types
- **Details:**
  - Authentication endpoints: stricter limits to prevent brute force
  - Admin endpoints: higher limits for authorized users
  - Public endpoints: moderate limits for general access
  - Resource-intensive endpoints: lower limits to protect system resources
- **Acceptance Criteria:**
  - [ ] Authentication endpoints limited to 5 requests per minute
  - [ ] Admin endpoints support 1000 requests per minute for authorized users
  - [ ] Public endpoints limited to 100 requests per minute
  - [ ] File upload endpoints limited to 10 requests per minute
  - [ ] Rate limits configurable per endpoint without code changes

### FR-406.3: Multi-Tier Rate Limiting
- **Requirement:** Implement IP-based and user-based rate limiting
- **Details:**
  - IP-based limits for anonymous requests
  - User-based limits for authenticated requests
  - Admin bypass for operational tasks
  - Progressive penalty for repeat violators
- **Acceptance Criteria:**
  - [ ] IP-based rate limiting for all requests
  - [ ] User-based rate limiting overrides IP limits for authenticated users
  - [ ] Admin users can bypass rate limits with proper authorization
  - [ ] Rate limit violations result in exponential backoff penalties
  - [ ] Whitelist support for trusted IPs and services

### FR-406.4: Rate Limit Response and Monitoring
- **Requirement:** Provide informative rate limit responses and comprehensive monitoring
- **Details:**
  - Standard rate limit headers in API responses
  - Detailed logging of rate limit violations
  - Real-time metrics and alerting for rate limiting effectiveness
- **Acceptance Criteria:**
  - [ ] X-RateLimit-* headers included in all API responses
  - [ ] Rate limit violations logged with request details
  - [ ] Metrics dashboard shows rate limiting effectiveness
  - [ ] Alerts configured for rate limit abuse patterns
  - [ ] Rate limit bypass attempts logged and monitored

## Technical Requirements

### TR-406.1: Rate Limiting Configuration Schema
```python
# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    "endpoints": {
        "auth": {
            "requests": 5,
            "window": 60,           # seconds
            "burst_limit": 10,      # allow brief bursts
            "penalty_multiplier": 2  # exponential backoff
        },
        "admin": {
            "requests": 1000,
            "window": 60,
            "burst_limit": 1500,
            "bypass_roles": ["admin", "system"]
        },
        "api_default": {
            "requests": 100,
            "window": 60,
            "burst_limit": 150
        },
        "public": {
            "requests": 20,
            "window": 60,
            "burst_limit": 30
        },
        "upload": {
            "requests": 10,
            "window": 60,
            "burst_limit": 15,
            "size_limit": "100MB"  # additional size-based limiting
        }
    },
    "global": {
        "ip_whitelist": [
            "127.0.0.1",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16"
        ],
        "default_penalty_duration": 300,  # 5 minutes
        "max_penalty_duration": 3600,     # 1 hour
        "violation_threshold": 3          # violations before penalty
    }
}

# Rate limit response headers
RATE_LIMIT_HEADERS = {
    "X-RateLimit-Limit": "requests_per_window",
    "X-RateLimit-Remaining": "remaining_requests",
    "X-RateLimit-Reset": "window_reset_timestamp",
    "X-RateLimit-RetryAfter": "retry_after_seconds"
}
```

### TR-406.2: Rate Limiting Service Architecture
```python
# Redis-based rate limiting service
class RateLimitingService:
    def __init__(self, redis_client, config: Dict[str, Any]):
        self.redis = redis_client
        self.config = config
        self.metrics = RateLimitMetrics()
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        endpoint_category: str,
        user_role: str = None
    ) -> RateLimitResult:
        """Check if request should be rate limited"""
        
        # Get rate limit configuration for endpoint
        endpoint_config = self.config["endpoints"].get(
            endpoint_category, 
            self.config["endpoints"]["api_default"]
        )
        
        # Check for admin bypass
        if user_role in endpoint_config.get("bypass_roles", []):
            return RateLimitResult(
                allowed=True,
                remaining=float('inf'),
                reset_time=0
            )
        
        # Check IP whitelist
        if self._is_whitelisted_ip(identifier):
            return RateLimitResult(allowed=True, remaining=1000, reset_time=0)
        
        # Implement sliding window rate limiting
        now = time.time()
        window_size = endpoint_config["window"]
        request_limit = endpoint_config["requests"]
        
        # Redis key for this identifier and endpoint
        rate_limit_key = f"rate_limit:{endpoint_category}:{identifier}"
        penalty_key = f"penalty:{identifier}"
        
        # Check if user is currently penalized
        penalty_until = await self.redis.get(penalty_key)
        if penalty_until and float(penalty_until) > now:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=float(penalty_until),
                reason="Penalty active due to repeated violations"
            )
        
        # Sliding window implementation using Redis sorted sets
        async with self.redis.pipeline() as pipe:
            # Remove expired entries
            pipe.zremrangebyscore(rate_limit_key, 0, now - window_size)
            
            # Count current requests in window
            pipe.zcard(rate_limit_key)
            
            # Add current request
            pipe.zadd(rate_limit_key, {str(uuid.uuid4()): now})
            
            # Set expiration
            pipe.expire(rate_limit_key, window_size + 1)
            
            results = await pipe.execute()
        
        current_requests = results[1] + 1  # +1 for current request
        remaining = max(0, request_limit - current_requests)
        
        # Check if limit exceeded
        if current_requests > request_limit:
            # Record violation
            await self._record_violation(identifier, endpoint_category)
            
            # Check if penalty should be applied
            violations = await self._get_violation_count(identifier)
            if violations >= self.config["global"]["violation_threshold"]:
                penalty_duration = min(
                    self.config["global"]["default_penalty_duration"] * (2 ** (violations - 3)),
                    self.config["global"]["max_penalty_duration"]
                )
                await self.redis.setex(penalty_key, int(penalty_duration), now + penalty_duration)
            
            self.metrics.record_rate_limit_violation(identifier, endpoint_category)
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=now + window_size,
                reason="Rate limit exceeded"
            )
        
        self.metrics.record_rate_limit_check(identifier, endpoint_category, remaining)
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=now + window_size
        )
    
    async def _record_violation(self, identifier: str, endpoint_category: str):
        """Record rate limit violation for penalty calculation"""
        violation_key = f"violations:{identifier}"
        await self.redis.incr(violation_key)
        await self.redis.expire(violation_key, 3600)  # Violations expire after 1 hour
    
    async def _get_violation_count(self, identifier: str) -> int:
        """Get current violation count for identifier"""
        violation_key = f"violations:{identifier}"
        count = await self.redis.get(violation_key)
        return int(count) if count else 0
    
    def _is_whitelisted_ip(self, ip_address: str) -> bool:
        """Check if IP is in whitelist"""
        # Implementation for IP whitelist checking
        for whitelisted_network in self.config["global"]["ip_whitelist"]:
            if ipaddress.ip_address(ip_address) in ipaddress.ip_network(whitelisted_network):
                return True
        return False

# Rate limiting middleware for FastAPI
class RateLimitMiddleware:
    def __init__(self, app, rate_limiter: RateLimitingService):
        self.app = app
        self.rate_limiter = rate_limiter
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract request information
        request = Request(scope, receive)
        client_ip = self._get_client_ip(request)
        endpoint_path = scope["path"]
        user_role = self._extract_user_role(request)
        
        # Determine endpoint category
        endpoint_category = self._categorize_endpoint(endpoint_path)
        
        # Determine rate limiting identifier (user ID or IP)
        identifier = self._get_identifier(request, client_ip)
        
        # Check rate limit
        rate_limit_result = await self.rate_limiter.check_rate_limit(
            identifier, endpoint_category, user_role
        )
        
        if not rate_limit_result.allowed:
            # Return rate limit exceeded response
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": rate_limit_result.reason,
                    "retry_after": int(rate_limit_result.reset_time - time.time())
                },
                headers={
                    "X-RateLimit-Limit": str(self.rate_limiter.config["endpoints"][endpoint_category]["requests"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(rate_limit_result.reset_time)),
                    "Retry-After": str(int(rate_limit_result.reset_time - time.time()))
                }
            )
            await response(scope, receive, send)
            return
        
        # Add rate limit headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers.update({
                    b"x-ratelimit-limit": str(self.rate_limiter.config["endpoints"][endpoint_category]["requests"]).encode(),
                    b"x-ratelimit-remaining": str(rate_limit_result.remaining).encode(),
                    b"x-ratelimit-reset": str(int(rate_limit_result.reset_time)).encode()
                })
                message["headers"] = [(k.lower() if isinstance(k, str) else k, v) for k, v in headers.items()]
            
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
```

## Implementation Plan

### Phase 1: Core Rate Limiting (Days 1-3)
**Duration:** 3 days  
**Dependencies:** Redis setup, configuration framework  

**Tasks:**
1. **Day 1:** Rate limiting service implementation
   - Implement RateLimitingService class
   - Add sliding window algorithm using Redis sorted sets
   - Create rate limit configuration system
   - Test basic rate limiting functionality

2. **Day 2:** Multi-tier rate limiting
   - Implement IP-based and user-based rate limiting
   - Add admin bypass functionality
   - Create IP whitelist support
   - Test different rate limiting scenarios

3. **Day 3:** Penalty system and violation tracking
   - Implement violation tracking and exponential backoff
   - Add penalty system for repeat violators
   - Create violation metrics and logging
   - Test penalty application and removal

### Phase 2: Middleware Integration (Days 4-5)
**Duration:** 2 days  
**Dependencies:** Phase 1 completion  

**Tasks:**
1. **Day 4:** FastAPI middleware implementation
   - Implement RateLimitMiddleware class
   - Add endpoint categorization logic
   - Integrate rate limit headers in responses
   - Test middleware with various endpoint types

2. **Day 5:** Application integration
   - Integrate rate limiting middleware in all applications
   - Configure endpoint-specific rate limits
   - Add rate limiting to admin and user applications
   - Test end-to-end rate limiting functionality

### Phase 3: Monitoring and Testing (Days 6-7)
**Duration:** 2 days  
**Dependencies:** Phase 2 completion  

**Tasks:**
1. **Day 6:** Monitoring and metrics
   - Implement rate limiting metrics collection
   - Add rate limit violation monitoring
   - Create rate limiting effectiveness dashboard
   - Set up alerts for rate limit abuse patterns

2. **Day 7:** Security testing and validation
   - Conduct DoS attack simulation testing
   - Test rate limiting under high load
   - Validate admin bypass functionality
   - Complete security audit and documentation

## Acceptance Criteria

### AC-406.1: Rate Limiting Implementation
- [ ] Rate limiting active on all API endpoints
- [ ] Sliding window algorithm provides accurate limiting
- [ ] Different rate limits enforced per endpoint category
- [ ] Rate limiting state shared across application instances
- [ ] Rate limit checks complete in <5ms

### AC-406.2: Security Protection
- [ ] DoS attack simulation blocked by rate limits
- [ ] Brute force authentication attacks prevented
- [ ] Resource exhaustion attacks mitigated
- [ ] Rate limit bypass attempts detected and logged
- [ ] Progressive penalties applied for repeat violators

### AC-406.3: User Experience
- [ ] Legitimate users not affected by rate limiting
- [ ] Clear error messages for rate limited requests
- [ ] Rate limit headers provide useful information
- [ ] Admin users can bypass limits when necessary
- [ ] Rate limit violations logged for analysis

### AC-406.4: Monitoring and Operations
- [ ] Rate limit metrics visible in monitoring dashboard
- [ ] Alerts configured for rate limit abuse patterns
- [ ] Rate limit configuration manageable without code changes
- [ ] Rate limiting health checks integrated
- [ ] Performance impact minimal (<5ms overhead per request)

## Testing Strategy

### Unit Tests
```python
class TestRateLimitingService:
    async def test_sliding_window_rate_limiting()
    async def test_admin_bypass_functionality()
    async def test_ip_whitelist_checking()
    async def test_violation_tracking_and_penalties()
    async def test_distributed_rate_limiting()

class TestRateLimitMiddleware:
    async def test_rate_limit_headers_added()
    async def test_rate_limit_exceeded_response()
    async def test_endpoint_categorization()
    async def test_user_vs_ip_identification()
```

### Security Tests
```python
class TestRateLimitSecurity:
    async def test_dos_attack_prevention()
    async def test_brute_force_protection()
    async def test_rate_limit_bypass_prevention()
    async def test_distributed_attack_mitigation()
```

### Performance Tests
```python
class TestRateLimitPerformance:
    async def test_rate_limit_check_latency()
    async def test_high_concurrency_rate_limiting()
    async def test_redis_performance_under_load()
    async def test_rate_limiting_memory_usage()
```

## Risk Management

### High-Risk Areas
1. **False Positives:** Legitimate users blocked by aggressive rate limiting
2. **Redis Failures:** Rate limiting unavailable during Redis outages
3. **Performance Impact:** Rate limiting adding significant latency
4. **Bypass Vulnerabilities:** Attackers finding ways to circumvent rate limits

### Mitigation Strategies
- **Graceful Degradation:** Continue operation when Redis unavailable
- **Performance Optimization:** Highly optimized rate limiting algorithms
- **Monitoring:** Comprehensive monitoring for false positives
- **Security Testing:** Extensive testing for bypass vulnerabilities

## Success Metrics

- **Security:** 99%+ DoS attack mitigation effectiveness
- **Performance:** <5ms rate limiting overhead per request
- **Accuracy:** <1% false positive rate for legitimate users
- **Availability:** Rate limiting available 99.9%+ of the time

## Documentation Requirements

- [ ] Rate limiting configuration guide
- [ ] API rate limit documentation for developers
- [ ] Rate limiting monitoring and troubleshooting guide
- [ ] Security incident response procedures for DoS attacks
- [ ] Rate limiting performance tuning guide

## Follow-up Work

- **Advanced Analytics:** Machine learning-based anomaly detection for sophisticated attacks
- **Dynamic Rate Limiting:** Adaptive rate limits based on system load
- **Geographic Rate Limiting:** Location-based rate limiting policies
- **API Key Management:** Enhanced rate limiting for API key-based access