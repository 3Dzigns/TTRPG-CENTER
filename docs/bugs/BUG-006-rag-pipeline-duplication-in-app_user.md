# BUG-006: RAG Pipeline Duplication in app_user Causes Inconsistent Behavior

## Summary
`app_user.py` implements `real_rag_query()` that first calls the core RAG endpoint (`/rag/ask`) via `TestClient`, then separately invokes OpenAI through `scripts/rag_openai.py`. This duplicates the “final answer” logic and risks drift from orchestrator behavior, error handling, and policies.

## Environment
- Application: User UI (`app_user.py`)
- Environments: dev/test/prod
- Date Reported: 2025-09-06
- Severity: High (inconsistent responses, bypassing orchestrator)

## Steps to Reproduce
1. Inspect `app_user.py:240-340` (real_rag_query implementation)
2. Note internal `TestClient` call to `/rag/ask` followed by direct call to `scripts/rag_openai.openai_chat`
3. Compare outputs vs calling the orchestrator-only pipeline

## Expected Behavior
- A single orchestrator-owned pipeline produces the final answer and metadata. Clients (UI, Admin, others) call the same API.

## Actual Behavior
- UI-side code reimplements portions of RAG composition and LLM invocation, potentially diverging from orchestrator policies and retries.

## Root Cause Analysis
- Historical layering placed OpenAI call in UI code. As the orchestrator matured, this path was not consolidated.

## Technical Details
- UI bridge: `app_user.py:240-340`
- Orchestrator: `src_common/orchestrator/service.py:1`
- OpenAI glue: `scripts/rag_openai.py`

## Fix Required
- Move OpenAI invocation into orchestrator service behind configuration.
- Extend `/rag/ask` to return the final consolidated answer (with citations) so UI only calls the RAG API.

## Priority
High

## Related Files
- `app_user.py:240`
- `src_common/orchestrator/service.py:1`
- `scripts/rag_openai.py:1`

## Testing Notes
- Compare `/rag/ask` answer parity before/after consolidation.
- Ensure `tests/functional/test_phase2_rag.py` and `tests/functional/test_phase5_user_interface.py` pass unchanged.

