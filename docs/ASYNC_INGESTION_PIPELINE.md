# Async Ingestion Pipeline

## 1. Overview
The TTRPG Center ingestion pipeline processes source files placed under `/Transfer_Station/sources` and produces dictionary entries, embeddings, and graph artifacts across Postgres, Cassandra, and Neo4j. Each stage is implemented as a dedicated Celery worker that communicates via RabbitMQ queues while persisting job state inside the shared Postgres-backed registry. Every worker writes a human-readable status snapshot to `/Transfer_Station/jobs/{job_id}.status.json`, enabling quick diagnosis without scanning logs.

### Key Guarantees
- **Asynchronous orchestration**: workers are bound to explicit queues (`unstructured`, `ingestion_engine`, `haystack`, `cassandra_upsert`, `llamaindex`, `graph_upsert`, `housekeeping`, `health_verifier`).
- **Idempotency & refresh safety**: per-stage fingerprints and ready markers ensure retries never produce duplicates and refresh jobs replace data deterministically.
- **Observability**: structured logging, Prometheus metrics, OpenTelemetry spans, DLQ capture, and status snapshots.
- **Operational tooling**: CLI commands (`job_management`, `status_monitor`, `log_monitor`) provide manual control and visibility.

## 2. Shared Volume Layout
All containers mount `/Transfer_Station` and agree on the following structure:

| Path | Purpose |
| --- | --- |
| `sources/` | Inbound files scanned by Source Sentinel. |
| `artifacts/{job_id}/` | Working directory for each pass (Unstructured output, metadata, embeddings, LlamaIndex artifacts, etc.). |
| `logs/` | Pipeline logs (tailed by `log_monitor`). |
| `jobs/{job_id}.status.json` | Human-readable snapshot containing stage, timestamps, counts, and last error. |
| `jobs/dlq.jsonl` | Dead-letter archive. |

## 3. Job Lifecycle
1. **Discovery** – Source Sentinel scans `sources/` every five minutes. If no active job exists, it enqueues `unstructured.process` with a deterministic job ID.
2. **Pass A (Unstructured → Metadata → Dictionary)**  
   - `unstructured.process`: runs the Unstructured pipeline; writes `artifacts/{job_id}/unstructured/elements.json`.  
   - `ingestion_engine.elements_to_metadata`: normalizes elements, writes metadata, records fingerprint to keep retries idempotent.  
   - `ingestion_engine.dictionary_upsert`: upserts normalized terms into Postgres, clearing existing entries once on refresh jobs.
3. **Pass B (Embeddings)**  
   - `haystack.generate_embeddings`: hashes payload, generates embeddings via provider (OpenAI or mock), saves `embeddings.json`. Content/model hash prevents redundant work.  
   - `cassandra_upsert.write`: upserts vectors into Cassandra, computes checksum, records a `ready.marker` file containing checksum + row count, then dispatches LlamaIndex.
4. **Pass C (Index + Graph)**  
   - `llamaindex.build_indices`: waits for the embeddings `ready.marker`, produces `llamaindex/ready.marker`, updates registry state, then queues Neo4j.  
   - `graph_upsert.write`: currently a stub; will materialize graph writes after LlamaIndex completes.
5. **Housekeeping** – Finalizes the job once all expected counts are recorded or enqueues removal flows. Removal jobs clear dictionary rows, Cassandra partitions, artifacts, and mark the job `REMOVED`.
6. **Health Verifier** – Scheduled nightly; recomputes checksums and counts. If mismatched, it enqueues a refresh job; if the source file disappears, it creates a removal job.
7. **Status Snapshots** – The registry writes `/jobs/{job_id}.status.json` on every state change and when failures occur. Snapshots include artifact paths, counts, and the last error message.

### Retry & DLQ Behaviour
- All tasks inherit exponential backoff with jitter (default max retries = 5).  
- When retries are exhausted, the base task pushes a payload to `dlq.record_failure`, which appends an entry to `/Transfer_Station/jobs/dlq.jsonl`.  
- Status snapshots capture the final error so operators can see failure causes at a glance.

## 4. Ready Markers & Idempotency
- **Elements & dictionary**: JSON fingerprints ensure each stage runs exactly once per unique content.  
- **Embeddings**: `ready.marker` (checksum + row count) tells downstream stages that Cassandra writes are durable.  
- **LlamaIndex**: Another ready marker signals completion so `graph_upsert` starts strictly after Pass C.  
- **Refresh jobs**: Purge markers (`dictionary_upsert_purge`, `cassandra_upsert_purge`) prevent repeated deletes.

## 5. Metrics & Tracing
- Every task increments `pipeline_task_started_total`, `pipeline_task_succeeded_total`, `pipeline_task_failed_total`, `pipeline_task_duration_seconds`, and `pipeline_retries_total`.  
- OpenTelemetry spans wrap expensive blocks such as file reads, metadata enrichment, embedding generation, Cassandra upsert, and LlamaIndex builds. Attributes include job ID, source ID, counts, and timing details.

## 6. Operational CLI Cheatsheet

| Command | Description |
| --- | --- |
| `job_management start --file <path> [--refresh] [--yes]` | Preview & queue a manual ingestion job. |
| `job_management mark-unhealthy --file <path> [--yes]` | Force existing jobs for the source into FAILED state. |
| `job_management remove --file <path> [--yes]` | Enqueue a removal job (with effects preview). |
| `job_management dlq-inspect [--limit N]` | Dump recent DLQ entries. |
| `status_monitor [--file <path>] [--deep] [--json]` | View registry entries with optional live counts. |
| `log_monitor [--follow] [--file <path>] [--errors]` | Tail logs or show recent errors only. |

## 7. Extending the Pipeline
- **Graph upsert**: replace the stub with Neo4j writes, reading the `llamaindex` artifacts once the ready marker exists.  
- **Observability**: integrate span exporters (OTLP, Jaeger) and expose Prometheus metrics via container ports defined by `METRICS_HOST`/`METRICS_PORT`.  
- **Testing**: Expand integration coverage to include DLQ routing and refresh/removal flows once Cassandra & Neo4j operations are fully implemented.  

