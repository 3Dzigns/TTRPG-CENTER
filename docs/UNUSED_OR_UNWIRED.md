# Potentially Unused or Unwired Code

This list highlights files that are not reached by the main runtime code paths (HTTP apps and mounted routers), or which appear to be test-only or CLI-only. These are not necessarily bugs — many are intentionally used in tests or one-off scripts — but they are not exercised by the primary app flows.

- src_common/reason/graphwalk.py
  - Observed usage: tests only (e.g., `tests/unit/test_reason_graphwalk.py:13`, `tests/functional/test_phase3_workflows.py:17`).
  - Not referenced by runtime RAG route in `src_common/orchestrator/service.py:1`.
  - Impact: Graph-guided reasoning exists but is not wired into `/rag/ask`.

- src_common/graph/build.py
  - Observed usage: documentation and tests (e.g., `docs/phases/phase3.md:67`, `tests/unit/test_graph_build.py`).
  - Not invoked by any HTTP route; `GraphStore` is used by Planner/State instead.

- extract_murderous_command.py
  - Standalone helper script; not imported elsewhere (only self-referenced).
  - Likely for ad-hoc data extraction; not part of app flows.

- scripts/* (ingest, dictionary_backfill, personas, rag_openai)
  - CLI utilities invoked manually or by tests.
  - Not reachable from HTTP routes except `app_user.real_rag_query` dynamically imports `scripts/rag_openai.py` to call OpenAI.

- src_common/app.py permissive CORS vs secure CORS
  - `src_common/app.py:36` configures `allow_origins=["*"]`, while app_*.py use `src_common.cors_security` hardened settings.
  - Not unused, but inconsistent with FR-SEC-402 intent.

Notes
- Mock ingestion (`/mock-ingest/{job_id}` in `src_common/app.py:265`) is reachable and used in tests; leaving as-is is fine.
- Reason executors (`src_common/reason/executors.py`) are used by `src_common/runtime/execute.py:72` and are not unused.

