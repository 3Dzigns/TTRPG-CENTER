# System Health Audit

## Purpose
(See procedure below.)

## Required tools
- memory (>=0.3.0)
- sequential-thinking (>=0.1.0)

## Optional tools
- code-index (>=0.1.0)
- flow-nexus (>=0.1.0)

## When to use
- Periodic or pre-release health checks across code, tests, and docs

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Plan audit phases (code, tests, docs, performance) with `sequential-thinking`.
2) Use `code-index` to scan for hotspots (TODOs, FIXME, anti-patterns).
3) If available, query `flow-nexus` for pipeline/agent health telemetry.
4) Emit `HealthReport.md`, `Scorecard.json`, and `ActionItems.md` (prioritized).

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
