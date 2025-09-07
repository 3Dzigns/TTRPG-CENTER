# TTRPG Center - Project Architecture Documentation

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Multi-Phase Development Structure](#multi-phase-development-structure)
4. [Environment Isolation System](#environment-isolation-system)
5. [Technology Stack](#technology-stack)
6. [Core Components](#core-components)
7. [Data Flow Architecture](#data-flow-architecture)
8. [Security & Testing Standards](#security--testing-standards)
9. [Development Workflows](#development-workflows)
10. [Deployment & Operations](#deployment--operations)
11. [API Reference](#api-reference)
12. [Quick Start Guide](#quick-start-guide)

---

## Project Overview

**TTRPG Center** is a comprehensive AI-powered platform for tabletop RPG content management and intelligent query handling. The system processes TTRPG PDFs through a sophisticated multi-phase ingestion pipeline and provides intelligent retrieval through various interfaces including web UI, APIs, and real-time communication.

### Key Capabilities
- **Intelligent Document Processing**: Multi-pass PDF ingestion (Parse → Enrich → Graph Compile)
- **Advanced Query Classification**: Intent-based routing with complexity analysis
- **Graph-Centered Reasoning**: Knowledge graphs for multi-hop reasoning and workflow management
- **Multi-Model AI Integration**: Dynamic model selection based on query type and complexity
- **Real-Time Interfaces**: WebSocket support, Discord integration capabilities
- **Environment Isolation**: Strict dev/test/prod separation with independent configurations
- **Comprehensive Testing**: Unit, functional, regression, and security test suites

### Architecture Philosophy
- **Phase-Driven Development**: 7 distinct phases with clear acceptance criteria
- **Graph-First Design**: Knowledge graphs as the backbone for reasoning and workflows
- **AI-Powered Intelligence**: Multi-model orchestration for optimal performance
- **Security by Design**: Environment isolation, PII redaction, injection protection
- **Observability**: Structured logging, telemetry, and comprehensive tracing

---

## System Architecture

### High-Level Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TTRPG Center Platform                         │
├─────────────────────────────────────────────────────────────────────────┤
│  User Interfaces                                                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │  Web UI     │ │  Admin UI   │ │  Discord    │ │  REST API   │      │
│  │ (Phase 5)   │ │ (Phase 4)   │ │ Integration │ │             │      │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │
├─────────────────────────────────────────────────────────────────────────┤
│  Core Orchestration Layer                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │   Query     │ │   Model     │ │  Workflow   │ │   Graph     │      │
│  │ Classifier  │ │   Router    │ │   Engine    │ │   Store     │      │
│  │ (Phase 2)   │ │ (Phase 2)   │ │ (Phase 3)   │ │ (Phase 3)   │      │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │
├─────────────────────────────────────────────────────────────────────────┤
│  AI & Processing Services                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │  Retrieval  │ │  Reasoning  │ │   Model     │ │  Feedback   │      │
│  │   Engine    │ │   Engine    │ │ Integration │ │   System    │      │
│  │ (Phase 2)   │ │ (Phase 3)   │ │             │ │ (Phase 6)   │      │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │
├─────────────────────────────────────────────────────────────────────────┤
│  Document Processing Pipeline                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                      │
│  │   Pass A    │ │   Pass B    │ │   Pass C    │                      │
│  │ PDF Parser  │ │  Enricher   │ │ Graph Comp. │                      │
│  │(Unstr'd.io) │ │ (Haystack)  │ │(LlamaIndex) │                      │
│  └─────────────┘ └─────────────┘ └─────────────┘                      │
├─────────────────────────────────────────────────────────────────────────┤
│  Data & Storage Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│  │  AstraDB    │ │  Knowledge  │ │  Workflow   │ │   Local     │      │
│  │ (Vectors &  │ │   Graph     │ │   Graph     │ │  Storage    │      │
│  │ Dictionary) │ │ (Neo4j/Mem) │ │ (State Mgmt)│ │ (Dev/Test)  │      │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Architectural Principles
1. **Microservices-Oriented**: Loosely coupled components with clear interfaces
2. **Event-Driven**: Status updates, workflow state changes via WebSocket broadcasts
3. **Graph-Centric**: Knowledge graphs drive reasoning and workflow decomposition
4. **Multi-Tenant Ready**: Environment isolation supports scaling to multiple instances
5. **AI-First**: Every major operation involves intelligent decision making

---

## Multi-Phase Development Structure

The project follows a 7-phase development methodology, each with specific objectives and acceptance criteria:

### Phase 0: Foundation & Environment Isolation
**Status**: ✅ Complete  
**Objective**: Establish clean, reproducible foundation with strict environment isolation

- **Environment Structure**: `env/{dev|test|prod}/{code|config|data|logs}`
- **Port Assignments**: dev=8000, test=8181, prod=8282
- **CI/CD Bootstrap**: GitHub Actions for Unit/Functional/Security/Regression testing
- **Logging Infrastructure**: Structured JSON logging with environment context
- **Security Foundations**: Secrets management, .env hygiene, gitignore compliance

### Phase 1: Ingestion Pipeline
**Status**: ✅ Complete  
**Objective**: Production-grade three-pass PDF processing with hard acceptance gates

- **Pass A - Parse/Chunk**: unstructured.io PDF extraction with metadata
- **Pass B - Enrich**: Haystack normalization with dictionary updates  
- **Pass C - Graph Compile**: LlamaIndex graph construction with entity linking
- **Quality Gates**: Each pass must use real tools, emit contract-compliant outputs
- **Artifact Management**: Job manifests, checksums, version tracking
- **AstraDB Integration**: Dictionary persistence with CI fallbacks

### Phase 2: Intelligent Retrieval & Model Routing
**Status**: ✅ Complete  
**Objective**: Query classification, policy-driven retrieval, dynamic model selection

- **Query Intent Classifier**: Heuristic + LLM fallback with 85%+ F1 score
- **Retrieval Policy Engine**: YAML-driven hybrid vector/metadata/graph policies
- **Model Router**: Cost/latency-aware model selection (GPT-4o, Claude, local models)
- **Prompt Template Library**: Versioned, intent-specific system prompts
- **Self-Consistency**: Multi-sample generation for high-complexity reasoning
- **Observability**: OpenTelemetry spans, correlation IDs, PII redaction

### Phase 3: Graph-Centered Workflows
**Status**: ✅ Complete  
**Objective**: Multi-step reasoning via knowledge graphs and workflow orchestration

- **Graph Schema**: Rules, Concepts, Procedures, Steps, Entities with versioned storage
- **Task Planner**: Graph-aware goal decomposition into executable DAGs
- **Workflow Engine**: Retry policies, state management, partial recovery
- **Human-in-the-Loop**: Approval checkpoints for complex/expensive operations
- **Provenance Tracking**: End-to-end citation and audit trails
- **Budget Enforcement**: Token/time limits with graceful degradation

### Phase 4: Admin UI
**Status**: ✅ Complete  
**Objective**: Operational tools for system management and monitoring

- **System Status Dashboard**: Real-time health monitoring, artifact browser
- **Ingestion Console**: Job management, pass status tracking, log streaming
- **Dictionary Management**: Term browsing, manual curation, bulk operations
- **Testing Interface**: Integration test runner, golden file management
- **Cache Control**: TTL management, invalidation triggers, development overrides

### Phase 5: User UI
**Status**: ✅ Complete  
**Objective**: End-user interface with retro terminal/LCARS design aesthetic

- **Query Interface**: Natural language input with real-time suggestions
- **Response Display**: Formatted answers with expandable source citations
- **Workflow Visualization**: Task progress tracking, approval interfaces
- **WebSocket Integration**: Real-time updates, collaborative features
- **Theme System**: LCARS aesthetic with accessibility compliance
- **Session Management**: Query history, saved workflows, user preferences

### Phase 6: Testing & Feedback
**Status**: ✅ Complete  
**Objective**: Automated testing infrastructure and user feedback loops

- **Comprehensive Test Suites**: Unit (>90% coverage), functional, regression, security
- **Golden File Management**: Baseline comparisons for classifier accuracy
- **Feedback Collection**: User ratings, issue reporting, improvement suggestions
- **Performance Monitoring**: Response time tracking, resource usage metrics
- **Automated Quality Gates**: CI/CD integration with quality thresholds

### Phase 7: Requirements & Features Management
**Status**: ✅ Complete  
**Objective**: Structured requirements management and feature evolution

- **Requirements Database**: Structured feature specifications with traceability
- **Schema Validation**: Automated validation of requirement document structure
- **Feature Lifecycle**: Request → Analysis → Implementation → Validation workflows
- **Impact Assessment**: Dependency analysis, breaking change detection
- **Documentation Generation**: Automated specification updates from code changes

---

## Environment Isolation System

### Directory Structure
```
TTRPG_Center/
├── env/                      # Environment-specific configurations
│   ├── dev/                  # Development environment
│   │   ├── code/            # DEV code deployment (symlink/copy)
│   │   ├── config/          # DEV configuration (.env, ports.json, logging.json)
│   │   ├── data/            # DEV data scratch (gitignored)
│   │   └── logs/            # DEV application logs
│   ├── test/                # Testing environment (port 8181)
│   └── prod/                # Production environment (port 8282)
├── src_common/              # Shared library modules (env-agnostic)
├── artifacts/               # Processing artifacts by environment
│   └── {ENV}/{JOB_ID}/     # Ingestion job outputs
├── tests/                   # Test suites
├── scripts/                 # Environment and build automation
├── docs/                    # Documentation
└── static/                  # Web UI assets
```

### Environment Configuration
Each environment maintains complete isolation:
- **Dedicated ports**: No cross-environment port conflicts
- **Separate configurations**: Environment-specific .env files
- **Isolated data**: Independent data directories and logs  
- **Independent artifacts**: Per-environment ingestion outputs
- **Network isolation**: Environment-specific API keys and endpoints

### Environment Variables
```bash
# Core Configuration
APP_ENV=dev|test|prod
PORT=8000|8181|8282
LOG_LEVEL=DEBUG|INFO|WARN|ERROR

# Database Configuration  
ASTRA_ENDPOINT=https://...
ASTRA_KEYSPACE=ttrpg_center
ASTRA_APPLICATION_TOKEN=AstraCS:...

# AI Service Configuration
OPENAI_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...

# Performance Tuning
CACHE_TTL_SECONDS=300
MAX_CONCURRENT_REQUESTS=10
```

---

## Technology Stack

### Core Technologies
- **Application Framework**: FastAPI with async support
- **Python Version**: 3.12+ with type hints and modern features
- **Web Server**: Uvicorn with auto-reload in development

### AI & Machine Learning
- **Document Processing**: unstructured.io, Haystack, LlamaIndex
- **Language Models**: OpenAI GPT-4o/4o-mini, Claude 3 Sonnet/Haiku
- **Embeddings**: sentence-transformers, OpenAI embeddings
- **Vector Search**: AstraDB with similarity search capabilities

### Data Storage
- **Primary Database**: AstraDB (Cassandra) with vector extensions
- **Knowledge Graph**: Neo4j (production) / In-memory (development)  
- **Workflow State**: Local JSON with migration paths to Redis/PostgreSQL
- **File Storage**: Local filesystem with S3-compatible backends planned

### Development & Testing
- **Testing**: pytest with asyncio support, coverage reporting
- **Code Quality**: bandit security scanning, type checking
- **Documentation**: Markdown with structured phase documentation
- **CI/CD**: GitHub Actions with matrix testing across environments

### Infrastructure
- **Containerization**: Docker support with environment-specific images
- **Monitoring**: Structured logging with JSON output, OpenTelemetry traces
- **Security**: Environment variable secrets, PII redaction, input sanitization
- **Performance**: Connection pooling, caching strategies, resource limits

---

## Core Components

### 1. Query Classification System (`src_common/orchestrator/classifier.py`)
**Purpose**: Intent recognition and complexity analysis for incoming queries

**Key Features**:
- Heuristic-first classification with LLM fallback
- Intent categories: fact_lookup, procedural_howto, creative_write, code_help, summarize, multi_hop_reasoning
- Domain detection: ttrpg_rules, ttrpg_lore, admin, system, unknown
- Complexity scoring: low/medium/high based on content analysis
- Sub-150ms p95 response time target

**Integration Points**:
- Feeds into Retrieval Policy Engine for strategy selection
- Influences Model Router decisions for optimal AI model selection
- Drives Workflow Engine task decomposition strategies

### 2. Retrieval Policy Engine (`src_common/orchestrator/policies.py`)
**Purpose**: Configuration-driven retrieval strategy selection

**Key Features**:
- YAML-based policy configuration with hot-reload
- Hybrid retrieval: vector search + metadata filtering + graph traversal
- Re-ranking strategies: MMR (Maximal Marginal Relevance), SBERT
- Cost guardrails: graph_depth ≤ 3, vector_top_k ≤ 50
- Graceful fallback hierarchy for unknown intents/domains

**Policy Structure**:
```yaml
ttrpg_rules:
  fact_lookup:
    low: { vector_top_k: 5, filters: {system: "PF2E"}, rerank: "mmr" }
    high: { vector_top_k: 12, graph_depth: 2, self_consistency: 3 }
```

### 3. Graph Store (`src_common/graph/store.py`)
**Purpose**: Knowledge and workflow graph storage with versioning

**Schema**:
- **Nodes**: Rule, Concept, Procedure, Step, Entity, SourceDoc, Artifact, Decision
- **Edges**: depends_on, part_of, implements, cites, produces, variant_of, prereq
- **Metadata**: Created/updated timestamps, version numbers, properties

**Security Features**:
- PII redaction in node properties
- Parametrized queries to prevent injection
- Depth limits (max 10) and neighbor limits (max 1000)
- Write-ahead logging for operation auditability

### 4. Task Planner (`src_common/planner/plan.py`)
**Purpose**: Graph-aware decomposition of user goals into executable workflows

**Workflow Generation**:
1. **Procedure Selection**: Graph search for relevant procedures
2. **Step Expansion**: Traverse graph to find constituent steps
3. **DAG Construction**: Create task dependencies with cycle detection
4. **Tool Assignment**: Map task types to appropriate tools/models
5. **Cost Estimation**: Token/time budgeting with approval checkpoints

**Budget Management**:
- Token limits: 50,000 per workflow
- Time limits: 300 seconds per workflow  
- Task limits: 20 tasks per workflow
- Automatic checkpoint injection for expensive operations

### 5. Workflow Runtime (`src_common/runtime/execute.py`)
**Purpose**: DAG execution with retry policies and state management

**Execution Features**:
- Status tracking: pending → running → succeeded/failed/skipped
- Retry policies: exponential backoff, configurable max attempts
- Parallel execution: Configurable concurrency limits
- State persistence: JSON-based with migration to distributed stores
- Artifact management: Checksum validation, download links

**Recovery Mechanisms**:
- Partial replay from checkpoints
- Dependency resolution after failures
- Idempotent task execution with deduplication keys

---

## Data Flow Architecture

### 1. Document Ingestion Pipeline
```
PDF Input → Pass A (Parse) → Pass B (Enrich) → Pass C (Graph) → Storage
    ↓           ↓                ↓                 ↓             ↓
  Validation  Chunks         Enriched+Dict    Graph+Links    AstraDB
             (JSON)           (JSON)          (JSON)        (Vector)
```

**Pass A - PDF Parsing**:
- Tool: unstructured.io
- Input: PDF files
- Output: Chunked text with page/section metadata
- Validation: Required fields, page coverage, content sanity

**Pass B - Enrichment**:  
- Tool: Haystack
- Input: Pass A chunks
- Output: Normalized text + extracted terms + dictionary deltas
- Validation: Referential integrity, term source citations

**Pass C - Graph Compilation**:
- Tool: LlamaIndex
- Input: Pass B enriched chunks + dictionary
- Output: Knowledge graph with nodes and edges
- Validation: Node coverage, edge consistency, checksum stability

### 2. Query Processing Pipeline
```
Query → Classifier → Policy → Retrieval → Router → Model → Answer
  ↓         ↓          ↓         ↓         ↓       ↓        ↓
Intent   Strategy   Context    Model     Call   Response Citations
                   Chunks     Selection
```

**Query Flow**:
1. **Classification**: Intent/domain/complexity analysis
2. **Policy Selection**: Retrieval strategy based on classification
3. **Context Retrieval**: Hybrid vector/metadata/graph search
4. **Model Routing**: Select appropriate AI model and configuration
5. **Answer Generation**: Prompt rendering and model invocation
6. **Citation Assembly**: Source aggregation and formatting

### 3. Workflow Execution Pipeline
```
Goal → Planner → DAG → Executor → State → Results
  ↓       ↓       ↓        ↓       ↓        ↓
Graph    Tasks   Deps    Runtime Status  Artifacts
Search          
```

**Workflow Stages**:
1. **Goal Analysis**: Extract requirements and constraints
2. **Procedure Matching**: Graph search for relevant workflows
3. **Task Decomposition**: Break into executable units with dependencies
4. **Resource Planning**: Estimate costs and identify checkpoints
5. **Execution**: Parallel task processing with retry logic
6. **State Management**: Progress tracking and artifact collection

---

## Security & Testing Standards

### Security Architecture

**Environment Isolation**:
- Strict separation of dev/test/prod configurations
- No cross-environment resource sharing
- Independent secret management per environment

**Input Validation**:
- Query sanitization to prevent injection attacks
- Graph query parameterization
- File upload validation and size limits
- Prompt injection detection and mitigation

**Data Protection**:
- PII redaction in logs and graph properties
- Sensitive data masking in API responses
- Secure secret storage with environment variables
- Token/API key rotation support

**Access Control**:
- Environment-specific access patterns
- Human-in-the-loop approval workflows
- Budget enforcement and resource limits
- Audit logging for all critical operations

### Testing Strategy

**Unit Tests** (>90% Coverage):
```python
tests/unit/
├── test_classifier.py       # Intent classification accuracy
├── test_policies.py         # Policy selection and fallbacks
├── test_graph_store.py      # Graph operations and validation
├── test_planner.py          # Workflow planning and DAG construction
├── test_executor.py         # Task execution and retry logic
└── test_security.py         # Input sanitization and PII redaction
```

**Functional Tests** (End-to-End):
```python
tests/functional/
├── test_ingestion.py        # Full pipeline with real tools
├── test_rag_retrieval.py    # Query → answer workflows
├── test_workflows.py        # Complex multi-step processes
├── test_api_endpoints.py    # REST API contract compliance
└── test_websockets.py       # Real-time communication
```

**Regression Tests** (Golden Files):
```python
tests/regression/
├── classifier_baselines/    # Intent classification snapshots
├── retrieval_golden/        # Query → chunk ID mappings
├── workflow_snapshots/      # DAG structure baselines
└── answer_comparisons/      # Response quality benchmarks
```

**Security Tests**:
```python
tests/security/
├── test_injection.py        # Prompt injection resistance
├── test_pii_redaction.py    # Sensitive data protection
├── test_resource_limits.py  # DoS prevention measures
└── test_auth_bypass.py      # Authorization validation
```

### Quality Gates

**Commit-Level Gates**:
- Unit test pass rate: 100%
- Code coverage: >90%
- Security scan: No high-severity findings
- Type checking: mypy compliance

**PR-Level Gates**:
- Functional test suite: All scenarios pass
- Regression tests: <1% degradation in baselines
- Integration tests: Real tool execution
- Documentation: Updated for feature changes

**Release Gates**:
- Performance benchmarks: Response time targets met
- Security audit: Penetration testing results
- Load testing: Concurrent user limits validated
- Environment promotion: Staging → production validation

---

## Development Workflows

### Local Development Setup
```bash
# 1. Environment initialization
./scripts/init-environments.sh dev
source env/dev/config/.env

# 2. Development server startup  
./scripts/run-local.sh dev

# 3. Testing execution
pytest tests/unit tests/functional --cov=src_common

# 4. Quality checks
bandit -r src_common
mypy src_common
```

### Feature Development Process
1. **Planning**: Create task in `.claude/tasks/active/`
2. **Implementation**: Follow TDD with unit tests first
3. **Integration**: Test with functional test scenarios
4. **Documentation**: Update relevant phase documentation
5. **Review**: PR with quality gate validation
6. **Deployment**: Environment promotion workflow

### Ingestion Workflow Management
```bash
# Manual ingestion job
python scripts/ingest.py --env dev --file path/to/document.pdf

# Monitor job progress
curl http://localhost:8000/admin/status

# View ingestion artifacts
ls artifacts/ingest/dev/job_$(date +%Y%m%d_%H%M%S)/
```

### Testing Workflows
```bash
# Development testing
pytest tests/unit -v --cov=src_common --cov-report=html

# Integration testing with real tools
pytest tests/functional -v --disable-warnings

# Regression testing
pytest tests/regression --compare-snapshots

# Security scanning
bandit -r src_common -f json -o security-report.json
```

---

## Deployment & Operations

### Environment Promotion
```bash
# 1. Validate current environment
./scripts/preflight.sh

# 2. Build with timestamp
./scripts/build.sh

# 3. Promote to next environment
./scripts/promote.sh dev test

# 4. Validation smoke tests
pytest tests/functional --env test

# 5. Rollback if issues
./scripts/rollback.sh test
```

### Monitoring & Observability

**Health Monitoring**:
- `/healthz`: Basic application health
- `/status`: Detailed system status with environment context
- WebSocket connection tracking
- Database connectivity validation

**Logging Strategy**:
- Structured JSON logging with correlation IDs
- Environment-specific log levels and outputs
- PII redaction with configurable patterns
- OpenTelemetry integration for distributed tracing

**Performance Metrics**:
- Query classification response times (<150ms p95)
- Retrieval operation latencies (<400ms p95)
- Workflow execution progress tracking
- Resource utilization monitoring

### Production Considerations

**Scalability**:
- Horizontal scaling via load balancer distribution
- Database connection pooling and query optimization
- Caching strategies for frequently accessed data
- Asynchronous processing for long-running operations

**Reliability**:
- Circuit breaker patterns for external service calls
- Graceful degradation when AI models are unavailable
- Automatic retry with exponential backoff
- Health checks and readiness probes

**Security**:
- API rate limiting and request throttling
- Input validation and output sanitization
- Secrets rotation and management
- Regular security vulnerability scanning

---

## API Reference

### Core Endpoints

**Health & Status**:
```http
GET /healthz
GET /status
GET /admin/system-status
```

**RAG & Query Processing**:
```http
POST /rag/ask
{
  "query": "What is the DC for casting a spell?",
  "user_id": "optional",
  "session_id": "optional"
}

Response:
{
  "answer": "...",
  "sources": [...],
  "trace_id": "...",
  "classification": {...},
  "workflow_id": "optional"
}
```

**Workflow Management**:
```http
POST /api/plan
{
  "goal": "Create a level 5 character with specific build",
  "constraints": {"max_tokens": 30000, "max_time_s": 180}
}

POST /api/run
{
  "goal": "...",
  "plan_id": "optional"
}

GET /api/workflow/{workflow_id}
GET /api/workflow/{workflow_id}/approve?task={task_id}&choice={A|B}
```

**Administration**:
```http
GET /admin/ingestion/status
POST /admin/ingestion/start
GET /admin/dictionary/browse
POST /admin/cache/invalidate
```

### WebSocket Events
```javascript
// Connection
ws://localhost:8000/ws

// Events
{
  "type": "workflow_status",
  "workflow_id": "...",
  "task_id": "...",
  "status": "running|completed|failed"
}

{
  "type": "ingestion_progress", 
  "job_id": "...",
  "pass": "A|B|C",
  "status": "...",
  "progress": 0.75
}
```

---

## Quick Start Guide

### Prerequisites
- Python 3.12+
- Git
- OpenAI API key (optional for full functionality)
- AstraDB instance (optional for full functionality)

### Installation
```bash
# 1. Clone repository
git clone <repository-url>
cd TTRPG_Center

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initialize development environment
./scripts/init-environments.sh dev

# 4. Configure environment variables
cp env/dev/config/.env.example env/dev/config/.env
# Edit .env with your API keys and configuration

# 5. Start development server
./scripts/run-local.sh dev
```

### First Steps
```bash
# 1. Verify system health
curl http://localhost:8000/healthz

# 2. Test basic query
curl -X POST http://localhost:8000/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a spell in D&D?"}'

# 3. Access admin interface
open http://localhost:8000/admin

# 4. Run test suite
pytest tests/unit tests/functional

# 5. Ingest a test document
python scripts/ingest.py --env dev --file tests/fixtures/sample.pdf
```

### Development Workflow
1. **Create Feature Branch**: `git checkout -b feature/new-capability`
2. **Write Tests**: Add unit and functional tests first
3. **Implement**: Code following existing patterns
4. **Test**: Run full test suite locally
5. **Document**: Update phase documentation as needed
6. **Submit PR**: Include test evidence and documentation updates

### Configuration Management
- **Environment Variables**: Use `env/{environment}/config/.env`
- **Policies**: Configure retrieval policies in `config/retrieval_policies.yaml`
- **Prompts**: Customize AI prompts in `config/prompts/`
- **Logging**: Adjust log levels via `LOG_LEVEL` environment variable

---

This documentation provides a comprehensive overview of the TTRPG Center architecture. For specific implementation details, refer to the phase documentation in `docs/phases/` and the inline code documentation in `src_common/`.

For questions or contributions, please follow the development workflow outlined above and refer to the testing standards for quality expectations.