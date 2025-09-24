# Ingest Service

## Purpose
Pass 0→G pipeline and tools adapters for PDF processing and content ingestion.

## Responsibilities
- **Pass A**: PDF parsing and chunking using unstructured.io
- **Pass B**: Logical splitting with 10MB threshold (MVP v2 requirement)
- **Pass C**: Content extraction and enrichment using Haystack
- **Pass D**: Vector enrichment and embedding generation
- **Pass E**: Graph building using LlamaIndex
- Tools adapters for various document formats

## Architecture
- FastAPI service running on configurable ports (dev: 8003, test: 8184, prod: 8285)
- Async processing pipeline with job queues
- Artifact management and manifest generation
- Health checks and observability

## Setup
```bash
# Install dependencies
pip install -e .[dev]

# Run service
python -m services.ingest.api

# Run tests
pytest tests/unit/ingest/
pytest tests/functional/ingest/
```

## Environment Configuration
- `env/{ENV}/config/ingest.env` - Service-specific configuration
- `env/{ENV}/data/ingest/` - Input and working directories
- `env/{ENV}/logs/ingest/` - Service logs
- `env/{ENV}/artifacts/` - Output artifacts and manifests

## API Endpoints
- `POST /ingest/upload` - Upload document for processing
- `GET /ingest/jobs/{job_id}` - Get job status
- `GET /ingest/jobs/{job_id}/artifacts` - Download job artifacts
- `GET /healthz` - Health check endpoint

## Status
🚧 **In Development** - Part of MVP v2 microservices architecture migration