# Containers Designer

## Purpose
Design container architectures, microservice deployment patterns, service mesh configurations, and auto-scaling strategies.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Designing container architectures for microservices
- Creating service mesh and networking patterns
- Planning auto-scaling and resilience strategies
- Inputs include `architecture_spec`, `scaling_requirements`, or `design_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `architecture_spec` (object, optional) - Architecture requirements
- `scaling_requirements` (object, optional) - Performance and scaling needs
- `orchestrator` (string, optional) - kubernetes/docker-swarm

## Procedure (must follow)
1) Use `sequential-thinking` to plan container architecture:
   - Microservice decomposition strategy
   - Service mesh and networking design
   - Auto-scaling and resource management
   - Resilience and fault tolerance
2) Read existing design decisions from `memory` key `containers/design/architectures`.
3) Use `context7` to retrieve containerization patterns (service mesh/sidecar/12-factor).
4) Use `code-index` to analyze existing container patterns.
5) Create design artifacts:
   - `MicroserviceArchitecture.md` - Service decomposition design
   - `ServiceMeshDesign.md` - Networking and service mesh
   - `AutoScalingStrategy.md` - Horizontal/vertical scaling approach
   - `ResiliencePatterns.md` - Fault tolerance and recovery
   - `DesignGuidelines.md` - Implementation guidelines
6) Store design decisions in `memory` under `containers/design/architectures/{system_name}`.

## Outputs (artifacts)
- `MicroserviceArchitecture.md` - Microservice architecture design
- `ServiceMeshDesign.md` - Service mesh patterns
- `AutoScalingStrategy.md` - Scaling and resource strategy
- `ResiliencePatterns.md` - Fault tolerance design
- `DesignGuidelines.md` - Implementation guide
- Architecture diagrams

## Failure policy
- If `sequential-thinking` or `memory` unavailable, STOP and emit remediation note.
- Always create architecture documentation even for simple systems.
- Never skip resilience and scaling considerations.

## Version
1.0.0
