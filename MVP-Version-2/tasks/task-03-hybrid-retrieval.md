# Task 03 — Hybrid Retrieval & Prompt Registry Integration

## Objective
Replace the orchestrator’s mocked behaviour with the full hybrid retrieval pipeline (classifier → policy → retrieval → rerank → answer) fed by a managed prompt/policy registry.

## Why This Matters
- `services/orchestrator/api.py` returns mocked chunks/answers, offering no hybrid retrieval or provenance.
- Retrieval policies are hard-coded instead of coming from `config/policies.yaml` / `config/retrieval_policies.yaml`.
- Prompt registry contains placeholder content and is not loaded at runtime.
- Error handling doesn’t follow the standard envelope and lacks idempotency support.
- OpenAPI specs for orchestrator/admin/user services are empty, preventing contract-driven development.

## Deliverables
- Modular orchestrator implementation: separate modules for classifier, policy resolution, retriever adapters (vector + graph), reranker, answer composer.
- Runtime integration with prompt registry and policy configs, including hot-reload hooks when flags permit.
- Standardised error envelopes and idempotency key middleware for state-mutating endpoints.
- Complete OpenAPI (`MVP-Version-2/openapi/*.yaml`) with versioned schemas and citations in response models.
- Unit/functional tests covering classification, policy selection, retrieval/graphwalk logic, rerankers, and answer composition with provenance.
- Updated documentation describing prompt lifecycle and retrieval strategies.

## Dependencies / Sequencing
- Relies on Task 01 for configuration loading (`get_environment_config`, path access).
- Consumes artefacts generated in Task 02 (dictionary deltas, graph) and Task 04 (Admin tooling) for verification.

## Detailed Steps
1. **Module refactor**
   - Break `services/orchestrator` into `classifier.py`, `policy.py`, `retrieve.py`, `rerank.py`, `answer.py`, `llm.py`, `types.py` per coding standards example.
   - Ensure each module exposes typed interfaces (TypedDicts / Pydantic models) and logs structured events.
2. **Policy & prompt loading**
   - Implement loaders that watch `config/policies.yaml`, `config/retrieval_policies.yaml`, and `config/prompts/` for changes when `flags.hot_reload` is enabled.
   - Link prompt IDs to entries in `Prompt-Registry/templates/*.yaml` with metadata (version, intent, domain).
3. **Hybrid retrieval execution**
   - Integrate vector store (Astra/Cassandra) and graph traversal (Neo4j/LlamaIndex) based on policy decisions, respecting token budgets and deduplication.
   - Add reranking (e.g., MMR or cross-encoder) with configurable weights and fallback to vector-only when graph store unavailable.
4. **Answer composer & observability**
   - Build answer composer that invokes configured LLMs, injects prompt templates, and returns citations `[Source Section p.Page]`.
   - Emit observability traces covering classify → plan → retrieve → compose; coordinate with Task 05 for OpenTelemetry exporters.
5. **API contract & error handling**
   - Adopt standard error envelope `{"error": {"code", "message", "trace_id"}}` and implement idempotency via header/middleware for requests with side-effects.
   - Populate OpenAPI specs for orchestrator and ensure FastAPI docs link to `/docs`.
6. **Testing & docs**
   - Add unit tests for classifier heuristics, policy routing, chunk retrieval merges, and answer generation.
   - Write functional tests that run hybrid retrieval end-to-end using golden datasets from Task 02.
   - Document prompt registry usage in `Prompt-Registry/README.md` and update `Coding-Standards` retrieval section.
