# FR-022: Automated Persona Test Suite in Admin UI (Testing Section) — Rev-A
**Date:** 2025-09-16  
**Owner:** Admin Platform / QA Automation  
**Status:** Draft (Updated)

## Summary (Updated)
Add an **Automated Persona Test Suite** to the **Admin UI → Testing** section. Admins can create, manage, and run persona-driven automated tests against the model and retrieval stack. Tests run as **multi-turn chats** with a **hard chat-depth cap** (client-side/orchestrator-enforced), support **filtering by persona attributes**, and allow **content scoping** so a persona only queries within specified sources (e.g., Pathfinder, Starfinder, specific publishers/books).

**New in Rev-A:**
1) When the Admin requests a **new persona**, the system can **randomly generate** one using **OpenAI GPT-5** from the template (Admin can regenerate/modify before saving).  
2) The **persona template** now includes:  
   - **system_under_test**: which system the run targets (e.g., Pathfinder, Starfinder).  
   - **persona_goal**: a discrete or complex goal that guides the conversation.  
      - **Discrete example:** “Explain Fireball.” (run may end early if the goal is clearly satisfied)  
      - **Complex example:** “Help me build a character.” or “Integrate an external tool with my game.” (may not complete before hitting max depth)

## Goals
- Codify **repeatable, multi-persona** testing of the RAG/Graph/tooling stack.
- Provide **attribute filters** and **content scoping** per persona.
- Enforce **chat depth** as a hard cap on number of queries sent (no model-side token governance).
- Automate **quality scoring** and **flagging** for fast triage.
- Enable **batch runs** across multiple personas and constraints for regression tracking.
- **NEW:** Accelerate test coverage via **auto-generated personas**.
- **NEW:** Drive tests by **explicit persona goals** with **early-stop** when goal success is detected.

## Non-Goals
- Replacing manual exploratory testing.
- Establishing legal/compliance policy for persona attribute usage (handled separately; this feature implements controls & audit).

## Scope
- **Admin UI (Testing)**: Persona management, filters, run configuration, results dashboard.
- **Orchestrator service**: Run lifecycle, depth enforcement, logging, scoring, persistence.
- **Storage**: Personas, runs, run steps, scores, flags.
- **Connectors**: Retrieval system callouts, OpenAI GPT-5 calls.
- **NEW**: GPT-5–backed **Persona Generator** and **Goal Satisfaction Heuristic**.

---

## Persona Model (Updated)
```yaml
Persona:
  id: uuid
  name: string (required, unique per tenant/env)
  profile:
    name: string
    age: integer
    gender: string
    location: string
    religion: string
    ethnicity: string
    sexual_orientation: string
    background: string
    preferred_gaming_system: enum[Pathfinder, Starfinder, D&D, Other]
    hobbies: string[]
    language: string  # for non-English Q&A
  key_attributes:                # indexed for filtering
    - attribute: string          # e.g., gender, location, preferred_gaming_system
      value: string
  content_scope:
    systems: string[]            # e.g., ["Pathfinder", "Starfinder"]
    books: string[]              # optional list of source books/IDs
    publishers: string[]         # optional
  # NEW fields
  system_under_test: enum[Pathfinder, Starfinder, D&D, Other]
  persona_goal:
    type: enum[discrete, complex]
    goal_text: string
    success_criteria: string     # optional natural-language acceptance, used by evaluator
  is_active: boolean (default: true)
  created_at/updated_at/by: timestamps & user IDs
```

> **Privacy & Sensitivity:** Persona fields include potentially sensitive attributes (religion, ethnicity, sexual orientation). Admin UI must display a privacy notice, require explicit confirmation before saving, restrict access to **Admin** role, and log access & edits. Data retention follows project policy.

---

## Admin UI Requirements (Updated)
1. **Persona Management**
   - Create, edit, delete, activate/deactivate personas.
   - **NEW:** “**Generate Random Persona**” action that uses GPT-5 to fill the template (Admin may regenerate/edit).
   - Validate required fields and uniqueness constraints.
   - Confirmations for delete; soft-delete or archive preferred.
2. **Filtering & Search**
   - Filter personas by **key attributes** (multi-select), free-text search by name/background.
   - Saved filters.
3. **Content Scoping**
   - UI to constrain **systems/publishers/books**; validate against catalog/dictionary.
4. **Run Configuration**
   - Select **one or multiple personas**.
   - Choose **system constraints** (e.g., Pathfinder vs Starfinder) and optional content scope override.
   - **Chat Depth** (integer ≥1): max number of Q→A cycles to execute; enforced by orchestrator.
   - Concurrency control (max N personas per batch; queue the rest).
5. **Execution & Monitoring**
   - Start batch; show **per-persona run status**: Pending → Running (step k/N) → Completed → Failed.
   - Live log tail (tokens/costs optional), cancel in-flight run, retry failed.
6. **Results & Review**
   - Per-run summary: score %, flagged (<90%), duration, errors, full transcript, retrieval traces, tool calls, citations.
   - Bulk actions: mark reviewed, create bug/FR, export JSON/CSV/MD bundle.
7. **Permissions & Audit**
   - Admin-only access; granular permissions for view/run/delete.
   - Audit trails for persona CRUD and run executions.

---

## Orchestration Flow (Updated)
1. **Init Question (OpenAI GPT-5)**: Prompt includes persona profile, **system_under_test**, **persona_goal**, content constraints, and project guardrails. GPT-5 returns the **first user-style question**.
2. **Answer via Project Tools**: Route through retrieval system (AstraDB + graph/dictionary/tools) to produce the answer; capture citations/metrics.
3. **Goal Progress Check (NEW)**: After each answer, call a **Goal Satisfaction Heuristic** (lightweight GPT-5 evaluation) that inspects the transcript vs. `persona_goal.success_criteria`:
   - If **discrete** and satisfied → **early stop** (success).
   - If **complex** and progress noted but not complete → continue until depth.
4. **Next Turn Generation**: If continuing, send the **full chat transcript** back to GPT-5 to request the **next question**.
5. **Depth Enforcement**: Repeat 2–4 until **chat depth** reached; orchestrator blocks further sends.
6. **Final Evaluation**: Provide the full chat transcript + goals/criteria to GPT-5 for a **quality/alignment score (0–100%)** + rubric notes.
7. **Flag & Persist**: If score <90%, flag run; store transcripts, signals, and artifacts.

---

## Configuration
- **Defaults**: depth=3, concurrency=3, timeout per step=60s, retry policy=exponential backoff (max 2).
- **Cost Controls**: per-run token/$$ cap; abort if exceeded; log actual usage.
- **Determinism**: option to set temperature/top_p; seed when available; store model version + params.
- **Citations**: require citations from retrieval system; store for review.
- **NEW:** Toggle **Goal Early-Stop** (on by default for discrete goals).

---

## Data Persistence (Updated)
```yaml
Run:
  id, started_at, ended_at, status, initiated_by, depth, config, totals(tokens,cost), score_percent, flagged:boolean, early_stop:boolean
RunStep:
  id, run_id, step_index, request(prompt hash), response, retrieval_traces, citations[], timings, errors[],
  goal_check: {"satisfied": boolean, "progress_notes": string, "confidence": float}
ScoreDetail:
  id, run_id, rubric_version, sub_scores{{grounding, coherence, instruction_following, safety, style, goal_alignment}}, notes
AuditLog:
  id, actor, action, object_type, object_id, timestamp, diff
```

---

## API Endpoints (illustrative, Updated)
- `POST /api/admin/personas` (create), `GET /api/admin/personas`, `PATCH /api/admin/personas/<built-in function id>`, `DELETE /api/admin/personas/<built-in function id>`
- **NEW:** `POST /api/admin/personas:generate` → returns a draft persona using GPT-5
- `POST /api/admin/tests/runs` (batch start)
- `GET /api/admin/tests/runs?status=&persona_id=` (list)
- `GET /api/admin/tests/runs/<built-in function id>` (detail)
- `POST /api/admin/tests/runs/<built-in function id>/cancel`
- `POST /api/admin/tests/runs/<built-in function id>/review` (mark reviewed)
- `GET /api/admin/tests/runs/<built-in function id>/export`

---

## Acceptance Criteria (Updated)
1. Admin can **create/edit/delete** personas; changes are audited.
2. Admin can **filter** personas by key attributes and free text.
3. Admin can **scope content** and **configure runs** with **multiple personas**.
4. **Chat depth** strictly enforced; no more than N Q→A cycles are executed.
5. Each run begins with **GPT-5 generated initial question** using persona, **system_under_test**, and **persona_goal**.
6. The system **routes to retrieval/tools**, stores transcripts, traces, and citations.
7. Final **GPT-5 evaluation score** recorded; **<90% flagged**.
8. Results view supports **transcript review**, **flag filters**, and **export**.
9. Permissions restrict access to Admin role; **audit logs** exist for CRUD & runs.
10. Basic **cost/timeout** safeguards prevent runaway usage and surface failures.
11. **NEW:** “Generate Random Persona” produces a **valid draft** aligned to the template and **editable** prior to save.
12. **NEW:** **Goal Satisfaction Heuristic** supports **early stop** for discrete goals and progress notes for complex goals.

---

## User Stories & Test Cases (Updated)

### US-1: Create Persona
**As an Admin**, I want to create a persona with profile, key attributes, content scope, **system_under_test**, and **persona_goal** so that it can be used in automated tests.  
**Acceptance Tests**
- TC-1.1: Creating a persona with required fields succeeds; appears in list.
- TC-1.2: Missing required fields → validation errors.
- TC-1.3: Duplicate name → conflict error.
- TC-1.4: Sensitive fields warning & confirmation step is displayed.
- TC-1.5: Audit log entry created with before/after.

### US-2: Generate Random Persona (NEW)
**As an Admin**, I want to auto-generate a random persona from the template using GPT-5 so I can quickly populate test coverage.  
**Acceptance Tests**
- TC-2.1: Clicking “Generate Random Persona” returns a complete draft with plausible, non-identifying values.
- TC-2.2: Draft includes **system_under_test** and **persona_goal** (type + goal_text).
- TC-2.3: Admin can regenerate; new draft replaces form values.
- TC-2.4: Admin can edit fields before saving; validation still applies.
- TC-2.5: API request/response logged; no persona stored until Admin clicks Save.

### US-3: Filter Personas
**As an Admin**, I want to filter personas by key attributes and search by text so I can quickly select relevant personas.  
**Acceptance Tests**
- TC-3.1: Multi-attribute filter reduces list correctly (AND logic).
- TC-3.2: Saved filter persists across sessions.
- TC-3.3: Clearing filters restores full list.

### US-4: Content Scoping
**As an Admin**, I want to limit a persona’s access to specific systems/books so tests reflect targeted coverage.  
**Acceptance Tests**
- TC-4.1: Selecting systems/books restricts retrieval calls to those sources (verify traces).
- TC-4.2: Invalid book ID → validation error.
- TC-4.3: Run-level scope override works and is logged.

### US-5: Configure & Start Batch Run
**As an Admin**, I want to select multiple personas, set chat depth, and start a test run.  
**Acceptance Tests**
- TC-5.1: Depth=N yields exactly N Q→A cycles per persona unless **early stop** triggers.
- TC-5.2: Depth=1 performs init→answer→goal-check→eval then stops.
- TC-5.3: Concurrency limit respected; excess queued.
- TC-5.4: Cancel during run transitions status to Canceled; no further steps executed.

### US-6: Initial Question via GPT-5
**As an Admin**, I want the first question to be generated by GPT-5 using persona, **system_under_test**, **persona_goal**, and constraints.  
**Acceptance Tests**
- TC-6.1: Prompt includes persona profile + system/content constraints + goal.
- TC-6.2: Returned question stored and shown in transcript.
- TC-6.3: Failure to call GPT-5 → step marked failed; surfaced in UI; retry works.

### US-7: Multi-Turn Loop, Goal Checks & Depth Enforcement
**As an Admin**, I want the system to iterate until either the goal is satisfied (for discrete goals) or chat depth is reached.  
**Acceptance Tests**
- TC-7.1: For discrete goal satisfied at step k < N, run stops early; **early_stop=true** recorded.
- TC-7.2: For complex goal, progress notes recorded at each step; run stops at depth N.
- TC-7.3: If retrieval fails on step k, step recorded as failed; run marked Failed unless retry succeeds.
- TC-7.4: Timeouts trigger retry per policy; exhaustion marks step failed.

### US-8: Final Evaluation & Flagging
**As an Admin**, I want a percent score and flagging for low scores.  
**Acceptance Tests**
- TC-8.1: Evaluation prompt includes full transcript + goals/rubric id; score 0–100 returned.
- TC-8.2: Score <90% sets flagged=true and appears in **Flagged** filter.
- TC-8.3: Score ≥90% not flagged.
- TC-8.4: Sub-scores include **goal_alignment** and notes.

### US-9: Results Review & Export
**As an Admin**, I want to review transcripts, traces, and export results.  
**Acceptance Tests**
- TC-9.1: Transcript view shows all turns with citations and goal-check outcomes.
- TC-9.2: Export JSON/CSV/MD includes run metadata, steps, scores, flags, early_stop.
- TC-9.3: “Create Bug/FR” action generates a prefilled issue payload (local file or API hook).

### US-10: Permissions & Audit
**As an Admin**, I need access control and auditability.  
**Acceptance Tests**
- TC-10.1: Non-Admin user forbidden from Testing section.
- TC-10.2: All persona CRUD and run actions create audit entries.
- TC-10.3: Audit entries include actor, timestamp, and diffs.

### US-11: Cost & Safety Controls
**As a Platform Owner**, I want guardrails to prevent runaway cost and unsafe prompts.  
**Acceptance Tests**
- TC-11.1: Per-run token/$ cap aborts run when exceeded; status explains abort.
- TC-11.2: Safety system prompt applied to GPT-5 calls.
- TC-11.3: Temperature/top-p stored; deterministic mode honored where supported.

---

## Prompts (Illustrative, Updated)
**Persona Generator Prompt (to GPT-5)**  
- System: “You generate realistic, non-identifying testing personas for {system_under_test}. Fill all template fields with plausible values. Avoid PII. Include a {persona_goal.type} goal with clear **goal_text** and optional **success_criteria**.”  
- User: Admin’s constraints (e.g., preferred systems/books, attribute hints).

**Init Question Prompt (to GPT-5)**  
- System: “You are a test question generator for {system_under_test}. Generate a single, concise question a user like this persona would ask, grounded in allowed content scope and aligned to **persona_goal**.”  
- User: persona profile + constraints + goal.

**Next Question Prompt (to GPT-5)**  
- System: “Given the full prior chat, constraints, and **persona_goal**, generate the next natural follow-up question. One question only.”  
- User: transcript so far + scope + goal.

**Goal Satisfaction Heuristic (to GPT-5)**
- System: “Assess whether the latest assistant response satisfies the persona’s **goal_text** per **success_criteria**. Return JSON: {'satisfied': bool, 'progress_notes': string, 'confidence': 0–1}.”  
- User: goal, success_criteria, transcript so far.

**Final Evaluation Prompt (to GPT-5)**  
- System: “Evaluate the conversation for grounding, coherence, instruction-following, safety, style, and **goal_alignment**, 0–100%. Return JSON with sub-scores and overall.”  
- User: full transcript + rubric id + goals.

---

## Telemetry & Reporting
- Per-run metrics: duration, steps, retries, token/$ usage, top errors, average score.
- Trend charts by persona, system, content scope; pass-rate (≥90%).
- **NEW:** Early-stop rate for discrete goals; average progress for complex goals.

## Security & Compliance
- Admin-only; sensitive attributes gated with notice/consent.
- Encrypt at rest; redact sensitive fields in exports unless explicitly enabled.
- Audit read/write; configurable retention & purge jobs.

## Rollout Plan
- Phase 1: Persona CRUD + generator + single persona run + depth enforcement + scoring + early-stop for discrete goals.
- Phase 2: Batch runs + filters + exports + bug/FR hooks + complex goal progress charts.
- Phase 3: Cost dashboards + seeds/determinism + saved configs + trend charts.

---

## Open Questions
- Do we require per-publisher opt-in for using personas with sensitive attributes in tests?
- Should flagged runs auto-open **BUG** tickets with transcript bundles?
- Do we want **library presets** for common discrete/complex goals per system?
