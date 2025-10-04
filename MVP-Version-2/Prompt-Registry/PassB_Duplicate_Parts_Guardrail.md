# Prompt: Add Pass B Part Deduplication Guardrail

## Background
- Current Pass B output for job `job_1759593741_dev` created 317 PDF parts. Many are byte-for-byte identical even though they belong to different `section_id`s (`split_index.json` shows identical SHA-256 hashes for parts 01/11, 02/12, etc.).
- These duplicates flow into Pass C, where each copy generates ~700 chunks, inflating total chunks into the tens of thousands and extending runtime to ~10 hours.

## Problem Statement
We lack a deduplication step in Pass B to collapse identical page windows. Even after TOC cleanup, unforeseen OCR issues could repeat ranges, so we need a safeguard to gate Pass C from redundant work.

## Goal
Implement a lightweight dedupe layer after the initial split planning that:
1. Detects identical page spans or identical rendered PDFs.
2. Collapses duplicates to one canonical part while preserving traceability for skipped items.
3. Updates downstream manifests so Pass C only processes unique content.

## Deliverables
1. Code changes (likely in Pass B orchestrator or manifest builder) that:
   - Compare planned parts by `(page_start, page_end)` OR checksum and skip re-emitting duplicates.
   - Record metadata about skipped duplicates (e.g., `duplicates_of` field) for observability.
2. Tests covering:
   - Deduped output when multiple sections map to the same page window.
   - Assurance that distinct adjacent parts still pass through untouched.
   - Regression test for existing multi-section documents without duplication.
3. Artifact example (from Cyberpunk job or a synthetic fixture) demonstrating the reduced part count and annotated manifest.

## Acceptance Criteria
- Post-dedupe `split_summary.json` reports the smaller, unique part count.
- `split_index.json` exposes any skipped parts via metadata for audit purposes.
- Pass C ingests only the unique part set without code changes.
- Runtime for Cyberpunk job projected to drop from ~10 h to <3 h based on chunk reduction.

## References
- Duplicate evidence: `env/dev/artifacts/job_1759593741_dev/pass_b/split_index.json` (compare parts 01 & 11, 02 & 12, etc.).
- Pipeline overview: `env/dev/artifacts/QA_Status_Update_20251004_1140.md` (Pass B/C table).

## Notes for AI Dev
- Coordinate with the TOC normalization effort—both changes should compose cleanly.
- Ensure manifest schema changes (if any) are communicated to consumers (Pass C, QA tooling).