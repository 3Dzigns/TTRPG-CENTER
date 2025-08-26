# Command: Trace Ingestion Status
Show live per-phase status for a given JOB_ID, with last 20 log lines per phase.

## Inputs
- `--job`: JOB_ID (required)
- `--env`: dev | test | prod (default: dev)

## Steps
1. Connect to ENV config and subscribe to `ingest:{ENV}:{JOB_ID}` channel.
2. Render a compact, updating view:
   - Phase → status (`queued | running | stalled | error | done`)
   - Progress % and `updated_at` timestamp
   - Tail 20 log lines per phase
3. If a phase is stalled for > N minutes, suggest remediation actions (retry chunk, requeue batch, etc.).

## Output
- Terminal-friendly status table
- JSON snapshot saved to:
