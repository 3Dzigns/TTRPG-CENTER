# Scripts Reference

Detailed reference for all ingestion pipeline scripts and utilities.

## Table of Contents

- [Document Splitter Tool](#document-splitter-tool)
- [Database Manager](#database-manager)
- [Complete Workflow Examples](#complete-workflow-examples)

---

## Document Splitter Tool

### doc_splitter - Document Page Range Extraction

The `doc_splitter` command is pre-installed for splitting documents by page range. It can optionally update Gate 0 marker files to track document splits (TOC and parts).

**Supported formats:**
- **PDF**: Physical pages (1-based)
- **DOCX**: Paragraph-based pages (50 paragraphs = 1 page)
- **TXT**: Line-based pages (50 lines = 1 page)

**Usage:**
```bash
doc_splitter <source> <start_page> <end_page> <destination> [options]
doc_splitter -v | --version
doc_splitter -? | --help
```

**Options:**
- `--update-marker FILE` - Update Gate 0 marker file with split info
- `--split-type TYPE` - Split type: `toc` or `part` (required with --update-marker)
- `--part-number N` - Part number (required when --split-type is `part`)

**Basic Examples:**
```bash
# Split PDF pages 1-10
docker exec n8n_TTRPG_ingestion_engine doc_splitter \
  /Transfer_Station/ingestion_inbound/manual.pdf 1 10 \
  /Transfer_Station/ingestion_processing/chapter1.pdf

# Split DOCX paragraphs 1-500 (pages 1-10 at 50 paras/page)
docker exec n8n_TTRPG_ingestion_engine doc_splitter \
  /Transfer_Station/ingestion_inbound/report.docx 1 10 \
  /Transfer_Station/ingestion_processing/section1.docx

# Check version
docker exec n8n_TTRPG_ingestion_engine doc_splitter -v
```

**Marker Integration Examples:**
```bash
# Step 1: Create Gate 0 marker
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf --quiet)

# Step 2: Split TOC and update marker
docker exec n8n_TTRPG_ingestion_engine doc_splitter \
  /Transfer_Station/sources/manual.pdf 1 8 \
  /Transfer_Station/Pass_A_Out/manual_toc.pdf \
  --update-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json \
  --split-type toc

# Step 3: Split Part 1 and update marker
docker exec n8n_TTRPG_ingestion_engine doc_splitter \
  /Transfer_Station/sources/manual.pdf 9 100 \
  /Transfer_Station/Pass_A_Out/manual_part1.pdf \
  --update-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json \
  --split-type part --part-number 1

# Step 4: Split Part 2 and update marker
docker exec n8n_TTRPG_ingestion_engine doc_splitter \
  /Transfer_Station/sources/manual.pdf 101 200 \
  /Transfer_Station/Pass_A_Out/manual_part2.pdf \
  --update-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json \
  --split-type part --part-number 2
```

**Marker File Structure After Splits:**
```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "original_filename": "Pathfinder Core Rulebook.pdf",
  "sha256_hash": "...",
  "splits": [
    {
      "type": "toc",
      "filename": "manual_toc.pdf",
      "path": "/Transfer_Station/Pass_A_Out/manual_toc.pdf",
      "pages": "1-8",
      "created_at": "2025-10-09T12:05:00Z"
    },
    {
      "type": "part",
      "part_number": 1,
      "filename": "manual_part1.pdf",
      "path": "/Transfer_Station/Pass_A_Out/manual_part1.pdf",
      "pages": "9-100",
      "created_at": "2025-10-09T12:06:00Z"
    },
    {
      "type": "part",
      "part_number": 2,
      "filename": "manual_part2.pdf",
      "path": "/Transfer_Station/Pass_A_Out/manual_part2.pdf",
      "pages": "101-200",
      "created_at": "2025-10-09T12:07:00Z"
    }
  ]
}
```

**Marker Validation:**
- Validates marker file has `document_id`, `original_filename`, and `sha256_hash` fields
- Ensures marker was created by `gate_0_hash.py`
- Creates `splits` array if not present
- Appends new split information on each call

**Output format:** `"{source_name} pages {start} to {end} extracted to {destination_name}"`

**Script location:** `/app/scripts/doc_splitter.py` (mounted from `./ingestion/`)

**Note:** For DOCX and TXT files, "pages" are logical units (50 paragraphs or 50 lines respectively), not physical pages.

---

## Database Manager

### db_manager.py - Unified Database Management

The `db_manager.py` script provides unified management for all databases (MongoDB, Cassandra, Neo4j, PostgreSQL).

**Operations:**
- `--summarize`: Display database statistics (collections, counts, schema)
- `--clear`: Delete all data from databases (with confirmation)

**Options:**
- `--db TYPE`: Target specific database (mongo|cassandra|neo4j|postgres|all)
- `--force`: Skip confirmation prompts for clear operations
- `--dry-run`: Preview clear operations without executing

**Usage:**
```bash
db_manager.py --summarize [options]
db_manager.py --clear [options]
db_manager.py -v | --version
db_manager.py -? | --help
```

**Examples:**
```bash
# Summarize all databases
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --summarize

# Summarize only MongoDB
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --summarize --db mongo

# Clear all databases (with confirmation prompt)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear

# Clear only Neo4j (skip confirmation)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear --db neo4j --force

# Preview clear operation without executing
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear --dry-run

# Clear multiple databases by running separately
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear --db mongo --force
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear --db neo4j --force
```

**Output Examples:**

**Summarize Output:**
```
Connecting to databases...
  MongoDB: Connected ✓
  Cassandra: Connected ✓
  Neo4j: Connected ✓
  PostgreSQL: Connection failed (skipping)

============================================================
MongoDB Summary
============================================================
  Database: ttrpg_ingestion
  Total Documents: 1,523

  Collections:
    - documents: 1 documents
    - elements: 1,234 documents
    - categories: 15 documents
    - terms: 273 documents

============================================================
Neo4j Summary
============================================================
  Total Nodes: 450
  Total Relationships: 823

  Node Labels:
    - Document: 5 nodes
    - Element: 200 nodes
    - Category: 15 nodes
    - Term: 230 nodes

  Relationship Types:
    - CONTAINS
    - REFERENCES
    - BELONGS_TO
```

**Clear Output:**
```
⚠️  WARNING: This will DELETE ALL DATA from the selected database(s)!
This operation CANNOT be undone.

Type 'yes' to confirm: yes

============================================================
MongoDB Clear
============================================================
  Collections: 4
  Documents to delete: 1,523
  Collections dropped: 4

============================================================
Neo4j Clear
============================================================
  Nodes to delete: 450
  Relationships to delete: 823

✓ Clear operation completed
```

**Connection Details:**
- **MongoDB**: n8n_TTRPG_mongodb:27017 (internal), localhost:9002 (external)
- **Cassandra**: n8n_TTRPG_cassandra:9042 (internal), localhost:9001 (external)
- **Neo4j**: n8n_TTRPG_neo4j:7687 (Bolt), localhost:9005 (external), auth: neo4j/password
- **PostgreSQL**: n8n_TTRPG_postgres:5432 (when deployed), localhost:5432 (external)

**Error Handling:**
- Gracefully skips databases that are unreachable or don't have drivers installed
- PostgreSQL is automatically skipped if container is not deployed
- Reports errors per database without stopping execution

**Script location:** `/app/scripts/db_manager.py` (mounted from `./ingestion/`)

---

### gate_0_validate.py - Gate 0 Chunk Count Validation

Validates that the expected chunk count (from Gate_0_Check) matches the actual count in Cassandra. Returns the difference between actual and expected counts.

**Usage:**
```bash
gate_0_validate.py <sha256_hash> [options]
gate_0_validate.py -v | --version
gate_0_validate.py -? | --help
```

**Options:**
- `--check-dir DIR` - Gate_0_Check directory (default: `/Transfer_Station/Gate_0_Check`)
- `--quiet` - Suppress output, only print difference value
- `--json` - Output as JSON

**Exit Codes:**
- `0` - Validation passed (counts match, difference = 0)
- `1` - Mismatch detected (difference != 0 and != -1)
- `2` - Unprocessed (both counts are 0, difference = -1)
- `3` - Error (connection failure, invalid input, etc.)

**Examples:**
```bash
# Basic validation
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_validate.py \
  4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0

# Quiet mode (just the difference number)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_validate.py \
  4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0 --quiet

# JSON output
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_validate.py \
  4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0 --json
```

**Output Example:**
```
============================================================
Gate 0 Validation
============================================================
SHA-256: 4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0
Document ID: cyberpunk_v3_cp4110_core_rulebook_4f81185e7057

Expected (Gate 0): 7,654 chunks
Actual (Cassandra): 7,654 chunks
Difference: 0

✓ Validation PASSED: Counts match
```

**Script location:** `/app/scripts/gate_0_validate.py` (mounted from `./ingestion/`)

---

### clear_document.py - Document-Specific Database Cleanup

Deletes all database entries for a specific document_id across all databases (MongoDB, Cassandra, Neo4j). Only affects the specified document_id.

**Usage:**
```bash
clear_document.py <document_id> [options]
clear_document.py -v | --version
clear_document.py -? | --help
```

**Options:**
- `--force` - Skip confirmation prompts
- `--dry-run` - Preview deletions without executing

**Exit Codes:**
- `0` - Deletion successful or dry-run completed
- `1` - User cancelled operation
- `2` - Connection error
- `3` - Invalid input

**Examples:**
```bash
# Delete with confirmation prompt
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/clear_document.py \
  cyberpunk_v3_cp4110_core_rulebook_4f81185e7057

# Delete without confirmation
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/clear_document.py \
  cyberpunk_v3_cp4110_core_rulebook_4f81185e7057 --force

# Preview deletions without executing
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/clear_document.py \
  cyberpunk_v3_cp4110_core_rulebook_4f81185e7057 --dry-run
```

**Output Example:**
```
Connecting to databases...
✓ All databases connected

Counting entries for document_id: cyberpunk_v3_cp4110_core_rulebook_4f81185e7057
============================================================
Document Cleanup - DRY RUN
============================================================
Document ID: cyberpunk_v3_cp4110_core_rulebook_4f81185e7057

MongoDB:
  Elements:    0
  Categories:  0
  Terms:       0
  Documents:   0
  Total:       0

Cassandra:
  Embeddings:  14,106

Neo4j:
  Nodes:         1
  Relationships: 14,106

Grand Total: 14,107 entries
============================================================

✓ Dry run completed (no deletions performed)
```

**Use Cases:**
- Clean up after failed Pass D runs
- Remove duplicate document entries
- Reset document state for reprocessing
- Resolve validation mismatches

**Script location:** `/app/scripts/clear_document.py` (mounted from `./ingestion/`)

---

### pass_f_consistency_check.py - Pass F Consistency Validation

Validates MongoDB dictionary, Cassandra metadata, and Neo4j graph consistency using HGRN (Hierarchical Graph Recurrent Network). Generates detailed remediation plans for database cleanup and pipeline improvement.

**Location:** `./ingestion/pass_f_consistency_check.py`

**Purpose:** Quality assurance pass that validates end-to-end ingestion quality using AI-powered consistency analysis.

**Usage:**
```bash
pass_f_consistency_check.py <gate0_marker> [options]
pass_f_consistency_check.py -v | --version
pass_f_consistency_check.py -? | --help
```

**Arguments:**
- `gate0_marker` - Path to Gate 0 marker file (required)

**Options:**
- `-o, --output DIR` - Output directory (default: `/Transfer_Station/Pass_F_Out`)
- `--hgrn-host HOST` - HGRN API host (default: `n8n_TTRPG_hgrn`)
- `--hgrn-port PORT` - HGRN API port (default: `8000`)
- `--threshold FLOAT` - Validation threshold 0.0-1.0 (default: `0.85`)
- `--timeout SECONDS` - HGRN API timeout (default: `300`)
- `--dry-run` - Validate inputs without execution

**Examples:**

*Basic validation:*
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/pathfinder_core_rulebook_20251009_120000.json
```

*Custom threshold and output:*
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_id.json \
  --threshold 0.90 -o /Transfer_Station/Pass_F_Out
```

*Dry run validation:*
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_id.json --dry-run
```

**Output Files:**

Manifest: `/Transfer_Station/Pass_F_Out/{document_id}_pass_f_manifest.json`
```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "pass": "pass_f",
  "timestamp": "2025-10-11T12:30:00Z",
  "inputs": {
    "gate_0_marker": "/Transfer_Station/Gate_0_Out/...",
    "pass_a_metadata": "/Transfer_Station/Pass_A_Out/...",
    "pass_c_metadata": "/Transfer_Station/Pass_C_Out/...",
    "pass_d_manifest": "/Transfer_Station/Pass_D_Out/...",
    "pass_e_manifest": "/Transfer_Station/Pass_E_Out/..."
  },
  "validation": {
    "overall_score": 0.92,
    "passed": true,
    "threshold": 0.85,
    "component_scores": {
      "mongodb": 0.92,
      "cassandra": 0.88,
      "neo4j": 0.95
    }
  },
  "remediation": {
    "mongodb_actions": 2,
    "cassandra_actions": 2,
    "neo4j_actions": 1,
    "chunk_actions": 1
  },
  "execution": {
    "duration_seconds": 45.3,
    "hgrn_version": "1.0.0"
  }
}
```

Remediation Plan: `/Transfer_Station/Pass_F_Out/{document_id}_remediation_plan.json`
```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "timestamp": "2025-10-11T12:30:00Z",
  "validation_summary": {
    "mongodb": 0.92,
    "cassandra": 0.88,
    "neo4j": 0.95
  },
  "overall_score": 0.92,
  "passed": true,
  "mongodb": {
    "score": 0.92,
    "issues": [
      "Term 'Armor Class' missing page reference on page 142",
      "Category 'equipment' has 3 uncategorized items"
    ],
    "warnings": [
      "Term frequency analysis suggests 'spell slot' may be undercounted"
    ],
    "remediation": [
      {
        "type": "dictionary_update",
        "priority": "medium",
        "description": "Add missing page reference for 'Armor Class'",
        "location": "terms collection, term_id: armor_class",
        "suggested_fix": {
          "page_references": [15, 142, 203]
        }
      }
    ]
  },
  "cassandra": {
    "score": 0.88,
    "issues": [
      "15 chunks have mismatched page_number vs element metadata"
    ],
    "remediation": [
      {
        "type": "metadata_correction",
        "priority": "high",
        "description": "Fix page_number mismatches in 15 chunks",
        "location": "embeddings table, document_id filter",
        "suggested_fix": {
          "correction_strategy": "reparse_elements"
        }
      }
    ]
  },
  "neo4j": {
    "score": 0.95,
    "issues": [
      "3 orphaned nodes (no incoming or outgoing edges)"
    ],
    "remediation": [
      {
        "type": "graph_cleanup",
        "priority": "medium",
        "description": "Connect or remove 3 orphaned nodes",
        "suggested_fix": {
          "strategy": "find_semantic_relationships"
        }
      }
    ]
  },
  "chunks": {
    "remediation": [
      {
        "type": "reprocess_recommendation",
        "priority": "low",
        "description": "Consider reprocessing chunks with metadata inconsistencies",
        "location": "Pass C output, chunks 142-156",
        "suggested_fix": {
          "passes_to_rerun": ["pass_c_parsing", "pass_c_metadata"]
        }
      }
    ]
  }
}
```

**Output Summary (Console):**
```
============================================================
Pass F: Consistency Validation Complete
============================================================
Document ID: pathfinder_core_rulebook_20251009_120000

Validation Scores:
  MongoDB:   0.920
  Cassandra: 0.880
  Neo4j:     0.950
  Overall:   0.917

Status: ✓ PASSED

Issues:   5
Warnings: 1

Remediation Actions: 6
  MongoDB:   2
  Cassandra: 2
  Neo4j:     1
  Chunks:    1

Output Files:
  Manifest:      pathfinder_core_rulebook_20251009_120000_pass_f_manifest.json
  Remediation:   pathfinder_core_rulebook_20251009_120000_remediation_plan.json
============================================================
```

**Exit Codes:**
- `0` - Validation successful and passed threshold
- `1` - Validation successful but failed threshold
- `2` - HGRN connection or API error
- `3` - Invalid input or configuration

**Validation Components:**

*MongoDB Dictionary:*
- Term accuracy and completeness
- Page reference quality
- Category assignments
- Dictionary structure

*Cassandra Metadata:*
- Field consistency (page_number, game_system, publisher)
- Metadata completeness
- Field standardization
- Data quality

*Neo4j Graph:*
- Graph structure integrity
- Relationship coherence
- Orphaned node detection
- Edge quality analysis

*Chunk Reprocessing:*
- Identifies chunks requiring reprocessing
- **NO vector change recommendations** (vectors are ground truth)
- Focuses on metadata and dictionary corrections

**Dependencies:**
- HGRN container must be running (`docker compose up -d hgrn`)
- GPU access required for HGRN (NVIDIA GPU with CUDA support)
- Gate 0 marker file must exist
- Pass A-E artifacts auto-discovered (optional but recommended)

**Integration Notes:**
- Run after Pass E (knowledge graph construction)
- Use remediation plan for manual database cleanup
- Store remediation plans for pipeline improvement analysis
- Exit code 0 indicates validation passed threshold
- Exit code 1 indicates validation completed but quality below threshold

**Script location:** `/app/scripts/pass_f_consistency_check.py` (mounted from `./ingestion/`)

---

## Complete Workflow Examples

### Full Pipeline: Gate 0 → Pass A → MongoDB

```bash
# Step 1: Gate 0 validation
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf --quiet)

# Step 2: Check if document_id exists (prevent duplicates)
if [ -f "/Transfer_Station/Gate_0_Out/${DOC_ID}.json" ]; then
  echo "Document already processed: $DOC_ID"
  exit 0
fi

# Step 3: Extract TOC from document
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only /Transfer_Station/sources/manual.pdf

# Step 4: Generate metadata from TOC
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_metadata.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json

# Step 5: Upsert to MongoDB
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json
```

### Complete Pass B → Pass D Pipeline

```bash
# Pass B creates manifest with parts
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_b_splitter.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json \
  -o /Transfer_Station/Pass_B_Out

# Pass C processes each part (done separately via n8n workflow)
# ... creates part01_elements.json, part02_elements.json, etc.

# Pass C metadata extraction
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_metadata.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json \
  --gate-marker /Transfer_Station/Gate_0_Out/document_20251009_120000.json

# Pass C MongoDB upsert
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_mongo_upsert.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json

# Pass D processes all parts in single call
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json --create-schema
```

### Complete Pass E: Knowledge Graph

```bash
# Build graph artifacts
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_e_graph_builder.py \
  /Transfer_Station/Pass_D_Out/document_pass_d_manifest.json --enable-similarity

# Upsert to Neo4j
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_e_neo4j_upsert.py \
  /Transfer_Station/Pass_E_Out/document_graph.json --create-indexes
```

### Quick TOC Extraction Workflow

```bash
# Fast TOC extraction for quick metadata generation (~30 seconds total)
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/pathfinder_core.pdf --quiet)

docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only /Transfer_Station/sources/pathfinder_core.pdf

docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_metadata.py \
  /Transfer_Station/Pass_A_Out/pathfinder_core_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json

docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/pathfinder_core_toc_elements.json \
  /Transfer_Station/Pass_A_Out/pathfinder_core_metadata.json

echo "✓ TOC processing complete for document: $DOC_ID"
```
