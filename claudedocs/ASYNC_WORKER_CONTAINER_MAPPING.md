# Async Worker Container Mapping

**Complete breakdown of all 15 workers and their production container assignments**

**Architecture**: Production-ready with 15 workers distributed across 7 specialized containers

---

## Production Architecture (7 Containers)

### Container 1: ttrpg_ingestion_engine

**Purpose**: Common tools, pipeline management, gates (7 workers)**

### Location
- Worker scripts: `/Transfer_Station/scripts/*_worker.py`
- Python environment: System Python 3
- Shared volume: `/Transfer_Station` (mounted from host)
- Image: python:3.11-slim

### Workers Running (7 total)

#### Gate 0 Workers (3 workers)
```
1. gate_0_hash_worker.py
   - Purpose: SHA-256 hash calculation + document_id generation
   - Timeout: None (runs until complete)
   - Script: /Transfer_Station/scripts/gate_0_hash.py
   - Input: Source PDF from /Transfer_Station/sources/
   - Output: document_id, sha256_hash
   - Next stage: gate_0_validate

2. gate_0_validate_worker.py
   - Purpose: Cassandra validation + routing decision
   - Timeout: None (runs until complete)
   - Script: /Transfer_Station/scripts/gate_0_validate.py
   - Input: document_id from gate_0_hash
   - Output: validation status (unprocessed/exists/needs_reprocess)
   - Next stage: doc_splitter OR pass_a_unstructured (conditional)

3. doc_splitter_worker.py
   - Purpose: TOC extraction (optional stage)
   - Timeout: None (runs until complete)
   - Script: /Transfer_Station/scripts/doc_splitter.py
   - Input: Source PDF
   - Output: toc_extracted flag
   - Next stage: pass_a_unstructured
   - Note: Conditional - only runs if configured
```

#### Pass A Workers (1 worker)
```
4. pass_a_metadata_worker.py
   - Purpose: Extract TOC metadata from Unstructured elements
   - Timeout: 300s (5 minutes)
   - Script: /Transfer_Station/scripts/pass_a_metadata.py
   - Input: pass_a_unstructured_output (elements JSON)
   - Output: metadata JSON (TOC, categories, terms)
   - Next stage: pass_a_mongo_upsert
   - Dependencies: Unstructured.io elements
   - Container: ttrpg_ingestion_engine (common tool)
```

#### Pass D Workers (0 workers - moved to specialized containers)
```
MOVED TO SPECIALIZED CONTAINERS (see below)
```

#### Pass E Workers (0 workers - moved to llamaindex container)
```
MOVED TO ttrpg_llamaindex CONTAINER (see below)
```

#### Pass F Worker (0 workers - moved to hgrn container)
```
MOVED TO ttrpg_hgrn CONTAINER (see below)
```

#### Gate 1 Workers (3 workers)
```
5. gate_1_log_analyzer_worker.py
   - Purpose: Analyze ingestion logs using OpenAI GPT-4o
   - Timeout: 600s (10 minutes)
   - Script: /Transfer_Station/scripts/gate_1_log_analyzer.py
   - Input: ingestion log file
   - Output: Issue analysis + remediation prompts
   - Next stage: gate_1_db_remediation
   - External service: OpenAI API (GPT-4o)
   - Optional: Non-critical, returns True on failure
   - Container: ttrpg_ingestion_engine (common tool)

6. gate_1_pipeline_optimizer_worker.py
   - Purpose: Generate pipeline optimization prompts using OpenAI
   - Timeout: 600s (10 minutes)
   - Script: /Transfer_Station/scripts/gate_1_pipeline_optimizer.py
   - Input: hgrn_pipeline_suggestions.md
   - Output: Optimization prompts
   - Next stage: gate_1_cleanup
   - External service: OpenAI API (GPT-4o-mini)
   - Optional: Non-critical, returns True on failure
   - Container: ttrpg_ingestion_engine (common tool)

7. gate_1_cleanup_worker.py
   - Purpose: Clean up temporary artifacts after successful pipeline
   - Timeout: 300s (5 minutes)
   - Script: /Transfer_Station/scripts/gate_1_cleanup.py
   - Input: document_id
   - Output: Cleanup statistics (deleted files, reclaimed space)
   - Next stage: complete/
   - Container: ttrpg_ingestion_engine (common tool)
```

---

## Container 2: ttrpg_unstructured

**Separate container running 1 specialized worker (unchanged from original architecture)**

### Location
- Worker script: `/opt/ingestion/unstructured_job_worker.py`
- Python environment: Custom environment with Unstructured.io
- Shared volume: `/Transfer_Station` (mounted from host)

### Worker Running (1 total)

```
1. unstructured_job_worker.py (pass_a_unstructured)
   - Purpose: Process PDFs using Unstructured.io API
   - Timeout: Variable (depends on PDF size/complexity)
   - Script: /opt/ingestion/pass_a_unstructured.py (wrapped)
   - Input: Source PDF from /Transfer_Station/sources/
   - Output: Elements JSON (structured document elements)
   - Next stage: pass_a_metadata
   - External service: Unstructured.io API
   - Job directory: /Transfer_Station/jobs/unstructured/
   - Log directory: /Transfer_Station/Logs/unstructured/
   - Note: Runs in separate container due to special dependencies
```

---

## Container 3: ttrpg_mongodb

**MongoDB upsert operations (1 worker)**

### Location
- Worker script: `/opt/workers/pass_a_mongo_upsert_worker.py`
- Python environment: Python 3 + pip (installed via install_python_db_containers.sh)
- Shared volume: `/Transfer_Station` (mounted from host)
- Image: mongo:6.0 + Python 3

### Worker Running (1 total)

```
1. pass_a_mongo_upsert_worker.py
   - Purpose: Upsert elements and metadata to MongoDB
   - Timeout: 600s (10 minutes)
   - Script: /opt/workers/pass_a_mongo_upsert.py
   - Input: elements JSON + metadata JSON
   - Output: mongodb_upserted flag
   - Next stage: pass_d_checksum
   - Database: ttrpg_mongodb (local)
   - Rebuild mode: Supports --gate-marker flag
```

---

## Container 4: ttrpg_cassandra

**Cassandra checksum operations (1 worker)**

### Location
- Worker script: `/opt/workers/pass_d_checksum_worker.py`
- Python environment: Python 3 + pip (installed via install_python_db_containers.sh)
- Shared volume: `/Transfer_Station` (mounted from host)
- Image: cassandra:5.0 + Python 3

### Worker Running (1 total)

```
1. pass_d_checksum_worker.py
   - Purpose: Write Gate 0 checksum files
   - Timeout: 60s (1 minute)
   - Script: /opt/workers/pass_d_checksum.py
   - Input: pass_d_manifest_output
   - Output: checksum JSON file
   - Next stage: pass_d_hayhooks
   - Database: Cassandra (local checksum records)
```

---

## Container 5: ttrpg_hayhooks

**OpenAI embedding generation (1 worker)**

### Location
- Worker script: `/opt/workers/pass_d_hayhooks_worker.py`
- Python environment: Python 3 (pre-installed in hayhooks image)
- Shared volume: `/Transfer_Station` (mounted from host)
- Image: deepset/hayhooks:v0.4.0

### Worker Running (1 total)

```
1. pass_d_hayhooks_worker.py
   - Purpose: Generate OpenAI embeddings via hayhooks service
   - Timeout: 7200s (2 HOURS - longest worker!)
   - Script: /opt/workers/pass_d_hayhooks.py
   - Input: pass_b_manifest_output
   - Output: embeddings in Cassandra
   - Next stage: pass_e_graph_builder
   - External service: hayhooks HTTP API (OpenAI)
   - Database: ttrpg_cassandra (vector storage)
   - Rebuild mode: Supports --gate-marker flag
   - Note: This is the bottleneck stage (2-hour timeout)
```

---

## Container 6: ttrpg_llamaindex

**Knowledge graph building with LlamaIndex (2 workers)**

### Location
- Worker scripts: `/opt/workers/*_worker.py`
- Python environment: Python 3.11 + LlamaIndex
- Shared volume: `/Transfer_Station` (mounted from host)
- Image: n8n_ttrpg_llamaindex:latest (custom build)

### Workers Running (2 total)

```
1. pass_e_graph_builder_worker.py
   - Purpose: Build knowledge graph from Cassandra vectors
   - Timeout: 1800s (30 minutes)
   - Script: /opt/workers/pass_e_graph_builder.py
   - Input: pass_d_manifest_output
   - Output: graph JSON (nodes + edges)
   - Next stage: pass_e_neo4j_upsert
   - Database: Reads from ttrpg_cassandra
   - Optional: --enable-similarity flag for semantic edges

2. pass_e_neo4j_upsert_worker.py
   - Purpose: Upsert graph nodes and edges to Neo4j
   - Timeout: 1800s (30 minutes)
   - Script: /opt/workers/pass_e_neo4j_upsert.py
   - Input: pass_e_graph_output (graph JSON)
   - Output: neo4j_upserted flag
   - Next stage: pass_f_validation
   - Database: ttrpg_neo4j
   - Rebuild mode: Supports --gate-marker flag
   - Note: Creates indexes on first run, future migration to ttrpg_neo4j container
```

---

## Container 7: ttrpg_hgrn

**HGRN validation and remediation (2 workers)**

### Location
- Worker scripts: `/opt/workers/*_worker.py`
- Python environment: Python 3 + PyTorch + CUDA
- Shared volume: `/Transfer_Station` (mounted from host)
- Image: pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime
- GPU: NVIDIA GPU required

### Workers Running (2 total)

```
1. pass_f_validation_worker.py
   - Purpose: Cross-store validation (MongoDB ↔ Cassandra ↔ Neo4j)
   - Timeout: 1800s (30 minutes)
   - Script: /opt/workers/pass_f_consistency_check.py
   - Input: document_id
   - Output: HGRN validation reports + remediation files
   - Next stage: gate_1_log_analyzer
   - Databases: Validates all 3 (MongoDB, Cassandra, Neo4j)
   - HGRN files:
     * {document_id}_hgrn_report.json
     * {document_id}_hgrn_db_remediations.json
     * {document_id}_hgrn_pipeline_suggestions.md

2. gate_1_db_remediation_worker.py
   - Purpose: Execute database remediation commands from HGRN
   - Timeout: 1800s (30 minutes)
   - Script: /opt/workers/gate_1_db_remediation_executor.py
   - Input: hgrn_db_remediations.json
   - Output: Executed commands + checksum regeneration
   - Next stage: gate_1_pipeline_optimizer
   - Databases: Can modify MongoDB, Cassandra, Neo4j
   - Optional: Non-critical, returns True on failure
   - Note: Uses --no-confirm flag for automation
```

---

## Supporting Service Containers (No Workers)

### Database Containers
```
1. ttrpg_mongodb
   - Purpose: Store document elements and metadata
   - Collections: documents, elements, metadata
   - Used by: pass_a_mongo_upsert_worker, pass_f_validation_worker

2. ttrpg_cassandra
   - Purpose: Store checksums and vector embeddings
   - Tables: checksums, chunk_vectors
   - Used by: gate_0_validate_worker, pass_d_checksum_worker,
             pass_d_hayhooks_worker, pass_e_graph_builder_worker,
             pass_f_validation_worker

3. ttrpg_neo4j
   - Purpose: Store knowledge graph (nodes + relationships)
   - Labels: Document, Chunk, Entity, etc.
   - Used by: pass_e_neo4j_upsert_worker, pass_f_validation_worker
```

### Processing Service Containers
```
4. ttrpg_hayhooks
   - Purpose: Generate OpenAI embeddings
   - API: Haystack pipelines via HTTP
   - Used by: pass_d_hayhooks_worker (calls via HTTP)

5. ttrpg_hgrn
   - Purpose: HGRN validation and remediation logic
   - Used by: pass_f_validation_worker (generates HGRN files)
```

### Other Containers (Not Used by Workers)
```
6. ttrpg_stargate
   - Purpose: Cassandra Stargate API (alternative access)
   - Status: Not currently used by async workers

7. ttrpg_n8n
   - Purpose: Workflow automation (legacy)
   - Status: Not used by async pipeline

8. ttrpg_langflow
   - Purpose: LLM flow builder (experimental)
   - Status: Not used by async pipeline

9. ttrpg_postgres
   - Purpose: PostgreSQL database
   - Status: Not currently used by async workers

10. ttrpg_webui
    - Purpose: Web interface
    - Status: Not involved in async processing
```

---

## Worker Launch Commands

### Start All Workers on ttrpg_ingestion_engine

Using the orchestration script:
```bash
docker exec ttrpg_ingestion_engine bash /Transfer_Station/scripts/start_all_workers.sh
```

This single command starts all 13 workers in `ttrpg_ingestion_engine` container.

### Start Unstructured Worker (Separate)

The unstructured worker is typically already running. If not:
```bash
docker exec -d ttrpg_unstructured sh -c \
  "cd /opt/ingestion && python3 unstructured_job_worker.py \
   --jobs-dir /Transfer_Station/jobs/unstructured \
   --log-dir /Transfer_Station/Logs/unstructured \
   --poll-interval 5"
```

### Start Individual Workers (Advanced)

If you need to start workers individually on ttrpg_ingestion_engine:
```bash
# Example: Start just gate_0_hash_worker
docker exec -d ttrpg_ingestion_engine bash -c \
  "cd /Transfer_Station/scripts && python3 gate_0_hash_worker.py \
   --jobs-dir /Transfer_Station/jobs \
   --log-dir /Transfer_Station/Logs \
   --poll-interval 5"
```

---

## Process Monitoring

### Check Workers in ttrpg_ingestion_engine
```bash
docker exec ttrpg_ingestion_engine ps aux | grep worker
```

Expected output: 13 Python processes running `*_worker.py`

### Check Worker in ttrpg_unstructured
```bash
docker exec ttrpg_unstructured ps aux | grep unstructured_job_worker
```

Expected output: 1 Python process running `unstructured_job_worker.py`

### View Worker Logs
```bash
# Logs for ttrpg_ingestion_engine workers
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/gate_0_hash/worker.log

# Logs for ttrpg_unstructured worker
docker exec ttrpg_unstructured tail -f /Transfer_Station/Logs/unstructured/worker.log
```

### Check Heartbeats
```bash
# All heartbeats
cat /e/n8n_TTRPG_Transfer_Station/Logs/*/heartbeat.json

# Specific worker heartbeat
cat /e/n8n_TTRPG_Transfer_Station/Logs/gate_0_hash/heartbeat.json
```

---

## Container Resource Requirements

### ttrpg_ingestion_engine
- **CPU**: High (13 concurrent workers)
- **Memory**: 4-8 GB (depends on concurrent jobs)
- **Disk I/O**: High (frequent file operations)
- **Network**: Medium (database connections)

### ttrpg_unstructured
- **CPU**: Medium (1 worker, CPU-intensive PDF processing)
- **Memory**: 2-4 GB (Unstructured.io library)
- **Disk I/O**: Medium (PDF reading, JSON writing)
- **Network**: High (Unstructured.io API calls)

---

## Worker Dependency Chain

```
Container: ttrpg_ingestion_engine
  gate_0_hash_worker
    ↓
  gate_0_validate_worker
    ↓
  doc_splitter_worker (optional)
    ↓
Container: ttrpg_unstructured
  unstructured_job_worker
    ↓
Container: ttrpg_ingestion_engine
  pass_a_metadata_worker
    ↓
  pass_a_mongo_upsert_worker
    ↓
  pass_d_checksum_worker
    ↓
  pass_d_hayhooks_worker (2-hour bottleneck)
    ↓
  pass_e_graph_builder_worker
    ↓
  pass_e_neo4j_upsert_worker
    ↓
  pass_f_validation_worker
    ↓
  gate_1_log_analyzer_worker (optional)
    ↓
  gate_1_db_remediation_worker (optional)
    ↓
  gate_1_pipeline_optimizer_worker (optional)
    ↓
  gate_1_cleanup_worker
    ↓
  COMPLETE
```

---

## Critical vs Optional Workers

### Critical Workers (11)
**Must succeed for pipeline to complete**

Container: `ttrpg_ingestion_engine` (10)
- gate_0_hash_worker
- gate_0_validate_worker
- pass_a_metadata_worker
- pass_a_mongo_upsert_worker
- pass_d_checksum_worker
- pass_d_hayhooks_worker
- pass_e_graph_builder_worker
- pass_e_neo4j_upsert_worker
- pass_f_validation_worker
- gate_1_cleanup_worker

Container: `ttrpg_unstructured` (1)
- unstructured_job_worker

### Optional Workers (3)
**Can fail without blocking pipeline**

Container: `ttrpg_ingestion_engine` (3)
- doc_splitter_worker (conditional execution)
- gate_1_log_analyzer_worker (OpenAI analysis)
- gate_1_db_remediation_worker (auto-remediation)
- gate_1_pipeline_optimizer_worker (optimization prompts)

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Total Workers** | **15** |
| **Total Containers** | **7** |
| Workers in ttrpg_ingestion_engine | 7 |
| Workers in ttrpg_unstructured | 1 |
| Workers in ttrpg_mongodb | 1 |
| Workers in ttrpg_cassandra | 1 |
| Workers in ttrpg_hayhooks | 1 |
| Workers in ttrpg_llamaindex | 2 |
| Workers in ttrpg_hgrn | 2 |
| Critical Workers | 11 |
| Optional Workers | 4 |
| Workers with Rebuild Mode | 3 |
| Workers calling OpenAI | 2 |
| Workers with External Services | 3 |
| Longest Timeout | 7200s (2 hours) |
| Shortest Timeout | 60s (1 minute) |
| Total Database Connections | 3 (MongoDB, Cassandra, Neo4j) |

---

## Production Deployment Commands

### Build and Start Infrastructure

```bash
# 1. Build LlamaIndex container
docker compose -f docker-compose-ttrpg.yml build llamaindex

# 2. Start all containers
docker compose -f docker-compose-ttrpg.yml up -d

# 3. Install Python in database containers
bash scripts/install_python_db_containers.sh
```

### Deploy and Start Workers

```bash
# 1. Deploy workers to all containers
bash scripts/deploy_workers_production.sh

# 2. Start all workers
bash scripts/start_all_workers_production.sh
```

### Monitoring

```bash
# Check all workers across containers
docker exec ttrpg_ingestion_engine ps aux | grep worker
docker exec ttrpg_mongodb ps aux | grep worker
docker exec ttrpg_cassandra ps aux | grep worker
docker exec ttrpg_hayhooks ps aux | grep worker
docker exec ttrpg_llamaindex ps aux | grep worker
docker exec ttrpg_hgrn ps aux | grep worker
docker exec ttrpg_unstructured ps aux | grep worker
```
