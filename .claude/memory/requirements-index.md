# Memory: Requirements Index

This file points Claude Code to the **authoritative requirements and documentation** that must always take precedence.  
If any ambiguity arises, Claude must prefer these specs and propose updates to `CLAUDE.md` if needed.

## Canonical Requirements & Docs
- `docs/requirements/2025-08-25_MVP_Requirements.json`
- `docs/requirements/requirements.schema.json`
- `docs/requirements/feature_request.schema.json`
- `docs/requirements/example_feature_request.json`
- `docs/documentation.md`
- `README.md`
- `LAUNCH_GUIDE.md`
- `API_TESTING.md`
- `STATUS.md`

## Rules
- Always **quote or reference requirement IDs** (e.g., `RAG-001`, `ADM-002`, `TEST-003`) when implementing or verifying work.
- If instructions in `CLAUDE.md` conflict with these files, **requirements win**.
- Superseding requirements and feature requests must go through the approval workflow defined in the schemas.
- Do not edit these documents in place — all requirement updates must be **versioned and immutable**.
