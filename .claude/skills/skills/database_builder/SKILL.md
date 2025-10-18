# Database Builder

## Purpose
Implement database schemas, create indexes, build queries, and execute data migrations.

## Required tools
- code-index (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- sequential-thinking (>=0.1.0)

## When to use
- Building database schemas and indexes
- Implementing queries and stored procedures
- Executing data migrations
- Inputs include `schema_spec`, `migration_spec`, or `build_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `schema_spec` (object, required) - Schema specification
- `database_type` (string, optional) - MongoDB/Cassandra/Neo4j/PostgreSQL
- `migration_type` (string, optional) - schema/data/index

## Procedure (must follow)
1) Use `code-index` to locate existing schema definitions and queries.
2) Read build state from `memory` key `database/build/{schema_name}`.
3) For complex builds, use `sequential-thinking` to plan implementation steps.
4) Use `context7` to retrieve database-specific documentation and patterns.
5) Implement database components following existing patterns:
   - Schema definition files
   - Index creation scripts
   - Query implementations
   - Migration scripts with rollback
6) Create build artifacts:
   - Schema definition files (SQL/JSON/Cypher)
   - Index creation scripts
   - Query implementation files
   - Migration scripts
   - `BuildReport.md`
7) Store build state in `memory` under `database/build/{schema_name}`.

## Outputs (artifacts)
- Schema definition files
- Index creation scripts
- Query implementation files
- Migration scripts with rollback
- `BuildReport.md` - Implementation summary
- `SchemaAPI.md` - Schema documentation
- Validation test files

## Failure policy
- If **required tools** (code-index, memory) unavailable, STOP and emit remediation note.
- Never create schemas without checking existing patterns first.
- Always emit build artifacts even if incomplete.

## Version
1.0.0
