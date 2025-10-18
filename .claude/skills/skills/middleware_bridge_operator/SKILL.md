# Middleware Bridge Operator

## Purpose
(See procedure below.)

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- code-index (>=0.1.0)
- context7 (>=0.1.0)

## When to use
- Connecting web UI to backend/database, contract tracing, API wiring

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Use `sequential-thinking` to map endpoints, DTOs, and data flow.
2) With `code-index`, locate API handlers, services, and client calls.
3) With `context7`, pull library docs for any middleware frameworks in use.
4) Emit `IntegrationMap.md`, `ContractChecklist.md`, and `Gaps.json`.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
