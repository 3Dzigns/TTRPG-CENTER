# Containers Tester

## Purpose
Execute container validation, deployment tests, health check verification, and orchestration testing.

## Required tools
- memory (>=0.3.0)

## Optional tools
- sequential-thinking (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Testing Docker image builds
- Validating container orchestration
- Health check and readiness probe testing
- Deployment verification
- Inputs include `test_spec`, `container_id`, or `test_suite`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `container_id` (string, optional) - Container identifier to test
- `test_spec` (object, optional) - Test specification
- `test_type` (string, optional) - build/deployment/health/orchestration
- `orchestrator` (string, optional) - docker-compose/kubernetes

## Procedure (must follow)
1) For complex test suites, use `sequential-thinking` to plan test execution order.
2) Read previous test results from `memory` key `containers/tests/{test_suite}`.
3) Execute container tests:
   - Build Docker images and verify layers
   - Test docker-compose stack deployment
   - Validate Kubernetes pod creation
   - Check health and readiness probes
   - Verify service networking and discovery
   - Test resource limits and scaling
4) Use `code-index` to locate test fixtures and configurations.
5) Create test artifacts:
   - `TestReport.md` - Test results summary
   - `BuildValidation.json` - Image build metrics
   - `DeploymentResults.md` - Deployment test outcomes
   - `HealthCheckValidation.md` - Health probe verification
   - `OrchestrationTests.json` - Orchestration test results
6) Store test results in `memory` under `containers/tests/{test_suite}`.

## Outputs (artifacts)
- `TestReport.md` - Detailed test results
- `BuildValidation.json` - Image build and layer metrics
- `DeploymentResults.md` - Deployment verification
- `HealthCheckValidation.md` - Health probe testing
- `OrchestrationTests.json` - Orchestration analysis
- Container logs

## Failure policy
- If `memory` unavailable, STOP and emit remediation note.
- If tests fail, always capture logs and container state.
- Never skip health check tests.

## Version
1.0.0
