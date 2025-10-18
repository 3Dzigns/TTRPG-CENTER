# Database Designer

## Purpose
Design scalable database architectures, sharding strategies, replication patterns, and data modeling frameworks.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Designing scalable database architectures
- Creating sharding and partitioning strategies
- Planning replication and high availability
- Inputs include `architecture_spec`, `scaling_requirements`, or `design_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `architecture_spec` (object, optional) - Architecture requirements
- `scaling_requirements` (object, optional) - Performance and scaling needs
- `database_type` (string, optional) - MongoDB/Cassandra/Neo4j/PostgreSQL

## Procedure (must follow)
1) Use `sequential-thinking` to plan database architecture:
   - Data modeling strategy (relational/document/graph)
   - Sharding and partitioning design
   - Replication and high availability
   - Backup and disaster recovery
2) Read existing design decisions from `memory` key `database/design/architectures`.
3) Use `context7` to retrieve database architectural patterns (sharding/replication/CAP).
4) Use `code-index` to analyze existing database patterns.
5) Create design artifacts:
   - `DataModelingFramework.md` - Data model design
   - `ShardingStrategy.md` - Sharding and partitioning approach
   - `ReplicationArchitecture.md` - Replication design
   - `BackupStrategy.md` - Backup and disaster recovery
   - `DesignGuidelines.md` - Implementation guidelines
6) Store design decisions in `memory` under `database/design/architectures/{database_name}`.

## Outputs (artifacts)
- `DataModelingFramework.md` - Data model architecture
- `ShardingStrategy.md` - Sharding design
- `ReplicationArchitecture.md` - Replication pattern
- `BackupStrategy.md` - Backup and recovery strategy
- `DesignGuidelines.md` - Implementation guide
- Architecture diagrams

## Failure policy
- If `sequential-thinking` or `memory` unavailable, STOP and emit remediation note.
- Always create architecture documentation even for simple systems.
- Never skip replication and backup considerations.

## Version
1.0.0
