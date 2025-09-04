# TTRPG Center — Phased Requirements (WebUI-Confirmable)

## Phase 0 — Environments, Builds, and Fast Testing (Caching)

**Goal:** Stand up **isolated environments with their own sub-directories**, immutable builds, and make WebUI testing instant via cache controls.

* **ARCH-001:** DEV, TEST, PROD with fixed ports (8000, 8181, 8282).

  * Each environment must run in its own isolated code space under `/env/dev`, `/env/test`, `/env/prod`.
  * No environment may share binaries, caches, or manifests; promotion occurs only via controlled copy into the next environment’s sub-directory.
* **ARCH-002:** Immutable builds with timestamped IDs and pointer promotion/rollback.
* **ARCH-003:** Scripts (`build.ps1`, `promote.ps1`, `rollback.ps1`) must respect environment sub-directories.
* **ARCH-004 (new): WebUI Cache Controls**

  * Very short TTL (≤5s) or **no-store** headers for dynamic pages.
  * `.env.dev`: default no-store; `.env.test`: ≤5s TTL; `.env.prod`: configurable.
  * Admin UI toggle: “Disable UI cache now.”
  * **Acceptance:** retesting in WebUI reflects new results within seconds, with logs showing which environment directory was used.

---

## Phase 1 — Ingestion Pipeline (unstructured.io → Haystack → LlamaIndex)

**Goal:** Run a three-pass ingestion with live status and dictionary updates, isolated by environment.

* **RAG-001:** Multi-pass ingestion

  1. **Pass A — Parse/Chunk (unstructured.io):** PDF → single-concept chunks, primary metadata.
  2. **Pass B — Enrich (Haystack):** normalize, update dictionary, secondary metadata.
  3. **Pass C — Graph Compile (LlamaIndex):** build/update workflow graphs linking nodes to dictionary.
* **RAG-002:** Metadata accuracy (pages, sections, tables self-contained).
* **RAG-003:** Dynamic dictionary system

  * Stored in AstraDB as part of metadata.
  * Organic growth from ingested content.
  * Admin-editable in WebUI.
* **Artifacts:** Stored under `./artifacts/{ENV}/{JOB_ID}/manifest.json`. Each environment has its own isolated ingestion space.
* **Acceptance:** WebUI → Ingestion Console shows per-phase progress + last 10–20 logs, scoped to the environment directory.

---

## Phase 2 — RAG Retrieval (Basic Queries)

**Goal:** Query against AstraDB chunks with provenance and traces, isolated per environment.

* **UI-001:** Query input with performance metrics (timer, token count, model badge).
* **RAG-VIEW:** Show top 3 chunks, OpenAI and Claude answers, and a heuristic selector.
* **Acceptance:** Results include retrieved chunks with metadata; provenance visible. Queries run only against the environment’s isolated code and data space.

---

## Phase 3 — Graph Workflows

**Goal:** Multi-step guided processes, environment-scoped.

* **WF-001:** Graph workflow engine (nodes/edges, state tracking, dictionary refs).
* **WF-002:** Character creation workflow.
* **WF-003:** Intelligent routing (RAG vs workflow, fallback to OpenAI, source labeling).
* **Acceptance:** “Start Character Creation” in User UI progresses step-by-step with validation. Each workflow run is isolated by environment sub-directory.

---

## Phase 4 — Admin UI

**Goal:** Operational tools, aware of environment isolation.

* **ADM-001:** System Status dashboard (shows DEV/TEST/PROD separately).
* **ADM-002:** Ingestion Console.
* **ADM-003:** Dictionary management (view/edit terms per environment).
* **ADM-004:** Regression tests & bug bundles (scoped to environment).
* **ADM-005 (new): Cache refresh compliance**

  * Admin pages respect Phase 0 cache policy; toggling “disable cache” reflects instantly.
  * Status updates show which environment directory the action applied to.

---

## Phase 5 — User UI

**Goal:** Query and interact in themed UI, isolated per environment.

* **UI-002:** Retro terminal / LCARS-inspired design.
* **UI-003:** Multimodal response area (text now, images later).
* **UI-004:** Memory modes (session, user, future: party).
* **UI-005 (new): Fast retest behavior**

  * Queries respect Phase 0 cache policy.
  * **Acceptance:** retrying a query after a config change shows updated behavior within seconds, scoped to environment sub-directory.

---

## Phase 6 — Testing & Feedback

**Goal:** Automate regression and bug capture, respecting environment isolation.

* **TEST-001:** 👍 creates regression test (environment-specific).
* **TEST-002:** 👎 creates bug bundle (environment-specific).
* **TEST-003:** DEV gates enforce requirements/tests.
* **TEST-004 (new): Feedback bypasses cache**

  * **Acceptance:** submitting 👍/👎 updates Admin UI immediately, in the correct environment directory.

---

## Phase 7 — Requirements & Features

**Goal:** Immutable requirements and controlled feature flow.

* **REQ-001:** Immutable requirements stored as versioned JSON.
* **REQ-002:** Feature request approval workflow.
* **REQ-003:** Schema validation for requirements & requests.
* **Acceptance:** Admin can approve/reject features; requirements visible in System Status; audit trail preserved, isolated by environment code space.