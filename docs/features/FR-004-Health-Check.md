# FR-004 — Health Check & Continuous Improvement

**Date:** 2025-09-11 16:46:23  
**Status:** Proposed  
**Owner:** QA / Retrieval / Graph

## Summary
Run daily health check on Q&A, compute metrics (accuracy, citations, latency), and propose corrective actions (re-chunk, re-embed, rebuild graph).

## User Stories & Acceptance Criteria
- **US-004.1:** Generate daily report; acceptance = report saved under artifacts/health/{date}.  
- **US-004.2:** Propose corrective actions; acceptance = low accuracy triggers re-chunk proposal.  
- **US-004.3:** Queue actions for admin approval; acceptance = no auto-delete without approval.

## Test Plan
- **Unit:** Metrics calculators correct; threshold triggers.  
- **Functional:** Simulated Q&A → report + actions; admin approval applies fix.  
- **Regression:** Golden eval set stable.  
- **Security:** Reports redact PII; actions require approval.

## Definition of Done
- Daily report generated.  
- Actions queued for admin review.  

## Implementation Tasks by User Story

### US-004.1 — Daily Health Report
- Tasks:
  - Define evaluation set (golden Q&A pairs with expected citations) and store in repo or data bucket.
  - Implement runners to execute Q&A over the eval set; collect metrics: accuracy@k, citation coverage, latency percentiles.
  - Emit report to `artifacts/health/{date}/report.json` (+ optional HTML summary).
  - Schedule job daily (can reuse nightly infra) and tag with environment.
- Tests:
  - Unit: metrics calculators (accuracy, precision/recall for citations, latency stats) handle edge cases.
  - Functional: dry-run produces report with correct schema in expected directory.

### US-004.2 — Propose Corrective Actions
- Tasks:
  - Define thresholds and rules mapping metrics to actions (e.g., low accuracy → re-chunk with size X; latency high → rebuild index).
  - Generate `actions.json` with action type, target scope, rationale, and estimated impact.
  - Deduplicate proposals across runs and link to prior attempts/outcomes.
- Tests:
  - Unit: rules trigger correct actions given synthetic metric inputs.
  - Functional: simulated poor metrics generate expected proposals with rationales.

### US-004.3 — Queue Actions for Admin Approval
- Tasks:
  - Reuse admin queue mechanism (see FR-001) to enqueue actions with states and audit trail.
  - Admin UI/CLI to approve/deny and to execute approved actions via orchestrated jobs.
  - Enforce RBAC; never auto-delete without explicit approval.
- Tests:
  - Unit: queue gating prevents execution before approval; state transitions tracked.
  - Security: role checks enforced; audit entries persisted.
