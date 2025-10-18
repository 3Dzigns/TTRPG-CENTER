# Backend Debugger

## Purpose
Debug pipeline failures, API errors, data processing issues, and integration problems in backend systems.

## Required tools
- sequential-thinking (>=0.1.0)
- code-index (>=0.1.0)

## Optional tools
- memory (>=0.3.0)
- firecrawl (>=0.1.0)

## When to use
- Debugging pipeline execution failures
- API error investigation
- Data transformation debugging
- Integration issue analysis
- Inputs include `bug_report`, `pipeline_id`, or `debug_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `pipeline_id` (string, required) - Pipeline identifier
- `bug_report` (object, optional) - Bug description
- `debug_type` (string, optional) - pipeline/api/data/integration
- `error_logs` (string, optional) - Error log file path

## Procedure (must follow)
1) Use `sequential-thinking` for 5-whys root cause analysis.
2) Read previous debugging sessions from `memory` key `backend/debug/{issue_id}`.
3) Use `code-index` to locate relevant pipeline source code:
   - Search for error message patterns
   - Find data transformation logic
   - Locate error handling code
4) Analyze pipeline execution:
   - Review error logs and stack traces
   - Inspect data at failure points
   - Check database connection status
   - Verify API endpoint configurations
5) Use `firecrawl` to debug web scraping components if applicable.
6) Create debugging artifacts:
   - `DebugReport.md` - Root cause analysis
   - `PipelineLogs.txt` - Pipeline execution logs
   - `DataSamples.json` - Data at failure points
   - `ErrorTrace.md` - Stack trace analysis
   - `FixSuggestions.md` - Recommended fixes
7) Store debugging session in `memory` under `backend/debug/{issue_id}`.

## Outputs (artifacts)
- `DebugReport.md` - 5-whys root cause analysis
- `PipelineLogs.txt` - Full pipeline execution logs
- `DataSamples.json` - Data samples at failure points
- `ErrorTrace.md` - Stack trace and error analysis
- `FixSuggestions.md` - Actionable fixes
- Configuration snapshots

## Failure policy
- If `sequential-thinking` or `code-index` unavailable, STOP and emit remediation note.
- Always capture full context even if root cause unclear.
- Never proceed without 5-whys analysis.

## Version
1.0.0
