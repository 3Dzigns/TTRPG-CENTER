# FR-REASON-502 — Integrate Graphwalk Reasoning in Orchestrator

## Summary
Wire `src_common/reason/graphwalk.py` (GraphGuidedReasoner) into the RAG orchestrator for complex queries. Trigger when policy indicates `multi_hop_reasoning` with `complexity` medium/high.

## Rationale
- Activates existing code for long-horizon reasoning
- Improves answer quality for complex procedural/relational questions

## Acceptance Criteria
- Policy flag enables reasoning step for appropriate queries
- Orchestrator emits reasoning trace metadata when used
- Functional tests demonstrate improved answers on complex prompts

## Implementation Notes
- Add a guarded step after retrieval to perform a bounded graph-walk and re-grounding
- Keep deterministic fallbacks when graph or retriever lacks context

