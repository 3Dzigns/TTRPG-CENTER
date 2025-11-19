# debug-containers

## Purpose
Debug container build failures, deployment issues, networking problems, and orchestration errors.

## Required tools
- sequential-thinking (>=0.1.0)
- code-index (>=0.1.0)

## Optional tools
- memory (>=0.3.0)

## When to use
- Debugging Docker build failures
- Container crash investigation
- Kubernetes pod issues
- Networking and service discovery problems
- Inputs include `bug_report`, `container_id`, or `debug_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `container_id` (string, required) - Container/pod identifier
- `bug_report` (object, optional) - Bug description
- `debug_type` (string, optional) - build/runtime/networking/orchestration
- `error_logs` (string, optional) - Error log file path

## Procedure (must follow)
1) Use `sequential-thinking` for 5-whys root cause analysis.
2) Read previous debugging sessions from `memory` key `containers/debug/{issue_id}`.
3) Use `code-index` to locate relevant Dockerfiles and manifests:
   - Search for Dockerfile instructions
   - Find deployment configurations
   - Locate networking policies
4) Analyze container issues:
   - Review build logs and layer failures
   - Inspect container logs and exit codes
   - Check resource usage (CPU/memory/disk)
   - Verify networking and DNS resolution
   - Examine Kubernetes events and pod status
5) Create debugging artifacts:
   - `DebugReport.md` - Root cause analysis
   - `ContainerLogs.txt` - Container execution logs
   - `ResourceUsage.json` - CPU/memory/disk metrics
   - `NetworkTrace.md` - Networking analysis
   - `FixSuggestions.md` - Recommended fixes
6) Store debugging session in `memory` under `containers/debug/{issue_id}`.

## Outputs (artifacts)
- `DebugReport.md` - 5-whys root cause analysis
- `ContainerLogs.txt` - Full container logs
- `ResourceUsage.json` - Resource consumption metrics
- `NetworkTrace.md` - Network connectivity analysis
- `FixSuggestions.md` - Actionable fixes
- Kubernetes event logs

## Failure policy
- If `sequential-thinking` or `code-index` unavailable, STOP and emit remediation note.
- Always capture full context even if root cause unclear.
- Never proceed without 5-whys analysis.

## Version
1.0.0
