# Cleanup System Fix - Two-Stage Cleanup Implementation

**Date:** October 16, 2025
**Files Modified:** `ingestion/ingestion_wrapper.py`
**Files Verified:** `ingestion/gate_1_cleanup.py` (no changes needed)

---

## Problem Statement

The ingestion pipeline has two distinct cleanup operations with different purposes that were not properly configured:

### Cleanup Operation 1: Pre-Pipeline Clean (--clean flag)
- **Purpose:** Force complete rebuild by clearing ALL artifacts
- **Trigger:** `ingestion_wrapper.py --clean` flag
- **When:** BEFORE Gate 0 runs
- **Issue:** Was protecting `Prompt_Lib/` and `Gate_0_Check/` folders, preventing fresh rebuild

### Cleanup Operation 2: Post-Pipeline Clean (Gate 1)
- **Purpose:** Reclaim disk space from temporary processing artifacts
- **Trigger:** Automatic at end of successful pipeline
- **When:** AFTER Pass F completes
- **Issue:** Working correctly, no changes needed

---

## Changes Made

### File: ingestion/ingestion_wrapper.py

#### Change 1: CLEAN_PROTECTED_PATHS (Lines 141-144)

**Before:**
```python
globals()['CLEAN_PROTECTED_PATHS'] = {
    globals()['SOURCES_DIR'],
    globals()['PROMPT_LIB'],      # ✗ Was protecting AI recommendations
    globals()['GATE_0_CHECK'],    # ✗ Was protecting validation checksums
}
```

**After:**
```python
globals()['CLEAN_PROTECTED_PATHS'] = {
    globals()['SOURCES_DIR'],      # Preserve original source documents
    globals()['LOG_DIR'],           # Preserve ingestion logs for audit trail
}
```

**Result:** `--clean` flag now clears AI recommendations and validation checksums, forcing fresh rebuild

#### Change 2: CLEAN_DEFAULT_TARGETS (Lines 146-157)

**Before:**
```python
globals()['CLEAN_DEFAULT_TARGETS'] = [
    globals()['GATE_0_OUT'],
    globals()['PASS_A_OUT'],
    globals()['PASS_B_OUT'],
    globals()['PASS_C_OUT'],
    globals()['PASS_D_OUT'],
    globals()['PASS_E_OUT'],
    globals()['PASS_F_OUT'],
    globals()['LOG_DIR'],           # ✗ Should be protected, not cleaned
    globals()['STATE_DIR'],
]
```

**After:**
```python
globals()['CLEAN_DEFAULT_TARGETS'] = [
    globals()['GATE_0_OUT'],        # Gate 0 hash markers
    globals()['GATE_0_CHECK'],      # Gate 0 validation checksums (forces fresh rebuild) ← ADDED
    globals()['PASS_A_OUT'],        # Pass A TOC extraction artifacts
    globals()['PASS_B_OUT'],        # Pass B document splitting artifacts
    globals()['PASS_C_OUT'],        # Pass C full processing artifacts
    globals()['PASS_D_OUT'],        # Pass D embedding generation artifacts
    globals()['PASS_E_OUT'],        # Pass E knowledge graph artifacts
    globals()['PASS_F_OUT'],        # Pass F consistency check results
    globals()['PROMPT_LIB'],        # AI-generated pipeline recommendations ← ADDED
    globals()['STATE_DIR'],         # Pipeline state tracking files
]
```

**Result:** All temporary folders are explicitly targeted for cleanup

---

## File Verified: ingestion/gate_1_cleanup.py

**Status:** ✓ No changes needed - Already correctly implemented

**CLEANUP_FOLDERS (Lines 65-74):** ✓ Correct
```python
CLEANUP_FOLDERS = [
    "Gate_0_Out",      # Temporary hash markers
    "Pass_A_Out",      # Processing artifacts
    "Pass_B_Out",
    "Pass_C_Out",
    "Pass_D_Out",
    "Pass_E_Out",
    "Pass_F_Out",
    "State_Files"      # Pipeline state
]
```

**PRESERVE_FOLDERS (Lines 77-82):** ✓ Correct
```python
PRESERVE_FOLDERS = [
    "sources",           # Original documents
    "ingestion_logs",    # Audit trail
    "Gate_0_Check",      # Validation checksums for next run
    "Prompt_Lib"         # AI recommendations for human review
]
```

---

## Expected Behavior After Fix

### Scenario 1: Normal Run (no --clean flag)

**Initial State:**
- Gate_0_Check/ contains checksums from previous run
- Prompt_Lib/ contains AI recommendations from previous run

**Process:**
1. Gate 0 checks existing checksums in Gate_0_Check/
2. If matching, skips reprocessing
3. Pipeline runs (or skips if unchanged)
4. Gate 1 cleanup executes:
   - ✓ Clears contents of: Gate_0_Out/, Pass_A-F_Out/, State_Files/
   - ✓ Preserves: sources/, Gate_0_Check/, Prompt_Lib/, Ingestion_Logs/

**Final State:**
- Disk space reclaimed from temporary artifacts
- Validation checksums preserved for next run
- AI recommendations preserved for human review

---

### Scenario 2: Clean Run (--clean flag)

**Initial State:**
- Gate_0_Check/ may contain old checksums
- Prompt_Lib/ may contain old recommendations
- All Pass_*_Out/ folders may contain old artifacts

**Process:**
1. **Pre-cleanup executes** (`_clean_transfer_station_outputs()`):
   - ✓ Clears contents of: Gate_0_Check/, Prompt_Lib/, all Pass_*_Out/, State_Files/
   - ✓ Preserves: sources/, Ingestion_Logs/
   - ✓ Folders remain, only contents deleted
2. **Database cleanup executes** (via db_manager.py):
   - Clears MongoDB, Cassandra, Neo4j
3. Gate 0 finds no checksums → detects everything as "new"
4. Full fresh rebuild of all artifacts
5. **Gate 1 cleanup executes** (at end of pipeline):
   - ✓ Clears temporary artifacts
   - ✓ Preserves new Gate_0_Check/ and Prompt_Lib/ for future runs

**Final State:**
- Complete fresh rebuild with no stale data
- New validation checksums created
- New AI recommendations generated
- All databases cleared and repopulated

---

## Key Implementation Details

### Folder Preservation Method
**Function:** `_clear_directory_contents()` (Lines 445-452)
```python
def _clear_directory_contents(self, directory: Path) -> None:
    """Delete directory contents while keeping the directory itself."""
    directory.mkdir(parents=True, exist_ok=True)
    for entry in directory.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()
```

**Behavior:** ✓ Deletes all files and subdirectories but preserves parent folder structure

### Protected Paths Logic
**Function:** `_clean_transfer_station_outputs()` (Lines 419-443)
```python
targets: List[Path] = []
for child in TRANSFER_ROOT.iterdir():
    if child in CLEAN_PROTECTED_PATHS:
        continue  # Skip protected folders
    targets.append(child)

for path in CLEAN_DEFAULT_TARGETS:
    if path not in targets:
        targets.append(path)  # Ensure all targets are included

for target in targets:
    if target in CLEAN_PROTECTED_PATHS:
        continue  # Double-check protection
    if target.is_dir():
        self.logger.info(f"Cleaning directory: {target}")
        self._clear_directory_contents(target)  # Clear contents only
```

**Behavior:** ✓ Protects sources/ and logs/, clears everything else

---

## Testing Recommendations

### Test 1: Verify --clean Clears Everything
```bash
# Setup: Run normal pipeline to create artifacts
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/scripts/ingestion_wrapper.py \
  --mode ad-hoc --file /Transfer_Station/sources/test.pdf

# Verify artifacts exist
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Gate_0_Check/
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Prompt_Lib/

# Run with --clean
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/scripts/ingestion_wrapper.py \
  --mode ad-hoc --file /Transfer_Station/sources/test.pdf --clean

# Verify folders exist but are empty
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Gate_0_Check/  # Should be empty
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Prompt_Lib/   # Should be empty
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/sources/      # Should contain test.pdf
```

### Test 2: Verify Gate 1 Preserves Checksums and Prompts
```bash
# Run normal pipeline
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/scripts/ingestion_wrapper.py \
  --mode ad-hoc --file /Transfer_Station/sources/test.pdf

# Verify Gate 1 cleanup preserved critical folders
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Gate_0_Check/  # Should have files
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Prompt_Lib/   # Should have files
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Pass_A_Out/   # Should be empty
docker exec n8n_TTRPG_ingestion_engine ls /Transfer_Station/Pass_F_Out/   # Should be empty
```

### Test 3: Verify Folder Structure Preserved
```bash
# After any cleanup operation, verify folders still exist
docker exec n8n_TTRPG_ingestion_engine ls -la /Transfer_Station/

# Should see all folders present (even if empty):
# - sources/
# - Gate_0_Out/
# - Gate_0_Check/
# - Pass_A_Out/ through Pass_F_Out/
# - Prompt_Lib/
# - Ingestion_Logs/
# - State_Files/
```

---

## Summary

### What Was Fixed

1. **--clean flag now forces complete rebuild**
   - Clears Gate_0_Check/ (validation checksums)
   - Clears Prompt_Lib/ (old AI recommendations)
   - Forces Gate 0 to see everything as "new"

2. **Gate 1 cleanup preserves important data**
   - Keeps Gate_0_Check/ for next run
   - Keeps Prompt_Lib/ for human review
   - Reclaims disk from temporary artifacts

3. **Folder structure always preserved**
   - Only contents deleted, never folders
   - Prevents directory creation issues
   - Maintains clean Transfer Station layout

### Impact

- ✓ `--clean` flag now works as intended (forces complete rebuild)
- ✓ Normal runs preserve validation data for efficiency
- ✓ AI recommendations preserved for human review unless explicitly cleaned
- ✓ Disk space reclaimed from temporary processing artifacts
- ✓ No breaking changes to existing workflows
