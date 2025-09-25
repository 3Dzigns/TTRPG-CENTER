# TTRPG Center — Engineering Coding Standards (Source of Truth)
**Version:** 1.0 • **Scope:** All repos/services in the TTRPG Center stack (ingestion, orchestrator, Admin UI, User UI, test harness, infra scripts).  
**Audience:** All contributors (devs, SRE, QA, docs).  
**Goals:** Consistency, readability, maintainability, testability, and security. These standards align with our MVP v2 requirements, phase roadmap, and CI/test architecture.

---

## 1) Repo & Directory Structure

> Enforce environment isolation and predictable locations for code, configs, data, logs, and artifacts.

```
/ (repo root)
  env/
    dev/{code,config,data,logs,artifacts,cache,uploads,ssl}
    test/{code,config,data,logs,artifacts,cache,uploads,ssl}
    prod/{code,config,data,logs,artifacts,cache,uploads,ssl}
  src_common/                   # Shared Python libs (no env‑specific state)
  services/
    ingest/                     # Pass 0→G pipeline, tools adapters
    orchestrator/               # Classifier, policy, retriever, router, prompts
    admin_api/                  # Admin API (artifacts, jobs, dictionary, HGRN)
    user_api/                   # /ask, /plan, /run, session memory
  web/
    admin-ui/                   # React/TS Admin app
    user-ui/                    # Retro/LCARS-themed User app
  tests/
    unit/                       # Pure unit tests
    functional/                 # API/UI functional & integration
    regression/                 # Golden snapshots, eval sets
    security/                   # SAST/DAST harness tests
    perf/                       # k6/Locust
  config/
    policies.yaml               # retrieval/workflow/prompt flags
    retrieval_policies.yaml     # policy engine inputs
    prompts/                    # prompt templates by intent/domain
    flags.yaml                  # feature flags/canaries
  scripts/                      # init-environments, preflight, promote/rollback
  .github/workflows/            # CI (PR gates, nightly regression)
```

**Ports:** dev 8000, test 8181, prod 8282 (configure in `env/*/config/ports.json`).  
**Rule:** All environment-specific code, data, and secrets reside under `env/<name>` (including `code`, `config`, `data`, `logs`, `artifacts`, `cache`, `uploads`, and `ssl`). No cross-env reads/writes.

---

## 2) Language Standards

### 2.1 Python (services, pipelines, tooling)
- **Version:** 3.12+ (pin in `pyproject.toml`).
- **Formatting & Lint:** Black (88 col), Ruff, isort. Enforced in CI.
- **Typing:** `from __future__ import annotations`; **mypy** required on changed code (no `Any` leaks in public APIs).
- **Docstrings:** Google style. Every public module/class/function has a docstring with Args/Returns/Raises.
- **Imports:** standard → third-party → local, separated by one blank line.
- **Functions/Methods:**
  - **Max length:** _soft_ 50 lines (prefer 20–40). Exceeding requires justification and unit tests.
  - **Cyclomatic complexity:** ≤ 10 (Ruff `C901`), or refactor.
  - **Parameters:** ≤ 6. Use dataclasses/TypedDicts for complex params.
  - **Return early** over deep nesting; pure functions when feasible.
- **Classes:** Prefer dataclasses for value objects; keep methods cohesive.
- **Errors:** Raise specific exceptions; never swallow (`except Exception: pass`). Log and re‑raise with context.
- **Logging:** Use structured JSON logs via shared helper; include `env`, `service`, `trace_id`.
- **I/O & Paths:** Always relative to the **env root**; never hardcode absolute paths.
- **Concurrency:** Use `async`/`await` for I/O bound services; bound parallelism for CPU/OCR stages.
- **Security:** No secrets in code. Read from env or secret stores. Validate and sanitize all external inputs.
- **Testing:** pytest for all modules; fast unit tests co‑located under `tests/unit`.

**Python naming:**
- Modules/files: `snake_case.py` (e.g., `manifest_writer.py`).
- Packages/dirs: `snake_case` (e.g., `src_common`).
- Classes: `PascalCase` (`IngestionJob`).  
- Functions/vars: `snake_case` (`build_graph`, `parent_id`).
- Constants: `UPPER_SNAKE` (`DEFAULT_TOP_K = 8`).  
- Private: prefix `_name` if truly internal.

### 2.2 TypeScript/JavaScript (Admin UI, User UI)
- **Version:** TypeScript latest stable.
- **Framework:** React + Vite; shadcn/ui when applicable; Tailwind for styles.
- **Formatting & Lint:** Prettier + ESLint (typescript-eslint). Enforced in CI.
- **State:** Prefer React Query/Zustand for server/cache state; avoid ad‑hoc globals.
- **Components:** Small, pure, typed. Avoid prop drilling > 3 levels (use context/hooks).
- **HTTP:** Typed API clients; never inline fetches in component bodies for complex flows.
- **Security:** Escape/sanitize untrusted HTML/markdown. Use CSP and `rel="noopener"` on external links.
- **Testing:** Vitest/Jest + Playwright for E2E. Components must have snapshot + accessibility checks.

**TS/JS naming:**
- Files: `kebab-case.tsx` (components), `snake_case.ts` (utility modules acceptable; prefer kebab).
- Components: `PascalCase` (default export when single component per file).
- Hooks: `useThing`.
- Types/Interfaces: `PascalCase` (`UserPrefs`), generics `T`, `K`, `V` with words when helpful (`TResult`).
- Enums: `PascalCase` members `UPPER_SNAKE` or `PascalCase` consistently.

### 2.3 Shell/PowerShell
- Scripts must be **idempotent** and **safe** to re‑run. Use `set -euo pipefail` (bash) and strict param validation (PowerShell).

---

## 3) Architectural Standards

- **Environment Isolation:** All services honor `TARGET_ENV` and read `BASE_URL`, env‑scoped secrets, and env‑scoped storage paths.
- **Health & Observability:** Every service exposes `/healthz` and logs in structured JSON. Use OpenTelemetry spans for classify→plan→retrieve→compose and ingestion passes.
- **Artifacts & Manifests:** Ingestion writes `manifest.json`, pass outputs, and checksums under `env/{env}/artifacts/{job_id}/`.
- **Cache Policy:** DEV = `no-store`, TEST = ≤5s, PROD = configurable; user feedback API must bypass cache.
- **Admin Test Console:** Admin UI can launch Unit/Functional/Security/Regression/Perf test runs against any environment and stream results.

---

## 4) API & Schema Conventions

- **HTTP JSON:** `application/json` bodies; snake_case keys in internal services; stable public schemas versioned (`v1`).
- **Error envelope:** `{"error": {"code": "X_Y_Z", "message": "...", "trace_id": "..."}}` with appropriate HTTP status.
- **Pagination:** cursor-based: `?cursor=<opaque>&limit=50` → `{items:[], next_cursor:null}`.
- **Idempotency:** Any POST that causes side effects should accept `Idempotency-Key`.
- **Security headers:** CORS allowlists per env; HSTS in TEST/PROD; rate-limit headers for public endpoints.

---

## 5) Code Layout & File Organization

**Python package layout (example):**
```
services/orchestrator/
  __init__.py
  classifier.py           # US-201
  policy.py               # US-202
  router.py               # US-203
  prompts.py              # US-204
  retrieve.py             # US-205
  answer.py               # US-206
  llm.py                  # adapters
  rerank.py               # mmr/sbert
  api.py                  # FastAPI surface (/ask)
  types.py                # TypedDicts, pydantic models
```

**UI layout (example):**
```
web/admin-ui/src/
  app/
  components/
  pages/
  hooks/
  lib/
  test/
```

**Tests layout (required):**
```
tests/unit/...          # fast, isolated
tests/functional/...    # API & UI flows; real tools where specified
tests/regression/...    # golden snapshots & eval sets
tests/security/...      # injection, authz, rate limit, secrets
tests/perf/...          # k6/Locust scripts
```

---

## 6) Function & Class Size Limits

- **Functions:** Soft cap 50 lines; hard cap 80 lines. Exceeding code must be split or justified in PR description.  
- **Classes:** ≤ 400 lines/file recommended; split by responsibility (SRP).  
- **Cyclomatic complexity:** ≤ 10 per function (Ruff).  
- **Nesting depth:** ≤ 3. Prefer guard clauses and early returns.  
- **Visibility:** Keep helpers private (`_helper`) unless used by multiple modules.

---

## 7) Documentation & Comments

- **README per service** (purpose, setup, run, tests).  
- **Docstrings on all public APIs** (Args/Returns/Raises, examples).  
- **Comments explain _why_, not _what_**; avoid outdated blocks.  
- **Architecture docs** in `/docs/` or service `README`; keep diagrams (draw.io/mermaid) under version control.

---

## 8) Security, Secrets & Compliance

- **Secrets:** Only from env or secret manager. Never commit. `.env` files belong under `env/*/config/` and are gitignored.
- **PII/Secrets redaction:** Log helpers must scrub common patterns (`sk-`, `AZURE_`, tokens).  
- **Dependency hygiene:** Pin versions; use `pip-audit`/`npm audit` in CI.  
- **Auth/RBAC:** Implement in Phase 6; until then, block privileged endpoints or require local dev auth.  
- **Data separation:** Never mix tenant or environment artifacts; include `{env, tenant}` tags in logs/artifacts.

---

## 9) Testing Standards (All Code Must Be Testable)

- **Unit tests** for every non-trivial function/public method. **Minimum coverage:** 80% per changed lines; critical modules ≥ 90%.
- **Functional tests** run **outside** the stack against env URLs.
- **Regression**: Golden snapshots for ingestion outputs, retrieval plans, ranked chunk IDs, and workflows.
- **Security**: SAST (Semgrep, Bandit) + DAST (ZAP baseline/full) and image scans (Trivy) as gates.
- **Performance**: k6 smoke scripts for critical endpoints (p95 targets documented).

**Naming & markers:**
- Files: `test_<module>.py`; tests named `test_<behavior>_<expected>()`.
- Use markers `@pytest.mark.regression`, `@pytest.mark.security` to select suites.

---

## 10) Git, Branching & Reviews

- **Branching:** `main` (protected), feature branches `feat/<slug>`, fixes `fix/<slug>`, experiments `exp/<slug>`.
- **Commits:** Conventional Commits (e.g., `feat(ingest): add Pass B lineage`).
- **PRs:** Template requires: problem, solution, screenshots, risk, tests, checkboxes for gates.
- **Reviews:** At least one senior reviewer. CI **must be green** (unit/functional/security) before merge.
- **Changelogs:** Auto-generated from Conventional Commits.

---

## 11) Error Handling & Logging

- Use structured logs with **stable schema** (`ts, level, msg, env, service, trace_id`).  
- **No bare excepts**; log context with `exc_info=True`. Map known errors to clear HTTP codes.  
- **User-facing errors** return safe messages; internal details only in logs.  
- **Tracing:** pass `trace_id` through request context and logs; include elapsed time per stage.

---

## 12) Configuration & Flags

- **Per-env config** under `env/<env>/config/` with `.env` and JSON/YAML files.  
- **Hot reload** for policy/prompt files where safe.  
- **Feature flags/canaries** in `config/flags.yaml`; never toggle via code branches.

---

## 13) Data & Artifacts

- **Naming:** Use stable identifiers `{doc_id, part_id, section_id, page}` and preserve lineage in all pass outputs and citations.
- **Manifests:** Record tool versions, checksums, pass statuses; block downstream on invariant failure.
- **Retention:** TTLs per environment; Admin UI includes bulk cleanup actions.

---

## 14) .gitignore (Repo Hygiene & Security)

```
# Environments (never commit secrets/artifacts)
env/*/config/.env
env/*/data/
env/*/logs/
env/*/artifacts/
env/*/cache/
env/*/uploads/
env/*/code/
env/*/ssl/

# Python
__pycache__/
*.pyc
.venv/
.venv*/
pip-wheel-metadata/
.mypy_cache/
.pytype/
.pytest_cache/
.coverage
htmlcov/

# Node/TS
node_modules/
dist/
.build/
*.log

# OS/editor
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp

# Reports & local outputs
artifacts/
reports/
coverage/
*.junit.xml

# Docker & containers
docker/*.local.*
*.bak
```

> Consider a `.dockerignore` mirroring the above to keep images lean (exclude `env/*/data`, `tests/`, `node_modules/`, local artifacts).

---

## 15) Example Module Skeletons

**Python service module:**
```python
\"\"\"Classifier service.
Classifies a query into {intent, domain, complexity} for retrieval planning.
\"\"\"
from __future__ import annotations
from typing import TypedDict, Literal

class Classification(TypedDict):
    intent: Literal['fact_lookup','procedural_howto','creative_write','code_help','summarize','multi_hop_reasoning']
    domain: Literal['ttrpg_rules','ttrpg_lore','admin','system','unknown']
    complexity: Literal['low','medium','high']
    needs_tools: bool
    confidence: float

def classify_query(q: str) -> Classification:
    \"\"\"Heuristic classifier with optional LLM fallback.
    Args:
      q: Raw user query.
    Returns:
      Classification dict with confidence in [0,1].
    \"\"\"
    # ...
    raise NotImplementedError
```

**React component file header:**
```tsx
/**
 * Admin Test Console – run suites against selected environment.
 * Responsibilities:
 *  - list suites (unit/functional/security/regression/perf)
 *  - trigger runs via tests-runner API
 *  - stream logs & link artifacts
 */
export default function TestConsole() {
  // ...
}
```

---

## 16) Deviation Process
If you must deviate (e.g., long function for performance, unusual directory) you **must**:
1) Document the reason in code,  
2) Propose an ADR (Architecture Decision Record) in `/docs/adr/NNN-title.md`, and  
3) Get reviewer approval in the PR.

---

## 17) Enforcement
- CI runs format/lint/type/test gates on PRs; failure blocks merge.
- Admin Test Console can run suites by environment and publish artifacts.
- Periodic style audits (pre‑commit hooks recommended).

---

**This standard is living**: propose updates via PR with an ADR. Keep it boring, typed, tested, and secure.



## Security & Observability

- All FastAPI services MUST call `src_common.security.bootstrap_app_security` immediately after app construction to enable JWT validation, security headers, rate limiting, and OpenTelemetry toggles.
- Use `record_audit_event` for any endpoint that mutates state (ingest uploads, dictionary/HGRN operations, test runner commands) so audit logs land in `env/<env>/logs/audit/`.
- Use `require_roles()` dependencies to guard admin-only endpoints. Admin API, ingest, test runner, and orchestrator admin routes are required to enforce `require_roles("admin")`.
- Retrieval code MUST respect `ALLOWED_SOURCES` configuration. Add new sources via environment `.env` (`ALLOWED_SOURCES` comma list) or per-env defaults; never bypass source gating in production.
- When OpenTelemetry is enabled (flag `observability.opentelemetry`), services should export traces to the OTLP endpoint declared in `.env`. Do not disable tracing in prod without SRE approval.
