# FR-003 — Log Review & Automatic Bug Bundle Creation

**Date:** 2025-09-11 16:46:23  
**Status:** Proposed  
**Owner:** Platform / QA

## Summary
Parse ingestion logs nightly, detect errors, group by signature, and create bug bundles for admin triage.

## User Stories & Acceptance Criteria
- **US-003.1:** Parse NDJSON logs; acceptance = ignores malformed lines, extracts errors.  
- **US-003.2:** Group errors into bundles; acceptance = same signature aggregated.  
- **US-003.3:** Admin UI lists bundles; acceptance = bug_id, env, count, samples included.

## Test Plan
- **Unit:** Parser tolerant of malformed lines; hash deterministic.  
- **Functional:** Logs → bundles in artifacts/bugs/.  
- **Regression:** Bundle schema stable.  
- **Security:** Secrets redacted; bundle size capped.

## Definition of Done
- Nightly task produces bundles.  
- Bundles shown in Admin UI.  

## Implementation Tasks by User Story

### US-003.1 — Parse NDJSON Logs
- Tasks:
  - Implement tolerant NDJSON reader: stream lines, `try/except` JSON decode, skip malformed, log counters.
  - Define error extraction schema: `ts`, `env`, `pass`, `code`, `message`, `stack` (optional), `context`.
  - Provide CLI `logs extract-errors --job-dir <path>` writing `artifacts/bugs/raw_errors.jsonl`.
- Tests:
  - Unit: parser skips malformed lines and extracts required fields from valid lines.
  - Unit: supports large files via streaming without excessive memory use.

### US-003.2 — Group Into Bug Bundles
- Tasks:
  - Define signature function (e.g., hash of `(code, top_frame, message_template)` with normalization).
  - Aggregate errors by signature into bundles with fields: `bug_id`, `env`, `count`, `examples`, `first_seen`, `last_seen`.
  - Persist per-run bundles under `artifacts/bugs/{job_id}/bundles.json` and cumulative index.
- Tests:
  - Unit: identical signatures aggregate; hash is deterministic and stable across runs.
  - Functional: sample logs produce expected bundle counts and example sampling limits.

### US-003.3 — Admin UI Lists Bundles
- Tasks:
  - Add Admin UI (or CLI) view that loads bundles and displays `bug_id`, `env`, `count`, and sample messages.
  - Sort by `count` desc; allow filter by env/pass/date, and mark bundle as triaged.
  - Redact secrets; cap sample payload sizes; link to source logs.
- Tests:
  - Functional: UI/CLI renders bundles accurately with sorting/filtering.
  - Security: redactions applied; oversize samples truncated.
