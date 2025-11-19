# WebUI Deployment Guide

## Overview

The TTRPG Center WebUI is a Next.js 15 App Router application containerized with Docker. It runs completely separate from the ingestion engine and connects to backend services via the `n8n_TTRPG_network`.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  WebUI Container (Port 3000)                            │
│  ├── Next.js 15 App Router                              │
│  ├── React 18 + TypeScript                              │
│  ├── Tailwind CSS + shadcn/ui                           │
│  ├── TanStack Query + Zustand                           │
│  └── Monorepo: apps/web + packages/{api,types,ui,config}│
└─────────────────────────────────────────────────────────┘
                          ↓
              n8n_TTRPG_network (Docker)
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Backend Services (Existing Stack)                       │
│  ├── n8n (Port 9000)                                     │
│  ├── MongoDB (Port 9002)                                 │
│  ├── Cassandra (Port 9001) + Stargate (9004/9008)       │
│  ├── Neo4j (Port 9003/9005)                              │
│  ├── Unstructured API (Port 9006)                        │
│  ├── Hayhooks (Port 9007)                                │
│  └── Langflow (Port 9010)                                │
└──────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Docker & Docker Compose** installed
2. **Backend services running** (`docker-compose-n8n_TTRPG.yml`)
3. **.env file** with required credentials (see `.env.docker` template)

## Quick Start

### 1. Build the WebUI Image

```bash
# From project root
docker build -f webui/Dockerfile -t n8n_ttrpg_webui:latest .
```

### 2. Start the WebUI Container

```bash
# Using docker-compose (recommended)
docker-compose -f docker-compose-webui.yml up -d

# Or standalone
docker run -d \
  --name n8n_TTRPG_webui \
  --network n8n_TTRPG_network \
  -p 3000:3000 \
  --env-file .env \
  n8n_ttrpg_webui:latest
```

### 3. Verify Health

```bash
# Check health endpoint
curl http://localhost:3000/api/health

# Check logs
docker logs n8n_TTRPG_webui

# Check container status
docker ps | grep webui
```

## Environment Variables

### Required Variables

Copy `webui/.env.docker` to `.env` and configure:

```env
# OpenAI API Key (REQUIRED)
OPENAI_API_KEY=sk-...

# Neo4j Credentials (REQUIRED)
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

### Automatic Variables (Docker Network)

These are automatically configured in `docker-compose-webui.yml`:

- `API_BASE_URL` - Internal n8n API URL
- `MONGODB_URI` - Internal MongoDB connection
- `NEO4J_URI` - Internal Neo4j connection
- `CASSANDRA_CONTACT_POINTS` - Internal Cassandra nodes
- `STARGATE_URL` - Internal Stargate API
- `LANGFLOW_URL` - Internal Langflow API
- `HAYHOOKS_URL` - Internal Hayhooks API
- `UNSTRUCTURED_URL` - Internal Unstructured API

### Public Variables (Browser)

```env
# External URL for browser requests
NEXT_PUBLIC_API_BASE_URL=http://localhost:9000
```

## Development Mode

### Hot Reload with Volume Mounts

Uncomment the volumes section in `docker-compose-webui.yml`:

```yaml
volumes:
  - ./apps/web:/app/apps/web
  - ./packages:/app/packages
  - /app/node_modules
  - /app/apps/web/.next
```

Then rebuild and restart:

```bash
docker-compose -f docker-compose-webui.yml up -d --build
```

### Local Development (Without Docker)

```bash
# Install dependencies
pnpm install

# Start dev server
pnpm --filter @ttrpg-center/web dev

# Open browser
http://localhost:3000
```

## Production Deployment

### 1. Build Optimized Image

```bash
docker build \
  --build-arg NODE_ENV=production \
  -f webui/Dockerfile \
  -t n8n_ttrpg_webui:v1.0.0 \
  .
```

### 2. Tag and Push (if using registry)

```bash
docker tag n8n_ttrpg_webui:v1.0.0 your-registry/n8n_ttrpg_webui:v1.0.0
docker push your-registry/n8n_ttrpg_webui:v1.0.0
```

### 3. Deploy with Production Compose

```bash
docker-compose -f docker-compose-webui.yml up -d
```

## Container Details

### Multi-Stage Build

The Dockerfile uses a 3-stage build:

1. **deps** - Install dependencies with pnpm
2. **builder** - Build all packages and Next.js app
3. **runner** - Production runtime with standalone output

### Image Optimizations

- ✅ Alpine Linux base (minimal size)
- ✅ pnpm for efficient dependency management
- ✅ Multi-stage build (only runtime in final image)
- ✅ Next.js standalone output (minimal dependencies)
- ✅ Non-root user (security)
- ✅ Layer caching (faster rebuilds)

### Health Checks

The container includes built-in health checks:

```yaml
healthcheck:
  test: ["CMD", "node", "-e", "require('http').get('http://localhost:3000/api/health', ...)"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs n8n_TTRPG_webui

# Check if port 3000 is available
netstat -an | findstr :3000

# Verify backend network exists
docker network ls | grep n8n_TTRPG_network
```

### Health Check Failing

```bash
# Test health endpoint manually
docker exec n8n_TTRPG_webui curl http://localhost:3000/api/health

# Check if Next.js is running
docker exec n8n_TTRPG_webui ps aux | grep node
```

### Cannot Connect to Backend Services

```bash
# Verify network connectivity
docker exec n8n_TTRPG_webui ping n8n_TTRPG_n8n
docker exec n8n_TTRPG_webui ping n8n_TTRPG_mongodb

# Check environment variables
docker exec n8n_TTRPG_webui env | grep API_BASE_URL
```

### Build Failures

```bash
# Clear Docker build cache
docker builder prune

# Build with no cache
docker build --no-cache -f webui/Dockerfile -t n8n_ttrpg_webui:latest .

# Check disk space
docker system df
```

## Maintenance

### Update Dependencies

```bash
# Update pnpm lockfile
pnpm update --latest

# Rebuild image
docker-compose -f docker-compose-webui.yml build --no-cache
```

### View Logs

```bash
# Real-time logs
docker logs -f n8n_TTRPG_webui

# Last 100 lines
docker logs --tail 100 n8n_TTRPG_webui

# Logs with timestamps
docker logs -t n8n_TTRPG_webui
```

### Container Management

```bash
# Stop container
docker-compose -f docker-compose-webui.yml stop

# Restart container
docker-compose -f docker-compose-webui.yml restart

# Remove container and volumes
docker-compose -f docker-compose-webui.yml down -v
```

## Performance Tuning

### Memory Limits

Add to `docker-compose-webui.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 1G
    reservations:
      memory: 512M
```

### CPU Limits

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
    reservations:
      cpus: '0.5'
```

## Security Considerations

1. **Non-root User**: Container runs as `nextjs` user (UID 1001)
2. **No Secrets in Image**: All credentials via environment variables
3. **Read-only Filesystem**: Can enable with `read_only: true`
4. **Network Isolation**: Only connected to n8n_TTRPG_network
5. **Security Scanning**: Run `docker scan n8n_ttrpg_webui:latest`

## Monitoring

### Container Stats

```bash
docker stats n8n_TTRPG_webui
```

### Health Status

```bash
docker inspect n8n_TTRPG_webui | grep -A 10 Health
```

### Access Metrics

Visit: http://localhost:3000/api/health

```json
{
  "status": "healthy",
  "timestamp": "2025-10-17T02:30:00.000Z",
  "uptime": 3600,
  "environment": "production",
  "version": "0.1.0"
}
```

## Next Steps

1. Configure OAuth/OIDC authentication (see P07)
2. Setup RBAC guards (see P14)
3. Configure error monitoring with Sentry (see P15)
4. Add E2E tests with Playwright (see P17)
5. Setup CI/CD pipeline for automated builds

## Related Documentation

- [P00 - Scaffold Monorepo & App Shell](../Prompt%20Lib/WebUI/P00_scaffold_monorepo_app_shell.md)
- [Workflow Guide](./WORKFLOW-GUIDE.md)
- [Docker Compose Main Stack](../docker-compose-n8n_TTRPG.yml)
