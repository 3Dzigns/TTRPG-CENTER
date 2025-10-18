# Backend Tester

## Purpose
Execute pipeline validation, API endpoint testing, integration tests, and data processing verification.

## Required tools
- memory (>=0.3.0)

## Optional tools
- sequential-thinking (>=0.1.0)
- firecrawl (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Testing data ingestion pipeline correctness
- Validating API endpoint functionality
- Integration testing for backend services
- Data processing verification
- Inputs include `test_spec`, `pipeline_id`, or `test_suite`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `pipeline_id` (string, optional) - Pipeline identifier to test
- `test_spec` (object, optional) - Test specification
- `test_type` (string, optional) - unit/integration/e2e
- `sample_data` (string, optional) - Test data file path

## Procedure (must follow)
1) For complex test suites, use `sequential-thinking` to plan test execution order.
2) Read previous test results from `memory` key `backend/tests/{test_suite}`.
3) Execute pipeline tests:
   - Run unit tests for individual components
   - Execute integration tests for full pipeline
   - Validate data transformation correctness
   - Check error handling and retry logic
   - Verify API endpoint responses
4) Use `firecrawl` to validate web scraping components if applicable.
5) Use `code-index` to locate test fixtures and sample data.
6) Create test artifacts:
   - `TestReport.md` - Test results summary
   - `DataValidation.json` - Data quality metrics
   - `APITestResults.md` - Endpoint test outcomes
   - `ErrorHandlingValidation.md` - Error recovery test results
7) Store test results in `memory` under `backend/tests/{test_suite}`.

## Outputs (artifacts)
- `TestReport.md` - Detailed test results
- `DataValidation.json` - Data quality and transformation metrics
- `APITestResults.md` - API endpoint test outcomes
- `ErrorHandlingValidation.md` - Error handling verification
- Pipeline execution logs

## Failure policy
- If `memory` unavailable, STOP and emit remediation note.
- If tests fail, always capture logs and data samples.
- Never skip error handling tests.

## Version
1.0.0
