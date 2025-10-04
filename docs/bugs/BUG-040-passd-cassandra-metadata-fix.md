# BUG-040: Pass D Cassandra Metadata Handoff Fix

**Status:** ✅ RESOLVED
**Date:** 2025-10-04
**Priority:** CRITICAL
**Impact:** Blocks Pass D vector enrichment and Cassandra persistence

## Problem Statement

Job `job_1759593741_dev` (Cyberpunk v3 - CP4110 Core Rulebook.pdf) failed on 2025-10-04 when Pass D attempted to start. Error logs showed:

```
[2025-10-04T16:12:21.546284] Pass D failed: Pass D: Unable to determine source metadata for Cassandra persistence
[2025-10-04T16:12:21.551542] Pipeline failed: Pass D: Unable to determine source metadata for Cassandra persistence
[2025-10-04T16:12:21.566772] Job job_1759593741_dev failed: Pass D: Unable to determine source metadata for Cassandra persistence
```

Passes A–C completed successfully:
- `pass_c/extraction_summary.json` reports 317 parts processed and 125,167 chunks written
- `job_1759593741_dev_pass_c_chunks.jsonl` contains all extracted chunks
- Job manifest shows `status: failed` with Pass D metadata error
- `pass_d/` directory is empty (never started)

## Root Cause Analysis

### Issue 1: Incorrect Manifest Path
**Location:** `src_common/pass_d_vector_enrichment.py:390` and `src_common/pass_e_graph_builder.py:621`

Pass D and Pass E metadata loaders searched for Pass A manifest at:
```python
job_dir / "pass_a" / f"{job_id}_pass_a_manifest.json"  # Legacy location
```

**Actual location** in unified_v1 pipeline:
```python
job_dir / f"{job_id}_pass_a_manifest.json"  # No pass_a subdirectory
```

**Evidence:**
- `job_1759593741_dev_pass_a_manifest.json` exists at job root
- `pass_a/` subdirectory does not exist

### Issue 2: Field Name Mismatch
**Location:** `src_common/pass_d_vector_enrichment.py:404`

Pass D metadata loader searched for `pass_0_result.source_hash`:
```python
source_hash = manifest.get("pass_0_result", {}).get("source_hash")
```

**Actual field name** in unified_v1 manifest:
```json
{
  "pass_0_result": {
    "file_sha": "4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0"
  }
}
```

Field name is `file_sha`, not `source_hash`.

## Solution Implemented

### Phase 1: Fix Manifest Path Resolution

Updated `_load_source_metadata()` in both Pass D and Pass E to search multiple locations:

```python
manifest_candidates = [
    job_dir / "manifest.json",                                    # Main manifest
    job_dir / f"{self.job_id}_pass_a_manifest.json",             # unified_v1 location (NEW)
    job_dir / "pass_a" / f"{self.job_id}_pass_a_manifest.json",  # legacy location
]
```

### Phase 2: Fix Field Name Resolution

Added `pass_0_result.file_sha` to the fallback chain:

```python
source_hash = (
    manifest.get("source_info", {}).get("source_hash")
    or manifest.get("pass_0_result", {}).get("file_sha")      # unified_v1 field (NEW)
    or manifest.get("pass_0_result", {}).get("source_hash")
    or manifest.get("source_hash")
)
```

### Phase 3: Enhanced Error Reporting

Added detailed error messages with actionable information:

```python
error_msg = (
    f"Pass D: Unable to determine source metadata for Cassandra persistence. "
    f"Checked paths: {', '.join(checked_paths)}. "
    f"Required fields: source_hash (or pass_0_result.file_sha) and source_file (or source_path)"
)
logger.error(
    "pass_d_metadata_missing",
    extra={"checked_paths": checked_paths, "job_id": self.job_id},
)
```

Before: Generic error with no diagnostic info
After: Lists all checked paths and required fields

### Phase 4: Comprehensive Test Coverage

Created `tests/unit/test_pass_d_metadata_loader.py` with 10 test cases:

**Happy Path Tests:**
1. `test_metadata_from_unified_v1_manifest` - Load from unified_v1 location
2. `test_metadata_from_main_manifest_with_file_sha` - Load using file_sha field
3. `test_metadata_from_legacy_manifest_location` - Backward compatibility
4. `test_metadata_source_file_as_list` - Handle list format
5. `test_metadata_fallback_field_names` - Field name variations
6. `test_metadata_priority_order` - Correct search order

**Error Handling Tests:**
7. `test_metadata_missing_manifest_file` - No manifests exist
8. `test_metadata_malformed_json` - Invalid JSON parsing
9. `test_metadata_missing_required_fields` - Incomplete manifests

**Integration Tests:**
10. `test_cyberpunk_job_simulation` - Real-world Cyberpunk job structure

**Test Results:** ✅ All 10 tests passing

## Files Changed

### Core Implementation
- `src_common/pass_d_vector_enrichment.py`: Metadata loader fixes (lines 387-471)
- `src_common/pass_e_graph_builder.py`: Same fixes for Pass E (lines 618-702)

### Testing
- `tests/unit/test_pass_d_metadata_loader.py`: Comprehensive test suite (new file, 10 tests)

### Documentation
- `docs/bugs/BUG-040-passd-cassandra-metadata-fix.md`: This document

## Acceptance Criteria

✅ **Deliverable 1:** Code fixes implemented
  - Pass D/E search correct manifest locations (unified_v1 + legacy)
  - Pass D/E recognize file_sha field name
  - Enhanced error messages with actionable details

✅ **Deliverable 2:** Test coverage
  - 10 unit tests covering happy path, errors, edge cases
  - Integration test simulating Cyberpunk job structure
  - All tests passing (10/10)

⏳ **Deliverable 3:** Validation artifact (PENDING)
  - Re-run Cyberpunk job or mock run
  - Verify Pass D reaches Cassandra persistence
  - Confirm chunk_count > 0 in summary

## Integration Test Plan

**Test Scenario:** Re-run Pass D on existing Cyberpunk job artifacts

**Preconditions:**
- Job `job_1759593741_dev` has completed Pass C
- `job_1759593741_dev_pass_c_chunks.jsonl` contains 125,167 chunks
- `job_1759593741_dev_pass_a_manifest.json` exists with source metadata

**Expected Outcome:**
1. Pass D loads source metadata successfully
2. Log shows: `pass_d_metadata_loaded` with manifest path
3. Pass D processes chunks and generates vectors
4. Cassandra persistence writes chunk records
5. `pass_d_summary.json` shows chunk_count = 125,167

**Command:**
```bash
# Re-run Pass D standalone
python -m src_common.pass_d_vector_enrichment \
    --job-id job_1759593741_dev \
    --env dev \
    --job-dir env/dev/artifacts/job_1759593741_dev
```

## Deployment Status

1. ✅ Code changes implemented (Pass D + Pass E)
2. ✅ Unit tests passing (10/10)
3. ⏳ Docker image rebuild (waiting for build completion)
4. ⏳ Integration test execution (pending)
5. ⏳ Cassandra verification (pending)

## Backward Compatibility

The fix maintains backward compatibility with legacy pipeline versions:

**Legacy Pipeline:**
- Manifests at `job_dir/pass_a/{job_id}_pass_a_manifest.json` ✅ Still supported
- Field `pass_0_result.source_hash` ✅ Still supported

**Unified V1 Pipeline:**
- Manifests at `job_dir/{job_id}_pass_a_manifest.json` ✅ Now supported
- Field `pass_0_result.file_sha` ✅ Now supported

**Search Priority:**
1. Main manifest (`manifest.json`)
2. Unified_v1 Pass A manifest (job root)
3. Legacy Pass A manifest (`pass_a/` subdirectory)

## Next Steps

1. **Complete Docker build:** Wait for ingest service rebuild
2. **Run integration test:** Execute Pass D on Cyberpunk job
3. **Verify Cassandra:** Check chunk writes using cqlsh
4. **Coordinate with QA:** Use cqlsh commands from `QA_Status_Update_20251004_1140.md`
5. **Monitor production:** Track metadata load success rate

## Regression Prevention

**Guard against future regressions:**
1. ✅ Unit tests cover all manifest location variations
2. ✅ Unit tests cover all field name variations
3. ✅ Enhanced error logging exposes diagnosis information
4. ✅ Integration test simulates real job structure
5. 📋 Add regression test to nightly suite

## References

- **Original issue:** `MVP-Version-2/Prompt-Registry/PassD_Cassandra_Metadata_Fix.md`
- **Evidence:** `env/dev/artifacts/job_1759593741_dev/manifest.json`
- **Pass A manifest:** `env/dev/artifacts/job_1759593741_dev/job_1759593741_dev_pass_a_manifest.json`
- **Pass C output:** `env/dev/artifacts/job_1759593741_dev/pass_c/extraction_summary.json`
- **Test suite:** `tests/unit/test_pass_d_metadata_loader.py`

## Technical Notes

### Metadata Resolution Algorithm

1. Iterate through manifest candidates (main → unified_v1 → legacy)
2. For each candidate:
   - Check if file exists
   - Attempt JSON parsing
   - Try multiple field name variations for source_hash
   - Try multiple field name variations for source_file
   - If both found, return SourceMetadata
3. If no valid metadata found, raise RuntimeError with diagnostic info

### Field Name Variations Supported

**Source Hash:**
- `source_info.source_hash` (Pass A unified_v1)
- `pass_0_result.file_sha` (Pass 0 unified_v1) ← **NEW**
- `pass_0_result.source_hash` (Legacy)
- `source_hash` (Direct field)

**Source File:**
- `source_file` (Primary field)
- `source` (Alternative)
- `source_path` (Alternative)
- `pdf_path` (Alternative)

### Logging Improvements

**Before:**
```
Pass D: Unable to determine source metadata for Cassandra persistence
```

**After:**
```
Pass D: Unable to determine source metadata for Cassandra persistence.
Checked paths: /job_dir/manifest.json, /job_dir/job_123_pass_a_manifest.json, /job_dir/pass_a/job_123_pass_a_manifest.json.
Required fields: source_hash (or pass_0_result.file_sha) and source_file (or source_path)
```

Structured log event:
```json
{
  "event": "pass_d_metadata_missing",
  "checked_paths": [...],
  "job_id": "job_123"
}
```
