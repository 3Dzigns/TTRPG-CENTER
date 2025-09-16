# FR-028 — Evaluation Set & Gates

## Goal
Introduce a minimum viable evaluation harness with canonical queries and measurable gates.

## User Stories

**US-0281: Canonical evaluation set**
- As a QA engineer, I want at least 20 canonical multi-hop queries (rules comparisons, ABP math, builds), so that system performance is measurable.

**US-0282: Metrics and thresholds**
- As a QA engineer, I want metrics `path_success_rate`, `support_rate`, `citation_accuracy`, and `multi-hop latency`, so that quality can be tracked.
- Gate thresholds: ≥85% support rate, ≥80% path success.

## Test Cases

### Unit
- Metrics computed correctly given gold standard answers.  

### Functional
- CI run fails if metrics drop below gate thresholds.  

### Regression
- Canonical queries always in the evaluation set.  

### Security
- Ensure evaluation set does not contain PII.  
