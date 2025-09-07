# BUG-005: Graph-Guided Reasoning Not Integrated Into RAG Route

## Summary
The `src_common/reason/graphwalk.py` module (GraphGuidedReasoner) is not invoked by the runtime RAG endpoint (`/rag/ask`). As a result, multi-hop reasoning and graph-walk capabilities exist but are unused in production flows.

## Environment
- Component: RAG Orchestrator (`src_common/orchestrator/service.py`)
- Environments: dev/test/prod
- Date Reported: 2025-09-06
- Severity: Medium (feature exists but is inert)

## Steps to Reproduce
1. Send a complex query to `/rag/ask` that should require multi-hop reasoning
2. Observe orchestrator pipeline: classify → choose plan → pick model → load/render prompt → retrieve
3. No call to `GraphGuidedReasoner` occurs; answers are synthesized from retrieved context only

## Expected Behavior
- When policy/complexity indicates multi-hop reasoning, orchestrator invokes `GraphGuidedReasoner` to perform a bounded graph-walk with re-grounding.

## Actual Behavior
- Orchestrator never calls the reasoning module; graphwalk remains tests-only.

## Root Cause Analysis
- The orchestrator service was implemented with a simplified flow and did not wire in the optional reasoning step.

## Technical Details
- RAG route: `src_common/orchestrator/service.py:1`
- Reasoner: `src_common/reason/graphwalk.py:1`
- Policies: `src_common/orchestrator/policies.py`

## Fix Required
- Integrate an optional reasoning step in orchestrator gated by policy (e.g., when `intent == multi_hop_reasoning` and `complexity in {medium,high}`).
- Add config flag to enable/disable reasoning for environments.

## Priority
Medium

## Related Files
- `src_common/orchestrator/service.py:1`
- `src_common/reason/graphwalk.py:1`
- `src_common/orchestrator/policies.py:1`

## Testing Notes
- Extend `tests/functional/test_phase3_workflows.py` to verify orchestrator triggers graphwalk when applicable.
- Unit tests already cover `GraphGuidedReasoner`; add integration coverage.

