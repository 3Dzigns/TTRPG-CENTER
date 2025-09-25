# Test Strategy
Unit, Functional, Regression, Security, Perf.


## Continuous Integration Gates
- **Lint & Type**: Black, isort, Ruff, and mypy execute on every push/PR.
- **Unit**: `pytest tests/unit` publishes coverage to Codecov and uploads a JUnit report.
- **Functional**: `pytest tests/functional` exercises service contracts and uploads JUnit XML for triage.
- **Security**: Bandit plus Semgrep (SAST), Trivy (dependency/container scan), and OWASP ZAP baseline (DAST) run in dedicated jobs. All artifacts are attached to the workflow summary and must pass before merge.
- **Build**: `python -m build` + `twine check` ensures packages are distributable.

## Nightly & On-Demand Suites
- `regression.yml` runs golden master and performance suites nightly at 02:00 UTC and on manual dispatch. Artifacts include regression reports and extracted logs from `env/test`.
- Pending failures automatically surface in GitHub Actions; on-call should inspect the uploaded artifacts and audit logs under `env/test/logs/audit`.

## Observability Hooks
- When `observability.opentelemetry` is enabled, CI exercises include verifying trace emission via the OTLP endpoint defined in environment `.env` files.
