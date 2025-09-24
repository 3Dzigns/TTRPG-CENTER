# Admin API Service

## Purpose
Admin API for artifacts management, job monitoring, dictionary management, and HGRN (Hierarchical Graph Reference Navigation).

## Responsibilities
- **Artifacts Management**: Job artifacts, manifests, and cleanup
- **Job Monitoring**: Ingestion job status and progress tracking
- **Dictionary Management**: Dynamic dictionary updates and validation
- **HGRN**: Hierarchical Graph Reference Navigation system
- **Admin Operations**: System configuration and maintenance

## Architecture
- FastAPI service running on configurable ports (dev: 8001, test: 8182, prod: 8283)
- Integration with Admin UI Test Console
- External test execution coordination
- Comprehensive audit logging

## Setup
```bash
# Install dependencies
pip install -e .[dev]

# Run service
python -m services.admin_api.api

# Run tests
pytest tests/unit/admin_api/
pytest tests/functional/admin_api/
```

## Environment Configuration
- `env/{ENV}/config/admin_api.env` - Service-specific configuration
- `env/{ENV}/data/admin/` - Admin data and configurations
- `env/{ENV}/logs/admin/` - Service logs
- `env/{ENV}/artifacts/` - Managed artifacts

## Core Components

### Artifacts Management
- Job artifact storage and retrieval
- Manifest validation and integrity checks
- Cleanup policies and retention management
- Bulk operations and batch processing

### Job Monitoring
- Real-time job status tracking
- Progress reporting and ETA calculation
- Error handling and recovery coordination
- Performance metrics collection

### Dictionary Management
- Dynamic dictionary updates from Pass B
- Validation and consistency checks
- Version control and rollback capabilities
- Cross-environment synchronization

### HGRN System
- Hierarchical graph navigation
- Reference integrity validation
- Graph traversal optimization
- Relationship mapping and visualization

## API Endpoints
- `GET /artifacts` - List available artifacts
- `GET /artifacts/{job_id}` - Get job artifacts
- `DELETE /artifacts/{job_id}` - Clean up job artifacts
- `GET /jobs` - List all jobs with status
- `GET /jobs/{job_id}` - Get detailed job status
- `POST /dictionary/update` - Update dictionary entries
- `GET /dictionary/validate` - Validate dictionary consistency
- `GET /hgrn/navigate/{node_id}` - Navigate graph hierarchy
- `POST /test/execute` - Execute external test suites
- `GET /healthz` - Health check endpoint

## Status
🚧 **In Development** - Part of MVP v2 microservices architecture migration