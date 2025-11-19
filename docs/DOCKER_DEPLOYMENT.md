# Docker Swarm Deployment Guide

## Overview

This guide covers deploying the TTRPG Center using the consolidated `docker-stack-ttrpg.yml` configuration with Docker Swarm.

## Architecture

### Services (12 total)
- **n8n** - Workflow orchestration (port 9000)
- **webui** - Next.js frontend (port 3000)
- **postgres** - Authentication database (port 5432)
- **mongodb** - Document storage (port 9002)
- **cassandra** - Vector database (port 9001)
- **stargate** - Cassandra API gateway (ports 9004, 9008, 9011, 9012)
- **neo4j** - Graph database (ports 9003, 9005)
- **unstructured** - Document processing (port 9006)
- **hayhooks** - Haystack pipelines (port 9007)
- **langflow** - Visual pipeline builder (port 9010)
- **ingestion_engine** - Python processing (port 9009)
- **hgrn** - GPU-accelerated processing (port 9013)

### Security Features
- Docker Secrets for sensitive credentials
- Encrypted overlay network (10.10.0.0/24)
- Non-root users in containers
- Read-only filesystem support
- Health checks on all services

## Prerequisites

### Required
- Docker Engine 20.10+ with Swarm mode
- Docker Compose V2
- At least 16GB RAM available
- 50GB disk space
- NVIDIA GPU with CUDA support (for HGRN service)

### Optional
- `openssl` for automatic password generation
- `git` for version control

## Quick Start

### 1. Initialize Docker Swarm

```bash
# Initialize swarm (if not already done)
docker swarm init

# Verify swarm is active
docker info | grep Swarm
```

### 2. Label GPU Node

```bash
# Get node ID
docker node ls

# Label the node with GPU
docker node update --label-add gpu=true <node-id>
```

### 3. Build Required Images

```bash
# Build WebUI (optimized production image)
docker build -f webui/Dockerfile.optimized -t ttrpg-webui:latest .

# Build Unstructured service (if needed)
docker build -f docker/unstructured/Dockerfile -t n8n_ttrpg_unstructured:latest .
```

### 4. Create Secrets

```bash
# Navigate to secrets directory
cd secrets

# Create all secrets (will auto-generate passwords if not in .env)
./create_secrets.sh --from-env-file ../.env

# Verify secrets were created
docker secret ls
```

### 5. Deploy Stack

```bash
# Deploy the complete stack
docker stack deploy -c docker-stack-ttrpg.yml ttrpg

# Watch services start
watch -n 2 'docker service ls'

# Check logs
docker service logs -f ttrpg_webui
```

## Configuration

### Environment Variables

Edit `.env` file with your credentials:

```env
# OpenAI API Key (required)
OPENAI_API_KEY=your-key-here

# Neo4j Credentials
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# PostgreSQL Credentials (auto-generated if empty)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=ttrpg_auth
```

### Transfer Station Path

The shared directory for inter-service communication is mounted at:
```
E:/n8n_TTRPG_Transfer_Station
```

**To change:** Edit `docker-stack-ttrpg.yml` and update all `source:` paths in bind mounts.

### Resource Limits

Default limits per service (can be adjusted in yml):
- WebUI: 1GB RAM
- Postgres: 1GB RAM
- MongoDB: 2GB RAM
- Cassandra: 2GB RAM
- Neo4j: 2GB RAM
- Ingestion: 2GB RAM
- HGRN: 8GB RAM (GPU)

## Service Management

### Scaling Services

```bash
# Scale ingestion engine to 3 replicas
docker service scale ttrpg_ingestion_engine=3

# Scale back to 1
docker service scale ttrpg_ingestion_engine=1
```

### Viewing Logs

```bash
# All logs for a service
docker service logs ttrpg_<service_name>

# Follow logs
docker service logs -f ttrpg_webui

# Last 100 lines
docker service logs --tail 100 ttrpg_neo4j
```

### Updating Services

```bash
# Update specific service image
docker service update --image ttrpg-webui:v2.0 ttrpg_webui

# Force update (recreate containers)
docker service update --force ttrpg_webui

# Rollback to previous version
docker service rollback ttrpg_webui
```

### Inspecting Services

```bash
# Service details
docker service inspect ttrpg_webui

# Service tasks/replicas
docker service ps ttrpg_webui

# Service logs with timestamps
docker service logs -t ttrpg_webui
```

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker service ls

# Inspect failed service
docker service ps ttrpg_<service> --no-trunc

# Check service logs
docker service logs ttrpg_<service>
```

### Secret Issues

```bash
# List secrets
docker secret ls

# Remove and recreate secret
docker secret rm openai_api_key
echo "your-key" | docker secret create openai_api_key -

# Force restart service to pick up new secret
docker service update --force ttrpg_webui
```

### Network Issues

```bash
# Inspect overlay network
docker network inspect ttrpg_overlay

# List services on network
docker network inspect ttrpg_overlay --format '{{range .Containers}}{{.Name}} {{end}}'

# Test connectivity between services
docker exec $(docker ps -q -f name=ttrpg_webui) ping -c 2 mongodb
```

### GPU Not Available

```bash
# Verify GPU is visible
docker run --rm --gpus all nvidia/cuda:11.7.0-base-ubuntu20.04 nvidia-smi

# Check HGRN service placement
docker service ps ttrpg_hgrn

# Verify node label
docker node inspect $(docker node ls -q) | grep gpu
```

### Health Check Failures

```bash
# Check health status
docker service inspect ttrpg_webui --format '{{json .UpdateStatus}}'

# View health check logs
docker service logs ttrpg_webui | grep -i health

# Manually test health endpoint
docker exec $(docker ps -q -f name=ttrpg_webui) curl -f http://localhost:3000/api/health
```

## Backup and Recovery

### Backup Volumes

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup all volumes
for volume in $(docker volume ls -q | grep ttrpg); do
  docker run --rm -v $volume:/data -v $(pwd)/backups:/backup alpine \
    tar czf /backup/$(date +%Y%m%d)/$volume.tar.gz -C /data .
done
```

### Restore Volumes

```bash
# Restore specific volume
docker run --rm -v ttrpg_neo4j_data:/data -v $(pwd)/backups:/backup alpine \
  tar xzf /backup/20251023/ttrpg_neo4j_data.tar.gz -C /data
```

### Export Secrets

```bash
# Secrets cannot be exported after creation
# Always keep backup of .env file with credentials
cp .env .env.backup.$(date +%Y%m%d)
```

## Stack Removal

### Safe Removal

```bash
# Remove stack (keeps volumes and secrets)
docker stack rm ttrpg

# Wait for cleanup
watch -n 2 'docker stack ps ttrpg 2>/dev/null || echo "Stack removed"'

# Verify services are gone
docker service ls
```

### Complete Cleanup

```bash
# Remove stack
docker stack rm ttrpg

# Remove volumes (WARNING: deletes all data)
docker volume rm $(docker volume ls -q | grep ttrpg)

# Remove secrets
docker secret rm openai_api_key neo4j_user neo4j_password \
                 postgres_user postgres_password postgres_db

# Remove network
docker network rm ttrpg_overlay
```

## Performance Tuning

### Cassandra Heap Sizes

Adjust in `docker-stack-ttrpg.yml`:
```yaml
environment:
  - HEAP_NEWSIZE=512M  # Default: 256M
  - MAX_HEAP_SIZE=2G   # Default: 1G
```

### Neo4j Memory

Adjust in `docker-stack-ttrpg.yml`:
```yaml
environment:
  - NEO4J_server_memory_heap_initial__size=1g  # Default: 512m
  - NEO4J_server_memory_heap_max__size=2g      # Default: 1g
```

### Postgres Connections

Add to postgres init script (`postgres/init/01-config.sql`):
```sql
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
```

## Monitoring

### Service Health

```bash
# Check all service health
docker service ls

# Health check details
docker service inspect ttrpg_webui --format '{{json .Spec.TaskTemplate.ContainerSpec.Healthcheck}}'
```

### Resource Usage

```bash
# Real-time stats for all services
docker stats $(docker ps -q -f name=ttrpg)

# Specific service
docker stats $(docker ps -q -f name=ttrpg_webui)
```

### Logs Aggregation

```bash
# Export all logs to file
for service in $(docker service ls --format '{{.Name}}' | grep ttrpg); do
  docker service logs $service > logs/$service.log 2>&1
done
```

## Security Best Practices

1. **Secrets Management**
   - Never commit `.env` to version control
   - Rotate secrets regularly using `secrets/rotate_secrets.sh`
   - Use different passwords for each environment

2. **Network Security**
   - Keep overlay network encrypted
   - Use firewall rules to restrict external access
   - Only expose necessary ports

3. **Image Security**
   - Regularly update base images
   - Scan images for vulnerabilities
   - Use distroless images where possible (WebUI uses gcr.io/distroless)

4. **Access Control**
   - Limit Docker socket access
   - Use RBAC for service access
   - Enable PostgreSQL authentication

## Production Checklist

- [ ] Docker Swarm initialized and stable
- [ ] GPU node labeled correctly
- [ ] All secrets created and verified
- [ ] Images built and tagged
- [ ] `.env` file configured with production values
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] Firewall rules applied
- [ ] SSL/TLS certificates configured (if public-facing)
- [ ] Resource limits reviewed and adjusted
- [ ] Health checks tested
- [ ] Log rotation configured

## Support

For issues and questions:
- Check logs: `docker service logs ttrpg_<service>`
- Review service status: `docker service ps ttrpg_<service>`
- Inspect configuration: `docker service inspect ttrpg_<service>`
- See troubleshooting section above
