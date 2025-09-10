# BUG-023 — Windows installer + documentation gaps for Poppler/Tesseract & PATH

**Severity:** Medium  
**Component:** Developer experience (DX) — setup scripts & docs  
**Status:** Open  
**Detected in run:** bulk_ingest_20250910_073323.log (indirect) fileciteturn3file0

## Summary
The repository doesn't provide a **guided setup** for Poppler/Tesseract on Windows nor a script that amends PATH for CI/local runners. Contributors frequently hit missing-binary failures that only surface mid-pipeline.

## Proposed Fix
- Add a **setup_windows.ps1** that:
  - Detects existing installs; if absent, downloads vetted builds (or prompts) and sets PATH for user/system scope.
  - Persists PATH changes and prints “Next steps”.
- Extend **requirements/README** with explicit steps, screenshots, and verification commands.
- Add `--verify-deps` CLI flag to run just the preflight checks.

## Acceptance Criteria
- New devs can run `.\scripts\setup_windows.ps1` and pass `--verify-deps` successfully on first run.
- CI self-hosted runner passes preflight without manual edits.

## Testing
- Script idempotency: multiple runs do not duplicate PATH entries.
- Negative test: simulate locked-down machine → script fails gracefully with remediation tips.
