# WebUI Debugger

## Purpose
Debug UI issues including console errors, performance problems, network issues, and React/Vue DevTools analysis.

## Required tools
- playwright (>=0.1.0)
- sequential-thinking (>=0.1.0)

## Optional tools
- memory (>=0.3.0)
- code-index (>=0.1.0)

## When to use
- Debugging console errors or runtime issues
- Performance profiling and optimization
- Network request debugging
- React/Vue state debugging
- Inputs include `bug_report`, `app_url`, or `debug_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `app_url` (string, required) - Application URL
- `bug_report` (object, optional) - Bug description
- `debug_type` (string, optional) - console/performance/network/state

## Procedure (must follow)
1) Use `sequential-thinking` for 5-whys root cause analysis.
2) Read previous debugging sessions from `memory` key `webui/debug/{issue_id}`.
3) Use `playwright` to inspect browser state:
   - Navigate to `app_url`
   - Capture console logs (errors/warnings)
   - Monitor network requests
   - Take performance profiles
   - Capture DOM snapshots
4) Use `code-index` to locate relevant source code for errors.
5) Create debugging artifacts:
   - `DebugReport.md` - Root cause analysis
   - `ConsoleLogs.txt` - Console output
   - `NetworkTrace.har` - Network activity
   - `PerformanceProfile.json` - Performance data
   - `FixSuggestions.md` - Recommended fixes
6) Store debugging session in `memory` under `webui/debug/{issue_id}`.

## Outputs (artifacts)
- `DebugReport.md` - 5-whys root cause analysis
- `ConsoleLogs.txt` - Full console output
- `NetworkTrace.har` - Network requests
- `PerformanceProfile.json` - Performance metrics
- `FixSuggestions.md` - Actionable fixes
- Screenshots at error points

## Failure policy
- If `playwright` unavailable, STOP and emit remediation note.
- Always capture full context even if root cause unclear.
- Never proceed without 5-whys analysis.

## Version
1.0.0
