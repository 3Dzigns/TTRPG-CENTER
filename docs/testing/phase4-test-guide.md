# Phase 4 Admin UI - Testing Guide

## Overview

Comprehensive testing strategy for Phase 4 Admin UI implementation covering all five admin service modules (ADM-001 through ADM-005) and the FastAPI admin application.

## Test Architecture

### Test Levels

1. **Unit Tests** (`tests/unit/test_admin_services.py`)
   - Test individual admin service classes in isolation
   - Mock external dependencies
   - Verify business logic and data processing

2. **Functional Tests** (`tests/functional/test_admin_api.py`)
   - Test FastAPI admin application endpoints
   - Test middleware and WebSocket functionality
   - Test security and performance characteristics

3. **Acceptance Tests** (`tests/functional/test_phase4_acceptance.py`)
   - Validate Phase 4 Definition of Done criteria
   - Test each ADM requirement individually
   - End-to-end integration scenarios

4. **Integration Tests** (`tests/integration/test_phase4_integration.py`)
   - Full system integration testing
   - Performance and error handling validation
   - Cross-service interaction testing

## Test Coverage

### ADM-001: System Status Dashboard Service
**Unit Tests (4 tests):**
- System overview retrieval with environment data
- Environment health checking with port assignments
- System metrics collection (CPU, memory, disk)
- Environment log retrieval with pagination

**Functional Tests (4 tests):**
- Status overview API endpoint
- Environment-specific status endpoints
- Environment log streaming
- Invalid environment handling

**Acceptance Tests (4 tests):**
- All environments displayed (dev/test/prod)
- Correct port assignments (8000/8181/8282)
- System metrics availability
- Health monitoring functionality

### ADM-002: Ingestion Console Service
**Unit Tests (3 tests):**
- Ingestion overview with environment breakdown
- Job listing with environment isolation
- Job creation with artifact tracking

**Functional Tests (3 tests):**
- Ingestion overview API
- Job listing and management
- Job retry/delete operations

**Acceptance Tests (4 tests):**
- Ingestion overview per environment
- Job listing by environment
- Job management operations
- Artifact tracking functionality

### ADM-003: Dictionary Management Service
**Unit Tests (5 tests):**
- Dictionary overview generation
- Environment statistics calculation
- Term listing with filtering
- Term creation with validation
- Search functionality

**Functional Tests (4 tests):**
- Dictionary overview API
- Term CRUD operations
- Search functionality
- Environment isolation validation

**Acceptance Tests (4 tests):**
- Overview per environment
- Environment-scoped operations
- Term creation with isolation
- Search functionality

### ADM-004: Testing & Bug Management Service
**Unit Tests (5 tests):**
- Testing overview generation
- Test listing and creation
- Bug listing and creation
- Test execution with timeout handling
- Environment isolation

**Functional Tests (4 tests):**
- Testing overview API
- Test CRUD operations
- Bug bundle management
- Test execution endpoints

**Acceptance Tests (5 tests):**
- Overview per environment
- Regression test management
- Bug bundle management
- Test execution functionality
- Test suite execution

### ADM-005: Cache Control Service
**Unit Tests (8 tests):**
- Cache overview generation
- Policy retrieval and updates
- Cache header generation
- Cache enable/disable operations
- Cache clearing functionality
- Compliance validation
- Pattern matching utility
- Environment-specific policies

**Functional Tests (8 tests):**
- Cache overview API
- Policy management endpoints
- Cache control operations
- Compliance validation
- Header generation
- Environment-specific behavior

**Acceptance Tests (8 tests):**
- Admin cache toggle availability
- Cache disable/enable functionality
- Environment-specific policies
- Compliance validation
- Critical page no-store policy
- Fast retest behavior
- Cache clearing operations

## Running Tests

### Individual Test Suites

```bash
# Unit tests - Admin services
python -m pytest tests/unit/test_admin_services.py -v

# Functional tests - Admin API
python -m pytest tests/functional/test_admin_api.py -v

# Acceptance tests - Phase 4
python -m pytest tests/functional/test_phase4_acceptance.py -v

# Integration tests - Full system
python -m pytest tests/integration/test_phase4_integration.py -v
```

### All Phase 4 Tests

```bash
# Run all Phase 4 tests
python -m pytest tests/unit/test_admin_services.py tests/functional/test_admin_api.py tests/functional/test_phase4_acceptance.py tests/integration/test_phase4_integration.py -v

# Or use the test runner script
python scripts/test-phase4.py
```

### Coverage Analysis

```bash
# Run tests with coverage
python -m pytest tests/unit/test_admin_services.py tests/functional/test_admin_api.py --cov=src_common.admin --cov=app_admin --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Data & Fixtures

### Mock Objects
- **AdminStatusService**: Mocked system metrics and health checks
- **AdminIngestionService**: Mocked job creation and file operations
- **AdminDictionaryService**: Mocked term storage and search
- **AdminTestingService**: Mocked test execution and bug tracking
- **AdminCacheService**: Mocked cache operations and compliance

### Test Environments
- **dev**: No caching, immediate updates
- **test**: Short TTL caching (5 seconds)
- **prod**: Full caching with longer TTL

## Security Testing

### Input Validation
- Environment parameter validation
- SQL injection protection
- Path traversal prevention
- Parameter boundary testing

### Authentication & Authorization
- Environment isolation enforcement
- Access control validation
- Session management (if applicable)

## Performance Testing

### Response Time Requirements
- Overview endpoints: < 5 seconds
- Individual operations: < 2 seconds
- WebSocket connections: < 1 second setup

### Load Testing
- Concurrent request handling
- Memory usage validation
- Resource cleanup verification

## Error Handling Testing

### Expected Errors
- Invalid environment parameters (400)
- Missing resources (404)  
- Malformed requests (422)
- Service unavailable (503)

### Resilience Testing
- Service failure recovery
- Database connection issues
- File system access problems
- Network timeout handling

## Continuous Integration

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### GitHub Actions (if configured)
- Unit tests on every commit
- Functional tests on PR
- Acceptance tests on main branch
- Integration tests nightly

## Definition of Done Validation

The final acceptance test `test_phase4_definition_of_done()` validates that:

✅ **ADM-001**: System Status Dashboard operational  
✅ **ADM-002**: Ingestion Console functional  
✅ **ADM-003**: Dictionary Management working  
✅ **ADM-004**: Testing & Bug Management active  
✅ **ADM-005**: Cache Control compliant  
✅ **Integration**: All services work together  
✅ **Security**: Input validation and isolation  
✅ **Performance**: Response time requirements met  
✅ **UI**: Admin dashboard renders successfully  

## Test Maintenance

### Adding New Tests
1. Follow existing test structure and naming
2. Use appropriate fixtures and mocks
3. Include both positive and negative test cases
4. Document test purpose and expected behavior

### Test Data Management
- Keep test data minimal and focused
- Use factories for complex object creation
- Clean up test artifacts after execution
- Avoid dependencies between tests

### Debugging Test Failures
1. Run individual failing test: `pytest tests/path/test_name.py::TestClass::test_method -v -s`
2. Check logs and error messages
3. Verify mock configurations
4. Validate test data and expectations

## Reporting

### Test Results
- JUnit XML reports for CI integration
- HTML coverage reports for development
- Performance metrics for monitoring
- Security scan results for compliance

### Metrics Tracking
- Test execution time trends
- Coverage percentage goals (>90%)
- Failure rate monitoring
- Performance regression detection