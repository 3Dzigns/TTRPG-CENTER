# FR-024 — Query → Plan (Multi-hop Intent)

## Goal
Introduce a lightweight planner that detects whether a query is single-hop, comparative, or procedural, and emits a small plan for graph-augmented reasoning.

## User Stories

**US-0241: Classify query complexity**
- As the orchestrator, I want to classify queries as single-hop, compare, or procedural, so that multi-hop questions can be planned correctly.
- Acceptance Criteria:
  - Classifier returns `{"type": "single|compare|procedural", "entities": [...], "relations": [...], "hop_budget": N}`.
  - Latency ≤150ms (heuristic path), ≤800ms with LLM fallback.

**US-0242: Emit plan for multi-hop**
- As the orchestrator, I want to generate small plans with entities, relations, and hop budget, so that retrieval can follow a structured path.
- Example: “Spell → DamageScaling → Compare(Spell)”

## Test Cases

### Unit
- Heuristic classification rules (short query = single-hop).
- Longer queries with “compare” flagged correctly.

### Functional
- Multi-hop query generates plan with ≥2 entities and relations.

### Regression
- 20 canonical queries maintain stable classification type.

### Security
- Prompt injection cannot force `hop_budget > 3`.
