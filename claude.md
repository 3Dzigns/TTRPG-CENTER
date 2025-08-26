# CLAUDE.md — TTRPG Center / Agentic RAG Platform

You are “Claude Code,” acting as a senior engineer on this repo. Follow these rules exactly.

## 1) Mission & Scope
- Build and maintain an **admin Web UI** and backend for ingesting TTRPG source material into AstraDB; support both **single** and **bulk** uploads.
- Provide **phase-by-phase ingestion status** with live progress and error surfacing.
- Enable **RAG QA** that shows: top 3 chunks, OpenAI answer, Claude answer, and a chooser/heuristic to pick the better answer.
- Honor **environment separation** (Dev/Test/Prod) until explicit promotion.

## 2) Canonical Requirements (always read first)
- `/mnt/data/2025-08-25_MVP_Requirements.json`
- `/mnt/data/README.md`
- `/mnt/data/LAUNCH_GUIDE.md`
- `/mnt/data/API_TESTING.md`
- `/mnt/data/STATUS.md`
- `/mnt/data/documentation.md`
If any instruction in this CLAUDE.md conflicts with those files, **prefer the requirements docs** and propose an update here.

## 3) Environments & Configuration
- Keep **Dev/Test/Prod** configs isolated. No cross-pollination of data or env vars.
- Use `.env.*` files and config loaders. Never hardcode secrets.
- **AstraDB** is the vector/primary store; index chunks + metadata.
- **Redis** may be used for job queues and real-time status caching. Add `redis` to `requirements.txt` if needed, but **only import when used**.

## 4) Ingestion Phases (must expose status)
1. **Upload → temp storage** (show %; file size + ETA).
2. **Chunking** (show % + last 2–3 chunk previews in natural language).
3. **Dictionary/Metadata extraction** (title, publisher, ISBN, system, chapter/section/sub-section; add dynamic tags like `spell/school`, etc.).
4. **Embeddings + Upsert → AstraDB** (batched; retry on failures).
5. **Enrichment** (optional classifiers; record provenance).
6. **Verify & commit** (write summary manifest; mark job complete).

For each phase, publish:
- `status` (queued|running|stalled|error|done), `progress` 0–100, `updated_at`, recent logs, and any **actionable error** details.
- Admin UI subscribes to live updates (e.g., SSE/WebSocket or Redis pub/sub).

## 5) Admin UI Expectations
- Show **separate progress bars per phase** + rolling log tail.
- Allow viewing the evolving **dictionary** in plain natural language (not Markdown).
- Surface **errors and stalls** prominently with remediation hints.
- Provide a **global “Shutdown”** that safely cancels running jobs and releases file locks.

## 6) RAG QA Panel
- For a query, show:
  - **Top 3 chunks** (verbatim excerpts + metadata).
  - **Answer A (OpenAI)** and **Answer B (Claude)**.
  - A **selector/heuristic** that chooses a preferred answer and explains the rationale.
- Log retrieval traces: what was asked, how routed, which chunks returned, scoring.

## 7) Coding Standards & Guardrails
- Prefer **typed Python** (mypy-clean) for services; **FastAPI** for APIs.
- Provide **integration tests** for ingestion, status updates, and RAG query flow.
- Any long-running work goes to a **queue/worker**; API remains non-blocking.
- **Never** run destructive commands without a plan/confirm step.
- Keep PRs small and reference requirement IDs. Include a “What changed / Why / How tested” section.

## 8) Workflow for Any Task
1. **Restate the requirement** in your own words.
2. **Locate the relevant spec** in `/mnt/data/*` and quote the controlling lines/IDs.
3. **Design first**: outline endpoints, data models, status schema, and UI wiring.
4. **Implement in small commits**, each with tests.
5. **Run**: `make dev` (or documented equivalent), then smoke tests.
6. **Record**: update `STATUS.md` with what changed and known gaps.

## 9) Definition of Done (DoD)
- Meets the requirement in the referenced spec.
- Unit + integration tests pass locally.
- Status events visible in Admin UI; error paths demonstrated.
- Docs updated (README/API_TESTING/LAUNCH_GUIDE as applicable).

## 10) Failure & Triage
- On ingest failure: write a **debug bundle** including request, routing path, retrieved chunks, scoring, and model answers for post-mortem (see “failed query file” requirements).
- Never swallow exceptions—emit structured errors and user-action guidance.

## 11) Custom Commands (examples)
Create these under `.claude/commands/`:
- `ingest.md`: “Run the ingestion pipeline on $ARGUMENTS and stream per-phase status to console and Redis.”
- `trace-status.md`: “Show live status for job $ARGUMENTS, including last 20 log lines per phase.”
- `write-tests.md`: “Generate missing tests for modules changed in last commit.”

## 12) Style of Responses
- Use concise bullet points.
- When unsure, **ask targeted questions** and propose a default plan.
- Always include **next steps** and **test instructions**.

## 13) Supplemental Memory & Commands

- Persistent project rules live in `.claude/memory/`
  - `requirements-index.md` → Canonical requirements sources
  - `status-schema.md` → Status event contract
  - `coding-standards.md` → Language/framework/test/DoD
  - `environments.md` → DEV/TEST/PROD separation rules
  - `ingestion-phases.md` → Six ingestion phase contract

- Reusable task prompts live in `.claude/commands/`
  - `ingest.md` → Run ingestion pipeline
  - `trace-status.md` → Monitor ingestion progress
  - `write-tests.md` → Generate/update tests
  - `promote.md` → Promote builds/artifacts between ENVs
  - `rag-eval.md` → Run RAG evaluation datasets
