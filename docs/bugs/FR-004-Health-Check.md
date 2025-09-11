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
