
# TTRPG Center — MVP v2 User Stories & Test Cases

> **Source of truth:** Requirements-MVP-Version-2.md (Phased MVP)  
> **Scope of this document:** Detailed user stories, acceptance criteria, and executable test cases for each requirement/phase.  
> **Test strategy:** All tests are runnable externally (from the local system or a separate Docker container) targeting the stack via environment-aware endpoints. Tests can be initiated from the Admin UI and via CI. Suites: **Unit, Functional, Integration, Security, Regression, Performance/Resilience**.

---

## 0. Test Architecture (Cross‑Cutting)

### 0.1 External Execution & Per‑Environment Switch
All tests run **outside** the target stack and talk over HTTP/WebSocket/gRPC (as applicable). Environments are selected via **environment variables** and **.env files**:

- `TARGET_ENV` in `{DEV,TEST,PROD}` (default: `DEV`)
- `BASE_URL` for the target API/UI (defaults by env):  
  - DEV → `http://localhost:8000`
  - TEST → `http://localhost:8181`
  - PROD → `https://prod.example.com` (TLS)
- `ADMIN_UI_URL` (Admin SPA):  
  - DEV → `http://localhost:8000/admin`
  - TEST → `http://localhost:8181/admin`
  - PROD → `https://prod.example.com/admin`
- `OTEL_EXPORTER_OTLP_ENDPOINT` (optional) for test telemetry
- `TEST_ARTIFACT_DIR` (default: `./artifacts/${TARGET_ENV}/`)

> Provide a `.env.dev`, `.env.test`, `.env.prod` with the above keys. All test runners load `.env` then allow overrides via CLI/CI vars.

### 0.2 Toolchain (Suggested, replaceable)
- **Unit/Integration**: `pytest` (Python) + coverage
- **API Functional/Regression**: Postman/Newman **or** `pytest` + `requests`
- **Browser Functional**: Playwright (headless) or Cypress
- **Security (DAST)**: OWASP ZAP Baseline/Full scan (containerized), Nikto (optional)
- **SAST**: Semgrep (polyglot), Bandit (Python), Trivy (images)
- **Performance/Resilience**: k6 (HTTP), Locust (optional)
- **Containers**: Dedicated `tests-runner` Docker image, network‑attached to target via Docker network or localhost

### 0.3 Admin UI Test Console (Run Tests from UI)
Add a **Test Console** to Admin UI (Phase 3) that can:
- List available suites: Unit, Functional (API/UI), Security, Regression, Performance.
- Run **full suite** or **subset** (by tag).
- Show **live logs** and **status** (WebSocket/Server‑Sent Events).
- Persist results to `/env/{env}/artifacts/test_runs/{timestamp}/` with `results.json`, `logs/`, `reports/`.
- Allow **download** of JUnit XML, HTML, ZAP, and k6 reports.

**Minimal API (tests‑runner container):**
- `POST /api/tests/run` body: `{ "suite": "functional|unit|security|regression|performance|all", "env": "DEV|TEST|PROD", "tags": ["..."] }`
- `GET  /api/tests/runs/:id` returns summary & links
- `GET  /api/tests/runs/:id/stream` (WS/SSE) for live output

> This tests‑runner is **external** to the app runtime. It invokes the same CLI commands documented below and stores artifacts in the per‑environment paths.

### 0.4 CLI Entrypoints (External or CI)
```bash
# Unit + Integration
pytest -q --maxfail=1 --disable-warnings --junitxml artifacts/${TARGET_ENV}/unit/junit.xml

# API Functional (Pytest style)
pytest tests/functional -q --junitxml artifacts/${TARGET_ENV}/functional/junit.xml

# API Functional (Newman alternative)
newman run postman/TTRPG.postman_collection.json \
  -e postman/${TARGET_ENV}.postman_environment.json \
  --reporters cli,junit --reporter-junit-export artifacts/${TARGET_ENV}/functional/newman.xml

# UI Functional (Playwright)
pytest tests/ui -q --junitxml artifacts/${TARGET_ENV}/ui/junit.xml

# Security (ZAP Baseline)
docker run --rm -v "$(pwd)/artifacts/${TARGET_ENV}/security:/zap/wrk" \
  -t owasp/zap2docker-stable zap-baseline.py -t "${BASE_URL}" -r zap-baseline.html

# Performance (k6)
k6 run --summary-export artifacts/${TARGET_ENV}/perf/summary.json tests/perf/api-smoke.js

# Regression
pytest tests/regression -q --junitxml artifacts/${TARGET_ENV}/regression/junit.xml -m "regression"
```

---

## Phase 0 — Environment Isolation & Foundations

### ENV‑001: Isolated Docker stacks & volumes
**User Stories**
1. As a **DevOps engineer**, I want each env (DEV/TEST/PROD) on distinct ports with isolated volumes so data never cross‑contaminates.
2. As a **developer**, I want to bring up a single env with one command to reproduce issues locally.
3. As a **QA engineer**, I want to target an env by URL to run external tests with no local code changes.

**Acceptance Criteria (AC)**
- AC‑0.1: `docker compose --profile DEV up` exposes `:8000`, TEST `:8181`, PROD `:8282`.
- AC‑0.2: Volumes under `/env/{env}/{code,config,data,artifacts,logs}` are created and isolated.
- AC‑0.3: Smoke test to DEV does not affect TEST/PROD artifacts.
- AC‑0.4: External tests only require `BASE_URL` and `TARGET_ENV` to switch targets.

**Test Cases**
- **Unit**
  - U‑001: Path resolver builds correct root path for `TARGET_ENV`.
  - U‑002: Config loader maps ports/volumes per env.
- **Functional**
  - F‑001: Curl `/healthz` on DEV/TEST/PROD returns 200, body includes env label.
  - F‑002: Write a log line in DEV; assert absence in TEST/PROD logs.
- **Regression**
  - R‑001: Bring up/down DEV repeatedly; volumes persist; no cross-env leakage.
- **Security**
  - S‑001: Confirm CORS and headers differ by env policy (later enforced in Phase 6).

### ENV‑002: Immutable builds & promotion/rollback
**User Stories**
1. As a **release manager**, I want promotion via retag/redeploy with no rebuilds, enabling rollbacks.
2. As a **DevOps engineer**, I want versioned images and compose files tracked in Git.

**AC**
- AC‑0.5: `promote.sh DEV→TEST` retags image and updates compose.
- AC‑0.6: `rollback.sh TEST` restores prior tag and stack reaches healthy state.
- AC‑0.7: Artifacts record image tags and timestamps.

**Test Cases**
- Unit: U‑003 (tag parser), U‑004 (compose mutator).
- Functional: F‑003 promote; F‑004 rollback; validate `/healthz` and version header.
- Regression: R‑002 nightly promotion/rollback smoke.
- Security: S‑002 image provenance check (Trivy).

### ENV‑003: Structured JSON logs & /healthz
**User Stories**
- As an **SRE**, I need JSON logs per env and a standard `/healthz` for probes.

**AC**
- AC‑0.8: Logs are JSON and include `env`, `service`, `timestamp`, `level`, `trace_id`.
- AC‑0.9: `/healthz` returns 200 with `status:ok` and `service_versions`.

**Test Cases**
- Unit: U‑005 JSON schema validation for log lines.
- Functional: F‑005 GET `/healthz` schema and timing < 250ms.
- Regression: R‑003 long‑run log rotation keeps size caps.
- Security: S‑003 logs exclude secrets (regex scan).

### ENV‑004: CI test gates
**User Stories**
- As a **maintainer**, I want Unit+Functional on PR and nightly Regression on `main`.

**AC**
- AC‑0.10: PR pipeline fails on any test failure.
- AC‑0.11: Nightly regression artifacts uploaded and linked.

**Test Cases**
- Unit: U‑006 CI config linter.
- Functional: F‑006 CI triggers on PR; reports visible.
- Regression: R‑004 nightly suite executes.
- Security: S‑004 Semgrep and Trivy fail on criticals.

---

## Phase 1 — Ingestion Pipeline (Pass 0 → G, 10 MB split)

### Pass 0: Preflight & De‑dup
**User Stories**
- As an **ingestion operator**, I want SHA/pagecount preflight to skip duplicates quickly.

**AC**
- AC‑1.1: For matching `file_sha` and chunk count, pipeline short‑circuits and records a “no‑op” job.

**Test Cases**
- Unit: U‑101 SHA calc correctness; U‑102 manifest reader.
- Functional: F‑101 Upload duplicate → status `skipped`; artifacts unchanged.
- Regression: R‑101 Re‑ingesting fixtures remains idempotent.
- Security: S‑101 Path traversal safeguards on uploads.

### Pass A: TOC & Dictionary Seed
**User Stories**
- As a **taxonomy editor**, I need stable `section_id` and initial canonical dictionary entries.

**AC**
- AC‑1.2: Extracted TOC maps to `{section_id, page_range}`.
- AC‑1.3: Dictionary canonicals created; Pass C/D/E/G produce **proposals** only.

**Test Cases**
- Unit: U‑103 TOC parser; U‑104 `section_id` stability.
- Functional: F‑102 Ingest PDF → `dictionary.seed.json` exists; entries unique.
- Regression: R‑102 Sections unchanged across re-runs given same input.
- Security: S‑102 TOC extraction sandboxed; no RCE in parsers.

### Pass B: Fast Split (≤10 MB parts)
**User Stories**
- As an **operator**, I need splitting safe for scanned PDFs and lineage preserved.

**AC**
- AC‑1.4: PDFs >10 MB split into parts ≤10 MB.
- AC‑1.5: `parts.jsonl` contains `{doc_id, parent_id, part_id, section_id, page_range, file_path}`.

**Test Cases**
- Unit: U‑105 size estimator; U‑106 lineage writer.
- Functional: F‑103 Upload >10 MB → parts produced; each ≤10 MB; lineage OK.
- Regression: R‑103 Scanned fixture splits deterministically.
- Security: S‑103 File type/size validation and quarantine on malformed.

### Pass C: Extraction (Unstructured.io)
**User Stories**
- As a **data engineer**, I need OCR for scans and chunk emission with metadata.

**AC**
- AC‑1.6: `chunks.jsonl` with `{doc_id, part_id, section_id, page, block_type, text}`.
- AC‑1.7: `dict_delta.passC.json` emitted with proposals.

**Test Cases**
- Unit: U‑107 OCR handler mocked; U‑108 chunk schema validator.
- Functional: F‑104 Run C → chunks and `dict_delta.passC.json` exist.
- Regression: R‑104 OCR quality baseline on scanned fixture ≥ threshold.
- Security: S‑104 Container network isolation; rate‑limits.

### Pass D: Normalize + Embeddings (Haystack)
**User Stories**
- As a **retrieval engineer**, I need normalized text embedded and upserted to vector store.

**AC**
- AC‑1.8: `dict_delta.passD.json` emitted; vector upserts counted and logged.

**Test Cases**
- Unit: U‑109 normalizer; U‑110 embedding call adapter.
- Functional: F‑105 Vector count equals chunk count (minus filtered).
- Regression: R‑105 Re‑run does not duplicate vectors.
- Security: S‑105 Secrets pulled from env, not code.

### Pass E: Graph Compile (LlamaIndex)
**User Stories**
- As a **knowledge engineer**, I need nodes/edges compiled and persisted.

**AC**
- AC‑1.9: `graph.json` present; `dict_delta.passE.json` emitted; lineage preserved.

**Test Cases**
- Unit: U‑111 node/edge schema; U‑112 lineage join.
- Functional: F‑106 Graph build completes; node/edge counts > 0.
- Regression: R‑106 Deterministic graph with same inputs.
- Security: S‑106 Graph schema migrations versioned.

### Pass F: Validation & Manifest
**User Stories**
- As a **QA**, I need referential integrity checks and a `manifest.json` with checksums.

**AC**
- AC‑1.10: All deltas merged to `dict_delta.all.json`.
- AC‑1.11: `manifest.json` has checksums and tool versions.

**Test Cases**
- Unit: U‑113 referential integrity rules; U‑114 checksum calculator.
- Functional: F‑107 Manifest exists; sums verified across artifacts.
- Regression: R‑107 Changing a chunk invalidates checksum as expected.
- Security: S‑107 Signed manifests (optional).

### Pass G: HGRN Consistency
**User Stories**
- As a **taxonomy editor**, I need alias drift/orphans detected with actionable report.

**AC**
- AC‑1.12: `hgrn.report.json`, `dict_delta.passG.json`, `hgrn.actions.json` produced.

**Test Cases**
- Unit: U‑115 alias detector; U‑116 orphan rule set.
- Functional: F‑108 Inject synthetic alias → detector flags and proposes fix.
- Regression: R‑108 Known drift corpus remains detected.
- Security: S‑108 Reports redact PII.

---

## Phase 2 — Retrieval Orchestrator (Hybrid RAG + Graph)

### RET‑001: Query classifier
**User Stories**
- As a **retrieval service**, I classify `{intent, domain, complexity}` to guide the plan.

**AC**
- AC‑2.1: Classifier output stored in trace with confidence.

**Test Cases**
- Unit: U‑201 classifier routing for single‑hop/compare/procedural.
- Functional: F‑201 Sample queries → expected labels.
- Regression: R‑201 20 canonical queries keep historical labels barring model change.
- Security: S‑201 Input validation; prompt injection sanitization.

### RET‑002: Policy → plan
**User Stories**
- As a **system**, I map classification to a plan (vector/metadata/graphwalk/rerank/self‑consistency).

**AC**
- AC‑2.2: Plan logged per query; tunable weights α,β,γ,δ.

**Test Cases**
- Unit: U‑202 policy tables; U‑203 weight resolver.
- Functional: F‑202 Plan contains expected steps for complexity tiers.
- Regression: R‑202 No plan regressions across versions (golden files).
- Security: S‑202 Config not mutable by user inputs.

### RET‑003: Hybrid retriever
**User Stories**
- As a **retriever**, I execute plan, dedupe, and enforce token budget.

**AC**
- AC‑2.3: Retriever returns N context packs with dedup and page/section refs.

**Test Cases**
- Unit: U‑204 dedupe; U‑205 pack builder.
- Functional: F‑203 Packs include path explanation + chunks + page refs.
- Regression: R‑203 Graph‑assisted plans outperform vector‑only baseline.
- Security: S‑203 Source gating enforced in Phase 6.

### RET‑004: Answer composer with citations
**User Stories**
- As a **user**, I receive an answer with **[Book §Section p.Page]** citations.

**AC**
- AC‑2.4: ≥2 citations per answer when available; compact provenance view.

**Test Cases**
- Unit: U‑206 citation renderer; U‑207 token budgeter.
- Functional: F‑204 Answers include required citations on fixtures.
- Regression: R‑204 Citation accuracy metric ≥ threshold.
- Security: S‑204 Output redaction for sensitive fields (Phase 6).

### RET‑005: Observability trace
**User Stories**
- As a **developer**, I can view end‑to‑end trace (classify → plan → retrieve → compose).

**AC**
- AC‑2.5: Trace available via Admin and exported to OTel.

**Test Cases**
- Unit: U‑208 trace schema.
- Functional: F‑205 Admin shows trace with latencies.
- Regression: R‑205 Trace fields stable.
- Security: S‑205 PII scrubber in traces.

---

## Phase 3 — Admin UI (CRUD + Bulk + Test Console)

### ADM‑001: Data explorer (env‑scoped)
**User Stories**
- As an **admin**, I can browse Postgres/Mongo/Cassandra scoped to current env.

**AC**
- AC‑3.1: Switching env in UI switches data sources.

**Test Cases**
- Unit: U‑301 auth/context providers (later tied to Phase 6).
- Functional: F‑301 Data views reflect selected env; no cross‑env data.
- Regression: R‑301 Pagination/sorting stable.
- Security: S‑301 RBAC enforced in Phase 6.

### ADM‑002: CRUD for dictionary/chunks/graph/jobs
**User Stories**
- As an **admin**, I maintain dictionaries, chunks, nodes/edges, jobs, artifacts, logs.

**AC**
- AC‑3.2: CRUD ops audit‑logged; revisions tracked.

**Test Cases**
- Unit: U‑302 validation schemas.
- Functional: F‑302 Create→Read→Update→Delete and audit log entries present.
- Regression: R‑302 Export/import round‑trips preserve integrity.
- Security: S‑302 Input validation & CSRF (if applicable).

### ADM‑003: Bulk actions
**User Stories**
- As an **admin**, I can bulk delete logs older than N days or chunks for DOC_ID, etc.

**AC**
- AC‑3.3: Bulk actions confirm scope and show counts before/after.

**Test Cases**
- Unit: U‑303 bulk selectors.
- Functional: F‑303 TTL cleanup; chunk purge per DOC_ID.
- Regression: R‑303 Safe‑guard prompts preventing large accidental deletes.
- Security: S‑303 Rate‑limit & audit.

### ADM‑004: Artifact browser
**User Stories**
- As an **admin**, I can download pass outputs and manifests per job.

**AC**
- AC‑3.4: Files listed by job; hashes shown; download works.

**Test Cases**
- Unit: U‑304 manifest parser.
- Functional: F‑304 Download `graph.json`, `manifest.json` works.
- Regression: R‑304 Large files stream without timeout.
- Security: S‑304 Path traversal prevention.

### ADM‑005: HGRN review
**User Stories**
- As an **editor**, I can accept/reject HGRN recommendations and create revisions.

**AC**
- AC‑3.5: Accepting proposals increments dictionary revision; actions stored.

**Test Cases**
- Unit: U‑305 decision journal writer.
- Functional: F‑305 Accept/reject flows update revision and graph diffs.
- Regression: R‑305 Undo/redo stack consistent.
- Security: S‑305 Audit completeness.

### ADM‑006: **Test Console** (initiate tests from Admin UI)
**User Stories**
- As a **QA/admin**, I can run **Unit/Functional/Security/Regression/Performance** suites from the Admin UI against any env and download reports.

**AC**
- AC‑3.6: Test Console lists suites & tags, runs selected, streams logs, and stores artifacts under `/env/{env}/artifacts/test_runs/`.
- AC‑3.7: Completed run shows pass/fail counts and links to JUnit/ZAP/k6 reports.

**Test Cases**
- Unit: U‑306 client → tests‑runner API adapter & schema.
- Functional: F‑306 Trigger Functional suite for DEV; watch live; download JUnit; statuses match CLI run.
- Regression: R‑306 Schedule nightly “full” from UI (optional) writes cron entry or triggers CI.
- Security: S‑306 Only admins can execute; request payload validated; rate‑limited.

---

## Phase 4 — Observability & Feedback

### OBS‑001: OTel spans + structured logs
**User Stories**
- As an **SRE**, I need cross‑service spans for ingestion/retrieval.

**AC**
- AC‑4.1: Spans visible in dashboard with env tags.

**Tests**: Unit U‑401 exporter stubs; Functional F‑401 trace appears for sample ingestion; Regression R‑401 trace fields stable; Security S‑401 token redaction.

### OBS‑002: Dashboards
**User Stories**
- As an **operator**, I can see progress, errors, and costs per env.

**AC**
- AC‑4.2: Ingestion/retrieval dashboards show KPIs and link to artifacts.

**Tests**: Unit U‑402 metrics calc; Functional F‑402 widgets render; Regression R‑402 thresholds alert; Security S‑402 dashboard auth.

### OBS‑003: Feedback → tests/bugs
**User Stories**
- As a **user**, 👍 creates regression tests; 👎 opens bug bundle with logs/artifacts.

**AC**
- AC‑4.3: 👍 stores query, expected behavior, and produces a regression test template.
- AC‑4.4: 👎 bundles logs and opens BUG with attachments.

**Tests**: Unit U‑403 feedback serializer; Functional F‑403 thumbs up generates test; Regression R‑403 test persists; Security S‑403 PII trim.

### OBS‑004: CI gates
**User Stories**
- As a **maintainer**, CI blocks bad commits via gates and surfaces artifacts.

**AC**
- AC‑4.5: PR gates Unit+Functional; nightly adds Regression; Security scans must pass.

**Tests**: as in Phase 0 ENV‑004 (re‑asserted).

---

## Phase 5 — User UI (Query & Provenance)

### UI‑001: Themed query UI
**User Stories**
- As a **player/GM**, I query with a retro/LCARS theme and get readable results.

**AC**
- AC‑5.1: Query input & results panel render consistently across envs.

**Tests**: Unit U‑501 UI components snapshot; Functional F‑501 Playwright E2E smoke; Regression R‑501 visual diffs; Security S‑501 CSP headers.

### UI‑002: Answer view with provenance & latency
**User Stories**
- As a **user**, I see provenance, model badge, and latency.

**AC**
- AC‑5.2: Citations + model badge + latency visible per answer.

**Tests**: Unit U‑502 renderer; Functional F‑502 answers include required fields; Regression R‑502 citation formatting; Security S‑502 XSS prevention.

### UI‑003: Session & user memory
**User Stories**
- As a **user**, I have per‑tab session memory and persisted preferences/history.

**AC**
- AC‑5.3: Session memory cleared on tab close (configurable); user memory saved according to policy.

**Tests**: Unit U‑503 store; Functional F‑503 memory restored; Regression R‑503 cache policy; Security S‑503 consent & privacy.

### UI‑004: Cache policies by env
**User Stories**
- As an **SRE**, I need DEV=no‑store, TEST=≤5s, PROD=configurable cache behavior.

**AC**
- AC‑5.4: Headers reflect env policy; override works.

**Tests**: Unit U‑504 cache header helper; Functional F‑504 header assertions; Regression R‑504 perf impact baseline; Security S‑504 no sensitive cache.


---

## Phase 6 — Authentication, RBAC & Source Gating

### SEC‑001: JWT auth (RS256)
**User Stories**
- As a **user/admin**, I authenticate via JWT; tokens verified server‑side.

**AC**
- AC‑6.1: Login obtains RS256 JWT; `/me` shows roles.

**Tests**: Unit U‑601 key loader; Functional F‑601 auth flow; Security S‑601 JWT attacks (replay/alg confusion) blocked; Regression R‑601 token refresh.

### SEC‑002: Source gating in retrieval
**User Stories**
- As a **content admin**, I set `allowed_sources` per user; retrieval filters by it.

**AC**
- AC‑6.2: Two users see different results based on source gates.

**Tests**: Unit U‑602 policy filter; Functional F‑602 A/B users diverge; Regression R‑602 no leakage; Security S‑602 bypass attempts blocked.

### SEC‑003: Admin RBAC
**User Stories**
- As an **admin**, I can promote canonicals, edit graph schema, perform bulk deletes; others cannot.

**AC**
- AC‑6.3: RBAC blocks non‑admins from admin endpoints.

**Tests**: Unit U‑603 role middleware; Functional F‑603 forbidden checks; Security S‑603 privilege escalation tests; Regression R‑603 audit completeness.

### SEC‑004: CORS/TLS/Rate‑limit
**User Stories**
- As an **SRE**, I need env‑scoped CORS, TLS/HSTS in TEST/PROD, and Redis rate limits.

**AC**
- AC‑6.4: CORS list per env; TLS terminates in TEST/PROD; rate‑limit headers present.

**Tests**: Unit U‑604 CORS config; Functional F‑604 TLS check; Security S‑604 rate‑limit evasion attempts; Regression R‑604 perf under limit.

### SEC‑005: Audit log
**User Stories**
- As a **security auditor**, I require audit of logins, role changes, dictionary promotions, bulk deletes.

**AC**
- AC‑6.5: Audit entries immutable; exportable per env.

**Tests**: Unit U‑605 append‑only store; Functional F‑605 events recorded; Security S‑605 tamper detection; Regression R‑605 export size & integrity.

---

## 7. Mappings & Traceability

| Requirement | User Stories (IDs) | Primary Test Suites | Key Artifacts |
|---|---|---|---|
| ENV‑001 | DevOps isolation | Unit, Functional, Regression | `/env/{env}/...`, `/healthz` |
| ENV‑002 | Promotion/rollback | Functional, Regression, Security | image tags, compose files |
| ENV‑003 | JSON logs/health | Unit, Functional | logs, health payload |
| ENV‑004 | CI gates | Regression, Security | CI configs, reports |
| Pass 0..G | Ingestion pipeline | Unit, Functional, Regression | manifest, deltas, graph |
| RET‑001..005 | Orchestrator | Unit, Functional, Regression | traces, citations |
| ADM‑001..006 | Admin UI | Unit, Functional, Security | audit logs, artifacts |
| OBS‑001..004 | Observability | Unit, Functional | spans, dashboards |
| UI‑001..004 | User UI | Unit, Functional, Regression | views, headers |
| SEC‑001..005 | Auth/RBAC/Gating | Unit, Functional, Security | JWT, audit, policies |

---

## 8. Example Test Files Layout

```
tests/
  unit/
    test_env_paths.py
    test_sha_manifest.py
  functional/
    test_healthz.py
    test_ingestion_pipeline.py
    test_admin_artifacts.py
  ui/
    test_user_query_flow_playwright.py
  regression/
    test_canonical_queries.py   # 20 canonical multi-hop tasks
  security/
    zap-baseline.conf
    test_jwt_hardening.py
  perf/
    api-smoke.js                # k6 script
postman/
  TTRPG.postman_collection.json
  DEV.postman_environment.json
  TEST.postman_environment.json
  PROD.postman_environment.json
artifacts/
  DEV/ ...
  TEST/ ...
  PROD/ ...
```

---

## 9. Sample Commands (Per‑Env)

```bash
export TARGET_ENV=DEV
export BASE_URL=http://localhost:8000
pytest -q tests/functional --junitxml artifacts/${TARGET_ENV}/functional/junit.xml

export TARGET_ENV=TEST
export BASE_URL=http://localhost:8181
newman run postman/TTRPG.postman_collection.json -e postman/TEST.postman_environment.json

export TARGET_ENV=PROD
export BASE_URL=https://prod.example.com
k6 run tests/perf/api-smoke.js
```

---

## 10. Exit Criteria (Green Gates)

- 100% of ACs above satisfied per requirement.  
- All suites green in CI and from Admin UI **Test Console**.  
- Regression baseline established from: 2 fixture PDFs (normal + scanned) and 20 canonical multi‑hop queries.  
- Security scans (SAST, DAST, image) no criticals; audit trail complete.
