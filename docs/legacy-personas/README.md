# Legacy Persona System Archives

This directory contains the extensive persona testing system that was developed for the pre-MVP v2 architecture.

## Archived Content

### original-personas/
Contains the original Pathfinder 1E and Eberron persona files:
- PF1E persona templates and character definitions
- Eberron campaign-specific personas
- Question/answer pairs for testing

### extended-personas/
Contains the expanded persona system with:
- International persona variants
- Response files and validation data
- Template systems for persona generation
- Multi-language testing scenarios

## Why Archived?
The extensive persona system was archived because:

1. **MVP v2 Focus**: The new system prioritizes core Pass 0→G pipeline functionality
2. **Testing Strategy**: MVP v2 uses external test execution architecture instead of persona-based testing
3. **Scope Reduction**: Focus on core TTRPG content ingestion and retrieval rather than persona simulation
4. **Resource Optimization**: Simplified testing reduces maintenance overhead

## MVP v2 Testing Approach
The new system uses:
- **External Test Runner Service** (port 8195) for isolated test execution
- **Test Console API** (port 8196) for web-based test monitoring
- **Structured Test Suites**: unit, functional, regression, security, integration, e2e
- **Docker-based Testing**: Containerized test environments

## Future Considerations
This persona system could be reintroduced in future phases if:
- Advanced user behavior simulation is required
- Campaign-specific AI testing becomes a priority
- Multi-character dialogue systems are implemented
- Role-playing game scenario testing is needed

## Historical Value
Preserved for:
- Understanding complex user interaction patterns
- Reference for future persona-based testing
- Learning from comprehensive test coverage approaches
- Campaign and rule system expertise

**Date Archived**: September 24, 2025
**Reason**: Scope reduction for MVP v2 core functionality focus