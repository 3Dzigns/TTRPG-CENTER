# FR-PERF-405: Async Database Operations

**Epic:** E4.3 - Performance & Scalability  
**Priority:** 🟡 HIGH  
**Status:** Not Started  
**Estimated Effort:** 1 week  
**Team:** 1 Backend Developer + 1 Performance Engineer  

## User Story

**As a** Developer  
**I want** to convert all database operations to async/await  
**So that** the application can handle concurrent requests efficiently without blocking

## Business Context

The current system uses synchronous database operations that block the event loop, reducing concurrency by up to 80% and creating performance bottlenecks under load. This prevents the system from efficiently handling production traffic volumes.

**Risk Level:** HIGH - Severe performance limitations  
**Business Impact:** Poor user experience under load, increased infrastructure costs, scalability limitations  

## Technical Context

**Current State:**
```python
def load_chunks(self, chunks: List[Dict]):
    """Synchronous database loading - blocks event loop"""
    for chunk in chunks:
        collection.insert_one(chunk)  # Blocking operation
```

**Affected Areas:**
- `src_common/astra_loader.py:88-118` - Synchronous AstraDB operations
- `src_common/graph/store.py` - Graph database operations
- All FastAPI endpoints using database operations

**Target State:**
- All database operations use async/await pattern
- Non-blocking request handlers
- Async connection pooling for optimal resource usage

## Functional Requirements

### FR-405.1: Async AstraDB Operations
- **Requirement:** Convert all AstraDB operations to async patterns
- **Details:**
  - Replace synchronous database calls with async equivalents
  - Implement async connection pooling
  - Maintain data consistency in async operations
- **Acceptance Criteria:**
  - [ ] All AstraDB operations use async/await pattern
  - [ ] Connection pool configured with optimal size (default: 20 connections)
  - [ ] Batch operations use async concurrency for improved performance
  - [ ] Transaction integrity maintained in async operations
  - [ ] Error handling updated for async operation patterns

### FR-405.2: Async FastAPI Endpoints
- **Requirement:** Update all FastAPI endpoints to async def
- **Details:**
  - Convert synchronous endpoint handlers to async
  - Update dependency injection for async operations
  - Ensure proper async context management
- **Acceptance Criteria:**
  - [ ] All FastAPI endpoint handlers use async def
  - [ ] Database-dependent endpoints fully async
  - [ ] Dependency injection works with async operations
  - [ ] Response streaming works with async patterns
  - [ ] WebSocket connections support async database operations

### FR-405.3: Async Context Management
- **Requirement:** Implement proper async context managers for resource cleanup
- **Details:**
  - Database connections properly closed in async context
  - Transaction rollback handling in async operations  
  - Resource leak prevention in async operations
- **Acceptance Criteria:**
  - [ ] Database connections use async context managers
  - [ ] Transaction handling with proper rollback in async context
  - [ ] Resource cleanup guaranteed even with async exceptions
  - [ ] Connection pool health monitoring for async connections
  - [ ] Memory leak prevention validated in long-running async operations

### FR-405.4: Concurrent Request Handling
- **Requirement:** Optimize application for high-concurrency async operations
- **Details:**
  - Request-level concurrency for independent operations
  - Batch processing optimization with async concurrency
  - Database operation parallelization where safe
- **Acceptance Criteria:**
  - [ ] Multiple database operations can run concurrently per request
  - [ ] Batch operations use async concurrency (asyncio.gather)
  - [ ] Independent database queries parallelized safely
  - [ ] Concurrent request performance improved by 300%+
  - [ ] No race conditions or data consistency issues

## Technical Requirements

### TR-405.1: Async Database Client Configuration
```python
# Async AstraDB client configuration
ASYNC_DB_CONFIG = {
    "connection_pool": {
        "min_connections": 5,
        "max_connections": 20,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 3600
    },
    "query_timeout": 30,
    "retry_policy": {
        "max_attempts": 3,
        "backoff_factor": 2,
        "max_backoff": 10
    },
    "batch_size": 100,
    "concurrent_operations": 10
}
```

### TR-405.2: Async Database Service Architecture
```python
# Async AstraDB service implementation
class AsyncAstraService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection_pool = None
        self.session = None
    
    async def initialize(self) -> None:
        """Initialize async database connection pool"""
        self.connection_pool = await aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=self.config["connection_pool"]["max_connections"],
                limit_per_host=self.config["connection_pool"]["max_connections"],
                ttl_dns_cache=300,
                use_dns_cache=True
            ),
            timeout=aiohttp.ClientTimeout(total=self.config["query_timeout"])
        )
        
        # Initialize AstraDB async client
        self.session = AsyncAstraDBClient(
            api_endpoint=os.getenv("ASTRA_DB_API_ENDPOINT"),
            application_token=os.getenv("ASTRA_DB_APPLICATION_TOKEN"),
            session=self.connection_pool
        )
    
    async def close(self) -> None:
        """Cleanup async resources"""
        if self.connection_pool:
            await self.connection_pool.close()
    
    async def insert_chunk(self, collection: str, chunk: Dict[str, Any]) -> str:
        """Insert single chunk asynchronously"""
        try:
            result = await self.session.collection(collection).insert_one(chunk)
            return result.inserted_id
        except Exception as e:
            logger.error(f"Async chunk insert failed: {e}")
            raise
    
    async def insert_chunks_batch(self, collection: str, chunks: List[Dict[str, Any]]) -> List[str]:
        """Insert multiple chunks with async concurrency"""
        semaphore = asyncio.Semaphore(self.config["concurrent_operations"])
        
        async def insert_with_semaphore(chunk):
            async with semaphore:
                return await self.insert_chunk(collection, chunk)
        
        # Process chunks in batches with concurrency control
        tasks = [insert_with_semaphore(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions and return successful inserts
        successful_inserts = []
        for result in results:
            if not isinstance(result, Exception):
                successful_inserts.append(result)
            else:
                logger.warning(f"Batch insert partial failure: {result}")
        
        return successful_inserts
    
    async def query_chunks(self, collection: str, filter_query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query chunks asynchronously"""
        try:
            cursor = self.session.collection(collection).find(filter_query)
            results = []
            async for document in cursor:
                results.append(document)
            return results
        except Exception as e:
            logger.error(f"Async chunk query failed: {e}")
            raise

# Async context manager for database operations
class AsyncDatabaseContext:
    def __init__(self, db_service: AsyncAstraService):
        self.db_service = db_service
        self.transaction = None
    
    async def __aenter__(self):
        # Start async transaction context
        self.transaction = await self.db_service.start_transaction()
        return self.db_service
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # Rollback on exception
            await self.transaction.rollback()
            logger.warning(f"Database transaction rolled back: {exc_val}")
        else:
            # Commit on success
            await self.transaction.commit()
        
        await self.db_service.close_transaction(self.transaction)
```

### TR-405.3: Async FastAPI Integration
```python
# Async FastAPI endpoint examples
from fastapi import FastAPI, Depends, HTTPException
from typing import List

app = FastAPI()

# Async dependency injection
async def get_async_db_service() -> AsyncAstraService:
    """Async database service dependency"""
    return await get_initialized_db_service()

# Async endpoint implementations
@app.post("/requirements/", response_model=RequirementResponse)
async def create_requirement(
    requirement: RequirementCreate,
    db_service: AsyncAstraService = Depends(get_async_db_service)
) -> RequirementResponse:
    """Create requirement with async database operations"""
    async with AsyncDatabaseContext(db_service) as db:
        # Async database operations
        requirement_id = await db.insert_chunk(
            "requirements", 
            requirement.dict()
        )
        
        # Concurrent related data updates
        related_tasks = [
            db.update_requirement_index(requirement_id),
            db.invalidate_cache_pattern(f"requirement:{requirement_id}"),
            db.log_requirement_creation(requirement_id)
        ]
        await asyncio.gather(*related_tasks)
        
        return RequirementResponse(id=requirement_id, **requirement.dict())

@app.get("/requirements/", response_model=List[RequirementResponse])
async def list_requirements(
    db_service: AsyncAstraService = Depends(get_async_db_service),
    limit: int = 50,
    offset: int = 0
) -> List[RequirementResponse]:
    """List requirements with async database operations"""
    async with AsyncDatabaseContext(db_service) as db:
        # Concurrent database operations
        requirements_task = db.query_chunks(
            "requirements", 
            {"archived": {"$ne": True}}
        )
        count_task = db.count_requirements({"archived": {"$ne": True}})
        
        requirements, total_count = await asyncio.gather(
            requirements_task, 
            count_task
        )
        
        return [RequirementResponse(**req) for req in requirements[offset:offset+limit]]

# Async WebSocket support
@app.websocket("/ws/requirements")
async def websocket_requirements(
    websocket: WebSocket,
    db_service: AsyncAstraService = Depends(get_async_db_service)
):
    """WebSocket with async database operations"""
    await websocket.accept()
    
    try:
        while True:
            # Receive message asynchronously
            message = await websocket.receive_json()
            
            # Process with async database operations
            async with AsyncDatabaseContext(db_service) as db:
                if message["type"] == "get_requirements":
                    requirements = await db.query_chunks(
                        "requirements",
                        message.get("filter", {})
                    )
                    await websocket.send_json({
                        "type": "requirements_data",
                        "data": requirements
                    })
                    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

## Implementation Plan

### Phase 1: Database Client Migration (Days 1-3)
**Duration:** 3 days  
**Dependencies:** Async client libraries installation  

**Tasks:**
1. **Day 1:** Async AstraDB client implementation
   - Implement AsyncAstraService class
   - Add async connection pooling
   - Create async context managers
   - Test basic async database operations

2. **Day 2:** Batch operations optimization
   - Implement async batch processing with concurrency control
   - Add retry logic for async operations
   - Create async transaction management
   - Test concurrent database operations

3. **Day 3:** Error handling and resource management
   - Implement async error handling patterns
   - Add resource cleanup for async operations
   - Create connection pool health monitoring
   - Test resource leak prevention

### Phase 2: FastAPI Endpoint Migration (Days 4-5)
**Duration:** 2 days  
**Dependencies:** Phase 1 completion  

**Tasks:**
1. **Day 4:** Core endpoint migration
   - Convert requirements management endpoints to async
   - Update features management endpoints
   - Migrate admin API endpoints
   - Test async endpoint functionality

2. **Day 5:** Advanced endpoints and WebSocket
   - Convert workflow and feedback endpoints
   - Update WebSocket handlers for async operations
   - Migrate complex query endpoints
   - Test concurrent request handling

### Phase 3: Testing and Optimization (Days 6-7)
**Duration:** 2 days  
**Dependencies:** Phase 2 completion  

**Tasks:**
1. **Day 6:** Performance testing and optimization
   - Load test async vs sync performance
   - Optimize connection pool configuration
   - Test concurrent request handling
   - Identify and fix performance bottlenecks

2. **Day 7:** Integration testing and validation
   - End-to-end async operation testing
   - Data consistency validation
   - Resource leak testing
   - Documentation completion

## Acceptance Criteria

### AC-405.1: Async Implementation
- [ ] All database operations use async/await pattern
- [ ] No blocking database calls in request handlers
- [ ] FastAPI endpoints converted to async def
- [ ] Connection pooling configured and optimized
- [ ] Async context managers prevent resource leaks

### AC-405.2: Performance Improvement
- [ ] Concurrent request performance improved by 300%+
- [ ] Database connection utilization optimized
- [ ] Response time improved for database-heavy endpoints
- [ ] System can handle 1000+ concurrent requests
- [ ] Memory usage stable under high concurrency

### AC-405.3: Data Integrity
- [ ] Data consistency maintained in async operations
- [ ] Transaction rollback working correctly
- [ ] No race conditions in concurrent operations
- [ ] Batch operations maintain atomicity where required
- [ ] Error handling preserves data integrity

### AC-405.4: Reliability
- [ ] Resource cleanup guaranteed in all scenarios
- [ ] Connection pool handles database server restarts
- [ ] Async operations handle network failures gracefully
- [ ] No memory leaks in long-running async operations
- [ ] Health checks validate async operation status

## Testing Strategy

### Unit Tests
```python
class TestAsyncAstraService:
    async def test_async_connection_establishment()
    async def test_async_chunk_insertion()
    async def test_batch_insert_with_concurrency()
    async def test_async_query_operations()
    async def test_connection_pool_management()
    async def test_error_handling_in_async_operations()

class TestAsyncEndpoints:
    async def test_async_requirement_creation()
    async def test_async_requirement_listing()
    async def test_concurrent_endpoint_requests()
    async def test_async_websocket_operations()

class TestAsyncResourceManagement:
    async def test_connection_cleanup_on_exception()
    async def test_transaction_rollback()
    async def test_memory_usage_under_load()
    async def test_connection_pool_health()
```

### Performance Tests
```python
class TestAsyncPerformance:
    async def test_concurrent_request_handling_1000_users()
    async def test_database_operation_throughput()
    async def test_connection_pool_efficiency()
    async def test_memory_usage_scaling()
    async def test_response_time_improvement()
```

### Integration Tests
```python
class TestAsyncIntegration:
    async def test_end_to_end_async_workflow()
    async def test_websocket_with_async_database()
    async def test_batch_processing_reliability()
    async def test_concurrent_user_scenarios()
```

## Risk Management

### High-Risk Areas
1. **Data Consistency:** Race conditions in concurrent operations
2. **Resource Leaks:** Unclosed async connections and contexts
3. **Performance Regression:** Inefficient async patterns causing slowdowns
4. **Error Handling:** Async exceptions not properly caught and handled

### Mitigation Strategies
- **Careful Migration:** Gradual conversion with extensive testing at each step
- **Resource Monitoring:** Comprehensive monitoring for connection leaks
- **Load Testing:** Extensive performance testing before production deployment
- **Error Tracking:** Detailed error logging and monitoring for async operations

## Success Metrics

- **Concurrency:** 300%+ improvement in concurrent request handling
- **Response Time:** 40%+ improvement in database-heavy endpoints
- **Resource Efficiency:** 50%+ improvement in connection pool utilization
- **Reliability:** No increase in error rates with async implementation

## Documentation Requirements

- [ ] Async database operations developer guide
- [ ] Connection pool configuration and tuning guide
- [ ] Async FastAPI endpoint patterns and best practices
- [ ] Performance optimization guide for async operations
- [ ] Troubleshooting guide for async-related issues
- [ ] Migration checklist for future async conversions

## Follow-up Work

- **Advanced Concurrency:** Implement advanced concurrency patterns for complex operations
- **Database Sharding:** Async support for database sharding and partitioning
- **Streaming Operations:** Async streaming for large data processing
- **Performance Profiling:** Continuous performance monitoring and optimization for async operations