# Manual Database Cleanup Guide - Pass F Validation Failures

**Generated:** October 17, 2025
**Purpose:** Human review and manual execution of database cleanup operations
**Status:** REQUIRES MANUAL REVIEW AND APPROVAL

---

## Executive Summary

All three ingestion files are failing Pass F validation due to data quality issues in Cassandra and Neo4j. The automated HGRN (Hybrid Generative Remediation Network) system has analyzed the failures and generated cleanup recommendations.

**Overall Assessment:**
- **MongoDB:** 100% valid (no cleanup needed)
- **Cassandra:** 0% valid (32,088 violations across 16,044 chunks)
- **Neo4j:** 0% valid (1 graph relationship failure)
- **Source Validation:** 81.3% valid (53 TOC/dictionary extraction issues)

**Root Cause:** Pass A (TOC extraction) and Pass C (dictionary extraction) generated invalid/noisy terms that were ingested into MongoDB and embedded into Cassandra. Neo4j validation failed due to missing document-level relationships.

---

## Database Connection Information

### MongoDB
- **Container:** `n8n_TTRPG_mongodb`
- **Host:** `n8n_TTRPG_mongodb` (Docker internal)
- **Port:** `27017` (internal), `9002` (external via host)
- **URI:** `mongodb://n8n_TTRPG_mongodb:27017`
- **Database:** `ttrpg_ingestion`
- **Collection:** `terms`

**External Connection:**
```bash
mongosh mongodb://localhost:9002/ttrpg_ingestion
```

### Cassandra
- **Container:** `n8n_TTRPG_cassandra`
- **Host:** `n8n_TTRPG_cassandra` (Docker internal)
- **Port:** `9042` (internal and external)
- **Keyspace:** `ttrpg_vectors`
- **Table:** `embeddings`
- **Validation Issues:** 32,088 violations across 16,044 chunks (exactly 2x ratio)

**External Connection:**
```bash
cqlsh localhost 9042
USE ttrpg_vectors;
```

### Neo4j
- **Container:** `n8n_TTRPG_neo4j`
- **Host:** `n8n_TTRPG_neo4j` (Docker internal)
- **Bolt Port:** `7687` (internal), `9005` (external)
- **HTTP Port:** `7474` (internal), `9003` (external)
- **URL:** `bolt://n8n_TTRPG_neo4j:7687`
- **User:** `neo4j`
- **Database:** `neo4j`

**External Connection:**
```bash
# Browser: http://localhost:9003
# Bolt: bolt://localhost:9005
```

---

## File 1: Pathfinder RPG Core Rulebook (6th Printing)

### Document Details
- **Document ID:** `pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c`
- **Source File:** `Pathfinder RPG - Core Rulebook (6th Printing).pdf`
- **SHA256:** `4f4b1d9d2b6ca812ab4fb5a38727ff7922c41cbfe4e4e214511249ce134a8cb5`
- **Pages:** 578
- **Overall Score:** 0.4533 (need 0.9)
- **Issues Found:** 98

### Validation Scores
| Database | Checked | Violations | Score | Status |
|----------|---------|------------|-------|--------|
| MongoDB | 2,079 | 0 | 1.0 | ✅ PASS |
| Cassandra | 16,044 | 32,088 | 0.0 | ❌ FAIL |
| Neo4j | 1 | 1 | 0.0 | ❌ FAIL |
| Source | 284 | 53 | 0.813 | ⚠️ WARN |

### MongoDB Cleanup (30 operations)

**Issue Type:** `TermNotFoundInSource` - Dictionary terms extracted but not found in source PDF

**Impact:** These are false positive terms extracted by Pass C that don't actually exist in the document. They pollute the search index and create noise in embeddings.

**Sample Issues:**
1. `"(7th), dimension door (9th), overland flight (11th), true seeing"` - Partial spell list fragment
2. `"(Cha; Trained Only)"` - Skill modifier fragment
3. `"(Dex; Armor Check Penalty)"` - Skill modifier fragment
4. `"102,660 gp (2 wishes), 142,960 gp (3 wishes); Weight 2 lbs."` - Table cell data
5. `"\ODIFIER MODIFIER MODIFIER MODIFER"` - OCR noise

**Root Cause:** Pass C dictionary extraction rules are too permissive, capturing:
- Table cell fragments
- Parenthetical modifiers
- OCR noise from headers/footers
- Multi-line text spans

#### MongoDB Cleanup Commands

**⚠️ IMPORTANT: Review each term before deletion to ensure it's truly invalid**

```javascript
// Connect to MongoDB
use ttrpg_ingestion

// Example cleanup commands (review before execution)

// 1. Delete obvious OCR noise
db.terms.deleteOne({
  "document_id": "pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c",
  "term": "\\ODIFIER MODIFIER MODIFIER MODIFER"
})

// 2. Delete table cell fragments
db.terms.deleteOne({
  "document_id": "pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c",
  "term": "102,660 gp (2 wishes), 142,960 gp (3 wishes); Weight 2 lbs."
})

// 3. Delete partial spell lists
db.terms.deleteOne({
  "document_id": "pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c",
  "term": "(7th), dimension door (9th), overland flight (11th), true seeing"
})

// 4. Bulk delete pattern: skill modifiers in parentheses
// (CAREFUL: Some might be valid cross-references)
db.terms.deleteMany({
  "document_id": "pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c",
  "term": { $regex": "^\\([A-Z][a-z]+; " }
})

// Verification: Count remaining terms
db.terms.countDocuments({
  "document_id": "pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c"
})
```

**Complete Command List:** See `pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c_remediation_plan.json` MongoDB section (30 DELETE operations)

---

### Cassandra Cleanup (11 operations)

**Issue Type:** Multiple validation failures per chunk

**Cassandra Statistics:**
- **Chunks Checked:** 16,044
- **Total Violations:** 32,088
- **Ratio:** Exactly 2.0x (each chunk fails ~2 of 7 validation checks)

**7 Validation Checks (from pass_f_consistency_check.py):**
1. **Page bounds check:** Verifies page number is within document range
2. **Game system check:** Verifies game_system matches expected value
3. **Publisher check:** Verifies publisher matches expected value
4. **Text content check:** Verifies chunk has non-empty text
5. **Content grounding check:** Verifies text overlaps with source pages
6. **Embedding validity check:** Verifies embedding is non-null and valid dimensions
7. **Chunk count check:** Verifies total chunks match expected count

**Failure Pattern Analysis:**

Based on 2.0x violation ratio, the most likely failing checks are:
- **#5 Content grounding** (text doesn't match source pages - caused by OCR noise)
- **#6 Embedding validity** (embedding is null or invalid - caused by Pass D failures)

Less likely but possible:
- **#1 Page bounds** (page numbers out of range - metadata issue)
- **#4 Text content** (empty chunks - Pass C extraction issue)

#### Cassandra Investigation Commands

**Step 1: Connect and inspect sample chunks**

```cql
-- Connect to Cassandra
cqlsh localhost 9042

USE ttrpg_vectors;

-- Inspect table schema
DESCRIBE TABLE embeddings;

-- Sample chunk inspection (first 5 chunks)
SELECT element_id, chunk_index, page_number, game_system, publisher,
       text_content, embedding, status, job_id
FROM embeddings
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
LIMIT 5;

-- Count total chunks
SELECT COUNT(*) FROM embeddings
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c';

-- Count chunks with null embeddings
SELECT COUNT(*) FROM embeddings
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
AND embedding = null
ALLOW FILTERING;

-- Count chunks with empty text
SELECT COUNT(*) FROM embeddings
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
AND text_content = ''
ALLOW FILTERING;

-- Sample chunks with potential issues
SELECT element_id, chunk_index, page_number, text_content
FROM embeddings
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
AND page_number > 578  -- Out of bounds (PDF has 578 pages)
ALLOW FILTERING;
```

**Step 2: Identify specific violation types**

Review the Pass F evidence file for exact violations:
```bash
# Read HGRN pipeline suggestions
cat /Transfer_Station/Pass_F_Out/hgrn_output/pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c/hgrn_pipeline_suggestions.md
```

**Step 3: Generate cleanup plan based on findings**

Once violation types are identified, create UPDATE/INSERT/DELETE commands:

```cql
-- Example: Update chunks with invalid embeddings
-- (REQUIRES: Re-running Pass D to regenerate embeddings)

UPDATE embeddings
SET status = 'stale'
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
AND embedding = null;

-- Example: Delete chunks with empty text content
DELETE FROM embeddings
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
AND element_id = '<specific_element_id>'
AND chunk_index = <specific_index>;

-- Example: Update incorrect game_system metadata
UPDATE embeddings
SET game_system = 'Pathfinder RPG'
WHERE document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
AND game_system != 'Pathfinder RPG';
```

**Complete Command List:** See `pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c_remediation_plan.json` Cassandra section (11 operations)

**⚠️ WARNING:** Cassandra cleanup may require re-ingestion of Pass D (embeddings) if embeddings are invalid.

---

### Neo4j Cleanup (1 operation)

**Issue Type:** Document-level relationship missing or invalid

**Neo4j Statistics:**
- **Relationships Checked:** 1
- **Violations:** 1
- **Score:** 0.0

**Root Cause:** Pass E (graph builder) likely failed to create the document-level node or relationships.

#### Neo4j Investigation Commands

**Step 1: Connect and inspect graph structure**

```cypher
// Connect to Neo4j browser: http://localhost:9003

// Check if document node exists
MATCH (d:Document {document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'})
RETURN d;

// Check for any nodes related to this document
MATCH (n)
WHERE n.document_id = 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'
RETURN labels(n), count(n);

// Check for orphaned chunks (chunks without document parent)
MATCH (c:Chunk {document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'})
WHERE NOT (c)-[:PART_OF]->(:Document)
RETURN count(c) AS orphaned_chunks;

// Inspect graph schema
CALL db.schema.visualization();

// Count total relationships for this document
MATCH (n {document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'})-[r]-()
RETURN type(r), count(r);
```

**Step 2: Create missing document node and relationships**

```cypher
// Create document node if missing
MERGE (d:Document {
  document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c',
  title: 'Pathfinder RPG - Core Rulebook (6th Printing)',
  game_system: 'Pathfinder RPG',
  publisher: 'Paizo Publishing',
  page_count: 578,
  created_at: datetime(),
  status: 'active'
})
RETURN d;

// Link orphaned chunks to document
MATCH (c:Chunk {document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'})
MATCH (d:Document {document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'})
WHERE NOT (c)-[:PART_OF]->(d)
MERGE (c)-[:PART_OF]->(d);

// Verify relationships created
MATCH (c:Chunk {document_id: 'pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c'})-[r:PART_OF]->(d:Document)
RETURN count(r) AS connected_chunks;
```

**Complete Command List:** See `pathfinder_rpg_core_rulebook_6th_printing_4f4b1d9d2b6c_remediation_plan.json` Neo4j section (1 UPDATE operation)

---

## File 2: Cyberpunk v3 - CP4110 Core Rulebook

### Document Details
- **Document ID:** `cyberpunk_v3_cp4110_core_rulebook_4f81185e7057`
- **Overall Score:** 0.4443 (need 0.9)

### Validation Scores
| Database | Checked | Violations | Score | Status |
|----------|---------|------------|-------|--------|
| MongoDB | 1,391 | 0 | 1.0 | ✅ PASS |
| Cassandra | 7,654 | 15,308 | 0.0 | ❌ FAIL |
| Neo4j | 1 | 1 | 0.0 | ❌ FAIL |

**Cleanup Commands:** See `cyberpunk_v3_cp4110_core_rulebook_4f81185e7057_remediation_plan.json` (41KB)

---

## File 3: Ultimate Magic (2nd Printing)

### Document Details
- **Document ID:** `ultimate_magic_2nd_printing_6aecba757f03`
- **Overall Score:** 0.4878 (need 0.9)

### Validation Scores
| Database | Checked | Violations | Score | Status |
|----------|---------|------------|-------|--------|
| MongoDB | 671 | 0 | 1.0 | ✅ PASS |
| Cassandra | 7,110 | 14,220 | 0.0 | ❌ FAIL |
| Neo4j | 1 | 1 | 0.0 | ❌ FAIL |

**Cleanup Commands:** See `ultimate_magic_2nd_printing_6aecba757f03_remediation_plan.json` (16KB)

---

## Root Cause Analysis & Pipeline Fixes

### Issue 1: Pass A - TOC Extraction Failures

**Problem:** 27 TOC entries not located on expected page 4

**Examples:**
- "Using This Book" not found on page 4
- "Common Terms" not found on page 4
- "Generating a Character" not found on page 4

**Root Cause:** TOC extraction logic assumes all entries are on a single page (page 4), but actual TOC spans multiple pages or uses different page numbering.

**Fix Required:** Update Pass A TOC extraction to:
1. Search across multiple pages (pages 2-8)
2. Handle multi-page TOCs
3. Validate page numbers against PDF metadata

**File:** `ingestion/pass_a_unstructured.py` or `ingestion/pass_a_metadata.py`

---

### Issue 2: Pass C - Dictionary Extraction Rules Too Permissive

**Problem:** 30+ invalid terms extracted (OCR noise, table fragments, modifiers)

**Examples:**
- `"\\ODIFIER MODIFIER MODIFIER MODIFER"` - Header OCR noise
- `"102,660 gp (2 wishes)..."` - Table cell data
- `"(Cha; Trained Only)"` - Skill modifier fragment

**Root Cause:** Dictionary extraction rules capture:
- Non-alphanumeric sequences
- Table cells with structured data
- Parenthetical modifiers without context
- Multi-line text spans

**Fix Required:** Update Pass C dictionary extraction rules:
1. Filter out strings with >35% non-alphabetic characters
2. Exclude parenthetical-only terms (e.g., "(Cha; Trained Only)")
3. Minimum sentence structure (subject + verb or 3+ words)
4. Table cell detection and exclusion

**File:** `ingestion/pass_c_parsing.py` or dictionary extraction configuration

---

### Issue 3: Pass D - Embedding Generation Failures

**Problem:** Cassandra chunks have invalid/null embeddings (inferred from 2x violation ratio)

**Root Cause:** Pass D (hayhooks embedding service) likely failed on:
- Empty text chunks
- Extremely long chunks (>512 tokens)
- Special characters/encoding issues
- API timeouts

**Fix Required:** Add retry logic and validation in Pass D:
1. Skip chunks with empty text
2. Truncate chunks >450 tokens before embedding
3. Retry failed embeddings with exponential backoff
4. Mark failed chunks as 'stale' instead of keeping null embeddings

**File:** `ingestion/pass_d_hayhooks.py`

---

### Issue 4: Pass E - Neo4j Graph Creation Failures

**Problem:** Document-level node missing for all 3 files (Neo4j score=0.0)

**Root Cause:** Pass E graph builder failed to create document node or relationships

**Possible Causes:**
- Neo4j connection timeout
- Transaction rollback on error
- Document metadata missing
- Incorrect Cypher query

**Fix Required:** Investigate Pass E logs and add:
1. Document node creation validation
2. Rollback recovery (re-create if missing)
3. Better error logging
4. Transaction timeout handling

**File:** `ingestion/pass_e_graph_builder.py` or `ingestion/pass_e_neo4j_upsert.py`

---

## Cleanup Execution Workflow

### Phase 1: Investigation (CURRENT PHASE)
✅ Analyze Pass F validation results
✅ Review HGRN remediation plans
✅ Identify root causes
⏸️ **Connect to databases and inspect data**
⏸️ **Verify violations match HGRN analysis**

### Phase 2: Manual Cleanup (AWAITING APPROVAL)
- [ ] Execute MongoDB deletions (30 operations for Pathfinder)
- [ ] Execute Cassandra updates (11 operations for Pathfinder)
- [ ] Execute Neo4j relationship creation (1 operation for Pathfinder)
- [ ] Verify Pass F score improves to >0.9

### Phase 3: Pipeline Fixes (MEDIUM TERM)
- [ ] Fix Pass A TOC extraction (spans multiple pages)
- [ ] Fix Pass C dictionary rules (filter noise)
- [ ] Fix Pass D embedding generation (null handling)
- [ ] Fix Pass E Neo4j document nodes (creation validation)

### Phase 4: Re-ingestion Test (VERIFICATION)
- [ ] Clear all data for one document
- [ ] Run full ingestion from raw PDF
- [ ] Verify Pass F score >0.9 on first attempt
- [ ] Apply pipeline fixes prevent recurrence

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MongoDB deletion removes valid terms | Low | Medium | Review each term manually before deletion |
| Cassandra cleanup breaks embeddings | Medium | High | Create backup before UPDATE operations |
| Neo4j relationship corruption | Low | Medium | Use MERGE instead of CREATE for idempotency |
| Re-ingestion still fails | High | High | Fix pipeline issues (Phase 3) before re-ingestion |

---

## Recommended Approach

### Option A: Quick Fix (Database Cleanup Only)
**Time:** 2-3 hours
**Pros:** Fast, unblocks current files
**Cons:** Issue will recur on new files

**Steps:**
1. Execute MongoDB deletions (review each term)
2. Execute Cassandra updates (mark invalid chunks as stale)
3. Execute Neo4j document node creation
4. Re-run Pass F validation
5. Verify scores >0.9

### Option B: Comprehensive Fix (Database + Pipeline)
**Time:** 8-12 hours
**Pros:** Prevents recurrence, long-term solution
**Cons:** Requires more time and testing

**Steps:**
1. Same as Option A (database cleanup)
2. Fix Pass A TOC extraction logic
3. Fix Pass C dictionary extraction rules
4. Fix Pass D embedding error handling
5. Fix Pass E Neo4j node creation
6. Re-ingest one document from scratch to verify fixes

### Option C: Hybrid (Quick Fix + Incremental Pipeline Fixes)
**Time:** 2-3 hours now, 1-2 hours per pipeline fix
**Pros:** Unblocks immediately, fixes incrementally
**Cons:** Multiple testing cycles

**Steps:**
1. Execute database cleanup (Option A)
2. Fix one pipeline issue per day
3. Test each fix individually
4. Build confidence incrementally

---

## Conclusion

The HGRN automated system has successfully identified the data quality issues, but the cleanup requires human review due to:

1. **MongoDB:** Need to verify each term deletion is truly invalid (not a false positive)
2. **Cassandra:** Need to inspect chunks to determine which specific validation checks are failing
3. **Neo4j:** Need to verify document metadata before creating nodes
4. **Pipeline Fixes:** Require code changes and testing

**Recommended:** Start with Option C (Hybrid) - execute database cleanup for one file (Pathfinder) as a test, verify improvement, then apply to other files while working on pipeline fixes in parallel.

**Next Steps:**
1. Review this document with project stakeholders
2. Connect to databases and verify HGRN analysis
3. Approve MongoDB deletions for Pathfinder (30 terms)
4. Execute cleanup and measure Pass F score improvement
5. Decide on pipeline fix priority and timeline

---

**Prepared by:** Claude Code (Debugging Root Cause Skill)
**Generated:** October 17, 2025
**Session ID:** swarm-ingestion-fixes-manual-cleanup
**Review Status:** ⏸️ AWAITING HUMAN APPROVAL
