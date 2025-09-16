# Feature Request FR-021 — HGRN Second-Pass Sanity Check with Source Book Alignment

## Summary

Introduce a **second-pass validation layer** using the **Hierarchical Graph Reasoning Network (HGRN)** to perform a sanity check on ingestion outputs. The pass will (1) validate dictionary metadata, (2) verify graph node/edge integrity, and (3) compare chunked artifacts against the original source book text to ensure alignment. The system will propose **recommended changes** via the Admin UI, which admins can accept or reject.

This ensures that the ingestion pipeline produces consistent, accurate metadata and graph structures, while giving admins fine-grained control to approve or deny corrections.

---

## Goals

1. Clone HGRN package from GitHub (outside repo, pinned version; no vendoring).
2. Run HGRN as a **second pass** after Pass C (graph compile) in Phase 1【83†Phase1.txt】.
3. Compare dictionary metadata and graph nodes/edges against:
   - **Option A (preferred):** Pass A/B/C artifacts from unstructured.io + Haystack + LlamaIndex (avoids duplicate OCR).
   - **Option B (fallback):** OCR-based re-read of source PDF when chunk coverage is insufficient or integrity checks fail.
4. Flag discrepancies (missing terms, malformed edges, out-of-sync metadata).
5. Surface **recommendations** in Admin UI (Phase 4【81†phase4.txt】, Phase 5【80†Phase5.txt】):
   - Suggested metadata corrections.
   - Suggested edge/node adjustments.
   - Confidence scores per recommendation.
6. Admin may **accept/deny** changes, with audit trail stored (Phase 7【87†Phase7.txt】).

---

## User Stories

### US-021A: HGRN Second Pass
**As** a system architect  
**I want** HGRN to analyze dictionary metadata and graph integrity  
**So that** ingestion outputs have an additional sanity check before promotion.

*Acceptance Criteria*
- HGRN pass runs after Pass C and before Phase 2 retrieval【84†Phase2.txt】.
- Outputs `hgrn_report.json` containing:
  * `missing_terms`, `metadata_conflicts`, `graph_inconsistencies`.
  * Recommended corrections with confidence scores.
- Report stored in `artifacts/{ENV}/{JOB_ID}/`.

---

### US-021B: Chunk-to-Source Validation
**As** a data quality engineer  
**I want** to verify chunk artifacts against the original source book  
**So that** metadata errors and omissions are detected.

*Acceptance Criteria*
- Primary method: Use Pass A/B artifacts from unstructured.io and enrich passes【83†Phase1.txt】.
- Compare normalized chunk text against original spans to detect truncation, duplicates, or missed content.
- If ≥10% of source content is unmatched, trigger OCR fallback to re-parse PDF for cross-check.

---

### US-021C: Admin UI Integration
**As** an admin  
**I want** to see proposed changes surfaced in the Admin UI  
**So that** I can approve or deny metadata/graph corrections.

*Acceptance Criteria*
- Admin UI panel “Sanity Check Recommendations.”
- Shows grouped recommendations:
  * **Dictionary:** Add/update/delete term suggestions.
  * **Graph:** Add/remove/redirect edges, merge/split nodes.
- Each suggestion shows:
  * Confidence score (0–1).
  * Raw evidence (chunk IDs, page refs).
- Accept/Reject recorded in audit log【87†Phase7.txt】.

---

### US-021D: CI Guardrails
**As** a developer  
**I want** to ensure HGRN second-pass does not pollute repo or fail silently  
**So that** it remains optional but reliable.

*Acceptance Criteria*
- HGRN package cloned in build/runtime (scripted in Dockerfile), never stored in repo (Phase 0 guardrails【86†Phase0.txt】).
- CI validates presence of `hgrn_report.json` for fixture PDFs.
- If recommendations differ from baseline > threshold, mark job yellow (warning) but not hard fail.
- Ensure time budget ≤2× baseline ingestion runtime.

---

## Test Cases

### Unit Tests
- HGRN validator detects known dictionary error (missing key term).
- Graph inconsistency injection (dangling edge) → flagged in `hgrn_report.json`.
- Chunk truncation injection → flagged against source artifacts.

### Functional Tests
- Ingest fixture PDF → run Pass A/B/C → run HGRN pass → `hgrn_report.json` produced with ≥1 recommendation.
- Admin UI displays recommendation panel with accept/deny actions.
- Accepting change updates dictionary entry in AstraDB; rejecting leaves untouched.

### Regression Tests
- Fixture PDFs with golden dictionary/graph produce empty/no-op `hgrn_report.json`.
- OCR fallback triggers only when >10% mismatch.

### Security Tests
- HGRN never writes outside `artifacts/` directory.
- Recommendations sanitized (no HTML injection) before showing in Admin UI.
- Audit log immutable, append-only.

---

## Deliverables

- `src_hgrn/runner.py`: wrapper to run HGRN and produce `hgrn_report.json`.
- Dockerfile: clone HGRN package at pinned version (outside repo).
- Admin UI (Phase 4/5) component: “Sanity Check Recommendations.”
- Audit log entries under `/audit/hgrn.log` (Phase 7【78†Phase7.txt】).

---

## Definition of Done

* HGRN integrated as Pass D (sanity check) in ingestion pipeline【83†Phase1.txt】.
* Reports (`hgrn_report.json`) produced for all ingestion jobs.
* Admin UI allows approve/reject with audit trail【81†phase4.txt】【87†Phase7.txt】.
* CI validates on fixture PDFs with injected errors.
* OCR fallback available but only invoked if chunk artifacts insufficient.
