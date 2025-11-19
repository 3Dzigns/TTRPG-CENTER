# Docker Swarm - Quick Start Guide

## 5-Minute Deployment

### Prerequisites Check
```bash
docker --version          # Should be 20.10+
docker compose version    # Should be v2.x
nvidia-smi               # Verify GPU is available
```

### Step 1: Initialize Swarm (30 seconds)
```bash
docker swarm init
docker node update --label-add gpu=true $(docker node ls -q)
```

### Step 2: Build Images (5-10 minutes)
```bash
# Build WebUI
docker build -f webui/Dockerfile.optimized -t ttrpg-webui:latest .

# Build Unstructured (optional if image exists)
docker build -f docker/unstructured/Dockerfile -t n8n_ttrpg_unstructured:latest .
```

### Step 3: Create Secrets (1 minute)
```bash
cd secrets
./create_secrets.sh --from-env-file ../.env
cd ..
```

### Step 4: Deploy Stack (2 minutes)
```bash
docker stack deploy -c docker-stack-ttrpg.yml ttrpg
```

### Step 5: Verify Deployment (1 minute)
```bash
# Watch services start
docker service ls

# Check WebUI is running
curl http://localhost:3000/api/health
```

## Common Commands

### Check Status
```bash
docker service ls                    # List all services
docker service ps ttrpg_webui       # Check WebUI replicas
docker service logs -f ttrpg_webui  # Follow WebUI logs
```

### Scale Services
```bash
docker service scale ttrpg_ingestion_engine=3  # Scale to 3 replicas
```

### Update Services
```bash
docker service update --force ttrpg_webui  # Restart service
```

### Remove Stack
```bash
docker stack rm ttrpg  # Remove all services (keeps volumes)
```

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| WebUI | http://localhost:3000 | Next.js Frontend |
| n8n | http://localhost:9000 | Workflow Engine |
| Neo4j Browser | http://localhost:9003 | Graph Database UI |
| MongoDB | mongodb://localhost:9002 | Document Store |
| Cassandra | localhost:9001 | Vector Database |
| Stargate REST | http://localhost:9004 | Cassandra API |
| Unstructured | http://localhost:9006 | Document Processing |
| Hayhooks | http://localhost:9007 | Haystack Pipelines |
| Ingestion | http://localhost:9009 | Python Processing |
| LangFlow | http://localhost:9010 | Visual Pipelines |
| HGRN | http://localhost:9013 | GPU Processing |
| Postgres | localhost:5432 | Auth Database |

## Troubleshooting

### Services Won't Start
```bash
# Check logs
docker service logs ttrpg_<service_name>

# Check if secrets exist
docker secret ls

# Recreate service
docker service update --force ttrpg_<service_name>
```

### "Image not found" Error
```bash
# Build missing image
docker build -f webui/Dockerfile.optimized -t ttrpg-webui:latest .
```

### GPU Not Working
```bash
# Verify node label
docker node inspect $(docker node ls -q) | grep gpu

# Re-label node
docker node update --label-add gpu=true $(docker node ls -q)
```

### Secrets Missing
```bash
# Recreate secrets
cd secrets && ./create_secrets.sh --from-env-file ../.env
```

## File Structure

```
E:\n8n_TTRPG_Center\
├── docker-stack-ttrpg.yml       # Main deployment file
├── .env                          # Environment variables
├── secrets/
│   └── create_secrets.sh        # Secret creation script
├── webui/
│   └── Dockerfile.optimized     # WebUI Docker build
├── docker/
│   └── unstructured/Dockerfile  # Unstructured build
└── docs/
    ├── DOCKER_DEPLOYMENT.md     # Full deployment guide
    └── DOCKER_QUICK_START.md    # This file
```

## Next Steps

1. Access WebUI: http://localhost:3000
2. Configure n8n workflows: http://localhost:9000
3. Explore Neo4j data: http://localhost:9003
4. Review [full deployment guide](./DOCKER_DEPLOYMENT.md)

## Important Notes

⚠️ **Security**
- Never commit `.env` file to version control
- Change default passwords before production
- Use secrets for all sensitive data

⚠️ **Data Persistence**
- All data is stored in Docker volumes
- Backup volumes regularly
- Use `docker volume ls | grep ttrpg` to see volumes

⚠️ **Resource Usage**
- Minimum 16GB RAM recommended
- GPU required for HGRN service
- ~50GB disk space needed

## Support

See full documentation: [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)
