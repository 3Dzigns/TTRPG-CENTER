# Release Checklist
Manual steps.

- [ ] Run `scripts/init-environments.ps1` for `dev`, `test`, and `prod` to seed `env/<env>/{code,config,data,logs,artifacts,cache,uploads,ssl}`.
- [ ] Verify Docker Compose stacks mount only environment-scoped volumes and no longer build the legacy monolith service.
- [ ] Confirm env-specific `.env` values include updated port and path keys (`CODE_ROOT`, `UPLOADS_PATH`, `TEST_RUNNER_PORT`).
