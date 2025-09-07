# BUG-009: extract_murderous_command.py Is Unreferenced and Likely Stale

## Summary
`extract_murderous_command.py` appears to be a standalone helper script that is not imported or called by any runtime code or tests. It may be dead code or should be moved under `scripts/` with documentation.

## Environment
- Component: Standalone script at repo root
- Date Reported: 2025-09-06
- Severity: Low (cleanup/clarity)

## Evidence
- `rg` shows only self-reference in the file (`if __name__ == "__main__"` path). No imports elsewhere.

## Expected Behavior
- Either referenced via a CLI workflow in `scripts/` or removed if obsolete.

## Actual Behavior
- Sits in repo root without documentation or integration.

## Fix Required
- Move to `scripts/` with README and example usage, or remove if no longer needed.

## Priority
Low

## Related Files
- `extract_murderous_command.py:1`

