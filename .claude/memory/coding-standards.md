# Memory: Coding Standards

These are the baseline development standards Claude Code and the dev team must follow across this project.

## Language & Framework
- **Python 3.12+** is the primary runtime.
- Use **FastAPI** for APIs and service endpoints.
- Queue/worker model for long-running jobs (non-blocking APIs).
- Type annotations everywhere; enforce with **mypy**.
- Style enforcement with **ruff**.

## Testing
- **pytest** as the test framework.
- New/changed modules must include unit tests.
- Integration tests required for:
  - Ingestion pipeline (all three passes)
  - Status event streaming
  - RAG query & answer selection
- All tests must pass locally before promotion.

## Version Control
- Small PRs with descriptive titles.
- Each PR must include a section: **What changed / Why / How tested**.
- Reference **requirement IDs** (e.g., `RAG-001`, `ADM-002`) in commits.

## Definition of Done (DoD)
- Implementation matches the controlling requirement(s).
- Unit + integration tests pass (`pytest -q` green).
- Status events visible in Admin UI for long-running tasks.
- Documentation updated where relevant (`README.md`, `API_TESTING.md`, `LAUNCH_GUIDE.md`).
- No hardcoded secrets (all configs from `.env.*`).

## Guardrails
- Never run destructive commands without confirmation.
- Never mix environment data (dev/test/prod isolation must hold).
- Always prefer clarity over cleverness in code.
- If requirements are ambiguous, defer to `CLAUDE.md` and requirements docs, or raise a question.
