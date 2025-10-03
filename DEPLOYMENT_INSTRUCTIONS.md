# TTRPG Center - Manual Deployment Instructions

## Prerequisites

- WSL installed with Docker Desktop integration enabled
- Navigate to project directory in WSL

## Step 1: Build All Microservice Images (Sequential)

**IMPORTANT:** Build services one at a time to avoid resource exhaustion. Each build takes ~5-10 minutes due to large ML dependencies (PyTorch, CUDA).

```bash
cd /mnt/e/TTRPG_Center

# Build services sequentially (one at a time)
docker compose -f docker-compose.rebuild.yml build ingest-build
docker compose -f docker-compose.rebuild.yml build pipeline-worker-build
docker compose -f docker-compose.rebuild.yml build orchestrator-build
docker compose -f docker-compose.rebuild.yml build admin-api-build

# Verify all images built successfully
docker images | grep "dev-20251003"
```

**Expected output:**
```
ttrpg-admin-api          dev-20251003   <image_id>   X minutes ago   ~9GB
ttrpg-orchestrator       dev-20251003   <image_id>   X minutes ago   ~9GB
ttrpg-pipeline-worker    dev-20251003   <image_id>   X minutes ago   ~9GB
ttrpg-ingest             dev-20251003   <image_id>   X minutes ago   ~9GB
```

## Step 2: Stop Existing Containers

```bash
# Stop and remove old containers
docker compose -f docker-compose.deploy-dev.yml down

# Or manually stop if needed
docker stop ttrpg-admin-api-dev ttrpg-orchestrator-dev ttrpg-pipeline-worker-dev ttrpg-ingest-dev
docker stop ttrpg-cassandra-dev ttrpg-mongo-dev ttrpg-redis-dev
docker rm ttrpg-admin-api-dev ttrpg-orchestrator-dev ttrpg-pipeline-worker-dev ttrpg-ingest-dev
```

## Step 3: Deploy Full Stack to DEV

```bash
# Deploy all services with new images
docker compose -f docker-compose.deploy-dev.yml up -d

# Watch logs to verify startup
docker compose -f docker-compose.deploy-dev.yml logs -f
```

## Step 4: Verify All Services Healthy

```bash
# Check container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check health endpoints
curl http://localhost:8000/healthz  # admin-api
curl http://localhost:8003/healthz  # ingest
curl http://localhost:8004/healthz  # orchestrator
curl http://localhost:8006/healthz  # pipeline-worker

# Verify datastores
docker exec ttrpg-cassandra-dev cqlsh -e "describe cluster"
docker exec ttrpg-mongo-dev mongosh --eval "db.adminCommand('ping')"
docker exec ttrpg-redis-dev redis-cli ping
```

**Expected output:** All services should respond with `{"status":"healthy"}` or similar.

## Step 5: Clear Datastores for Clean Ingestion

```bash
# Make script executable
chmod +x scripts/clear-datastores.sh

# Run datastore clearing script
./scripts/clear-datastores.sh
```

**Manual alternative if script fails:**

```bash
# Clear MongoDB
docker exec ttrpg-mongo-dev mongosh ttrpg_dev --eval 'db.dropDatabase()'

# Clear Cassandra
docker exec ttrpg-cassandra-dev cqlsh -e "DROP KEYSPACE IF EXISTS ttrpg_dev; CREATE KEYSPACE ttrpg_dev WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};"

# Clear Redis
docker exec ttrpg-redis-dev redis-cli FLUSHALL
```

## Step 6: Verify Code Fixes Applied

Verify the critical bug fixes are present in the running containers:

```bash
# Check Pass B logical splitter fix (TOC-based splitting)
docker exec ttrpg-pipeline-worker-dev grep -A 5 "_generate_toc_based_splits" /app/src_common/pass_b_logical_splitter.py

# Check environment isolation fix
docker exec ttrpg-pipeline-worker-dev grep "self.environment_name = " /app/src_common/environment_isolation.py
```

## Step 7: Access Services

- **Admin UI:** http://localhost:8000
- **Ingest API:** http://localhost:8003/docs
- **Orchestrator API:** http://localhost:8004/docs
- **Pipeline Worker API:** http://localhost:8006/docs

## Troubleshooting

### Build Issues

**Problem:** Out of memory during build
```bash
# Increase Docker memory in Docker Desktop settings
# Or build with limited parallelism (already done in rebuild file)
```

**Problem:** Build cache issues
```bash
# Clear build cache and rebuild
docker builder prune -af
docker compose -f docker-compose.rebuild.yml build --no-cache ingest-build
```

### Deployment Issues

**Problem:** Containers not starting
```bash
# Check logs
docker compose -f docker-compose.deploy-dev.yml logs <service_name>

# Check resource usage
docker stats
```

**Problem:** Health checks failing
```bash
# Check service logs
docker logs ttrpg-<service>-dev

# Verify environment variables
docker exec ttrpg-<service>-dev env | grep -E "ENVIRONMENT|SERVICE_NAME|PORT"
```

### Datastore Issues

**Problem:** Cassandra not starting
```bash
# Cassandra needs time to initialize
docker logs ttrpg-cassandra-dev
# Wait for "Starting listening for CQL clients"
```

**Problem:** MongoDB connection refused
```bash
# Verify MongoDB is ready
docker exec ttrpg-mongo-dev mongosh --eval "db.adminCommand('ping')"
```

## Quick Reference Commands

```bash
# View all containers
docker ps -a

# View all images
docker images | grep ttrpg

# View logs for specific service
docker logs -f ttrpg-admin-api-dev

# Restart specific service
docker restart ttrpg-<service>-dev

# Execute command in container
docker exec -it ttrpg-admin-api-dev bash

# Check disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

## Success Criteria

✅ All 7 containers running and healthy:
- ttrpg-cassandra-dev
- ttrpg-mongo-dev
- ttrpg-redis-dev
- ttrpg-ingest-dev
- ttrpg-pipeline-worker-dev
- ttrpg-orchestrator-dev
- ttrpg-admin-api-dev

✅ All datastores cleared and ready

✅ Admin UI accessible at http://localhost:8000

✅ Code fixes verified in running containers:
- `pass_b_logical_splitter.py` has TOC-based splitting
- `environment_isolation.py` has environment_name attribute

You're now ready to test the ingestion pipeline with the bug fixes!
