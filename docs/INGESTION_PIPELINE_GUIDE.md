# TTRPG Document Ingestion Pipeline - Comprehensive User Guide

**Version:** 2.1.0
**Last Updated:** 2025-10-11
**Audience:** Data Engineers, ML Engineers, DevOps, System Administrators

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture & Design Principles](#architecture--design-principles)
3. [Pipeline Stages Deep Dive](#pipeline-stages-deep-dive)
4. [Complete Workflow Examples](#complete-workflow-examples)
5. [Configuration Management](#configuration-management)
6. [Error Handling & Troubleshooting](#error-handling--troubleshooting)
7. [Performance Optimization](#performance-optimization)
8. [Security & Best Practices](#security--best-practices)
9. [Monitoring & Validation](#monitoring--validation)
10. [Advanced Topics](#advanced-topics)

---

## Overview

### What is the TTRPG Ingestion Pipeline?

The TTRPG Document Ingestion Pipeline is a **multi-stage ETL system** designed to transform tabletop RPG rulebooks (PDF/DOCX/TXT) into searchable, queryable knowledge graphs with semantic understanding. The pipeline extracts structured metadata, generates vector embeddings, builds knowledge graphs, and validates data consistency across three database backends.

### Key Capabilities

- ✅ **Document Validation**: SHA-256 hashing with integrity verification
- ✅ **Intelligent Parsing**: OCR-based extraction with structure recognition
- ✅ **Metadata Extraction**: Hierarchical TOC, categories, and term indexing
- ✅ **Smart Chunking**: Character-based chunking (500-600 chars) for semantic search
- ✅ **Vector Embeddings**: OpenAI text-embedding-3-small (1536 dimensions)
- ✅ **Knowledge Graphs**: Neo4j graph construction with relationship mapping
- ✅ **Multi-DB Validation**: MongoDB, Cassandra, Neo4j consistency checking
- ✅ **Source Validation**: Token-based content verification against original documents

### System Requirements

**Docker Stack:**
- Docker Engine 24.0+
- Docker Compose 2.20+
- 16GB RAM minimum (32GB recommended for large documents)
- 50GB disk space for databases
- NVIDIA GPU (optional, for HGRN acceleration)

**External Services:**
- OpenAI API key (for embeddings)
- Unstructured.io API access

**Supported Document Formats:**
- PDF (preferred, with OCR support)
- DOCX (paragraph-based processing)
- TXT (line-based processing)

---

## Architecture & Design Principles

### Transfer Station Pattern

The **Transfer Station** is a shared filesystem volume (`E:/n8n_TTRPG_Transfer_Station`) mounted into all containers. This eliminates network dependencies and provides clear audit trails.

**Directory Structure:**
```
E:/n8n_TTRPG_Transfer_Station/
├── sources/              # Original source documents (read-only)
├── Gate_0_Out/           # SHA-256 validation markers
├── Gate_0_Check/         # Checksum verification files
├── Pass_A_Out/           # TOC extraction results
├── Pass_B_Out/           # Document split manifests
├── Pass_C_Out/           # Full document elements
├── Pass_D_Out/           # Embedding manifests
├── Pass_E_Out/           # Graph construction results
├── Pass_F_Out/           # Validation reports
│   └── hgrn_output/      # HGRN remediation bundles
└── n8n_inbound/          # n8n workflow inputs
```

**Key Principles:**
- **Immutability**: Source documents never modified
- **Traceability**: Every stage produces versioned artifacts
- **Idempotency**: Re-running stages with same input produces same output
- **Isolation**: Each service only accesses its designated directories

### Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Source Document                          │
│                     (PDF, DOCX, TXT)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Gate 0: File Validation                                         │
│ ├─ SHA-256 hash computation                                     │
│ ├─ Document ID generation (filename + timestamp)                │
│ └─ Marker file creation (Gate_0_Out/<document_id>.json)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pass A: TOC Extraction (Fast - 10-20 seconds)                  │
│ ├─ Unstructured.io API: OCR + structure detection              │
│ ├─ TOC-only mode: first 8 pages                                │
│ ├─ Metadata extraction: categories, terms, hierarchies         │
│ └─ MongoDB upsert: documents, elements, terms collections      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pass B: Document Splitting (Logical Parts)                     │
│ ├─ TOC-based section grouping                                  │
│ ├─ 10-20 page parts (configurable)                             │
│ ├─ Manifest creation: part boundaries                          │
│ └─ Physical file splits: <document_id>_part##.pdf              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pass C: Full Document Processing (Slow - ~2 min/200 pages)     │
│ ├─ Unstructured.io API: hi_res OCR for all parts               │
│ ├─ Auto-discovery: reads Pass B manifest                       │
│ ├─ Metadata consolidation: all parts → unified dictionary      │
│ └─ MongoDB upsert: comprehensive elements + metadata           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pass D: Vector Embedding Generation                            │
│ ├─ Character-based chunking: 500-600 chars, 50 overlap         │
│ ├─ OpenAI API: text-embedding-3-small (1536 dims)              │
│ ├─ Batch processing: 100 chunks/batch                          │
│ ├─ Cassandra storage: embeddings table                         │
│ └─ Cost tracking: ~$0.020 per 1M tokens                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pass E: Knowledge Graph Construction                           │
│ ├─ Vector retrieval: Cassandra embeddings                      │
│ ├─ Node creation: Document, Element, Term, Category            │
│ ├─ Relationship mapping: CONTAINS, REFERENCES, BELONGS_TO      │
│ ├─ Optional: SIMILAR_TO edges (cosine similarity > 0.82)       │
│ └─ Neo4j upsert: batch MERGE with indexing                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Pass F: Consistency Validation (NEW in v2.1.0)                 │
│ ├─ MongoDB validation: term sources, category membership       │
│ ├─ Cassandra validation: chunk counts, embedding dimensions    │
│ ├─ Neo4j validation: orphan detection, cycle detection         │
│ ├─ Source validation: token-based content matching             │
│ ├─ TOC validation: entries exist on declared pages             │
│ ├─ Term validation: terms exist in source document             │
│ ├─ Remediation plans: actionable database fixes (JSON)         │
│ └─ HGRN outputs: machine (JSON) + human (Markdown)             │
└─────────────────────────────────────────────────────────────────┘
```

### Database Architecture

**MongoDB (Port 9002):**
- **Purpose**: Document storage, metadata, terms, categories
- **Collections**: `documents`, `elements`, `terms`, `categories`
- **Schema**: Flexible document store with compound indexes
- **Access Pattern**: Direct queries, bulk upserts

**Cassandra (Port 9001):**
- **Purpose**: Vector embeddings for semantic search
- **Keyspace**: `ttrpg_vectors`
- **Table**: `embeddings` (partitioned by document_id)
- **Schema**: Wide-column store with embedding vectors (list<float>)
- **Access Pattern**: Range scans, batch inserts, vector similarity

**Neo4j (Ports 9003, 9005):**
- **Purpose**: Knowledge graph, relationships, graph queries
- **Labels**: `Document`, `Element`, `Term`, `Category`, `Chunk`
- **Relationships**: `CONTAINS`, `REFERENCES`, `BELONGS_TO`, `SIMILAR_TO`
- **Access Pattern**: Cypher queries, graph traversals, pattern matching

---

## Pipeline Stages Deep Dive

### Gate 0: File Validation

**Script:** `gate_0_hash.py`
**Purpose:** Create authoritative document identifiers with SHA-256 integrity verification

#### What It Does

1. **Computes SHA-256 Hash**: Efficient chunked reading (64KB blocks)
2. **Generates Document ID**: Sanitized filename + timestamp (UTC)
3. **Creates Marker File**: JSON metadata in `Gate_0_Out/`

#### Document ID Format

```
Pattern: <sanitized_filename>_<timestamp>
Example: pathfinder_core_rulebook_20251009_120000

Sanitization Rules:
- Lowercase conversion
- Special chars → underscores
- Multiple underscores → single
- 100 char limit (before timestamp)
```

#### Usage Examples

**Basic Validation:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf
```

**Output:**
```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "original_filename": "Pathfinder Core Rulebook.pdf",
  "original_path": "/Transfer_Station/sources/Pathfinder Core Rulebook.pdf",
  "file_size_bytes": 98535290,
  "sha256_hash": "4f4b1d9d2b6ca812ab4fb5a38727ff7922c41cbfe4e4e214511249ce134a8cb5",
  "computed_at": "2025-10-09T12:00:00.000000Z"
}
```

**Quiet Mode (for Scripting):**
```bash
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf --quiet)
echo "Document ID: $DOC_ID"
```

**Custom Output Directory:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf -o /Transfer_Station/custom_gate
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output DIR` | Output directory | `/Transfer_Station/Gate_0_Out` |
| `-q, --quiet` | Suppress output, print document_id only | Off |
| `-v, --version` | Show version | - |
| `-?, --help` | Show help | - |

#### Error Handling

```python
# File not found
if not input_path.exists():
    print(f"Error: File not found: {input_path}")
    sys.exit(1)

# Unreadable file
try:
    hash_result = compute_hash(input_path)
except PermissionError:
    print(f"Error: Permission denied: {input_path}")
    sys.exit(1)
except Exception as e:
    print(f"Error: Failed to compute hash: {e}")
    sys.exit(1)
```

#### Integration Pattern

```bash
# Step 1: Validate document
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf --quiet)

# Step 2: Check for duplicates
MARKER_FILE="/Transfer_Station/Gate_0_Out/${DOC_ID}.json"
if docker exec n8n_TTRPG_ingestion_engine test -f "$MARKER_FILE"; then
  echo "Document already processed: $DOC_ID"
  exit 0
fi

# Step 3: Continue to Pass A with document_id
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  /Transfer_Station/sources/manual.pdf
```

---

### Pass A: TOC Extraction and Metadata

**Scripts:** `pass_a_unstructured.py`, `pass_a_metadata.py`, `pass_a_mongo_upsert.py`
**Purpose:** Extract table of contents, build hierarchical structure, create term dictionary

#### Pass A.1: Document Element Extraction

**Script:** `pass_a_unstructured.py`
**Processing Time:** 10-20 seconds (TOC-only), ~2 minutes (full document)

##### What It Does

1. **API Call**: Unstructured.io OCR + layout detection
2. **Element Extraction**: Title, Text, Table, List, Image metadata
3. **TOC-Only Mode**: Fast extraction (first 8 pages only)
4. **Full Mode**: Comprehensive extraction (all pages, hi_res OCR)

##### Processing Strategies

| Strategy | Speed | Quality | Use Case |
|----------|-------|---------|----------|
| `toc_pages` | Fast (10-20s) | Good | TOC extraction only |
| `hi_res` | Slow (~2 min/200p) | Excellent | Full document |
| `fast` | Fast | Poor | No OCR, basic text only |

##### Usage Examples

**TOC-Only Extraction (Recommended for Pass A):**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only /Transfer_Station/sources/manual.pdf
```

**Full Document Extraction:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  /Transfer_Station/sources/manual.pdf
```

**Spanish OCR:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only -l spa /Transfer_Station/sources/libro.pdf
```

**Custom Page Limit:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only --max-pages 12 /Transfer_Station/sources/manual.pdf
```

##### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output DIR` | Output directory | `/Transfer_Station/Pass_A_Out` |
| `-l, --language LNG` | OCR language code | `eng` |
| `-t, --toc-only` | Extract TOC only (fast) | Off |
| `-s, --strategy STR` | Processing strategy | `hi_res` |
| `-m, --max-pages N` | Max pages for TOC | `8` |

##### Output Files

```
/Transfer_Station/Pass_A_Out/
├── manual_toc_elements.json      # TOC-only mode
└── manual_elements.json          # Full document mode
```

#### Pass A.2: Metadata Extraction

**Script:** `pass_a_metadata.py`
**Processing Time:** <5 seconds

##### What It Does

1. **TOC Structure**: Hierarchical section tree with page ranges
2. **Category Detection**: Character creation, combat, magic, etc.
3. **Term Indexing**: Extracted terms with page references
4. **System Detection**: Auto-detect PF1E, PF2E, DND5E, etc.
5. **Gate 0 Integration**: Link metadata to source document

##### Gate 0 Integration (Recommended)

**Why Use --gate-marker?**
- Links all terms to authoritative `document_id`
- Preserves source file SHA-256 hash
- Tracks document splits (TOC, parts)
- Enables Pass F source validation

**Usage:**
```bash
# With Gate 0 integration (recommended)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_metadata.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/manual_20251009_120000.json
```

**Without Gate 0 (legacy mode):**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_metadata.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json
```

##### Metadata Structure (with Gate 0)

```json
{
  "document": {
    "document_id": "pathfinder_core_rulebook_20251009_120000",
    "original_filename": "Pathfinder Core Rulebook.pdf",
    "sha256_hash": "4f4b1d9d...",
    "file_size_bytes": 98535290
  },
  "extraction": {
    "system": "PF2E",
    "publisher": "Paizo",
    "extraction_date": "2025-10-09T15:30:00Z"
  },
  "toc_structure": [
    {
      "level": 1,
      "title": "CHAPTER 1: CLASSES",
      "page_start": 15,
      "page_end": 68,
      "category": "character_creation"
    }
  ],
  "categories": {
    "character_creation": ["Fighter", "Wizard", "Rogue"],
    "combat": ["Weapons", "Armor", "Actions"],
    "magic": ["Spells", "Rituals"]
  },
  "terms": [
    {
      "term": "Armor Class",
      "category": "combat",
      "page_references": [15, 142, 203],
      "document_id": "pathfinder_core_rulebook_20251009_120000"
    }
  ],
  "statistics": {
    "total_toc_entries": 127,
    "unique_categories": 7,
    "unique_terms": 243
  }
}
```

##### Detected Categories

| Category | Examples |
|----------|----------|
| `character_creation` | Races, classes, backgrounds, abilities |
| `combat` | Weapons, armor, actions, initiative |
| `magic` | Spells, rituals, casting, spell slots |
| `equipment` | Gear, items, treasure, magical items |
| `rules` | Mechanics, gameplay, conditions, checks |
| `setting` | World, lore, history, factions |
| `game_master` | GM/DM guidance, encounters, adventures |

##### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output DIR` | Output directory | Same as input |
| `-s, --system STR` | Game system | `auto` |
| `-p, --publisher STR` | Publisher name | Auto-detect |
| `--gate-marker FILE` | Gate 0 marker file | None |

#### Pass A.3: MongoDB Upsert

**Script:** `pass_a_mongo_upsert.py`
**Processing Time:** 1-3 seconds

##### What It Does

1. **Change Detection**: SHA-256 content hashing for efficient comparison
2. **Bulk Operations**: Batch inserts/updates for performance
3. **Version Tracking**: Timestamps for created_at, updated_at
4. **Detailed Reporting**: Adds, modifications, deletions

##### Usage Examples

**Standard Upsert:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json
```

**Dry Run (Preview Changes):**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json \
  --dry-run
```

**External MongoDB:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json \
  --host localhost --port 9002
```

##### MongoDB Collections

| Collection | Purpose | Indexes |
|------------|---------|---------|
| `documents` | Document metadata, system info | `document_id` (unique) |
| `elements` | Individual TOC elements | `document_id`, `element_id` |
| `categories` | Category hierarchy | `document_id`, `category` |
| `terms` | Term index with page refs | `document_id`, `term` |

##### Output Report

```
MongoDB Upsert Report
============================================================
Document: pathfinder_core_rulebook_20251009_120000
Database: ttrpg_ingestion
Timestamp: 2025-10-09T15:30:00Z

Elements:
  Added: 127
  Modified: 12
  Deleted: 5
  Unchanged: 78
  Total: 222

Categories:
  Added: 15
  Modified: 3
  Deleted: 0
  Total: 18

Terms:
  Added: 243
  Modified: 8
  Deleted: 2
  Total: 253

Execution Time: 1.23s
```

##### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--host HOST` | MongoDB host | `n8n_TTRPG_mongodb` |
| `--port PORT` | MongoDB port | `27017` |
| `--db NAME` | Database name | `ttrpg_ingestion` |
| `--dry-run` | Preview changes without applying | Off |

---

### Pass B: Document Splitting

**Script:** `pass_b_splitter.py`
**Purpose:** Split large documents into logical parts for distributed processing

#### What It Does

1. **TOC Analysis**: Read Pass A metadata for section boundaries
2. **Part Planning**: Group sections into 10-20 page parts
3. **Manifest Creation**: JSON manifest with part boundaries
4. **Physical Splitting**: Create PDF/DOCX/TXT part files

#### Usage Examples

**Basic Splitting (10-20 pages per part):**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_b_splitter.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json
```

**Custom Page Range:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_b_splitter.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json \
  --min-pages 5 --max-pages 15
```

#### Manifest Structure

```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "parts": [
    {
      "part": 1,
      "filename": "pathfinder_core_rulebook_20251009_120000_part01.pdf",
      "page_start": 9,
      "page_end": 28,
      "page_count": 20
    },
    {
      "part": 2,
      "filename": "pathfinder_core_rulebook_20251009_120000_part02.pdf",
      "page_start": 29,
      "page_end": 48,
      "page_count": 20
    }
  ],
  "total_parts": 16,
  "timestamp": "2025-10-09T12:10:00Z"
}
```

#### Output Files

```
/Transfer_Station/Pass_B_Out/
├── {document_id}_pass_b_manifest.json
├── {document_id}_part01.pdf
├── {document_id}_part02.pdf
└── {document_id}_part##.pdf
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output DIR` | Output directory | `/Transfer_Station/Pass_B_Out` |
| `--min-pages N` | Min pages per part | `10` |
| `--max-pages N` | Max pages per part | `20` |

---

### Pass C: Full Document Processing

**Scripts:** `pass_c_metadata.py`, `pass_c_mongo_upsert.py`
**Purpose:** Process all document parts for comprehensive metadata and storage

#### Pass C.1: Full Metadata Extraction

**Script:** `pass_c_metadata.py`
**Processing Time:** <10 seconds

##### What It Does

1. **Auto-Discovery**: Reads Pass B manifest and discovers all Pass C element files
2. **Metadata Consolidation**: Combines metadata from all parts
3. **Category Aggregation**: Unified category dictionary
4. **Term Consolidation**: Combined term index with page references
5. **Gate 0 Integration**: Links to source document

##### Usage Examples

**With Gate 0 Integration:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_metadata.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json \
  --gate-marker /Transfer_Station/Gate_0_Out/document_20251009_120000.json
```

**Specify System Explicitly:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_metadata.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json \
  --system PF2E --publisher "Paizo Publishing"
```

##### Output Structure

```json
{
  "document": {
    "document_id": "pathfinder_core_rulebook_20251009_120000",
    "original_filename": "Pathfinder Core Rulebook.pdf",
    "sha256_hash": "..."
  },
  "extraction": {
    "system": "PF2E",
    "publisher": "Paizo Publishing",
    "extraction_date": "2025-10-09T15:30:00Z"
  },
  "categories": {
    "character_creation": [...],
    "combat": [...],
    "magic": [...]
  },
  "terms": [
    {
      "term": "Armor Class",
      "category": "combat",
      "page_references": [15, 142, 203],
      "document_id": "pathfinder_core_rulebook_20251009_120000"
    }
  ],
  "statistics": {
    "total_elements": 5234,
    "unique_categories": 7,
    "unique_terms": 458
  }
}
```

#### Pass C.2: MongoDB Full Document Upsert

**Script:** `pass_c_mongo_upsert.py`
**Processing Time:** 5-10 seconds

##### What It Does

1. **Auto-Discovery**: Discovers all element files from Pass B manifest
2. **Bulk Operations**: Efficient batch inserts/updates
3. **Change Tracking**: Detailed add/modify/delete reporting
4. **Version Management**: Timestamp tracking

##### Usage Examples

**Standard Upsert:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_mongo_upsert.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json
```

**Dry Run:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_mongo_upsert.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json --dry-run
```

##### Output Report

```
MongoDB Upsert Report
============================================================
Document: pathfinder_core_rulebook_20251009_120000
Database: ttrpg_ingestion

Elements:
  Added: 4523
  Modified: 127
  Unchanged: 584
  Total: 5234

Categories:
  Added: 7
  Modified: 0
  Total: 7

Terms:
  Added: 458
  Modified: 12
  Total: 470

Execution Time: 7.89s
```

---

### Pass D: Vector Embedding Generation

**Script:** `pass_d_hayhooks.py`
**Purpose:** Generate OpenAI embeddings and store in Cassandra for semantic search

#### What It Does

1. **Auto-Discovery**: Reads Pass B manifest and discovers Pass C element files
2. **Character-Based Chunking**: 500-600 character chunks with 50-char overlap
3. **Batch Embedding**: OpenAI API calls with 100 chunks/batch
4. **Metadata Integration**: Includes game_system, publisher from Pass C
5. **Cassandra Storage**: Vector embeddings with metadata
6. **Cost Tracking**: Estimated OpenAI API costs

#### Character-Based Chunking Strategy

**Why Character-Based?**
- Fine-grained semantic search precision
- Context continuity with overlap
- Optimal for short-form content (rules, abilities)

**Configuration:**
```ini
min_chunk_chars = 500   # Minimum characters per chunk
max_chunk_chars = 600   # Maximum characters per chunk
chunk_overlap = 50      # Overlap between consecutive chunks
```

**Example Chunking:**
```
Original Text (800 chars):
"The Fighter class is a versatile warrior... [800 characters]"

Chunks:
1. "The Fighter class is a versatile warrior... [550 chars]"
2. "...versatile warrior adept at both offense... [550 chars]" (50 char overlap)
```

#### OpenAI Embedding Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| Model | `text-embedding-3-small` | 1536 dimensions |
| Cost | ~$0.020 per 1M tokens | ~$0.009 per 200-page doc |
| Batch Size | 100 chunks | Configurable |
| Rate Limit | 0.1s delay between batches | Prevents throttling |

#### Usage Examples

**Basic Processing:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json --create-schema
```

**Custom Chunk Sizes:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/manifest.json \
  --min-chunk-chars 800 --max-chunk-chars 1000 --chunk-overlap 100
```

**Dry Run Validation:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/manifest.json --dry-run
```

#### Cassandra Schema

```cql
CREATE KEYSPACE IF NOT EXISTS ttrpg_vectors
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE ttrpg_vectors.embeddings (
  document_id text,
  element_id text,
  chunk_index int,
  sub_chunk int,
  source_part int,
  text_content text,
  embedding list<float>,       -- 1536 dimensions
  element_type text,
  page_number text,
  filename text,
  game_system text,             -- From Pass C metadata
  publisher text,               -- From Pass C metadata
  category text,
  embedding_model text,
  created_at timestamp,
  PRIMARY KEY ((document_id), element_id, chunk_index)
);
```

#### Manifest Output

```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "processing": {
    "parts_discovered": 16,
    "parts_processed": 16,
    "total_chunks": 5234,
    "embedded_chunks": 5234,
    "failed_chunks": 0,
    "total_tokens": 456789,
    "estimated_cost_usd": 0.0091,
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536
  },
  "cassandra": {
    "host": "n8n_TTRPG_cassandra",
    "port": 9042,
    "keyspace": "ttrpg_vectors",
    "table": "embeddings",
    "rows_inserted": 5234
  },
  "metadata": {
    "game_system": "PF2E",
    "publisher": "Paizo Publishing"
  }
}
```

#### Environment Configuration

**Required:** OpenAI API key in `.env` file at project root:
```bash
# .env file
OPENAI_API_KEY=sk-proj-...
```

**IMPORTANT:** Never commit `.env` to version control (gitignored).

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output DIR` | Output directory | `/Transfer_Station/Pass_D_Out` |
| `--pass-c-dir DIR` | Pass C directory | `/Transfer_Station/Pass_C_Out` |
| `--host HOST` | Cassandra host | `n8n_TTRPG_cassandra` |
| `--port PORT` | Cassandra port | `9042` |
| `--keyspace NAME` | Keyspace | `ttrpg_vectors` |
| `--model NAME` | Embedding model | `text-embedding-3-small` |
| `--min-chunk-chars N` | Min chunk size | `500` |
| `--max-chunk-chars N` | Max chunk size | `600` |
| `--chunk-overlap N` | Overlap size | `50` |
| `--batch-size N` | Batch size | `100` |
| `--create-schema` | Create schema if not exists | Off |
| `--dry-run` | Validate without processing | Off |

---

### Pass E: Knowledge Graph Construction

**Scripts:** `pass_e_graph_builder.py`, `pass_e_neo4j_upsert.py`
**Purpose:** Build Neo4j knowledge graph from vectors and metadata

#### Pass E.1: Graph Artifact Builder

**Script:** `pass_e_graph_builder.py`

##### What It Does

1. **Vector Retrieval**: Fetch embeddings from Cassandra
2. **Node Creation**: Document, Element, Term, Category, Chunk nodes
3. **Relationship Mapping**: CONTAINS, REFERENCES, BELONGS_TO edges
4. **Similarity Calculation**: Optional SIMILAR_TO edges (cosine > 0.82)
5. **Artifact Generation**: JSON graph structure for Neo4j upsert

##### Usage Examples

**Basic Graph Building:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_e_graph_builder.py \
  /Transfer_Station/Pass_D_Out/document_pass_d_manifest.json
```

**With Similarity Edges:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_e_graph_builder.py \
  /Transfer_Station/Pass_D_Out/document_pass_d_manifest.json \
  --enable-similarity
```

##### Output Files

```
/Transfer_Station/Pass_E_Out/
├── {document_id}_vectors.json            # Cassandra vectors
├── {document_id}_graph.json              # Neo4j graph structure
└── {document_id}_pass_e_intermediate.json  # Processing metadata
```

#### Pass E.2: Neo4j Graph Upsert

**Script:** `pass_e_neo4j_upsert.py`

##### What It Does

1. **Batch MERGE**: Efficient node and relationship creation
2. **Index Creation**: Performance indexes on key properties
3. **Change Tracking**: Nodes/edges added, modified, unchanged
4. **Credential Management**: Loads from `.env` file

##### Usage Examples

**Basic Upsert:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_e_neo4j_upsert.py \
  /Transfer_Station/Pass_E_Out/document_graph.json --create-indexes
```

**Custom Credentials:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_e_neo4j_upsert.py \
  /Transfer_Station/Pass_E_Out/document_graph.json \
  --user neo4j --password mypassword
```

##### Neo4j Schema

**Node Labels:**
- `Document` - Source document metadata
- `Element` - Individual content elements
- `Term` - Dictionary terms
- `Category` - Content categories
- `Chunk` - Text chunks with embeddings

**Relationships:**
- `CONTAINS` - Document contains Elements
- `REFERENCES` - Element references Terms
- `BELONGS_TO` - Term belongs to Category
- `SIMILAR_TO` - Chunks with high semantic similarity

##### Output Manifest

```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "neo4j": {
    "url": "bolt://n8n_TTRPG_neo4j:7687",
    "nodes_added": 1250,
    "nodes_modified": 45,
    "edges_added": 3420,
    "edges_modified": 12,
    "indexes_created": 5
  },
  "timing": {
    "node_upsert_seconds": 12.34,
    "edge_upsert_seconds": 23.45,
    "index_creation_seconds": 5.67,
    "total_seconds": 41.46
  }
}
```

#### Configuration

**ingestion.cfg:**
```ini
[Pass_E]
cassandra_host = n8n_TTRPG_cassandra
cassandra_port = 9042
cassandra_keyspace = ttrpg_vectors

neo4j_host = n8n_TTRPG_neo4j
neo4j_port = 7687
neo4j_database = neo4j

enable_similarity = false
similarity_threshold = 0.82
similarity_top_k = 5
```

---

### Pass F: Consistency Validation

**Script:** `pass_f_consistency_check.py` (v2.1.0)
**Purpose:** Validate multi-database consistency and source document accuracy

#### What It Does (v2.1.0 NEW Features)

1. **MongoDB Validation**: Term sources, category membership, document metadata
2. **Cassandra Validation**: Chunk counts, embedding dimensions, content matching
3. **Neo4j Validation**: Orphan detection, cycle detection, similarity degree caps
4. **Source Validation**: Token-based matching against original document
5. **TOC Validation**: Verify TOC entries exist on declared pages
6. **Term Validation**: Verify extracted terms exist in source document
7. **Remediation Plans**: Actionable database fixes (JSON)
8. **HGRN Outputs**: Machine-readable (JSON) + human-readable (Markdown)

#### Token-Based Source Validation (NEW in v2.1.0)

**What It Does:**
- Extracts 4+ character alphanumeric tokens from source pages
- Builds inverted index: token → page numbers (O(1) lookup)
- Validates TOC entries exist on their declared pages
- Validates terms exist in source document
- Validates Cassandra chunk text matches source pages

**Token Configuration:**
```python
SOURCE_TOKEN_PATTERN = re.compile(r"[a-z0-9]{4,}")  # 4+ char tokens
SOURCE_TOKEN_PAGE_LIMIT = 256          # Max tokens indexed per page
SOURCE_TOKEN_MIN_MATCH = 3             # Min token overlap for validation
SOURCE_TOKEN_SAMPLE_LIMIT = 8          # Token sample in evidence
```

**Inverted Index Structure:**
```python
source_token_index = {
    'armor': {1, 5, 12, 15, 23},  # Pages containing 'armor'
    'spell': {3, 8, 14, 19},       # Pages containing 'spell'
    'damage': {2, 7, 11, 16},      # Pages containing 'damage'
}
```

**Performance:**
- Indexing Time: ~1-2 seconds (200 pages)
- Memory Usage: ~50KB/200 pages
- Lookup Complexity: O(1) per token
- Total Overhead: ~10-20 seconds

#### Usage Examples

**Basic Validation (No Source):**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json
```

**With Source Validation (Recommended):**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json \
  --source-file /Transfer_Station/sources/document.pdf
```

**Custom Threshold:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json \
  --threshold 0.85
```

**With HGRN Output Directory:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json \
  --source-file /Transfer_Station/sources/document.pdf \
  --hgrn-output /Transfer_Station/Pass_F_Out/hgrn_output
```

#### Validation Checks

**MongoDB Checks:**
- ✅ Term sources exist and are valid
- ✅ Category membership is correct
- ✅ Document metadata is consistent
- ✅ Page references are within document bounds

**Cassandra Checks:**
- ✅ Chunk count matches expected (±5% tolerance)
- ✅ Embedding dimensions are correct (1536)
- ✅ Metadata fields populated (game_system, publisher)
- ✅ **NEW:** Text content matches source pages (token overlap)

**Neo4j Checks:**
- ✅ No orphan chunks (all chunks connected to Document)
- ✅ No cycles in PART_OF relationships
- ✅ Similarity degree cap enforced (max 12 edges)
- ✅ **NEW:** Chunk nodes exist (count > 0)

**Source Validation Checks (NEW in v2.1.0):**
- ✅ TOC entries exist on declared pages
- ✅ Terms exist in source document
- ✅ Cassandra chunk text matches source pages
- ✅ Page references are accurate

#### HGRN Output Structure (NEW in v2.1.0)

**Directory Structure:**
```
/Transfer_Station/Pass_F_Out/hgrn_output/
└── {document_id}/
    ├── hgrn_db_remediations.json      # Machine-readable
    └── hgrn_pipeline_suggestions.md   # Human-readable
```

**hgrn_db_remediations.json:**
```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "source_file": "/Transfer_Station/sources/pathfinder.pdf",
  "source_file_sha256": "4f4b1d9d...",
  "overall_score": 0.89,
  "issues_found": 23,
  "mongodb": [
    {
      "type": "TermMissingSource",
      "term": "Armor Penetration",
      "suggested_action": {
        "rationale": "Term missing sources field",
        "dry_run": true,
        "update": {
          "collection": "terms",
          "operation": "updateOne",
          "filter": {"document_id": "...", "term": "Armor Penetration"},
          "update": {"$set": {"sources": []}}
        }
      }
    }
  ],
  "cassandra": [
    {
      "type": "ChunkContentMismatch",
      "chunk_id": "elem_123:5",
      "page": 15,
      "token_sample": ["armor", "class", "bonus", "defense"],
      "suggested_action": {
        "rationale": "Chunk text not found on source page 15",
        "dry_run": true,
        "update": {
          "statement": "-- Review chunk extraction for elem_123:5"
        }
      }
    }
  ],
  "neo4j": [
    {
      "type": "OrphanChunk",
      "chunk_id": "chunk_456",
      "suggested_action": {
        "rationale": "Chunk not connected to any Document",
        "dry_run": true,
        "update": {
          "statement": "MATCH (c:Chunk {chunk_id: 'chunk_456'}) DELETE c"
        }
      }
    }
  ],
  "source_analysis": [
    {
      "type": "toc_missing",
      "title": "Chapter 3: Spells",
      "page": 42,
      "token_sample": ["chapter", "spells", "magic", "casting"]
    }
  ],
  "pipeline_suggestions": [
    "Pass A: TOC entry 'Chapter 3: Spells' was not located on page 42.",
    "Pass C: Chunk elem_123:5 text was not located on source page 15.",
    "Pass C: Review dictionary extraction rules for term 'Armor Penetration'."
  ]
}
```

**hgrn_pipeline_suggestions.md:**
```markdown
# Pipeline Suggestions

## Pass A Issues
- TOC entry 'Chapter 3: Spells' was not located on page 42.
- Review OCR accuracy for pages 40-45.

## Pass C Issues
- Chunk elem_123:5 text was not located on source page 15.
- Term 'Armor Penetration' not found in source document.
- Review dictionary extraction rules.

## Pass D Issues
- No issues detected.

## Pass E Issues
- Orphan chunk detected: chunk_456 (no Document connection).
```

#### Validation Report Output

**Console Output:**
```
Pass F: Consistency Validation Report
============================================================
Document: pathfinder_core_rulebook_20251009_120000
Source: /Transfer_Station/sources/pathfinder.pdf
SHA-256: 4f4b1d9d...

Source Document Analysis:
  Pages: 200
  Tokens Indexed: 51,200 (256/page)
  Indexing Time: 1.23s

MongoDB Validation:
  Score: 0.92 (target: 0.90)
  Terms Checked: 458
  Terms Missing Sources: 5
  Terms with Invalid Pages: 3

Cassandra Validation:
  Score: 0.87 (target: 0.90)
  Expected Chunks: 5234
  Actual Chunks: 5200 (within 5% tolerance)
  Embedding Dimensions: 1536 ✓
  Content Mismatches: 15

Neo4j Validation:
  Score: 0.91 (target: 0.90)
  Orphan Chunks: 2
  Cycles Detected: 0
  Similarity Degree Violations: 1

Source Validation:
  TOC Entries Checked: 127
  TOC Missing on Page: 3
  Terms Checked: 200
  Terms Not in Source: 5

Overall Score: 0.89 (target: 0.90)
Status: ⚠️  BELOW THRESHOLD

HGRN Outputs:
  Remediations: /Transfer_Station/Pass_F_Out/hgrn_output/.../hgrn_db_remediations.json
  Suggestions: /Transfer_Station/Pass_F_Out/hgrn_output/.../hgrn_pipeline_suggestions.md
```

#### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--source-file FILE` | Original source document | None (from Gate 0) |
| `--threshold FLOAT` | Validation threshold | `0.90` |
| `--rules-dir DIR` | Validation rules directory | `/Transfer_Station/hgrn/rules` |
| `--hgrn-output DIR` | HGRN output directory | `/Transfer_Station/Pass_F_Out/hgrn_output` |
| `--mongo-uri URI` | MongoDB URI | `mongodb://n8n_TTRPG_mongodb:27017` |
| `--cassandra-hosts HOST` | Cassandra hosts | `n8n_TTRPG_cassandra` |
| `--neo4j-url URL` | Neo4j Bolt URL | `bolt://n8n_TTRPG_neo4j:7687` |

#### Configuration

**ingestion.cfg:**
```ini
[Pass_F]
output_dir = /Transfer_Station/Pass_F_Out
validation_threshold = 0.90
chunk_tolerance = 0.05
expected_vector_dimension = 1536
similarity_degree_cap = 12

mongo_uri = mongodb://n8n_TTRPG_mongodb:27017
mongo_db = ttrpg_ingestion

cassandra_hosts = n8n_TTRPG_cassandra
cassandra_port = 9042
cassandra_keyspace = ttrpg_vectors

neo4j_url = bolt://n8n_TTRPG_neo4j:7687
neo4j_user =
neo4j_password =
env_file = /app/.env

rules_dir = /Transfer_Station/hgrn/rules
hgrn_output_dir = /Transfer_Station/Pass_F_Out/hgrn_output
```

**.env File:**
```bash
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password
OPENAI_API_KEY=sk-proj-...
```

---

## Complete Workflow Examples

### Example 1: Single Document End-to-End Processing

This example demonstrates processing a single PDF document through all pipeline stages.

```bash
#!/bin/bash
# complete_pipeline.sh - End-to-end document processing

SOURCE_DOC="/Transfer_Station/sources/Pathfinder_Core_Rulebook.pdf"
ENGINE="n8n_TTRPG_ingestion_engine"

echo "=== Gate 0: File Validation ==="
DOC_ID=$(docker exec $ENGINE python3 /app/scripts/gate_0_hash.py "$SOURCE_DOC" --quiet)
echo "Document ID: $DOC_ID"
GATE_0_MARKER="/Transfer_Station/Gate_0_Out/${DOC_ID}.json"

echo ""
echo "=== Pass A: TOC Extraction ==="
docker exec $ENGINE python3 /app/scripts/pass_a_unstructured.py \
  --toc-only "$SOURCE_DOC"

TOC_ELEMENTS="/Transfer_Station/Pass_A_Out/${DOC_ID}_toc_elements.json"

docker exec $ENGINE python3 /app/scripts/pass_a_metadata.py \
  "$TOC_ELEMENTS" --gate-marker "$GATE_0_MARKER"

TOC_METADATA="/Transfer_Station/Pass_A_Out/${DOC_ID}_metadata.json"

docker exec $ENGINE python3 /app/scripts/pass_a_mongo_upsert.py \
  "$TOC_ELEMENTS" "$TOC_METADATA"

echo ""
echo "=== Pass B: Document Splitting ==="
docker exec $ENGINE python3 /app/scripts/pass_b_splitter.py \
  "$GATE_0_MARKER"

PASS_B_MANIFEST="/Transfer_Station/Pass_B_Out/${DOC_ID}_pass_b_manifest.json"

echo ""
echo "=== Pass C: Full Document Processing ==="
# Note: Pass C requires manual processing of each part through Unstructured.io
# This is typically done via n8n workflows
echo "⚠️  Manual step required: Process parts through Unstructured.io"
echo "   Use n8n workflow: ttrpg_ingestion_laneA_n8n_workflow.json"

# Assuming Pass C element files exist:
docker exec $ENGINE python3 /app/scripts/pass_c_metadata.py \
  "$PASS_B_MANIFEST" --gate-marker "$GATE_0_MARKER"

docker exec $ENGINE python3 /app/scripts/pass_c_mongo_upsert.py \
  "$PASS_B_MANIFEST"

echo ""
echo "=== Pass D: Vector Embedding Generation ==="
docker exec $ENGINE python3 /app/scripts/pass_d_hayhooks.py \
  "$PASS_B_MANIFEST" --create-schema

PASS_D_MANIFEST="/Transfer_Station/Pass_D_Out/${DOC_ID}_pass_d_manifest.json"

echo ""
echo "=== Pass E: Knowledge Graph Construction ==="
docker exec $ENGINE python3 /app/scripts/pass_e_graph_builder.py \
  "$PASS_D_MANIFEST"

GRAPH_JSON="/Transfer_Station/Pass_E_Out/${DOC_ID}_graph.json"

docker exec $ENGINE python3 /app/scripts/pass_e_neo4j_upsert.py \
  "$GRAPH_JSON" --create-indexes

echo ""
echo "=== Pass F: Consistency Validation ==="
docker exec $ENGINE python3 /app/scripts/pass_f_consistency_check.py \
  "$GATE_0_MARKER" --source-file "$SOURCE_DOC"

echo ""
echo "=== Pipeline Complete ==="
echo "Document ID: $DOC_ID"
echo "Check validation results in:"
echo "  /Transfer_Station/Pass_F_Out/hgrn_output/${DOC_ID}/"
```

### Example 2: Batch Processing Multiple Documents

```bash
#!/bin/bash
# batch_processing.sh - Process multiple documents

SOURCE_DIR="/Transfer_Station/sources"
ENGINE="n8n_TTRPG_ingestion_engine"

for pdf in "$SOURCE_DIR"/*.pdf; do
  echo "Processing: $pdf"

  # Gate 0
  DOC_ID=$(docker exec $ENGINE python3 /app/scripts/gate_0_hash.py "$pdf" --quiet)
  GATE_0_MARKER="/Transfer_Station/Gate_0_Out/${DOC_ID}.json"

  # Check if already processed
  if docker exec $ENGINE test -f "/Transfer_Station/Pass_F_Out/${DOC_ID}_validation.json"; then
    echo "  Already processed: $DOC_ID"
    continue
  fi

  # Pass A (TOC only for speed)
  docker exec $ENGINE python3 /app/scripts/pass_a_unstructured.py \
    --toc-only "$pdf"

  TOC_ELEMENTS="/Transfer_Station/Pass_A_Out/${DOC_ID}_toc_elements.json"

  docker exec $ENGINE python3 /app/scripts/pass_a_metadata.py \
    "$TOC_ELEMENTS" --gate-marker "$GATE_0_MARKER"

  TOC_METADATA="/Transfer_Station/Pass_A_Out/${DOC_ID}_metadata.json"

  docker exec $ENGINE python3 /app/scripts/pass_a_mongo_upsert.py \
    "$TOC_ELEMENTS" "$TOC_METADATA"

  echo "  Completed Pass A for: $DOC_ID"
done

echo "Batch Pass A complete. Continue with Pass B-F for each document as needed."
```

### Example 3: Re-validation After Database Updates

```bash
#!/bin/bash
# revalidate.sh - Re-run Pass F validation after database changes

DOC_ID="pathfinder_core_rulebook_20251009_120000"
GATE_0_MARKER="/Transfer_Station/Gate_0_Out/${DOC_ID}.json"
SOURCE_DOC="/Transfer_Station/sources/Pathfinder_Core_Rulebook.pdf"
ENGINE="n8n_TTRPG_ingestion_engine"

echo "=== Re-validating: $DOC_ID ==="

docker exec $ENGINE python3 /app/scripts/pass_f_consistency_check.py \
  "$GATE_0_MARKER" \
  --source-file "$SOURCE_DOC" \
  --threshold 0.90

echo ""
echo "=== Validation Report ==="
cat "/Transfer_Station/Pass_F_Out/hgrn_output/${DOC_ID}/hgrn_pipeline_suggestions.md"
```

### Example 4: Incremental Processing (TOC + Selected Parts)

```bash
#!/bin/bash
# incremental_processing.sh - Process TOC first, then specific parts

DOC_ID="pathfinder_core_rulebook_20251009_120000"
GATE_0_MARKER="/Transfer_Station/Gate_0_Out/${DOC_ID}.json"
SOURCE_DOC="/Transfer_Station/sources/Pathfinder_Core_Rulebook.pdf"
ENGINE="n8n_TTRPG_ingestion_engine"

# Step 1: Gate 0 + Pass A (TOC only)
echo "=== Processing TOC ==="
docker exec $ENGINE python3 /app/scripts/gate_0_hash.py "$SOURCE_DOC" --quiet
docker exec $ENGINE python3 /app/scripts/pass_a_unstructured.py --toc-only "$SOURCE_DOC"

TOC_ELEMENTS="/Transfer_Station/Pass_A_Out/${DOC_ID}_toc_elements.json"
docker exec $ENGINE python3 /app/scripts/pass_a_metadata.py \
  "$TOC_ELEMENTS" --gate-marker "$GATE_0_MARKER"

# Step 2: Pass B (create split plan)
echo ""
echo "=== Creating Split Plan ==="
docker exec $ENGINE python3 /app/scripts/pass_b_splitter.py "$GATE_0_MARKER"

# Step 3: Process specific parts (e.g., parts 1-3 only)
echo ""
echo "=== Processing Parts 1-3 ==="
for part in 01 02 03; do
  PART_FILE="/Transfer_Station/Pass_B_Out/${DOC_ID}_part${part}.pdf"

  # Process through Unstructured.io (manual or via n8n)
  echo "  Processing part $part..."

  # Continue with Pass D-F for these parts only
done

echo ""
echo "Incremental processing complete for parts 1-3."
echo "Process remaining parts as needed."
```

---

## Configuration Management

### ingestion.cfg Overview

The `ingestion.cfg` file is the **single source of truth** for all pipeline configuration. Located at `./ingestion/ingestion.cfg`, it uses INI format with type-safe accessors.

#### Configuration Sections

**[Gate_0]:**
```ini
output_dir = /Transfer_Station/Gate_0_Out
```

**[Pass_A]:**
```ini
output_dir = /Transfer_Station/Pass_A_Out
unstructured_strategy = hi_res
ocr_language = eng
toc_start_page = 1
toc_end_page = 8
mongo_host = n8n_TTRPG_mongodb
mongo_port = 27017
mongo_db = ttrpg_ingestion
```

**[Pass_B]:**
```ini
output_dir = /Transfer_Station/Pass_B_Out
min_pages = 10
max_pages = 20
```

**[Pass_C]:**
```ini
input_dir = /Transfer_Station/Pass_C_Out
output_dir = /Transfer_Station/Pass_C_Out
game_system = auto
publisher = auto
mongo_host = n8n_TTRPG_mongodb
mongo_port = 27017
mongo_db = ttrpg_ingestion
```

**[Pass_D]:**
```ini
output_dir = /Transfer_Station/Pass_D_Out
cassandra_host = n8n_TTRPG_cassandra
cassandra_port = 9042
cassandra_keyspace = ttrpg_vectors
embedding_model = text-embedding-3-small
min_chunk_chars = 500
max_chunk_chars = 600
chunk_overlap = 50
batch_size = 100
```

**[Pass_E]:**
```ini
output_dir = /Transfer_Station/Pass_E_Out
cassandra_host = n8n_TTRPG_cassandra
cassandra_port = 9042
cassandra_keyspace = ttrpg_vectors
neo4j_host = n8n_TTRPG_neo4j
neo4j_port = 7687
neo4j_database = neo4j
enable_similarity = false
similarity_threshold = 0.82
similarity_top_k = 5
```

**[Pass_F]:**
```ini
output_dir = /Transfer_Station/Pass_F_Out
validation_threshold = 0.90
chunk_tolerance = 0.05
expected_vector_dimension = 1536
similarity_degree_cap = 12

mongo_uri = mongodb://n8n_TTRPG_mongodb:27017
mongo_db = ttrpg_ingestion

cassandra_hosts = n8n_TTRPG_cassandra
cassandra_port = 9042
cassandra_keyspace = ttrpg_vectors

neo4j_url = bolt://n8n_TTRPG_neo4j:7687
neo4j_user =
neo4j_password =
env_file = /app/.env

rules_dir = /Transfer_Station/hgrn/rules
hgrn_output_dir = /Transfer_Station/Pass_F_Out/hgrn_output
```

### Environment Variables (.env)

**Critical:** Never commit `.env` to version control. It contains sensitive credentials.

**Required Variables:**
```bash
# OpenAI API Key (Pass D)
OPENAI_API_KEY=sk-proj-...

# Neo4j Credentials (Pass E, Pass F)
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_secure_password

# Optional: MongoDB Auth (if enabled)
MONGO_USERNAME=admin
MONGO_PASSWORD=your_mongo_password

# Optional: Cassandra Auth (if enabled)
CASSANDRA_USERNAME=cassandra
CASSANDRA_PASSWORD=your_cassandra_password
```

### Configuration Loader (config_loader.py)

**Python Usage:**
```python
from config_loader import load_config, get_pass_d_config

config = load_config()  # Loads ./ingestion/ingestion.cfg
pass_d_cfg = get_pass_d_config(config)

output_dir = pass_d_cfg['output_dir']
embedding_model = pass_d_cfg['embedding_model']
```

**Available Functions:**
- `load_config(config_path)` - Load configuration file
- `get_pass_config(config, pass_name)` - Get section as dictionary
- `get_gate0_config(config)` - Get typed Gate 0 config
- `get_pass_a_config(config)` - Get typed Pass A config
- `get_pass_b_config(config)` - Get typed Pass B config
- `get_pass_c_config(config)` - Get typed Pass C config
- `get_pass_d_config(config)` - Get typed Pass D config
- `get_pass_e_config(config)` - Get typed Pass E config
- `get_pass_f_config(config)` - Get typed Pass F config

---

## Error Handling & Troubleshooting

### Common Errors

#### Error 1: OpenAI API Rate Limit

**Error Message:**
```
openai.error.RateLimitError: Rate limit exceeded
```

**Cause:** Too many embedding requests in short time

**Solutions:**
1. Increase batch delay: `time.sleep(0.2)` in pass_d_hayhooks.py
2. Reduce batch size: `--batch-size 50`
3. Upgrade OpenAI tier (higher rate limits)

#### Error 2: Cassandra Connection Timeout

**Error Message:**
```
cassandra.cluster.NoHostAvailable: Unable to connect to any servers
```

**Cause:** Cassandra not fully started or network issue

**Solutions:**
```bash
# Check Cassandra health
docker exec n8n_TTRPG_cassandra nodetool status

# Check Docker network
docker network inspect n8n_ttrpg_network

# Restart Cassandra
docker restart n8n_TTRPG_cassandra

# Wait for healthy status (~40s)
docker ps  # Check HEALTH column
```

#### Error 3: Neo4j Authentication Failed

**Error Message:**
```
neo4j.exceptions.AuthError: The client is unauthorized due to authentication failure.
```

**Cause:** Incorrect credentials in `.env`

**Solutions:**
```bash
# Verify .env file exists
ls -la .env

# Check NEO4J_USER and NEO4J_PASSWORD
cat .env | grep NEO4J

# Reset Neo4j password
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'new_password'"

# Update .env
echo "NEO4J_PASSWORD=new_password" >> .env
```

#### Error 4: Source File Not Found (Pass F)

**Error Message:**
```
Warning: Source file not found: /Transfer_Station/sources/document.pdf
```

**Cause:** Source file moved or deleted, or incorrect path in Gate 0 marker

**Solutions:**
```bash
# Check source file exists
ls -l /Transfer_Station/sources/

# Verify Gate 0 marker has correct path
cat /Transfer_Station/Gate_0_Out/document_id.json | grep original_path

# Manually specify source file
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/document_id.json \
  --source-file /Transfer_Station/sources/correct_path.pdf
```

#### Error 5: PDF Extraction Failed (Pass F Source Validation)

**Error Message:**
```
ImportError: pypdf is not installed
```

**Cause:** pypdf not installed in container

**Solutions:**
```bash
# Install pypdf
docker exec n8n_TTRPG_ingestion_engine pip install pypdf

# Rebuild container with updated requirements.txt
docker compose -f docker-compose-n8n_TTRPG.yml up -d --build ingestion_engine
```

### Debug Commands

**Check Database Connections:**
```bash
# MongoDB
docker exec n8n_TTRPG_mongodb mongosh --eval "db.adminCommand('ping')"

# Cassandra
docker exec n8n_TTRPG_cassandra cqlsh -e "DESCRIBE KEYSPACES"

# Neo4j
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p password \
  "MATCH (n) RETURN count(n) AS node_count"
```

**View Script Logs:**
```bash
# Last 100 lines of ingestion_engine logs
docker logs n8n_TTRPG_ingestion_engine --tail 100

# Follow logs in real-time
docker logs n8n_TTRPG_ingestion_engine -f
```

**Validate Data Consistency:**
```bash
# MongoDB document count
docker exec n8n_TTRPG_mongodb mongosh ttrpg_ingestion --quiet \
  --eval "db.documents.countDocuments({})"

# Cassandra embedding count
docker exec n8n_TTRPG_cassandra cqlsh -e \
  "SELECT COUNT(*) FROM ttrpg_vectors.embeddings WHERE document_id = 'document_id';"

# Neo4j node count
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p password \
  "MATCH (n {document_id: 'document_id'}) RETURN count(n) AS node_count"
```

---

## Performance Optimization

### Pipeline Timing Benchmarks

**200-Page PDF Document:**

| Stage | Time | Notes |
|-------|------|-------|
| Gate 0 | ~2 seconds | SHA-256 computation |
| Pass A (TOC) | 10-20 seconds | Unstructured.io API |
| Pass A (Metadata) | <5 seconds | Local processing |
| Pass A (MongoDB) | 1-3 seconds | Bulk upserts |
| Pass B | 5-10 seconds | PDF splitting |
| Pass C (Full) | ~2 minutes | Unstructured.io hi_res OCR |
| Pass C (Metadata) | <10 seconds | Consolidation |
| Pass C (MongoDB) | 5-10 seconds | Bulk upserts |
| Pass D | ~30 seconds | OpenAI API + Cassandra |
| Pass E (Build) | 10-15 seconds | Graph construction |
| Pass E (Upsert) | 20-30 seconds | Neo4j batch MERGE |
| Pass F | 15-30 seconds | Multi-DB validation + source |

**Total:** ~4-6 minutes (with TOC-only Pass A)

### Optimization Strategies

#### 1. Parallel Processing

**Current:** Sequential pass-by-pass processing
**Optimization:** Process multiple documents in parallel

```bash
#!/bin/bash
# parallel_batch.sh - Process 5 documents in parallel

SOURCE_DIR="/Transfer_Station/sources"
MAX_PARALLEL=5

find "$SOURCE_DIR" -name "*.pdf" | head -n 5 | xargs -P $MAX_PARALLEL -I {} \
  bash -c 'echo "Processing: {}"; docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py "{}"'
```

#### 2. Cassandra Batch Size Tuning

**Default:** 100 chunks/batch
**Optimization:** Increase for faster ingestion (if memory allows)

```bash
# Larger batches = fewer API calls
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/manifest.json --batch-size 200
```

#### 3. Neo4j Index Pre-Creation

**Default:** Create indexes during first upsert
**Optimization:** Create indexes before ingestion

```cypher
// Run once before processing documents
CREATE INDEX document_id_idx IF NOT EXISTS FOR (n:Document) ON (n.document_id);
CREATE INDEX element_id_idx IF NOT EXISTS FOR (n:Element) ON (n.element_id);
CREATE INDEX term_name_idx IF NOT EXISTS FOR (n:Term) ON (n.term);
CREATE INDEX chunk_id_idx IF NOT EXISTS FOR (n:Chunk) ON (n.chunk_id);
```

#### 4. MongoDB Connection Pooling

**Current:** Single connection per script
**Optimization:** Reuse connections in long-running processes

```python
# In ingestion_wrapper.py (future enhancement)
mongo_client = MongoClient("mongodb://n8n_TTRPG_mongodb:27017", maxPoolSize=50)
# Reuse client across multiple Pass A/C operations
```

#### 5. Skip Validation During Bulk Ingestion

**When:** Processing 100+ documents
**Why:** Pass F validation adds 15-30 seconds per document

```bash
# Bulk ingestion without validation
for pdf in *.pdf; do
  # Gate 0 - Pass E only
  process_without_validation.sh "$pdf"
done

# Run Pass F validation once at end
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_f_consistency_check.py \
  /Transfer_Station/Gate_0_Out/*.json
```

---

## Security & Best Practices

### Security Checklist

#### 1. Credential Management

- ✅ **Never commit `.env` to version control**
- ✅ Use Docker secrets in production (not bind-mounted `.env`)
- ✅ Rotate credentials regularly (90 days)
- ✅ Use strong passwords (16+ characters, mixed case, symbols)

#### 2. Database Security

**MongoDB:**
```ini
# Enable authentication in production
mongo_uri = mongodb://admin:password@n8n_TTRPG_mongodb:27017/ttrpg_ingestion?authSource=admin
```

**Neo4j:**
```bash
# Change default password immediately
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p neo4j \
  "ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'strong_password_here'"
```

**Cassandra:**
```cql
-- Enable authentication
ALTER ROLE cassandra WITH PASSWORD = 'strong_password_here';
```

#### 3. Network Security

**Docker Network Isolation:**
```yaml
# In docker-compose-n8n_TTRPG.yml
networks:
  ttrpg_network:
    driver: bridge
    internal: false  # Set to true for full isolation (no external access)
```

**Port Exposure:**
- Expose only necessary ports (9000-9013)
- Use firewall rules to restrict access
- Consider VPN for production access

#### 4. Data Validation

**Input Validation:**
```python
# Always validate file paths
if not input_path.exists():
    raise ValueError(f"File not found: {input_path}")

if input_path.suffix.lower() not in ['.pdf', '.docx', '.txt']:
    raise ValueError(f"Unsupported file type: {input_path.suffix}")
```

**SHA-256 Verification:**
```bash
# Verify file integrity before processing
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/document.pdf

# Compare hash with Gate 0 marker
cat /Transfer_Station/Gate_0_Out/document_id.json | grep sha256_hash
```

### Best Practices

#### 1. Version Control

- ✅ Use semantic versioning for scripts (X.Y.Z)
- ✅ Tag releases in Git
- ✅ Document breaking changes in CHANGELOG.md

#### 2. Backup Strategy

**MongoDB Backups:**
```bash
# Daily backup
docker exec n8n_TTRPG_mongodb mongodump \
  --out=/data/backup/$(date +%Y%m%d) \
  --db=ttrpg_ingestion
```

**Cassandra Backups:**
```bash
# Snapshot keyspace
docker exec n8n_TTRPG_cassandra nodetool snapshot ttrpg_vectors
```

**Neo4j Backups:**
```bash
# Export database
docker exec n8n_TTRPG_neo4j neo4j-admin dump \
  --database=neo4j --to=/data/backup/neo4j_$(date +%Y%m%d).dump
```

#### 3. Monitoring

**Resource Usage:**
```bash
# Monitor Docker stats
docker stats n8n_TTRPG_mongodb n8n_TTRPG_cassandra n8n_TTRPG_neo4j

# Monitor disk usage
docker system df
```

**Database Health:**
```bash
# MongoDB
docker exec n8n_TTRPG_mongodb mongosh --eval "db.serverStatus()"

# Cassandra
docker exec n8n_TTRPG_cassandra nodetool status

# Neo4j
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p password \
  "CALL dbms.queryJmx('org.neo4j:*') YIELD name, attributes"
```

---

## Monitoring & Validation

### Validation Scripts

#### verify_neo4j.py

**Purpose:** Comprehensive Neo4j graph validation

**Usage:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/verify_neo4j.py
```

**Checks:**
- Node counts by label
- Relationship counts by type
- Orphan detection
- Cycle detection
- Index status

#### gate_0_validate.py

**Purpose:** Verify Gate 0 marker integrity

**Usage:**
```bash
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_validate.py \
  /Transfer_Station/Gate_0_Out/document_id.json
```

**Checks:**
- SHA-256 hash matches file
- document_id format valid
- Required fields present
- File size matches

### Database Validation Queries

**MongoDB - Document Count:**
```javascript
// Connect: docker exec -it n8n_TTRPG_mongodb mongosh ttrpg_ingestion

db.documents.countDocuments({})
db.elements.countDocuments({})
db.terms.countDocuments({})
db.categories.countDocuments({})

// Find documents missing terms
db.documents.find({
  document_id: { $exists: true }
}).forEach(doc => {
  const termCount = db.terms.countDocuments({ document_id: doc.document_id });
  if (termCount === 0) {
    print(`Missing terms: ${doc.document_id}`);
  }
});
```

**Cassandra - Embedding Verification:**
```cql
-- Connect: docker exec -it n8n_TTRPG_cassandra cqlsh

SELECT COUNT(*) FROM ttrpg_vectors.embeddings;

-- Check embedding dimensions
SELECT document_id, element_id, LENGTH(embedding) AS dim
FROM ttrpg_vectors.embeddings
WHERE document_id = 'document_id'
LIMIT 10;

-- Find missing embeddings
SELECT document_id, element_id
FROM ttrpg_vectors.embeddings
WHERE embedding = null
ALLOW FILTERING;
```

**Neo4j - Graph Structure:**
```cypher
// Connect: docker exec -it n8n_TTRPG_neo4j cypher-shell -u neo4j -p password

// Node counts
MATCH (n) RETURN labels(n) AS label, count(n) AS count
ORDER BY count DESC;

// Relationship counts
MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count
ORDER BY count DESC;

// Find orphan chunks
MATCH (c:Chunk {document_id: 'document_id'})
WHERE NOT (c)--()
RETURN c.chunk_id LIMIT 10;

// Find cycles
MATCH path = (n)-[*]->(n)
WHERE n.document_id = 'document_id'
RETURN path LIMIT 5;
```

---

## Advanced Topics

### Custom Validation Rules (HGRN)

**Rules Directory Structure:**
```
/Transfer_Station/hgrn/rules/
├── mongodb_rules.json
├── cassandra_rules.json
├── neo4j_rules.json
└── source_validation_rules.json
```

**Example: mongodb_rules.json**
```json
{
  "rules": [
    {
      "name": "term_sources_required",
      "description": "All terms must have sources field",
      "severity": "error",
      "check": {
        "collection": "terms",
        "filter": {"sources": {"$exists": false}},
        "action": "flag"
      }
    },
    {
      "name": "term_page_references_valid",
      "description": "Page references must be within document bounds",
      "severity": "warning",
      "check": {
        "collection": "terms",
        "filter": {},
        "validate": "page_references_in_bounds"
      }
    }
  ]
}
```

### Multi-Tenancy Support

**Configuration:**
```ini
[Pass_F]
tenant_id = customer_abc
corpus_version = v2.1
expected_system = PF2E
expected_publisher = Paizo
```

**Directory Structure:**
```
/Transfer_Station/
├── tenants/
│   ├── customer_abc/
│   │   ├── sources/
│   │   ├── Gate_0_Out/
│   │   └── Pass_*_Out/
│   └── customer_xyz/
│       ├── sources/
│       └── ...
```

### GPU Acceleration (HGRN)

**Docker Compose Configuration:**
```yaml
hgrn:
  image: n8n_ttrpg_hgrn:latest
  runtime: nvidia
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**Performance Impact:**
- CPU-only: ~30-60 seconds validation
- GPU-accelerated: ~5-10 seconds validation
- Memory: 4GB GPU RAM recommended

### Custom Chunking Strategies

**Token-Based Chunking (Alternative to Character-Based):**
```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

def token_based_chunking(text, max_tokens=512, overlap=50):
    tokens = tokenizer.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        start = end - overlap
    return chunks
```

**Semantic Chunking (LangChain):**
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split_text(document_text)
```

---

## Appendix

### Service Ports Reference

| Service | External Port | Internal Port | Access URL |
|---------|---------------|---------------|------------|
| n8n | 9000 | 5678 | http://localhost:9000 |
| Cassandra CQL | 9001 | 9042 | cqlsh localhost 9001 |
| MongoDB | 9002 | 27017 | mongodb://localhost:9002 |
| Neo4j Browser | 9003 | 7474 | http://localhost:9003 |
| Stargate REST | 9004 | 8082 | http://localhost:9004 |
| Neo4j Bolt | 9005 | 7687 | bolt://localhost:9005 |
| Unstructured API | 9006 | 8000 | http://localhost:9006 |
| Hayhooks API | 9007 | 8000 | http://localhost:9007 |
| Stargate REST (alt) | 9008 | 8082 | http://localhost:9008 |
| Ingestion Engine | 9009 | 8000 | http://localhost:9009 |
| LangFlow UI | 9010 | 7860 | http://localhost:9010 |
| Stargate GraphQL | 9011 | 8080 | http://localhost:9011 |
| Stargate gRPC | 9012 | 8090 | localhost:9012 |
| HGRN API | 9013 | 8000 | http://localhost:9013 |

### Script Version Matrix

| Script | Version | Last Updated | Breaking Changes |
|--------|---------|--------------|------------------|
| gate_0_hash.py | 2.1.0 | 2025-10-11 | None |
| pass_a_unstructured.py | 2.0.0 | 2025-10-09 | None |
| pass_a_metadata.py | 2.0.0 | 2025-10-09 | Added --gate-marker |
| pass_a_mongo_upsert.py | 2.0.0 | 2025-10-09 | None |
| pass_b_splitter.py | 1.2.0 | 2025-10-10 | None |
| pass_c_metadata.py | 2.0.0 | 2025-10-09 | Added --gate-marker |
| pass_c_mongo_upsert.py | 2.0.0 | 2025-10-09 | None |
| pass_d_hayhooks.py | 2.1.0 | 2025-10-11 | Auto-discovery |
| pass_e_graph_builder.py | 1.0.0 | 2025-10-08 | None |
| pass_e_neo4j_upsert.py | 1.0.0 | 2025-10-08 | None |
| pass_f_consistency_check.py | 2.1.0 | 2025-10-11 | Major: Source validation |

### Glossary

- **Document ID**: Unique identifier generated by Gate 0 (sanitized filename + timestamp)
- **Gate 0 Marker**: JSON file with document metadata and SHA-256 hash
- **TOC**: Table of Contents
- **Element**: Individual content block extracted by Unstructured.io
- **Chunk**: Text segment for embedding generation (500-600 chars)
- **Embedding**: Vector representation of text (1536 dimensions)
- **Token**: 4+ character alphanumeric string used for source validation
- **Inverted Index**: Map of tokens to page numbers (O(1) lookup)
- **HGRN**: Hierarchical Graph Recurrent Network for consistency validation
- **Remediation**: Actionable database fix recommendation
- **Transfer Station**: Shared filesystem volume for inter-service communication

---

**End of Guide**

For additional help, consult:
- `CLAUDE.md` - Quick reference for Claude Code
- `docs/INDEX.md` - Project knowledge base
- `claudedocs/ANALYSIS_REPORT.md` - Code analysis report
- `claudedocs/PASS_F_v2.1_UPGRADE_ANALYSIS.md` - Pass F upgrade details
