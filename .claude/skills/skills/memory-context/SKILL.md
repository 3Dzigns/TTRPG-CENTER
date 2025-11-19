# memory-context

## Purpose
(See procedure below.)

## Required tools
- memory (>=0.3.0)

## Optional tools
- (none)

## When to use
- Any task that should read prior context or persist results
- Input includes `"memory": true` or `"persist": true`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) `memory.read` `${session.user_id}/task_context` (optional).
2) Merge `context_delta` from inputs into prior context.
3) `memory.write` updated context to `${session.user_id}/task_context`.
4) Emit `memory_status.json` and `warnings.md` (if any).

Hard requirement: If memory MCP is not connected, STOP and return `missing_memory.md`.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
