# 00 Policy Skill Enforcer

## Purpose
(See procedure below.)

## Required tools
- memory (>=0.3.0)
- sequential-thinking (>=0.1.0)

## Optional tools
- (none)

## When to use
- Input includes "enforce_skills": true
- User asks "use skills", "use memory", or "follow project policy"
- Project policy requires memory usage or multi-step reasoning

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Always begin by reading session state:
   - Call `memory.read` for key `${session.user_id}/state`.
   - If unavailable: STOP and return `missing_memory.md` with instructions.

2) Evaluate the user's task and select the appropriate Skill by name:
   - For UI work: `webui_operator`
   - For ingestion: `ingestion_pipeline_operator`
   - For DB work: `database_work_operator`
   - For API/middleware: `middleware_bridge_operator`
   - For debugging: `debugging_root_cause`
   - For documentation: `documentation_generator`
   - For system health: `system_health_audit`

3) Use `sequential-thinking` MCP to plan 3–7 explicit steps. Persist the plan:
   - `memory.write` → `${session.user_id}/plan/{task_id}`

4) Handoff: call the selected Skill with original inputs + `plan_ref`.
   - If the target Skill is not available, STOP with `skill_not_found.md`.

5) On completion, update memory:
   - Append summary, artifacts, and next-actions to `${session.user_id}/history`.

6) Return a final `PolicyReport.md` artifact including:
   - Which Skill ran, tools used, memory keys touched, and any guardrail refusals.

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
