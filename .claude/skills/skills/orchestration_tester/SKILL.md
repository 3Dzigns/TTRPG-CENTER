# Orchestration Tester

## Purpose
Execute swarm validation, agent coordination tests, performance benchmarks, and distributed system stress testing.

## Required tools
- ruv-swarm (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- sequential-thinking (>=0.1.0)
- flow-nexus (>=0.1.0)

## When to use
- Testing multi-agent swarm coordination
- Validating task orchestration correctness
- Performance benchmarking for agent systems
- Stress testing distributed AI workflows
- Inputs include `test_spec`, `swarm_id`, or `test_suite`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `swarm_id` (string, optional) - Swarm identifier to test
- `test_spec` (object, optional) - Test specification
- `benchmark_type` (string, optional) - Performance/coordination/stress
- `expected_throughput` (number, optional) - Expected tasks per second

## Procedure (must follow)
1) For complex test suites, use `sequential-thinking` to plan test execution order.
2) Read previous test results from `memory` key `orchestration/tests/{test_suite}`.
3) Use `ruv-swarm` to execute swarm tests:
   - `swarm_status` to verify swarm health
   - `agent_list` to check agent availability
   - `task_orchestrate` to run test tasks
   - `agent_metrics` to collect performance data
   - `benchmark_run` for performance testing
4) Use `flow-nexus` for advanced testing if available:
   - `workflow_status` for workflow execution metrics
   - `workflow_queue_status` for message queue health
5) Create test artifacts:
   - `TestReport.md` - Test results summary
   - `PerformanceMetrics.json` - Throughput and latency data
   - `CoordinationValidation.md` - Agent coordination test results
   - `StressTestResults.json` - Stress test findings
6) Store test results in `memory` under `orchestration/tests/{test_suite}`.

## Outputs (artifacts)
- `TestReport.md` - Detailed test results
- `PerformanceMetrics.json` - Performance/timing data
- `CoordinationValidation.md` - Agent coordination analysis
- `StressTestResults.json` - Stress test outcomes
- Agent execution logs

## Failure policy
- If `ruv-swarm` unavailable, STOP and emit remediation note.
- If tests fail, always capture metrics and logs.
- Never skip coordination tests when enabled.

## Version
1.0.0
