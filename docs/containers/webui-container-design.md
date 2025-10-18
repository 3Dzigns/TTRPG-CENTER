# TTRPG Center WebUI - Container Design Documentation

**Date**: 2025-10-18
**Version**: 1.0.0
**Status**: Production-Ready

---

## Executive Summary

This document describes the containerized architecture for the TTRPG Center WebUI, a Next.js 15 monorepo application providing Player, GM, and Admin hubs for TTRPG game management.

**Key Features**:
- Multi-stage Docker build optimized for size and security
- Production-ready with distroless base image
- Multiple deployment profiles (development, staging, production)
- Security-hardened with non-root user and minimal attack surface
- Integrated health checks and monitoring
- Resource-optimized with BuildKit caching

---

## Architecture Overview

### Application Stack

```
TTRPG Center WebUI
├── Next.js 15 (App Router)
├── TypeScript (strict mode)
├── Tailwind CSS + shadcn/ui
├── TanStack Query (server state)
├── Zustand (client state)
└── Monorepo Structure (pnpm workspaces)
    ├── apps/web          # Main Next.js app
    ├── packages/ui       # Shared UI components
    ├── packages/types    # TypeScript types
    ├── packages/api      # Typed API client
    └── packages/config   # Shared configuration
```

### Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Multi-Stage Build                        │
├─────────────────────────────────────────────────────────────┤
│ Stage 0: base           │ Common Alpine Node 20 layer       │
│ Stage 1: deps-fetcher   │ pnpm fetch (cached layer)         │
│ Stage 2: deps           │ pnpm install (offline)            │
│ Stage 3: builder        │ TypeScript compilation            │
│ Stage 4: runner         │ Distroless production runtime     │
│ Stage 5: development    │ Hot-reload dev environment        │
│ Stage 6: testing        │ CI/CD testing stage               │
└─────────────────────────────────────────────────────────────┘
```

---

## Multi-Stage Build Strategy

### Stage 0: Base (Common Layer)
- **Image**: `node:20-alpine`
- **Purpose**: Common base for all stages
- **Optimizations**:
  - pnpm corepack enabled
  - Security updates applied
  - Maximum layer reuse

### Stage 1: Dependencies Fetcher
- **Purpose**: Create pnpm virtual store (cached layer)
- **Key Files**: `pnpm-lock.yaml` only
- **Caching Strategy**: Invalidates only on lock file change
- **Command**: `pnpm fetch --prod`
- **Build Time**: ~30 seconds (cached), ~2 minutes (uncached)

### Stage 2: Dependencies Installer
- **Purpose**: Install all workspace dependencies
- **Mode**: Offline using fetched packages
- **Command**: `pnpm install --frozen-lockfile --prefer-offline`
- **Build Time**: ~1 minute

### Stage 3: Builder
- **Purpose**: Compile TypeScript and build Next.js
- **Build Order**:
  1. `@ttrpg-center/types` (first - base types)
  2. `@ttrpg-center/config` (second - configs)
  3. `@ttrpg-center/ui` + `@ttrpg-center/api` (parallel)
  4. `@ttrpg-center/web` (last - Next.js app)
- **Output**: Next.js standalone bundle
- **Build Time**: ~3-4 minutes

### Stage 4: Runner (Production)
- **Image**: `gcr.io/distroless/nodejs20-debian12:nonroot`
- **Size**: ~150-180MB (optimized)
- **Security**:
  - No shell (distroless)
  - Non-root user (`nonroot:nonroot`)
  - Minimal attack surface
- **Contents**: Next.js standalone output only

### Stage 5: Development
- **Image**: `node:20-alpine` with dev tools
- **Purpose**: Hot-reload development environment
- **Features**:
  - Volume mounts for source code
  - Full devDependencies installed
  - curl/bash for debugging
  - Next.js dev server

### Stage 6: Testing
- **Purpose**: CI/CD quality gates
- **Tests Run**:
  - Linting (`pnpm -w lint`)
  - Type checking (`pnpm -w typecheck`)
  - Unit tests (`pnpm -w test`)
  - Build verification

---

## Network Architecture

### Service Dependencies

```
WebUI (Port 3000)
    ├── n8n (Port 5678)          # API Gateway
    ├── MongoDB (Port 27017)     # Document store
    ├── Neo4j (Port 7687)        # Graph database
    ├── Cassandra (Port 9042)    # Vector embeddings
    ├── Stargate (Port 8082)     # Cassandra API
    ├── LangFlow (Port 7860)     # LLM workflows
    ├── Hayhooks (Port 8000)     # Haystack API
    └── Unstructured (Port 8000) # Document parsing
```

### Network Configuration
- **Network**: `n8n_TTRPG_network` (external bridge)
- **Internal DNS**: Docker DNS resolution
- **Public Port**: 3000 (WebUI HTTPS via reverse proxy)

---

## Deployment Profiles

### 1. Development Profile

**Use Case**: Local development with hot-reload

**Command**:
```bash
docker-compose -f docker-compose-webui-enhanced.yml --profile development up
```

**Features**:
- Source code volume mounts
- Hot-reload enabled
- Debug logging
- Relaxed resource limits (2 CPU, 2GB RAM)
- Shell access for debugging

**Dockerfile Target**: `development`

---

### 2. Staging Profile

**Use Case**: Pre-production testing with production-like build

**Command**:
```bash
docker-compose -f docker-compose-webui-enhanced.yml --profile staging up
```

**Features**:
- Production build with Next.js standalone
- Moderate resource limits (1.5 CPU, 1GB RAM)
- Security hardening enabled
- Separate staging database

**Dockerfile Target**: `runner`

---

### 3. Production Profile

**Use Case**: Production deployment with maximum security

**Command**:
```bash
docker-compose -f docker-compose-webui-enhanced.yml --profile production up
```

**Features**:
- Distroless runtime
- Strict resource limits (1 CPU, 1GB RAM)
- Full security hardening:
  - `no-new-privileges:true`
  - `read_only: false` (Next.js needs .next cache)
  - `cap_drop: ALL`
  - tmpfs for /tmp
- Structured JSON logging
- External health monitoring
- Automatic restart policies

**Dockerfile Target**: `runner`

---

## Security Hardening

### Container Security Measures

| Security Feature | Development | Staging | Production |
|-----------------|-------------|---------|------------|
| **Distroless Base** | ❌ (Alpine) | ✅ | ✅ |
| **Non-root User** | ✅ | ✅ | ✅ |
| **no-new-privileges** | ❌ | ✅ | ✅ |
| **Read-only Root** | ❌ | ❌ | ❌* |
| **Capability Drop** | ❌ | ❌ | ✅ |
| **tmpfs /tmp** | ❌ | ✅ | ✅ |
| **Security Updates** | ✅ | ✅ | ✅ |

*Note: Next.js standalone requires write access to `.next` cache directory

### Vulnerability Scanning

**Tools**:
- **Trivy**: Container image CVE scanning
- **Snyk**: Dependency vulnerability analysis
- **Grype**: SBOM-based security audits

**CI/CD Integration**:
```bash
# Scan production image
trivy image --severity HIGH,CRITICAL ttrpg-webui:latest

# Generate SBOM
syft ttrpg-webui:latest -o json > sbom.json
```

---

## Resource Management

### Memory Allocation

| Profile | Limit | Reservation | Typical Usage |
|---------|-------|-------------|---------------|
| Development | 2GB | 512MB | 800MB-1.2GB |
| Staging | 1GB | 512MB | 600MB-800MB |
| Production | 1GB | 512MB | 500MB-700MB |

### CPU Allocation

| Profile | Limit | Reservation | Typical Usage |
|---------|-------|-------------|---------------|
| Development | 2.0 cores | 0.5 cores | 0.5-1.5 cores |
| Staging | 1.5 cores | 0.5 cores | 0.3-1.0 cores |
| Production | 1.0 cores | 0.5 cores | 0.2-0.8 cores |

### Storage

- **Image Size**: 150-180MB (production), 800MB-1GB (development)
- **Runtime Disk**: Minimal (Next.js standalone self-contained)
- **Temp Space**: 100MB (tmpfs)

---

## Health Checks & Monitoring

### Health Check Endpoint

**Endpoint**: `GET /api/health`

**Response Format**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-18T10:30:00Z",
  "uptime": 3600,
  "version": "1.0.0",
  "dependencies": {
    "mongodb": "connected",
    "neo4j": "connected",
    "cassandra": "connected"
  }
}
```

### Development Health Check
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### Production Monitoring

**External Monitoring** (distroless has no curl):
- Kubernetes liveness/readiness probes
- Prometheus metrics scraping
- External monitoring service (Datadog, New Relic)

**Metrics Endpoint**: `GET /api/metrics` (Prometheus format)

---

## Build Performance

### Build Time Benchmarks

| Stage | Cold Build | Warm Build (Cached) |
|-------|------------|---------------------|
| deps-fetcher | 2 minutes | 5 seconds |
| deps | 1 minute | 10 seconds |
| builder | 3-4 minutes | 30 seconds |
| **Total** | **6-7 minutes** | **45-60 seconds** |

### BuildKit Cache Optimization

**Enable BuildKit**:
```bash
export DOCKER_BUILDKIT=1
```

**Cache Mounts**:
- `pnpm store`: `/root/.local/share/pnpm/store`
- `Next.js cache`: `.next/cache`

**Multi-arch Builds**:
```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --cache-from type=registry,ref=ttrpg-webui:cache \
  --cache-to type=registry,ref=ttrpg-webui:cache,mode=max \
  -t ttrpg-webui:latest \
  -f webui/Dockerfile.optimized .
```

---

## Logging

### Log Configuration

**Development**:
- Driver: `json-file`
- Max Size: 10MB
- Max Files: 3

**Staging**:
- Driver: `json-file`
- Max Size: 10MB
- Max Files: 5
- Labels: `env=staging`

**Production**:
- Driver: `json-file` (or external driver)
- Max Size: 10MB
- Max Files: 10
- Labels: `env=production,service=webui`
- Tag: `{{.Name}}/{{.ID}}`

### Log Structure

```json
{
  "timestamp": "2025-10-18T10:30:00Z",
  "level": "info",
  "service": "webui",
  "trace_id": "abc123",
  "message": "User authenticated",
  "context": {
    "userId": "user_123",
    "role": "player"
  }
}
```

---

## Troubleshooting

### Common Issues

#### 1. Build Fails at pnpm install
**Symptom**: `pnpm install` fails with network errors

**Solution**:
```bash
# Clear BuildKit cache
docker builder prune -af

# Rebuild without cache
docker build --no-cache -f webui/Dockerfile.optimized .
```

#### 2. Next.js standalone output not found
**Symptom**: Build fails with "standalone output not found"

**Solution**: Verify `next.config.js` has standalone output enabled:
```javascript
module.exports = {
  output: 'standalone',
  // ...
}
```

#### 3. Container crashes immediately
**Symptom**: Container exits with code 1

**Solution**: Check logs and health check endpoint:
```bash
docker logs ttrpg_webui_prod
docker exec ttrpg_webui_prod node -e "console.log('Health check test')"
```

#### 4. Out of Memory (OOM) errors
**Symptom**: Container killed by OOM killer

**Solution**: Increase memory limit in docker-compose:
```yaml
deploy:
  resources:
    limits:
      memory: 2G  # Increase from 1G
```

---

## CI/CD Integration

### GitHub Actions Workflow

See `.github/workflows/webui-container.yml` for complete CI/CD pipeline.

**Pipeline Steps**:
1. **Checkout** code
2. **Setup** BuildKit and Docker Buildx
3. **Cache** pnpm store and Docker layers
4. **Build** multi-stage Dockerfile
5. **Test** using `testing` stage
6. **Scan** with Trivy for CVEs
7. **Generate** SBOM with Syft
8. **Sign** image with Cosign
9. **Push** to registry

---

## Performance Tuning

### Optimization Checklist

- ✅ Multi-stage build with minimal runtime
- ✅ BuildKit cache mounts for pnpm store
- ✅ Next.js standalone output
- ✅ Parallel package builds (ui + api)
- ✅ Distroless base image
- ✅ Resource limits defined
- ✅ tmpfs for temporary files
- ⚠️ Consider CDN for static assets
- ⚠️ Consider Redis for session storage

### Next.js Optimizations

**next.config.js**:
```javascript
module.exports = {
  output: 'standalone',
  compress: true,
  swcMinify: true,
  images: {
    unoptimized: false,
    domains: ['cdn.example.com'],
  },
  experimental: {
    optimizeCss: true,
    optimizePackageImports: ['@ttrpg-center/ui'],
  },
}
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-10-18 | Initial production-ready container design |

---

## References

- [Next.js 15 Documentation](https://nextjs.org/docs)
- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Distroless Container Images](https://github.com/GoogleContainerTools/distroless)
- [pnpm Workspaces](https://pnpm.io/workspaces)
- [TTRPG Center WebUI Prompts](../Prompt%20Lib/WebUI/)

---

**Document Owner**: TTRPG Center DevOps Team
**Last Updated**: 2025-10-18
**Review Cycle**: Quarterly
