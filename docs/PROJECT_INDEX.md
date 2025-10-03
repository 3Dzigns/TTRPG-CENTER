# TTRPG Center - Master Project Index

> **The definitive navigation guide for the TTRPG Center AI-powered platform**

This document serves as the master index for all project documentation, code organization, and development resources. Use this as your starting point to navigate the comprehensive TTRPG Center platform.

---

## 🎯 Quick Access

| Need | Resource | Location |
|------|----------|----------|
| **System Overview** | Architecture Documentation | [docs/PROJECT_ARCHITECTURE.md](./docs/PROJECT_ARCHITECTURE.md) |
| **Get Started** | Quick Start Guide | [docs/README.md](./docs/README.md) |
| **Implementation** | Phase Documentation | [docs/phases/](./docs/phases/) |
| **API Reference** | Endpoint Documentation | [docs/PROJECT_ARCHITECTURE.md#api-reference](./docs/PROJECT_ARCHITECTURE.md#api-reference) |
| **Testing** | Test Suites | [tests/](./tests/) |
| **Configuration** | Environment Setup | [env/](./env/) |

---

## 📋 Complete Project Map

### 📚 Documentation Hub (`/docs`)
```
docs/
├── 📄 README.md                    # Main documentation index
├── 📄 PROJECT_ARCHITECTURE.md      # Master architecture document  
├── 📄 comprehensive_code_analysis_2025.md  # Detailed code analysis
├── 📄 code_analysis_report.md      # Implementation status
│
├── 📁 phases/                      # Phase-specific documentation
│   ├── Phase0.md                   # Environment isolation & foundation
│   ├── Phase1.md                   # Three-pass ingestion pipeline
│   ├── Phase2.md                   # Intelligent retrieval & routing
│   ├── phase3.md                   # Graph-centered workflows
│   ├── phase4.md                   # Admin UI implementation
│   ├── Phase5.md                   # User interface & experience  
│   ├── Phase6.md                   # Testing & feedback systems
│   └── Phase7.md                   # Requirements management
│
├── 📁 requirements/                # Feature specifications
│   ├── Requirement.md              # Master requirements document
│   ├── FR001.md                    # Sample functional requirement
│   └── FR-*.md                     # Individual feature requirements
│
├── 📁 setup/                       # Configuration guides
│   └── ASTRA_SETUP.md             # AstraDB setup instructions
│
├── 📁 testing/                     # Testing documentation
│   ├── phase4-test-guide.md       # Testing procedures
│   └── phase4-test-summary.md     # Test execution summaries
│
├── 📁 bugs/                        # Issue tracking
│   ├── BP001.md                    # Bug report format
│   └── BP*.md                      # Individual bug reports
│
└── 📁 reports/                     # Analysis reports
    └── code_analysis_report.md     # Current implementation status
```

### 💻 Source Code Organization (`/src_common`)
```
src_common/
├── 📄 app.py                      # Main FastAPI application
├── 📄 logging.py                  # Structured logging infrastructure
├── 📄 secrets.py                  # Environment-aware secrets management
│
├── 📁 orchestrator/               # Phase 2: Intelligent Query Processing
│   ├── classifier.py              # Intent classification system
│   ├── policies.py                # Retrieval policy engine
│   ├── router.py                  # Model selection and routing
│   ├── service.py                 # RAG service orchestration
│   ├── retriever.py               # Hybrid retrieval implementation
│   └── prompts.py                 # Prompt template management
│
├── 📁 graph/                      # Phase 3: Knowledge Graph System
│   ├── store.py                   # Graph storage with versioning
│   └── build.py                   # Graph construction from text
│
├── 📁 planner/                    # Phase 3: Workflow Planning
│   ├── plan.py                    # Graph-aware task planning
│   └── budget.py                  # Resource budgeting and limits
│
├── 📁 runtime/                    # Phase 3: Workflow Execution  
│   ├── execute.py                 # DAG execution engine
│   └── state.py                   # Workflow state management
│
├── 📁 reason/                     # Phase 3: Reasoning Systems
│   ├── graphwalk.py               # Graph-guided reasoning
│   └── executors.py               # Specialized task executors
│
├── 📁 admin/                      # Phase 4: Administrative Tools
│   ├── status.py                  # System status monitoring
│   ├── ingestion.py               # Ingestion job management
│   ├── dictionary.py              # Dictionary management tools
│   ├── testing.py                 # Integration testing interface
│   └── cache_control.py           # Cache management utilities
│
└── 📄 requirements_manager.py     # Phase 7: Requirements tracking
```

### 🧪 Test Suite Architecture (`/tests`)
```  
tests/
├── 📄 conftest.py                 # Shared test configuration
│
├── 📁 unit/                       # Unit tests (>90% coverage)
│   ├── test_classifier.py         # Query classification tests
│   ├── test_policies.py           # Policy selection tests
│   ├── test_graph_store.py        # Graph operations tests
│   ├── test_planner.py            # Workflow planning tests
│   ├── test_executor.py           # Task execution tests
│   ├── test_logging.py            # Logging infrastructure tests
│   └── test_*.py                  # Component-specific unit tests
│
├── 📁 functional/                 # End-to-end integration tests
│   ├── test_phase2_rag.py         # RAG pipeline testing
│   ├── test_phase3_workflows.py   # Workflow execution testing
│   ├── test_admin_api.py          # Admin interface testing
│   ├── test_health_endpoint.py    # Health check testing
│   └── test_*.py                  # Feature integration tests
│
├── 📁 regression/                 # Baseline comparison tests
│   ├── test_baseline_contracts.py # Golden file comparisons
│   └── test_*.py                  # Regression test suites
│
├── 📁 security/                   # Security and injection tests
│   ├── test_env_gitignore.py      # Secret protection tests
│   ├── test_phase3_security.py    # Workflow security tests
│   └── test_*.py                  # Security validation tests
│
└── 📁 personas/                   # User persona testing
    └── test_phase3_persona_qa.py  # Persona-based QA testing
```

### 🔧 Environment & Configuration (`/env`)
```
env/
├── 📁 dev/                        # Development environment (port 8000)
│   ├── config/
│   │   ├── .env                   # Development configuration
│   │   ├── ports.json             # Port assignments
│   │   └── logging.json           # Logging configuration
│   ├── data/                      # Development data (gitignored)
│   └── logs/                      # Development logs
│
├── 📁 test/                       # Testing environment (port 8181)
│   └── config/                    # Test-specific configuration
│
└── 📁 prod/                       # Production environment (port 8282)
    └── config/                    # Production configuration
```

### 🗃️ Data & Artifacts (`/artifacts`)
```
artifacts/
├── 📁 ingest/                     # Ingestion pipeline outputs
│   └── {ENV}/{JOB_ID}/           # Environment-specific job artifacts
│       ├── manifest.json          # Job metadata and status
│       ├── passA_chunks.json      # Pass A: Parsed chunks
│       ├── passB_enriched.json    # Pass B: Enriched content
│       ├── passB_dictionary_delta.json  # Dictionary updates
│       └── passC_graph.json       # Pass C: Knowledge graph
│
└── 📁 graph/                      # Graph storage
    ├── nodes.json                 # Graph nodes
    ├── edges.json                 # Graph edges
    └── write_ahead_log.json       # Operation audit log
```

### 🚀 Application Interfaces (`/app_*.py`)
```
├── 📄 app_admin.py                # Phase 4: Admin interface application
├── 📄 app_user.py                 # Phase 5: User interface application
├── 📄 app_workflow.py             # Phase 3: Workflow management API
├── 📄 app_plan_run.py             # Phase 3: Planning and execution API
├── 📄 app_feedback.py             # Phase 6: Feedback collection API
└── 📄 app_requirements.py         # Phase 7: Requirements management API
```

### ⚙️ Automation & Utilities (`/scripts`)
```
scripts/
├── 📄 init-environments.sh        # Environment initialization
├── 📄 run-local.sh               # Local development server
├── 📄 preflight.sh               # Pre-deployment validation
├── 📄 ingest.py                  # Document ingestion utility
├── 📄 rag_openai.py              # RAG query testing tool
└── 📄 *.py                       # Various utility scripts
```

---

## 🎯 Navigation by Use Case

### 🆕 **New Developer Onboarding**
**Goal**: Get up and running with development environment
```
1. 📄 docs/README.md                    # Project overview
2. 📄 docs/PROJECT_ARCHITECTURE.md      # System architecture  
3. 🛠️ Quick Start Guide                 # Setup instructions
4. 📁 env/dev/config/.env.example       # Configuration template
5. 🧪 tests/unit/                       # Example test patterns
```

### 🏗️ **Architecture Understanding**  
**Goal**: Understand system design and component interactions
```
1. 📄 docs/PROJECT_ARCHITECTURE.md      # Master architecture
2. 📁 docs/phases/                      # Phase-specific designs
3. 💻 src_common/orchestrator/          # Query processing system
4. 💻 src_common/graph/                 # Knowledge graph system
5. 💻 src_common/planner/               # Workflow planning system
```

### 🔧 **Feature Implementation**
**Goal**: Implement new features or modify existing ones
```
1. 📁 docs/requirements/                # Feature specifications
2. 💻 src_common/{relevant_module}/     # Implementation code
3. 🧪 tests/unit/test_{module}.py       # Unit tests
4. 🧪 tests/functional/test_{feature}.py # Integration tests
5. 📄 docs/phases/Phase{N}.md           # Phase documentation
```

### 🚀 **Deployment & Operations**
**Goal**: Deploy and manage production systems
```
1. 📄 docs/PROJECT_ARCHITECTURE.md#deployment--operations
2. ⚙️ scripts/                          # Deployment automation
3. 📁 env/prod/config/                  # Production configuration
4. 🧪 tests/functional/                 # Deployment validation
5. 📄 docs/setup/                       # Setup guides
```

### 🧪 **Testing & Quality Assurance**
**Goal**: Ensure quality and run comprehensive tests
```
1. 📄 docs/PROJECT_ARCHITECTURE.md#security--testing-standards
2. 🧪 tests/                            # Complete test suites
3. 📄 docs/testing/                     # Testing documentation
4. ⚙️ scripts/preflight.sh              # Pre-deployment validation
5. 📁 docs/bugs/                        # Issue tracking
```

### 📊 **Monitoring & Analysis**
**Goal**: Monitor system performance and analyze behavior  
```
1. 📄 docs/reports/                     # Analysis reports
2. 🗃️ artifacts/                        # System artifacts
3. 📁 env/{ENV}/logs/                   # Environment-specific logs
4. 💻 src_common/admin/status.py        # Status monitoring
5. 📄 docs/PROJECT_ARCHITECTURE.md#deployment--operations
```

---

## 🔍 Key File Quick Reference

### 📋 **Essential Reading**
| File | Purpose | When to Read |
|------|---------|--------------|
| `docs/README.md` | Project overview and navigation | First time, periodic updates |
| `docs/PROJECT_ARCHITECTURE.md` | Complete system architecture | Understanding system design |
| `CLAUDE.md` | Development guidelines for AI assistant | Working with AI assistance |
| `requirements.txt` | Python dependencies | Setting up environment |

### ⚙️ **Configuration Files**
| File | Purpose | Environment |
|------|---------|-------------|
| `env/{ENV}/config/.env` | Environment variables | Specific to dev/test/prod |
| `env/{ENV}/config/ports.json` | Port assignments | Environment isolation |
| `config/retrieval_policies.yaml` | RAG policies | Query processing behavior |
| `config/prompts/*.txt` | AI prompt templates | Model interactions |
| `docs/setup/CASSANDRA_SETUP.md` | Local Cassandra setup runbook | DEV/CI |

### 🔧 **Development Tools**
| File | Purpose | Usage |
|------|---------|-------|
| `scripts/init-environments.sh` | Environment setup | Initial setup |
| `scripts/run-local.sh` | Development server | Daily development |
| `scripts/ingest.py` | Document processing | Testing ingestion |
| `pytest.ini` | Test configuration | Running test suites |

### 📊 **Monitoring & Status**
| File | Purpose | Information |
|------|---------|-------------|
| `artifacts/graph/nodes.json` | Knowledge graph state | Graph contents |
| `artifacts/ingest/{ENV}/{JOB}/` | Ingestion artifacts | Processing results |
| `env/{ENV}/logs/` | Runtime logs | System behavior |
| `docs/reports/` | Analysis reports | System analysis |

---

## 🚦 Development Status Dashboard

### ✅ **Completed Features**
- **Environment Isolation**: Complete separation of dev/test/prod
- **Document Processing**: Three-pass ingestion with real tool integration
- **Query Intelligence**: Intent classification with model routing  
- **Graph Workflows**: Multi-step reasoning with human-in-the-loop
- **Admin Interface**: System management and monitoring tools
- **User Interface**: Web-based interaction with real-time updates
- **Testing Infrastructure**: Comprehensive test suites with >90% coverage
- **Requirements Management**: Structured feature tracking and validation

### 🎯 **Current State**
- **All 7 Phases**: Complete and operational
- **Test Coverage**: >90% across all core modules
- **Documentation**: Comprehensive with 25+ detailed documents
- **API Endpoints**: 15+ REST endpoints with WebSocket support
- **CI/CD Pipeline**: Automated testing and quality gates

### 🔄 **Active Areas**
- **Performance Optimization**: Response time improvements
- **Documentation Maintenance**: Keeping docs synchronized with code  
- **Feature Enhancement**: User-requested improvements
- **Integration Testing**: Cross-component validation

---

## 💡 Pro Tips for Navigation

### 🎯 **Finding What You Need**
1. **Start with Purpose**: Use the "Navigation by Use Case" section above
2. **Follow the Trail**: Each document has cross-references to related content
3. **Check the Index**: This document provides the master map
4. **Use Search**: Most editors can search across all files in the project

### 🔍 **Understanding Code Structure**
1. **Phase Documentation**: Read the relevant phase doc first
2. **Test Files**: Tests often provide the best usage examples  
3. **Interface Files**: Look at `app_*.py` files for API patterns
4. **Core Modules**: `src_common/` contains the main business logic

### 📚 **Staying Current**
1. **README Files**: Check for updates in major directories
2. **Git History**: Review recent commits for changes
3. **Test Results**: Current test status indicates system health
4. **Documentation Dates**: Most docs include last update timestamps

---

## 🆘 Help & Support

### 📖 **Documentation Issues**
- **Missing Information**: Check phase-specific documentation
- **Outdated Content**: Cross-reference with source code
- **Unclear Instructions**: Review test files for examples

### 🐛 **Technical Issues**  
- **Setup Problems**: Review environment configuration
- **Test Failures**: Check logs and error messages
- **Integration Issues**: Verify API keys and database connections

### 🤝 **Contributing**
- **Feature Requests**: Document in `docs/requirements/`
- **Bug Reports**: Use format in `docs/bugs/BP001.md`
- **Code Changes**: Follow patterns in existing test suites

---

**This index is maintained as the single source of truth for project navigation. Bookmark this page and refer to it whenever you need to find something in the TTRPG Center project.**

---

**Last Updated**: December 2024 | **Project Status**: All phases complete | **Version**: v0.1.0