# FR-001 — Source Traceability, Reconciliation & Data Health

**Date:** 2025-09-11 16:46:23  
**Status:** Proposed  
**Owner:** Platform / Ingestion / QA

## Summary
Ensure sources are traceable (SHA), enforce chunk counts, auto-reconcile mismatches, and add an admin-approval deletion queue. Provide observability and audit trail.

## User Stories & Acceptance Criteria
- **US-001.1:** Compute SHA for each source; acceptance = SHA stable across identical inputs.  
- **US-001.2:** Enforce expected vs actual chunk counts; acceptance = mismatch triggers reconcile.  
- **US-001.3:** Auto reconcile drift; acceptance = stale chunks purged after reprocess.  
- **US-001.4:** Queue missing sources for admin approval; acceptance = deletion requires approval.

## Test Plan
- **Unit:** SHA stable, mismatch detection, deletion queue entry.  
- **Functional:** Inject mismatch → reconcile run; missing source → queued for deletion.  
- **Regression:** Healthy sources remain stable.  
- **Security:** RBAC for deletion approvals; audit log covers actions.

## Definition of Done
- SHA tracking visible in DB/UI.  
- Reconcile job operational.  
- Admin deletion queue live.  

## Implementation Tasks by User Story

### US-001.1 — Compute Source SHA
- Tasks:
  - Define canonicalization rules for sources (e.g., raw bytes vs. normalized text; newline/whitespace policy).
  - Implement `compute_sha256(source: bytes|str) -> str` with explicit encoding and normalization.
  - Persist SHA in storage (DB column or `manifest.source_sha_map`) at import and post-process checkpoints.
  - Add CLI `ingest sha verify <source_id>` to recompute and compare stored SHA.
  - Surface SHA in Admin UI detail view and logs for traceability.
- Tests:
  - Unit: identical inputs yield identical SHA; distinct inputs yield different SHA.
  - Unit: canonicalization makes path/line-ending differences produce identical SHA when intended.
  - Functional: ingestion run records SHA in manifest and logs; CLI verify passes.

### US-001.2 — Enforce Expected vs Actual Chunk Counts
- Tasks:
  - Define expected count per source (derived from TOC/Pass A or prior gold run) and persist as baseline.
  - Implement validator that compares expected vs. actual chunk records post Pass C.
  - Record mismatch event to manifest and structured logs; trigger reconcile queue item.
  - Add operator-facing summary in Admin UI with delta and suggested action.
- Tests:
  - Unit: given expected/actual counts, mismatch detector flags discrepancies correctly.
  - Functional: simulate mismatch; reconcile is queued and visible in logs/UI.

### US-001.3 — Auto Reconcile Drift
- Tasks:
  - Implement `reconcile` job: re-run chunking for affected sources; diff authoritative vs. current chunks.
  - Identify stale chunks and purge safely; repair downstream references (embeddings/graph) or mark for rebuild.
  - Ensure idempotency and audit log for all actions.
- Tests:
  - Unit: diff algorithm returns correct stale/new chunk sets.
  - Functional: after reconcile, stale chunks removed; counts align with baseline; no dangling references.

### US-001.4 — Admin-Approval Deletion Queue
- Tasks:
  - Create deletion queue (table or `artifacts/admin/deletions/*.json`) with states: PENDING, APPROVED, REJECTED, EXECUTED.
  - Add producer: missing sources detected by validator enqueue delete proposals with context and impact.
  - Add admin approval flow (UI/CLI) to approve/reject; executor performs deletion on APPROVED.
  - Enforce RBAC on approvals; write audit trail (who/when/what) and outcome.
- Tests:
  - Unit: queue state transitions valid; unauthorized approvals are denied.
  - Functional: missing source creates queue item; approval leads to deletion; rejection cancels safely.
  - Security: audit entries written and immutable; attempts without role are blocked.
