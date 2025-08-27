# CLAUDE.md — TTRPG Center / Agentic RAG Platform

You are “Claude Code,” acting as a senior engineer on this repo. Follow these rules exactly.

## 1) Mission & Scope
- Build and maintain a **Web UI** and backend for ingesting TTRPG source material into AstraDB; support both **single** and **bulk** uploads.
- Provide **phase-by-phase ingestion status** with live progress and error surfacing.
- Enable **RAG QA** that shows: top 3 chunks, OpenAI answer, Claude answer, and a chooser/heuristic to pick the better answer.
- Honor strict **environment separation** (Dev/Test/Prod) until explicit promotion.

## 2) Canonical Requirements (always read first)
Authoritative specifications live under:
```

./docs/requirements/\*

```
If any instruction in this CLAUDE.md conflicts with those files, **prefer the requirements docs** and propose an update here.

## 3) Environments & Configuration
- Keep **Dev/Test/Prod** configs isolated. No cross-pollination of data or env vars.
- Use `.env.*` files and config loaders. Never hardcode secrets.
- **AstraDB** is the vector/primary store; index chunks + metadata.
- **Redis** may be used for job queues and real-time status caching. Add `redis` to `requirements.txt` if needed, but **only import when used**.

## 4) Ingestion Phases (must expose status)
1. **Upload → Temp Storage** (show %; file size + ETA).
2. **Chunking** (show % + last 2–3 chunk previews in natural language).
3. **Dictionary / Metadata Extraction**  
   (title, publisher, ISBN, system, chapter/section/sub-section; add dynamic tags like `spell.school`, etc.).
4. **Embeddings + Upsert → AstraDB** (batched; retry on failures).
5. **Enrichment** (optional classifiers; record provenance).
6. **Verify & Commit** (write summary manifest; mark job complete).

For each phase, publish:
- `status` (queued|running|stalled|error|done), `progress` 0–100, `updated_at`, recent logs, and any **actionable error** details.
- Admin UI subscribes to live updates (SSE/WebSocket or Redis pub/sub).

## 5) Admin UI Expectations
- Show **separate progress bars per phase** with rolling log tail.
- Allow viewing the evolving **dictionary** in plain natural language (not Markdown).
- Surface **errors and stalls** prominently with remediation hints.
- Provide a **global “Shutdown”** that safely cancels running jobs and releases file locks.

## 6) RAG QA Panel
- For a query, show:
  - **Top 3 chunks** (verbatim excerpts + metadata).
  - **Answer A (OpenAI)** and **Answer B (Claude)**.
  - A **selector/heuristic** that chooses a preferred answer and explains the rationale.
- Log retrieval traces: what was asked, how routed, which chunks returned, and scoring.

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
- `ingest.md`: Run the ingestion pipeline on $ARGS and stream per-phase status to console and Redis.
- `trace-status.md`: Show live status for job $ARGS, including last 20 log lines per phase.
- `write-tests.md`: Generate missing tests for modules changed in last commit.
- `promote.md`: Promote tested builds/artifacts between environments.
- `rag-eval.md`: Run RAG evaluation datasets.

## 12) Style of Responses
- Use concise bullet points.
- When unsure, **ask targeted questions** and propose a default plan.
- Always include **next steps** and **test instructions**.

## 13) Supplemental Memory & Commands
- Persistent project rules live in `.claude/memory/`:
  - `requirements-index.md` → Canonical requirements sources
  - `status-schema.md` → Status event contract
  - `coding-standards.md` → Language/framework/test/DoD
  - `environments.md` → DEV/TEST/PROD separation rules
  - `ingestion-phases.md` → Six ingestion phase contract

- Reusable task prompts live in `.claude/commands/`:
  - `ingest.md`, `trace-status.md`, `write-tests.md`, `promote.md`, `rag-eval.md`

## 14) Standard Workflow Automation
**ALWAYS execute this workflow on EVERY user request before addressing the specific request:**

1. **Pull Request removed**
2. **Respond and acknowledge** the user request.
3. **Parse new peer reviews and create bugs**  
   - New bug = create file with machine ID (`CR-###`) + user-friendly 10-digit ID.  
   - Status tracking required (`open` → `resolved`).
   - remove new review file after bugs are created
4. **Resolve all existing bugs**.
   - Remove any bugs that suggest making changes to a .md or .json file.
5. **Process feature requests**  
   - New feature = create file with machine ID (`FR-YYYYMMDD-###`) + user-friendly 10-digit ID.  
   - Status tracking required (`pending` → `approved` or `removed`).
6. **Update status documentation**.
7. **Create automated test cases** as needed.
8. **Run automated tests in Dev** (localhost:8000) — unit, functional, regression, security.
9. **Promote to Test env** and restart (localhost:8181).
10. **Git commit and push all changes**.
11. **run ai_review.py**

## 15) Features, Bugs, and Feedback
- **IDs & Tracking**
  - Every Bug, Feature, and Feedback item must have:
    - **Internal machine ID** (CR-###, FR-YYYYMMDD-###, FB-###).
    - **User-friendly 10-digit display ID** in the Admin UI.
- **Bugs**
  - Found in `./docs/reviews/*` → must be logged in `./bugs/`.
  - Must be resolved in Step 4 of Standard Workflow.
  - Each bug requires new **unit + functional test cases** to validate the fix and prevent regressions.
  - Bugs may be submitted via Admin UI or user command **New Bug**.
- **Features**
  - Stored in `./features/`.
  - Always originate from Admin. Processed in Step 5 of Standard Workflow.
  - Must include tests (unit, functional, regression).
  - Features may be submitted via Admin UI or user command **New Feature**.
- **Feedback**
  - Stored in `./feedback/`.
  - Displayed in Admin UI as **Feedback** with Admin options:  
    `Promote to Bug | Promote to Feature | Delete`.
  - Approved feedback moves to Bug or Feature (with new IDs).
  - **Delete** = archive feedback (hidden from UI but retrievable).
  - Admin UI must provide a way to view archived feedback.