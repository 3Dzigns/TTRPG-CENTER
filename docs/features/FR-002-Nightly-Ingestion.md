# FR-002 — Nightly Bulk Ingestion Scheduler

**Date:** 2025-09-11 16:46:23  
**Status:** Proposed  
**Owner:** Platform / Ops

## Summary
Run 6-pass ingestion nightly via Task Scheduler, produce artifacts, manifest, and logs.

## User Stories & Acceptance Criteria
- **US-002.1:** Nightly run at 02:00; acceptance = passes A–F executed sequentially.  
- **US-002.2:** Manifest created per job; acceptance = manifest.json includes job_id, pass statuses.  
- **US-002.3:** Structured logs; acceptance = NDJSON with env, pass, status.

## Test Plan
- **Unit:** Script generates job dir, manifest skeleton.  
- **Functional:** Run produces artifacts/logs; failure returns non-zero exit.  
- **Regression:** Manifest schema stable.  
- **Security:** Paths restricted to env; ExecutionPolicy bypass scoped.

## Definition of Done
- Nightly job succeeds in DEV.  
- Artifacts/logs visible.  
- On failure, a single consolidated run report is generated at `docs/bugs/RUN-YYYYMMDD_HHMMSS.md` (with optional AI enrichment when `OPENAI_API_KEY` is set).

## Implementation Tasks by User Story

### US-002.1 — Nightly Run at 02:00
- Tasks:
  - Create orchestrator wrapper script (`scripts/run_nightly_ingestion.ps1` or Python CLI) to run passes A–F.
  - Generate `job_id` using timestamp and create job directory under `artifacts/ingest/{env}/{job_id}`.
  - Configure Windows Task Scheduler (and document cron alternative) to run daily at 02:00 with correct working directory and environment.
  - Ensure non-zero exit on any pass failure; propagate code to scheduler.
- Tests:
  - Unit: `job_id` format function returns expected pattern and path resolution.
  - Functional: manual run executes A→F sequentially; failure short-circuits with non-zero code.

### US-002.2 — Manifest Per Job
- Tasks:
  - Implement manifest writer/loader with schema validation and atomic persist.
  - Update wrapper to initialize manifest and append pass results/statuses.
  - Include `job_id`, `env`, pass statuses, artifact paths, and metrics.
- Tests:
  - Unit: manifest round-trip (serialize/deserialize) preserves data; schema validates.
  - Functional: job directory contains `manifest.json` with all passes recorded.

### US-002.3 — Structured NDJSON Logs
- Tasks:
  - Add NDJSON logger emitting one line per event with fields: `ts`, `level`, `env`, `job_id`, `pass`, `status`, `message`, `error`.
  - Rotate logs per job directory; ensure append-only with UTF-8 encoding.
- Tests:
  - Unit: logger produces well-formed JSON lines with required fields.
  - Functional: log file includes start/end for each pass and final summary; malformed lines are not emitted.

### US-002.4 — Post-run Consolidated Bug Report
- Tasks:
  - Extend `scripts/post_run_bug_scan.py` with `--single-report` mode that consolidates all failures in a run into one markdown report, defaulting to `docs/bugs/RUN-<timestamp>.md`.
  - Add optional OpenAI enrichment controlled by `--ai-enrich` and `OPENAI_API_KEY` to draft a single, structured report for review.
  - Update `scripts/run_nightly_ingestion.ps1` to invoke consolidated mode after each run.
- Tests:
  - Functional: with failures present, a `RUN-*.md` is created summarizing groups and instances.
  - Functional: with `OPENAI_API_KEY`, the report includes an "AI Consolidated Report" section.
