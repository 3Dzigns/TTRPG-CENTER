# BUG-INGEST-002: Job Status Endpoint Returns 404

**Status:** Critical
**Priority:** P0 - Blocks observability
**Component:** Admin API / Ingestion Console
**Environment:** DEV
**Discovered:** 2025-10-02
**Discovered By:** Automated QA Validation

## Summary
The job status monitoring endpoint `/api/admin/ingestion/jobs/{job_id}/status` returns 404 Not Found, preventing real-time job monitoring and progress tracking through the Admin UI.

## Impact
- **Severity:** Critical - No job observability
- **Scope:** All ingestion job monitoring
- **User Impact:** Cannot track job progress, status, or phase completion
- **Observability Impact:** Blind execution - no visibility into pipeline execution

## Reproduction Steps
1. Start a selective ingestion job:
   ```bash
   curl -X POST "http://localhost:8000/api/admin/ingestion/selective" \
     -H "Content-Type: application/json" \
     -d '{"env": "dev", "selected_sources": ["Cyberpunk v3 - CP4110 Core Rulebook.pdf"]}'
   ```
   Response: `{"job_id": "selective_1759439438_dev", "status": "started", ...}`

2. Attempt to monitor job status:
   ```bash
   curl "http://localhost:8000/api/admin/ingestion/jobs/selective_1759439438_dev/status"
   ```

3. **Expected:** Job status with current phase, progress, etc.
4. **Actual:** `404 Not Found`

## Error Details

### HTTP Response
```
GET /api/admin/ingestion/jobs/selective_1759439438_dev/status HTTP/1.1
404 Not Found
```

### Container Logs (120 attempts over 6 minutes)
```
INFO: 172.18.0.1:60070 - "GET /api/admin/ingestion/jobs/selective_1759439438_dev/status HTTP/1.1" 404 Not Found
INFO: 172.18.0.1:60084 - "GET /api/admin/ingestion/jobs/selective_1759439438_dev/status HTTP/1.1" 404 Not Found
[... 118 more identical 404 responses ...]
```

## Investigation Details

### Correct Endpoint Found
The actual working endpoint is:
```
GET /api/admin/logs/status?job_id={job_id}&env={env}
```

**Source:** `src_common/admin_routes.py:2560-2570`

### Route Definition
```python
@admin_router.get("/api/admin/logs/status")
async def get_log_job_status(
    job_id: str = Query(...),
    env: str = Query(...)
):
    """Get status of a specific job"""
    return await log_service.get_job_status(job_id, env)
```

### Endpoint Mismatch
- **Expected (by monitoring script):** `/api/admin/ingestion/jobs/{job_id}/status`
- **Actual (implemented):** `/api/admin/logs/status?job_id={job_id}&env={env}`

## Affected Operations
- ✗ Real-time job progress monitoring
- ✗ Phase transition tracking
- ✗ Job completion detection
- ✗ Error state identification
- ✗ Admin UI live updates

## Root Cause Analysis
1. **API Design Inconsistency:** Status endpoint uses different URL pattern than job creation
   - Job creation: `/api/admin/ingestion/selective`
   - Job status: `/api/admin/logs/status` (different namespace)

2. **Missing RESTful Convention:** Should be `/api/admin/ingestion/jobs/{job_id}` or `/api/admin/ingestion/jobs/{job_id}/status`

3. **Documentation Gap:** No API specification documenting correct endpoint structure

## Recommended Fix

### Option 1: Add Missing Endpoint (Preferred)
Add to `src_common/admin_routes.py`:
```python
@admin_router.get("/api/admin/ingestion/jobs/{job_id}/status")
async def get_ingestion_job_status(job_id: str, env: str = Query("dev")):
    """Get status of a specific ingestion job - RESTful endpoint"""
    return await ingestion_service.get_job_status(job_id, env)
```

### Option 2: Update Documentation
If current endpoint is intentional, update:
- API documentation
- Admin UI client code
- Monitoring scripts
- OpenAPI/Swagger specs

### Option 3: Add Route Alias
Create alias for backward compatibility:
```python
# Alias for RESTful access pattern
@admin_router.get("/api/admin/ingestion/jobs/{job_id}/status")
async def get_job_status_restful(job_id: str, env: str = Query("dev")):
    """RESTful alias for job status endpoint"""
    return await get_log_job_status(job_id=job_id, env=env)
```

## Test Evidence
**Test Run:** 120 polling attempts over 360 seconds (6 minutes)
**Success Rate:** 0% (120/120 failures)
**Job ID:** `selective_1759439438_dev`
**Timestamp:** 2025-10-02 21:10:38 - 21:16:38

## Verification Steps
After fix is applied:
1. Start test ingestion job
2. Query status via new endpoint: `GET /api/admin/ingestion/jobs/{job_id}/status`
3. Verify response contains: `job_id`, `status`, `current_phase`, `progress_percent`
4. Confirm Admin UI updates reflect job progress
5. Test with multiple concurrent jobs

## Observability Impact
**Admin UI Behavior:**
- Cannot display real-time progress bars
- Cannot show current phase indicators
- Cannot update job status dynamically
- Cannot detect job completion automatically
- Users must manually refresh or check logs

## Related Issues
- **BUG-INGEST-001**: Unstructured library missing (prevents job execution)
- **BUG-INGEST-003**: Missing streaming log endpoints for real-time monitoring
- **FR-034**: Observability Dashboard enhancement requirements

## API Specification Recommendations
Document expected endpoints:
```
POST   /api/admin/ingestion/selective              # Start job
GET    /api/admin/ingestion/jobs/{job_id}          # Get job details
GET    /api/admin/ingestion/jobs/{job_id}/status   # Get job status
GET    /api/admin/ingestion/jobs/{job_id}/logs     # Get job logs
DELETE /api/admin/ingestion/jobs/{job_id}          # Cancel job
```

## References
- Current endpoint: `src_common/admin_routes.py:2560`
- Job creation: `src_common/admin_routes.py:1993`
- Container logs: `docker logs ttrpg-admin-api-dev --since 15m`
