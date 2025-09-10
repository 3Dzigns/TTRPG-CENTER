# Naming Conventions

This project uses consistent, machine-friendly names for bug reports and feature requests so they are easy to scan, link, and index.

## Bugs
- Pattern: `BUG-<NNN>[-<TYPE>]-<Slug>.md`
  - `NNN`: zero-padded integer ID (e.g., `003`, `014`).
  - `TYPE` (optional): sub-document type for the same bug, e.g. `REPORT`, `RCA`, `FIX`, `NOTES`.
  - `Slug`: short kebab-case summary (letters/numbers/hyphens only).

Examples:
- `BUG-003-oauth-authentication-failed.md`
- `BUG-003-REPORT-Deep-Analysis.md`
- `BUG-014-Design-Drift-Persona-Pipeline-Encoding-Corruption-API-Contract-Gaps.md`

Status line inside each file:
- Include a single line near the top: `Status: Open|In Progress|Closed`.

## Feature Requests
- Pattern: `FR-<AREA>-<NNN>-<Slug>.md`
  - `AREA`: domain code, e.g. `SEC`, `PERF`, `ARCH`, `DB`, `CONFIG`, `REASON`, `INGEST`.
  - `NNN`: zero-padded integer within that domain.
  - `Slug`: short kebab-case summary.

Examples:
- `FR-SEC-401-JWT-Authentication.md`
- `FR-ARCH-501-Unify-RAG-Pipeline.md`
- `FR-INGEST-201-Ingestion-Graph-Enhancements.md`

Status line inside each file:
- Include a single line near the top: `Status: pending|approved|rejected|in_progress|completed|cancelled`.
  - Matches `schemas/feature_request.schema.json`.

## Indexes
- Bugs index: `docs/bugs/INDEX.md`
- Features index: `docs/requirements/INDEX.md`
- Master status index: `docs/STATUS_INDEX.md`

Regenerate indexes with:
```
python scripts/generate_status_index.py
```

