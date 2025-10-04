# Stub Removal Plan

## AEHRL Evaluator Real Implementation
Prompt: You are an AI developer tasked with replacing the placeholder returns in `src_common/aehrl/evaluator.py` (lines 593-627). Follow these steps:
1. For each evaluation helper (`_evaluate_dictionary_consistency`, `_evaluate_graph_integrity`, `_evaluate_chunk_quality`, `_process_hgrn_recommendations`), implement real scoring logic that inspects the provided artifacts and returns populated `CorrectionRecommendation` objects when issues are detected. Leverage existing models and dataclasses in the AEHRL package.
2. Ensure the new logic handles missing or malformed artifact data gracefully, logging context-rich warnings instead of raising unless execution cannot continue.
3. Update `evaluate_ingestion_artifacts` so it aggregates the new recommendations correctly, including HGRN-derived items, and persists meaningful metrics.
4. Add or extend unit/integration tests (e.g., in `tests/unit/test_aehrl_evaluator.py` or create one) that cover positive, negative, and edge cases for each helper. Use real fixture data rather than empty stubs.
5. Document any new configuration flags or metrics in the AEHRL module README.

## Answer Pipeline Provenance Extraction
Prompt: You are an AI developer enabling provenance handoff in `AnswerPipeline`. Implement these steps:
1. Replace the stubbed `_extract_provenance_data` in `src_common/orchestrator/answer_pipeline.py` (around line 288) with logic that pulls provenance metadata from the provided `QueryPlan`.
2. Use the FR-027 provenance structures already defined in the plan or evaluation metadata to build a dictionary suitable for `EvalGate.evaluate_answer`.
3. Update the pipeline to include provenance in the evaluation call and any downstream logging or summaries.
4. Add tests demonstrating that provenance is captured when present and omitted gracefully when absent.

## User UI Endpoints
Prompt: You are an AI developer connecting the user UI to live services. Proceed as follows:
1. Replace the mock response block in `src_common/user_routes.py` (lines 148-165) with a call into the real orchestrator or answer pipeline, returning authentic answers and sources.
2. Update `/ask/stream` and `/plan` handlers in `services/user_api/api.py` to call real services instead of emitting scripted strings or `_generate_mock_plan_steps`.
3. Remove or refactor `_generate_mock_plan_steps` so plan generation relies on the orchestrator’s planner.
4. Ensure websocket broadcasts and session tracking still work with live responses.
5. Extend functional tests to cover the new live paths, adding fixtures/mocks where necessary to keep tests deterministic.

## Admin Vector Store Client
Prompt: You are an AI developer finishing the Admin API vector client. Execute these steps:
1. Implement `VectorStoreClient.get_collection_stats` in `services/admin_api/clients.py` to call the actual vector backend (via the existing factory or REST endpoints) and return real totals, index status, and per-collection metrics.
2. Enhance `health_check` to perform a lightweight real operation (e.g., ping or count) and surface failure diagnostics.
3. Update admin API routes or dashboards that consume these methods to handle error cases and display new data.
4. Add integration tests (container or functional) verifying stats/health endpoints behave correctly against a test vector store.

## Cache Policy Persistence
Prompt: You are an AI developer ensuring cache policies persist. Follow these actions:
1. Implement `_save_cache_policy` in `src_common/admin/cache_control.py` so updates are written to environment-scoped storage (filesystem, database, or config service).
2. Make `get_cache_policy` load from the same persistent store, falling back to defaults only when no record exists.
3. Add error handling and logging around persistence failures, ensuring the admin UI surfaces meaningful feedback.
4. Create unit tests covering save/load round-trips and failure scenarios.

## TLS Certificate Provisioning
Prompt: You are an AI developer providing real ACME support. Steps:
1. Replace the stubbed `_provision_lets_encrypt` in `src_common/tls_security.py` with a workflow that uses an ACME client (e.g., certbot via subprocess or an ACME Python library) to obtain/renew certificates.
2. Handle staging vs production environments, rate limiting, and challenge responses (HTTP-01 or DNS) based on existing config.
3. Cache certificates locally and reuse when valid, falling back to self-signed only when provisioning fails.
4. Add integration or smoke tests that exercise renewal logic in a sandbox, along with documentation for required credentials.

## Graph Reasoner Retriever
Prompt: You are an AI developer wiring the graph reasoner to real retrieval. Implement these steps:
1. Change the default in `GraphGuidedReasoner` (src_common/reason/graphwalk.py) so it requires an explicit retriever; remove or limit use of `_mock_retriever` to tests.
2. Integrate the production retriever component (vector or hybrid search) to fetch supporting context during graph hops.
3. Update unit/integration tests to inject mock retrievers explicitly, verifying both the happy path and fallback behavior.
4. Refresh documentation describing how to configure the reasoner in production environments.

## Procedure Executor Steps
Prompt: You are an AI developer grounding checklist execution in the graph. Steps:
1. In `src_common/reason/executors.py`, ensure `_get_procedure_steps` always resolves via the graph store; remove `_mock_procedure_steps` or relegate it to test-only code.
2. Populate graph fixtures or adapters so procedure IDs referenced in production map to real step nodes.
3. Extend tests to cover scenarios with missing steps, verifying graceful error reporting.
4. Update any CLI or API endpoints that expose procedure execution to reflect the real data source.

## HGRN Adapter Mock Fallback
Prompt: You are an AI developer providing true HGRN integration. Proceed as follows:
1. Ensure the HGRN adapter in `src_common/hgrn/adapter.py` can install or import the real external package and run validations without falling back to `_mock_validation_results` under normal conditions.
2. Implement rich error handling that distinguishes between configuration issues and transient runtime failures, logging actionable guidance.
3. When mock results are unavoidable (e.g., in development without the package), clearly flag them in the API and surface warnings to operators.
4. Add automated tests that cover both real-package execution (using a stubbed package module) and the intentional mock path, verifying metadata flags.
