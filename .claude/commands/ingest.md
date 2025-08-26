# Command: Run Ingestion
You are Claude Code. Execute the end-to-end ingestion pipeline on the given path(s) and stream per-phase status.

## Inputs
- `--paths`: one or more local file/folder paths
- `--env`: dev | test | prod (default: dev)
- `--batch-size`: integer for embed/upsert batching (default 64)

## Steps
1. Restate the task and the selected ENV.
2. Validate config for ENV (AstraDB, Redis/websocket channel for status, temp storage path).
3. For each file:
   - **Pass A (Parse/Structure)**: Upload → temp storage; emit `status=running`, `progress`, file size and ETA.
   - **Pass B (Enrich/Dictionary)**: Normalize terms, emit percent + last 2–3 chunk previews in **plain language**.
   - **Pass C (Graph Compile)**: Update workflows, verify graph nodes link to dictionary/RAG.
   - Upsert enriched chunks into AstraDB (batched, retry on failure).
4. On errors, emit **actionable** messages and keep processing other inputs.
5. Output a concise summary table (file → success/fail, counts, duration).

## Expected Artifacts
- A per-job manifest in `./artifacts/ingest/{ENV}/{JOB_ID}/manifest.json`
- Status events published via Redis pub/sub or SSE topic: `ingest:{ENV}:{JOB_ID}`

## Test
- Run API smoke test for ingestion endpoints.
- Confirm Admin UI receives per-phase updates and displays dictionary in natural language.
