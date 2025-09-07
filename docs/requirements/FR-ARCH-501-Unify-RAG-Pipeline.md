# FR-ARCH-501 — Unify RAG Pipeline in Orchestrator

## Summary
Consolidate final-answer generation for RAG inside `src_common/orchestrator/service.py` so clients (User UI, Admin, external) call a single API (`/rag/ask`). Remove duplication in `app_user.py` that calls `/rag/ask` and then separately invokes OpenAI via `scripts/rag_openai.py`.

## Rationale
- Eliminates drift between UI and core service logic
- Centralizes policies, retries, and observability
- Simplifies clients and reduces error surface

## Acceptance Criteria
- `/rag/ask` returns final answers with citations and model metadata
- `app_user.py` calls only `/rag/ask` (no direct `openai_chat` usage)
- Tests in `tests/functional/test_phase2_rag.py` and `tests/functional/test_phase5_user_interface.py` remain green
- Logging records classification, retrieval, and synthesis in one place

## Implementation Notes
- Move OpenAI call from `app_user.py:real_rag_query` into orchestrator with config guard
- Provide env-driven toggle to disable LLM call in `test` (use stubs)
- Ensure response schema stability for callers

