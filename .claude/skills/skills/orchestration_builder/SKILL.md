# Orchestration Builder

## Purpose
Implement AI agent swarms, task orchestration systems, multi-agent coordination, and distributed LLM workflows.

## Required tools
- ruv-swarm (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- flow-nexus (>=0.1.0)
- sequential-thinking (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Building multi-agent swarm implementations
- Implementing task orchestration and delegation
- Creating agent coordination and communication systems
- Inputs include `orchestration_spec`, `agent_definitions`, or `build_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `orchestration_spec` (object, required) - Orchestration specification
- `topology` (string, optional) - Swarm topology (mesh/hierarchical/ring/star)
- `max_agents` (number, optional) - Maximum concurrent agents
- `strategy` (string, optional) - Distribution strategy (balanced/specialized/adaptive)

## Procedure (must follow)
1) Read build state from `memory` key `orchestration/build/{workflow_name}`.
2) Use `code-index` to locate existing agent implementations and patterns.
3) For complex builds, use `sequential-thinking` to plan implementation phases.
4) Use `ruv-swarm` to initialize swarm topology:
   - `swarm_init` with specified topology and max agents
   - `agent_spawn` for each required agent type
   - `task_orchestrate` to set up task delegation
5) Use `flow-nexus` for cloud-based orchestration if advanced features needed:
   - `workflow_create` for event-driven workflows
   - `workflow_agent_assign` for optimal agent matching
6) Create build artifacts:
   - Agent implementation files
   - Orchestration configuration
   - Task delegation rules
   - `BuildReport.md`
7) Store build state in `memory` under `orchestration/build/{workflow_name}`.

## Outputs (artifacts)
- Agent implementation files
- Orchestration configuration (YAML/JSON)
- `BuildReport.md` - Implementation summary
- `AgentAPI.md` - Agent interface documentation
- Task delegation rules

## Failure policy
- If **required tools** (ruv-swarm, memory) unavailable, STOP and emit remediation note.
- Never create agents without checking existing implementations first.
- Always emit build artifacts even if incomplete.

## Version
1.0.0
