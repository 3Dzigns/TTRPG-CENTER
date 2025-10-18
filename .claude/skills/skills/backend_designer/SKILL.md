# Backend Designer

## Purpose
Design scalable backend architectures, microservice patterns, data processing frameworks, and API design systems.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Designing scalable backend architectures
- Creating microservice and API patterns
- Planning data processing frameworks
- Inputs include `architecture_spec`, `scaling_requirements`, or `design_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `architecture_spec` (object, optional) - Architecture requirements
- `scaling_requirements` (object, optional) - Performance and scaling needs
- `framework` (string, optional) - Target framework

## Procedure (must follow)
1) Use `sequential-thinking` to plan backend architecture:
   - Service decomposition strategy
   - API design patterns (REST/GraphQL/gRPC)
   - Data flow and processing architecture
   - Scaling and performance strategy
2) Read existing design decisions from `memory` key `backend/design/architectures`.
3) Use `context7` to retrieve architectural patterns (microservices/event-driven/CQRS).
4) Use `code-index` to analyze existing backend patterns.
5) Create design artifacts:
   - `ServiceArchitecture.md` - Service decomposition design
   - `APIDesignPatterns.md` - API standards and conventions
   - `DataProcessingFramework.md` - Processing architecture
   - `ScalingStrategy.md` - Horizontal scaling approach
   - `DesignGuidelines.md` - Implementation guidelines
6) Store design decisions in `memory` under `backend/design/architectures/{system_name}`.

## Outputs (artifacts)
- `ServiceArchitecture.md` - Service architecture design
- `APIDesignPatterns.md` - API design patterns
- `DataProcessingFramework.md` - Data processing architecture
- `ScalingStrategy.md` - Scaling and performance strategy
- `DesignGuidelines.md` - Implementation guide
- Architecture diagrams

## Failure policy
- If `sequential-thinking` or `memory` unavailable, STOP and emit remediation note.
- Always create architecture documentation even for simple systems.
- Never skip scaling considerations.

## Version
1.0.0
