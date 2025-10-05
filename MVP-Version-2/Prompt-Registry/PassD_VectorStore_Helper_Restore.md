# Prompt: Repair Cassandra Vector Store Serialization + Document Identity Propagation

## Background
- Job `selective_1759615005_dev` failed in Pass D on 2025-10-04: `'CassandraVectorStore' object has no attribute '_json_default'`.
- Same failure signature occurs on `job_1759593741_dev` when Pass D launches after Pass C completes.
- Code review of `src_common/vector_store/cassandra.py` shows `_json_default` (and helper methods `_coerce_datetime`, `_coerce_timestamp`, `_fallback_chunk_id`) defined outside `CassandraVectorStore` because `_lexical_score` lost its indentation (see lines 460-480). The class therefore lacks these attributes, so `self._json_default` raises `AttributeError` when serializing payloads in `_normalise_document`.
- Existing chunks from Pass C already carry `doc_id: job_1759593741_dev`, demonstrating document identity is available, but metadata never reaches Cassandra because Pass D aborts before writing any rows.

## Problem Statement
Pass D cannot serialize documents for Cassandra persistence because class-level helpers were accidentally dedented. We must restore these helpers, verify document/metadata propagation from Gate 0 through Pass G, and add tests so regression cannot recur.

## Goals
1. Re-attach `_lexical_score`, `_coerce_datetime`, `_coerce_timestamp`, `_json_default`, and `_fallback_chunk_id` as `@staticmethod`s inside `CassandraVectorStore`.
2. Confirm document identity and source metadata follow the document from Gate 0 (preflight) ? Pass A/B/C ? Pass D (vector enrichment) ? downstream passes E–G.
3. Reinforce automated coverage for both helper availability and doc-id propagation across the pipeline.

## Deliverables
1. **Code Fixes**
   - Update `src_common/vector_store/cassandra.py` to restore proper indentation (or refactor to module-level helpers explicitly referenced) so `CassandraVectorStore` exposes `_json_default` et al.
   - While touching `_normalise_document`, assert `doc_id/source_hash/environment` remain intact; emit meaningful errors if missing.
   - Audit pipeline manifests to ensure Gate 0 ? Pass C include the needed metadata for Pass D; add explicit handoff (e.g., `pass_c_manifest.json`) if gaps exist.
2. **Tests**
   - Unit test for `CassandraVectorStore._normalise_document` verifying payload serialization uses `_json_default` (datetime ? ISO string) and accepts document ids from metadata.
   - Regression test exercising Pass D over a fixture pipeline run to ensure no AttributeError and Cassandra write payload contains consistent `doc_id`, `source_hash`, `environment`.
   - Optional: contract test from Gate 0 to Pass D ensuring manifest files carry document id and source hash.
3. **Validation Artifacts**
   - Re-run (or mocked run) for `selective_1759615005_dev` or equivalent fixture showing Pass D completes, Cassandra row count > 0, and manifest lists expected doc id.
   - QA check ensuring Pass E–G can proceed (graph build, finalization, HGRN validation) with the restored metadata.

## Acceptance Criteria
- Pass D no longer raises AttributeError; pipeline advances to Pass E.
- `CassandraVectorStore` exposes helper methods and serializes payloads with ISO-formatted timestamps.
- Manifests from Gate 0 onward retain `doc_id`, `source_hash`, `environment`, `stage`; QA tools can trace each chunk back to the source document.
- Tests fail if helpers are removed or document identity drops anywhere in the pipeline.

## References
- Error logs: `env/dev/artifacts/job_1759593741_dev/manifest.json` (`error_message`), user log excerpt for `selective_1759615005_dev`.
- Source file: `src_common/vector_store/cassandra.py` (lines 360-480 show the dedented helpers).
- Chunk evidence: `env/dev/artifacts/job_1759593741_dev/pass_c/job_1759593741_dev_pass_c_chunks.jsonl` (contains `doc_id`).

## Notes for AI Dev
- Watch for mixed indentation or auto-formatters that might re-dedent nested helpers; apply lint rule or formatter config to lock this down.
- Coordinate with QA to re-run Cassandra validation queries (already scripted in `env/dev/artifacts/QA_Status_Update_20251004_1140.md`).
- If additional document-id guards are needed in downstream passes (E–G), file follow-up issues but ensure Pass D fix lands first.