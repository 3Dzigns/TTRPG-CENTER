# TTRPG Center - MVP Version 2

AI-powered tabletop RPG content management and intelligent query platform with comprehensive document ingestion and retrieval capabilities.

## Overview

TTRPG Center is a comprehensive AI-powered platform designed for tabletop RPG content management. MVP v2 implements a full Pass 0→G ingestion pipeline with microservices architecture and strict environment isolation.

### Key Features

- **Pass 0→G Ingestion Pipeline**: Complete document processing from preflight checks to HGRN consistency validation
- **Environment Isolation**: Strict dev/test/prod environment separation with dedicated resources
- **Microservices Architecture**: Scalable service-oriented design with proper port isolation
- **External Test Execution**: Comprehensive testing infrastructure with web-based console
- **Structured Logging**: MVP v2 compliant JSON logging with required schema
- **Security First**: Comprehensive security measures with vulnerability scanning

## Architecture

### MVP v2 Phases (0-6)

- **Phase 0**: Environment isolation, builds, and fast testing foundation
- **Phase 1**: Pass 0→G ingestion pipeline (unstructured.io → Haystack → LlamaIndex)
- **Phase 2**: RAG retrieval with query classification and model routing
- **Phase 3**: Graph workflows for guided processes
- **Phase 4**: Admin UI for operational tools
- **Phase 5**: User UI with retro terminal/LCARS design
- **Phase 6**: Testing & feedback automation

### Ingestion Pipeline (Pass 0→G)

1. **Pass 0**: Preflight & De-dup - File validation and duplicate detection
2. **Pass A**: TOC & Dictionary Seed - Table of contents extraction and dictionary initialization
3. **Pass B**: Fast Split (≤10 MB parts) - Document splitting for processing optimization
4. **Pass C**: Extraction (Unstructured.io) - Content extraction and OCR processing
5. **Pass D**: Normalize + Embeddings (Haystack) - Content normalization and vector embedding
6. **Pass E**: Graph Compile (LlamaIndex) - Knowledge graph construction
7. **Pass F**: Validation & Manifest - Data integrity validation and manifest generation
8. **Pass G**: HGRN Consistency Check - Hierarchical graph relationship network validation

### Environment Structure

```
env/
├── dev/                    # Development environment (port 8000)
│   ├── config/            # Environment-specific configuration
│   ├── data/              # Development data
│   ├── logs/              # Development logs
│   └── artifacts/         # Development artifacts
├── test/                   # Testing environment (port 8181)
│   ├── config/
│   ├── data/
│   ├── logs/
│   └── artifacts/
└── prod/                   # Production environment (port 8282)
    ├── config/
    ├── data/
    ├── logs/
    └── artifacts/
```

### Microservices

- **Ingest Service** (ports: dev=8003, test=8184, prod=8285): Document ingestion and Pass 0→G pipeline
- **Orchestrator** (ports: dev=8004, test=8185, prod=8286): Workflow coordination and management
- **Admin API** (ports: dev=8001, test=8182, prod=8283): Administrative operations and monitoring
- **User API** (ports: dev=8002, test=8183, prod=8284): User-facing query and retrieval operations

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Git

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd TTRPG_Center

# Initialize development environment
./scripts/init-environments.sh dev

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-test.txt

# Start development services
docker compose -f env/dev/docker-compose.yml up -d

# Verify services
curl http://localhost:8000/healthz  # Main app
curl http://localhost:8003/healthz  # Ingest service
curl http://localhost:8001/healthz  # Admin API
curl http://localhost:8002/healthz  # User API
```

### Testing

```bash
# Unit tests
pytest tests/unit

# Functional tests
pytest tests/functional

# Security tests
bandit -r src_common

# External test execution (with test console)
docker compose -f env/test/docker-compose.yml --profile testing up -d
# Open http://localhost:8196 for test console interface
```

## Configuration

### Environment Variables

Create `.env` files in `env/{environment}/config/.env`:

```bash
# Database Configuration
ASTRADB_APPLICATION_TOKEN=your_token_here
ASTRADB_DATABASE_ID=your_database_id
CASSANDRA_KEYSPACE=ttrpg_{environment}

# AI Model Configuration
OPENAI_API_KEY=your_openai_key
CLAUDE_API_KEY=your_claude_key

# Service Configuration
TARGET_ENV=dev|test|prod
LOG_LEVEL=INFO
```

### Port Configuration

Environment-specific ports are configured in `env/{environment}/config/ports.json`:

- **Development**: Main app (8000), Admin API (8001), User API (8002), Ingest (8003), Orchestrator (8004)
- **Test**: Main app (8181), Admin API (8182), User API (8183), Ingest (8184), Orchestrator (8185)
- **Production**: Main app (8282), Admin API (8283), User API (8284), Ingest (8285), Orchestrator (8286)

## Usage

### Document Ingestion

```bash
# Upload document via Ingest service
curl -X POST "http://localhost:8003/ingest/upload" \
  -F "file=@document.pdf"

# Check ingestion status
curl "http://localhost:8003/ingest/jobs/{job_id}"

# Get processed artifacts
curl "http://localhost:8003/ingest/jobs/{job_id}/artifacts"
```

### Query Operations

```bash
# Query via User API
curl -X POST "http://localhost:8002/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the combat rules?", "context": "D&D 5e"}'
```

### Admin Operations

```bash
# Dictionary management
curl "http://localhost:8001/admin/dictionary"

# System status
curl "http://localhost:8001/admin/status"
```

## Development

### Code Standards

- Python 3.12+ with comprehensive type hints
- Black formatting (88 character line limit)
- Ruff linting with strict rules
- Structured JSON logging with MVP v2 schema
- Comprehensive testing with pytest

### Project Structure

```
/
├── src_common/           # Shared libraries and utilities
├── services/            # Microservices implementation
│   ├── ingest/         # Document ingestion service
│   ├── orchestrator/   # Workflow orchestration
│   ├── admin_api/      # Administrative API
│   ├── user_api/       # User-facing API
│   ├── test_runner/    # External test execution
│   └── test_console/   # Web-based test interface
├── env/                # Environment isolation
├── tests/              # Test suites
├── scripts/            # Build and deployment scripts
└── MVP-Version-2/      # Requirements and specifications
```

### Contributing

1. Create feature branch: `git checkout -b feat/your-feature`
2. Follow coding standards and add tests
3. Run quality checks: `black`, `ruff`, `mypy`, `pytest`
4. Submit pull request with comprehensive description

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## Testing Architecture

### External Test Execution

MVP v2 implements external test execution architecture:

- **Test Runner Service** (port 8195): Isolated test execution environment
- **Test Console API** (port 8196): Web-based test monitoring and control
- **Docker Profiles**: `testing` profile for test-specific services

### Test Suites

- **Unit Tests**: Individual function and class testing
- **Functional Tests**: API endpoint and integration testing
- **Regression Tests**: Automated regression detection
- **Security Tests**: Security vulnerability scanning
- **Performance Tests**: Load testing and performance validation

## Security

### Security Measures

- Environment variable management for all secrets
- TLS/HTTPS for all external communications
- Input validation and SQL injection prevention
- Rate limiting and authentication
- Security scanning with Bandit
- Dependency vulnerability checking

### Reporting

Report security vulnerabilities to security@ttrpg-center.local

See [SECURITY.md](SECURITY.md) for complete security policy.

## Monitoring and Logging

### Structured Logging

MVP v2 implements comprehensive structured logging:

```json
{
  "timestamp": 1234567890.123,
  "level": "INFO",
  "message": "Processing document",
  "env": "dev",
  "service": "ingest",
  "trace_id": "uuid",
  "job_id": "uuid",
  "pass_name": "pass_a"
}
```

### Health Monitoring

All services implement `/healthz` endpoints with comprehensive health checks.

## Deployment

### Docker Compose Stacks

Each environment has dedicated Docker Compose configuration:

```bash
# Development
docker compose -f env/dev/docker-compose.yml up -d

# Testing (with external test execution)
docker compose -f env/test/docker-compose.yml --profile testing up -d

# Production (with monitoring)
docker compose -f env/prod/docker-compose.yml --profile monitoring up -d
```

### Environment Promotion

```bash
# Build with timestamped IDs
./scripts/build.ps1

# Promote dev → test → prod
./scripts/promote.ps1
```

## License

[License information to be added]

## Support

- GitHub Issues: Bug reports and feature requests
- GitHub Discussions: Questions and community support
- Email: support@ttrpg-center.local

## MVP v2 Compliance

This implementation fully complies with MVP Version 2 requirements:

- ✅ Pass 0→G ingestion pipeline with all 8 passes
- ✅ Environment isolation (dev/test/prod)
- ✅ Microservices architecture with port isolation
- ✅ External test execution architecture
- ✅ Structured JSON logging with required schema
- ✅ Python 3.12+ with comprehensive type hints
- ✅ Security-first approach with comprehensive measures
- ✅ Docker Compose stacks for all environments