# Immutable Image Promotion Guide

This runbook describes how to build, promote, and roll back immutable images for the TTRPG Center platform without relying on GitHub Actions.

## Prerequisites
- Docker CLI installed on the build runner ("container-with-2" or equivalent)
- Access to the target container registry (default: `ghcr.io/ttrpg-center`)
- `ripgrep (rg)` available for compose verification
- Logged-in registry session (`docker login ghcr.io`)

## Build + Push Workflow
1. Choose the environments you want to publish (`dev`, `test`, `prod`).
2. Execute the container runner wrapper (suitable for container-with-2 pipelines):
   ```bash
   # Build dev + test images and push to GHCR
   TTRPG_ENVIRONMENTS="dev test" \
   TTRPG_REGISTRY="ghcr.io/ttrpg-center" \
   scripts/ci/container-build.sh
   ```
3. The wrapper calls `scripts/registry/build-images.py`, which:
   - Builds each service image
   - Tags it as `ghcr.io/ttrpg-center/<service>:YYYYMMDD.<git-sha>`
   - Pushes to the registry (unless `TTRPG_PUSH=false`)
   - Writes `env/<env>/images.lock` with the digest pinned reference
4. `scripts/registry/check-compose-no-build.sh` validates that the compose files resolve with the new digests and contain no `build:` entries.
5. Baseline templates live in `config/image-locks/`; copy the appropriate file into `env/<env>/images.lock` (or let the build script overwrite it) before deployments.

### Dry Run / Local Testing
To validate the build matrix without pushing:
```bash
scripts/registry/build-images.py --env dev --dry-run --registry ghcr.io/ttrpg-center
```
This prints the would-be `images.lock` contents with placeholder digests.

## Deploying Using the New Images
1. Export the generated lock file before running `docker compose`:
   ```bash
   export $(grep -v '^#' env/test/images.lock | xargs)
   docker compose -f env/test/docker-compose.yml up -d
   ```
   The compose files also contain placeholder defaults, so the command succeeds even if you forget to export values; using the lock file ensures the exact digest is used.
2. For local development helper stacks (`docker-compose.dev.yml`, etc.), export the same environment variables or pass `--env-file env/dev/images.lock` when running `docker compose`.

## Promotion Flow
1. **Build in Lower Environment** – Run the build script for `dev` to produce new digests.
2. **Smoke + Regression** – Deploy using the exported `images.lock` and run verification (unit/functional/regression suites).
3. **Promote to Test** – Re-run the build script with `--env test` but reuse the same tag to avoid drift, or manually copy the digest from `env/dev/images.lock` into `env/test/images.lock`.
4. **Promote to Prod** – After approvals, execute the build for `prod` (or copy digests) and commit the updated lock files.
5. **Commit Artifacts** – Copy the generated `env/<env>/images.lock` artifacts into `config/image-locks/<env>.images.lock` (commit the copy) in the release PR. Compose files already contain digest fallbacks, so no additional edits are necessary.

## Rollback Procedure
1. Identify the previous known-good lock file (VCS history for `env/<env>/images.lock`).
2. Re-export the older values:
   ```bash
   export $(grep -v '^#' env/prod/images.lock | xargs)
   docker compose -f env/prod/docker-compose.yml pull
   docker compose -f env/prod/docker-compose.yml up -d
   ```
3. Alternatively, run `scripts/registry/build-images.py --tag <previous-tag>` to relabel the already-pushed image if you need to republish the same bits under a new tag.

## Verification Checklist
- `docker compose -f env/dev/docker-compose.yml config` (and test/prod variants) succeed without local builds
- `rg '^\s*build:' env docker-compose.*.yml` returns no matches
- `env/<env>/images.lock` references the expected digest(s)
- Release notes record the tag/digest mapping and promotion decision

## Artifacts to Commit
- Updated `env/<env>/images.lock` files after each promotion
- Release documentation referencing the tag (see `docs/release/RELEASE_NOTES_TEMPLATE.md`)
- Any automation changes (scripts/registry/**, scripts/ci/container-build.sh)

## Frequently Used Environment Variables
| Variable | Purpose | Default |
| --- | --- | --- |
| `TTRPG_REGISTRY` | Target registry root | `ghcr.io/ttrpg-center` |
| `TTRPG_ENVIRONMENTS` | Space-delimited env list for container-build | `dev test prod` |
| `TTRPG_PUSH` | Set to `false` to skip `docker push` | `true` |
| `TTRPG_IMAGE_TAG` | Override tag when calling build-images.py | auto `YYYYMMDD.<git-sha>` |

Refer to this runbook whenever preparing a release or investigating image drift across environments.

## CI Integration (container-with-2)
- Reference `ci/container-with-2.yml` for a ready-to-import pipeline.
- Ensure secrets `CI_REGISTRY_USERNAME`/`CI_REGISTRY_PASSWORD` map to your registry account.
- Override `TTRPG_ENVIRONMENTS`/`TTRPG_PUSH` per stage (e.g., dev-only dry run).
- Publish the generated `env/<env>/images.lock` artifacts so promotion PRs can consume exact digests.



