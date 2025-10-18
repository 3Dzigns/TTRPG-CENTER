# TTRPG Center WebUI - Container Documentation

**Version**: 1.0.0
**Date**: 2025-10-18

---

## Overview

This directory contains comprehensive documentation for the TTRPG Center WebUI container architecture, deployment, and operations.

The WebUI is a Next.js 15 monorepo application providing Player, GM, and Admin hubs for TTRPG game management, built with TypeScript, Tailwind CSS, and shadcn/ui components.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| **[webui-container-design.md](./webui-container-design.md)** | Complete container architecture, multi-stage build strategy, security hardening, and performance optimization |
| **[deployment-guide.md](./deployment-guide.md)** | Step-by-step deployment instructions for development, staging, and production environments with troubleshooting |

---

## Quick Links

### For Developers
- **Development Setup**: See [deployment-guide.md § Development Deployment](./deployment-guide.md#development-deployment)
- **Build Optimization**: See [webui-container-design.md § Multi-Stage Build Strategy](./webui-container-design.md#multi-stage-build-strategy)
- **Troubleshooting**: See [deployment-guide.md § Troubleshooting](./deployment-guide.md#troubleshooting)

### For DevOps Engineers
- **Production Deployment**: See [deployment-guide.md § Production Deployment](./deployment-guide.md#production-deployment)
- **Security Hardening**: See [webui-container-design.md § Security Hardening](./webui-container-design.md#security-hardening)
- **CI/CD Pipeline**: See [../../.github/workflows/webui-container.yml](../../.github/workflows/webui-container.yml)

### For Architects
- **Architecture Diagrams**: See [webui-container-design.md § Architecture Overview](./webui-container-design.md#architecture-overview)
- **Network Design**: See [webui-container-design.md § Network Architecture](./webui-container-design.md#network-architecture)
- **Performance Benchmarks**: See [deployment-guide.md § Performance Benchmarks](./deployment-guide.md#performance-benchmarks)

---

## Container Images

### Available Dockerfiles

| Dockerfile | Target | Use Case |
|------------|--------|----------|
| `webui/Dockerfile` | runner | Original production Dockerfile |
| **`webui/Dockerfile.optimized`** | runner/development/testing | **Optimized multi-stage build (recommended)** |

### Available Profiles

| Profile | Image | Use Case | Resource Limits |
|---------|-------|----------|-----------------|
| **development** | ttrpg-webui:dev | Local development with hot-reload | 2 CPU, 2GB RAM |
| **staging** | ttrpg-webui:staging | Pre-production testing | 1.5 CPU, 1GB RAM |
| **production** | ttrpg-webui:latest | Production deployment | 1 CPU, 1GB RAM |

---

## Quick Start Commands

### Development
```bash
# Start development environment
docker-compose -f docker-compose-webui-enhanced.yml --profile development up

# Access at http://localhost:3000
```

### Staging
```bash
# Build and start staging environment
docker-compose -f docker-compose-webui-enhanced.yml --profile staging up --build

# Run smoke tests
npx playwright test --config=playwright.config.staging.ts
```

### Production
```bash
# Build optimized production image
docker build -f webui/Dockerfile.optimized -t ttrpg-webui:latest .

# Start production environment
docker-compose -f docker-compose-webui-enhanced.yml --profile production up -d

# Check health
curl http://localhost:3000/api/health
```

---

## Key Features

### 🚀 Performance Optimizations
- **Build Time**: 45-60s (cached), 6-7min (cold)
- **Image Size**: 150-180MB (distroless production)
- **Startup Time**: 5-8 seconds
- **Memory Usage**: 500-700MB typical
- **BuildKit Caching**: pnpm store and Docker layers

### 🔒 Security Hardening
- **Distroless Base**: No shell in production
- **Non-root User**: `nonroot:nonroot` (UID/GID 65532)
- **Minimal Attack Surface**: Only Node.js runtime
- **Security Scanning**: Trivy + Grype in CI/CD
- **Image Signing**: Cosign keyless signing
- **SBOM Generation**: Syft CycloneDX format

### 🎯 Development Experience
- **Hot Reload**: Source code volume mounts
- **Full DevTools**: curl, bash, debugging tools
- **Parallel Builds**: Independent packages build concurrently
- **Type Safety**: TypeScript strict mode throughout

### 📊 Monitoring & Observability
- **Health Checks**: `/api/health` endpoint
- **Metrics**: `/api/metrics` (Prometheus format)
- **Structured Logging**: JSON logs with `trace_id`
- **Resource Limits**: CPU/memory constraints enforced

---

## Architecture Highlights

### Monorepo Structure
```
apps/web/          # Next.js 15 App Router application
packages/
  ├── ui/          # Shared UI components (shadcn/ui)
  ├── types/       # TypeScript type definitions
  ├── api/         # Typed API client (fetch-based)
  └── config/      # Shared config (theme, ESLint, tsconfig)
```

### Multi-Stage Build Flow
```
base → deps-fetcher → deps → builder → runner (production)
                                    └→ development (dev mode)
                                    └→ testing (CI/CD)
```

### Technology Stack
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS + shadcn/ui (Radix)
- **State**: TanStack Query + Zustand
- **Forms**: react-hook-form + zod
- **Testing**: Vitest + RTL + Playwright

---

## WebUI Features (from 20 Prompts)

### Player Hub
- Character management (create, select, assign to game)
- Game selection and join via invite code
- Source multi-select (owned + game-allowed)
- Usage meters (text_assist, audio, Discord)
- Chat panel with streaming and citations

### GM Hub
- Game CRUD (create, delete with confirmation)
- Member management (invite, remove, role adjust)
- Source management (add/remove game sources)
- Settings (tier selection, feature toggles)
- Billing link integration

### Admin Dashboard
- Source table (view all, ownership override)
- User table (roles, usage, billing)
- System health audit
- Override panels for emergency actions

### Shared Features
- OAuth/OIDC authentication
- Role-aware routing (Player/GM/Admin)
- WCAG 2.2 AA accessibility compliance
- Responsive design (mobile/tablet/desktop)
- Dark/light theme with CSS variables

---

## CI/CD Pipeline

### Automated Workflows
- ✅ Multi-architecture builds (amd64, arm64)
- ✅ Security scanning (Trivy, Grype)
- ✅ SBOM generation (Syft)
- ✅ Image signing (Cosign)
- ✅ Automated testing (unit + e2e)
- ✅ Deployment to staging/production
- ✅ Old image cleanup

### GitHub Actions Workflow
See [.github/workflows/webui-container.yml](../../.github/workflows/webui-container.yml)

---

## Support & Maintenance

### Reporting Issues
- **GitHub Issues**: https://github.com/your-org/n8n_TTRPG_Center/issues
- **Security**: security@ttrpg-center.example.com

### Documentation Updates
This documentation is maintained by the TTRPG Center DevOps team.
**Review Cycle**: Quarterly

### Version History
| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-10-18 | Initial production-ready container design |

---

## Related Documentation

- [WebUI Prompts (20 specs)](../../Prompt%20Lib/WebUI/)
- [CLAUDE.md](../../CLAUDE.md) - Project-level Claude Code configuration
- [CHANGELOG.md](../../CHANGELOG.md) - Release notes

---

**Last Updated**: 2025-10-18
**Maintainer**: TTRPG Center DevOps Team
**License**: Internal Use Only
