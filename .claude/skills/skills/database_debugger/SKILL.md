# Database Debugger

## Purpose
Debug schema issues, slow queries, migration failures, and data corruption problems.

## Required tools
- sequential-thinking (>=0.1.0)
- code-index (>=0.1.0)

## Optional tools
- memory (>=0.3.0)

## When to use
- Debugging schema constraint violations
- Slow query investigation
- Migration failure analysis
- Data corruption debugging
- Inputs include `bug_report`, `database_id`, or `debug_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `database_id` (string, required) - Database identifier
- `bug_report` (object, optional) - Bug description
- `debug_type` (string, optional) - schema/query/migration/corruption
- `error_logs` (string, optional) - Error log file path

## Procedure (must follow)
1) Use `sequential-thinking` for 5-whys root cause analysis.
2) Read previous debugging sessions from `memory` key `database/debug/{issue_id}`.
3) Use `code-index` to locate relevant schema and query code:
   - Search for schema definitions
   - Find query implementations
   - Locate migration scripts
4) Analyze database issues:
   - Review error logs and constraint violations
   - Execute EXPLAIN/EXPLAIN ANALYZE on slow queries
   - Check index usage and table statistics
   - Verify migration script correctness
   - Inspect data samples for corruption
5) Create debugging artifacts:
   - `DebugReport.md` - Root cause analysis
   - `QueryPlans.txt` - EXPLAIN output for slow queries
   - `SchemaAnalysis.md` - Schema constraint analysis
   - `DataSamples.json` - Data samples showing corruption
   - `FixSuggestions.md` - Recommended fixes
6) Store debugging session in `memory` under `database/debug/{issue_id}`.

## Outputs (artifacts)
- `DebugReport.md` - 5-whys root cause analysis
- `QueryPlans.txt` - Query execution plans
- `SchemaAnalysis.md` - Schema and constraint analysis
- `DataSamples.json` - Data samples at failure points
- `FixSuggestions.md` - Actionable fixes
- Index usage statistics

## Failure policy
- If `sequential-thinking` or `code-index` unavailable, STOP and emit remediation note.
- Always capture full context even if root cause unclear.
- Never proceed without 5-whys analysis.

## Version
1.0.0
