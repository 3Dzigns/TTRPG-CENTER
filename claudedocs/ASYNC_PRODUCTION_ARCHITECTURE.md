# Production Async Pipeline Architecture

**Date**: 2025-10-24
**Status**: Implementation Complete - Ready for Deployment

---

## Overview

Production-ready async pipeline architecture with **15 workers distributed across 7 specialized containers** for independent scalability and resource optimization.

### Key Benefits

- **Independent Scaling**: Each container can scale based on resource needs
- **Resource Optimization**: Specialized containers match worker requirements
- **Production Ready**: Designed for node-based deployment with different capacities
- **Fault Isolation**: Worker failures contained to specific containers

---

## Container Distribution

### Container 1: ttrpg_ingestion_engine (7 workers)
**Purpose**: Common tools, pipeline management, gates
**Image**: python:3.11-slim
**Workers**:
- gate_0_hash_worker
- gate_0_validate_worker
- doc_splitter_worker
- pass_a_metadata_worker
- gate_1_log_analyzer_worker
- gate_1_pipeline_optimizer_worker
- gate_1_cleanup_worker

### Container 2: ttrpg_unstructured (1 worker)
**Purpose**: Unstructured.io PDF processing
**Image**: downloads.unstructured.io/unstructured-io/unstructured-api:latest
**Workers**:
- unstructured_job_worker

### Container 3: ttrpg_mongodb (1 worker)
**Purpose**: MongoDB upserts
**Image**: mongo:6.0 + Python 3
**Workers**:
- pass_a_mongo_upsert_worker

### Container 4: ttrpg_cassandra (1 worker)
**Purpose**: Cassandra checksum operations
**Image**: cassandra:5.0 + Python 3
**Workers**:
- pass_d_checksum_worker

### Container 5: ttrpg_hayhooks (1 worker)
**Purpose**: OpenAI embedding generation
**Image**: deepset/hayhooks:v0.4.0
**Workers**:
- pass_d_hayhooks_worker (2-hour timeout - bottleneck)

### Container 6: ttrpg_llamaindex (2 workers)
**Purpose**: Knowledge graph building with LlamaIndex
**Image**: n8n_ttrpg_llamaindex:latest
**Workers**:
- pass_e_graph_builder_worker
- pass_e_neo4j_upsert_worker

### Container 7: ttrpg_hgrn (2 workers)
**Purpose**: HGRN validation and remediation
**Image**: pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime
**Workers**:
- pass_f_validation_worker
- gate_1_db_remediation_worker

---

## Deployment Process

### Phase 1: Prepare Infrastructure

```bash
# 1. Build LlamaIndex container
cd /e/n8n_TTRPG_Center
docker compose -f docker-compose-ttrpg.yml build llamaindex

# 2. Start all containers
docker compose -f docker-compose-ttrpg.yml up -d

# 3. Install Python in database containers
bash scripts/install_python_db_containers.sh
```

### Phase 2: Deploy Workers

```bash
# Deploy workers and base infrastructure to all containers
bash scripts/deploy_workers_production.sh
```

**What this does**:
- Copies AsyncWorkerBase, async_job_utils.py, path_utils.py to each container
- Deploys workers to designated containers
- Copies synchronous scripts dependencies
- Validates container availability

### Phase 3: Start Workers

```bash
# Start all 15 workers across 7 containers
bash scripts/start_all_workers_production.sh
```

**What this does**:
- Launches workers in background with proper logging
- Configures job directories and poll intervals
- Sets up log rotation paths
- Provides monitoring commands

---

## Worker-to-Container Mapping Table

| Worker | Container | Purpose | Timeout |
|--------|-----------|---------|---------|
| gate_0_hash_worker | ingestion_engine | SHA-256 hashing | None |
| gate_0_validate_worker | ingestion_engine | Cassandra validation | None |
| doc_splitter_worker | ingestion_engine | TOC extraction | None |
| unstructured_job_worker | unstructured | Unstructured.io | Variable |
| pass_a_metadata_worker | ingestion_engine | Metadata extraction | 300s |
| pass_a_mongo_upsert_worker | mongodb | MongoDB upsert | 600s |
| pass_d_checksum_worker | cassandra | Checksum writing | 60s |
| pass_d_hayhooks_worker | hayhooks | Embedding generation | 7200s |
| pass_e_graph_builder_worker | llamaindex | Graph building | 1800s |
| pass_e_neo4j_upsert_worker | llamaindex | Neo4j upsert | 1800s |
| pass_f_validation_worker | hgrn | Cross-store validation | 1800s |
| gate_1_log_analyzer_worker | ingestion_engine | Log analysis (optional) | 600s |
| gate_1_db_remediation_worker | hgrn | DB remediation (optional) | 1800s |
| gate_1_pipeline_optimizer_worker | ingestion_engine | Optimization (optional) | 600s |
| gate_1_cleanup_worker | ingestion_engine | Artifact cleanup | 300s |

---

## Resource Requirements

### High Resource Containers

**ttrpg_llamaindex**: 4GB RAM, 2 CPU cores
- Runs 2 graph processing workers
- LlamaIndex + vector operations
- Neo4j client libraries

**ttrpg_hgrn**: 8GB RAM, 1 GPU
- Runs 2 validation/remediation workers
- PyTorch + CUDA operations
- Cross-store validation

**ttrpg_hayhooks**: 2GB RAM, 2 CPU cores
- Runs 1 embedding worker (2-hour timeout)
- OpenAI API calls
- High network I/O

### Medium Resource Containers

**ttrpg_ingestion_engine**: 2GB RAM, 2 CPU cores
- Runs 7 workers (gates + common tools)
- Python 3.11 + standard libraries
- High file I/O

**ttrpg_unstructured**: 4GB RAM, 2 CPU cores
- Runs 1 worker (PDF processing)
- Unstructured.io library
- CPU-intensive operations

### Low Resource Containers

**ttrpg_mongodb**: 2GB RAM, 1 CPU
- Runs 1 worker (upsert operations)
- MongoDB + Python 3
- Database connections

**ttrpg_cassandra**: 2GB RAM, 1 CPU
- Runs 1 worker (checksum operations)
- Cassandra + Python 3
- Database connections

---

## Monitoring

### Check All Workers

```bash
# Check workers in each container
docker exec ttrpg_ingestion_engine ps aux | grep worker
docker exec ttrpg_mongodb ps aux | grep worker
docker exec ttrpg_cassandra ps aux | grep worker
docker exec ttrpg_hayhooks ps aux | grep worker
docker exec ttrpg_llamaindex ps aux | grep worker
docker exec ttrpg_hgrn ps aux | grep worker
docker exec ttrpg_unstructured ps aux | grep worker
```

### View Logs

```bash
# Container-specific logs
docker exec ttrpg_ingestion_engine tail -f /Transfer_Station/Logs/gate_0_hash/worker.log
docker exec ttrpg_mongodb tail -f /Transfer_Station/Logs/pass_a_mongo_upsert/worker.log
docker exec ttrpg_llamaindex tail -f /Transfer_Station/Logs/pass_e_graph_builder/worker.log
docker exec ttrpg_hgrn tail -f /Transfer_Station/Logs/pass_f_validation/worker.log
```

### Heartbeat Monitoring

```bash
# Check heartbeats for all workers
cat /e/n8n_TTRPG_Transfer_Station/Logs/*/heartbeat.json | jq .
```

---

## Scaling Strategy

### Horizontal Scaling (Multiple Instances)

**Same Worker Type Across Nodes**:
```bash
# Node 1: Run core ingestion
docker-compose up -d ingestion_engine unstructured mongodb

# Node 2: Run graph processing
docker-compose up -d llamaindex cassandra neo4j

# Node 3: Run validation
docker-compose up -d hgrn hayhooks
```

### Vertical Scaling (Resource Allocation)

**Increase Container Resources**:
```yaml
# docker-compose-ttrpg.yml
services:
  llamaindex:
    mem_limit: 8g  # Increase from 4g
    cpus: 4        # Increase from 2
```

---

## Migration from Original Architecture

### Before (2-Container Architecture)
- ttrpg_ingestion_engine: 13 workers
- ttrpg_unstructured: 1 worker
- **Total**: 14 workers in 2 containers

### After (7-Container Architecture)
- ttrpg_ingestion_engine: 7 workers (gates + common)
- ttrpg_unstructured: 1 worker (unchanged)
- ttrpg_mongodb: 1 worker (new)
- ttrpg_cassandra: 1 worker (new)
- ttrpg_hayhooks: 1 worker (new)
- ttrpg_llamaindex: 2 workers (new)
- ttrpg_hgrn: 2 workers (new)
- **Total**: 15 workers in 7 containers

---

## Files Created

### Deployment Scripts
- `scripts/deploy_workers_production.sh` - Deploy workers to containers
- `scripts/start_all_workers_production.sh` - Start all workers
- `scripts/install_python_db_containers.sh` - Install Python in DB containers

### Docker Configuration
- `docker/llamaindex/Dockerfile` - LlamaIndex container image
- `docker-compose-ttrpg.yml` - Updated with llamaindex service

### Documentation
- `claudedocs/ASYNC_PRODUCTION_ARCHITECTURE.md` - This file

---

## Next Steps

### Immediate
1. Build LlamaIndex container
2. Install Python in database containers
3. Deploy workers to all containers
4. Start all workers
5. Test with sample PDF

### Testing
1. Queue test job via ingestion_wrapper_async
2. Monitor worker progression across containers
3. Validate database writes in all 3 stores
4. Check HGRN validation reports
5. Verify cleanup completion

### Production Deployment
1. Set up node-specific resource allocation
2. Configure horizontal scaling for bottleneck stages
3. Implement centralized monitoring dashboard
4. Set up alerting for worker failures
5. Configure log aggregation across containers

---

## Troubleshooting

### Worker Not Starting
```bash
# Check if container is running
docker ps | grep ttrpg_

# Check worker deployment
docker exec <container> ls -la /opt/workers/

# Check Python installation (database containers)
docker exec <container> python3 --version
```

### Worker Failing
```bash
# Check worker logs
docker exec <container> tail -100 /Transfer_Station/Logs/<stage>/worker.log

# Check job status
cat /e/n8n_TTRPG_Transfer_Station/jobs/<stage>/<job_id>/status.json
```

### Container Resource Issues
```bash
# Check container stats
docker stats <container_name>

# Increase resources in docker-compose-ttrpg.yml
```

---

**Status**: ✅ Implementation Complete - Ready for Deployment
**Last Updated**: 2025-10-24
**Next**: Build and test production deployment
