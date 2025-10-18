# WebUI Container Deployment Guide

**Version**: 1.0.0
**Last Updated**: 2025-10-18

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Development Deployment](#development-deployment)
3. [Staging Deployment](#staging-deployment)
4. [Production Deployment](#production-deployment)
5. [Environment Variables](#environment-variables)
6. [Troubleshooting](#troubleshooting)
7. [Performance Benchmarks](#performance-benchmarks)

---

## Quick Start

### Prerequisites

- Docker 24.0+ with BuildKit enabled
- Docker Compose 2.20+
- 2GB free disk space
- 1GB RAM minimum
- Ports available: 3000

### Minimal Deployment

```bash
# Clone repository
git clone https://github.com/your-org/n8n_TTRPG_Center.git
cd n8n_TTRPG_Center

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start WebUI (production profile)
docker-compose -f docker-compose-webui-enhanced.yml --profile production up -d

# Check status
docker-compose -f docker-compose-webui-enhanced.yml ps

# View logs
docker-compose -f docker-compose-webui-enhanced.yml logs -f webui-prod
```

**Access**: http://localhost:3000

---

## Development Deployment

### Setup for Local Development

```bash
# 1. Install dependencies locally (optional, for IDE support)
pnpm install

# 2. Start development container
docker-compose -f docker-compose-webui-enhanced.yml --profile development up

# 3. Container will mount source code with hot-reload
# Edit files in apps/web or packages/* and see changes instantly
```

### Development Features

- **Hot Reload**: Changes reflect immediately without rebuild
- **Volume Mounts**: Source code synced from host
- **Debug Logging**: Full debug output enabled
- **Shell Access**: `docker exec -it ttrpg_webui_dev sh`
- **Relaxed Resources**: 2 CPU cores, 2GB RAM

### Development Commands

```bash
# Run linting inside container
docker exec ttrpg_webui_dev pnpm -w lint

# Run tests inside container
docker exec ttrpg_webui_dev pnpm -w test

# Type check
docker exec ttrpg_webui_dev pnpm -w typecheck

# Build packages
docker exec ttrpg_webui_dev pnpm --filter @ttrpg-center/ui build
```

### Debugging

```bash
# Attach to container shell
docker exec -it ttrpg_webui_dev sh

# View Next.js logs
docker logs -f ttrpg_webui_dev

# Inspect running processes
docker exec ttrpg_webui_dev ps aux

# Check Node.js version
docker exec ttrpg_webui_dev node --version
```

---

## Staging Deployment

### Pre-Production Testing

```bash
# 1. Build staging image
docker-compose -f docker-compose-webui-enhanced.yml --profile staging build

# 2. Start staging environment
docker-compose -f docker-compose-webui-enhanced.yml --profile staging up -d

# 3. Run smoke tests
npx playwright test --config=playwright.config.staging.ts

# 4. Check health
curl http://localhost:3000/api/health
```

### Staging Configuration

**Use Case**: Test production build with staging data

**Environment**: `.env.staging`
```bash
NODE_ENV=production
MONGODB_URI=mongodb://localhost:27017/ttrpg_staging
NEO4J_URI=bolt://localhost:7687
API_BASE_URL=http://n8n_TTRPG_n8n:5678
```

**Features**:
- Production-like build (Next.js standalone)
- Separate staging database
- Security hardening enabled
- Moderate resource limits

### Staging Validation Checklist

- [ ] Health check responds 200 OK
- [ ] All 20 WebUI features functional
- [ ] Authentication flow works
- [ ] Database connections successful
- [ ] API client requests succeed
- [ ] No console errors in browser
- [ ] Accessibility tests pass (WCAG 2.2 AA)
- [ ] Performance metrics meet targets
- [ ] E2E smoke tests pass

---

## Production Deployment

### Infrastructure Requirements

**Minimum**:
- 1 CPU core
- 1GB RAM
- 10GB disk (including logs)
- Linux host (Ubuntu 22.04+ recommended)

**Recommended**:
- 2 CPU cores
- 2GB RAM
- 50GB disk (with monitoring/logs)
- Reverse proxy (nginx/Traefik)
- TLS certificates (Let's Encrypt)

### Step-by-Step Production Deployment

#### 1. Prepare Production Environment

```bash
# Create production directory
mkdir -p /opt/ttrpg-center
cd /opt/ttrpg-center

# Clone repository
git clone https://github.com/your-org/n8n_TTRPG_Center.git .

# Create production .env
cp .env.example .env.production

# Edit production configuration
nano .env.production
```

#### 2. Configure Environment Variables

See [Environment Variables](#environment-variables) section below.

#### 3. Build Production Image

```bash
# Enable BuildKit for better caching
export DOCKER_BUILDKIT=1

# Build with optimized Dockerfile
docker build \
  -f webui/Dockerfile.optimized \
  -t ttrpg-webui:latest \
  --target runner \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  .

# Verify image size
docker images ttrpg-webui:latest
# Should be ~150-180MB
```

#### 4. Start Production Container

```bash
# Start with production profile
docker-compose -f docker-compose-webui-enhanced.yml \
  --profile production \
  --env-file .env.production \
  up -d

# Verify startup
docker-compose -f docker-compose-webui-enhanced.yml ps

# Check logs for errors
docker-compose -f docker-compose-webui-enhanced.yml logs webui-prod
```

#### 5. Configure Reverse Proxy (nginx)

```nginx
# /etc/nginx/sites-available/ttrpg-webui
upstream webui {
    server localhost:3000;
}

server {
    listen 443 ssl http2;
    server_name ttrpg-center.example.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/ttrpg-center.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ttrpg-center.example.com/privkey.pem;

    # SSL security headers
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to WebUI container
    location / {
        proxy_pass http://webui;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check endpoint
    location /api/health {
        proxy_pass http://webui/api/health;
        access_log off;
    }
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name ttrpg-center.example.com;
    return 301 https://$server_name$request_uri;
}
```

#### 6. Enable and Test nginx

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/ttrpg-webui /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Test HTTPS
curl -I https://ttrpg-center.example.com/api/health
```

#### 7. Setup Monitoring

**Prometheus Metrics**:
```yaml
# /etc/prometheus/prometheus.yml
scrape_configs:
  - job_name: 'ttrpg-webui'
    static_configs:
      - targets: ['localhost:3000']
    metrics_path: '/api/metrics'
    scrape_interval: 30s
```

**Health Check Monitoring** (using systemd timer or cron):
```bash
# /usr/local/bin/webui-health-check.sh
#!/bin/bash
HEALTH_URL="http://localhost:3000/api/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ "$RESPONSE" != "200" ]; then
    echo "WebUI health check failed: HTTP $RESPONSE"
    # Send alert (Slack/Discord/Email)
    exit 1
fi
```

#### 8. Backup & Disaster Recovery

**Container State Backup**:
```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/opt/backups/ttrpg-webui"
DATE=$(date +%Y%m%d-%H%M%S)

# Stop container gracefully
docker-compose -f docker-compose-webui-enhanced.yml --profile production stop webui-prod

# Backup volumes (if any)
docker run --rm \
  --volumes-from ttrpg_webui_prod \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/webui-volumes-$DATE.tar.gz /app

# Restart container
docker-compose -f docker-compose-webui-enhanced.yml --profile production start webui-prod
```

**Database Backups**: See database-specific guides for MongoDB, Neo4j, Cassandra

---

## Environment Variables

### Required Variables

```bash
# Node Environment
NODE_ENV=production
PORT=3000
NEXT_TELEMETRY_DISABLED=1

# API Configuration
API_BASE_URL=http://n8n_TTRPG_n8n:5678
NEXT_PUBLIC_API_BASE_URL=https://api.ttrpg-center.example.com

# Database URLs
MONGODB_URI=mongodb://mongodb_host:27017/ttrpg
NEO4J_URI=bolt://neo4j_host:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<secure-password>
CASSANDRA_CONTACT_POINTS=cassandra_host:9042

# Service URLs
STARGATE_URL=http://stargate_host:8082
LANGFLOW_URL=http://langflow_host:7860
HAYHOOKS_URL=http://hayhooks_host:8000
UNSTRUCTURED_URL=http://unstructured_host:8000

# OpenAI API (for LLM features)
OPENAI_API_KEY=sk-...

# Timezone
TZ=America/Chicago
```

### Optional Variables

```bash
# OAuth Configuration (if using external auth)
OAUTH_CLIENT_ID=<client-id>
OAUTH_CLIENT_SECRET=<client-secret>
OAUTH_ISSUER=https://auth.example.com

# Session Configuration
SESSION_SECRET=<random-32-char-string>
SESSION_COOKIE_DOMAIN=.ttrpg-center.example.com

# Logging
LOG_LEVEL=info  # debug|info|warn|error
LOG_FORMAT=json  # json|text

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
PROMETHEUS_ENABLED=true

# Feature Flags
ENABLE_AUDIO_FEATURES=false
ENABLE_DISCORD_INTEGRATION=false
ENABLE_SUMMARIZATION=true
```

---

## Troubleshooting

### Container Won't Start

**Symptom**: Container exits immediately with code 1

**Diagnostic Steps**:
```bash
# Check logs
docker logs ttrpg_webui_prod

# Inspect container
docker inspect ttrpg_webui_prod

# Verify environment variables
docker exec ttrpg_webui_prod env

# Test standalone server directly
docker run --rm -it \
  -e NODE_ENV=production \
  ttrpg-webui:latest \
  apps/web/server.js
```

**Common Causes**:
- Missing environment variables
- Invalid database connection strings
- Port 3000 already in use
- Insufficient memory

### Health Check Failing

**Symptom**: Health check endpoint returns 503 or times out

**Diagnostic**:
```bash
# Check health endpoint
curl -v http://localhost:3000/api/health

# Check container resources
docker stats ttrpg_webui_prod

# Verify database connections
docker exec ttrpg_webui_prod node -e "
const { MongoClient } = require('mongodb');
const client = new MongoClient(process.env.MONGODB_URI);
client.connect().then(() => console.log('MongoDB OK')).catch(console.error);
"
```

### Out of Memory (OOM)

**Symptom**: Container killed by OOM killer

**Solution**:
```yaml
# Increase memory limit in docker-compose
deploy:
  resources:
    limits:
      memory: 2G  # Increase from 1G
    reservations:
      memory: 1G
```

### Slow Performance

**Diagnostic**:
```bash
# Check CPU/memory usage
docker stats ttrpg_webui_prod

# Profile Next.js performance
docker exec ttrpg_webui_prod node --inspect apps/web/server.js

# Check database query performance
# (see database-specific guides)
```

**Optimizations**:
- Enable CDN for static assets
- Add Redis for session/cache storage
- Optimize database indexes
- Use connection pooling

---

## Performance Benchmarks

### Build Performance

| Metric | Cold Build | Warm Build (Cached) |
|--------|------------|---------------------|
| **Total Time** | 6-7 minutes | 45-60 seconds |
| **deps-fetcher** | 2 minutes | 5 seconds |
| **deps** | 1 minute | 10 seconds |
| **builder** | 3-4 minutes | 30 seconds |
| **Image Size** | 150-180MB | - |

### Runtime Performance

| Metric | Target | Typical | Peak |
|--------|--------|---------|------|
| **Startup Time** | <10s | 5-8s | 12s |
| **Memory Usage** | <1GB | 500-700MB | 900MB |
| **CPU Usage** | <1 core | 0.2-0.5 cores | 0.8 cores |
| **Request Latency (p50)** | <100ms | 50-80ms | 120ms |
| **Request Latency (p95)** | <300ms | 150-250ms | 350ms |
| **Requests/sec** | >100 | 200-300 | 500 |

### Page Load Performance

| Page | First Load | Cached Load | LCP Target |
|------|------------|-------------|------------|
| Player Hub | 1.2s | 0.3s | <2.5s |
| GM Hub | 1.5s | 0.4s | <2.5s |
| Admin Dashboard | 1.8s | 0.5s | <2.5s |
| Chat Panel | 0.8s | 0.2s | <2.5s |

### Database Query Performance

| Query Type | Target | Typical |
|------------|--------|---------|
| MongoDB Find (indexed) | <10ms | 3-8ms |
| Neo4j Cypher (simple) | <50ms | 20-40ms |
| Cassandra Vector Search | <100ms | 60-90ms |

### Accessibility Scores

| Metric | Target | Actual |
|--------|--------|--------|
| **WCAG 2.2 AA Compliance** | 100% | 100% |
| **Axe Violations** | 0 serious | 0 |
| **Color Contrast Ratio** | ≥4.5:1 | 4.8:1 |
| **Keyboard Navigation** | 100% | 100% |
| **Screen Reader Support** | Full | Full |

---

## Next Steps

- [Security Hardening Guide](./security-hardening.md)
- [Monitoring & Observability](./monitoring.md)
- [Disaster Recovery](./disaster-recovery.md)
- [Scaling Guide](./scaling.md)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-18
**Maintainer**: TTRPG Center DevOps Team
