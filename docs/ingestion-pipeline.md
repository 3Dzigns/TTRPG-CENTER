# Ingestion Pipeline Reference

Complete documentation for the n8n TTRPG Center ingestion pipeline (Gate 0 through Pass E).

## Table of Contents

- [Gate 0: File Validation](#gate-0-file-validation)
- [Pass A: TOC Extraction](#pass-a-toc-extraction)
- [Pass B: Document Splitting](#pass-b-document-splitting)
- [Pass C: Full Document Processing](#pass-c-full-document-processing)
- [Pass D: Vector Embeddings](#pass-d-vector-embeddings)
- [Pass E: Knowledge Graph](#pass-e-knowledge-graph)
- [Configuration System](#configuration-system)

---

## Gate 0: File Validation

### gate_0_hash.py - SHA-256 Hashing & Document ID Generation

Creates document validation markers with unique document IDs for ingestion gating. This is the first step in document processing pipelines.

**Features:**
- Generates unique `document_id` from sanitized filename + timestamp
- Computes SHA-256 hash for file integrity verification
- Creates JSON marker files with complete metadata
- Efficient chunked reading for large files
- Safe filename sanitization (lowercase alphanumeric + underscores)

**Usage:**
```bash
gate_0_hash.py <input_file> [options]
gate_0_hash.py -v | --version
gate_0_hash.py -? | --help
```

**Options:**
- `input_file` - Path to file for hash computation (required)
- `-o, --output DIR` - Output directory (default: `/Transfer_Station/Gate_0_Out`)
- `-q, --quiet` - Suppress output, only print document_id
- `-v, --version` - Show version
- `-?, --help` - Show help

**Examples:**
```bash
# Basic validation
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/n8n_inbound/manual.pdf

# Custom output directory
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/doc.pdf -o /Transfer_Station/custom_gate

# Quiet mode (only print document_id for scripting)
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/doc.pdf --quiet)
echo "Document ID: $DOC_ID"
```

**Output:**

Creates JSON marker file: `/Transfer_Station/Gate_0_Out/<document_id>.json`

**Marker File Content:**
```json
{
  "document_id": "pathfinder_rpg_core_rulebook_6th_printing_20251009_175402",
  "original_filename": "Pathfinder RPG - Core Rulebook (6th Printing).pdf",
  "original_path": "/Transfer_Station/sources/Pathfinder RPG - Core Rulebook (6th Printing).pdf",
  "file_size_bytes": 98535290,
  "sha256_hash": "4f4b1d9d2b6ca812ab4fb5a38727ff7922c41cbfe4e4e214511249ce134a8cb5",
  "computed_at": "2025-10-09T17:54:02.123456Z"
}
```

**Document ID Format:**
- Pattern: `<sanitized_filename>_<timestamp>`
- Timestamp: `YYYYMMDD_HHMMSS` (UTC)
- Sanitization: Lowercase, alphanumeric + underscores, max 100 chars (before timestamp)

**Examples:**
- `Pathfinder RPG - Core Rulebook (6th Printing).pdf` → `pathfinder_rpg_core_rulebook_6th_printing_20251009_175402`
- `TOC-Pathfinder.pdf` → `toc_pathfinder_20251009_175335`

---

## Pass A: TOC Extraction

The Pass A pipeline extracts table of contents from documents for fast metadata generation.

### 1. pass_a_unstructured.py - Document Element Extraction

Processes documents through Unstructured.io API for structured element extraction.

**Usage:**
```bash
pass_a_unstructured.py <document> [options]
```

**Options:**
- `document` - Path to input document (required)
- `-o, --output DIR` - Output directory (default: `/Transfer_Station/Pass_A_Out`)
- `-l, --language LNG` - OCR language code (default: `eng`)
- `-t, --toc-only` - Extract TOC only (fast, first 8 pages)
- `-s, --strategy STR` - Processing strategy: `hi_res|toc_pages|fast` (default: `hi_res`)
- `-m, --max-pages N` - Maximum pages for TOC extraction (default: 8)

**Examples:**
```bash
# Full document with hi_res OCR (~2 min for 200 pages)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  /Transfer_Station/sources/manual.pdf

# TOC only (fast - ~10-20 seconds)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only /Transfer_Station/sources/manual.pdf
```

**Output:**
- Full: `/Transfer_Station/Pass_A_Out/<filename>_elements.json`
- TOC: `/Transfer_Station/Pass_A_Out/<filename>_toc_elements.json`

**Processing Strategies:**
- `hi_res` - High-resolution OCR with YOLOX object detection (slow, comprehensive)
- `toc_pages` - TOC extraction only (fast, first N pages)
- `fast` - Fast processing without OCR (no layout detection)

### 2. pass_a_metadata.py - TOC Metadata Extraction

Extracts hierarchical structure, categories, and term index from TOC elements.

**Usage:**
```bash
pass_a_metadata.py <elements_json> [options]
```

**Options:**
- `elements_json` - Path to elements JSON from pass_a_unstructured (required)
- `-o, --output DIR` - Output directory (default: same as input)
- `-s, --system STR` - Game system: `PF1E|PF2E|DND5E|auto` (default: `auto`)
- `-p, --publisher STR` - Publisher name (default: auto-detect)
- `--gate-marker FILE` - Gate 0 marker file for document metadata linkage

**Examples:**
```bash
# With Gate 0 marker integration (recommended)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_metadata.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/manual_20251009_120000.json

# Complete workflow with Gate 0
DOC_ID=$(docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py \
  /Transfer_Station/sources/manual.pdf --quiet)

docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_unstructured.py \
  --toc-only /Transfer_Station/sources/manual.pdf

docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_metadata.py \
  /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json
```

**Output:** `/Transfer_Station/Pass_A_Out/<filename>_metadata.json`

**Metadata Structure (with Gate 0 integration):**
```json
{
  "document": {
    "document_id": "pathfinder_core_rulebook_20251009_120000",
    "original_filename": "Pathfinder Core Rulebook.pdf",
    "original_path": "/Transfer_Station/sources/Pathfinder Core Rulebook.pdf",
    "file_size_bytes": 98535290,
    "sha256_hash": "4f4b1d...",
    "computed_at": "2025-10-09T12:00:00Z"
  },
  "extraction": {
    "system": "PF2E",
    "publisher": "Paizo",
    "extraction_date": "2025-10-09T15:30:00Z"
  },
  "toc_structure": [...],
  "categories": {...},
  "terms": [
    {
      "term": "Armor Class",
      "category": "combat",
      "page_references": [15, 142, 203],
      "document_id": "pathfinder_core_rulebook_20251009_120000"
    }
  ],
  "statistics": {...}
}
```

**Detected Categories:**
- `character_creation` - Races, classes, backgrounds
- `combat` - Weapons, armor, actions
- `magic` - Spells, rituals, casting
- `equipment` - Gear, items, treasure
- `rules` - Mechanics, gameplay
- `setting` - World, lore, history
- `game_master` - GM/DM guidance

**Supported Systems:** PF1E, PF2E, DND5E, STARFINDER, CALL_OF_CTHULHU

### 3. pass_a_mongo_upsert.py - MongoDB Storage

Upserts elements and metadata to MongoDB with detailed change tracking.

**Usage:**
```bash
pass_a_mongo_upsert.py <elements_json> <metadata_json> [options]
```

**Options:**
- `elements_json` - Path to elements JSON (required)
- `metadata_json` - Path to metadata JSON (required)
- `--host HOST` - MongoDB host (default: `n8n_TTRPG_mongodb`)
- `--port PORT` - MongoDB port (default: `27017`)
- `--db NAME` - Database name (default: `ttrpg_ingestion`)
- `--dry-run` - Show changes without applying

**Examples:**
```bash
# Standard upsert
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json

# Dry run (preview changes)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json \
  --dry-run
```

**MongoDB Collections:**
- `documents` - Document metadata and system info
- `elements` - Individual elements (Title, Text, Table, etc.)
- `categories` - Category hierarchy
- `terms` - Term index with page references

---

## Pass B: Document Splitting

### pass_b_splitter.py - Document Part Splitting

Splits large documents into logical parts for distributed processing.

**Usage:**
```bash
pass_b_splitter.py <gate0_marker> [options]
```

**Options:**
- `-o, --output DIR` - Output directory (default: `/Transfer_Station/Pass_B_Out`)
- `--min-pages N` - Minimum pages per part (default: 10)
- `--max-pages N` - Maximum pages per part (default: 20)

**Examples:**
```bash
# Basic splitting with defaults (10-20 pages per part)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_b_splitter.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json

# Custom page range (5-15 pages per part)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_b_splitter.py \
  /Transfer_Station/Gate_0_Out/document_20251009_120000.json \
  --min-pages 5 --max-pages 15
```

**Output:**
- Manifest: `/Transfer_Station/Pass_B_Out/{document_id}_pass_b_manifest.json`
- Part files: `/Transfer_Station/Pass_B_Out/{document_id}_part##.pdf`

**Manifest Structure:**
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
    }
  ],
  "total_parts": 16,
  "timestamp": "2025-10-09T12:10:00Z"
}
```

---

## Pass C: Full Document Processing

### 1. pass_c_metadata.py - Full Document Metadata Extraction

Extracts comprehensive metadata from all Pass C element files (all document parts).

**Usage:**
```bash
pass_c_metadata.py <pass_b_manifest> [options]
```

**Options:**
- `-o, --output DIR` - Output directory (default: same as Pass B manifest)
- `--pass-c-dir DIR` - Pass C elements directory (default: `/Transfer_Station/Pass_C_Out`)
- `-s, --system STR` - Game system: `PF1E|PF2E|DND5E|auto` (default: `auto`)
- `-p, --publisher STR` - Publisher name (default: auto-detect)
- `--gate-marker FILE` - Gate 0 marker file for document linkage

**Examples:**
```bash
# Auto-detect system and publisher with Gate 0 integration
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_metadata.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json \
  --gate-marker /Transfer_Station/Gate_0_Out/document_20251009_120000.json
```

**Output:** `/Transfer_Station/Pass_C_Out/{document_id}_pass_c_metadata.json`

### 2. pass_c_mongo_upsert.py - Full Document MongoDB Storage

Upserts full document elements and metadata to MongoDB with change tracking.

**Usage:**
```bash
pass_c_mongo_upsert.py <pass_b_manifest> [options]
```

**Options:**
- `--pass-c-dir DIR` - Pass C directory (default: `/Transfer_Station/Pass_C_Out`)
- `--host HOST` - MongoDB host (default: `n8n_TTRPG_mongodb`)
- `--port PORT` - MongoDB port (default: `27017`)
- `--db NAME` - Database name (default: `ttrpg_ingestion`)
- `--dry-run` - Show changes without applying

**Examples:**
```bash
# Standard upsert
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_mongo_upsert.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json

# Dry run (preview changes)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_c_mongo_upsert.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json --dry-run
```

---

## Pass D: Vector Embeddings

### pass_d_hayhooks.py - Vector Embedding and Storage

Processes Pass B manifest, auto-discovers Pass C element files, generates embeddings via OpenAI API, and stores vectors in Cassandra.

**Features:**
- Character-based chunking: 500-600 character chunks with 50-char overlap
- Metadata integration: Automatically loads Pass C metadata
- Auto-discovery: Discovers all Pass C element files from Pass B manifest
- Batch processing: Efficient OpenAI API usage with configurable batch sizes

**Usage:**
```bash
pass_d_hayhooks.py <pass_b_manifest> [options]
```

**Options:**
- `-o, --output DIR` - Output directory (default: `/Transfer_Station/Pass_D_Out`)
- `--pass-c-dir DIR` - Pass C output directory (default: `/Transfer_Station/Pass_C_Out`)
- `--host HOST` - Cassandra host (default: `n8n_TTRPG_cassandra`)
- `--port PORT` - Cassandra port (default: `9042`)
- `--keyspace NAME` - Cassandra keyspace (default: `ttrpg_vectors`)
- `--model NAME` - Embedding model (default: `text-embedding-3-small`)
- `--min-chunk-chars N` - Minimum characters per chunk (default: `500`)
- `--max-chunk-chars N` - Maximum characters per chunk (default: `600`)
- `--chunk-overlap N` - Character overlap between chunks (default: `50`)
- `--batch-size N` - Embedding batch size (default: `100`)
- `--create-schema` - Create Cassandra schema if not exists
- `--dry-run` - Validate input without processing

**Environment Configuration:**

The script requires an OpenAI API key stored in `.env` file at project root:
```bash
# .env file
OPENAI_API_KEY=sk-proj-...
```

**IMPORTANT:** The `.env` file is protected by `.gitignore` and should NEVER be committed.

**Examples:**
```bash
# Basic processing with defaults (500-600 char chunks, 50 overlap)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/document_manifest.json --create-schema

# Custom chunk sizes
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/pass_d_hayhooks.py \
  /Transfer_Station/Pass_B_Out/manifest.json \
  --min-chunk-chars 800 --max-chunk-chars 1000 --chunk-overlap 100
```

**Output:** `/Transfer_Station/Pass_D_Out/<document_id>_pass_d_manifest.json`

**Cassandra Schema:**
```cql
CREATE TABLE ttrpg_vectors.embeddings (
  document_id text,
  element_id text,
  chunk_index int,
  sub_chunk int,
  source_part int,
  text_content text,
  embedding list<float>,
  element_type text,
  page_number text,
  filename text,
  game_system text,
  publisher text,
  category text,
  embedding_model text,
  created_at timestamp,
  PRIMARY KEY ((document_id), element_id, chunk_index)
);
```

**OpenAI Integration:**
- Model: `text-embedding-3-small` (1536 dimensions)
- Batch processing: 100 chunks per batch (configurable)
- Rate limiting: 0.1s delay between batches
- Cost tracking: $0.020 per 1M tokens

---

## Pass E: Knowledge Graph

Pass E turns Pass D embeddings and Pass C metadata into a Neo4j knowledge graph.

### 1. pass_e_graph_builder.py - Graph Artifact Builder

Builds graph artifacts from vectors and metadata.

**Usage:**
```bash
pass_e_graph_builder.py <pass_d_manifest> [--enable-similarity]
```

**Options:**
- `--enable-similarity` - Enable SIMILAR_TO relationships (threshold: 0.82, top-5 neighbors)

**Output:**
- `{document_id}_vectors.json` - Vector data
- `{document_id}_graph.json` - Graph structure
- `{document_id}_pass_e_intermediate.json` - Intermediate processing data

### 2. pass_e_neo4j_upsert.py - Neo4j Graph Storage

Upserts graph into Neo4j with batch processing.

**Usage:**
```bash
pass_e_neo4j_upsert.py <document_id>_graph.json [--create-indexes]
```

**Options:**
- `--create-indexes` - Create Neo4j indexes
- `--user USER` - Neo4j username (default: from `.env`)
- `--password PASS` - Neo4j password (default: from `.env`)

**Output:** `{document_id}_pass_e_manifest.json` with change statistics and timings

**Verifying a run:**
- Check manifest for node/edge counts and upsert timings
- Use Neo4j Browser queries to confirm nodes/relationships
- `--dry-run` performs validation without mutating database

---

## Configuration System

### ingestion.cfg - Central Configuration File

Contains configuration for all pipeline passes in INI format. Located in `./ingestion/ingestion.cfg`.

**Key Sections:**
```ini
[Gate_0]
output_dir = /Transfer_Station/Gate_0_Out

[Pass_A]
output_dir = /Transfer_Station/Pass_A_Out
unstructured_strategy = hi_res
ocr_language = eng
toc_start_page = 1
toc_end_page = 8
mongo_host = n8n_TTRPG_mongodb
mongo_port = 27017
mongo_db = ttrpg_ingestion

[Pass_B]
output_dir = /Transfer_Station/Pass_B_Out
min_pages = 10
max_pages = 20

[Pass_C]
input_dir = /Transfer_Station/Pass_C_Out
output_dir = /Transfer_Station/Pass_C_Out
game_system = auto
publisher = auto
mongo_host = n8n_TTRPG_mongodb
mongo_port = 27017
mongo_db = ttrpg_ingestion

[Pass_D]
output_dir = /Transfer_Station/Pass_D_Out
cassandra_host = n8n_TTRPG_cassandra
cassandra_port = 9042
cassandra_keyspace = ttrpg_vectors
embedding_model = text-embedding-3-small
min_chunk_chars = 500
max_chunk_chars = 600
chunk_overlap = 50
batch_size = 100

[Pass_E]
cassandra_host = n8n_TTRPG_cassandra
cassandra_port = 9042
neo4j_host = n8n_TTRPG_neo4j
neo4j_port = 7687
similarity_threshold = 0.82
similarity_top_k = 5
```

### config_loader.py - Configuration Management

Loads and validates configuration with type-safe access.

**Usage:**
```python
from config_loader import load_config, get_pass_a_config

config = load_config()  # Loads ./ingestion.cfg
pass_a_cfg = get_pass_a_config(config)

# Access with defaults
output_dir = pass_a_cfg['output_dir']
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
