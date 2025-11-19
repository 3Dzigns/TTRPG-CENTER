# database-ops

## Purpose
(See procedure below.)

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- code-index (>=0.1.0)

## When to use
- Schema review, query optimization, or DB-related refactors
- Inputs include `db_task` or references to schema files

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Plan with `sequential-thinking` (3–7 steps). Persist plan to memory.
2) Use `code-index` to find schema/DAO/repository files (>10K LOC friendly).
3) Propose changes as patches (do not execute DB mutations here).
4) Emit `DB_Work_Report.md` and `PatchPlan.json`.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
