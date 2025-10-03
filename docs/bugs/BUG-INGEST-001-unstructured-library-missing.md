# BUG-INGEST-001: Unstructured Library Dependency Missing (libGL.so.1)

**Status:** Critical
**Priority:** P0 - Blocks all ingestion
**Component:** Ingestion Pipeline / Pass A
**Environment:** DEV
**Discovered:** 2025-10-02
**Discovered By:** Automated QA Validation

## Summary
Selective ingestion fails immediately on job start with error: "unstructured library not available". Root cause is missing system library `libGL.so.1` required by OpenCV (cv2), which is a dependency of `unstructured-inference`.

## Impact
- **Severity:** Critical - Complete pipeline failure
- **Scope:** All ingestion operations (Pass A→G)
- **User Impact:** 100% - No documents can be ingested
- **Datastore Impact:** No updates possible to Cassandra/Mongo/Neo4J

## Reproduction Steps
1. Navigate to Admin UI at `http://localhost:3000`
2. Trigger selective ingestion via API:
   ```bash
   curl -X POST "http://localhost:8000/api/admin/ingestion/selective" \
     -H "Content-Type: application/json" \
     -d '{"env": "dev", "selected_sources": ["Cyberpunk v3 - CP4110 Core Rulebook.pdf"], "options": {}}'
   ```
3. **Expected:** Job starts and progresses through Pass A
4. **Actual:** Job fails immediately with "unstructured library not available"

## Error Details

### Primary Error
```
Error in Lane A pipeline for job selective_1759439438_dev: unstructured library not available
Ingestion pipeline failed for selective_1759439438_dev
```

### Root Cause Stack Trace
```python
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
  at cv2/__init__.py:153 in bootstrap
  at unstructured_inference/models/detectron2onnx.py:4
  at unstructured_inference/models/base.py:8
  at unstructured/partition/pdf.py:19
```

### Dependency Chain
```
unstructured.partition.pdf
  └→ unstructured_inference.inference.layout
      └→ unstructured_inference.models.base
          └→ unstructured_inference.models.detectron2onnx
              └→ cv2 (OpenCV)
                  └→ libGL.so.1 [MISSING]
```

## Investigation Details

### Container Check
```bash
# Unstructured module exists but cannot load partition.pdf
docker exec ttrpg-admin-api-dev python -c "import unstructured"  # ✓ Success
docker exec ttrpg-admin-api-dev python -c "from unstructured.partition.pdf import partition_pdf"  # ✗ Fails
```

### Missing System Library
- **Library:** `libGL.so.1` (OpenGL library)
- **Required By:** OpenCV (cv2) → unstructured-inference → unstructured
- **Container:** ttrpg-admin-api-dev
- **Base Image:** Likely missing GL libraries for headless operation

## Affected Operations
- ✗ Pass A: PDF parsing and ToC extraction
- ✗ Pass B: Logical splitting (depends on Pass A)
- ✗ Pass C: Content extraction (depends on Pass A/B)
- ✗ Pass D: Vector enrichment (depends on Pass C)
- ✗ Pass E: Graph building (depends on Pass D)
- ✗ Pass F: Finalization (depends on Pass E)
- ✗ Pass G: HGRN validation (depends on Pass F)

## Recommended Fix

### Option 1: Install System Dependencies (Preferred)
Add to `Dockerfile.microservice` or admin API Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*
```

### Option 2: Use Headless OpenCV
```dockerfile
RUN pip install opencv-python-headless
```

### Option 3: Alternative PDF Parser
Consider using PyPDF2/PyMuPDF for Pass A if unstructured issues persist:
```python
# Fallback parser without ML dependencies
from pypdf import PdfReader
```

## Test Evidence
**Job ID:** `selective_1759439438_dev`
**Timestamp:** 2025-10-02 21:10:38
**Log Source:** `docker logs ttrpg-admin-api-dev --since 10m`

## Verification Steps
After fix is applied:
1. Rebuild admin-api container with system dependencies
2. Restart DEV environment
3. Trigger selective ingestion for test PDF
4. Verify Pass A completes successfully
5. Confirm Pass A artifacts created in `artifacts/ingest/dev/{job_id}/`

## Related Issues
- **BUG-INGEST-002**: Job status endpoint not found (prevents monitoring)
- **BUG-INGEST-003**: Observability gap - no clear error messages in Admin UI

## References
- OpenCV headless docs: https://pypi.org/project/opencv-python-headless/
- Unstructured docs: https://unstructured-io.github.io/unstructured/
- Container logs: `docker logs ttrpg-admin-api-dev --since 15m`
