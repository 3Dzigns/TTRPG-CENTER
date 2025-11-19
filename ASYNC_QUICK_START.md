# Async Pipeline - Quick Start Guide

## 🚀 One-Command Test

```bash
bash E:/n8n_TTRPG_Center/scripts/test_async_vertical_slice.sh
```

This automated script tests the complete vertical slice end-to-end.

---

## 📋 Manual Testing (4 Steps)

### 1. Start Workers (3 terminals)

**Terminal 1:**
```bash
docker exec -it ttrpg_ingestion_engine bash
cd /app/ingestion  # Container working directory is /app
python3 gate_0_hash_worker.py --log-level INFO
```

**Terminal 2:**
```bash
docker exec -it ttrpg_ingestion_engine bash
cd /app/ingestion
python3 gate_0_validate_worker.py --log-level INFO
```

**Terminal 3:**
```bash
docker exec -it ttrpg_ingestion_engine bash
cd /app/ingestion
python3 doc_splitter_worker.py --log-level INFO
```

### 2. Queue a Job

```bash
docker exec ttrpg_ingestion_engine bash -c \
  "cd /app/ingestion && python3 ingestion_wrapper_async.py \
   --source '/Transfer_Station/sources/Cyberpunk v3 - CP4110 Core Rulebook.pdf'"
```

### 3. Monitor Progress

```bash
# Watch job status (updates every 2 seconds)
watch -n 2 'find /e/n8n_TTRPG_Transfer_Station/jobs -name status.json -exec cat {} \; | jq .current_stage,.status,.validation_status'

# Or tail worker logs
tail -f /e/n8n_TTRPG_Transfer_Station/Logs/*/worker.log
```

### 4. Check Results

```bash
# Find completed job
ls /e/n8n_TTRPG_Transfer_Station/jobs/complete/

# Read final status
cat /e/n8n_TTRPG_Transfer_Station/jobs/complete/{job_id}/status.json | jq
```

---

## 📂 Key Locations

**Container**:
- Working Directory: `/app`
- Ingestion Scripts: `/app/ingestion/` (mounted from volume)

**Host** (Windows):
- Ingestion Code: `E:\n8n_TTRPG_Center\ingestion\`
- Job Queues: `E:\n8n_TTRPG_Transfer_Station\jobs\`
- Worker Logs: `E:\n8n_TTRPG_Transfer_Station\Logs\`
- Test Sources: `E:\n8n_TTRPG_Transfer_Station\sources\`

---

## ✅ Expected Flow

### New Document (Unprocessed)
```
Wrapper queues → gate_0_hash (5s)
  → gate_0_validate (Cassandra query: 0 chunks found)
  → doc_splitter (extract TOC pages 1-10)
  → pass_a_unstructured (next stage, not yet implemented)
```

**Status**: `validation_status: "unprocessed"`, `toc_extracted: true`

### Already Processed (Valid)
```
Wrapper queues → gate_0_hash (5s)
  → gate_0_validate (Cassandra query: 150 chunks found, matches checksum)
  → complete (skips all remaining stages)
```

**Status**: `validation_status: "valid"`, warning: "Document already processed"

### Partial Processing (Mismatch)
```
Wrapper queues → gate_0_hash (5s)
  → gate_0_validate (Cassandra query: 142 chunks, checksum says 150)
  → doc_splitter (cleanup + reprocess)
  → pass_a_unstructured (full reprocessing)
```

**Status**: `validation_status: "mismatch"`, `chunk_count_difference: -8`

---

## 🔧 Troubleshooting

### Workers Not Starting
```bash
# Check if files exist
docker exec ttrpg_ingestion_engine ls -la /app/ingestion/ | grep worker

# If missing, they're in the mounted volume
docker exec ttrpg_ingestion_engine ls -la /app/ingestion/
```

### Job Not Moving
```bash
# Check which stage job is in
find /e/n8n_TTRPG_Transfer_Station/jobs -name status.json -exec grep -l "job_id" {} \;

# Check if worker for that stage is running
docker exec ttrpg_ingestion_engine ps aux | grep worker

# Check worker logs for errors
tail -50 /e/n8n_TTRPG_Transfer_Station/Logs/*/worker.log
```

### Import Errors
```bash
# Test imports in container
docker exec ttrpg_ingestion_engine bash -c \
  "cd /app/ingestion && python3 -c 'import async_worker_base; print(\"OK\")'"

# If fails, check sys.path
docker exec ttrpg_ingestion_engine python3 -c "import sys; print(sys.path)"
```

---

## 📚 Documentation

**Complete Details**: `docs/ASYNC_VERTICAL_SLICE_SUMMARY.md` (26 pages)
**Deployment Guide**: `docs/ASYNC_DEPLOYMENT_INSTRUCTIONS.md`
**Implementation Status**: `docs/ASYNC_IMPLEMENTATION_COMPLETE.md`
**Progress Tracking**: `docs/ASYNC_PIPELINE_IMPLEMENTATION_PROGRESS.md`

---

## 🎯 What's Implemented

✅ Core Infrastructure:
- `pipeline_routes.json` - Centralized routing config
- `async_job_utils.py` - Job management utilities
- `async_worker_base.py` - Worker base class

✅ Vertical Slice Workers:
- `gate_0_hash_worker.py` - SHA-256 + document_id
- `gate_0_validate_worker.py` - Cassandra validation
- `doc_splitter_worker.py` - TOC extraction
- `ingestion_wrapper_async.py` - Job queueing

✅ Testing:
- `test_async_vertical_slice.sh` - Automated test script

---

## ⏭️ Next Steps

1. **Test**: Run automated script or manual testing
2. **Validate**: Verify job flows correctly through all 3 stages
3. **Deploy**: Implement remaining 10-12 workers (Phase 2B)
4. **Automate**: Add source_monitor_worker + cleanup_worker
5. **Monitor**: Build pipeline_monitor dashboard

---

**Status**: Ready for Testing ✅
**Architecture**: Validated ✅
**Documentation**: Complete ✅
