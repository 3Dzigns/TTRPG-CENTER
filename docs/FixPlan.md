# Fix Plan - Ingestion Pipeline Failures

**Date**: 2025-10-17
**Priority**: CRITICAL (gate_1_log_analyzer), HIGH (Pass F validation), MEDIUM (Pass C timeout)
**Target Completion**: Within 1-2 days

---

## Executive Summary

Three distinct issues require fixes with different priorities and complexities:

1. **CRITICAL**: Fix gate_1_log_analyzer.py OpenAI response parsing (1-2 hours, low risk)
2. **HIGH**: Investigate and fix Pass F Cassandra/Neo4j validation failures (4-8 hours, medium risk)
3. **MEDIUM**: Optimize Pass C Unstructured API timeout handling (2-4 hours, low risk)

**Recommended Order**: Fix #1 first (unblocks diagnostics), then #2 (data quality), then #3 (performance).

---

## Fix #1: gate_1_log_analyzer OpenAI Parsing Bug

### Priority: CRITICAL
**Reason**: Blocks all automated remediation for pipeline failures

### Impact
- **Current**: Gate 1 analysis fails 100% of the time
- **Fixed**: Automated issue detection and remediation prompts work correctly

### Solution Strategy

#### Option A: Flexible Response Parsing (RECOMMENDED)

**Changes to `gate_1_log_analyzer.py` lines 227-240**:

```python
# Current (BROKEN):
if isinstance(result, list):
    issues = result
elif isinstance(result, dict) and "issues" in result:
    issues = result["issues"]
else:
    raise Gate1LogAnalyzerError(f"Unexpected response format: {type(result)}")

# Fixed (ROBUST):
if isinstance(result, list):
    issues = result
elif isinstance(result, dict):
    # Try multiple possible keys
    for key in ["issues", "problems", "findings", "errors", "analysis", "results"]:
        if key in result and isinstance(result[key], list):
            issues = result[key]
            break
    else:
        # If no known key with array, try to extract values
        array_values = [v for v in result.values() if isinstance(v, list)]
        if array_values:
            issues = array_values[0]  # Take first array found
        else:
            # Last resort: wrap entire dict in array if it looks like an issue
            if any(k in result for k in ["issue_type", "severity", "summary"]):
                issues = [result]
            else:
                raise Gate1LogAnalyzerError(
                    f"Cannot extract issues from response. Keys: {list(result.keys())}"
                )
else:
    raise Gate1LogAnalyzerError(f"Unexpected response format: {type(result)}")
```

**Pros**:
- Handles multiple possible response structures
- Gracefully degrades to sensible defaults
- No API changes needed
- Backward compatible

**Cons**:
- Slightly more complex logic
- Adds ~10 lines of code

#### Option B: Remove JSON Object Constraint (ALTERNATIVE)

**Changes to `gate_1_log_analyzer.py` line 211**:

```python
# Current:
"response_format": {"type": "json_object"}

# Fixed:
# Remove response_format parameter entirely, let OpenAI return natural JSON
```

**Update lines 227-233**:
```python
# Handle array directly without object wrapper
if isinstance(result, list):
    issues = result
elif isinstance(result, dict) and "issues" in result:
    issues = result["issues"]
else:
    # If we get a raw dict that looks like a single issue, wrap it
    if all(k in result for k in ["issue_type", "severity", "summary"]):
        issues = [result]
    else:
        raise Gate1LogAnalyzerError(f"Unexpected response: {result}")
```

**Pros**:
- Simpler change (remove constraint)
- Aligns prompt and API behavior
- OpenAI may return more natural format

**Cons**:
- Less control over response structure
- May get non-JSON responses occasionally
- Requires more error handling

#### Option C: Update System Prompt (COMPLEMENTARY)

**Changes to `gate_1_log_analyzer.py` lines 122-136**:

```python
# Current:
"""
Output Format:
Return a JSON array of issue objects. Each object should have:
{
  "issue_type": "error|performance|data_quality|configuration",
  ...
}
"""

# Fixed:
"""
Output Format:
Return a JSON object with an "issues" key containing an array of issue objects:
{
  "issues": [
    {
      "issue_type": "error|performance|data_quality|configuration",
      "severity": "critical|high|medium|low",
      ...
    }
  ]
}

If no issues are found, return: {"issues": []}
"""
```

**Pros**:
- Aligns prompt with API response_format constraint
- Makes expected structure explicit
- Can combine with Option A for maximum robustness

**Cons**:
- Requires testing to ensure OpenAI follows new format
- Slightly longer prompt (minor token cost)

### Implementation Steps

1. **Create feature branch**:
   ```bash
   cd E:/n8n_TTRPG_Center
   git checkout -b fix/gate1-log-analyzer-openai-parsing
   ```

2. **Implement Option A + Option C** (most robust):
   - Update system prompt (lines 122-136)
   - Update parsing logic (lines 227-240)
   - Add logging for response structure debugging

3. **Add unit tests**:
   ```python
   # tests/test_gate1_log_analyzer.py
   def test_openai_response_parsing():
       # Test array format
       assert parse_response([{...}]) == [{...}]

       # Test object with "issues" key
       assert parse_response({"issues": [{...}]}) == [{...}]

       # Test object with alternative keys
       assert parse_response({"problems": [{...}]}) == [{...}]

       # Test single issue as dict
       assert parse_response({"issue_type": "error", ...}) == [{...}]
   ```

4. **Test with actual OpenAI API**:
   ```bash
   python gate_1_log_analyzer.py \
     E:/n8n_TTRPG_Transfer_Station/Ingestion_Logs/20251017_205214_ingestion.log \
     --output /tmp/test_fix
   ```

5. **Validate success**:
   - Exit code should be 0
   - Prompt files created in output directory
   - No "Unexpected response format" errors

6. **Run integration test**:
   - Trigger Pass F failure
   - Verify Gate 1 analysis completes successfully
   - Check generated remediation prompts are valid

7. **Code review and merge**:
   ```bash
   git add ingestion/gate_1_log_analyzer.py tests/test_gate1_log_analyzer.py
   git commit -m "fix: Robust OpenAI response parsing in gate_1_log_analyzer

   - Support multiple response structure formats
   - Handle object wrappers with various key names
   - Graceful fallback to first array found in response
   - Updated system prompt to align with API constraints
   - Added unit tests for response parsing logic

   Fixes: gate_1_log_analyzer_bug
   Closes: #issue-number"

   git push origin fix/gate1-log-analyzer-openai-parsing
   ```

### Risk Assessment
- **Risk Level**: LOW
- **Blast Radius**: Small (single script, non-critical path)
- **Rollback**: Easy (revert commit)
- **Testing**: Can test thoroughly before deployment

### Time Estimate
- Coding: 30 minutes
- Testing: 30 minutes
- Documentation: 15 minutes
- Review & Merge: 15 minutes
- **Total**: 1.5 hours

---

## Fix #2: Pass F Cassandra/Neo4j Validation Failures

### Priority: HIGH
**Reason**: Data integrity issues affect 2/3 of data stores

### Impact
- **Current**: 66% of data stores fail validation (Cassandra, Neo4j)
- **Fixed**: All stores pass validation, pipeline progresses to Pass G

### Root Cause Hypotheses

#### Hypothesis 1: Pass D Embedding Issues
**Evidence**: Cassandra violations = 2x checked count (15,308 vs 7,654)

**Possible causes**:
- Embedding generation failing silently
- Cassandra writes succeeding but data malformed
- Vector dimension mismatches (expected 1536)
- Duplicate chunk IDs causing double-counting

**Investigation steps**:
```bash
# Check Cassandra data
docker exec n8n_TTRPG_cassandra cqlsh -e "
  USE ttrpg_vectors;
  SELECT COUNT(*) FROM embeddings WHERE document_id='cyberpunk_v3_cp4110_core_rulebook_4f81185e7057';
  SELECT chunk_id, LENGTH(embedding_vector) FROM embeddings LIMIT 10;
"

# Check for duplicate chunk_ids
docker exec n8n_TTRPG_cassandra cqlsh -e "
  USE ttrpg_vectors;
  SELECT chunk_id, COUNT(*) FROM embeddings
  WHERE document_id='cyberpunk_v3_cp4110_core_rulebook_4f81185e7057'
  GROUP BY chunk_id HAVING COUNT(*) > 1;
"
```

#### Hypothesis 2: Pass E Graph Building Issues
**Evidence**: Neo4j score = 0.0 (1 checked, 1 violation)

**Possible causes**:
- Document node not created
- Graph relationship errors
- Neo4j connection failures during Pass E
- Validation logic checking wrong node properties

**Investigation steps**:
```bash
# Check Neo4j graph data
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p password "
  MATCH (d:Document {document_id: 'cyberpunk_v3_cp4110_core_rulebook_4f81185e7057'})
  RETURN d;
"

# Check relationships
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p password "
  MATCH (d:Document {document_id: 'cyberpunk_v3_cp4110_core_rulebook_4f81185e7057'})-[r]->(n)
  RETURN type(r), count(n);
"
```

#### Hypothesis 3: Pass F Validation Logic Bug
**Evidence**: MongoDB works (1.0 score), others fail (0.0 score)

**Possible causes**:
- Validation thresholds too strict
- Incorrect violation counting logic
- Schema expectations mismatched with actual data
- The suspicious 2x pattern in Cassandra suggests counting error

**Investigation steps**:
```bash
# Review Pass F validation code
grep -n "violations" ingestion/pass_f_consistency_check.py
grep -n "score" ingestion/pass_f_consistency_check.py

# Check validation logic for Cassandra section
# Look for duplicate increment patterns or off-by-one errors
```

### Solution Strategy

#### Step 1: Diagnostic Pass (2-3 hours)

1. **Run investigations from hypotheses above**
2. **Add debug logging to Pass F**:
   ```python
   # In pass_f_consistency_check.py
   print(f"[DEBUG] Cassandra checked: {checked}")
   print(f"[DEBUG] Cassandra violations: {violations}")
   print(f"[DEBUG] Sample violation reasons: {violation_reasons[:5]}")
   ```

3. **Run Pass F with verbose output**:
   ```bash
   python pass_f_consistency_check.py <doc_json> \
     --output /tmp/debug_passf \
     --verbose --debug
   ```

4. **Analyze results**:
   - Determine if issue is in Pass D/E (bad data) or Pass F (bad validation)
   - Identify specific violation types
   - Check if 2x pattern is consistent or varies

#### Step 2: Fix Implementation (2-4 hours)

**Scenario A: Bug in Pass F Validation Logic**

```python
# Example fix for double-counting bug
# In pass_f_consistency_check.py Cassandra validation section

# BEFORE (hypothetical bug):
for chunk in cassandra_chunks:
    if not validate_chunk(chunk):
        violations += 1
        violations += 1  # Accidental duplicate!

# AFTER:
for chunk in cassandra_chunks:
    if not validate_chunk(chunk):
        violations += 1
```

**Scenario B: Missing Data from Pass D/E**

```python
# Fix Pass D to ensure embeddings are written
# In pass_d_hayhooks.py

def write_embedding(chunk_data, embedding_vector):
    # Add validation before write
    if len(embedding_vector) != 1536:
        raise ValueError(f"Invalid vector dimension: {len(embedding_vector)}")

    # Add retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            cassandra_session.execute(insert_query, (chunk_id, embedding_vector))
            break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

**Scenario C: Schema Mismatch**

```python
# Update Pass F validation expectations
# In pass_f_consistency_check.py

# Align validation with actual Pass D/E schemas
EXPECTED_CASSANDRA_FIELDS = ["chunk_id", "document_id", "embedding_vector", "metadata"]
EXPECTED_NEO4J_PROPERTIES = ["document_id", "title", "source_file", "doc_hash"]
```

#### Step 3: Re-run Full Pipeline (1 hour)

```bash
# Test with a small document first
docker exec n8n_TTRPG_ingestion python ingestion_wrapper.py \
  --source /Transfer_Station/sources/small_test.pdf \
  --passes A,B,C,D,E,F,G \
  --force-rebuild

# Check Pass F scores - should be > 0.9 for all stores
```

### Risk Assessment
- **Risk Level**: MEDIUM-HIGH
- **Blast Radius**: Medium (affects data pipeline, could corrupt stores)
- **Rollback**: Medium difficulty (may need to clean/rebuild databases)
- **Testing**: Requires database access, longer test cycles

### Time Estimate
- Investigation: 2-3 hours
- Fix Implementation: 2-4 hours
- Testing: 1-2 hours
- Documentation: 30 minutes
- **Total**: 6-10 hours

---

## Fix #3: Pass C Unstructured API Timeout

### Priority: MEDIUM
**Reason**: Performance issue, specific to large documents

### Impact
- **Current**: Large documents (>200 pages) may timeout during Pass C
- **Fixed**: All documents process reliably regardless of size

### Solution Strategy

#### Option A: Increase Timeout (QUICK FIX)

**Changes to Pass C or Unstructured client**:

```python
# In pass_c_parsing.py or API client config

# Current:
timeout = 300  # 5 minutes

# Fixed:
timeout = 600  # 10 minutes (or configurable via env var)
```

**Pros**: Simple, immediate relief
**Cons**: Doesn't address root performance issue

#### Option B: Implement Retry with Backoff (RECOMMENDED)

```python
# In pass_c_parsing.py

import time
from requests.exceptions import Timeout

def process_chunk_with_retry(chunk_file, max_retries=3, base_timeout=300):
    """Process chunk with exponential backoff retry."""
    for attempt in range(max_retries):
        timeout = base_timeout * (2 ** attempt)  # 300s, 600s, 1200s

        try:
            result = unstructured_api.process(chunk_file, timeout=timeout)
            return result
        except Timeout as e:
            if attempt == max_retries - 1:
                logging.error(f"Failed after {max_retries} attempts: {chunk_file}")
                raise

            logging.warning(f"Timeout on attempt {attempt+1}, retrying with {timeout*2}s timeout")
            time.sleep(30)  # Brief cooldown
```

**Pros**: Resilient, handles transient issues
**Cons**: Longer overall processing time for problematic chunks

#### Option C: Optimize Unstructured API Processing (LONG-TERM)

- Profile Unstructured API performance
- Optimize OCR settings (lower resolution for faster processing)
- Consider alternative chunking strategy (smaller parts)
- Scale Unstructured API horizontally (multiple instances)

**Pros**: Addresses root cause
**Cons**: Requires infrastructure changes, more complex

### Implementation Steps

1. **Quick win: Implement Option A + B**:
   ```python
   # Add to pass_c_parsing.py
   UNSTRUCTURED_TIMEOUT = int(os.getenv("UNSTRUCTURED_TIMEOUT", "600"))  # Default 10min
   MAX_RETRIES = int(os.getenv("PASS_C_MAX_RETRIES", "2"))
   ```

2. **Add monitoring**:
   ```python
   # Log timing for each chunk
   start_time = time.time()
   result = process_chunk_with_retry(chunk_file)
   duration = time.time() - start_time
   logging.info(f"Processed {chunk_file} in {duration:.1f}s")
   ```

3. **Test with large document**:
   ```bash
   # Use Pathfinder (known to timeout)
   python pass_c_parsing.py \
     /Transfer_Station/Pass_B_Out/pathfinder_rpg_core_rulebook_manifest.json \
     --output /tmp/test_passC
   ```

### Risk Assessment
- **Risk Level**: LOW
- **Blast Radius**: Small (only affects Pass C, easy to revert)
- **Rollback**: Trivial (change timeout back)
- **Testing**: Requires large test documents

### Time Estimate
- Implementation: 1 hour
- Testing: 1-2 hours
- **Total**: 2-3 hours

---

## Implementation Priority & Timeline

### Phase 1: Critical (Day 1)
**Target**: Fix gate_1_log_analyzer (Fix #1)
- **Duration**: 1.5 hours
- **Owner**: Backend developer
- **Blockers**: None
- **Dependencies**: None

### Phase 2: High Priority (Day 1-2)
**Target**: Fix Pass F validation issues (Fix #2)
- **Duration**: 6-10 hours
- **Owner**: Backend + Data engineer
- **Blockers**: None (can run parallel to Phase 1)
- **Dependencies**: Database access, test data

### Phase 3: Medium Priority (Day 2)
**Target**: Optimize Pass C timeouts (Fix #3)
- **Duration**: 2-3 hours
- **Owner**: Backend developer
- **Blockers**: None
- **Dependencies**: Large test documents

**Total Estimated Time**: 10-15 hours (1.5-2 days)

---

## Testing Strategy

### Unit Tests
```bash
# Test gate_1_log_analyzer response parsing
pytest tests/test_gate1_log_analyzer.py -v

# Test Pass F validation logic
pytest tests/test_pass_f_validation.py -v

# Test Pass C retry logic
pytest tests/test_pass_c_timeout.py -v
```

### Integration Tests
```bash
# End-to-end pipeline test with small document
./scripts/test_ingestion_pipeline.sh --quick-test

# Full pipeline test with large document
./scripts/test_ingestion_pipeline.sh --full-test --document=pathfinder_core.pdf
```

### Smoke Tests Post-Deployment
```bash
# Verify Gate 1 analysis works
python gate_1_log_analyzer.py <any_log_file>

# Verify Pass F validation passes
python pass_f_consistency_check.py <test_doc_json>

# Verify Pass C handles large docs
python pass_c_parsing.py <large_doc_manifest>
```

---

## Rollback Plan

### If Fix #1 Breaks
```bash
git revert <commit-hash>
docker restart n8n_TTRPG_ingestion
```

### If Fix #2 Causes Data Corruption
```bash
# Stop ingestion pipeline
docker stop n8n_TTRPG_ingestion

# Restore databases from backup
./scripts/restore_db_backup.sh --date=2025-10-17

# Revert code changes
git revert <commit-hash>

# Restart with original code
docker start n8n_TTRPG_ingestion
```

### If Fix #3 Makes Things Worse
```bash
# Simply adjust timeout back
export UNSTRUCTURED_TIMEOUT=300
docker restart n8n_TTRPG_ingestion
```

---

## Success Criteria

### Fix #1 Success
- [ ] gate_1_log_analyzer runs without "Unexpected response format" error
- [ ] Remediation prompt files are generated in output directory
- [ ] OpenAI API calls succeed with various response structures
- [ ] Unit tests pass for all response format variations

### Fix #2 Success
- [ ] Pass F validation scores > 0.9 for all three stores (MongoDB, Cassandra, Neo4j)
- [ ] Cassandra violations no longer 2x the checked count
- [ ] Neo4j score > 0.0 with valid graph data
- [ ] Pipeline progresses to Pass G after Pass F

### Fix #3 Success
- [ ] Large documents (>200 pages) process without timeout
- [ ] Retry logic handles transient failures
- [ ] Overall Pass C duration acceptable (< 1 hour for 500-page doc)
- [ ] No data loss or corruption from timeout handling

---

## Post-Fix Monitoring

### Metrics to Track
```python
# Add to ingestion monitoring
metrics = {
    "gate_1_analysis_success_rate": 0.0,  # Should reach 100%
    "pass_f_mongo_avg_score": 0.0,        # Should stay 1.0
    "pass_f_cassandra_avg_score": 0.0,    # Should reach > 0.9
    "pass_f_neo4j_avg_score": 0.0,        # Should reach > 0.9
    "pass_c_timeout_rate": 0.0,           # Should drop to < 1%
    "pass_c_avg_duration_seconds": 0.0,   # Monitor for degradation
}
```

### Alert Thresholds
- Gate 1 analysis failure rate > 10%: ALERT
- Pass F any store score < 0.9: WARNING
- Pass C timeout rate > 5%: WARNING
- Pass C avg duration > 600s: WARNING

---

## Related Documentation

- **Root Cause Analysis**: `docs/RCA.md`
- **Reproduction Steps**: `docs/ReproSteps.md`
- **Pipeline Guide**: `docs/INGESTION_PIPELINE_GUIDE.md`
- **Pass F Changelog**: `ingestion/PASS_F_V2.2.0_CHANGELOG.md`

---

**Plan Version**: 1.0
**Created**: 2025-10-17
**Status**: Ready for implementation
**Approval**: Pending review
