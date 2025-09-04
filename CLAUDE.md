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
- **Phase 1:** Three-pass ingestion pipeline (unstructured.io → Haystack → LlamaIndex)
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

### Ingestion Pipeline (Phase 1)
Three-pass processing with hard acceptance gates:
1. **Pass A:** PDF parsing and chunking using unstructured.io
2. **Pass B:** Content enrichment and dictionary updates using Haystack
3. **Pass C:** Graph compilation using LlamaIndex

Each pass must use real tools (no mocks in acceptance tests) and emit contract-compliant outputs.

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