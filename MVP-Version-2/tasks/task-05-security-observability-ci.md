# Task 05 — Security, Observability, and CI/Test Automation

## Objective
Embed the MVP V2 security, observability, and CI gates across all services so JWT/RBAC, source gating, OTel tracing, and automated test suites become enforceable guardrails.

## Why This Matters
- Services still run without enforcing JWT auth, RBAC, or source gating despite shared implementations in `src_common/jwt_service.py`.
- CORS/TLS/HSTS/rate limiting policies are not applied per environment.
- Observability flags for OpenTelemetry are disabled, and services lack trace instrumentation.
- Audit logging for privileged actions isn’t persisted to env-scoped storage.
- CI workflows run basic tests but don’t execute SAST/DAST/image scans or nightly regression gates.

## Deliverables
- Shared FastAPI middleware enforcing JWT (RS256), role-based access, and source gating aligned with Phase 6 requirements.
- Environment-specific security headers, rate limiting, and TLS configuration (dev/test/prod) with secrets pulled from env config.
- OpenTelemetry instrumentation across ingestion/retrieval/admin/user flows, with exporters configurable via `.env`/feature flags.
- Persistent audit logging pipeline storing events under `env/<env>/logs/audit/` with rotation and retention policies.
- CI updates running unit/functional/security/perf suites, plus Semgrep, Bandit, Trivy, and OWASP ZAP (baseline) for gated merges; nightly regressions on main.
- Test artifacts uploaded for each suite and referenced in build summaries.

## Dependencies / Sequencing
- Builds on Tasks 01–04 so services and pipelines exist to secure/observe.
- Coordinate with Admin UI for presenting audit logs/HGRN actions.

## Detailed Steps
1. **JWT/RBAC integration**
   - Create shared FastAPI dependencies/middleware to validate RS256 JWTs, populate request context, and enforce role checks.
   - Apply the middleware to ingest, orchestrator, admin_api, user_api, and test_runner where applicable, keeping a dev bypass flag for local testing.
   - Update tests to cover authorised vs unauthorised access and source gating behaviour.
2. **Security headers & rate limiting**
   - Implement environment-aware CORS policies, HSTS for test/prod, and Redis-backed rate limiting.
   - Ensure responses include standard headers (`Strict-Transport-Security`, `X-RateLimit-*`), and add functional tests verifying header presence.
3. **Source gating & audit logging**
   - Enforce `allowed_sources` filters in retrieval flows (Task 03) and record decisions.
   - Persist audit events (`logins`, `role changes`, `dictionary promotions`, `bulk deletes`) to JSON logs under env-specific audit directories with rotation.
   - Expose audit retrieval endpoints in Admin API and corresponding UI updates (Task 04).
4. **Observability instrumentation**
   - Enable `config/flags.yaml` toggles (`opentelemetry`) and wire services to emit spans/metrics using OTLP exporters configured per env.
   - Add structured logging improvements (trace IDs, user/session/job context) and propagate through ingestion/retrieval/test runner flows.
   - Document tracing setup in runbooks and provide local collector instructions.
5. **CI/CD hardening**
   - Update `.github/workflows/ci.yml` to run unit + functional + lint/type checks on PRs, attach artifacts, and fail on coverage regressions.
   - Add dedicated workflows for nightly regression (`regression.yml`), security scans (Semgrep, Bandit, Trivy), and OWASP ZAP baseline.
   - Surface test reports in workflow summaries and ensure required checks block merges.
6. **Documentation & training**
   - Update `MVP-Version-2/Test-Strategy.md`, `Coding-Standards`, and security docs with the new processes.
   - Provide onboarding notes for configuring JWT keys, TLS certs, and OTel exporters.
