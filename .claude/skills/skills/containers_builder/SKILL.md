# Containers Builder

## Purpose
Implement Dockerfiles, docker-compose configurations, Kubernetes manifests, and container orchestration setups.

## Required tools
- code-index (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- sequential-thinking (>=0.1.0)

## When to use
- Building Docker images and multi-stage Dockerfiles
- Implementing docker-compose configurations
- Creating Kubernetes manifests and Helm charts
- Inputs include `containerization_spec`, `deployment_spec`, or `build_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `containerization_spec` (object, required) - Container specification
- `orchestrator` (string, optional) - docker-compose/kubernetes/docker-swarm
- `base_image` (string, optional) - Base container image

## Procedure (must follow)
1) Use `code-index` to locate existing Dockerfiles and deployment configs.
2) Read build state from `memory` key `containers/build/{deployment_name}`.
3) For complex builds, use `sequential-thinking` to plan implementation steps.
4) Use `context7` to retrieve containerization documentation and patterns.
5) Implement container components following existing patterns:
   - Multi-stage Dockerfiles with optimization
   - docker-compose.yml with service definitions
   - Kubernetes manifests (Deployment/Service/ConfigMap/Secret)
   - Health checks and readiness probes
6) Create build artifacts:
   - Dockerfile files
   - docker-compose.yml configuration
   - Kubernetes manifests
   - Helm charts (if applicable)
   - `BuildReport.md`
7) Store build state in `memory` under `containers/build/{deployment_name}`.

## Outputs (artifacts)
- Dockerfile files (multi-stage optimized)
- docker-compose.yml configuration
- Kubernetes manifests (YAML)
- Helm charts
- `BuildReport.md` - Implementation summary
- `ContainerAPI.md` - Container interface documentation
- Build validation scripts

## Failure policy
- If **required tools** (code-index, memory) unavailable, STOP and emit remediation note.
- Never create containers without checking existing patterns first.
- Always emit build artifacts even if incomplete.

## Version
1.0.0
