# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TTRPG Center is a comprehensive AI-powered platform for tabletop RPG content management and intelligent query handling. The system processes TTRPG PDFs through a multi-phase ingestion pipeline and provides intelligent retrieval through various interfaces.

## Architecture & Key Concepts

### Environment Isolation
The project enforces strict environment isolation with dedicated sub-directories:
- `env/dev/` - Development environment (port 8000)
- `env/test/` - Testing environment (port 8181) 
- `env/prod/` - Production environment (port 8282)

Each environment has isolated `code/`, `config/`, `data/`, and `logs/` directories. No environment may share binaries, caches, or manifests.

### Multi-Phase Development Structure
The project is organized into 7 distinct phases, each with specific acceptance criteria:

- **Phase 0:** Environment isolation, builds, and fast testing foundation
- **Phase 1:** Seven-pass ingestion pipeline "Lane A" (A→B→C→D→E→F→G)
- **Phase 2:** RAG retrieval with query classification and model routing
- **Phase 3:** Graph workflows for guided processes
- **Phase 4:** Admin UI for operational tools
- **Phase 5:** User UI with retro terminal/LCARS design
- **Phase 6:** Testing & feedback automation
- **Phase 7:** Requirements management and feature flow

### Core Technology Stack
- **Database:** AstraDB with vector search capabilities
- **Ingestion Tools:** unstructured.io, Haystack, LlamaIndex
- **AI Models:** OpenAI API, Claude API
- **Backend:** Python with FastAPI (inferred from Phase documentation)
- **Frontend:** WebUI with retro terminal/LCARS theming

## Development Commands

### Environment Setup
```powershell
# Initialize environments (Windows)
.\scripts\init-environments.ps1 -Env dev|test|prod

# Initialize environments (POSIX)
./scripts/init-environments.sh dev|test|prod
```

### Local Development
```powershell
# Run local environment
.\scripts\run-local.ps1 -Env dev

# Preflight checks
.\scripts\preflight.ps1
```

### Build & Deployment
```powershell
# Build with timestamped IDs
.\scripts\build.ps1

# Promote between environments
.\scripts\promote.ps1

# Rollback if needed
.\scripts\rollback.ps1
```

### Testing
```bash
# Unit tests
pytest tests/unit

# Functional tests  
pytest tests/functional

# Security tests
pytest tests/security
bandit -r src_common

# Regression tests (nightly)
pytest tests/regression

# Run all tests
pytest tests/unit tests/functional
```

## Project Structure

```
/
├── env/                    # Environment isolation
│   ├── dev/               # Development environment
│   ├── test/              # Testing environment  
│   └── prod/              # Production environment
├── src_common/            # Shared libraries (no env-specific state)
├── scripts/               # Environment and build scripts
├── tests/                 # Test suites
│   ├── unit/
│   ├── functional/
│   ├── regression/
│   └── security/
├── artifacts/             # Ingestion job artifacts
│   └── ingest/{ENV}/{JOB_ID}/
└── Phase*.txt            # Detailed phase specifications
```

## Key Implementation Requirements

### Ingestion Pipeline (Phase 1) - Lane A
Seven-pass processing pipeline with hard acceptance gates:
1. **Pass A:** PDF parsing and ToC extraction using unstructured.io
2. **Pass B:** Logical splitting for large files (>25MB) using PyPDF
3. **Pass C:** Content extraction and chunking using unstructured.io
4. **Pass D:** Vector enrichment and NER using Haystack with OpenAI embeddings
5. **Pass E:** Graph building and cross-references using LlamaIndex
6. **Pass F:** Finalization, validation, and cleanup operations
7. **Pass G:** HGRN validation and quality gates

Each pass must use real tools (no mocks in acceptance tests) and emit contract-compliant outputs. The complete pipeline forms "Lane A" - the primary ingestion pathway that transforms raw PDFs into fully processed, searchable content.

### Query Processing (Phase 2)
- Query Intent Classification (QIC) with sub-150ms p95 response time
- Hybrid retrieval policies (vector/metadata/graph)
- Dynamic model routing based on query complexity
- Structured telemetry and confidence scoring

### Environment Configuration
- Environment-specific `.env` files under `env/{ENV}/config/.env`
- Port assignments: dev=8000, test=8181, prod=8282
- AstraDB configuration with vector search capabilities
- OpenAI API integration for AI model access

### Lane A Pipeline Architecture (7-Pass System)

The ingestion pipeline has evolved from a 3-pass to a 7-pass architecture to provide comprehensive document processing:

#### Pass A: PDF Parsing & ToC Extraction
**Module:** `src_common/pass_a_toc_parser.py`
**Purpose:** Extract text content and table of contents structure from PDF files
**Tools:** unstructured.io
**Output:** Raw chunks and ToC hierarchy
**Key Operations:**
- PDF text extraction and parsing
- Table of contents structure identification
- Page-level content segmentation
- Initial metadata extraction

#### Pass B: Logical Splitting
**Module:** `src_common/pass_b_logical_splitter.py`
**Purpose:** Split large PDFs (>25MB) into logical sections based on ToC structure
**Tools:** PyPDF
**Output:** Split PDF files or split index for large documents
**Key Operations:**
- File size threshold checking (25MB)
- ToC-guided logical splitting
- Page range extraction for sections
- Split index generation

#### Pass C: Content Extraction & Chunking
**Module:** `src_common/pass_c_extraction.py`
**Purpose:** Extract structured content chunks from processed PDFs
**Tools:** unstructured.io
**Output:** Structured content chunks with metadata
**Key Operations:**
- Advanced content extraction
- Chunk boundary optimization
- Element type classification
- Structured metadata assignment

#### Pass D: Vector Enrichment & NER
**Module:** `src_common/pass_d_vector_enrichment.py`
**Purpose:** Generate embeddings and extract named entities
**Tools:** Haystack, OpenAI Embeddings API
**Output:** Vectorized chunks with entity annotations
**Key Operations:**
- Text embedding generation (1536-dimensional vectors)
- Named Entity Recognition (NER)
- Keyword extraction and scoring
- Chunk deduplication and merging

#### Pass E: Graph Building & Cross-References
**Module:** `src_common/pass_e_graph_builder.py`
**Purpose:** Build document graph and extract cross-references
**Tools:** LlamaIndex
**Output:** Graph structure with entity relationships
**Key Operations:**
- Document hierarchy graph construction
- Cross-reference extraction (spells ↔ classes/feats)
- ToC lineage assignment
- Entity relationship mapping

#### Pass F: Finalization & Cleanup
**Module:** `src_common/pass_f_finalizer.py`
**Purpose:** Validate artifacts and finalize processing
**Tools:** Native Python validation
**Output:** Finalized manifest with checksums
**Key Operations:**
- Artifact integrity validation
- Atomic file operations
- Cleanup of temporary files
- Manifest finalization with run summary

#### Pass G: HGRN Validation & Quality Gates
**Module:** `src_common/admin/ingestion.py` (execute_pass_g)
**Purpose:** Final quality validation and compliance checking
**Tools:** HGRN validation framework
**Output:** Quality metrics and validation report
**Key Operations:**
- Content quality assessment
- Structural integrity verification
- Metadata consistency validation
- Performance metrics collection

#### Pipeline Flow & Data Contracts

```
PDF Input → Pass A → Pass B → Pass C → Pass D → Pass E → Pass F → Pass G → Complete
          ↓        ↓        ↓        ↓        ↓        ↓        ↓
        ToC/Raw   Split    Chunks   Vectors  Graph   Final   Valid
       Content   Index             +NER    +XRefs  Manifest +QC
```

Each pass maintains strict data contracts:
- **Input validation:** Verify prerequisites from previous passes
- **Processing stage:** Perform pass-specific operations
- **Output generation:** Emit contract-compliant artifacts
- **Manifest update:** Record completion and metadata
- **Error handling:** Graceful failure with diagnostic information

## Critical Development Guidelines

### Security & Secrets
- All `.env` files must be gitignored
- No secrets or API keys in code or logs
- Use environment variables for sensitive configuration
- File permissions on `.env` files should be 0600 on POSIX systems

### Testing Standards
- Unit tests run on every commit
- Functional tests run on every PR
- Security tests (Bandit) run on every PR
- Regression tests run nightly on main branch
- F1 score ≥ 0.85 required for classification components

#### Phase 1 Regression Testing (7-Pass Pipeline)
The Phase 1 regression suite validates the complete Lane A pipeline:

**Individual Pass Tests:**
- `test_rag001a_parse.py`: Pass A PDF parsing and ToC extraction
- `test_rag001b_logical_split.py`: Pass B logical splitting with PyPDF
- `test_rag001c_extraction.py`: Pass C content extraction with unstructured.io
- `test_rag001d_vector_enrichment.py`: Pass D vector enrichment with Haystack
- `test_rag001e_graph_builder.py`: Pass E graph building with LlamaIndex
- `test_rag001f_finalizer.py`: Pass F finalization and cleanup
- `test_rag001g_hgrn_validation.py`: Pass G HGRN validation and quality gates

**Integration Testing:**
- `test_lane_a_integration.py`: Complete pipeline flow (A→B→C→D→E→F→G)
- Sequential execution validation
- Data flow integrity testing
- Error recovery and rollback capabilities
- Performance baseline measurement
- Manifest consistency throughout pipeline

**Quality Gates:**
- Each pass test includes HARD GATE requirements
- Mock-based testing for external dependencies
- Contract compliance validation
- Performance baselines (processing time limits)
- Error handling verification

### Logging & Status
- Use structured JSON logging via `src_common/logging.py`
- Include environment context in all log entries
- Emit telemetry for performance monitoring
- Status updates must show environment directory context

### Cache Controls & WebUI
- Very short TTL (≤5s) for dynamic pages in test/dev
- No-store headers for development environment
- Admin UI toggle for cache disabling
- Fast retest behavior with config change reflection within seconds

### Performance Optimization Patterns (BUG-031 Implementation)
- **Timer Lifecycle Management**: All polling timers must implement proper cleanup on page unload/hide
- **Visibility-Based Resource Management**: Pause polling and WebSocket connections when page is hidden
- **Staggered Loading**: Critical data loads first, secondary data loads with delays to improve perceived performance
- **Request Deduplication**: Track active requests to prevent duplicate API calls during navigation
- **Proper Event Cleanup**: Use both `beforeunload` and `pagehide` events for comprehensive cleanup

## Dependencies & External Services

- **AstraDB:** Vector database for chunk storage and retrieval
- **OpenAI API:** Language model services
- **unstructured.io:** PDF parsing and document processing
- **Haystack:** Content enrichment and normalization
- **LlamaIndex:** Graph compilation and workflow management

Current environment uses AstraDB endpoint in us-east-2 region with configured keyspace and application token (see `.env` file).

## Task Planning & Management Workflow

### Task Organization System
All tasks are managed through the `.claude/tasks/` directory structure:
- `active/` - Currently active tasks requiring attention
- `completed/` - Archived completed tasks for reference and knowledge transfer
- `templates/` - Standardized task documentation templates

### Before Starting Work

#### 1. Planning Phase (Plan Mode)
- **Always enter plan mode first** for non-trivial tasks
- Create comprehensive implementation plan with:
  - Clear objectives and success criteria
  - Technical requirements and constraints
  - Phased implementation approach
  - Risk assessment and mitigation strategies

#### 2. Task Documentation
- Copy `templates/task_template.md` to `active/TASK_NAME.md`
- Use descriptive, kebab-case naming: `implement-user-authentication.md`
- Fill out complete task overview:
  - **Objective**: What needs to be accomplished
  - **Context**: Why this task is needed, project fit
  - **Success Criteria**: Specific, measurable completion requirements
  - **Technical Requirements**: Prerequisites, constraints, acceptance criteria
  - **Implementation Plan**: Detailed phase breakdown with specific tasks

#### 3. Research & Knowledge Gathering
- Use Task tool for external research when needed
- Document latest package versions and compatibility
- Research best practices and security considerations
- Include research findings in task documentation

#### 4. Review & Approval Gate
- Present detailed plan to user for review
- **CRITICAL**: Do not proceed until explicit user approval
- Address any feedback or concerns before implementation
- Update task documentation with approved changes

### During Implementation

#### Progress Tracking
- Update task status to "In Progress" when beginning work
- Maintain regular progress log entries with dates
- Document technical decisions and rationale as they occur
- Record issues encountered and resolution approaches
- Track all file modifications in Technical Details section

#### Development Best Practices
- Follow MVP approach - avoid over-engineering
- Update task progress after each significant milestone
- Document any deviations from original plan with reasoning
- Include code snippets or configuration examples when helpful

#### Issue Management
- Document blockers immediately with attempted solutions
- Record technical challenges and resolution approaches
- Note any assumptions made during implementation
- Highlight any technical debt or known limitations

### After Completion

#### Task Finalization
- Update task status to "Completed"
- Fill out comprehensive Completion Summary:
  - **What Was Delivered**: Detailed summary of changes
  - **Impact & Benefits**: How task contributes to project goals
  - **Follow-up Tasks**: Any additional work identified

#### Knowledge Transfer Documentation
- **Handover Notes**: Critical information for future engineers
  - Key architectural decisions made
  - Code patterns and conventions established
  - Testing approaches implemented
  - Known limitations or constraints
- **Lessons Learned**: What worked well and areas for improvement
- **Recommendations**: Guidance for similar future tasks

#### Task Archival
- Move completed task file from `active/` to `completed/`
- Update any related documentation or README files
- Reference completed tasks in future related work

### Quality Gates & Standards

#### Documentation Requirements
- All tasks must use the standardized template
- Progress updates must include specific accomplishments
- Technical decisions must include rationale
- Handover documentation must enable smooth transition

#### Review Checkpoints
- Initial plan approval before implementation
- Progress review at major milestones (if requested)
- Final completion review with deliverable demonstration
- Post-completion feedback integration

#### Handover Standards
- Assume another engineer will continue related work
- Document all assumptions and context
- Provide clear next steps and dependencies
- Include troubleshooting guidance for common issues

## 🔁 Playbook: Feature Request (FR) Flow
**Trigger phrase:** “FR flow <ticket> — <short title>”
**Goal:** Run the whole FR lifecycle: design → plan → implement → **build+deploy to DEV** → test (in DEV container) → document → commit/push → open PR.

**When I say the trigger:**
1) Use `/sc:design` to produce a short design brief + acceptance criteria tied to `<ticket>`. Ask 0–2 clarifying questions max.
2) Use `/sc:workflow` to turn the brief into a checklist (tasks, files to touch, test strategy).
3) **Checkout a feature branch** (normal git; do NOT skip):
   - `git checkout -b feat/<ticket>-kebab-title`
   - (Optional) `git push -u origin feat/<ticket>-kebab-title`
4) Use `/sc:implement` to create/update code following the plan on the *current feature branch*.
5) **Build & Deploy to DEV (containerized)**:
   - Build image: `docker compose -f env/dev/docker-compose.yml build app`
   - Start/refresh app: `docker compose -f env/dev/docker-compose.yml up -d app`
   - (Optional) Health: `curl http://localhost:8000/healthz` or `docker compose -f env/dev/docker-compose.yml ps`
6) Use `/sc:test` and run tests **inside the DEV container**:
   - Unit/functional: `docker compose -f env/dev/docker-compose.yml exec app pytest -q`
   - (Optional) Regression (still in DEV): `docker compose -f env/dev/docker-compose.yml exec app pytest tests/regression -q`
   - If a container isn’t present, generate the minimal compose/services I need.
7) Use `/sc:document` to update README/CHANGELOG and add any runbooks.
8) Use `/sc:git` to:
   - stage changes,
   - write a Conventional Commit (`feat: <ticket> - <summary>`),
   - push the branch and open a PR.

### Notes
- **No TEST promotion right now.** Do not start or deploy any TEST environment containers in this flow.
- Keep logs and artifacts under `env/<env>/logs` per our repo layout.
- If any step fails, stop and show a crisp fix-list; don’t proceed until green.

---

## 🐛 Playbook: Bug Fix Flow
**Trigger phrase:** “Bug flow <ticket> — <short title>”

1) Use `/sc:troubleshoot` to reproduce + isolate the root cause; save a minimal repro.
2) Create hotfix branch `fix/<ticket>-kebab-title`; apply fix with `/sc:implement`.
3) **Build & Deploy to DEV (containerized)**:
   - `docker compose -f env/dev/docker-compose.yml build app`
   - `docker compose -f env/dev/docker-compose.yml up -d app`
4) Add/adjust tests that *fail first*, then pass after the fix:
   - Run tests in **DEV container only**:
     - `docker compose -f env/dev/docker-compose.yml exec app pytest -q`
     - (Optional) `docker compose -f env/dev/docker-compose.yml exec app pytest tests/regression -q`
5) `/sc:document` the root cause & prevention notes.
6) `/sc:git` conventional commit `fix: <ticket> - <summary>` → push → open PR.
