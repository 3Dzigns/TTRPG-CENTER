# Ingestion Pipeline Runbook (MVP v2)

## Overview
- Coordinates Pass 0 through Pass G for every ingestion job and records a manifest under `env/<env>/artifacts/<job_id>/manifest.json`.
- Every pass emits structured JSON artifacts with lineage (`doc_id`, `part_id`, `section_id`) and is indexed in the manifest alongside SHA-256 checksums.
- Jobs execute inside the environment root reported by the Environment Validator (`env/dev`, `env/test`, `env/prod`).

## Directory Layout
- `env/<env>/artifacts/<job_id>/pass_b/parts/*.pdf` – logical splits generated when files exceed the configured threshold.
- `pass_c/{job_id}_pass_c_chunks.jsonl` – extraction output (JSONL) with one chunk per line.
- `pass_d/{job_id}_pass_d_vectors.jsonl` – vector enrichments and dictionary delta `dict_delta.passD.json`.
- `pass_e/graph.json` – knowledge graph nodes/edges plus `dict_delta.passE.json`.
- `pass_f/manifest.snapshot.json` – snapshot of all artifacts and verification report.
- `pass_g/hgrn.report.json` – HGRN issues and recommended admin actions.

## Pass Summary
- **Pass 0 – Preflight**: Computes file hash/page count, short-circuits duplicates. Manifest status set to `skipped` with `skip_reason`.
- **Pass A – ToC Parser**: Generates dictionary seeds consumed by Pass B. Output stored beside manifest.
- **Pass B – Logical Split**: Uses `PASS_B_SPLIT_THRESHOLD_MB` (default 10) to decide whether to split. Produces `split_index.json` plus per-part metadata.
- **Pass C – Extraction**: Calls Unstructured when available, otherwise falls back to deterministic `pypdf` extraction when `ALLOW_UNSTRUCTURED_FALLBACK=true`.
- **Pass D – Vector Enrichment**: Sends chunks to Haystack when configured; deterministic fallback builds embeddings locally (`PASS_D_EMBED_DIM`).
- **Pass E – Graph Builder**: Uses LlamaIndex when installed, otherwise constructs a linear graph linking sequential chunks.
- **Pass F – Finalizer**: Verifies checksums, merges deltas, and emits a manifest snapshot for downstream consumers.
- **Pass G – HGRN Consistency**: Flags dangling references, orphan nodes, and builds `hgrn.actions.json` for Admin UI prompts.

## Running the Pipeline
```bash
python -m services.ingest.pipeline <job_id> <path_to_pdf>
```
- Ensure `TARGET_ENV` is exported prior to execution (`dev`, `test`, or `prod`).
- The bootstrap script `scripts/init-environments.ps1` provisions required directories if they do not exist.


## Security & Audit Logging
- Upload endpoints require an admin JWT; tokens are validated by `bootstrap_app_security`. Requests without a valid `Authorization: Bearer` header receive `401/403`.
- Source gating is enforced by the orchestrator via `ALLOWED_SOURCES` in `env/<env>/config/.env`. Update this variable when onboarding new trusted stores.
- Every ingestion mutation writes a structured audit record to `env/<env>/logs/audit/audit-<YYYYMMDD>.log`. Include these logs when handing off to Ops or during postmortems.
- Configure OpenTelemetry exporters via `OTLP_ENDPOINT` in the environment `.env` to send ingestion traces to the shared collector.

## Troubleshooting
- **Duplicate detected**: Manifest status `skipped`; confirm SHA in `manifest.json > source.file_sha` and either purge old artifacts or re-upload with unique content.
- **Pass failures**: `manifest.json > failed_pass` indicates the failing stage. Inspect the pass-specific summary (e.g., `pass_c/extraction_summary.json`).
- **Missing artifacts**: Pass F reports checksum failures in `pass_f/validation_report.json`. Re-run from Pass B after cleaning corrupted files.
- **Graph anomalies**: Pass G report includes `severity` and recommended `action`. Critical issues block promotion to Admin guidance until resolved.

## Validation & Regression
- Run `pytest tests/unit/test_ingestion_pipeline_v2.py` to execute unit coverage for thresholds, fallbacks, vectors, graph integrity, finalization, and HGRN checks.
- Golden fixtures live under `tests/regression/golden_masters`. The regression test verifies manifests include mandatory passes and artifact prefixes for both a born-digital and a scanned PDF.

## Recovery Procedures
1. Inspect `manifest.json` for the last successful pass and remove downstream directories (`pass_*`) beyond that point.
2. Re-run the pipeline; the orchestrator will resume from Pass A (or Pass 0 if the manifest was removed).
3. For environment outages, rotate credentials by updating `env/<env>/config/.env` and re-running the pipeline. Tool versions captured in manifest help audit discrepancies.

## Interfaces & Consumers
- Admin UI (Task 04) consumes `manifest.snapshot.json`, `hgrn.report.json`, and `hgrn.actions.json`.
- Dictionary services ingest combined deltas from Pass D/E/F located in the respective `dict_delta.*.json` artifacts.
- Metrics exporters can tail structured logs (logger `services.ingest.pipeline`) or parse manifest summaries for timing information.
