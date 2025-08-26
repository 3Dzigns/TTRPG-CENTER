# Command: Bugs (Open/Resolve)

## Open (from latest review for HEAD)
- Run: `python scripts/ci/make_bugs_from_review.py --sha $(git rev-parse HEAD)`

## Resolve
- Edit the relevant `bugs/<HEAD_SHA>/CR-xxx_*.md` file(s):
  - Change `**Status:** open` → `**Status:** resolved`
  - Fill in “Fix Notes”
- Commit the bug file edits with your code changes:
  - `git add bugs/<HEAD_SHA>/*.md`
  - `git commit -m "fix: resolve CR-xxx (tests+docs) [refs RAG-xxx]"`
  - `git push`
