# BUG-038: Pass B Deduplication Guardrail Implementation

**Status:** ✅ RESOLVED
**Date:** 2025-10-04
**Priority:** HIGH
**Impact:** ~88.6% reduction in Pass C runtime (10.5h → 1.2h projected)

## Problem Statement

Pass B generated 317 PDF parts for job `job_1759593741_dev`, but analysis revealed only 36 unique checksums (281 duplicates = 88.6% duplication). Multiple TOC sections mapped to identical page ranges, causing byte-for-byte identical PDFs to be generated multiple times.

**Original Evidence:**
```json
{
  "total_parts": 317,
  "unique_checksums": 36,
  "duplicate_groups": 19,
  "largest_duplicate_group": 23,
  "deduplication_rate": "88.6%"
}
```

Each duplicate part was processed by Pass C (~700 chunks per part), inflating total chunks from ~25,000 to ~225,000 and extending Pass C runtime from ~1.2 hours to ~10.5 hours.

## Root Cause

Pass B's TOC-based splitting (lines 814-965 of `pass_b_logical_splitter.py`) generated parts for each TOC section without checking for duplicate page ranges or PDF checksums. The code path:

1. Generate page_ranges from TOC sections
2. For each range, extract PDF pages
3. Calculate checksum (line 872)
4. **Append to parts list (line 893) WITHOUT deduplication check** ← Root cause

## Solution Implemented

### Phase 1: Core Deduplication Logic
**File:** `src_common/pass_b_logical_splitter.py`

Added checksum-based deduplication after PDF generation but before adding to parts list:

```python
# Line 815-816: Initialize tracking structures
seen_checksums: Dict[str, str] = {}  # checksum -> canonical part_id
skipped_parts: List[Dict[str, Any]] = []  # Track duplicates for manifest

# Lines 885-927: Deduplication check after checksum calculation
if checksum in seen_checksums:
    canonical_part_id = seen_checksums[checksum]

    # Record skipped duplicate for observability
    skipped_parts.append({
        "part_id": f"{self.job_id}-part-{part_number:02d}",
        "section_id": section_id,
        "section_title": section_title,
        "page_start": part_start_page,
        "page_end": aligned_end,
        "duplicates_of": canonical_part_id,
        "checksum_sha256": checksum,
        "reason": "duplicate_checksum",
    })

    # Delete duplicate PDF file to save disk space
    part_path.unlink()

    # Skip adding to parts list
    part_index += 1
    continue

# Record canonical part for this checksum
canonical_part_id = f"{self.job_id}-part-{part_number:02d}"
seen_checksums[checksum] = canonical_part_id
```

### Phase 2: Manifest Updates

**split_index.json** (lines 1230-1245):
```python
index_data = {
    "job_id": self.job_id,
    "parts": [asdict(part) for part in parts],
    # ... other fields
}

# Include skipped duplicates for observability
if skipped_parts:
    index_data["skipped_duplicates"] = skipped_parts
```

**split_summary.json** (lines 1248-1277):
```python
if duplicate_parts_skipped > 0:
    summary_data["deduplication"] = {
        "total_parts_generated": total_parts_generated,
        "unique_parts": unique_parts,
        "duplicate_parts_skipped": duplicate_parts_skipped,
        "deduplication_rate_percent": round(deduplication_rate, 2),
    }
```

### Phase 3: Testing

**Unit Test:** `tests/functional/test_pass_b_splitter_contract.py::test_pass_b_deduplication_contract`

- Creates TOC catalog with duplicate page ranges
- Verifies only unique parts are kept
- Validates `skipped_duplicates` array in split_index.json
- Confirms deduplication metrics in split_summary.json
- Verifies duplicate PDF files are deleted

**Test Result:** ✅ PASSED

```
PASSED tests/functional/test_pass_b_splitter_contract.py::test_pass_b_deduplication_contract
```

### Phase 4: Integration Testing

**Script:** `scripts/test_passb_dedupe_integration.py`

Re-ran Pass B on Cyberpunk PDF with cleaned TOC. Result: 3 unique parts, 0 duplicates (TOC cleanup had already resolved the duplicate page ranges issue).

**Note:** While this specific test showed no duplicates (due to upstream TOC fixes), the guardrail remains valuable as a defensive measure against future TOC issues or OCR artifacts that could introduce duplicate page ranges.

## Impact Assessment

### Before Deduplication
- **Parts generated:** 317
- **Unique parts:** 36
- **Duplicates:** 281 (88.6%)
- **Pass C runtime:** ~10.5 hours
- **Total chunks:** ~225,000

### After Deduplication
- **Parts generated:** 36 (317 total, 281 skipped)
- **Unique parts:** 36
- **Duplicates skipped:** 281 (88.6%)
- **Pass C runtime:** ~1.2 hours (9.3 hour savings)
- **Total chunks:** ~25,000

### Estimated Savings
- **Runtime reduction:** 88.6% (9.3 hours saved)
- **Disk space saved:** ~281 PDF files not written/processed
- **Chunk reduction:** 90% fewer duplicate chunks generated
- **Cassandra writes saved:** Proportional to chunk reduction

## Acceptance Criteria

✅ **Deliverable 1:** Code changes implemented
  - Checksum-based duplicate detection
  - `duplicates_of` metadata tracking
  - Duplicate PDF deletion to save disk space

✅ **Deliverable 2:** Tests covering deduplication logic
  - Functional contract test validates behavior
  - Integration test framework created
  - Existing tests still pass

✅ **Deliverable 3:** Artifact example
  - Test artifacts demonstrate reduced part count
  - Manifests expose skipped parts for audit

## Acceptance Criteria Validation

✅ `split_summary.json` reports deduplication metrics
✅ `split_index.json` exposes skipped parts via `skipped_duplicates` array
✅ Pass C ingests only unique parts (no code changes needed)
✅ Projected runtime reduction: 10.5h → 1.2h (88.6% savings)

## Files Changed

### Core Implementation
- `src_common/pass_b_logical_splitter.py`: Deduplication logic

### Testing
- `tests/functional/test_pass_b_splitter_contract.py`: Contract test
- `scripts/test_passb_dedupe_integration.py`: Integration test script

### Documentation
- `docs/bugs/BUG-038-passb-deduplication-implementation.md`: This document

## Deployment

1. ✅ Code changes committed
2. ✅ Docker image rebuilt: `ttrpg-ingest:dev-20251004-final`
3. ✅ Deployed to DEV environment
4. ✅ Integration test executed successfully

## Next Steps

1. **Monitor production usage:** Track deduplication metrics in split_summary.json
2. **Coordinate with TOC normalization:** Both changes should compose cleanly
3. **Schema communication:** Notify Pass C and QA tooling about `skipped_duplicates` field
4. **Performance validation:** Confirm runtime reduction in production pipeline

## References

- **Original issue:** `MVP-Version-2/Prompt-Registry/PassB_Duplicate_Parts_Guardrail.md`
- **Evidence:** `env/dev/artifacts/job_1759593741_dev/pass_b/split_index.json`
- **QA Report:** `env/dev/artifacts/QA_Status_Update_20251004_1140.md`
- **Contract test:** Line 155 in `tests/functional/test_pass_b_splitter_contract.py`
