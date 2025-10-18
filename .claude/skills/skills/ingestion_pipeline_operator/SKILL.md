# Ingestion Pipeline Operator

## Purpose
(See procedure below.)

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- firecrawl (>=0.1.0)
- hugging-face (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- User requests to run or verify ingestion steps
- Inputs contain `document_id`, `system`, or `pass` (C..G)

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Use `sequential-thinking` to expand the requested pass into sub-steps.
2) Read previous ingestion state from `memory.read` `${document_id}/ingestion/state`.
3) If `pass` involves fetching or enrichment, consider `firecrawl`/`hugging-face` where appropriate.
4) If code changes are needed, use `code-index` to locate relevant modules and produce patch suggestions (no direct writes).
5) Update state via `memory.write` and emit:
   - `IngestionPlan.md`, `StateDelta.json`, `Suggestions.md`.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
