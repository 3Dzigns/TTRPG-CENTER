# Orchestration Planner

## Purpose
Plan AI agent workflows, swarm topologies, task decomposition strategies, and coordination patterns for LLM-based orchestration systems.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- ruv-swarm (>=0.1.0)
- flow-nexus (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Planning multi-agent swarm architectures
- Designing task decomposition and delegation strategies
- Creating coordination patterns for distributed AI systems
- Inputs include `agent_workflow_spec`, `swarm_requirements`, or `orchestration_plan`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `agent_workflow_spec` (object, optional) - Agent workflow requirements
- `topology` (string, optional) - Swarm topology (mesh/hierarchical/ring/star)
- `max_agents` (number, optional) - Maximum concurrent agents

## Procedure (must follow)
1) Use `sequential-thinking` to analyze orchestration requirements and break down into phases:
   - Task decomposition strategy
   - Swarm topology selection
   - Coordination pattern design
   - Agent role definitions
2) Read existing orchestration patterns from `memory` key `orchestration/patterns`.
3) Use `ruv-swarm` to query available topology types and agent capabilities.
4) Use `flow-nexus` to check cloud orchestration features if advanced scaling needed.
5) Use `code-index` to discover existing agent implementations for reuse.
6) Create planning artifacts:
   - `AgentWorkflowDiagram.md` - Agent interaction flow
   - `TopologySpecification.md` - Swarm topology and scaling strategy
   - `TaskDecomposition.md` - Task breakdown and delegation rules
   - `CoordinationPatterns.md` - Inter-agent communication patterns
7) Store planning decisions in `memory` under `orchestration/plans/{workflow_name}`.

## Outputs (artifacts)
- `AgentWorkflowDiagram.md` - Visual agent interaction flow
- `TopologySpecification.md` - Swarm topology design
- `TaskDecomposition.md` - Task breakdown strategy
- `CoordinationPatterns.md` - Agent coordination patterns
- `ScalingStrategy.json` - Auto-scaling rules and agent limits

## Failure policy
- If **required tools** (sequential-thinking, memory) unavailable, STOP and emit remediation note.
- If optional tools unavailable, proceed with basic planning and note limitations.
- Never fabricate swarm capabilities or topology types.

## Version
1.0.0
