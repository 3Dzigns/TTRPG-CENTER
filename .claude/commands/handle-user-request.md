# Command: Handle User Request (Respect Review Gate)

## ALWAYS run `Pre-Run Sync` first.
Then follow this loop:

1) **List open bugs for HEAD_SHA**
   - HEAD_SHA := `git rev-parse HEAD`
   - Bug dir: `bugs/HEAD_SHA`
   - If any file in that folder has `**Status:** open` and **Severity: high** → produce and execute a fix plan BEFORE handling new user work. Commit fixes and STOP for review.

2) **Execute the user request**
   - Plan minimal safe changes aligned to requirements.
   - Implement changes with small, logical commits that reference requirement IDs and bug IDs (if fixing).
   - Keep working tree clean and tests passing.

3) **Resolve bugs you fixed**
   - For every bug you addressed, open its markdown file and change `**Status:** open` → `**Status:** resolved`.
   - Add concise “Fix Notes” detailing the resolution and tests added.

4) **Commit and push**
   - Commit message format:
     ```
     feat|fix(scope): summary
     Refs: CR-xxx, CR-yyy; RAG-001, ADM-002
     ```
   - Push branch. The CI will run the review and update `docs/review_status.md`.

5) **Stop and wait for review**
   - Do NOT continue to the next task until the review for the new HEAD is **OK** (see Review Gate).
