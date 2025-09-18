# TTRPG Center Consolidated Requirements (September 2025)

## 1. Project Snapshot
- Platform spans 7 delivery phases with mature ingestion, security, testing, and governance foundations already in place.
- Environment isolation (dev/test/prod), 6-pass ingestion, JWT security, and admin tooling are operational; user-facing LCARS UI polish and intelligent retrieval remain the largest open items.
- Codebase health is strong with 44+ automated test files, comprehensive logging, and production-leaning security posture; keep performance monitoring and RAG intelligence improvements as the top priority follow-up.

## 2. Phase Requirements Status

### Phase 0 - Environment Isolation & Build Controls
- Status: Implemented, pending deployment automation into env/{ENV}/code/ directories.
- Requirements: isolated directories, fixed ports (8000/8181/8282), immutable builds, cache control toggles.
- Follow-up: add automated environment promotion/rollback and populate code directories per Implementation Roadmap.

### Phase 1 - Multi-Pass Ingestion
- Status: Implemented; exceeds baseline specs with passes A-F, artifact validation, and consistency checks.
- Requirements: TOC priming, logical splits, unstructured extraction, Haystack enrichment, graph compilation, cleanup.
- Follow-up: monitor job telemetry and integrate HGRN/AEHRL passes when ready.

### Phase 2 - Retrieval Augmentation (Partial)
- Status: Foundation present (AstraDB integration, scripts); missing query intent classification, hybrid routing, provenance.
- Requirements: intent detection, policy-driven routing, source citations, performance budget (<=150 ms QIC).
- Follow-up: implement FR-024/025/026/027 stack, add provenance telemetry, finish model routing metrics.

### Phase 3 - Graph Workflows (Partial)
- Status: Graph build exists; orchestration, state management, and graph-walk reasoning remain outstanding.
- Requirements: workflow engine, character creation flow, policy-aware routing, multi-hop reasoning traces.
- Follow-up: deliver FR-021/022 integration, persistent workflow state, and admin debugging tools.

### Phase 4 - Admin UI
- Status: Implemented with dashboards, ingestion console, dictionary manager, cache controls, bug/testing hooks.
- Requirements: environment health, job control, dictionary edit/versioning, cache compliance, ticketing integration.
- Follow-up: surface AEHRL/HGRN suggestions, expand persona and evaluation dashboards.

### Phase 5 - User UI (Partial)
- Status: Core interaction path exists; LCARS theming, real-time token display, and persona-aware UI still pending.
- Requirements: retro terminal skin, multimodal response area, memory modes, fast retest behavior.
- Follow-up: execute FR-019 wireframe workflow and FR-020 model telemetry alignment.

### Phase 6 - Testing & Feedback
- Status: Implemented beyond baseline (44 test files, security suites); automation for bug bundles and visualization still open.
- Requirements: automated regression creation, feedback ingestion, environment-scoped gates, cache-bypass feedback pipeline.
- Follow-up: build evaluation dashboards, auto bug bundle generation (FR-003), integrate FR-023 persona test suite.

### Phase 7 - Requirements & Governance
- Status: Implemented (immutable JSON store, feature workflow, schema validation, audit trail).
- Requirements: versioned requirements, feature request approval, schema enforcement, visible audits.
- Follow-up: maintain audit health, extend reporting into admin dashboards.

## 3. Functional Requirements Catalog

### 3.1 Implemented or In-Service
- **FR-015 - MongoDB Dictionary Integration** (Complete): Mongo-backed dictionary with circuit breaker, 15+ indexes, admin telemetry.
- **FR-020 - GPT-5 Model Routing** (Complete in DEV): Feature-flagged GPT-5 integration with graceful fallback and telemetry.
- **FR-021 - HGRN Second-Pass Sanity Check** (Integrated per changelog, monitoring ongoing): HGRN validation producing recommendation bundles and admin approve/reject flow.
- **FR-022 - AEHRL Layer** (Complete): Query-time hallucination detection, ingestion sanity checks, admin correction workflow, metrics and alerts.
- **FR-023 - Automated Persona Test Suite (Rev A)** (Foundational tooling available; persona generator pending finalization): Persona CRUD, GPT-5 persona seeding, chat-depth enforced regression runs, scoring and exports.
- **FR-015 Validation Summary & Implementation Summary**: capture acceptance evidence, testing artifacts, and deployment footprint for dictionary upgrade.
- **FR-017 Security Workflow**: comprehensive JWT-enforced bug management, secure uploads, CSP, audit logging, penetration testing plan.
- **FR-SEC-401/402/403**: JWT auth, restricted CORS, TLS enforcement with certificates and security headers across services.
- **Bug Resolutions (BUG-001, BUG-006-011)**: logging reliability, job ID collision prevention, resume validation, cache isolation, /api/sources endpoint, ingestion race fixes.

### 3.2 In Flight / Proposed Enhancements
- **FR-001 - Source Traceability** (Proposed): SHA tracking, chunk reconciliation, admin deletion queue.
- **FR-002 - Nightly Ingestion Scheduler** (Proposed): automated 6-pass nightly runs, manifest and log retention.
- **FR-003 - Log Review & Bug Bundles** (Proposed): structured log parsing, signature grouping, automated bug bundles.
- **FR-004 - Health Check Automation** (Proposed): consolidated system health endpoints and notification hooks.
- **FR-005 - Modular Ingestion Passes** (Proposed/ongoing): pass isolation, retries, admin diagnostics.
- **FR-006 - Containerized Dev Environment** (Complete per feature doc, still tracked for onboarding): Dockerized stack and scripts.
- **FR-007 - CI/CD Pipeline** (Complete): automated build, test, and quality gates.
- **FR-008-FR-014** (Proposed): cover RAG UI polish, admin enhancements, workflow refinements (see respective docs for detailed user stories and tests).
- **FR-016 - Testing Page** (In progress): admin-run smoke suites, timestamped results, bug creation flows.
- **FR-017 - Bug Page** (In progress): bug lifecycle management, filters, evidence capture.
- **FR-018 - Feedback Routing** (Documented): unify thumbs-up/down and feedback loops.
- **FR-019 - LCARS UI & Wireframe Workflow** (In progress): wireframe editor, component library, code generation, admin integration.
- **FR-019 UI Wireframe Implementation Workflow**: phased build plan for drag/drop editor, component palette, export engine.
- **FR-020 Platform Update** (Proposed): centralized model resolver, GPT-5 mini/nano policies, kill-switch, telemetry.
- **FR-024 - Query Planner** (Planned): classify query complexity and emit hop-limited plans.
- **FR-025 - Graph-Augmented Retrieval** (Planned): expand vector hits via graph neighborhoods into context packs.
- **FR-026 - Hybrid Rerank** (Planned): blend embedding, BM25, graph weights, recency with dedupe budget.
- **FR-027 - Answer Provenance** (Planned): enforce citation blocks and trace rendering in UI.
- **FR-028 - Evaluation Gates** (Planned): canonical query set with support-rate gates and CI enforcement.
- **FR-029 - Delta Refresh** (Planned): targeted cache invalidation and partial ingestion updates.
- **FR-030 - Favicon & Branding** (Documented): asset updates for admin/user portals.
- **FR-031 - Cassandra Vector Store** (Implemented per changelog & setup guide): Cassandra-backed vector store with Docker compose wiring for DEV/CI.

## 4. Security & Compliance Requirements
- JWT auth (FR-SEC-401) replaces mock headers with Argon2-hardened credentials, RBAC middleware, token blacklisting, and audit logging.
- CORS (FR-SEC-402) restricts origins per environment and logs blocked requests; TLS (FR-SEC-403) enforces HTTPS with strong ciphers, HSTS, and certificate monitoring.
- FR-017 security workflow adds fine-grained permissions, sanitized schemas, secure file handling, CSP, privacy classification, and automated security scanning.
- Incident response requires audit trails, circuit breakers, health checks, and regular security reviews; ensure metrics feed admin dashboards.

## 5. Testing, Evaluation, and Quality Management
- Phase 6 delivers extensive unit/functional/security/regression coverage; maintain >44 test files with persona and security suites.
- FR-016 testing page enables admins to execute smoke suites, inspect logs, export results, and open bugs with context.
- FR-023 persona suite extends regression coverage with GPT-5 persona generation, run scoring, cost/safety controls, and audit logging.
- FR-028 evaluation gates define canonical queries and success thresholds (support rate >=85%, path success >=80%) with CI enforcement.
- AEHRL (FR-022) provides hallucination metrics, alerts, correction bundles, and ensures unsupported claims are flagged during QA.

## 6. Retrieval, Reasoning, and Data Integrity
- HGRN (FR-021) validates dictionary metadata and graph structure after ingestion, producing admin-reviewed recommendation bundles.
- AEHRL (FR-022) operates at ingestion and query time to flag unsupported claims and track hallucination trends.
- Planned query planner, graph-augmented retrieval, hybrid rerank, answer provenance, and delta refresh work together to complete Phase 2/3 goals.
- Cassandra setup (FR-031) introduces local vector store support with Docker, schema migration, health checks, and troubleshooting guidance.

## 7. User Experience, UI, and Personas
- FR-019 wireframe workflow describes canvas editor, LCARS/admin component libraries, code export, and admin integration roadmap.
- Phase 5 requirements call for retro terminal theming, memory modes, latency badges, and feedback dialogs; FR-019_LCARS_UI.md plus personas directory inform styling.
- Persona library (docs/Personas and docs/Personas/Persona_*.md) pairs with FR-023 persona testing to ensure coverage across user archetypes and supports localized/language-specific needs.

## 8. Bug Resolution & Operational Readiness
- BUG-001 fix suite resolves logging, job IDs, resume validation, and consistency checks with extensive unit coverage.
- BUG-006-011 resolution confirms database reset safety, dictionary upserts, pass barriers, cache isolation, and /api/sources endpoint availability.
- Current issue monitoring highlights Pass B JSON parsing errors after SSL fix; continue observing ingestion logs for regressions.

## 9. Implementation Priorities and Follow-Up
- Critical: implement query intent classification, hybrid retrieval policies, workflow orchestration, and populate environment deployments.
- High: finish LCARS UI polish, persona automation, evaluation dashboards, and integrate AEHRL/HGRN outputs into admin views.
- Medium: deliver delta refresh tooling, automated bug bundle generation, and test result visualization.
- Ongoing: maintain security posture (CSP, rate limiting), monitor GPT-5 costs, update documentation, and refresh dependency versions.

## 10. Reference Documents
- requirements master v2, full traceability matrix, phase playbooks, feature requirement specs (FR-001-FR-031), security summaries, setup runbooks, testing guides, bug resolution reports, implementation roadmap, and code analysis report.
