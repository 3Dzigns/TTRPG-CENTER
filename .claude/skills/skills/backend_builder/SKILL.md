# Backend Builder

## Purpose
Implement data ingestion pipelines, API endpoints, processing workers, and backend service integration.

## Required tools
- code-index (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- context7 (>=0.1.0)
- sequential-thinking (>=0.1.0)
- firecrawl (>=0.1.0)

## When to use
- Building data ingestion and processing pipelines
- Implementing REST/GraphQL API endpoints
- Creating background workers and processors
- Inputs include `pipeline_spec`, `api_spec`, or `build_request`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `pipeline_spec` (object, required) - Pipeline specification
- `framework` (string, optional) - FastAPI/Express/Django/Flask
- `data_sources` (array, optional) - Input data sources

## Procedure (must follow)
1) Use `code-index` to locate existing pipeline components and patterns.
2) Read build state from `memory` key `backend/build/{pipeline_name}`.
3) For complex builds, use `sequential-thinking` to plan implementation steps.
4) Use `context7` to retrieve framework-specific documentation and patterns.
5) Use `firecrawl` if web scraping or data extraction needed for pipeline.
6) Implement pipeline components following existing patterns:
   - Data validation and transformation
   - Error handling and retry logic
   - Logging and monitoring
   - API endpoint routing
7) Create build artifacts:
   - Pipeline implementation files
   - API endpoint handlers
   - Worker processes
   - Unit test files
   - `BuildReport.md`
8) Store build state in `memory` under `backend/build/{pipeline_name}`.

## Outputs (artifacts)
- Pipeline source files (Python/JavaScript/TypeScript)
- API endpoint handlers
- Worker processes
- `BuildReport.md` - Implementation summary
- `PipelineAPI.md` - Pipeline interface documentation
- Unit test files

## Failure policy
- If **required tools** (code-index, memory) unavailable, STOP and emit remediation note.
- Never create pipelines without checking existing patterns first.
- Always emit build artifacts even if incomplete.

## Version
1.0.0
