# BUG-022 — Result status mismatch: “OK” despite incomplete pipeline

**Severity:** High  
**Component:** Finalizer / summary aggregator  
**Status:** Open  
**Detected in run:** bulk_ingest_20250910_073323.log fileciteturn3file0

## Summary
The final summary can report overall **OK** even when guard warnings indicate an **incomplete pipeline** (e.g., 0 chunks, empty vectors/graphs). This creates false confidence and hides data loss.

## Expected
- Any of the following should force **FAILED** for the source and the batch red/yellow status:
  - `raw_chunk_count == 0` after Pass C (required pass).
  - `vector_count == 0` after Pass D (required pass).
  - Finalizer raises “incomplete pipeline” or similar integrity warning.

## Actual
- “OK” appears even when integrity checks imply failure.

## Proposed Fix
- Finalizer computes **Success Criteria**:
  - `has_toc_entries >= 1` **AND** `raw_chunk_count >= 1` **AND** `vector_count >= 1`.
  - If any are false → status = **FAILED**.
- Add `chunk_to_dict_ratio` to summary and warn below 0.2; below 0.05 → **FAIL**.
- Exit code non-zero if any source failed.

## Acceptance Criteria
- A batch with any failed source returns **non-zero exit code**.
- Per-source status lines correctly show FAILED when integrity thresholds not met.
- CLI prints a concise failure table: `source | failed_pass | reason`.

## Testing
### Unit
- Feed summary aggregator with `vector_count=0` → returns FAILED.
- Verify exit code propagation to shell.

### Functional
- Run a mix: 1 good, 1 failing source → batch exit code != 0, printed failure table lists the failing source/reason.
