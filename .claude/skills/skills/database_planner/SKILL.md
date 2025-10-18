# Database Planner

## Purpose
Plan database schemas, indexing strategies, query optimization approaches, and data migration workflows.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- code-index (>=0.1.0)
- context7 (>=0.1.0)

## When to use
- Planning database schema and indexing strategies
- Designing data migration workflows
- Creating query optimization plans
- Inputs include `schema_spec`, `migration_plan`, or `optimization_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `schema_spec` (object, optional) - Schema requirements
- `database_type` (string, optional) - MongoDB/Cassandra/Neo4j/PostgreSQL
- `migration_plan` (object, optional) - Migration requirements

## Procedure (must follow)
1) Use `sequential-thinking` to analyze database requirements and break down into phases:
   - Schema design and normalization
   - Indexing strategy for performance
   - Query optimization approach
   - Migration and rollback strategy
2) Read existing database patterns from `memory` key `database/patterns`.
3) Use `context7` to retrieve database best practices (MongoDB/Cassandra/Neo4j patterns).
4) Use `code-index` to discover existing schema definitions and queries.
5) Create planning artifacts:
   - `SchemaDesign.md` - Schema structure and relationships
   - `IndexingStrategy.md` - Index design for performance
   - `QueryOptimization.md` - Query performance approach
   - `MigrationPlan.md` - Migration and rollback strategy
6) Store planning decisions in `memory` under `database/plans/{database_name}`.

## Outputs (artifacts)
- `SchemaDesign.md` - Visual schema structure
- `IndexingStrategy.md` - Index specifications
- `QueryOptimization.md` - Query optimization plan
- `MigrationPlan.md` - Migration strategy with rollback
- `PerformanceTargets.json` - Query performance targets

## Failure policy
- If **required tools** (sequential-thinking, memory) unavailable, STOP and emit remediation note.
- If optional tools unavailable, proceed with reduced functionality and note limitations.
- Never fabricate tool outputs.

## Version
1.0.0
