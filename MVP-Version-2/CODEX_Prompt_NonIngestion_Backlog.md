# CODEX Execution Prompt — TTRPG Center (Non‑Ingestion Backlog)
**Date:** 2025-10-02 15:07:41
**Owner:** AI Dev (CODEX)
**Repo Context:** Multi‑env (DEV/TEST/PROD) with Phase‑gated MVP‑Version‑2. Ingestion pipeline (Pass 0/A–G) is **owned by Claude** and **out of scope** here.

---

## 🔒 Scope & Guardrails
- **Do NOT modify** anything under `src_common/pass_*`, `services/ingest_*`, or any code that implements Pass 0/A–G or their artifacts/manifests. If a change is required in those areas, **open a PR description and stop**.
- You **may** add non‑breaking hooks (telemetry, interfaces) that the ingestion team can consume **later**, but leave them disabled by default.
- Everything else in this prompt is **in scope**.

---

## 🎯 Program Objective
Raise repo health from ~49.5% to ≥75% by fixing cross‑cutting platform gaps **outside** ingestion:
- Phase 0: env/ports parity + immutable builds
- Phase 2: retrieval policy hardening & provenance
- Phase 3: admin API backed stores & CRUD operability
- Phase 4: tracing/telemetry & feedback plumbing
- Phase 5: UI provenance block polish
- Phase 6: security (RS256/RBAC, source gating, TLS/CORS/rate limit)
- Phase 7: feature workflow polish

Where possible, implement unit/functional/security tests and CI gates as part of each change.

---

## 🧭 Acceptance Philosophy
Each task includes: **Goal → Acceptance Criteria → Tests → Artifacts → DoD**. If an acceptance cannot be proven by code/tests, the task isn’t done.

---

## 📌 Repo Clues (from the latest assessment)
- **Port drift & builds:** `env/test/docker-compose.yml` (test ingress uses 8182/8183), `env/dev/docker-compose.yml` uses `build:` instead of pinned images; contract says **8000/8181/8282**.  
- **Admin API stubs:** `services/admin_api/api.py` stores data in in‑memory dicts (blocks Phase 3).  
- **Security:** `src_common/jwt_service.py` defaults to **HS256**; Phase‑6 requires **RS256** + per‑user source gating.  
- **Observability:** OTel spans missing around classify→plan→retrieve; dashboards/alerts absent.  
- **UI:** Provenance block exists but needs clearer source display & session trace.  
(If any path differs in your checkout, search equivalents and proceed.)

---

## 🚀 Workstream Backlog (execute in order)

### 1) Align Test Compose Ports to Contract (Phase 0)
**Goal:** Test stack exposes 8181, matching Phase‑0 contract.
**Do:**
- Update `env/test/docker-compose.yml` so public ingress listens on **8181**. Preserve internal service isolation.
- Add `env/test/README.md` describing port map and health endpoints.
**Acceptance:**
- `docker compose -f env/test/docker-compose.yml config` shows 8181 for ingress.
- CI smoke hits `/healthz` on 8181 and passes.
**Tests:**
- Add a targeted smoke in CI (curl 127.0.0.1:8181/healthz in container network or service name).

### 2) Immutable Builds via Registry Images (Phase 0)
**Goal:** Replace `build:` with `image:` tags (digest‑pinned) across env compose files.
**Do:**
- Introduce CI stage that builds/pushes versioned images (e.g., `ghcr.io/<org>/<svc>:YYYYMMDD.sha`), outputs digests.
- Replace `env/*/docker-compose.yml` `build:` blocks with `image:` + `@sha256:…`.
- Document promotion/rollback.
**Acceptance:**
- `docker compose … pull` works with no build step.
- Rollback doc demonstrates switching to previous digest.
**Tests:**
- CI job asserts that `docker compose -f env/dev/docker-compose.yml config` contains no `build:` keys.

### 3) RS256 JWT + Per‑User Allowed Sources (Phase 6)
**Goal:** Cryptographic separation + data gating at retrieval layer.
**Do:**
- Update `src_common/jwt_service.py` to **RS256**: load `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` from env/vault (PEM). Rotateable.
- Embed `allowed_sources` (list of source IDs/scopes) in user claims.
- In `services/orchestrator/retrieve.py` (or retrieval facade), **filter** by `allowed_sources` when present; default‑deny if claim exists but empty.
- Add `.env.sample` variables & docs for key generation.
**Acceptance:**
- Tokens signed with RS256 verify with public key.
- Retrieval returns different result sets for different `allowed_sources`.
**Tests:**
- Unit: token verify; claim parsing; filter guard.
- Security: negative tests for algorithm downgrade (“alg: none”), missing audience, and empty scope.

### 4) Admin API Backed Stores & Bulk Ops (Phase 3)
**Goal:** Replace in‑memory façade with real DBs and add ops endpoints.
**Do:**
- Wire Admin API to **Mongo** (dictionary/documents), **Cassandra** (vectors), **Postgres**/**SQLite** (metadata/logs)—minimal adapters are fine.
- Implement CRUD with **env scoping** (dev/test/prod namespaces).
- Add **bulk cleanup** endpoint (delete logs/artifacts older than N days, env‑scoped).
**Acceptance:**
- CRUD persists/retrieves from actual stores; responses include env namespace.
- Bulk cleanup deletes ≥1 old artifact set in tests.
**Tests:**
- Functional tests hitting containerized DBs (compose services).  
- Security tests: role check, tenant/env scoping enforced.

### 5) OpenTelemetry Spans Across Orchestrator (Phase 2/4)
**Goal:** Tracing for classify → plan → retrieve → compose; trace ids back to client.
**Do:**
- Instrument service with OTel SDK; spans per major step; propagate `trace_id` in API responses.
- Add OTLP exporter config (env‑controlled); safe no‑op when disabled.
**Acceptance:**
- When collector is up, traces visible; when disabled, zero overhead errors.
**Tests:**
- Unit: tracer mocked; spans recorded.
- Functional: trace id present and consistent across logs and response.

### 6) Security Hardening: TLS/CORS/Rate Limit/Audit (Phase 6)
**Goal:** Bring transport & API surface to Phase‑6 baseline.
**Do:**
- Centralize CORS policy; default locked to admin/user UIs.
- Add simple token bucket rate limiter per IP/user.
- Ensure TLS termination guidance (nginx/caddy config sample) is documented; if TLS not in app, provide reverse‑proxy sample under `env/`.
- Implement **audit logging** of auth/retrieval events (redacted).
**Acceptance:**
- CORS preflights pass only from approved origins.
- 429s on burst tests.
- Audit log entries appear for login and /ask.
**Tests:**
- Security tests simulate cross‑origin requests and rapid bursts.

### 7) Provenance Display & Session Tracing in User UI (Phase 5)
**Goal:** Clearer source display + trace affordances.
**Do:**
- Enhance `web/user-ui` message bubbles to show: human‑readable citation list (book/section/page) and a small “Trace” chip that copies the `trace_id`.
- Respect cache policy from Phase 0 (DEV no‑store; TEST ≤5s; PROD configurable).
**Acceptance:**
- Users can copy trace id; citations render with stable styling; cache behavior verified by retry after config change.
**Tests:**
- Jest/Playwright tests for rendering and cache header checks.

### 8) Feedback → Tests/Bugs Plumbing (Phase 4/6)
**Goal:** Wire thumbs up/down to storage and CI hooks.
**Do:**
- Implement `/feedback` write path (👍 creates regression fixture, 👎 creates bug bundle JSON under `artifacts/bugs/…`) and ensure **no-store** cache on the POST.
- Add CI job to sweep new 👍 fixtures into regression suite and run them.
**Acceptance:**
- New 👍 appears in test list and runs in next pipeline.
- 👎 bundle visible in Admin UI.
**Tests:**
- Unit/functional for API; regression harness picks up new fixtures.

### 9) CI Quality Gates & Image Promotion Notes (Phase 4/0)
**Goal:** Enforce quality and document the new release flow.
**Do:**
- Add CI step to fail on regression drop (EM/F1/Citation metrics if available) or missing spans.
- Provide `RELEASE_NOTES.md` template and `promote.md` with step‑by‑step image promotion.

---

## 🧪 Verification Commands (put into CI where applicable)
- `docker compose -f env/test/docker-compose.yml config`
- `pytest -q tests/functional/test_admin_api.py`
- `pytest -q tests/security/test_fr_sec_402_cors.py`
- `pytest -q tests/regression/test_observability_logging.py`
- Negative tests for JWT alg‑none & scope filtering

---

## 📦 Deliverables
- PRs grouped by workstream (1 PR per numbered item).
- Updated docs: `env/test/README.md`, security key mgmt guide, observability runbook, promotion/rollback docs.
- Test coverage for added modules.
- Feature flags off by default where appropriate.

---

## ✅ Definition of Done (global)
- All new/changed code has unit + functional + security tests.
- CI green; quality gate rules pass.
- No ingestion code modified (or only guarded hooks, default off).
- Docs updated; demo notes included for reviewers.

---

## 🆘 Escalation
If any task requires changes in the ingestion pipeline, **stop** and open a PR draft that lists the dependency and proposed interface so Claude’s lane can pick it up.
