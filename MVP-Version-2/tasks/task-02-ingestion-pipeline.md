# Task 02 — Ingestion Pipeline Pass 0–G Completion

## Objective
Deliver production-ready implementations for Pass 0 through Pass G that emit the required manifests, dictionary deltas, graph artefacts, and HGRN reports under `env/<env>/artifacts/{job_id}`.

## Why This Matters
- Current pipeline orchestrator (`services/ingest/pipeline.py`) coordinates passes but lacks invariant checks, tool versions, and checksum tracking.
- Pass B logging is broken (`total_pages` undefined, Unicode noise) and needs regression coverage for the 10 MB split contract.
- Pass C/D/E still contain fallbacks / stubs instead of invoking the real Unstructured, Haystack, and LlamaIndex integrations with credentials pulled from env config.
- HGRN consistency outputs (`hgrn.report.json`, `dict_delta.passG.json`, `hgrn.actions.json`) are not wired through to manifests or Admin tooling guidance.
- Runbooks and fixtures do not reflect the new pipeline behaviour, making it hard to validate ingestion end-to-end.

## Deliverables
- Updated Pass modules (`pass_0_preflight` … `pass_g_hgrn_consistency`) that produce complete artefacts with lineage fields (`doc_id`, `part_id`, `section_id`).
- Clean manifest writer that records per-pass status, checksums, tool versions, and failure metadata.
- Deterministic logging (structured) and metrics for each pass, including the 10 MB split summary.
- Refreshed ingestion runbook with troubleshooting, recovery steps, and interface contracts.
- Regression/unit tests covering duplicate detection, split threshold, extraction fallbacks, embedding upserts, graph integrity, and HGRN issue handling.
- Golden fixtures (one scanned, one born-digital PDF) stored under `tests/regression/golden_masters/` with expected outputs.

## Dependencies / Sequencing
- Depends on Task 01 for final artefact paths and env config helpers.
- Coordinate with Task 04 so Admin API’s artifact browser expects the new manifest schema.

## Detailed Steps
1. **Manifest schema & pipeline orchestration**
   - Refactor `services/ingest/pipeline.py` to centralise manifest updates (`_write_manifest`) with checksum/tool-version helpers in a shared utility.
   - Capture start/completion timestamps, pass statuses, and failure reasons per pass.
   - Ensure duplicate short-circuit writes a minimal manifest and exits gracefully.
2. **Pass B fixes & coverage**
   - Repair logging around total pages and remove corrupt characters in `src_common/pass_b_logical_splitter.py`.
   - Add size-threshold regression tests confirming splits occur only above 10 MB, and that manifest entries include parts, checksums, and ToC lineage.
3. **Real integrations for Pass C/D**
   - Wire `pass_c_extraction` to call Unstructured with OCR toggles based on env config, handling credential validation and fallbacks when `ALLOW_UNSTRUCTURED_FALLBACK` is true.
   - Update `pass_d_vector_enrichment` to push embeddings via Haystack, respecting concurrency limits and capturing `dict_delta.passD.json` output.
   - Securely read API keys from `env/<env>/config/.env` via `ConfigManager`.
4. **Graph & HGRN outputs**
   - Implement actual graph build logic in `pass_e_graph_builder` using LlamaIndex; include node/edge counts and dictionary proposals.
   - Enhance `pass_f_finalizer` to verify checksums, merge dictionary deltas, and emit `manifest.json` with tool metadata.
   - Ensure `pass_g_hgrn_consistency` generates actionable reports and recommended actions consumed by Admin UI (Task 04).
5. **Runbook & fixtures**
   - Update `MVP-Version-2/RUNBOOKS/ingest.md` with step-by-step procedures, env requirements, and rollback guidance.
   - Create/refresh ingestion fixtures under `tests/regression/golden_masters/` and update tests to assert manifest structure and artefact presence.
   - Document how to seed/test ingestion in `docs/` (possibly an ADR or README section).
