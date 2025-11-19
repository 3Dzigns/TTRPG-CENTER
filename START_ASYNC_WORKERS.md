# Start Async Workers - Command Reference

## 🚀 Quick Start - All Workers at Once

```bash
# Start all 3 async workers in background
docker exec -d ttrpg_ingestion_engine bash -c "cd /app/scripts && python3 gate_0_hash_worker.py --log-level INFO"
docker exec -d ttrpg_ingestion_engine bash -c "cd /app/scripts && python3 gate_0_validate_worker.py --log-level INFO"
docker exec -d ttrpg_ingestion_engine bash -c "cd /app/scripts && python3 doc_splitter_worker.py --log-level INFO"

echo "✅ Workers started in background"
```

## 📋 Individual Worker Commands

### Start gate_0_hash_worker
```bash
docker exec -d ttrpg_ingestion_engine bash -c "cd /app/scripts && python3 gate_0_hash_worker.py --log-level INFO"
```

### Start gate_0_validate_worker
```bash
docker exec -d ttrpg_ingestion_engine bash -c "cd /app/scripts && python3 gate_0_validate_worker.py --log-level INFO"
```

### Start doc_splitter_worker
```bash
docker exec -d ttrpg_ingestion_engine bash -c "cd /app/scripts && python3 doc_splitter_worker.py --log-level INFO"
```

## 🧪 Queue a Test Job

```bash
docker exec ttrpg_ingestion_engine bash -c \
  "cd /app/scripts && python3 ingestion_wrapper_async.py \
   --source '/Transfer_Station/sources/Cyberpunk v3 - CP4110 Core Rulebook.pdf'"
```

## 📊 Monitor Workers

### Check if workers are running
```bash
docker exec ttrpg_ingestion_engine ps aux | grep worker
```

Expected output:
```
root  123  gate_0_hash_worker.py
root  456  gate_0_validate_worker.py
root  789  doc_splitter_worker.py
```

### Check worker logs
```bash
# Live tail all worker logs
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_hash/worker.log &
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_validate/worker.log &
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/doc_splitter/worker.log &
```

### Check heartbeat files
```bash
cat /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_hash/heartbeat.json
cat /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_validate/heartbeat.json
cat /e/n8n_TTRPG_Transfer_Station/Logs/doc_splitter/heartbeat.json
```

### Monitor job progress
```bash
# Watch job status (updates every 2 seconds)
watch -n 2 'find /e/n8n_TTRPG_Transfer_Station/jobs -name status.json -exec cat {} \; | jq -r ".job_id, .current_stage, .status, .validation_status"'
```

## 🛑 Stop Workers

```bash
# Kill all async workers
docker exec ttrpg_ingestion_engine pkill -f "gate_0_hash_worker.py"
docker exec ttrpg_ingestion_engine pkill -f "gate_0_validate_worker.py"
docker exec ttrpg_ingestion_engine pkill -f "doc_splitter_worker.py"
```

## 🔍 Troubleshooting

### Workers not starting?
```bash
# Test worker imports
docker exec ttrpg_ingestion_engine bash -c \
  "cd /app/scripts && python3 -c 'import async_worker_base; print(\"✅ Imports OK\")'"
```

### Find job locations
```bash
find /e/n8n_TTRPG_Transfer_Station/jobs -type d -maxdepth 2
```

### Check job status
```bash
# Find all status.json files
find /e/n8n_TTRPG_Transfer_Station/jobs -name status.json -exec cat {} \; | jq
```

## 📁 File Locations

**Container**:
- Workers: `/app/scripts/`
- Working directory: `/app`

**Host**:
- Source code: `E:\n8n_TTRPG_Center\ingestion\`
- Job queues: `E:\n8n_TTRPG_Transfer_Station\jobs\`
- Worker logs: `E:\n8n_TTRPG_Transfer_Station\Logs\`
- Test files: `E:\n8n_TTRPG_Transfer_Station\sources\`

## ✅ Current Status

**Running Workers**:
- ✅ unstructured_job_worker.py (old synchronous worker)

**Not Running** (need to start):
- ❌ gate_0_hash_worker.py
- ❌ gate_0_validate_worker.py
- ❌ doc_splitter_worker.py

**Action Required**: Run the "Quick Start" commands above to start the async workers.

---

**Next**: Start workers, queue a test job, monitor progress
