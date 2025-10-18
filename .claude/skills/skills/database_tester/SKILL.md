# Database Tester

## Purpose
Execute schema validation, query performance tests, migration verification, and data integrity checks.

## Required tools
- memory (>=0.3.0)

## Optional tools
- sequential-thinking (>=0.1.0)
- code-index (>=0.1.0)

## When to use
- Testing database schema correctness
- Validating query performance
- Migration testing and rollback verification
- Data integrity validation
- Inputs include `test_spec`, `database_id`, or `test_suite`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `database_id` (string, optional) - Database identifier to test
- `test_spec` (object, optional) - Test specification
- `test_type` (string, optional) - schema/performance/migration/integrity
- `sample_data` (string, optional) - Test data file path

## Procedure (must follow)
1) For complex test suites, use `sequential-thinking` to plan test execution order.
2) Read previous test results from `memory` key `database/tests/{test_suite}`.
3) Execute database tests:
   - Run schema validation tests
   - Execute query performance benchmarks
   - Verify migration and rollback correctness
   - Check data integrity constraints
   - Validate index effectiveness
4) Use `code-index` to locate test fixtures and sample data.
5) Create test artifacts:
   - `TestReport.md` - Test results summary
   - `SchemaValidation.json` - Schema correctness metrics
   - `PerformanceResults.md` - Query performance benchmarks
   - `MigrationValidation.md` - Migration test outcomes
   - `IntegrityCheck.json` - Data integrity results
6) Store test results in `memory` under `database/tests/{test_suite}`.

## Outputs (artifacts)
- `TestReport.md` - Detailed test results
- `SchemaValidation.json` - Schema validation metrics
- `PerformanceResults.md` - Query performance data
- `MigrationValidation.md` - Migration verification
- `IntegrityCheck.json` - Data integrity analysis
- Query execution plans

## Failure policy
- If `memory` unavailable, STOP and emit remediation note.
- If tests fail, always capture query plans and data samples.
- Never skip integrity tests.

## Version
1.0.0
