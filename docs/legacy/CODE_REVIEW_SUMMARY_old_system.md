# Code Review – TTRPG Center

Scope
- Reviewed FastAPI apps, shared core in `src_common`, admin/requirements/feedback modules, and tests.
- Built a flowchart (see `docs/ARCH_FLOW.md` and `docs/ARCH_FLOW.mmd`).
- Flagged potentially unused/unwired code (see `docs/UNUSED_OR_UNWIRED.md`).

Architecture Overview
- Core API: `src_common/app.py:1` mounts RAG (`/rag/*`) and Phase 3 routers (`/api/workflow/*`, `/api/plan|run`).
- User UI: `app_user.py:1` serves UI and bridges to core RAG via `real_rag_query()`; invokes OpenAI through `scripts/rag_openai.py`.
- Admin UI: `app_admin.py:1` dashboards; uses services under `src_common/admin/*` to read artifacts and status.
- Requirements: `app_requirements.py:1` CRUD + schema validation; secured by `auth_endpoints`, `jwt_service`, `auth_database`.
- Feedback: `app_feedback.py:1` creates regression tests and bug bundles in `artifacts/`.
- Orchestrator: lightweight RAG flow in `src_common/orchestrator/service.py:1` (classification → policy → prompts → retrieval).
- Planner/Workflow: `src_common/planner/*`, `src_common/runtime/*`, `app_plan_run.py`, `app_workflow.py` mounted by core app.

Strengths
- Clear phase separation and tests per phase; strong modularization under `src_common/*`.
- Structured logging (`src_common/ttrpg_logging.py`) and thin shim (`src_common/logging.py`) to stabilize imports.
- Security surfaces present: CORS/TLS helpers, JWT/OAuth endpoints and models.
- Environment isolation pattern (env/{env}) and deterministic artifact structure.

Key Risks / Gaps
- RAG duplication: `app_user.real_rag_query()` calls `/rag/ask` then bypasses core to call OpenAI via script. Suggest consolidating the “final answer” path inside `orchestrator.service` so all clients share the same pipeline.
- Reasoning not wired: `src_common/reason/graphwalk.py` isn’t used by the RAG route. If long-horizon reasoning is in-scope, integrate a hop when policies request it.
- CORS inconsistency: `src_common/app.py:36` uses `allow_origins=["*"]` while app_* modules use hardened `cors_security`. Align to FR-SEC-402 for all apps.
- Large modules: `app_user.py` (and some admin modules) mix concerns (UI, caching, auth, RAG bridge). Consider extracting services.

Recommendations
- Unify RAG: move OpenAI invocation (currently in `scripts/rag_openai.py`) into `src_common/orchestrator/service.py` guarded by config. Let `app_user` call only the RAG API.
- Wire reasoning: add an optional `graphwalk` step in orchestrator when policy indicates multi-hop/high complexity.
- Security parity: adopt `src_common.cors_security.setup_secure_cors()` in `src_common/app.py`; enforce TLS consistently.
- Config/Secrets: ensure `ttrpg_secrets` remains the single source; avoid duplicating env loaders in app_* files.
- Keep scripts CLI-only: avoid `sys.path` hacks in runtime (e.g., `app_user.py: real_rag_query`); prefer shared service modules.

Unused/Unwired Highlights
- See `docs/UNUSED_OR_UNWIRED.md` for concrete file list and notes.

