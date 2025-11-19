# Async Pipeline Deployment Instructions

## Quick Start

### 1. Copy Files to Container

The async pipeline files are in `ingestion/` directory and need to be available in the ingestion_engine container at `/opt/ingestion/`.

Since ingestion files are mounted as a volume, they should already be accessible. Verify:

```bash
docker exec ttrpg_ingestion_engine ls -la /opt/ingestion/ | grep -E 'async_|gate_0_|pipeline_routes|ingestion_wrapper'
```

If files are missing, the ingestion directory is likely mounted. No manual copy needed.

### 2. Create Job Queue Structure

```bash
# Create all required directories
mkdir -p /e/n8n_TTRPG_Transfer_Station/jobs/{gate_0_hash,gate_0_validate,doc_splitter,pass_a_unstructured,complete,failed}
mkdir -p /e/n8n_TTRPG_Transfer_Station/Logs/{gate_0_hash,gate_0_validate,doc_splitter}
mkdir -p /e/n8n_TTRPG_Transfer_Station/{Gate_0_Out,Gate_0_Check,Pass_A_Out}
```

### 3. Run the Test Script

```bash
bash E:/n8n_TTRPG_Center/scripts/test_async_vertical_slice.sh
```

This automated script will:
- Find the ingestion container
- Verify all worker files exist
- Set up directory structure
- Queue a test job with a PDF from sources
- Start 3 workers in background
- Monitor job progress for 60 seconds
- Report final status and worker logs

### 4. Manual Testing (Alternative)

If you prefer manual control:

**Terminal 1 - gate_0_hash worker:**
```bash
docker exec -it ttrpg_ingestion_engine bash
cd /opt/ingestion
python3 gate_0_hash_worker.py --log-level INFO
```

**Terminal 2 - gate_0_validate worker:**
```bash
docker exec -it ttrpg_ingestion_engine bash
cd /opt/ingestion
python3 gate_0_validate_worker.py --log-level INFO
```

**Terminal 3 - doc_splitter worker:**
```bash
docker exec -it ttrpg_ingestion_engine bash
cd /opt/ingestion
python3 doc_splitter_worker.py --log-level INFO
```

**Terminal 4 - Queue a job:**
```bash
docker exec ttrpg_ingestion_engine bash -c \
  "cd /opt/ingestion && python3 ingestion_wrapper_async.py \
   --source '/Transfer_Station/sources/Cyberpunk v3 - CP4110 Core Rulebook.pdf'"
```

**Monitor progress:**
```bash
# Watch job status files
watch -n 2 'find /e/n8n_TTRPG_Transfer_Station/jobs -name status.json -exec tail -50 {} \;'

# Or use jq for better formatting
watch -n 2 'find /e/n8n_TTRPG_Transfer_Station/jobs -name status.json -exec cat {} \; | jq'
```

## Verification

### Check Worker Health

Each worker writes a heartbeat file:

```bash
cat /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_hash/heartbeat.json
cat /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_validate/heartbeat.json
cat /e/n8n_TTRPG_Transfer_Station/Logs/doc_splitter/heartbeat.json
```

Should show:
- `worker_id`: Container name + PID
- `last_heartbeat`: Recent timestamp (within 30s)
- `jobs_processed`: Count of successful jobs
- `jobs_failed`: Count of failed jobs

### Check Worker Logs

```bash
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_hash/worker.log
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_validate/worker.log
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/doc_splitter/worker.log
```

Expected log entries:
- `Worker starting (stage=..., queue=..., poll_interval=5s)`
- `Claimed job {job_id}`
- `Job {job_id} completed successfully`
- `Job {job_id} moved to {next_stage} queue`

### Check Job Status

```bash
# Find job directories
ls -la /e/n8n_TTRPG_Transfer_Station/jobs/*/

# Read specific job status
cat /e/n8n_TTRPG_Transfer_Station/jobs/complete/{job_id}/status.json | jq

# Or check current stage
cat /e/n8n_TTRPG_Transfer_Station/jobs/*/{job_id}/status.json | jq '.current_stage, .status, .validation_status'
```

## Expected Behavior

### Test Scenario 1: New Document (Unprocessed)

**Flow**:
1. Wrapper queues job → `gate_0_hash/`
2. gate_0_hash worker claims job → computes SHA-256 → moves to `gate_0_validate/`
3. gate_0_validate worker claims job → queries Cassandra (returns 0 chunks) → sets `validation_status="unprocessed"` → moves to `doc_splitter/`
4. doc_splitter worker claims job → extracts TOC pages 1-10 → moves to `pass_a_unstructured/` (next stage)

**Expected Status**:
```json
{
  "current_stage": "pass_a_unstructured",
  "status": "queued",
  "validation_status": "unprocessed",
  "toc_extracted": true,
  "stages_completed": ["gate_0_hash", "gate_0_validate", "doc_splitter"]
}
```

### Test Scenario 2: Already Processed (Valid)

**Flow**:
1. Wrapper queues job → `gate_0_hash/`
2. gate_0_hash worker claims job → computes SHA-256 → moves to `gate_0_validate/`
3. gate_0_validate worker claims job → queries Cassandra (returns 150 chunks, matches checksum) → sets `validation_status="valid"` → moves to `complete/`
4. **Pipeline skips remaining stages** (doc_splitter, pass_a_unstructured, etc.)

**Expected Status**:
```json
{
  "current_stage": "complete",
  "status": "completed",
  "validation_status": "valid",
  "stages_completed": ["gate_0_hash", "gate_0_validate"],
  "warnings": [
    {
      "message": "Document already processed (chunks match: 150)",
      "stage": "gate_0_validate"
    }
  ]
}
```

### Test Scenario 3: Mismatch (Partial Processing)

**Flow**:
1. Wrapper queues job → `gate_0_hash/`
2. gate_0_hash worker claims job → computes SHA-256 → moves to `gate_0_validate/`
3. gate_0_validate worker claims job → queries Cassandra (returns 142 chunks, checksum says 150) → sets `validation_status="mismatch"` → moves to `doc_splitter/`
4. doc_splitter worker claims job → extracts TOC → moves to `pass_a_unstructured/` (reprocessing)

**Expected Status**:
```json
{
  "current_stage": "pass_a_unstructured",
  "status": "queued",
  "validation_status": "mismatch",
  "expected_chunk_count": 150,
  "actual_chunk_count": 142,
  "chunk_count_difference": -8,
  "stages_completed": ["gate_0_hash", "gate_0_validate", "doc_splitter"],
  "warnings": [
    {
      "message": "Chunk count mismatch, will cleanup and reprocess",
      "stage": "gate_0_validate"
    }
  ]
}
```

## Troubleshooting

### Workers Not Processing Jobs

**Check 1: Are workers running?**
```bash
docker exec ttrpg_ingestion_engine ps aux | grep worker
```

Should show Python processes for each worker.

**Check 2: Are there queued jobs?**
```bash
find /e/n8n_TTRPG_Transfer_Station/jobs/gate_0_hash -name "queued.marker"
```

If no marker files, jobs aren't queued properly.

**Check 3: Worker logs for errors**
```bash
tail -50 /e/n8n_TTRPG_Transfer_Station/Logs/*/worker.log
```

### Jobs Stuck in One Stage

**Check 1: Next stage worker running?**
If job stuck in `gate_0_hash`, check if `gate_0_validate_worker` is running.

**Check 2: Job claimed but not completed?**
```bash
find /e/n8n_TTRPG_Transfer_Station/jobs -name "claimed.marker"
```

If claimed.marker exists for >5 minutes, worker may have crashed. Kill worker and restart.

**Check 3: Routing configuration**
```bash
cat ingestion/pipeline_routes.json | jq '.default_pipeline[] | select(.stage=="gate_0_hash")'
```

Verify `next` field points to correct stage.

### Import Errors

If workers fail with `ModuleNotFoundError`:

```bash
docker exec ttrpg_ingestion_engine python3 -c "import sys; sys.path.insert(0, '/opt/ingestion'); import async_worker_base"
```

If this fails, check:
1. Files exist: `docker exec ttrpg_ingestion_engine ls -la /opt/ingestion/async_*.py`
2. Permissions: `docker exec ttrpg_ingestion_engine ls -la /opt/ingestion/ | grep async`
3. Python path: `docker exec ttrpg_ingestion_engine python3 -c "import sys; print(sys.path)"`

### File Lock Errors

If you see `fcntl.flock` errors, multiple workers may be trying to claim the same job.

**Solution**: This is normal contention. The worker that fails to claim will try the next job. No action needed.

If errors persist:
1. Check for stale claimed.marker files
2. Verify only one worker per stage is running
3. Check filesystem supports fcntl (should be fine on ext4/NTFS)

## Production Deployment

Once vertical slice is validated:

### 1. Update Container Entrypoints

Add workers to ingestion_engine container startup:

```dockerfile
# In docker/ingestion_engine/entrypoint.sh
python3 /opt/ingestion/gate_0_hash_worker.py &
python3 /opt/ingestion/gate_0_validate_worker.py &
python3 /opt/ingestion/doc_splitter_worker.py &
# ... add remaining workers
```

### 2. Add Process Monitoring

Use `supervisord` or similar to ensure workers restart on crash:

```ini
[program:gate_0_hash_worker]
command=python3 /opt/ingestion/gate_0_hash_worker.py
directory=/opt/ingestion
autostart=true
autorestart=true
stderr_logfile=/Transfer_Station/Logs/gate_0_hash/supervisor.err
stdout_logfile=/Transfer_Station/Logs/gate_0_hash/supervisor.log
```

### 3. Log Rotation

Configure logrotate for worker logs:

```
/Transfer_Station/Logs/*/worker.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0644 root root
}
```

### 4. Monitoring Dashboard

Implement `pipeline_monitor.py` to aggregate status from all jobs and heartbeat files.

### 5. Auto-Queue New Sources

Deploy `source_monitor_worker.py` to automatically queue new files every 10 minutes.

---

**Deployment Status**: Ready for testing
**Next Steps**: Run test script, validate results, deploy remaining workers
