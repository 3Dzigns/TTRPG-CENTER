# Command: Promote Artifacts Between Environments
Promote a **tested, immutable build** or specific artifacts from a lower ENV to a higher ENV without data bleed.

## Inputs
- `--from`: dev | test            # source environment
- `--to`:   test | prod           # target environment (must be adjacent)
- `--build`: BUILD_ID             # e.g., 2025-08-25_14-30-15_build-1234
- `--what`: schema | config | embeddings | all (default: all)
- `--dry-run`: true|false (default: true)
- `--notes`: "short description of why/what"

## Preconditions (hard stops on failure)
1. **Adjacency**: Only `dev→test` or `test→prod`.
2. **Build exists & immutable** in `./builds/{BUILD_ID}/`.
3. **DEV gates / UAT pass** for the source ENV:
   - Requirements validation success (REQ-001/002/003).
   - No critical failing tests or open blockers.
4. **Clean status**: `/status` for source ENV shows healthy services.

## Steps (safe & repeatable)
1. **Summarize intent** (from, to, build, what, dry-run).
2. **Load configs** for both ENVs (.env.{from}, .env.{to}) without exposing secrets.
3. **Plan**:
   - If `schema` → compute pending migrations for target (no destructive ops without explicit confirm).
   - If `config` → diff config maps; prepare target-safe overrides.
   - If `embeddings` → list index segments to copy; compute target upserts.
   - If `all` → union of the above.
4. **Dry-run** (default):
   - Print a human-readable plan and a machine-readable plan (`promotion_plan.json`).
   - Abort here if `--dry-run=true`.
5. **Apply** (only when `--dry-run=false`):
   - Execute schema migrations with transactional guards.
   - Sync config maps (non-secret values only).
   - Transfer embedding segments and verify counts/hashes.
   - Update **release pointer** for `{to}` to `{BUILD_ID}`.
6. **Verify**:
   - Hit health endpoints for target ENV.
   - Run smoke tests: query, workflow start, ingestion status read.
7. **Record**:
   - Append a promotion entry to `logs/{to}/promotions.jsonl`.
   - Update `STATUS.md` “Promotions” with a short summary.
   - Emit a promotion report artifact.

## Outputs / Artifacts
- `./artifacts/promotions/{to}/{BUILD_ID}/promotion_report.json`
- `./artifacts/promotions/{to}/{BUILD_ID}/promotion_plan.json` (always written in dry-run)

## Rollback (quick path)
- Use existing `scripts/rollback.ps1 -Env {to}` to revert `{to}` pointer to previous build.
- Never attempt rollback if schema migrations are irreversible; require a forward fix.

## Safety & Guardrails
- **Never** copy secrets; use `.env.{to}` only.
- **No cross-environment data** moves (logs, bugs, tests remain in their ENV).
- **Confirm** any operation that drops/rewrites data (double confirmation in interactive mode).
- **Idempotent**: Re-running with same inputs should be a no-op if already applied.

## Tests (Definition of Done)
- `--dry-run=true` prints a plan and writes `promotion_plan.json`.
- `--dry-run=false` completes with:
  - Target `/health` and `/status` green.
  - Pointer updated to `{BUILD_ID}`.
  - Smoke tests pass (query, workflow, ingestion status read).
  - `promotion_report.json` written with timestamps, hashes, counts.
