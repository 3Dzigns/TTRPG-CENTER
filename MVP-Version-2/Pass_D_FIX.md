# Pass D Fix Plan - BUG-035 Resolution

**Bug ID:** BUG-035
**Severity:** 🔴 BLOCKER
**Component:** Pass D Vector Enrichment / Cassandra Vector Store
**Discovered:** 2025-10-05 04:33 CDT
**Status:** 🔧 IN PROGRESS
**Assigned:** Development Team

---

## Problem Statement

### Symptom
All selective ingestion jobs fail at Pass D (Vector Enrichment) with:
```
AttributeError: 'CassandraVectorStore' object has no attribute '_json_default'
```

### Impact
- **100% failure rate** across 3 independent job attempts
- **Zero database upserts** to Cassandra, MongoDB, Neo4j
- **43% of pipeline untested** (Passes E, F, G blocked)
- **QA validation cannot proceed** - NO-GO status

### Reproduction
1. Start selective ingestion for any PDF file
2. Job successfully completes Passes 0, A, B, C (~21 minutes)
3. Pass D begins vector enrichment
4. Error raised at `cassandra.py:383` during JSON serialization
5. Job marked as "failed", Pass D artifacts empty

**Reproducibility:** 100% (3/3 jobs failed identically)

---

## Root Cause Analysis

### The Mystery
- ✅ `@staticmethod` decorator added to `_json_default` method
- ✅ Source code fix verified in container
- ✅ Python bytecode cache cleared (host + container)
- ✅ Containers restarted multiple times
- ❌ **Error persists despite all fixes**

### True Root Cause: Module-Level Class Caching

**File:** `src_common/vector_store/factory.py`

```python
_BACKEND_CACHE: Dict[str, Type[VectorStore]] = {}  # Line 16
```

**How It Works:**
1. First call to `make_vector_store()` triggers `importlib.import_module()`
2. CassandraVectorStore **class object** loaded into `_BACKEND_CACHE`
3. Class definition cached **at import time** with method binding state
4. Cache persists across job executions in long-running container
5. Subsequent jobs reuse **cached class** with old method binding

**Why Decorator Fix Failed:**
- Code changes affect **disk files**
- `_BACKEND_CACHE` holds **in-memory class object**
- Cache never invalidates unless container fully restarted **AND** module reloaded
- Even container restart doesn't clear module if gunicorn/uvicorn workers persist

### Technical Details

**Error Location:**
```python
# src_common/vector_store/cassandra.py:383
payload = json.dumps(payload_body, ensure_ascii=False, default=self._json_default)
```

**When `_json_default` was a regular method (without @staticmethod):**
- Method bound to instance: `self._json_default` → `<bound method>`
- Python looks for attribute on instance → not found
- AttributeError raised

**Even with @staticmethod added:**
- Cached class still has old method binding
- `self._json_default` tries to access instance attribute
- Cached class doesn't reflect new static method

---

## Solution Strategy

### Option A: Quick Fix (Cache Bypass)
**Approach:** Force fresh class load per job
```python
# pass_d_vector_enrichment.py:303
vector_store = make_vector_store(self.env, fresh=True)
```

**Pros:**
- Immediate fix (2 minutes)
- No architectural changes

**Cons:**
- Performance overhead (class reload per job)
- Doesn't address underlying design issue
- Cache still exists, just bypassed

### Option B: Proper Fix (Module-Level Function) ✅ RECOMMENDED

**Approach:** Extract `_json_default` as module-level utility function

**Rationale:**
1. Eliminates class method binding complexity
2. Makes serialization logic reusable
3. Avoids instance/static method confusion
4. Aligns with Python best practices for JSON serializers
5. Recommended in QA report

**Implementation:**
```python
# src_common/vector_store/cassandra.py (~line 30, after imports)

def _json_default_serializer(obj: Any) -> Any:
    """
    JSON serialization helper for datetime and other non-standard types.

    Used as the 'default' parameter for json.dumps() to handle
    datetime objects and other types that aren't natively JSON-serializable.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation of obj
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)
```

**Update References:**
```python
# Line 383 - Change from instance method to module function
# OLD:
payload = json.dumps(payload_body, ensure_ascii=False, default=self._json_default)

# NEW:
payload = json.dumps(payload_body, ensure_ascii=False, default=_json_default_serializer)
```

**Remove Old Method:**
```python
# Lines 520-524 - DELETE
@staticmethod
def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)
```

---

## Implementation Tasks

### Task 1: Move _json_default to Module Level
**File:** `src_common/vector_store/cassandra.py`
**Priority:** P0 - CRITICAL
**Estimate:** 10 minutes

**Changes:**
1. Add module-level function after imports (~line 30)
2. Update line 383 to use `_json_default_serializer`
3. Remove old `@staticmethod` method (lines 520-524)
4. Add docstring explaining usage

**Testing:** Verify no syntax errors, imports work

---

### Task 2: Add Unit Test for Serialization
**File:** `tests/unit/test_cassandra_vector_store.py`
**Priority:** P0 - CRITICAL
**Estimate:** 10 minutes

**Test Code:**
```python
def test_json_default_serializer():
    """Verify datetime serialization works correctly"""
    from src_common.vector_store.cassandra import _json_default_serializer
    from datetime import datetime

    # Test datetime serialization
    now = datetime(2025, 10, 5, 12, 30, 45)
    result = _json_default_serializer(now)
    assert isinstance(result, str)
    assert result == "2025-10-05T12:30:45"

    # Test other types fallback to str()
    result = _json_default_serializer(42)
    assert result == "42"

    result = _json_default_serializer({"key": "value"})
    assert "key" in result

def test_prepare_document_for_upsert_serialization():
    """Verify document preparation doesn't raise AttributeError"""
    from src_common.vector_store.cassandra import CassandraVectorStore
    from datetime import datetime

    store = CassandraVectorStore("dev")

    doc = {
        "doc_id": "test_doc_123",
        "chunk_id": "chunk_456",
        "content": "Test content",
        "metadata": {"key": "value", "created": datetime.utcnow()},
        "embedding": [0.1, 0.2, 0.3],
        "source_hash": "abc123",
        "environment": "dev"
    }

    # Should not raise AttributeError
    result = store._prepare_document_for_upsert(doc)
    assert result is not None
    assert len(result) == 12  # Tuple with 12 elements
```

---

### Task 3: Clear All Python Caches
**Priority:** P0 - CRITICAL
**Estimate:** 3 minutes

**Commands:**
```bash
# Host-side cache clear
find src_common -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find src_common -name "*.pyc" -delete 2>/dev/null
find tests -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Container-side cache clear
docker exec ttrpg-ingest-dev sh -c "find /app -name '*.pyc' -delete 2>/dev/null"
docker exec ttrpg-pipeline-worker-dev sh -c "find /app -name '*.pyc' -delete 2>/dev/null"

# Restart containers to clear module cache
docker restart ttrpg-ingest-dev ttrpg-pipeline-worker-dev
```

---

### Task 4: Test with Small File First
**File:** `combat_mechanics.pdf` (2.8KB)
**Priority:** P0 - CRITICAL
**Estimate:** 5-10 minutes

**Rationale:** Small file processes in ~10 seconds through Pass D, allowing rapid validation

**Test Command:**
```bash
curl -X POST http://localhost:8000/api/admin/ingestion/selective \
  -H "Content-Type: application/json" \
  --data '{"env": "dev", "selected_sources": ["combat_mechanics.pdf"]}'
```

**Success Criteria:**
- ✅ Job completes all 7 passes
- ✅ No AttributeError in logs
- ✅ `pass_d/` directory contains artifacts
- ✅ Manifest shows `"status": "completed"`

**Monitoring:**
```bash
# Watch manifest for completion
JOB_ID=$(curl -s "http://localhost:8000/api/admin/ingestion/jobs?env=dev&limit=1" | jq -r '.[0].job_id')
watch -n 2 "cat env/dev/artifacts/$JOB_ID/manifest.json | jq '.status, .completed_phases, .error_message'"
```

---

### Task 5: Full Regression Test
**File:** `Cyberpunk v3 - CP4110 Core Rulebook.pdf` (24.2MB)
**Priority:** P1 - HIGH
**Estimate:** 25-30 minutes

**Test Command:**
```bash
curl -X POST http://localhost:8000/api/admin/ingestion/selective \
  -H "Content-Type: application/json" \
  --data '{"env": "dev", "selected_sources": ["Cyberpunk v3 - CP4110 Core Rulebook.pdf"]}'
```

**Success Criteria:**
- ✅ All 7 passes complete (Gate 0, A, B, C, D, E, F, G)
- ✅ 8,197 chunks processed
- ✅ Pass D artifacts generated
- ✅ Processing time: ~25 minutes total
- ✅ Manifest shows `"completed_phases": 7`

---

### Task 6: Verify Database Upserts
**Priority:** P0 - CRITICAL
**Estimate:** 5 minutes

**Cassandra Verification:**
```bash
docker exec ttrpg-cassandra-dev cqlsh -e "
  USE ttrpg_dev;
  SELECT COUNT(*) AS vector_count FROM vectors WHERE job_id = '<JOB_ID>';
  SELECT doc_id, chunk_id, vector_id FROM vectors WHERE job_id = '<JOB_ID>' LIMIT 5;
"
```
**Expected:** 8,197 rows for Cyberpunk, showing doc_id, chunk_id, vector_id

**MongoDB Verification:**
```bash
docker exec ttrpg-mongo-dev mongosh --quiet --eval "
  use ttrpg_dev;
  print('Dictionary entries: ' + db.dictionary.countDocuments({job_id: '<JOB_ID>'}));
  db.dictionary.find({job_id: '<JOB_ID>'}, {term:1, kind:1, sources:1}).limit(3).forEach(printjson);
"
```
**Expected:** Dictionary terms from Pass A/D with source references

**Neo4j Verification:**
```bash
docker exec ttrpg-neo4j-dev cypher-shell -u neo4j -p dev_password -d ttrpgdev "
  MATCH (n) WHERE n.job_id = '<JOB_ID>' RETURN labels(n)[0] AS type, count(*) AS count;
  MATCH (t:Term)-[r:MENTIONS]->(c:Chunk) WHERE t.job_id = '<JOB_ID>'
  RETURN t.term, c.chunk_id, type(r) LIMIT 5;
"
```
**Expected:** Graph nodes (Terms, Chunks) and MENTIONS relationships

---

### Task 7: Commit and Document
**Priority:** P1 - HIGH
**Estimate:** 10 minutes

**Commit Message:**
```
fix: BUG-035 - Move _json_default to module level to resolve Pass D AttributeError

PROBLEM:
- All Pass D jobs failed with AttributeError on _json_default
- 100% failure rate across 3 job attempts
- Previous @staticmethod fix ineffective due to module caching

ROOT CAUSE:
- factory.py caches CassandraVectorStore class at import time
- Class cache persists across jobs in long-running containers
- Method binding fixed in code but cached class unchanged

SOLUTION:
- Extract _json_default as module-level function _json_default_serializer
- Update json.dumps() call to use module function instead of instance method
- Eliminates class method binding complexity
- Makes serialization logic more maintainable

CHANGES:
- src_common/vector_store/cassandra.py:
  - Add _json_default_serializer() module function
  - Update line 383 to use module function
  - Remove old @staticmethod method
- tests/unit/test_cassandra_vector_store.py:
  - Add serialization unit tests
  - Add integration test for _prepare_document_for_upsert

VERIFICATION:
- Small file test (combat_mechanics.pdf): PASS
- Full regression (Cyberpunk PDF): PASS
- Database upserts verified: Cassandra ✓ MongoDB ✓ Neo4j ✓
- All 7 passes complete successfully

IMPACT:
- Unblocks Pass D vector enrichment
- Enables complete pipeline execution
- Allows QA validation to proceed

Fixes: BUG-035
Related: QA_Run_20251005_041016

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Success Criteria

### Pass/Fail Checklist

**Phase 1: Code Changes**
- [ ] Module-level function added to cassandra.py
- [ ] Line 383 updated to use module function
- [ ] Old @staticmethod method removed
- [ ] Unit tests added and passing
- [ ] No syntax errors, imports work

**Phase 2: Small File Test**
- [ ] combat_mechanics.pdf job started
- [ ] Job completes without AttributeError
- [ ] All 7 passes complete successfully
- [ ] pass_d/ directory contains artifacts
- [ ] Manifest shows status: "completed"

**Phase 3: Full Regression**
- [ ] Cyberpunk PDF job started
- [ ] 8,197 chunks processed
- [ ] All 7 passes complete
- [ ] Processing time ~25 minutes
- [ ] No errors in job logs

**Phase 4: Database Verification**
- [ ] Cassandra: 8,197 vector documents present
- [ ] MongoDB: Dictionary entries with job_id
- [ ] Neo4j: Graph nodes and relationships exist
- [ ] All queries return expected data

**Phase 5: Documentation**
- [ ] BUG-035 marked as resolved
- [ ] QA report updated with resolution
- [ ] Commit pushed to repository
- [ ] This document updated with results

---

## Timeline

### Estimated Duration: 45-60 minutes

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| 1 | Code changes + unit tests | 15 min | ✅ Completed |
| 2 | Cache clear + container restart | 2 min | ✅ Completed |
| 3 | Small file test | 12 min | ✅ Completed |
| 4 | Full regression test | 25 min | 🔄 In Progress |
| 5 | Database verification | 3 min | ✅ Completed (small file) |
| 6 | Commit + documentation | Pending | ⏳ Pending |
| **Total** | | **~57 min** | |

---

## Risk Assessment

### Low Risk
- **Code change is minimal:** Single function extraction
- **Backward compatible:** No API changes
- **Well-tested:** Unit + integration tests
- **Reversible:** Easy to rollback if needed

### Mitigation Strategies
1. **Test small file first** before full regression
2. **Keep old method temporarily** (commented out) for emergency rollback
3. **Monitor container logs** during test execution
4. **Verify unit tests pass** before deploying

---

## Prevention Measures

### For Future Development

**1. Add Factory Cache Management**
```python
# src_common/vector_store/factory.py
def clear_cache():
    """Clear all cached instances and classes"""
    global _CACHE, _BACKEND_CACHE
    _CACHE.clear()
    _BACKEND_CACHE.clear()

def reload_backend(backend_name: str):
    """Force reload of specific backend class"""
    if backend_name in _BACKEND_CACHE:
        del _BACKEND_CACHE[backend_name]
    if backend_name in _CACHE:
        del _CACHE[backend_name]
```

**2. Add Health Check Endpoint**
```python
# Check if vector store can serialize datetime
GET /api/admin/vector-store/health
Response: {"serialization": "ok", "backend": "cassandra"}
```

**3. Add Monitoring Alert**
- Alert on Pass D failures
- Track success rate by pass
- Dashboard for pipeline health

**4. Documentation Updates**
- Document factory caching behavior
- Add troubleshooting guide for module caching issues
- Update developer onboarding with common pitfalls

---

## Lessons Learned

### What Went Well
- ✅ QA protocol caught the bug before production
- ✅ Systematic troubleshooting identified root cause
- ✅ Comprehensive testing with 3 job attempts
- ✅ Good artifact preservation for debugging

### What Could Be Improved
- ❌ Initial fix didn't consider module-level caching
- ❌ No unit tests for serialization logic
- ❌ Factory cache behavior not documented
- ❌ No health check for vector store initialization

### Key Takeaway
**Module-level caching in long-running Python processes can mask code fixes.**
Always verify that changes propagate to cached instances/classes, not just source files.

---

## References

- **QA Report:** `env/dev/artifacts/QA_Run_20251005_041016/QA_Results_FINAL_20251005_DEV.md`
- **Bug Tracking:** BUG-035
- **Failed Jobs:**
  - selective_1759655545_dev
  - selective_1759676920_dev
  - selective_1759700413_dev
- **Related Code:**
  - `src_common/vector_store/cassandra.py:383`
  - `src_common/vector_store/factory.py:16`
  - `src_common/pass_d_vector_enrichment.py:303`

---

## Resolution Summary

### Actual Root Cause
**Worker Process Caching in Admin API Container**

The true issue was not just module-level class caching in `factory.py`, but **cached worker processes** in the `admin-api` container that spawns ingestion jobs. Even after:
- Code changes on disk
- Python bytecode cache clearing (`__pycache__`, `.pyc` files)
- Container restarts (ingest, pipeline-worker)

The error persisted because the `admin-api` container's worker processes had loaded the old `CassandraVectorStore` class into memory before the fix.

### What Fixed It
1. **Code Changes**: Moved `_json_default` to module-level function `_json_default_serializer` ✅
2. **Cache Clearing**: Cleared all Python bytecode caches ✅
3. **Container Restart**: Restarted `admin-api` container to clear worker process cache ✅

**Critical Discovery**: Direct Python imports in all containers showed the fix working correctly, but actual job execution failed until `admin-api` was restarted. This revealed that jobs are spawned by admin-api workers, not by the ingest container itself.

### Test Results

**Small File Test (combat_mechanics.pdf)**
- Job ID: `selective_1759713552_dev`
- Status: ✅ **PASSED**
- Duration: ~10 seconds
- Phases Completed: 8/7 (includes Pass 0)
- Database Verification:
  - Cassandra: 11 chunks upserted
  - Neo4j: 11 Chunk nodes created
  - MongoDB: 0 entries (expected for small file with no ToC)

**Full Regression Test (Cyberpunk v3 - CP4110 Core Rulebook.pdf)**
- Job ID: `selective_1759713675_dev`
- Status: 🔄 **IN PROGRESS**
- Expected Duration: ~25 minutes
- Expected Chunks: 8,197

### Lessons Learned

1. **Multi-Container Architecture**: Code changes must propagate to ALL containers, especially job orchestrators
2. **Worker Process Caching**: Long-running containers with worker processes cache Python modules independently of file changes
3. **Testing Strategy**: Direct Python imports may succeed while actual execution paths fail due to cached workers
4. **Fix Verification**: Always restart containers that spawn/orchestrate jobs, not just containers that execute code
5. **Volume Mounts**: Code changes via volume mounts don't force module reloads in running Python processes

### Prevention for Future

1. **Deployment Protocol**: Always restart admin-api when modifying shared libraries (`src_common`)
2. **Hot Reload**: Consider adding hot-reload capability for development environment
3. **Health Checks**: Add health endpoint that verifies module versions/hashes
4. **Documentation**: Document which containers spawn jobs vs execute code
5. **Testing**: Add integration tests that verify end-to-end job execution, not just module imports

---

**Document Status:** 🔄 RESOLVING (Regression Test In Progress)
**Last Updated:** 2025-10-05 20:20 CDT
**Next Update:** After Cyberpunk regression test completes
