# TTRPG Center — Master Requirements (v2, Expanded User Stories & Tests)

> This version expands Section 2 (User Stories) and Section 3 (Automated Tests) with **richer story detail**, **clear acceptance criteria**, and **explicit Entry/Exit criteria** (plus example test code) for each capability, Feature Request, and Bug fix.

---

## Section 1: Executive Requirements (CIO Readable) — Unchanged Summary
(See v1 for the full CIO summary. Key points retained for context.)
- Isolated **DEV/TEST/PROD** environments with immutable builds and fixed ports.
- **6‑Pass Ingestion** (A–F): TOC prime → logical split → unstructured → Haystack enrich/vectorize → LlamaIndex graph → cleanup/manifest.
- **RAG Retrieval** with provenance, **Graph workflows**, **Admin UI** (status, ingestion, dictionary, tests, tickets), **User UI** (enter‑to‑submit, stop, thumbs feedback).
- **Security** (JWT, HTTPS/TLS, CORS, rate‑limit). **Performance** (Redis cache/session, async DB). **Governance** (immutable reqs, approvals, audit).

---

## Section 2: Detailed User Stories (Rich)

### Phase 0 — Environments, Builds, WebUI Cache
**US-ARCH-001 — Environment Isolation**  
As a DevOps engineer, I need isolated `/env/dev`, `/env/test`, `/env/prod` with dedicated ports (8000/8181/8282) so code/data don’t leak across environments.  
**Acceptance:** Processes run only within their env directory; Admin “System Status” shows active env and build ID.

**US-ARCH-002 — Immutable Builds & Promotion**  
As an Admin, I need timestamped build IDs with promote/rollback so releases are deterministic.  
**Acceptance:** Build metadata stored; promote/rollback visible in audit log; UI shows current build per env.

**US-ARCH-004 — WebUI Cache Controls**  
As an Admin, I can disable UI cache on demand so QA sees changes instantly.  
**Acceptance:** Toggle updates headers (no‑store/low TTL), verified by network panel.

---

### Phase 1 — 6‑Pass Ingestion
**US-ING-001 (Pass A: TOC Prime)**  
As an ingestion operator, I want TOC/heading parse to seed a dictionary (term → pages/sections) so downstream chunking is section‑aware.  
**Acceptance:** `artifact/{job}/passA.json` has `{term, page_range, section_title}`.

**US-ING-002 (Pass B: Logical Split >25MB)**  
As the pipeline, I must split oversized PDFs along semantic section boundaries, preserving page ranges.  
**Acceptance:** `passB.manifest` lists sub‑files with contiguous, non‑overlapping ranges.

**US-ING-003 (Pass C: Unstructured Extraction)**  
As the pipeline, I convert PDFs into paragraph‑level chunks with metadata `{book, section, page, figure/table flags}`.  
**Acceptance:** ≥ 95% of paragraphs represented; tables/lists marked.

**US-ING-004 (Pass D: Haystack Enrich & Embed)**  
As the pipeline, I normalize fields, add embeddings, and index to AstraDB so retrieval is accurate and fast.  
**Acceptance:** embeddings present; index count equals chunk count; latency P95 ≤ target.

**US-ING-005 (Pass E: LlamaIndex Graph Compile)**  
As the pipeline, I build a graph (nodes: terms/sections/entities; edges: references/depends_on) to enable graphwalk reasoning.  
**Acceptance:** Graph ≥ N nodes; edges validated; sample queries return multi‑hop paths.

**US-ING-006 (Pass F: Cleanup & Manifest)**  
As the pipeline, I deduplicate near‑identical chunks and finalize `manifest.json` with checksums and pass statuses.  
**Acceptance:** Duplicate rate < threshold; manifest has PassA..F complete=true.

---

### Phase 2 — RAG Retrieval
**US-RAG-001 — Query with Provenance**  
As a Player/GM, I want natural language answers with citations and top‑k chunks shown.  
**Acceptance:** Response shows answer, 3 sources with page/section, model/latency stats.

**US-RAG-002 — Policy‑Aware Orchestrator**  
As the orchestrator, I choose paths (simple/graphwalk/workflow) based on complexity & content type.  
**Acceptance:** Trace metadata shows route decision; fallbacks logged.

---

### Phase 3 — Graph Workflows
**US-WF-001 — Character Creation Flow**  
As a Player, I step through a validated, stateful creation flow; invalid choices prompt corrections.  
**Acceptance:** State saved; back/next; summary export; invalid steps blocked with reasons.

**US-WF-002 — Graphwalk Reasoning**  
As the system, I perform bounded graph‑walk + re‑grounding for multi‑hop rules.  
**Acceptance:** “reasoning_trace” present; correctness delta on complex set improves over baseline.

---

### Phase 4 — Admin UI
**US-ADM-001 — System Status**  
As an Admin, I view per‑env health, job counts, build IDs, error rates.  
**Acceptance:** Cards update ≤5s; links to logs.

**US-ADM-002 — Ingestion Console**  
As an Admin, I start/stop jobs, view live logs (last 20), and download artifacts.  
**Acceptance:** Job lifecycle transitions visible; artifacts downloadable.

**US-ADM-003 — Dictionary Manager**  
As an Admin, I search/edit terms; changes versioned by env.  
**Acceptance:** Edit audit stored; rollback possible.

**US-ADM-004 — Regression Tests & Bug Bundles**  
As an Admin, I run suites per env and inspect failures (inputs, traces, diffs).  
**Acceptance:** Test results persist; “Create Bug” from failure pre‑fills bundle.

**US-ADM-005 — Ticketing (Bug/Feature) & Feedback Review**  
As an Admin, I manage tickets (open/closed), filter by status/type, add notes; feedback triage has buttons **Feature | Bug | Close** plus notes.  
**Acceptance:** New ticket adheres to standard template; filters persist; actions logged.

---

### Phase 5 — User UI
**US-UI-001 — Enter‑to‑Submit**  
As a User, pressing Enter submits the query (Shift+Enter = newline).  
**Acceptance:** Works with IME; preference remembered.

**US-UI-002 — Stop Button**  
As a User, I can stop a running generation.  
**Acceptance:** Job cancels promptly; partial answer labeled “stopped”.

**US-UI-003 — Feedback (Thumbs)**  
As a User, I click 👍/👎 to open a dialog (tags, notes, include context), which reaches Admin Feedback Review.  
**Acceptance:** Record created with session/query hash; visible in Admin within seconds.

---

### Phase 6 — Testing & Feedback
**US-TEST-001 — 👍 Creates Regression**  
As a User, a 👍 can convert to a pinned regression in that env.  
**Acceptance:** New test created with input/expected; appears in Admin Tests.

**US-TEST-002 — 👎 Creates Bug Bundle**  
As a User, a 👎 can create a prefilled bug (inputs, retrieved chunks, traces, errors).  
**Acceptance:** Bug file saved; link shared; ticket opened.

**US-TEST-003 — Admin Test Review**  
As an Admin, I review/approve/disable tests; approvals required for PROD promotion.  
**Acceptance:** Gate blocks promote when failures exist.

---

### Phase 7 — Requirements & Features (Governance)
**US-REQ-001 — Immutable Requirements**  
As an Admin, I store versioned JSON requirements; changes require a PR & approval.  
**Acceptance:** Schema‑validated; visible in System Status.

**US-REQ-002 — Feature Approval Workflow**  
As an Admin, I approve/deny features with rationale; links to impacted tests.  
**Acceptance:** Only approved FRs deploy; audit trail complete.

---

### Security (FR-SEC-401/402/403/406/407)
**US-SEC-401 — JWT Authentication**  
As a Security Engineer, I implement RS256 JWTs, roles, refresh, logout blacklist.  
**Acceptance:** Admin endpoints require admin token; rate‑limited login; tokens rotated.

**US-SEC-402 — CORS per‑Env**  
As Security, I enforce allow‑lists; production is HTTPS‑only origins.  
**Acceptance:** No wildcard in prod; startup validation fails on wildcards.

**US-SEC-403 — HTTPS/TLS**  
As Security/DevOps, I enforce HTTPS, HSTS, strong ciphers, cert monitoring.  
**Acceptance:** HTTP→HTTPS 301; SSL Labs A/A+; expiry alerts 30/7/1 days.

**US-SEC-406 — Rate Limiting**  
As Security, I use Redis sliding‑window, endpoint categories, IP & user tiers.  
**Acceptance:** 429 with headers; penalties for violators; admin bypass role.

**US-SEC-407 — Core CORS Aligned**  
As Security, I reuse the shared secure CORS helper in core app.  
**Acceptance:** Tests for FR‑SEC‑402 pass in core app.

---

### Performance (FR-PERF-404/405)
**US-PERF-404 — Redis Cache/Session/Compaction**  
As a SysAdmin, I add Redis for cache/session and auto‑compaction of conversation context with a UI status bar.  
**Acceptance:** Cache hit‑ratio target; session resume; compaction bar and events.

**US-PERF-405 — Async DB Ops**  
As a Dev, I convert DB calls & endpoints to async, with pooling and proper cleanup.  
**Acceptance:** P95 latency ↓40%; concurrency ↑3×; no leaks.

---

### Architecture/Config (FR-ARCH-501/602, FR-CONFIG-601, FR-DB-001, FR-INGEST-201, FR-REASON-502)
**US-ARCH-501 — Unify RAG Pipeline**  
As a Dev, final answer generation happens in the orchestrator, not UI apps.  
**Acceptance:** Single code path; duplicate logic removed; tests pass.

**US-ARCH-602 — Decouple UI**  
As a Dev, I split monolithic UI handlers into service modules.  
**Acceptance:** Smaller modules; clear ownership; same behavior.

**US-CONFIG-601 — Centralize Secrets/Env**  
As a DevOps, I load env/secrets through a single config layer with validation.  
**Acceptance:** Start‑up fails on invalid; no hardcoded secrets.

**US-DB-001 — Local DB**  
As a Dev, I use SQLite + SQLModel + Alembic for auth/roles/source links & a local admin UX.  
**Acceptance:** CRUD works; migrations tested; data integrity constraints enforced.

**US-INGEST-201 — Ingestion/Graph Enhancements**  
As a Data Engineer, I improve section awareness, table/list handling, dictionary quality, multi‑threading, and file‑size thresholds.  
**Acceptance:** Higher precision/recall on rules QA; stable multithread with no race conditions.

**US-REASON-502 — Integrate Graphwalk**  
As the orchestrator, I invoke graphwalk + deterministic fallback.  
**Acceptance:** Policy triggers; trace recorded; accuracy improves on benchmark set.

---

### Bugs → Corrective Stories (Selected Highlights; all BUG‑001..018 covered in tests below)
- **BUG‑001 OAuth Redirect**: Fix incorrect login redirect.  
- **BUG‑002 Mock Data**: Remove mocks; wire to real data behind a feature flag for tests only.  
- **BUG‑003 OAuth Auth Failed**: Implement proper JWT/RBAC; surface clear errors.  
- **BUG‑004 CORS Wildcards**: Remove `*` in prod.  
- **BUG‑005 Reasoner Not Wired**: Connect graphwalk in orchestrator.  
- **BUG‑006 RAG Duplication**: Deduplicate code paths; single orchestrator.  
- **BUG‑007 app_user Mixed Concerns**: Decouple UI → services.  
- **BUG‑008 Graph Build Not in Runtime**: Ensure runtime loads graph artifacts.  
- **BUG‑009 Extract ‘Murderous Command’ Unreferenced**: Ensure dictionary linking & tests.  
- **BUG‑010 Phase 0/1 Gaps**: Close gaps per acceptance.  
- **BUG‑011 Regression Failures**: Fix tests & infra flakiness.  
- **BUG‑012 Planner Neighbors**: Fix GraphStore.neighbors expansion.  
- **BUG‑013 Prod Sec/Perf**: Enforce TLS, rate limit, remove insecure patterns.  
- **BUG‑014 Persona Pipeline Drift**: Fix encoding, API contracts.  
- **BUG‑015 Phase 7 API Contracts**: Align and lock.  
- **BUG‑016 Non‑Phase7 Regressions**: Stabilize suites.  
- **BUG‑017 SSL Verify**: Proper cert checks; DEV‑only overrides.  
- **BUG‑018 Bulk Ingestion**: Pass B JSON validation, thread race fix, safe DB upserts.

---

## Section 3: Detailed Automated Test Cases (with Entry/Exit)

> Abbreviations: **E** = Entry Criteria, **X** = Exit Criteria.

### Phase 0
**TST-ARCH-001 — Env Isolation**  
**E:** Processes started via `./env/dev`, `./env/test`, `./env/prod`.  
**X:** PID cwd matches env path; ports bound correctly; cross‑env file access denied.  
```python
def test_env_isolation(dev_proc, test_proc, prod_proc):
    assert dev_proc.cwd.endswith("/env/dev")
    assert prod_proc.port == 8282
```

**TST-ARCH-002 — Immutable Builds/Promotion**  
**E:** Build created with ID; promote invoked.  
**X:** Target env shows new ID; rollback restores previous ID; audit log has entries.

**TST-ARCH-004 — UI Cache Toggle**  
**E:** Admin toggles “Disable cache now”.  
**X:** Response headers reflect no-store/low TTL; subsequent request differs.

### Phase 1 — Ingestion
**TST-ING-001 (Pass A)**  
**E:** PDF with valid TOC.  
**X:** `passA.json` contains ≥1 term with page range & section title.

**TST-ING-002 (Pass B)**  
**E:** PDF >25MB.  
**X:** Sub‑files manifest with contiguous non‑overlapping page ranges.

**TST-ING-003 (Pass C)**  
**E:** Source PDF accessible.  
**X:** ≥95% para coverage; tables/lists flagged.  
```python
def test_unstructured_extraction(artifact_dir):
    chunks = load_chunks(artifact_dir/"passC.json")
    assert coverage(chunks) >= 0.95
```

**TST-ING-004 (Pass D)**  
**E:** passC.json exists.  
**X:** embeddings present, index count == chunk count; search latency P95 ≤ target.

**TST-ING-005 (Pass E)**  
**E:** dictionary + chunks available.  
**X:** graph nodes/edges counts > thresholds; sample multi‑hop returns path.  
```python
def test_graph_compile(graph):
    assert graph.node_count > 100
    assert has_path(graph, "Feats:Metamagic", "Spellcasting:Concentration")
```

**TST-ING-006 (Pass F)**  
**E:** Prior passes completed.  
**X:** Manifest reports all passes done; duplicates pruned (< threshold); checksums present.

### Phase 2 — RAG
**TST-RAG-001 — Answer with Provenance**  
**E:** Index populated.  
**X:** Response includes answer + 3 chunk citations with page/section and model badge.

**TST-RAG-002 — Orchestrator Routing**  
**E:** Policy JSON configured.  
**X:** Simple prompts bypass graph; complex prompts show `route=graphwalk` in trace.

### Phase 3 — Workflows
**TST-WF-001 — Character Creation**  
**E:** Workflow graph loaded.  
**X:** Step navigation, validation errors surfaced, final summary exported.  
```python
def test_char_creation_workflow(flow_client):
    s = flow_client.start("character_creation")
    s = flow_client.next(s, {"race":"Elf"})
    assert "invalid" not in s.messages
```

**TST-WF-002 — Graphwalk Trace**  
**E:** Graph present; complex prompt.  
**X:** `reasoning_trace` included; answer correctness ≥ benchmark.

### Phase 4 — Admin
**TST-ADM-001 — Status Dashboard**  
**E:** Services running.  
**X:** Cards show health & build; clicking opens logs.

**TST-ADM-002 — Ingestion Console**  
**E:** Job started.  
**X:** Live logs stream; artifacts downloadable.

**TST-ADM-003 — Dictionary Manager**  
**E:** Term exists.  
**X:** Edit saved with version; rollback restores prior version.

**TST-ADM-004 — Tests & Bug Bundles**  
**E:** Regression suite executed.  
**X:** Failures list diffs; “Create Bug” prefilled with reproducer.

**TST-ADM-005 — Ticketing & Feedback Review**  
**E:** Feedback submitted from UI.  
**X:** Ticket form enforces template; filter by status/type; triage buttons work (Feature | Bug | Close).

### Phase 5 — User UI
**TST-UI-001 — Enter/Stop**  
**E:** Query typed.  
**X:** Enter submits (Shift+Enter = newline); Stop cancels and tags response as stopped.

**TST-UI-003 — Feedback Dialog**  
**E:** Response rendered.  
**X:** 👍/👎 opens dialog; sending stores record with session/query hash; appears in Admin.

### Phase 6 — Testing/Feedback
**TST-TEST-001 — 👍→Regression**  
**E:** Feedback tagged “convert to regression”.  
**X:** New test created with input/expected; visible in Admin Tests.

**TST-TEST-002 — 👎→Bug Bundle**  
**E:** Feedback tagged “create bug”.  
**X:** Bug repo file created with artifacts & traces; ticket opened/linked.

### Phase 7 — Governance
**TST-REQ-001 — Immutable Requirements JSON**  
**E:** PR updates requirements JSON.  
**X:** Schema check passes; version increments; audit entry recorded.

**TST-REQ-002 — Feature Approval**  
**E:** New FR submitted.  
**X:** Requires approval to deploy; Admin UI shows approver & rationale.

### Security
**TST-SEC-401 — JWT**  
**E:** User table seeded; RS256 keys present.  
**X:** Login returns JWT (role claim); admin endpoint 200 with admin token, 403 otherwise.  
```python
def test_jwt_admin(client, admin_jwt, user_jwt):
    assert client.get("/admin/status", headers={"Authorization":f"Bearer {admin_jwt}"}).status_code == 200
    assert client.get("/admin/status", headers={"Authorization":f"Bearer {user_jwt}"}).status_code in (401,403)
```

**TST-SEC-402 — CORS**  
**E:** Env config set (no wildcards).  
**X:** Allowed origins succeed; disallowed origins get 403; prod enforces HTTPS origins only.

**TST-SEC-403 — TLS**  
**E:** TLS configured.  
**X:** HTTP→HTTPS redirects; security headers present; weak ciphers rejected.

**TST-SEC-406 — Rate Limiting**  
**E:** Redis reachable.  
**X:** Exceed category limits → 429 + headers; penalties applied; admin bypass.  
```python
def test_rate_limit_auth(client):
    for _ in range(6): client.post("/auth/login", json={"u":"x","p":"y"})
    r = client.post("/auth/login", json={"u":"x","p":"y"})
    assert r.status_code == 429
    assert "X-RateLimit-Reset" in r.headers
```

### Performance
**TST-PERF-404 — Redis Cache/Session/Compaction**  
**E:** Redis configured; long conversation.  
**X:** Compaction triggers at threshold; UI bar updates; latency improves vs no‑cache baseline.

**TST-PERF-405 — Async DB**  
**E:** Async service enabled.  
**X:** Concurrency ↑3×; memory stable; no resource leaks after 1h soak.

### Architecture/Config
**TST-ARCH-501 — Orchestrator Unification**  
**E:** UI calls orchestrator only.  
**X:** No duplicate pipelines in UI apps; results match baseline.

**TST-ARCH-602 — Decouple UI**  
**E:** Modules refactored.  
**X:** Feature parity; smaller cyclomatic complexity; module tests pass.

**TST-CONFIG-601 — Centralized Config**  
**E:** Invalid config supplied.  
**X:** Startup fails with actionable error; secrets not logged.

**TST-DB-001 — Local DB**  
**E:** DB migrated.  
**X:** CRUD/RBAC pass; migrations up/down clean; referential integrity enforced.

### Bug Fix Validations (tie tests back to BUG‑001..018)
- **TST-BUG-001** OAuth redirect → correct target after login (E: button click; X: redirect URL exact).  
- **TST-BUG-002** remove mock responses (E: feature flag off; X: API returns real indexed data).  
- **TST-BUG-003** auth failures show precise errors; JWT success path works.  
- **TST-BUG-004** prod has no wildcard CORS.  
- **TST-BUG-005** reasoner step invoked when policy says multi‑hop.  
- **TST-BUG-006** single RAG pipeline path used.  
- **TST-BUG-007** UI module boundaries enforced (lint rule, import graph).  
- **TST-BUG-008** runtime loads graph artifacts.  
- **TST-BUG-009** “Murderous Command” links to rules; retrieval succeeds.  
- **TST-BUG-010** Phase 0/1 gaps closed (composite checks).  
- **TST-BUG-011** regression suite stable (no flakiness > threshold).  
- **TST-BUG-012** GraphStore.neighbors expands as expected (unit + integration).  
- **TST-BUG-013** TLS+rate limit enforced in PROD.  
- **TST-BUG-014** persona pipeline encodings correct; API contracts honored.  
- **TST-BUG-015** Phase 7 contracts locked and validated.  
- **TST-BUG-016** non‑Phase7 tests green.  
- **TST-BUG-017** SSL verification on by default; DEV can opt‑out with explicit flag; PROD blocks.  
- **TST-BUG-018** Pass B JSON validation, race‑free threading, safe upserts.

---

## Section 4: Admin UI Spec (Expanded)
- **Ticketing System:** Create/view/update; **type** (Bug/Feature), **status** (Open/Closed), **filter**; body uses a standard template (ID, title, repro, env, logs, artifacts, severity/priority).  
- **Feedback Review:** Stream of UI feedback; actions: **Feature | Bug | Close**; admin notes box; one‑click convert to ticket/regression.  
- **Tests Dashboard:** Suites by env, last run, failures, diff viewer, approve/disable toggles.  
- **System Status:** Env tiles, build IDs, service health, error rates; link to logs.  
- **Ingestion Console:** Start/stop jobs, tail logs (last 20), artifact browser & download.  
- **Dictionary Manager:** Search/edit/version/rollback per env; audit entries.

---

## Section 5: User UI Spec (Expanded)
- **Editor:** Enter submits; Shift+Enter newline; Stop cancels with label.  
- **Response Footer:** 👍/👎 → dialog (tags: “accuracy”, “citation”, “latency”, “UI”, “other”; notes; include retrieved chunks?).  
- **Latency/Model Badge:** Visible on every answer.  
- **Memory Modes:** session/user/party (party future flag).  
- **Theme:** Retro terminal / LCARS; accessible contrast; keyboard shortcuts.

---

## Section 6: Automation & Review
- All tests runnable headless (PyTest + Playwright + Locust, etc.).  
- CI gates: unit → integration → security → performance; failure blocks promote.  
- Admin review page to **approve** test additions from 👍 and to **open bugs** from 👎.  
- Exportable **JUnit/Allure** results attached to tickets.

---

## Section 7: Governance & Traceability
- Requirements JSON schema; versioning; PR approvals; audit.  
- Feature approval workflow; mapping to tests & environments.  
- **Traceability Matrix** (see separate file `Requirements-Full-Traceability.md`).

---
