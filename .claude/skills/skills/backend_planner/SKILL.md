# Backend Planner

## Purpose
Plan data ingestion pipelines, API architectures, processing workflows, and backend system integration strategies.

## Required tools
- sequential-thinking (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- code-index (>=0.1.0)
- context7 (>=0.1.0)

## When to use
- Planning data ingestion and processing pipelines
- Designing REST/GraphQL API architectures
- Creating ETL workflow strategies
- Inputs include `pipeline_spec`, `api_requirements`, or `integration_plan`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `pipeline_spec` (object, optional) - Pipeline requirements
- `api_requirements` (object, optional) - API design specifications
- `data_sources` (array, optional) - Input data sources

## Procedure (must follow)
1) Use `sequential-thinking` to analyze backend requirements and break down into phases:
   - Data flow architecture
   - API endpoint design
   - Processing pipeline stages
   - Error handling and retry strategies
2) Read existing backend patterns from `memory` key `backend/patterns`.
3) Use `context7` to retrieve framework best practices (FastAPI/Express/Django patterns).
4) Use `code-index` to discover existing pipeline components for reuse.
5) Create planning artifacts:
   - `DataFlowDiagram.md` - Data ingestion and processing flow
   - `APIArchitecture.md` - Endpoint design and routing
   - `PipelineStages.md` - Processing stages and transformations
   - `ErrorHandling.md` - Error recovery and retry strategy
6) Store planning decisions in `memory` under `backend/plans/{pipeline_name}`.

## Outputs (artifacts)
- `DataFlowDiagram.md` - Visual data flow architecture
- `APIArchitecture.md` - API endpoint specifications
- `PipelineStages.md` - Pipeline stage definitions
- `ErrorHandling.md` - Error handling strategy
- `IntegrationRoadmap.json` - Phased integration plan

## Failure policy
- If **required tools** (sequential-thinking, memory) unavailable, STOP and emit remediation note.
- If optional tools unavailable, proceed with reduced functionality and note limitations.
- Never fabricate tool outputs.

## Version
1.0.0
