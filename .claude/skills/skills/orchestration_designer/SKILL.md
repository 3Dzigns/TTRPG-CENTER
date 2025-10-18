# Orchestration Designer

## Purpose
Design distributed AI architectures, consensus patterns, fault-tolerant coordination systems, and scalable agent topologies.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- ruv-swarm (>=0.1.0)
- flow-nexus (>=0.1.0)

## When to use
- Designing distributed AI system architectures
- Creating consensus and coordination patterns
- Planning fault-tolerant agent systems
- Inputs include `architecture_spec`, `scaling_requirements`, or `design_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `architecture_spec` (object, optional) - Architecture requirements
- `scaling_requirements` (object, optional) - Scaling and performance needs
- `fault_tolerance` (string, optional) - Byzantine/raft/gossip/quorum

## Procedure (must follow)
1) Use `sequential-thinking` to plan distributed system architecture:
   - Consensus pattern selection
   - Fault tolerance strategy
   - Scaling architecture
   - Communication patterns
2) Read existing architecture decisions from `memory` key `orchestration/design/architectures`.
3) Use `ruv-swarm` to query available consensus patterns:
   - Byzantine fault tolerance
   - Raft consensus
   - Gossip protocols
   - Quorum management
   - CRDT synchronization
4) Use `flow-nexus` to check cloud orchestration patterns if advanced features needed.
5) Create design artifacts:
   - `ConsensusArchitecture.md` - Consensus pattern design
   - `FaultToleranceStrategy.md` - Fault tolerance approach
   - `ScalingArchitecture.md` - Horizontal scaling design
   - `CommunicationPatterns.md` - Inter-agent communication
   - `DesignGuidelines.md` - Implementation guidelines
6) Store design decisions in `memory` under `orchestration/design/architectures/{system_name}`.

## Outputs (artifacts)
- `ConsensusArchitecture.md` - Consensus pattern design
- `FaultToleranceStrategy.md` - Fault tolerance strategy
- `ScalingArchitecture.md` - Scaling architecture
- `CommunicationPatterns.md` - Communication patterns
- `DesignGuidelines.md` - Implementation guide
- Architecture diagrams

## Failure policy
- If `sequential-thinking` or `memory` unavailable, STOP and emit remediation note.
- Always create architecture documentation even for simple systems.
- Never skip fault tolerance considerations.

## Version
1.0.0
