# Command: Pre-Run Sync (Must run before any user request)

## Goals
- Ensure the working tree and review status are current before starting.
- Generate/refresh local bug files from the latest review JSON for HEAD.

## Steps
1) **Git sync**
   - Run: `git fetch --all --prune`
   - Run: `git status` → if not on `main`, stay on current feature branch.
   - If the working tree is dirty, either `git stash -u` (if safe) or STOP and ask for operator guidance.

2) **Ensure local review artifacts exist for HEAD**
   - Determine `HEAD_SHA = git rev-parse HEAD`.
   - If `docs/reviews_json/HEAD_SHA.json` is missing:
     - If online: run `powershell -ExecutionPolicy Bypass -File scripts/ci/Fetch-Review.ps1`.
     - If still missing: STOP and request a new push/CI run.

3) **Gate check**
   - Open `docs/review_status.md` and verify it references **HEAD_SHA**.
   - If STATUS is FAIL or `HIGH_ISSUES > 0`, proceed to step 4 (bug creation) and then STOP after producing a fix plan.
   - If STATUS is OK, continue to step 4 anyway (some issues can be medium/low).

4) **Create/refresh local bug files from review JSON**
   - Run: `python scripts/ci/make_bugs_from_review.py --sha HEAD_SHA`
   - This will create/update `bugs/HEAD_SHA/CR-xxx.md` files for each issue.

5) **Output**
   - Print the path list of created/updated bug files.
   - If any **high** severity issues exist, STOP and produce a step-by-step fix plan that references the created bug files.
