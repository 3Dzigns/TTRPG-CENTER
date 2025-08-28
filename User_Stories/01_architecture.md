# Architecture & Environment Management — User Stories & Test Plan

**Scope:** Multi-environment setup with immutable builds and promotion workflow

## User Stories

- As a **stakeholder**, I want **Support DEV, TEST, and PROD environments with distinct ports (8000, 8181, 8282)** (**ARCH-001**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Immutable build system with timestamped artifacts** (**ARCH-002**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **PowerShell automation scripts for build/promote/rollback operations** (**ARCH-003**, priority=high), so that we meet the MVP acceptance criteria.

## Acceptance Criteria

### ARCH-001: Support DEV, TEST, and PROD environments with distinct ports (8000, 8181, 8282)
- [ ] DEV runs on port 8000
- [ ] TEST runs on port 8181 with UAT features
- [ ] PROD runs on port 8282 with ngrok exposure
### ARCH-002: Immutable build system with timestamped artifacts
- [ ] Builds stored in /builds/<timestamp>_build-#### format
- [ ] Build manifests include source hash and metadata
- [ ] Promotion system using pointer files
### ARCH-003: PowerShell automation scripts for build/promote/rollback operations
- [ ] build.ps1 creates immutable build artifacts
- [ ] promote.ps1 moves builds between environments
- [ ] rollback.ps1 reverts to previous build

## Test Plan

### Unit Tests

- ARCH-001: Unit tests for core logic/config implementing 'Support DEV, TEST, and PROD environments with distinct ports (8000, 8181, 8282)'.
- ARCH-002: Unit tests for core logic/config implementing 'Immutable build system with timestamped artifacts'.
- ARCH-003: Unit tests for core logic/config implementing 'PowerShell automation scripts for build/promote/rollback operations'.

### Functional (E2E) Tests

- ARCH-001: End-to-end scenario demonstrating all acceptance criteria.
- ARCH-002: End-to-end scenario demonstrating all acceptance criteria.
- ARCH-003: End-to-end scenario demonstrating all acceptance criteria.

### Regression Tests

- ARCH-001: Snapshot/behavioral checks to prevent future regressions.
- ARCH-002: Snapshot/behavioral checks to prevent future regressions.
- ARCH-003: Snapshot/behavioral checks to prevent future regressions.

### Security Tests

- Adjacent-only promotions (dev→test→prod) enforced; dry-run plan mandatory.
- No secrets in Git/CI artifacts; use `.env.*` and masked logs.
- Ports bound only to localhost in DEV/TEST by default; PROD behind ngrok tunnel.

## Example Snippet

```powershell
# Build → Promote → Rollback lifecycle
.\scripts\build.ps1
.\scripts\promote.ps1 -BuildId "2025-08-25_14-30-15_build-1234" -Env test -DryRun
.\scripts\promote.ps1 -BuildId "2025-08-25_14-30-15_build-1234" -Env test
.\scripts\rollback.ps1 -Env test
```
