# TTRPG Center — MVP Requirements (Version 2, Phased)

This document defines the phased requirements for the MVP build of the TTRPG Center system, targeting a functional **Hybrid RAG + Graph system** with an admin ingestion process and a user retrieval process. Authentication, roles, and source gating are deferred to the final phase to validate function first.

---

## Phase 0 — Environment Isolation & Foundations
**Goal:** Establish clean, isolated DEV/TEST/PROD environments with Docker and CI.

- **ENV-001:** Each environment runs in its own Docker Compose stack with distinct ports (8000/8181/8282) and isolated volumes under `/env/{env}/{code,config,data,artifacts,logs}`.
- **ENV-002:** Immutable builds; promotion = retag/compose update; rollback = previous tag.
- **ENV-003:** Structured JSON logs; baseline `/healthz` endpoint.
- **ENV-004:** CI runs Unit + Functional tests per PR; nightly Regression on `main`.

**DoD:** `docker compose up` boots all envs; `/healthz` OK; logs scoped per env; CI green.

---

## Phase 1 — Ingestion Pipeline (Pass 0 → G, 10 MB split)
**Goal:** Produce stable artifacts, dictionary, and graph from TTRPG PDFs.

### Pass 0 — Preflight & De-dup
- Compute `file_sha`, page count; short-circuit if identical to prior.

### Pass A — TOC & Dictionary Seed
- Extract sections/page ranges; assign stable `section_id`.
- Seed dictionary with canonical entries (system, edition, section names, rule terms).

### Pass B — Fast Split (≤10 MB parts)
- If >10 MB, split PDF into section-based or fixed-page windows (scan-safe).
- Emit `parts.jsonl` with lineage: `{doc_id, parent_id, part_id, section_id, page_range, file_path}`.

### Pass C — Extraction (Unstructured.io, containerized)
- OCR for scanned PDFs; emit `chunks.jsonl` with `{doc_id, part_id, section_id, page, block_type, text}`.
- Emit dictionary proposals as `dict_delta.passC.json`.

### Pass D — Normalize + Embeddings (Haystack)
- Normalize, embed, upsert to vector store; emit `dict_delta.passD.json`.

### Pass E — Graph Compile (LlamaIndex)
- Build graph `{nodes, edges}` from chunks/dictionary; emit `graph.json` + `dict_delta.passE.json`.

### Pass F — Validation & Manifest
- Validate referential integrity; merge deltas to `dict_delta.all.json`; emit `manifest.json` with checksums/tool versions.

### Pass G — HGRN Consistency Check
- Detect alias drift, orphan nodes, broken `part_of`; emit `hgrn.report.json`, `dict_delta.passG.json`, `hgrn.actions.json`.

**DoD:** Ingest two fixture PDFs (scanned + normal). All artifacts present; dictionary seeded in A, deltas proposed in C/D/E/G; split threshold = 10 MB enforced.

---

## Phase 2 — Retrieval Orchestrator (Hybrid RAG + Graph)
**Goal:** Answer queries with provenance using hybrid retrieval.

- **RET-001:** Query classifier → `{intent, domain, complexity}`.
- **RET-002:** Policy engine maps classification → retrieval plan (vector, metadata, optional graphwalk, rerank, self-consistency).
- **RET-003:** Hybrid retriever executes plan; dedup + token budget.
- **RET-004:** Answer composer generates text with **citations [Book §Section p.Page]**.
- **RET-005:** Observability trace (classify → plan → retrieve → compose).

**DoD:** 20 canonical queries run; answers include ≥2 citations; graph-assisted plans outperform vector-only baseline.

---

## Phase 3 — Admin UI (CRUD + Bulk Cleanup)
**Goal:** Operability and artifact management.

- **ADM-001:** Data explorer across Postgres/Mongo/Cassandra with env scoping.
- **ADM-002:** CRUD for dictionary entries, chunks, graph nodes/edges, jobs, artifacts, logs.
- **ADM-003:** Bulk actions (delete logs older than N days; delete all chunks for DOC_ID; revert dictionary proposals).
- **ADM-004:** Artifact browser to download pass outputs.
- **ADM-005:** HGRN review screen to accept/reject recommendations.

**DoD:** Admin bulk deletes logs; dictionary revision increments when HGRN proposals accepted.

---

## Phase 4 — Observability & Feedback
**Goal:** Visibility into ingestion/retrieval quality and user-driven feedback.

- **OBS-001:** OpenTelemetry spans across all pipeline steps; structured JSON logs.
- **OBS-002:** Dashboards show ingestion progress, retrieval traces, errors, costs.
- **OBS-003:** 👍 auto-creates regression tests; 👎 creates bug bundle with logs/artifacts.
- **OBS-004:** CI gates: unit + functional on PR, regression nightly; fail on red.

**DoD:** CI gates block bad commits; dashboard shows traces; feedback visible within seconds.

---

## Phase 5 — User UI (Query & Provenance)
**Goal:** End-user interface for immersive querying.

- **UI-001:** Retro/LCARS-inspired theme; query box and results panel.
- **UI-002:** Answer view includes provenance, model badge, latency.
- **UI-003:** Session memory (per tab); user memory (persisted preferences/history).
- **UI-004:** Cache-respecting retest: DEV=no-store, TEST=≤5s, PROD=configurable.

**DoD:** User queries show themed answers with citations; session + user memory working; cache policies enforced.

---

## Phase 6 — Authentication, RBAC & Source Gating
**Goal:** Enforce access control after validating function.

- **SEC-001:** JWT auth (RS256); roles = {admin, user}.
- **SEC-002:** Users have `allowed_sources`; retrieval filters enforce this pre-query.
- **SEC-003:** Admin RBAC: only admins can promote dictionary canonicals, modify graph schema, bulk delete.
- **SEC-004:** CORS scoped per env; TLS/HSTS in TEST/PROD; Redis rate limiting.
- **SEC-005:** Audit log of logins, role changes, dictionary promotions, bulk deletes.

**DoD:** Two users with different source scopes get different results; audit trails captured; all security tests green.

---

## Cross-Cutting Contracts & Limits
- **File split threshold:** PDFs >10 MB trigger Pass B splitting; parts ≤10 MB each.
- **Lineage:** All artifacts carry `{doc_id, part_id, section_id}` into chunks, graph nodes, citations.
- **Dictionary:** Pass A writes authoritative canonicals; C/D/E/G emit proposal deltas; Admin approves promotions in Phase 3.
- **Containerization:** Unstructured.io, Haystack, LlamaIndex run in containers with tunable concurrency.
- **Retention:** Logs/artifacts follow per-env TTL; bulk cleanup available in Admin UI.

---

# Definition of Done (MVP v2)
- Ingestion: full Pass 0→G with manifests, 10 MB split, dictionary authority, and HGRN check.
- Retrieval: hybrid RAG + graphwalk functional, answers with citations.
- Admin: CRUD + bulk cleanup; HGRN review; artifact browser.
- User: Retro UI with provenance, session/user memory, cache policy.
- Security: JWT, RBAC, source gating, TLS, rate-limit, audit logging (Phase 6).
- Observability: Structured logs, OTel spans, dashboards, feedback loops, CI gates.
- Traceability: requirements ↔ user stories ↔ test cases; all tests green in CI.

