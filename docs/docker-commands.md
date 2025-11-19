# Docker Commands Reference

Comprehensive Docker command reference for managing the n8n TTRPG Center stack.

## Table of Contents

- [Stack Management](#stack-management)
- [Service Management](#service-management)
- [Container Access](#container-access)
- [Database Operations](#database-operations)
- [Custom Node Development](#custom-node-development)
- [Workflow Development](#workflow-development)
- [Logging and Debugging](#logging-and-debugging)
- [Cleanup and Maintenance](#cleanup-and-maintenance)

---

## Stack Management

### Start/Stop Stack

```bash
# Start entire stack
docker compose -f docker-compose-n8n_TTRPG.yml up -d

# Stop all services (preserves volumes)
docker compose -f docker-compose-n8n_TTRPG.yml down

# Stop and remove volumes (DATA LOSS!)
docker compose -f docker-compose-n8n_TTRPG.yml down -v
```

### Stack Status

```bash
# View all services with status
docker compose -f docker-compose-n8n_TTRPG.yml ps

# Quick health check (Docker CLI)
docker ps --format "table {{.Names}}\t{{.Status}}"

# Detailed status with ports
docker ps
```

### Stack Rebuild

```bash
# Rebuild specific service
docker compose -f docker-compose-n8n_TTRPG.yml build <service_name>

# Rebuild and restart
docker compose -f docker-compose-n8n_TTRPG.yml up -d --build <service_name>

# Force recreate without rebuild
docker compose -f docker-compose-n8n_TTRPG.yml up -d --force-recreate <service_name>

# Rebuild entire stack
docker compose -f docker-compose-n8n_TTRPG.yml build
docker compose -f docker-compose-n8n_TTRPG.yml up -d
```

---

## Service Management

### Start/Stop Individual Services

```bash
# Start specific service
docker compose -f docker-compose-n8n_TTRPG.yml up -d n8n

# Stop specific service
docker compose -f docker-compose-n8n_TTRPG.yml stop n8n

# Restart specific service
docker compose -f docker-compose-n8n_TTRPG.yml restart n8n

# Remove specific service container
docker compose -f docker-compose-n8n_TTRPG.yml rm -f n8n
```

### Service Health Monitoring

```bash
# Check health status
docker inspect n8n_TTRPG_cassandra --format='{{.State.Health.Status}}'

# View health check logs
docker inspect n8n_TTRPG_cassandra --format='{{range .State.Health.Log}}{{.Output}}{{end}}'

# Wait for service to be healthy
while [ "$(docker inspect n8n_TTRPG_cassandra --format='{{.State.Health.Status}}')" != "healthy" ]; do
  echo "Waiting for Cassandra..."
  sleep 5
done
echo "Cassandra is healthy!"
```

---

## Container Access

### Shell Access

```bash
# Access ingestion_engine bash shell
docker exec -it n8n_TTRPG_ingestion_engine bash

# Access n8n shell
docker exec -it n8n_TTRPG_n8n sh

# Access MongoDB shell
docker exec -it n8n_TTRPG_mongodb mongosh

# Access Cassandra CQL shell
docker exec -it n8n_TTRPG_cassandra cqlsh

# Access Neo4j Cypher shell
docker exec -it n8n_TTRPG_neo4j cypher-shell -u neo4j -p password
```

### Run Commands Without Shell

```bash
# Run Python script
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/gate_0_hash.py /Transfer_Station/sources/doc.pdf

# Check Python packages
docker exec n8n_TTRPG_ingestion_engine pip list

# Install additional packages
docker exec n8n_TTRPG_ingestion_engine pip install pandas numpy

# List files
docker exec n8n_TTRPG_ingestion_engine ls -la /Transfer_Station/
```

### Copy Files To/From Containers

```bash
# Copy from host to container
docker cp /path/on/host/file.txt n8n_TTRPG_ingestion_engine:/Transfer_Station/

# Copy from container to host
docker cp n8n_TTRPG_ingestion_engine:/Transfer_Station/output.json /path/on/host/

# Copy directory
docker cp n8n-nodes-pdf-slice/dist n8n_TTRPG_n8n:/home/node/.n8n/custom/n8n-nodes-pdf-slice/
```

---

## Database Operations

### MongoDB

```bash
# Connect via mongosh
docker exec -it n8n_TTRPG_mongodb mongosh

# Backup database
docker exec n8n_TTRPG_mongodb mongodump --out=/data/backup

# Restore database
docker exec n8n_TTRPG_mongodb mongorestore /data/backup

# Execute MongoDB command
docker exec n8n_TTRPG_mongodb mongosh --eval "db.adminCommand('ping')"

# List databases
docker exec n8n_TTRPG_mongodb mongosh --eval "show dbs"

# Export collection to JSON
docker exec n8n_TTRPG_mongodb mongoexport --db=ttrpg_ingestion --collection=elements --out=/data/elements.json
```

### Cassandra

```bash
# Connect via cqlsh
docker exec -it n8n_TTRPG_cassandra cqlsh

# Check cluster status
docker exec n8n_TTRPG_cassandra nodetool status

# Execute CQL command
docker exec n8n_TTRPG_cassandra cqlsh -e "DESCRIBE KEYSPACES;"

# Create keyspace
docker exec n8n_TTRPG_cassandra cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS ttrpg_vectors
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};"

# Query table
docker exec n8n_TTRPG_cassandra cqlsh -e "SELECT * FROM ttrpg_vectors.embeddings LIMIT 10;"
```

### Neo4j

```bash
# Access Cypher shell
docker exec -it n8n_TTRPG_neo4j cypher-shell -u neo4j -p password

# Execute Cypher query
docker exec n8n_TTRPG_neo4j cypher-shell -u neo4j -p password \
  "MATCH (n) RETURN count(n) AS node_count;"

# Browser UI access
# Navigate to: http://localhost:9003
# Credentials: neo4j / password

# Dump database
docker exec n8n_TTRPG_neo4j neo4j-admin dump --to=/data/neo4j_dump.dump
```

### Stargate API

```bash
# Health check
curl http://localhost:9004/v2/schemas/keyspaces

# List keyspaces via REST API
curl http://localhost:9004/v2/schemas/keyspaces

# Create keyspace via REST API
curl -X POST http://localhost:9004/v2/schemas/keyspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ttrpg_vectors",
    "replicas": 1
  }'
```

### Database Management Tool

```bash
# Summarize all databases
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --summarize

# Summarize specific database
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --summarize --db mongo

# Clear all databases (with confirmation)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear

# Clear specific database without confirmation
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear --db neo4j --force

# Dry run (preview changes)
docker exec n8n_TTRPG_ingestion_engine python3 /app/scripts/db_manager.py --clear --dry-run
```

---

## Custom Node Development

### n8n-nodes-pdf-slice

```bash
# Build node from source
cd n8n-nodes-pdf-slice
npm install
npm run build

# Clean and rebuild
npm run clean
npm run build

# Watch mode (if configured)
npm run build -- --watch
```

### Install Custom Node to Container

```bash
# Copy built node to running container
docker cp n8n-nodes-pdf-slice/dist n8n_TTRPG_n8n:/home/node/.n8n/custom/n8n-nodes-pdf-slice/

# Restart n8n to load node
docker restart n8n_TTRPG_n8n

# Verify installation
docker exec n8n_TTRPG_n8n ls -la /home/node/.n8n/custom/n8n-nodes-pdf-slice/
```

### Using PowerShell Installer

```powershell
# Build in Docker and install to container
.\Install-PdfSliceNode_FIXED.ps1 -ContainerName n8n_TTRPG_n8n -BuildInDocker

# Print docker-compose mount snippet
.\Install-PdfSliceNode_FIXED.ps1 -PrintComposeSnippet
```

---

## Workflow Development

### Import n8n Workflows

```bash
# Via n8n UI:
# 1. Navigate to http://localhost:9000
# 2. Settings → Import from File
# 3. Select ttrpg_ingestion_laneA_n8n_workflow.json

# Via API (if credentials configured)
curl -X POST http://localhost:9000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -d @ttrpg_ingestion_laneA_n8n_workflow.json
```

### Test Lane A Ingestion Webhook

```bash
# Minimal payload
curl -X POST http://localhost:9000/webhook/ingest/laneA \
  -H "Content-Type: application/json" \
  -d '{
    "env": "dev",
    "jobType": "adhoc",
    "source": {
      "filePath": "/Transfer_Station/n8n_inbound/test.pdf",
      "filename": "test.pdf",
      "lane": "A",
      "system": "PF2E"
    }
  }'

# Full payload with metadata
curl -X POST http://localhost:9000/webhook/ingest/laneA \
  -H "Content-Type: application/json" \
  -d '{
    "env": "prod",
    "jobType": "scheduled",
    "source": {
      "filePath": "/Transfer_Station/n8n_inbound/pathfinder_core.pdf",
      "filename": "pathfinder_core.pdf",
      "lane": "A",
      "system": "PF2E",
      "publisher": "Paizo"
    },
    "options": {
      "toc_only": true,
      "max_pages": 12
    }
  }'
```

### LangFlow Development

```bash
# Access LangFlow UI
# Navigate to: http://localhost:9010

# Install Python dependencies for LangFlow
docker exec -it n8n_TTRPG_langflow pip install pypdf

# Check LangFlow version
docker exec n8n_TTRPG_langflow pip show langflow

# View LangFlow logs
docker logs -f n8n_TTRPG_langflow
```

---

## Logging and Debugging

### View Container Logs

```bash
# Follow logs for specific service
docker compose -f docker-compose-n8n_TTRPG.yml logs -f n8n

# View last 100 lines
docker compose -f docker-compose-n8n_TTRPG.yml logs --tail=100 n8n

# View logs from multiple services
docker compose -f docker-compose-n8n_TTRPG.yml logs -f n8n mongodb cassandra

# View logs for all services
docker compose -f docker-compose-n8n_TTRPG.yml logs -f

# View logs with timestamps
docker compose -f docker-compose-n8n_TTRPG.yml logs -f --timestamps n8n
```

### Search Logs

```bash
# Search for errors
docker logs n8n_TTRPG_n8n 2>&1 | grep -i error

# Search for specific pattern
docker logs n8n_TTRPG_cassandra 2>&1 | grep -i "listening"

# Save logs to file
docker logs n8n_TTRPG_n8n > n8n_logs.txt 2>&1
```

### Inspect Containers

```bash
# View container configuration
docker inspect n8n_TTRPG_n8n

# View environment variables
docker inspect n8n_TTRPG_n8n --format='{{range .Config.Env}}{{println .}}{{end}}'

# View port mappings
docker port n8n_TTRPG_n8n

# View mounted volumes
docker inspect n8n_TTRPG_n8n --format='{{range .Mounts}}{{println .Source}}:{{.Destination}}{{end}}'

# View network settings
docker inspect n8n_TTRPG_n8n --format='{{range .NetworkSettings.Networks}}{{println .IPAddress}}{{end}}'
```

### Resource Usage

```bash
# View resource usage for all containers
docker stats

# View resource usage for specific container
docker stats n8n_TTRPG_cassandra

# View disk usage
docker system df

# View detailed disk usage
docker system df -v
```

---

## Cleanup and Maintenance

### Remove Stopped Containers

```bash
# Remove all stopped containers
docker container prune -f

# Remove specific stopped container
docker rm n8n_TTRPG_n8n
```

### Remove Unused Images

```bash
# Remove dangling images
docker image prune -f

# Remove all unused images
docker image prune -a -f

# Remove specific image
docker rmi <image_name>
```

### Remove Volumes

```bash
# List volumes
docker volume ls

# Remove specific volume
docker volume rm n8n_TTRPG_n8n_data

# Remove all unused volumes
docker volume prune -f
```

### Complete Cleanup

```bash
# Remove everything (containers, networks, volumes, images)
docker system prune -a --volumes -f

# Remove only this project's resources
docker compose -f docker-compose-n8n_TTRPG.yml down -v --rmi all
```

### Update Images

```bash
# Pull latest images
docker compose -f docker-compose-n8n_TTRPG.yml pull

# Rebuild and restart with new images
docker compose -f docker-compose-n8n_TTRPG.yml up -d --build
```

---

## Networking

### View Networks

```bash
# List all networks
docker network ls

# Inspect network
docker network inspect n8n_ttrpg_center_default

# View containers in network
docker network inspect n8n_ttrpg_center_default --format='{{range .Containers}}{{println .Name}}{{end}}'
```

### Test Connectivity

```bash
# Test connectivity from ingestion_engine to MongoDB
docker exec n8n_TTRPG_ingestion_engine ping -c 3 n8n_TTRPG_mongodb

# Test port connectivity
docker exec n8n_TTRPG_ingestion_engine nc -zv n8n_TTRPG_mongodb 27017

# Test HTTP endpoint
docker exec n8n_TTRPG_ingestion_engine curl -s http://n8n_TTRPG_unstructured:8000/
```

---

## Backup and Restore

### Backup Volumes

```bash
# Backup n8n data volume
docker run --rm \
  -v n8n_TTRPG_n8n_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/n8n_backup.tar.gz -C /data .

# Backup MongoDB data volume
docker run --rm \
  -v n8n_TTRPG_mongodb_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/mongodb_backup.tar.gz -C /data .
```

### Restore Volumes

```bash
# Restore n8n data volume
docker run --rm \
  -v n8n_TTRPG_n8n_data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/n8n_backup.tar.gz"

# Restore MongoDB data volume
docker run --rm \
  -v n8n_TTRPG_mongodb_data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/mongodb_backup.tar.gz"
```

### Export/Import Container State

```bash
# Export container as image
docker commit n8n_TTRPG_ingestion_engine my_ingestion_backup

# Save image to file
docker save my_ingestion_backup > ingestion_backup.tar

# Load image from file
docker load < ingestion_backup.tar
```

---

## Performance Tuning

### Increase Container Resources

Edit `docker-compose-n8n_TTRPG.yml`:

```yaml
services:
  cassandra:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
        reservations:
          cpus: '2'
          memory: 2G
```

### View Resource Limits

```bash
# View memory limits
docker inspect n8n_TTRPG_cassandra --format='{{.HostConfig.Memory}}'

# View CPU limits
docker inspect n8n_TTRPG_cassandra --format='{{.HostConfig.NanoCpus}}'
```
