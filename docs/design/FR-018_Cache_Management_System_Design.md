# FR-018 Cache Management System Design

## Executive Summary

This document outlines the comprehensive system design for FR-018 - Cache Page implementation. The design extends the existing AdminCacheService to provide detailed cache introspection, targeted invalidation, and comprehensive audit logging capabilities for TTRPG Center's multi-environment infrastructure.

## Architecture Overview

### Current State Analysis
- **Existing Foundation**: AdminCacheService with basic enable/disable/clear functionality
- **Current Admin UI**: Basic cache control toggles in admin dashboard
- **Missing Components**: Detailed cache inspection, granular invalidation, audit trails

### Target Architecture

```
┌─────────────────────────────────────────┐
│              Admin Cache UI             │
├─────────────────────────────────────────┤
│  • Cache Key Browser                    │
│  • Size/Age Metrics Display             │
│  • Targeted Invalidation Controls       │
│  • Real-time Updates (WebSocket)        │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│          Enhanced Cache API             │
├─────────────────────────────────────────┤
│  GET  /api/cache/{env}/keys             │
│  GET  /api/cache/{env}/metrics          │
│  POST /api/cache/{env}/invalidate       │
│  GET  /api/cache/{env}/audit            │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│        Enhanced AdminCacheService       │
├─────────────────────────────────────────┤
│  • Cache Key Inspection                 │
│  • Granular Invalidation               │
│  • Audit Trail Generation              │
│  • Performance Metrics Collection       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│           Cache Storage Layer           │
├─────────────────────────────────────────┤
│  • Redis/Memory Store                   │
│  • Key-Value Mappings                   │
│  • TTL Management                       │
│  • Size Tracking                        │
└─────────────────────────────────────────┘
```

## Detailed Component Design

### 1. Data Models

#### CacheEntry
```python
@dataclass
class CacheEntry:
    """Individual cache entry with metadata"""
    key: str
    size_bytes: int
    ttl_seconds: int
    created_at: float
    last_accessed: float
    hit_count: int
    content_type: str
    environment: str
    invalidated: bool = False

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def expires_at(self) -> float:
        return self.created_at + self.ttl_seconds
```

#### CacheAuditEntry
```python
@dataclass
class CacheAuditEntry:
    """Audit trail for cache operations"""
    timestamp: float
    environment: str
    action: str  # 'invalidate', 'clear', 'create'
    target_keys: List[str]
    user_id: str
    reason: Optional[str]
    affected_count: int
    success: bool
    error_message: Optional[str]
```

#### CacheMetricsDetailed
```python
@dataclass
class CacheMetricsDetailed:
    """Enhanced cache metrics"""
    environment: str
    total_keys: int
    total_size_bytes: int
    average_key_age_seconds: float
    hit_ratio: float
    memory_pressure: float
    eviction_count: int
    top_keys_by_size: List[Tuple[str, int]]
    top_keys_by_hits: List[Tuple[str, int]]
    expiring_soon: List[str]  # Keys expiring within 5 minutes
```

### 2. Enhanced AdminCacheService

#### Core Methods
```python
async def list_cache_keys(self, environment: str,
                         pattern: Optional[str] = None,
                         sort_by: str = 'age',
                         limit: int = 100) -> List[CacheEntry]:
    """List cache keys with filtering and sorting"""

async def get_cache_entry_details(self, environment: str,
                                 key: str) -> Optional[CacheEntry]:
    """Get detailed information about specific cache entry"""

async def invalidate_cache_keys(self, environment: str,
                              keys: List[str],
                              user_id: str,
                              reason: Optional[str] = None) -> CacheAuditEntry:
    """Invalidate specific cache keys with audit trail"""

async def get_detailed_metrics(self, environment: str) -> CacheMetricsDetailed:
    """Get comprehensive cache performance metrics"""

async def get_audit_trail(self, environment: str,
                         limit: int = 100,
                         start_time: Optional[float] = None) -> List[CacheAuditEntry]:
    """Retrieve cache operation audit trail"""
```

### 3. API Endpoints Design

#### Cache Inspection Endpoints
```python
@admin_router.get("/api/cache/{environment}/keys")
async def list_cache_keys(
    environment: str,
    pattern: Optional[str] = Query(None),
    sort: str = Query("age", regex="^(age|size|hits|name)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(100, ge=1, le=1000)
):
    """List cache keys with filtering and sorting"""

@admin_router.get("/api/cache/{environment}/keys/{key_id}")
async def get_cache_key_details(environment: str, key_id: str):
    """Get detailed information about specific cache key"""

@admin_router.get("/api/cache/{environment}/metrics/detailed")
async def get_detailed_cache_metrics(environment: str):
    """Get comprehensive cache metrics"""
```

#### Cache Management Endpoints
```python
@admin_router.post("/api/cache/{environment}/invalidate")
async def invalidate_cache_keys(environment: str, request: InvalidateRequest):
    """Invalidate specific cache keys with audit logging"""

@admin_router.get("/api/cache/{environment}/audit")
async def get_cache_audit_trail(
    environment: str,
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[float] = Query(None)
):
    """Retrieve cache operation audit trail"""
```

### 4. Frontend UI Components

#### Cache Browser Component
```html
<!-- Cache Key Browser with Search/Filter -->
<div class="cache-browser">
    <div class="cache-controls">
        <input type="text" placeholder="Filter keys..." id="key-filter">
        <select id="sort-select">
            <option value="age-desc">Oldest First</option>
            <option value="size-desc">Largest First</option>
            <option value="hits-desc">Most Used</option>
        </select>
        <button onclick="refreshCacheKeys()">Refresh</button>
    </div>

    <div class="cache-key-list" id="cache-key-list">
        <!-- Dynamic content populated by JavaScript -->
    </div>
</div>
```

#### Cache Metrics Dashboard
```html
<!-- Real-time Cache Metrics -->
<div class="cache-metrics-grid">
    <div class="metric-card">
        <h6>Total Keys</h6>
        <span class="metric-value" id="total-keys">--</span>
    </div>
    <div class="metric-card">
        <h6>Total Size</h6>
        <span class="metric-value" id="total-size">--</span>
    </div>
    <div class="metric-card">
        <h6>Hit Ratio</h6>
        <span class="metric-value" id="hit-ratio">--</span>
    </div>
    <div class="metric-card">
        <h6>Memory Pressure</h6>
        <span class="metric-value" id="memory-pressure">--</span>
    </div>
</div>
```

#### Targeted Invalidation Interface
```html
<!-- Selective Cache Invalidation -->
<div class="invalidation-panel">
    <h6>Invalidate Cache Keys</h6>
    <div class="form-group">
        <label>Select Keys to Invalidate:</label>
        <div class="key-selection-list" id="invalidation-targets">
            <!-- Checkboxes for selected keys -->
        </div>
    </div>
    <div class="form-group">
        <label>Reason (Optional):</label>
        <input type="text" placeholder="e.g., Schema update, Content change"
               id="invalidation-reason">
    </div>
    <button onclick="performInvalidation()" class="btn-danger">
        Invalidate Selected Keys
    </button>
</div>
```

### 5. Real-time Updates Architecture

#### WebSocket Integration
```javascript
// Enhanced WebSocket handling for cache updates
class CacheWebSocketHandler {
    constructor() {
        this.ws = new WebSocket(`ws://${window.location.host}/ws/admin`);
        this.setupEventHandlers();
    }

    setupEventHandlers() {
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'cache_update') {
                this.handleCacheUpdate(message.data);
            }
        };
    }

    handleCacheUpdate(data) {
        // Update UI components based on cache changes
        if (data.action === 'invalidate') {
            this.removeKeysFromUI(data.keys);
            this.updateMetrics();
            this.addAuditEntry(data.audit);
        }
    }
}
```

## Acceptance Criteria Implementation

### AC1: Real Cache Metrics Display
- **Implementation**: Enhanced cache inspection endpoints return actual cache data from Redis/memory store
- **Validation**: Unit tests verify metrics accuracy against known cache state
- **UI Components**: Real-time metrics dashboard with automatic refresh

### AC2: Targeted Key Invalidation
- **Implementation**: Granular invalidation API with key selection interface
- **Safety**: Confirmation dialogs for bulk operations, pattern matching validation
- **Feedback**: Real-time UI updates showing invalidation results

### AC3: Comprehensive Audit Trail
- **Implementation**: All cache operations logged to persistent audit store
- **Data**: Timestamp, user, action, affected keys, success status, reason
- **UI**: Searchable audit log viewer with filtering capabilities

## Security Considerations

### Access Control
- Admin-only cache management endpoints
- User identification for all audit entries
- Rate limiting on invalidation operations

### Data Protection
- Sensitive cache keys filtered from UI display
- Audit log rotation and retention policies
- No cache content exposure in browser

### Operational Safety
- Confirmation dialogs for destructive operations
- Pattern validation for bulk operations
- Recovery procedures for accidental invalidation

## Performance Considerations

### Scalability
- Pagination for large key listings (100 keys default, 1000 max)
- Efficient key filtering using Redis SCAN operations
- Cached metrics with 30-second refresh intervals

### Response Time Targets
- Key listing: <500ms for 100 keys
- Metrics retrieval: <200ms
- Invalidation operations: <100ms per key

### Resource Usage
- Memory-efficient key iteration using cursors
- Lightweight UI updates using incremental DOM manipulation
- WebSocket connection pooling for multiple admin users

## Testing Strategy

### Unit Tests
- Cache service methods with mock Redis backend
- API endpoint validation with test data
- Audit trail generation and retrieval

### Integration Tests
- End-to-end cache operations across environments
- WebSocket message handling and UI updates
- Multi-user admin session handling

### Performance Tests
- Large cache dataset handling (10K+ keys)
- Concurrent admin user operations
- Memory usage under sustained load

## Deployment Considerations

### Environment Configuration
- Redis connection strings per environment
- Audit log storage location configuration
- WebSocket endpoint security settings

### Migration Path
- Extend existing AdminCacheService without breaking changes
- Progressive enhancement of admin UI
- Backward compatibility with existing cache controls

### Monitoring
- Cache operation success/failure rates
- Admin UI performance metrics
- Audit trail storage usage tracking

## Future Enhancements

### Advanced Features
- Cache key content preview (non-sensitive data)
- Automated cache warming strategies
- Predictive cache invalidation based on content changes
- Export cache metrics to external monitoring systems

### UI Improvements
- Graphical cache usage visualization
- Bulk operation progress indicators
- Advanced search and filtering capabilities
- Mobile-responsive cache management interface

This comprehensive design provides a robust foundation for implementing FR-018 while maintaining consistency with the existing TTRPG Center architecture and ensuring operational reliability across all environments.