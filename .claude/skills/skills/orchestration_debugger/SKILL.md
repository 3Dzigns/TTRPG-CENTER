# Orchestration Debugger

## Purpose
Debug agent coordination issues, task delegation failures, swarm performance problems, and distributed system bottlenecks.

## Required tools
- ruv-swarm (>=0.1.0)
- sequential-thinking (>=0.1.0)

## Optional tools
- memory (>=0.3.0)
- flow-nexus (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Debugging agent coordination failures
- Performance profiling for swarms
- Task delegation debugging
- Distributed system bottleneck analysis
- Inputs include `bug_report`, `swarm_id`, or `debug_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `swarm_id` (string, required) - Swarm identifier
- `bug_report` (object, optional) - Bug description
- `debug_type` (string, optional) - coordination/performance/delegation/bottleneck

## Procedure (must follow)
1) Use `sequential-thinking` for 5-whys root cause analysis.
2) Read previous debugging sessions from `memory` key `orchestration/debug/{issue_id}`.
3) Use `ruv-swarm` to inspect swarm state:
   - `swarm_status` with verbose mode for detailed state
   - `agent_list` to check agent health and status
   - `agent_metrics` for performance profiling
   - `task_status` to track task execution
   - `memory_usage` to identify memory leaks
   - `swarm_monitor` for real-time activity tracking
4) Use `flow-nexus` for advanced debugging if available:
   - `workflow_status` for workflow execution analysis
   - `workflow_audit_trail` for event history
   - `workflow_queue_status` for message queue issues
5) Use `code-index` to locate relevant agent source code for errors.
6) Create debugging artifacts:
   - `DebugReport.md` - Root cause analysis
   - `AgentLogs.txt` - Agent execution logs
   - `PerformanceProfile.json` - Performance data
   - `CoordinationTrace.md` - Agent interaction timeline
   - `FixSuggestions.md` - Recommended fixes
7) Store debugging session in `memory` under `orchestration/debug/{issue_id}`.

## Outputs (artifacts)
- `DebugReport.md` - 5-whys root cause analysis
- `AgentLogs.txt` - Full agent execution logs
- `PerformanceProfile.json` - Performance metrics
- `CoordinationTrace.md` - Agent interaction timeline
- `FixSuggestions.md` - Actionable fixes
- Swarm state snapshots

## Failure policy
- If `ruv-swarm` unavailable, STOP and emit remediation note.
- Always capture full context even if root cause unclear.
- Never proceed without 5-whys analysis.

## Version
1.0.0
