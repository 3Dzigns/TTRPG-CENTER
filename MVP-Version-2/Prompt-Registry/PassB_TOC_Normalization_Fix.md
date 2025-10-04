# Prompt: Stabilize Pass B TOC Normalization

## Background
- Job `job_1759593741_dev` on 2025-10-04 split *Cyberpunk v3 - CP4110 Core Rulebook.pdf* (24.16 MB, 382 pg) into 317 parts during Pass B.
- `split_plan.json` shows every TOC entry flagged as `large_section_chunked`, repeatedly assigning the same 30-page windows to different `section_id`s (e.g. parts 01 and 11 both cover pages 1-30).
- OCR outputs for headings contain severe noise ("Cyberpunk Essence...1", "S t a rt at Page"), so section boundaries fail to resolve and Pass B defaults to brute-force 30-page chunks.
- The duplication explodes Pass C throughput (˜700 chunks per part, ~13k chunks after 19/317 parts).

## Problem Statement
We need a preprocessing step that normalizes noisy TOC text before Pass B decides on split ranges. Better title cleanup should prevent phantom sections spanning the whole document and reduce duplicate page windows.

## Goal
Implement TOC normalization (or fallback suppression) so Pass B produces at most one part per true document segment. The immediate target is for the Cyberpunk job to yield =40 parts with distinct page ranges.

## Deliverables
1. Code changes in the ingestion pipeline (likely TOC parsing utilities in `ingest/pass_b` or shared OCR helpers).
2. Unit/integration coverage demonstrating:
   - No duplicate 30-page windows for identical headings.
   - Normalized titles for headings like "S t a rt at Page" ? "Start at Page".
3. Re-run (or dry-run) evidence showing `split_plan.json` for the Cyberpunk source produces the reduced part count.

## Acceptance Criteria
- Pass B part counts obey token/page thresholds *without* repeated ranges.
- Normalization logic is resilient to dotted leaders, extra whitespace, and interspersed numerals.
- Guardrails: if the TOC remains unusable after cleanup, Pass B must fall back to a single-section split instead of cloning segments.

## References
- Artifact root: `env/dev/artifacts/job_1759593741_dev/pass_b/`
- Key files: `split_plan.json`, `split_index.json`, `split_summary.json`.
- Status snapshot: `env/dev/artifacts/QA_Status_Update_20251004_1140.md` (Pass B/C analysis lines 48-70).

## Notes for AI Dev
- Review any shared TOC heuristics used by other jobs to avoid regressions.
- Coordinate with QA once implemented; they monitor Pass C chunk counts.