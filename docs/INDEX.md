# n8n TTRPG Center - Project Knowledge Base Index

**Last Updated:** 2025-10-11
**Version:** 1.0.0
**Documentation Status:** Comprehensive

---

## Quick Navigation

### 🚀 Getting Started
- [Quick Reference](#quick-reference) - Essential commands and ports
- [First Time Setup](#first-time-setup) - Installation and configuration
- [Common Workflows](#common-workflows) - Typical usage patterns

### 📚 Core Documentation
- [Architecture Overview](#architecture-overview) - System design and patterns
- [Pipeline Reference](#pipeline-reference) - Gate 0 through Pass F
- [Configuration Guide](#configuration-guide) - Settings and customization
- [API Reference](#api-reference) - Service endpoints and interfaces

### 🔧 Development
- [Development Setup](#development-setup) - Local environment configuration
- [Testing Guide](#testing-guide) - Testing strategies and procedures
- [Troubleshooting](#troubleshooting) - Common issues and solutions
- [Contributing](#contributing) - Development guidelines

### 📊 Analysis & Reports
- [Code Analysis Report](../claudedocs/ANALYSIS_REPORT.md) - Comprehensive codebase analysis
- [Pass F v2.1 Upgrade](../claudedocs/PASS_F_v2.1_UPGRADE_ANALYSIS.md) - Latest feature analysis

---

## Quick Reference

### Essential Commands

```bash
# Start entire stack
docker compose -f docker-compose-n8n_TTRPG.yml up -d

# View service logs
docker compose -f docker-compose-n8n_TTRPG.yml logs -f [service_name]

# Access ingestion engine
docker exec -it n8n_TTRPG_ingestion_engine bash

# Database management
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --summarize
```

### Service Ports

| Service | External Port | Internal Port | Access URL |
|---------|---------------|---------------|------------|
| n8n | 9000 | 5678 | http://localhost:9000 |
| MongoDB | 9002 | 27017 | mongodb://localhost:9002 |
| Cassandra | 9001 | 9042 | localhost:9001 |
| Neo4j Browser | 9003 | 7474 | http://localhost:9003 |
| Neo4j Bolt | 9005 | 7687 | bolt://localhost:9005 |
| Unstructured | 9006 | 8000 | http://localhost:9006 |
| LangFlow | 9010 | 7860 | http://localhost:9010 |
| HGRN | 9013 | 8000 | http://localhost:9013 |

### Key Scripts

All scripts support `-v|--version` and `-?|--help` flags.

```bash
# Prefix for all commands
EXEC="docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts"

# Gate 0: Document validation
$EXEC/gate_0_hash.py <input_file> [-o DIR] [--quiet]

# Pass A: TOC extraction
$EXEC/pass_a_unstructured.py --toc-only <document>
$EXEC/pass_a_metadata.py <elements_json> --gate-marker <marker>
$EXEC/pass_a_mongo_upsert.py <elements> <metadata>

# Pass B: Document splitting
$EXEC/pass_b_splitter.py <gate0_marker> [-o DIR] [--min-pages N] [--max-pages N]

# Pass F: Consistency validation
$EXEC/pass_f_consistency_check.py <gate0_marker> [--threshold 0.90] [--source-file FILE]

# Database management
$EXEC/db_manager.py --{summarize|clear} [--db TYPE] [--force]
$EXEC/clear_document.py <document_id> [--force] [--dry-run]
```

---

## Architecture Overview

### System Design

**Pattern:** Multi-pass pipeline with Transfer Station filesystem broker

```
┌─────────────┐
│  Gate 0     │  File Validation (SHA-256)
│  Validation │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Pass A     │  TOC Extraction (8 pages)
│  TOC        │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Pass B     │  Document Splitting (10-20 page parts)
│  Split      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Pass C     │  Full Document Processing
│  Parse      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Pass D     │  Vector Embeddings (OpenAI)
│  Vectors    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Pass E     │  Knowledge Graph (Neo4j)
│  Graph      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Pass F     │  Consistency Validation (HGRN)
│  Validate   │
└─────────────┘
```

### Core Components

**Services (8 total):**
- **n8n**: Workflow orchestration
- **MongoDB**: Document storage (terms, categories, metadata)
- **Cassandra**: Vector embeddings storage
- **Neo4j**: Knowledge graph database
- **Unstructured.io**: Document parsing API
- **Hayhooks**: Haystack pipeline execution
- **Ingestion Engine**: Python 3.11 processing environment
- **HGRN**: Consistency validation (GPU-enabled)

**Transfer Station Pattern:**
- Filesystem broker: `E:/n8n_TTRPG_Transfer_Station`
- Service-specific directories: `{service}_inbound/`, `{service}_processing/`
- Decouples services, provides audit trails
- No network dependencies for file passing

### Key Architectural Patterns

1. **Sequential Pipeline**: Gate 0 → Pass A-F with clear data flow
2. **Transfer Station**: Filesystem-based service decoupling
3. **Configuration Centralization**: Single `ingestion.cfg` file
4. **Service Isolation**: Dedicated inbound/processing directories

---

## Pipeline Reference

### Gate 0: File Validation

**Purpose:** SHA-256 hash + unique document_id generation
**Script:** `gate_0_hash.py`
**Output:** `/Transfer_Station/Gate_0_Out/{document_id}.json`

**Document ID Format:**
```
{sanitized_filename}_{timestamp}
Example: pathfinder_core_rulebook_20251009_120000
```

**Marker File Structure:**
```json
{
  "document_id": "pathfinder_core_rulebook_20251009_120000",
  "original_filename": "Pathfinder Core Rulebook.pdf",
  "original_path": "/Transfer_Station/sources/...",
  "file_size_bytes": 98535290,
  "sha256_hash": "4f4b1d9d2b6ca812ab4fb5a38727ff...",
  "computed_at": "2025-10-09T17:54:02.123456Z"
}
```

**Integrity Tracking:** Pass D writes an embedding_manifests row for each document (chunk count, vector checksum, chunk index range, embedding model). Gate 0 validation compares its checksum file against this manifest instead of scanning the entire embeddings table.

**Usage:**
```bash
# Basic validation
gate_0_hash.py /Transfer_Station/sources/manual.pdf

# Quiet mode (script usage)
DOC_ID=$(gate_0_hash.py /Transfer_Station/sources/manual.pdf --quiet)
```

---

### Pass A: TOC Extraction

**Purpose:** Fast TOC extraction (first 8 pages) → metadata → MongoDB
**Scripts:** `pass_a_unstructured.py`, `pass_a_metadata.py`, `pass_a_mongo_upsert.py`
**Output:** TOC elements + metadata + MongoDB storage

**Processing Strategies:**
- `hi_res`: High-resolution OCR with YOLOX (slow, comprehensive)
- `toc_pages`: TOC extraction only (fast, first N pages)
- `fast`: Fast processing without OCR

**Workflow:**
```bash
# 1. Extract TOC
pass_a_unstructured.py --toc-only /Transfer_Station/sources/manual.pdf

# 2. Generate metadata
pass_a_metadata.py /Transfer_Station/Pass_A_Out/manual_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json

# 3. Upsert to MongoDB
pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/manual_elements.json \
  /Transfer_Station/Pass_A_Out/manual_metadata.json
```

**Metadata Structure:**
```json
{
  "document": {
    "document_id": "...",
    "original_filename": "...",
    "sha256_hash": "..."
  },
  "extraction": {
    "system": "PF2E",
    "publisher": "Paizo",
    "extraction_date": "2025-10-09T15:30:00Z"
  },
  "toc_structure": [...],
  "categories": {...},
  "terms": [...]
}
```

---

### Pass B: Document Splitting

**Purpose:** Split large documents into parts (10-20 pages each)
**Script:** `pass_b_splitter.py`
**Output:** Part PDFs + manifest

**Usage:**
```bash
pass_b_splitter.py /Transfer_Station/Gate_0_Out/document.json \
  --min-pages 10 --max-pages 20
```

**Manifest Structure:**
```json
{
  "document_id": "...",
  "parts": [
    {
      "part": 1,
      "filename": "document_part01.pdf",
      "page_start": 9,
      "page_end": 28,
      "page_count": 20
    }
  ],
  "total_parts": 16
}
```

---

### Pass C: Full Document Processing

**Purpose:** Comprehensive metadata extraction from all parts → MongoDB
**Scripts:** `pass_c_metadata.py`, `pass_c_mongo_upsert.py`
**Output:** Full metadata + MongoDB storage

**Detected Categories:**
- `character_creation` - Races, classes, backgrounds
- `combat` - Weapons, armor, actions
- `magic` - Spells, rituals, casting
- `equipment` - Gear, items, treasure
- `rules` - Mechanics, gameplay
- `setting` - World, lore, history
- `game_master` - GM/DM guidance

**Supported Systems:** PF1E, PF2E, DND5E, STARFINDER, CALL_OF_CTHULHU

---

### Pass D: Vector Embeddings

**Purpose:** Generate OpenAI embeddings (500-600 char chunks) → Cassandra
**Script:** `pass_d_hayhooks.py`
**Output:** Vector embeddings + manifest
**Requires:** `.env` file with `OPENAI_API_KEY`

**Character-Based Chunking:**
- Default: 500-600 characters per chunk
- Overlap: 50 characters
- Model: `text-embedding-3-small` (1536 dimensions)
- Batch size: 100 chunks

**Cassandra Schema:**
```cql
CREATE TABLE ttrpg_vectors.embeddings (
  document_id text,
  element_id text,
  chunk_index int,
  text_content text,
  embedding list<float>,  -- 1536 dimensions
  element_type text,
  page_number text,
  game_system text,
  publisher text,
  PRIMARY KEY ((document_id), element_id, chunk_index)
);
```

---

### Pass E: Knowledge Graph

**Purpose:** Build Neo4j knowledge graph from vectors + metadata
**Scripts:** `pass_e_graph_builder.py`, `pass_e_neo4j_upsert.py`
**Output:** Graph nodes/edges + manifest

**Graph Structure:**
- **Nodes:** Document, Chunk, Term, Category
- **Relationships:** CONTAINS, REFERENCES, BELONGS_TO, SIMILAR_TO
- **Similarity Edges:** Optional, threshold-based (0.82 default)

**Configuration:**
```ini
[Pass_E]
enable_similarity = false
similarity_threshold = 0.82
similarity_top_k = 5
```

---

### Pass F: Consistency Validation

**Purpose:** Validate MongoDB, Cassandra, Neo4j against source documents
**Script:** `pass_f_consistency_check.py` (v2.1.0)
**Output:** Validation scores + remediation plan + HGRN outputs
**Requires:** Optional GPU for HGRN AI model

**New in v2.1.0:**
- ✨ Source document validation (token-based matching)
- ✨ TOC validation against source pages
- ✨ Term dictionary validation
- ✨ Cassandra content validation
- ✨ HGRN output structure (machine + human readable)

**Validation Components:**
1. **MongoDB**: Dictionary quality, term accuracy, category assignments
2. **Cassandra**: Metadata consistency, chunk text validation, embedding integrity
3. **Neo4j**: Graph structure, orphan nodes, relationship cycles
4. **Source**: TOC page matching, term presence verification

**Usage:**
```bash
# Basic validation
pass_f_consistency_check.py /Transfer_Station/Gate_0_Out/document_id.json

# With source validation
pass_f_consistency_check.py /Transfer_Station/Gate_0_Out/document_id.json \
  --source-file /Transfer_Station/sources/document.pdf \
  --threshold 0.90
```

**Output Structure:**
```
Pass_F_Out/
├── {document_id}_pass_f_manifest.json      # Validation scores
├── {document_id}_remediation_plan.json     # Database fixes
└── {document_id}/
    ├── hgrn_db_remediations.json           # Machine-readable
    └── hgrn_pipeline_suggestions.md        # Human-readable
```

**Exit Codes:**
- `0`: Passed validation threshold
- `1`: Failed validation threshold
- `2`: Connection error (MongoDB/Cassandra/Neo4j)
- `3`: Invalid input

---

## Configuration Guide

### Central Configuration: ingestion.cfg

**Location:** `./ingestion/ingestion.cfg`

**Sections:**
- `[Gate_0]` - Output directory
- `[Pass_A]` - Unstructured.io settings, MongoDB config
- `[Pass_B]` - Page range settings
- `[Pass_C]` - Game system detection, MongoDB config
- `[Pass_D]` - OpenAI embeddings, Cassandra config, chunking parameters
- `[Pass_E]` - Neo4j config, similarity settings
- `[Pass_F]` - Validation thresholds, database connections, HGRN options

**Type-Safe Access:**
```python
from config_loader import load_config, get_pass_d_config

config = load_config()  # Loads ./ingestion.cfg
pass_d_cfg = get_pass_d_config(config)

embedding_model = pass_d_cfg['embedding_model']
batch_size = pass_d_cfg['batch_size']
```

### Environment Variables: .env

**Location:** Project root (gitignored)

**Required Variables:**
```bash
# OpenAI API (Pass D)
OPENAI_API_KEY=sk-proj-...

# Neo4j Authentication (Pass F)
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

**IMPORTANT:** Never commit `.env` to version control!

---

## API Reference

### Unstructured.io API

**Endpoint:** `http://localhost:9006`
**Purpose:** Document parsing and element extraction

**Common Strategies:**
- `hi_res`: High-resolution OCR (comprehensive)
- `fast`: Fast processing without OCR
- `toc_pages`: TOC extraction only

### Hayhooks API

**Endpoint:** `http://localhost:9007`
**Purpose:** Haystack pipeline execution

### LangFlow API

**Endpoint:** `http://localhost:9010`
**Purpose:** Visual AI workflow builder

### HGRN API

**Endpoint:** `http://localhost:9013`
**Purpose:** Consistency validation

**Endpoints:**
- `GET /health` - Health check
- `POST /validate/document` - Document validation

---

## Development Setup

### Prerequisites

- Docker Desktop with E: drive access
- Windows 10/11 or WSL2
- NVIDIA GPU (optional, for HGRN)
- 16GB+ RAM recommended
- 50GB+ free disk space

### Initial Setup

```bash
# 1. Clone repository
git clone <repository_url>
cd n8n_TTRPG_Center

# 2. Create Transfer Station directory
mkdir E:\n8n_TTRPG_Transfer_Station

# 3. Create .env file
cp .env.example .env
# Edit .env with your API keys

# 4. Start services
docker compose -f docker-compose-n8n_TTRPG.yml up -d

# 5. Verify health
docker ps
```

### Custom Node Development

**Location:** `n8n-nodes-pdf-slice/`

```bash
# Build node
cd n8n-nodes-pdf-slice
npm install
npm run build

# Install to n8n
docker cp dist n8n_TTRPG_n8n:/home/node/.n8n/custom/n8n-nodes-pdf-slice/
docker restart n8n_TTRPG_n8n
```

---

## Testing Guide

### Manual Testing

**Complete Pipeline Test:**
```bash
# 1. Gate 0
DOC_ID=$(gate_0_hash.py /Transfer_Station/sources/test.pdf --quiet)

# 2. Pass A
pass_a_unstructured.py --toc-only /Transfer_Station/sources/test.pdf
pass_a_metadata.py /Transfer_Station/Pass_A_Out/test_toc_elements.json \
  --gate-marker /Transfer_Station/Gate_0_Out/${DOC_ID}.json
pass_a_mongo_upsert.py \
  /Transfer_Station/Pass_A_Out/test_elements.json \
  /Transfer_Station/Pass_A_Out/test_metadata.json

# 3. Verify MongoDB
db_manager.py --summarize --db mongo
```

### Database Validation

```bash
# Summarize all databases
db_manager.py --summarize

# Check specific database
db_manager.py --summarize --db mongo

# Count Cassandra chunks
db_manager.py --count-document <document_id> --cassandra-keyspace ttrpg_vectors --cassandra-table embeddings

# List Cassandra partitions (sample 20 documents)
db_manager.py --list-partitions --partition-limit 20
```

### Dry Run Mode

Most scripts support `--dry-run`:
```bash
pass_f_consistency_check.py <marker> --dry-run
clear_document.py <document_id> --dry-run
```

---

## Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check health
docker ps

# View logs
docker compose -f docker-compose-n8n_TTRPG.yml logs -f <service_name>
```

**Startup delays:**
- Cassandra: ~40 seconds (highest)
- Neo4j: ~30 seconds
- Stargate: Waits for Cassandra healthy

**Custom node not appearing:**
1. Rebuild: `npm run build` in `n8n-nodes-pdf-slice/`
2. Copy dist: `docker cp dist n8n_TTRPG_n8n:/home/node/.n8n/custom/`
3. Restart: `docker restart n8n_TTRPG_n8n`

**Transfer Station file not found:**
- Verify path: `E:/n8n_TTRPG_Transfer_Station`
- Docker Desktop: Check E: drive access in Settings
- Use absolute paths in containers: `/Transfer_Station/...`

**Database connection issues:**
- Check service health: `docker ps`
- Verify ports: See [Service Ports](#service-ports)
- Check logs: `docker logs <container_name>`

### Debug Commands

```bash
# Container shell access
docker exec -it n8n_TTRPG_ingestion_engine bash

# Database shells
docker exec -it n8n_TTRPG_mongodb mongosh
docker exec -it n8n_TTRPG_cassandra cqlsh
docker exec -it n8n_TTRPG_neo4j cypher-shell -u neo4j -p password

# Service health checks
curl http://localhost:9000  # n8n
curl http://localhost:9013/health  # HGRN
```

---

## Contributing

### Development Guidelines

**Code Style:**
- Python: PEP 8 compliance
- TypeScript: ES2020 modules with ESM imports
- All scripts: Support `-v|--version` and `-?|--help`

**Script Structure:**
```python
#!/usr/bin/env python3
"""
script_name.py - Brief Description
================================

Detailed description here.
"""

__version__ = "1.0.0"

# Imports
# Constants
# Functions
# CLI

if __name__ == "__main__":
    sys.exit(main())
```

**Configuration:**
- Add new settings to `ingestion.cfg`
- Update `config_loader.py` with type-safe accessors
- Document in CLAUDE.md

**Documentation:**
- Update CLAUDE.md for architecture changes
- Update scripts-reference.md for new scripts
- Add examples to docs/

---

## Additional Resources

### Documentation Files

| File | Purpose |
|------|---------|
| [CLAUDE.md](../CLAUDE.md) | Quick reference for Claude Code |
| [scripts-reference.md](scripts-reference.md) | Comprehensive script documentation |
| [docker-commands.md](docker-commands.md) | Docker operations reference |
| [troubleshooting.md](troubleshooting.md) | Detailed troubleshooting guide |
| [ingestion-pipeline.md](ingestion-pipeline.md) | Pipeline architecture details |

### Analysis Reports

| Report | Purpose |
|--------|---------|
| [ANALYSIS_REPORT.md](../claudedocs/ANALYSIS_REPORT.md) | Comprehensive code analysis (4.5/5) |
| [PASS_F_v2.1_UPGRADE_ANALYSIS.md](../claudedocs/PASS_F_v2.1_UPGRADE_ANALYSIS.md) | Pass F upgrade features (A grade) |

### External Links

- [n8n Documentation](https://docs.n8n.io/)
- [Unstructured.io Docs](https://unstructured-io.github.io/unstructured/)
- [Haystack Documentation](https://haystack.deepset.ai/)
- [Neo4j Documentation](https://neo4j.com/docs/)
- [Cassandra Documentation](https://cassandra.apache.org/doc/)

---

## Version History

### v1.0.0 (2025-10-11)
- Initial comprehensive knowledge base
- Complete pipeline documentation (Gate 0 - Pass F)
- Architecture patterns and design decisions
- Configuration and API reference
- Development setup and troubleshooting guide

---

**End of Index** | [Back to Top](#n8n-ttrpg-center---project-knowledge-base-index)

