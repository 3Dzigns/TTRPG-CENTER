# FR-007 — CI/CD Pipeline (Immutable Builds, Environment Promotion)

## Summary

Design and implement a CI/CD pipeline that automates commit, push, build, and deploy with immutable artifacts and consistent versioning. The pipeline promotes from Code → DEV → TEST through explicit, auditable gates. PROD remains stubbed for now.

## Goals

- Automated: On merge to main, build and publish an immutable image/artifact with version + metadata.
- Deterministic: Rebuilds are reproducible; artifacts are content-addressed and tagged.
- Observable: Pipeline emits structured logs and attaches build metadata (git SHA, build time, source branch, build number).
- Promote/Demote: Manual approval jobs to promote from DEV to TEST and rollback capabilities to any previous version.

## Non-Goals

- PROD deployments (stub only).
- Complex canary/blue‑green strategies (later FRs).

## Versioning Strategy

- Semver-like application version (X.Y.Z) tracked in `VERSION` file.
- Build metadata appended: `X.Y.Z+<gitSHA>-<buildTimestamp>`.
- Docker image tags:
  - `ttrpg/app:<X.Y.Z>` (immutable), `ttrpg/app:<gitSHA>`, and floating `ttrpg/app:dev` and `:test` for latest per env.

## Pipeline Stages (GitHub Actions example)

1. CI (on PR + push):
   - Lint, unit tests, security scans (Bandit).
   - Build app image (multi-stage Dockerfile) and run smoke tests in container.
   - On PR: publish to ephemeral `ghcr.io/<org>/ttrpg/app:<gitSHA>`.
2. Build & Publish (on merge to main):
   - Compute version from `VERSION` + git SHA; update labels.
   - Build/push immutable tags: `<X.Y.Z>` and `<gitSHA>` to registry (GHCR/Artifactory/ECR).
   - Upload SBOM (optional) and artifact checksums.
3. Deploy DEV:
   - Pull image `<X.Y.Z>` to DEV cluster/host.
   - `docker compose -f docker-compose.dev.yml up -d` with the pinned image tag.
   - Post-deploy smoke test (`/healthz`).
4. Promote TEST (manual approval):
   - Pull same `<X.Y.Z>` to TEST.
   - Bring up TEST compose (or K8s) with pinned image.
   - Run integration test suite.
5. Rollback (manual):
   - Select prior `<X.Y.Z>` from registry and redeploy to DEV/TEST with one click.
6. PROD (stub):
   - Job scaffold only; disabled by default.

## Required Files/Changes

- `.github/workflows/ci.yml` — CI (lint, tests).
- `.github/workflows/release.yml` — Build/publish immutable images; deploy DEV; promote TEST (approval).
- `VERSION` — current semver.
- `scripts/release.ps1` — helpers to tag, label, and push images.
- Compose env files for DEV/TEST (`.env.dev`, `.env.test`) with non‑secret defaults; secrets from CI/CD vault.

## Acceptance Criteria

- On push to main:
  - CI passes; image built and pushed with tags `<X.Y.Z>` and `<gitSHA>`.
  - DEV deploy uses an immutable tag and passes smoke tests.
- On approval:
  - TEST deploy uses the exact same `<X.Y.Z>`.
  - Integration tests pass.
- Rollback:
  - Operator can deploy any prior `<X.Y.Z>` to DEV/TEST via a workflow input.
- Auditability:
  - Build and deploy logs include version, SHA, environment, and timestamps.

## Rollback & Promotion Policy

- Promote only the exact image digest built from main.
- Never retag mutable `latest` for environment pins; only use immutable `<X.Y.Z>` or `<digest>`.
- Store changelog and SBOM per release for traceability.

## Future Work (Follow‑ups)

- PROD environment gating and change management.
- Canary/Blue‑Green strategies.
- Database migration orchestration with auto‑backup/restore hooks.

