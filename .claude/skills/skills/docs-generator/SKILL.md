# docs-generator

## Purpose
(See procedure below.)

## Required tools
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- API docs, architectural overviews, contributor guides

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Gather context from memory (recent features, decisions, ADRs).
2) Use `code-index` to extract signatures and endpoints.
3) Use `context7` for official library guidance and examples.
4) Render `docs/` artifacts via templates (see `templates/`).
5) Emit `DocPackIndex.md` with links to generated files.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
