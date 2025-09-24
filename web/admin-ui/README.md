# Admin UI

## Purpose
React/TypeScript Admin application for operational tools and system management.

## Responsibilities
- **System Monitoring**: Real-time system status and health checks
- **Job Management**: Monitor and control ingestion jobs
- **Test Console**: Execute external test suites (Unit/Functional/Security/Regression/Perf)
- **Artifacts Management**: Browse, download, and clean up job artifacts
- **Dictionary Management**: Update and validate dictionary entries
- **Configuration**: Manage system configuration and feature flags

## Technology Stack
- **Framework**: React + Vite
- **Language**: TypeScript
- **UI Components**: shadcn/ui
- **Styling**: Tailwind CSS
- **State Management**: React Query + Zustand
- **Testing**: Vitest + Playwright

## Setup
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test
npm run test:e2e
```

## Environment Configuration
- Development: http://localhost:3000
- Test: http://localhost:3001
- Production: Configured via environment variables

## Key Features

### Admin Test Console (MVP v2 Requirement)
- **External Test Execution**: Run test suites against any environment
- **Real-time Streaming**: Live test output and progress
- **Suite Selection**: Unit/Functional/Security/Regression/Performance
- **Environment Targeting**: Execute tests against dev/test/prod
- **Results Management**: View, download, and archive test results

### Dashboard
- System overview and health metrics
- Active jobs and processing status
- Resource utilization monitoring
- Alert and notification center

### Job Management
- Job queue visualization
- Individual job progress tracking
- Error investigation and debugging
- Job artifact access and download

### Artifacts Browser
- Navigate job output artifacts
- Manifest validation and integrity checks
- Bulk operations and cleanup
- Cross-environment artifact comparison

### Configuration Management
- Feature flag toggles
- Policy configuration editing
- Environment-specific settings
- Configuration validation and rollback

## Components Structure
```
src/
├── app/          # Main application setup
├── components/   # Reusable UI components
├── pages/        # Page components
│   ├── dashboard/
│   ├── jobs/
│   ├── artifacts/
│   ├── test-console/
│   └── config/
├── hooks/        # Custom React hooks
├── lib/          # Utility functions and API clients
└── test/         # Component tests
```

## API Integration
- **Admin API**: Primary backend integration (port 8001/8182/8283)
- **Orchestrator**: Health and status monitoring
- **Ingest Service**: Job management and control
- **External Test Runner**: Test execution coordination

## Coding Standards
- Follow MVP v2 TypeScript standards
- Component naming: PascalCase
- Files: kebab-case.tsx
- Props: typed interfaces, no prop drilling >3 levels
- Testing: Snapshot + accessibility checks

## Status
🚧 **In Development** - Part of MVP v2 microservices architecture migration

## Next Steps
1. Implement Admin Test Console for external test execution
2. Create job management interface
3. Build artifacts browser with manifest validation
4. Add configuration management UI