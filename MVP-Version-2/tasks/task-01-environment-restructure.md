# Task 01 — Environment & Repo Restructure

## Objective
Bring the repo layout and environment bootstrap in line with MVP V2 standards so every environment (dev/test/prod) is isolated under `env/<env>/{code,config,data,logs,artifacts,cache,uploads,ssl}` and all services consume the shared configuration contract.

## Why This Matters
- Multiple services and scripts still assume legacy paths in the repo root (`artifacts/`, `uploads/`, etc.).
- `scripts/init-environments.ps1` only creates a subset of the required directories and omits cache/uploads/ssl.
- Docker Compose still builds the legacy monolith service and mounts the entire repo rather than env-scoped volumes.
- `EnvironmentValidator` and `get_environment_config` need to reflect the canonical directory/port mapping so downstream services/tests stop hard-coding ports or relative paths.

## Deliverables
- Updated `scripts/init-environments.ps1` that provisions all required directories, writes `.env` templates with correct cache TTLs, and guards against overwriting user-provided values.
- Synchronized directory enforcement in `src_common/environment_isolation.py` plus helpers to surface `env/<env>/code` for service mounts.
- Restructured environment data: move repo-root `artifacts/`, `uploads/`, `test_uploads_minimal/`, and similar into their respective `env/<env>/...` homes with migration notes.
- Docker Compose files for dev/test/prod that expose only the new microservices, bind to the canonical ports (8000/8181/8282 sequences), and mount env-specific volumes.
- Documentation updates (`Coding-Standards`, `Requirements`, runbooks) summarising the new directory structure and promotion/rollback workflow.

## Dependencies / Sequencing
- No external blockers, but coordinate with ingestion/pipeline work so manifest paths remain accurate.
- Align with the security task to ensure secrets remain under `env/<env>/config`.

## Detailed Steps
1. **Expand environment bootstrap script**
   - Update `scripts/init-environments.ps1` to create the full directory list (`code, config, data, logs, artifacts, cache, uploads, ssl`).
   - Ensure generated `.env.template` / `.env` files include `TARGET_ENV`, per-phase cache TTLs (0/5/300), and placeholders for JWT/secret keys.
   - Add idempotent checks so existing `.env` values aren’t overwritten, and document the behaviour in script comments.
2. **Harden `EnvironmentValidator`**
   - Modify `src_common/environment_isolation.py` so `ensure_environment_directories` mirrors the expanded directory list.
   - Extend `get_environment_config` to expose `code_path`, `artifacts_path`, and per-service base URLs derived from the configured base port.
   - Add unit tests in `tests/unit/test_environment_isolation.py` to cover the new directories and config keys.
3. **Relocate environment artefacts**
   - Move or symlink legacy directories (`artifacts/`, `uploads/`, `test_uploads_minimal/`, any top-level logs) into the appropriate `env/<env>/...` location.
   - Update ingestion, tests, and scripts that reference the old paths to use `get_environment_config` helpers or environment variables.
   - Capture migration guidance in `docs/` (new ADR or update existing README).
4. **Revise Docker Compose stacks**
   - Remove the legacy `app` container from `env/dev/docker-compose.yml` and replicate changes for test/prod variants.
   - Ensure each microservice mounts only the required env-specific directories and uses the shared `.env` file.
   - Confirm port bindings follow 8000–8004 for dev, 8181–8185 for test, 8282–8286 for prod.
   - Update health checks to reference `/healthz` on each service.
5. **Documentation refresh**
   - Update `MVP-Version-2/Coding-Standards-TTRPG-Center.md` and `Requirements-MVP-Version-2.md` repo-structure sections with the final diagram and notes on `.dockerignore`.
   - Amend relevant runbooks or add an ADR describing the environment isolation migration.
   - Provide a short migration checklist in `MVP-Version-2/RELEASE-CHECKLIST.md`.
