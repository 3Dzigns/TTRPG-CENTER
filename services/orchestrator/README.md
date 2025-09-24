# Orchestrator Service

## Purpose
Classifier, policy engine, retriever, router, and prompts management for intelligent query handling.

## Responsibilities
- **Query Intent Classification (QIC)**: Classify queries by intent, domain, and complexity
- **Policy Engine**: Apply retrieval and workflow policies based on classification
- **Retriever**: Execute hybrid retrieval strategies (vector + metadata + graph)
- **Router**: Route queries to appropriate models and services
- **Prompts**: Manage dynamic prompt templates and model selection

## Architecture
- FastAPI service running on configurable ports (dev: 8004, test: 8185, prod: 8286)
- Sub-150ms p95 response time requirement for QIC
- Hybrid RAG + Graph system integration
- Structured telemetry and confidence scoring

## Setup
```bash
# Install dependencies
pip install -e .[dev]

# Run service
python -m services.orchestrator.api

# Run tests
pytest tests/unit/orchestrator/
pytest tests/functional/orchestrator/
```

## Environment Configuration
- `env/{ENV}/config/orchestrator.env` - Service-specific configuration
- `config/policies.yaml` - Retrieval and workflow policies
- `config/retrieval_policies.yaml` - Policy engine inputs
- `config/prompts/` - Prompt templates by intent/domain

## Core Components

### Classifier (`classifier.py`)
- US-201: Query Intent Classification
- Intent, domain, and complexity detection
- Confidence scoring and validation

### Policy Engine (`policy.py`)
- US-202: Policy-based retrieval decisions
- Dynamic strategy selection
- Configurable thresholds and rules

### Router (`router.py`)
- US-203: Model and service routing
- Load balancing and failover
- Performance optimization

### Prompts (`prompts.py`)
- US-204: Dynamic prompt management
- Template rendering and model selection
- Context-aware prompt generation

### Retriever (`retrieve.py`)
- US-205: Hybrid retrieval execution
- Vector, metadata, and graph search
- Result ranking and synthesis

## API Endpoints
- `POST /classify` - Classify query intent and complexity
- `POST /retrieve` - Execute retrieval strategy
- `POST /answer` - Generate answer with context
- `GET /policies` - Get current policies
- `GET /healthz` - Health check endpoint

## Status
🚧 **In Development** - Part of MVP v2 microservices architecture migration