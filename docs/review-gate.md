# Review Gate Directive

This document defines the mandatory process for handling **AI Peer Review results** before any new user request or commit is executed.

---

## 1. Pre-Execution Workflow

1. **Pull Latest Repo**
   - Always `git pull origin main` before executing any user input.
   - This ensures the local working copy includes the latest code and review files.

2. **Locate Review File**
   - Path: `/reviews/ai-review-report.md`
   - This file is generated automatically by the GitHub Actions pipeline after each commit.

3. **Check Review Status**
   - If the latest review report contains unresolved issues:
     - Parse all items marked as **ISSUE** or **FAIL**.
     - Create a bug entry for each unresolved issue.

---

## 2. Bug Handling

1. **Bug Bundle Location**
   - All bug bundles are stored under: `/bugs/`
   - Format: `bug_<timestamp>.json`

2. **Bug Resolution Workflow**
   - Each bug must be:
     - Investigated,
     - Fixed in the code,
     - Marked as resolved in the bug file.

3. **Commit After Bug Fixes**
   - Once all bugs are addressed:
     - `git add .`
     - `git commit -m "fix: resolve peer review issues"`
     - `git push origin main`
   - This triggers a **new peer review cycle**.

---

## 3. Execution Rules

- **DO NOT** process any new user input or feature request until:
  - The latest review cycle has completed, AND
  - All issues are resolved and committed.

- **Every task sequence begins with review resolution.**

---

## 4. Review Modes

- Review mode is controlled by `review_mode.txt` in the root:
  - `diff` → Only review new changes since last commit
  - `full` → Run a full project review on next commit

- After execution, always reset mode back to `diff`.

---

## 5. Required Context for Review

Each review cycle must include the following files in its bundle:

- `docs/documentation.md`
- `docs/requirements/*.json`
- `docs/requirements/*.schema.json`
- `README.md`
- `LAUNCH_GUIDE.md`
- `API_TESTING.md`
- `STATUS.md`
- `.claude/commands/*.md`
- `review-gate.md` (this file)

---

## 6. Status Page Updates

- Always update `/status/review_status.json` after each cycle:
  - `last_review_commit`
  - `review_mode_used`
  - `unresolved_issues_count`
  - `bugs_opened_count`
  - `bugs_resolved_count`

---

## 7. Golden Rule

**Claude must never skip peer review gates.**  
If a review report is missing, corrupted, or not yet available:
- Stop,
- Wait until it is generated,
- Then continue.

---

**End of Review Gate Directive**
