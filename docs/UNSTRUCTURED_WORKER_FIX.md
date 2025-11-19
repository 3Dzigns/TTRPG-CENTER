# Unstructured Worker Fix - Zombie Process Issue

**Date**: 2025-10-23
**Issue**: Async unstructured worker becoming zombie process and not processing jobs
**Status**: ✅ **FIXED**

## Problem Description

### Symptoms
- Worker process PID 8 showing as `[python3]` (zombie process)
- No CPU usage despite pending job in queue
- Worker log file never created
- Jobs stuck in "queued" state

### Root Cause Analysis

**Primary Issue**: `set -euo pipefail` in entrypoint.sh causing worker to die immediately

The entrypoint script used strict error handling (`set -euo pipefail`) which caused the entire script to exit if the background worker process encountered any issue during startup. This created zombie processes because:

1. Worker starts with `nohup ... &`
2. If worker encounters any error (even minor), `set -euo pipefail` kills the parent shell
3. Worker becomes orphaned zombie process
4. No log file created because worker died before initialization
5. Job queue never processed

**Secondary Issue**: Inadequate process monitoring

The script didn't verify the worker was actually running after startup, making it difficult to detect failures.

## Solution Implemented

### Changes to `docker/unstructured/entrypoint.sh`

**Before**:
```bash
#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/opt/ingestion:${PYTHONPATH:-}"

JOBS_DIR="${UNSTRUCTURED_JOBS_DIR:-/Transfer_Station/jobs/unstructured}"
LOG_DIR="${UNSTRUCTURED_LOG_DIR:-/Transfer_Station/Logs/unstructured}"

mkdir -p "${JOBS_DIR}" "${LOG_DIR}"

# Start async job worker in background
echo "Starting unstructured_job_worker.py..."
nohup python3 /opt/ingestion/unstructured_job_worker.py \
  --jobs-dir "${JOBS_DIR}" \
  --log-dir "${LOG_DIR}" \
  --poll-interval 5 \
  >> "${LOG_DIR}/worker.log" 2>&1 &

WORKER_PID=$!
echo "Started unstructured_job_worker.py (PID: ${WORKER_PID})"

# Give worker a moment to initialize
sleep 2
```

**After**:
```bash
#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="/opt/ingestion:${PYTHONPATH:-}"

JOBS_DIR="${UNSTRUCTURED_JOBS_DIR:-/Transfer_Station/jobs/unstructured}"
LOG_DIR="${UNSTRUCTURED_LOG_DIR:-/Transfer_Station/Logs/unstructured}"

mkdir -p "${JOBS_DIR}" "${LOG_DIR}"

# Start async job worker in background
# Disable error exit for worker startup to prevent zombie processes
echo "Starting unstructured_job_worker.py..."
set +e
(
  python3 /opt/ingestion/unstructured_job_worker.py \
    --jobs-dir "${JOBS_DIR}" \
    --log-dir "${LOG_DIR}" \
    --poll-interval 5 \
    >> "${LOG_DIR}/worker.log" 2>&1
) &
WORKER_PID=$!
set -e

echo "Started unstructured_job_worker.py (PID: ${WORKER_PID})"

# Give worker a moment to initialize and verify it's running
sleep 2
if kill -0 "${WORKER_PID}" 2>/dev/null; then
  echo "Worker process verified running (PID: ${WORKER_PID})"
else
  echo "WARNING: Worker process may have died (PID: ${WORKER_PID})"
fi
```

### Key Improvements

1. **Isolated Error Handling**:
   - `set +e` before worker startup
   - Worker runs in subshell `( ... ) &`
   - `set -e` re-enabled after worker starts
   - Worker failures no longer crash parent script

2. **Process Verification**:
   - Added `kill -0` check to verify worker is alive
   - Logs warning if worker dies
   - Helps identify startup issues

3. **Graceful Degradation**:
   - API server starts even if worker has issues
   - Worker can be manually restarted without container restart

## Verification Results

### Worker Process Status ✅
```bash
$ docker exec ttrpg_unstructured ps aux | grep python
PID   USER     TIME  COMMAND
    1 notebook  0:12 {uvicorn} /usr/bin/python3.12 /home/notebook-user/.local/bin/uvicorn prepline_general.api.app:app --host 0.0.0.0 --port 8000 --log-level info
    8 notebook  0:00 python3 /opt/ingestion/unstructured_job_worker.py --jobs-dir /Transfer_Station/jobs/unstructured --log-dir /Transfer_Station/Logs/unstructured --poll-interval 5
```

**Result**: Worker showing as actual process (not `[python3]` zombie) ✅

### Worker Log File ✅
```bash
$ cat /Transfer_Station/Logs/unstructured/worker.log
2025-10-23 22:59:19,667 [INFO] unstructured_worker - Worker starting (jobs_root=/Transfer_Station/jobs/unstructured, poll_interval=5s)
```

**Result**: Log file created successfully ✅

### Job Processing ✅
Test job `ultimate_magic_2nd_printing_6aecba757f03_ee66c632` completed successfully:
- ✅ pass_a: 2312.8s (6142 elements)
- ✅ pass_a_metadata: 0.67s
- ✅ pass_b_splitter: 0.51s (258 pages)
- ✅ pass_b_chunker: 2.09s (1 chunk)
- ✅ pass_c_parsing: 2370.52s (6142 elements)
- ✅ pass_c_metadata: 0.73s

**Total Processing Time**: ~78 minutes
**Result**: Job completed successfully ✅

## Impact Analysis

### Fixed Issues
✅ **No More Zombie Processes**: Worker runs as proper background process
✅ **Reliable Job Processing**: Worker picks up and processes queued jobs
✅ **Proper Logging**: Worker.log created and maintained
✅ **Error Visibility**: Warning logged if worker dies during startup
✅ **Service Resilience**: API server runs even if worker has issues

### Deployment Steps

1. **Update entrypoint script**: Modified `docker/unstructured/entrypoint.sh`
2. **Rebuild container**: `docker compose -f docker-compose-ttrpg.yml build unstructured`
3. **Restart container**: `docker compose -f docker-compose-ttrpg.yml restart unstructured`
4. **Verify worker**: Check process status and log file

### Files Modified

| File | Changes | Purpose |
|------|---------|---------|
| `docker/unstructured/entrypoint.sh` | Lines 11-33 | Added `set +e` wrapper and process verification |

## Testing Recommendations

### Test 1: Worker Startup Verification
```bash
# Check worker is running
docker exec ttrpg_unstructured ps aux | grep worker

# Expected: Shows python3 worker process (not [python3])
```

### Test 2: Log File Creation
```bash
# Check log file exists and has content
cat E:/n8n_TTRPG_Transfer_Station/Logs/unstructured/worker.log

# Expected: Shows "Worker starting" message
```

### Test 3: Job Processing
```bash
# Submit a test job via ingestion pipeline
docker exec ttrpg_ingestion_engine python3 /app/scripts/ingestion_wrapper.py \
  --sources-dir /Transfer_Station/sources

# Monitor worker log
tail -f E:/n8n_TTRPG_Transfer_Station/Logs/unstructured/worker.log

# Expected: See job claim and processing messages
```

### Test 4: Container Restart Resilience
```bash
# Restart container
docker compose -f docker-compose-ttrpg.yml restart unstructured

# Verify worker auto-starts
docker exec ttrpg_unstructured ps aux | grep worker

# Expected: Worker running with new PID
```

## Best Practices for Future

### Background Process Management
When running background processes in Docker entrypoints:

1. **Isolate Error Handling**:
   ```bash
   set +e
   ( background_process ) &
   set -e
   ```

2. **Verify Process Started**:
   ```bash
   PID=$!
   sleep 2
   if kill -0 "${PID}" 2>/dev/null; then
     echo "Process verified running"
   fi
   ```

3. **Use Subshells for Background Jobs**:
   ```bash
   ( command >> log.txt 2>&1 ) &
   ```

4. **Provide Initialization Time**:
   ```bash
   sleep 2  # Give process time to initialize
   ```

### Debugging Zombie Processes
If encountering zombie processes:

1. Check parent process error handling (`set -euo pipefail`)
2. Test background command manually in foreground
3. Verify log file paths and permissions
4. Check for `nohup` vs subshell `( ... ) &` patterns
5. Monitor parent process for early exit

## Related Documentation

- **Async Deployment**: `docs/ASYNC_UNSTRUCTURED_DEPLOYMENT.md`
- **Cleanup Fix**: `docs/INGESTION_CLEANUP_FIX.md`
- **Database Fix**: `docs/DATABASE_CONNECTION_FIX.md`

## Conclusion

✅ **Worker Zombie Process Fixed**: Background worker runs reliably
✅ **Job Processing Restored**: Queue processing working correctly
✅ **Error Handling Improved**: Graceful degradation on worker issues
✅ **Production Ready**: Worker auto-starts on container restart

The async unstructured worker is now fully operational and processing jobs as designed.

---
**Fixed By**: Isolated error handling for background worker process
**Deployed**: 2025-10-23
**Status**: Production Ready ✅
