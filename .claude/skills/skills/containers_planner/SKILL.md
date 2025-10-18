# Containers Planner

## Purpose
Plan Docker containerization strategies, Kubernetes deployments, orchestration architectures, and container security policies.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- code-index (>=0.1.0)
- context7 (>=0.1.0)

## When to use
- Planning Docker containerization strategies
- Designing Kubernetes deployment architectures
- Creating container orchestration plans
- Inputs include `containerization_spec`, `k8s_requirements`, or `deployment_plan`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `containerization_spec` (object, optional) - Containerization requirements
- `orchestrator` (string, optional) - docker-compose/kubernetes/docker-swarm
- `environment` (string, optional) - development/staging/production

## Procedure (must follow)
1) Use `sequential-thinking` to analyze container requirements and break down into phases:
   - Dockerfile design and multi-stage builds
   - Container orchestration strategy
   - Networking and service discovery
   - Security and resource limits
2) Read existing container patterns from `memory` key `containers/patterns`.
3) Use `context7` to retrieve containerization best practices (Docker/Kubernetes patterns).
4) Use `code-index` to discover existing Dockerfiles and deployment configs.
5) Create planning artifacts:
   - `ContainerizationStrategy.md` - Dockerfile design approach
   - `OrchestrationPlan.md` - K8s/docker-compose architecture
   - `NetworkingDesign.md` - Service discovery and networking
   - `SecurityPolicy.md` - Container security and resource limits
6) Store planning decisions in `memory` under `containers/plans/{deployment_name}`.

## Outputs (artifacts)
- `ContainerizationStrategy.md` - Container design strategy
- `OrchestrationPlan.md` - Orchestration architecture
- `NetworkingDesign.md` - Networking and service discovery
- `SecurityPolicy.md` - Security and resource policies
- `DeploymentRoadmap.json` - Phased deployment plan

## Failure policy
- If **required tools** (sequential-thinking, memory) unavailable, STOP and emit remediation note.
- If optional tools unavailable, proceed with reduced functionality and note limitations.
- Never fabricate tool outputs.

## Version
1.0.0
