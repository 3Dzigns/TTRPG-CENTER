# TTRPG Center Documentation Index

> **Comprehensive AI-Powered Platform for Tabletop RPG Content Management**

Welcome to the TTRPG Center documentation hub. This system provides intelligent document processing, query handling, and workflow orchestration for tabletop RPG content through a sophisticated multi-phase architecture.

## 🚀 Quick Navigation

### For New Developers
- **[Project Architecture](./PROJECT_ARCHITECTURE.md)** - Complete system overview and technical deep-dive
- **[Quick Start Guide](./PROJECT_ARCHITECTURE.md#quick-start-guide)** - Get up and running in 10 minutes
- **[Development Workflows](./PROJECT_ARCHITECTURE.md#development-workflows)** - Local development and testing procedures

### For System Architects  
- **[Multi-Phase Structure](./PROJECT_ARCHITECTURE.md#multi-phase-development-structure)** - Phase-driven development methodology
- **[Environment Isolation](./PROJECT_ARCHITECTURE.md#environment-isolation-system)** - Dev/test/prod separation architecture
- **[Technology Stack](./PROJECT_ARCHITECTURE.md#technology-stack)** - Core technologies and integration patterns

### For Operations Teams
- **[Deployment Guide](./PROJECT_ARCHITECTURE.md#deployment--operations)** - Production deployment and monitoring
- **[API Reference](./PROJECT_ARCHITECTURE.md#api-reference)** - Complete endpoint documentation
- **[Security Standards](./PROJECT_ARCHITECTURE.md#security--testing-standards)** - Security architecture and compliance

---

## 📁 Documentation Structure

### Core Documentation
```
docs/
├── README.md                          # This index file
├── PROJECT_ARCHITECTURE.md            # Master architecture document
├── comprehensive_code_analysis_2025.md # Detailed code analysis
└── code_analysis_report.md            # Implementation status report
```

### Phase Documentation
```
docs/phases/
├── Phase0.md    # Foundation & Environment Isolation
├── Phase1.md    # Three-Pass Ingestion Pipeline  
├── Phase2.md    # Intelligent Retrieval & Model Routing
├── phase3.md    # Graph-Centered Workflows
├── phase4.md    # Admin UI Implementation
├── Phase5.md    # User Interface & Experience
├── Phase6.md    # Testing & Feedback Systems
└── Phase7.md    # Requirements & Feature Management
```

### Specialized Documentation  
```
docs/
├── requirements/           # Feature requirements and specifications
│   ├── Requirement.md     # Master requirements document
│   ├── FR001.md          # Functional requirement examples
│   └── FR-*.md           # Individual requirement documents
├── setup/                 # Setup and configuration guides
│   └── ASTRA_SETUP.md    # AstraDB configuration guide
├── testing/              # Testing documentation and guides
│   ├── phase4-test-guide.md
│   └── phase4-test-summary.md
├── bugs/                 # Bug reports and tracking
│   ├── BP001.md          # Individual bug reports
│   └── BP*.md            # Bug tracking documents
└── reports/              # Analysis and status reports
    └── code_analysis_report.md
```

---

## 🏗️ System Overview

### Architecture at a Glance
TTRPG Center is built on a **7-phase development methodology** with strict **environment isolation** and **graph-centric reasoning**:

1. **Foundation** (Phase 0): Environment isolation, CI/CD, logging infrastructure
2. **Ingestion** (Phase 1): Multi-pass PDF processing (unstructured.io → Haystack → LlamaIndex)
3. **Intelligence** (Phase 2): Query classification, policy-driven retrieval, model routing
4. **Workflows** (Phase 3): Graph-aware planning, multi-step reasoning, HITL approvals
5. **Admin Tools** (Phase 4): System management, monitoring, operational interfaces
6. **User Experience** (Phase 5): Web UI, real-time features, LCARS design
7. **Quality Assurance** (Phase 6): Testing automation, feedback collection
8. **Requirements** (Phase 7): Structured feature management, documentation generation

### Key Capabilities
- ✅ **Multi-Pass Document Processing**: PDF → Chunks → Enrichment → Knowledge Graph
- ✅ **Intelligent Query Handling**: Intent classification with model routing 
- ✅ **Graph-Powered Reasoning**: Multi-hop reasoning via knowledge graphs
- ✅ **Workflow Orchestration**: Complex task planning with human-in-the-loop
- ✅ **Real-Time Interfaces**: WebSocket support, live status updates
- ✅ **Comprehensive Testing**: Unit, functional, regression, security test suites

---

## 🛠️ Technology Stack

### Core Technologies
- **Framework**: FastAPI with async support
- **AI Models**: OpenAI GPT-4o/4o-mini, Claude 3 Sonnet/Haiku
- **Document Processing**: unstructured.io, Haystack, LlamaIndex
- **Database**: AstraDB with vector search, Neo4j for knowledge graphs
- **Testing**: pytest with comprehensive coverage

### Environment Structure
```
TTRPG_Center/
├── env/{dev|test|prod}/        # Environment isolation
│   ├── config/                 # Environment-specific configurations
│   ├── data/                   # Environment data directories  
│   └── logs/                   # Environment-specific logging
├── src_common/                 # Shared application code
├── tests/                      # Comprehensive test suites
├── docs/                       # Documentation (you are here)
├── artifacts/                  # Processing artifacts and outputs
└── scripts/                    # Automation and deployment scripts
```

---

## 🔧 Development Quick Start

### Prerequisites
- Python 3.12+
- Git
- OpenAI API key (optional for full functionality)
- AstraDB instance (optional for full functionality)

### Get Running in 5 Steps
```bash
# 1. Clone and setup
git clone <repository-url> && cd TTRPG_Center
pip install -r requirements.txt

# 2. Initialize development environment  
./scripts/init-environments.sh dev

# 3. Configure (edit with your keys)
cp env/dev/config/.env.example env/dev/config/.env

# 4. Start development server
./scripts/run-local.sh dev

# 5. Verify system health
curl http://localhost:8000/healthz
```

### First Development Tasks
```bash
# Run comprehensive tests
pytest tests/unit tests/functional

# Test document ingestion
python scripts/ingest.py --env dev --file tests/fixtures/sample.pdf

# Try a query
curl -X POST http://localhost:8000/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a fireball spell in D&D?"}'

# Access admin interface  
open http://localhost:8000/admin
```

---

## 📊 Implementation Status

### ✅ Completed Phases
- **Phase 0**: Environment isolation, CI/CD foundation *(Complete)*
- **Phase 1**: Three-pass ingestion pipeline *(Complete)*  
- **Phase 2**: Intelligent retrieval and model routing *(Complete)*
- **Phase 3**: Graph-centered workflows *(Complete)*
- **Phase 4**: Admin UI and operational tools *(Complete)*
- **Phase 5**: User interface and experience *(Complete)*
- **Phase 6**: Testing and feedback systems *(Complete)*
- **Phase 7**: Requirements and feature management *(Complete)*

### 🔍 Key Metrics
- **Test Coverage**: >90% unit test coverage across all modules
- **Performance**: <150ms p95 query classification, <400ms retrieval
- **Quality Gates**: All phases pass unit/functional/regression/security tests
- **Documentation**: Comprehensive phase documentation with acceptance criteria

---

## 🧭 Navigation by Role

### 👩‍💻 **Software Developers**
Start here for implementation details:
1. [Project Architecture Overview](./PROJECT_ARCHITECTURE.md#system-architecture)
2. [Core Components Deep Dive](./PROJECT_ARCHITECTURE.md#core-components)
3. [Development Workflows](./PROJECT_ARCHITECTURE.md#development-workflows)
4. [Testing Standards](./PROJECT_ARCHITECTURE.md#security--testing-standards)

**Key Files to Explore**:
- `src_common/orchestrator/` - Query classification and routing
- `src_common/graph/` - Knowledge graph storage and operations
- `src_common/planner/` - Workflow planning and task decomposition
- `tests/` - Comprehensive test suites with examples

### 🏗️ **System Architects**  
Focus on system design and integration:
1. [Multi-Phase Architecture](./PROJECT_ARCHITECTURE.md#multi-phase-development-structure)
2. [Data Flow Architecture](./PROJECT_ARCHITECTURE.md#data-flow-architecture)
3. [Environment Isolation](./PROJECT_ARCHITECTURE.md#environment-isolation-system)
4. [Technology Integration](./PROJECT_ARCHITECTURE.md#technology-stack)

**Key Documents**:
- [Phase Documentation](./phases/) - Detailed phase specifications
- [Requirements](./requirements/) - Functional requirements and specifications
- [Setup Guides](./setup/) - Configuration and deployment procedures

### 🚀 **DevOps Engineers**
Infrastructure and operations focus:
1. [Deployment & Operations](./PROJECT_ARCHITECTURE.md#deployment--operations)
2. [Environment Management](./PROJECT_ARCHITECTURE.md#environment-isolation-system)
3. [Monitoring & Observability](./PROJECT_ARCHITECTURE.md#deployment--operations)
4. [Security Standards](./PROJECT_ARCHITECTURE.md#security--testing-standards)

**Operational Resources**:
- `scripts/` - Deployment and environment automation
- `env/` - Environment-specific configurations
- `artifacts/` - Processing outputs and job artifacts

### 🧪 **QA Engineers**
Testing and quality assurance:
1. [Testing Strategy](./PROJECT_ARCHITECTURE.md#security--testing-standards)
2. [Quality Gates](./PROJECT_ARCHITECTURE.md#security--testing-standards)
3. [Test Suite Organization](./testing/)
4. [Bug Tracking](./bugs/)

**Testing Resources**:
- `tests/unit/` - Unit test suites with >90% coverage
- `tests/functional/` - End-to-end integration tests
- `tests/regression/` - Golden file baseline comparisons
- `tests/security/` - Security and injection testing

### 📝 **Product Managers**
Feature planning and requirements:
1. [Phase Objectives](./phases/) - Development roadmap and features
2. [Requirements Documentation](./requirements/) - Feature specifications
3. [Implementation Status](./reports/) - Progress and completion reports
4. [User Experience](./PROJECT_ARCHITECTURE.md#core-components) - Interface capabilities

---

## 🔍 Key Concepts

### Environment Isolation
Each environment (dev/test/prod) maintains complete separation:
- **Independent ports**: 8000/8181/8282  
- **Isolated configurations**: Environment-specific .env files
- **Separate data**: Independent storage and logging
- **Security boundaries**: No cross-environment contamination

### Graph-Centric Reasoning  
Knowledge graphs drive intelligent behavior:
- **Schema**: Rules, Concepts, Procedures, Steps, Entities with relationships
- **Workflow Planning**: Graph traversal for task decomposition
- **Multi-Hop Reasoning**: Citation-backed traversal with re-grounding
- **Provenance**: Full audit trails from graph to final answers

### AI Model Orchestration
Dynamic model selection based on query characteristics:
- **Classification**: Intent/domain/complexity analysis (<150ms)
- **Policy-Driven**: YAML configuration for retrieval strategies  
- **Model Routing**: Cost/latency-aware selection (GPT-4o, Claude, local)
- **Self-Consistency**: Multi-sample generation for complex reasoning

---

## 📞 Getting Help

### Documentation Issues
- **Missing Information**: Check phase-specific documentation in `docs/phases/`
- **Setup Problems**: Review environment configuration in `env/*/config/`
- **API Questions**: Consult [API Reference](./PROJECT_ARCHITECTURE.md#api-reference)

### Development Support  
- **Test Failures**: Review test output and check environment configuration
- **Integration Issues**: Verify API keys and database connections
- **Performance Problems**: Check resource limits and caching configuration

### Contributing
1. **Read**: [Development Workflows](./PROJECT_ARCHITECTURE.md#development-workflows)
2. **Follow**: Testing standards and quality gates
3. **Document**: Update phase documentation for feature changes
4. **Test**: Comprehensive test coverage required for all changes

---

## 📈 Project Stats

- **Total Lines of Code**: ~15,000+ (Python/JavaScript/Configuration)
- **Test Coverage**: >90% across all core modules
- **Documentation Pages**: 25+ comprehensive documents
- **API Endpoints**: 15+ REST endpoints with WebSocket support
- **Supported Formats**: PDF documents with multi-pass processing
- **AI Model Integrations**: OpenAI, Claude, local model support
- **Database Support**: AstraDB, Neo4j, local storage options

---

This documentation is actively maintained and updated with each phase completion. For the most current information, refer to the individual phase documentation and implementation code.

**Last Updated**: December 2024  
**Current Version**: v0.1.0  
**Status**: All 7 phases complete and operational