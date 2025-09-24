# Legacy Phase-Based Tests Archive

This directory contains tests from the pre-MVP v2 system that were based on the old Phase 0-7 architecture.

## Archived Test Categories

### personas/
- **Content**: Persona-based testing system with character simulations
- **Coverage**: Pathfinder 1E and Eberron campaign scenarios
- **Reason Archived**: MVP v2 focuses on Pass 0→G pipeline, not persona simulation

### Phase-Based Functional Tests
- **test_phase3_workflows.py** - Graph workflow testing
- **test_phase4_acceptance.py** - Admin UI acceptance tests
- **test_phase5_user_interface.py** - User interface testing
- **test_phase5_websocket.py** - WebSocket communication tests
- **test_phase6_feedback_integration.py** - Feedback system integration
- **test_phase7_requirements_api.py** - Requirements management API tests

### Phase-Based Unit Tests
- **test_phase5_frontend_themes.py** - Frontend theme testing
- **test_phase5_user_services.py** - User service layer tests
- **test_phase6_feedback_system.py** - Feedback system unit tests
- **test_phase7_requirements_manager.py** - Requirements manager tests
- **test_phase7_schema_validator.py** - Schema validation tests

### Phase-Based Security Tests
- **test_phase3_security.py** - Graph security testing
- **test_phase5_content_security.py** - Content security policy tests
- **test_phase6_security.py** - Feedback system security tests
- **test_phase7_requirements_security.py** - Requirements security tests

### Phase-Based Regression Tests
- **test_phase3_golden_workflows.py** - Golden path workflow tests
- **test_phase7_requirements_regression.py** - Requirements regression tests

### Phase-Based Integration Tests
- **test_phase4_integration.py** - Admin UI integration tests

## MVP v2 Test Strategy

The new testing approach uses:

### External Test Execution Architecture
- **Test Runner Service** (port 8195) - Isolated test execution
- **Test Console API** (port 8196) - Web-based test monitoring
- **Docker-based Testing** - Containerized test environments

### Test Categories
- **Unit Tests** - Individual component testing
- **Functional Tests** - API endpoint and integration testing
- **Regression Tests** - Automated regression detection
- **Security Tests** - Security vulnerability scanning
- **Integration Tests** - End-to-end system testing
- **E2E Tests** - Complete user journey testing

### Retained Core Tests (Renamed)
- **test_rag_retrieval.py** (was test_phase2_rag.py) - RAG functionality
- **test_astra_integration.py** (was test_phase2_astra_integration.py) - Database integration

## Migration Notes

### What Was Preserved
- Core RAG retrieval functionality tests
- AstraDB integration tests
- Environment isolation tests
- Health endpoint tests

### What Was Archived
- Phase-specific UI components not in MVP v2
- Persona simulation systems
- Complex workflow orchestration (beyond core Pipeline)
- Advanced feedback systems
- Requirements management systems

## Future Considerations

These archived tests contain valuable patterns for:
- User interface testing strategies
- WebSocket communication patterns
- Security testing approaches
- Integration testing methodologies

They can be referenced when implementing similar functionality in future phases beyond MVP v2.

**Date Archived**: September 24, 2025
**Reason**: MVP v2 scope reduction to focus on Pass 0→G pipeline core functionality