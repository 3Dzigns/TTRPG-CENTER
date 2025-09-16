# FR-022: Automated Evaluation & Hallucination Reduction Layer

## Summary
Introduce an automated evaluation and self-checking layer that continuously validates model outputs against ingested sources, dictionary entries, and graph nodes. This layer leverages **HGRN (Hybrid Graph Reasoning Network)** introduced in **FR-021** to act as a second-pass grounding check during ingestion *and* at query-time, surfacing recommended corrections to the Admin UI.  

The goal is to ensure answers remain faithful to source material, hallucination rates are tracked/reduced, and admins have fine-grained control to accept/reject automated recommendations.

---

## Epics & User Stories

### Epic E8.1 — Auto Evaluation Harness

**US-801: Eval Harness at Query Time**  
*As* a User  
*I want* every answer to be checked against retrieved chunks and graph nodes  
*So that* hallucinated or unsupported claims are flagged.  

**Acceptance Criteria**  
- Each answer passes through a hallucination-check pipeline:  
  - **Fact extractor → cross-check with retrieval set + HGRN graph nodes.**  
- If a claim lacks support:  
  - Inline warning: “⚠️ Unsupported statement — please verify.”  
  - Logged for Admin review.  
- Eval harness produces metrics per query: `support_rate`, `halluc_rate`, `cit_accuracy`.  

**Tests**  
- *Unit:* Unsupported claim correctly flagged in stub dataset.  
- *Functional:* Complex query returns warning when model strays outside retrieved context.  
- *Regression:* Baseline hallucination rate ≤ previous release.  
- *Security:* Eval logs redact user input and secrets.

---

### Epic E8.2 — HGRN-Backed Sanity Layer

**US-802: HGRN Cross-Check on Ingestion**  
*As* a Pipeline Engineer  
*I want* ingestion chunks and graph links validated by HGRN  
*So that* dictionary metadata and graph nodes remain consistent with source PDFs.  

**Acceptance Criteria**  
- HGRN runs on Pass C output (graph compile).  
- If discrepancies found (e.g., dangling edges, mis-typed nodes), a correction bundle is created in `artifacts/hgrn/{JOB_ID}/recommendations.json`.  
- Admin UI presents changes as “Suggested Corrections” with *Accept/Reject*.  

**Tests**  
- *Unit:* Inject malformed edge → correction bundle generated.  
- *Functional:* PDF ingestion with deliberate metadata mismatch produces Admin recommendations.  
- *Regression:* Golden PDFs ingest without spurious corrections.  
- *Security:* Correction bundles sanitized, no raw secrets included.

---

### Epic E8.3 — Admin UI Controls

**US-803: Accept/Reject Auto Corrections**  
*As* an Admin  
*I want* to review suggested corrections in the Admin UI  
*So that* I remain in control of dictionary and graph integrity.  

**Acceptance Criteria**  
- New Admin panel: “Auto Evaluation” with:  
  - Pending suggestions list.  
  - Accept → applies correction to dictionary/graph.  
  - Reject → logs decision, keeps baseline unchanged.  
- Audit trail stored in `/audit/hgrn_corrections.log`.  

**Tests**  
- *Unit:* Accept applies fix, Reject leaves baseline intact.  
- *Functional:* Admin UI updates correction status in real-time.  
- *Regression:* Previously accepted fixes remain applied after upgrade.  
- *Security:* Only Admin role can apply corrections.

---

### Epic E8.4 — Continuous Hallucination Tracking

**US-804: Metrics & Alerts**  
*As* an Operator  
*I want* hallucination metrics tracked over time  
*So that* alerts trigger if hallucinations rise above thresholds.  

**Acceptance Criteria**  
- Metrics emitted: hallucination rate, citation accuracy, unsupported claim count.  
- Alerts configured (Phase 4 alert system) if `halluc_rate > 5%`.  
- Metrics visible in dashboard (Phase 4 observability).  

**Tests**  
- *Unit:* Simulated queries → hallucination rate correctly calculated.  
- *Functional:* Threshold breach triggers alert.  
- *Regression:* Metrics schema stable across releases.  
- *Security:* Metrics aggregated, no PII leakage.

---

## Test Plan Additions

| Test Type     | New Requirements                                                                                   |
|---------------|----------------------------------------------------------------------------------------------------|
| **Unit**      | Fact extractor flags unsupported claims; correction bundles generated on malformed graph edges.     |
| **Functional**| End-to-end query → hallucinated claim flagged; Admin accepts correction → dictionary updated.      |
| **Regression**| Baseline hallucination rate ≤ prior release; golden PDFs ingest without false correction.          |
| **Security**  | Eval logs redact user text; Admin actions logged with checksum; correction bundles sanitized.      |

---

## Definition of Done (FR-022)
- Every answer evaluated against retrieval + graph, hallucinated claims flagged.  
- HGRN runs as ingestion sanity layer, producing correction bundles.  
- Admin UI exposes corrections with Accept/Reject.  
- Continuous hallucination metrics tracked; alerts fire at thresholds.  
- All new unit, functional, regression, and security tests pass in CI.  
