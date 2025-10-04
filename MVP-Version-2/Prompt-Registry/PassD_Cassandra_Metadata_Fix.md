# Prompt: Restore Pass D Cassandra Metadata Handoff

## Background
- Job `job_1759593741_dev` (Cyberpunk v3 - CP4110 Core Rulebook.pdf, dev lane A) failed on 2025-10-04 when Pass D tried to start.
- Log extract:
  - `[2025-10-04T16:12:21.546284] Pass D failed: Pass D: Unable to determine source metadata for Cassandra persistence`
  - `[2025-10-04T16:12:21.551542] Pipeline failed: Pass D: Unable to determine source metadata for Cassandra persistence`
  - `[2025-10-04T16:12:21.566772] Job job_1759593741_dev failed: Pass D: Unable to determine source metadata for Cassandra persistence`
- Passes A–C completed; `pass_c/extraction_summary.json` reports 317 parts processed and 125,167 chunks written to `job_1759593741_dev_pass_c_chunks.jsonl`.
- Job manifest (`env/dev/artifacts/job_1759593741_dev/manifest.json`) now shows `status: failed` with the above error and `pass_d` directory is empty.

## Problem Statement
Pass D’s Cassandra writer cannot locate the source document metadata it requires (doc identifier, environment, source hash, etc.). Either Pass C failed to persist the metadata bundle Pass D expects, or Pass D’s loader is looking at the wrong artifact path/schema. Without resolving this, vector enrichment never starts and Cassandra stays empty.

## Goal
Restore the metadata handshake between Pass C and Pass D so the Cassandra persistence layer can derive the full record (doc_id, environment, source hash, chunk totals, timestamps) and proceed with chunk upserts.

## Deliverables
1. **Code Fixes**
   - Identify where Pass D collects source metadata (likely `ingest/pass_d` or shared `metadata.py`) and patch the lookup so it succeeds for unified_v1 jobs.
   - If Pass C should emit a manifest or metadata file, ensure it does so (e.g., enrich `extraction_summary.json` or add a dedicated `pass_c_manifest.json` with the required fields).
   - Harden error handling so missing metadata is reported with actionable details (which file/path/field was missing).
2. **Tests**
   - Unit coverage for the metadata loader, covering: happy path (metadata present), missing file, malformed payload.
   - Integration/fixture test that simulates the Cyberpunk job artifacts and verifies Pass D resolves metadata and schedules Cassandra writes.
3. **Validation Artifact**
   - Re-run (or mocked run) demonstrating Pass D reaches Cassandra persistence, with summary showing chunk_count > 0 for `job_1759593741_dev`.

## Acceptance Criteria
- Pass D no longer aborts with “Unable to determine source metadata…” for unified_v1 jobs.
- Required metadata fields (doc_id, environment, source hash, page_count, chunk_count) are confirmed in logs/telemetry before Cassandra load begins.
- Regression: existing jobs that already succeed in Pass D remain unaffected.

## References
- Error context: `env/dev/artifacts/job_1759593741_dev/manifest.json` (lines 1-40).
- Pass C output: `env/dev/artifacts/job_1759593741_dev/pass_c/extraction_summary.json` and `job_1759593741_dev_pass_c_chunks.jsonl` (verify chunk schema: doc_id, part_id, section_id, chunk_id, page_number, checksum).
- Previous Pass metadata: `env/dev/artifacts/job_1759593741_dev/job_1759593741_dev_pass_a_manifest.json` (contains source hash and source_info).

## Notes for AI Dev
- Confirm whether Cass persistence expects a `source_metadata.json` or similar; if the schema changed recently, update the loader accordingly.
- Coordinate with QA to validate Cassandra after the fix (they already have cqlsh commands queued in `QA_Status_Update_20251004_1140.md`).
- While you’re in Pass C/Pass D shared helpers, consider normalizing the `section_id` values emitted in chunks (currently just `"section"`), but treat that as follow-up unless it blocks metadata resolution.