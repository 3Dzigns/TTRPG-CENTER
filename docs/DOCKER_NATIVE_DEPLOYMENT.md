# Docker-Native Worker Deployment

## Overview

This document describes the Docker-native worker architecture where all 15 async workers auto-deploy and auto-start when containers launch via `docker compose up`.

## Architecture Summary

### 6 Custom Worker Containers

Each container extends its base image (mongo:6.0, cassandra:5.0, etc.) with:
- Python 3.11 runtime
- supervisord for process management
- Async worker scripts + base infrastructure
- Auto-restart on failure
- Health checks for database + worker status

### Worker Distribution

| Container | Workers | Database |
|-----------|---------|----------|
| **ingestion_engine** | 8 workers | None (pure Python) |
| - source_monitor | Auto-discovery | |
| - gate_0_hash | Hash computation | |
| - gate_0_validate | PDF validation | |
| - doc_splitter | Document splitting | |
| - pass_a_metadata | Metadata extraction | |
| - gate_1_log_analyzer | Log analysis | |
| - gate_1_pipeline_optimizer | Pipeline optimization | |
| - gate_1_cleanup | Cleanup operations | |
| **mongodb** | 1 worker | MongoDB 6.0 |
| - pass_a_mongo_upsert | Element upsert | |
| **cassandra** | 1 worker | Cassandra 5.0 |
| - pass_d_checksum | Vector checksums | |
| **hayhooks** | 1 worker | Hayhooks v0.4.0 |
| - pass_d_hayhooks | Embeddings (2hr timeout) | |
| **llamaindex** | 2 workers | None |
| - pass_e_graph_builder | Graph construction | |
| - pass_e_neo4j_upsert | Graph upsert | |
| **hgrn** | 2 workers | PyTorch + CUDA |
| - pass_f_consistency_check | HGRN validation | |
| - gate_1_db_remediation | Remediation executor | |

**Total: 15 workers** managed by supervisord across 6 containers

## One-Command Deployment

```bash
docker compose -f docker-compose-ttrpg.yml up -d --build
```

This single command:
1. Builds 6 custom Docker images with embedded workers
2. Starts all containers with health checks
3. supervisord auto-starts all 15 workers
4. Workers poll job queues immediately
5. source_monitor waits 60s for pipeline ready, then starts polling sources/

## Health Checks

Each container has a health check that verifies:
- Database is running (for DB containers)
- Worker processes are RUNNING (via supervisorctl)

Example health checks:
```yaml
# ingestion_engine - verify 7 workers (excluding source_monitor)
test: ["CMD", "bash", "-c", "supervisorctl status | grep -E '(gate_0_hash|gate_0_validate|doc_splitter|pass_a_metadata|gate_1_log_analyzer|gate_1_pipeline_optimizer|gate_1_cleanup):RUNNING' | wc -l | grep -q '7'"]

# mongodb - verify MongoDB + worker
test: ["CMD", "bash", "-c", "mongosh --eval 'db.adminCommand(\"ping\")' && supervisorctl status pass_a_mongo_upsert | grep -q RUNNING"]

# cassandra - verify Cassandra + worker
test: ["CMD", "bash", "-c", "cqlsh -e 'SELECT release_version FROM system.local' && supervisorctl status pass_d_checksum | grep -q RUNNING"]
```

## Dependency Management

Containers use `depends_on` with `service_healthy` conditions:

```yaml
ingestion_engine:
  depends_on:
    mongodb:
      condition: service_healthy
    cassandra:
      condition: service_healthy
    neo4j:
      condition: service_healthy
```

This ensures:
- Database containers start and become healthy first
- Worker containers wait for dependencies
- source_monitor has 60s grace period via supervisord priority

## Supervisor Configuration

### Priority System
Workers have different startup priorities:
- **100-800**: Pipeline workers (start immediately)
- **999**: source_monitor (waits 60s via startsecs=60)

### Auto-Restart
All workers configured with:
```ini
autostart=true
autorestart=true
startretries=10
startsecs=30  # or 60 for source_monitor
```

### Log Management
Each worker has separate stdout/stderr logs:
```ini
stderr_logfile=/Transfer_Station/Logs/pass_d_checksum/supervisor_stderr.log
stdout_logfile=/Transfer_Station/Logs/pass_d_checksum/supervisor_stdout.log
```

## Monitoring Commands

### Check All Worker Status
```bash
# View supervisor status for each container
docker exec ttrpg_ingestion_engine supervisorctl status
docker exec ttrpg_mongodb supervisorctl status
docker exec ttrpg_cassandra supervisorctl status
docker exec ttrpg_hayhooks supervisorctl status
docker exec ttrpg_llamaindex supervisorctl status
docker exec ttrpg_hgrn supervisorctl status
```

### View Worker Logs
```bash
# Real-time logs via supervisor
docker exec ttrpg_ingestion_engine supervisorctl tail -f source_monitor stdout
docker exec ttrpg_mongodb supervisorctl tail -f pass_a_mongo_upsert stdout
docker exec ttrpg_cassandra supervisorctl tail -f pass_d_checksum stderr

# Or view Transfer Station logs
ls -lh /e/n8n_TTRPG_Transfer_Station/Logs/
```

### Restart Individual Workers
```bash
# Restart specific worker
docker exec ttrpg_ingestion_engine supervisorctl restart source_monitor

# Restart all workers in a container
docker exec ttrpg_ingestion_engine supervisorctl restart all
```

## Dockerfile Pattern

### Database Containers (mongo, cassandra)
```dockerfile
FROM <base_image>

# Install Python + supervisor
RUN apt-get update && apt-get install -y \
    python3 python3-pip supervisor

# Install Python dependencies
RUN pip3 install cassandra-driver pymongo neo4j

# Copy workers + infrastructure
COPY ingestion/async_worker_base.py /opt/workers/
COPY ingestion/pass_x_worker.py /opt/workers/
COPY docker/container/supervisord.conf /etc/supervisor/conf.d/

# Copy entrypoint script
COPY docker/container/entrypoint.sh /entrypoint.sh

# Health check: database + worker
HEALTHCHECK CMD <database_check> && supervisorctl status <worker> | grep -q RUNNING

# Start database + supervisor
ENTRYPOINT ["/entrypoint.sh"]
```

### Worker-Only Containers (ingestion_engine, llamaindex, hgrn, hayhooks)
```dockerfile
FROM <base_image>

# Install supervisor
RUN apt-get update && apt-get install -y supervisor

# Copy workers + supervisord config
COPY ingestion/*_worker.py /opt/workers/
COPY docker/container/supervisord.conf /etc/supervisor/conf.d/

# Health check: worker status only
HEALTHCHECK CMD supervisorctl status | grep RUNNING | wc -l | grep -q "N"

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/worker.conf"]
```

## Entrypoint Pattern (Database Containers)

```bash
#!/bin/bash
set -e

echo "Starting database in background..."
<original_entrypoint> &

echo "Waiting for database ready..."
until <health_check> || [ $COUNTER -eq TIMEOUT ]; do
  sleep N
  COUNTER=$((COUNTER + N))
done

echo "Database ready! Starting supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/worker.conf
```

## Benefits

1. **Zero Manual Steps**: No deployment/start scripts needed
2. **Declarative**: All configuration in docker-compose.yml and Dockerfiles
3. **Reliable**: Health checks ensure proper startup order
4. **Observable**: supervisor logs + health checks provide visibility
5. **Maintainable**: Standard Docker patterns, no custom orchestration
6. **Portable**: Works on any Docker environment (local, cloud, CI/CD)

## Migration from Manual Scripts

### Old Approach (Manual)
```bash
docker compose up -d                        # Start base containers
bash scripts/install_python_db_containers.sh  # Install Python
bash scripts/deploy_workers_production.sh     # Copy worker files
bash scripts/start_all_workers_production.sh  # Start workers manually
```

### New Approach (Docker-Native)
```bash
docker compose up -d --build               # Done!
```

## Files Created

### Dockerfiles
- `docker/ingestion_engine/Dockerfile`
- `docker/mongodb_worker/Dockerfile`
- `docker/cassandra_worker/Dockerfile`
- `docker/hayhooks_worker/Dockerfile`
- `docker/llamaindex/Dockerfile` (updated)
- `docker/hgrn_worker/Dockerfile`

### Supervisor Configs
- `docker/ingestion_engine/supervisord.conf`
- `docker/mongodb_worker/supervisord.conf`
- `docker/cassandra_worker/supervisord.conf`
- `docker/hayhooks_worker/supervisord.conf`
- `docker/llamaindex/supervisord.conf`
- `docker/hgrn_worker/supervisord.conf`

### Entrypoint Scripts
- `docker/mongodb_worker/entrypoint.sh`
- `docker/cassandra_worker/entrypoint.sh`

### Updated Files
- `docker-compose-ttrpg.yml` (custom builds + health checks)

### Deleted Files
- ~~`scripts/deploy_workers_production.sh`~~ (obsolete)
- ~~`scripts/start_all_workers_production.sh`~~ (obsolete)
- ~~`scripts/install_python_db_containers.sh`~~ (obsolete)

## Troubleshooting

### Workers Not Starting
```bash
# Check supervisor logs
docker exec ttrpg_ingestion_engine supervisorctl tail source_monitor

# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# Restart specific container
docker compose -f docker-compose-ttrpg.yml restart ingestion_engine
```

### Database Connection Errors
```bash
# Verify databases are healthy
docker exec ttrpg_mongodb mongosh --eval "db.adminCommand('ping')"
docker exec ttrpg_cassandra cqlsh -e "SELECT release_version FROM system.local"
docker exec ttrpg_neo4j wget -qO- http://localhost:7474

# Check dependency order
docker compose -f docker-compose-ttrpg.yml ps
```

### Worker Crashes
```bash
# Check worker logs
docker exec ttrpg_ingestion_engine supervisorctl tail -f gate_0_hash stderr

# Manually restart worker
docker exec ttrpg_ingestion_engine supervisorctl restart gate_0_hash

# View supervisor process status
docker exec ttrpg_ingestion_engine supervisorctl status
```

## Production Readiness

✅ **Ready for Production**:
- Workers auto-start on container launch
- Health checks verify proper operation
- Auto-restart on failures
- Centralized logging via supervisor
- Declarative configuration in version control
- No manual scripts or SSH access needed

🔒 **Security Notes**:
- Credentials via .env file (not in images)
- No hardcoded secrets
- Read-only mounts where appropriate
- Network isolation via bridge network
