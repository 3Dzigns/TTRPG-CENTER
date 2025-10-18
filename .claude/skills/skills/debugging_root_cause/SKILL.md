# Debugging Root Cause

## Purpose
(See procedure below.)

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- code-index (>=0.1.0)
- playwright (>=0.1.0)

## When to use
- Bug reports, 5-whys, reproductions, and failure triage

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Drive a 5-Whys analysis via `sequential-thinking` with numbered thoughts.
2) Read prior incidents from memory keys matching `debug/*`.
3) Use `code-index` to surface relevant modules quickly.
4) If frontend: reproduce with `playwright`, attach screenshots and console logs.
5) Emit `RCA.md`, `ReproSteps.md`, `FixPlan.md`, and update memory under `debug/{issue_id}`.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
