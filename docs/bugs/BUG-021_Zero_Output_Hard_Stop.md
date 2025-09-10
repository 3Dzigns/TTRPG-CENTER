# BUG-021 — Hard-stop pipeline when a pass yields zero output (no downstream work)

**Severity:** Critical  
**Component:** Pass controller / orchestrator  
**Status:** Open  
**Detected in run:** bulk_ingest_20250910_073323.log fileciteturn3file0

## Summary
If Pass C (extraction) produces **0 chunks**, the orchestrator continues to Pass D/E/F. This should be a **hard stop** per-source, with a clear failure state, because there is nothing to vectorize or graph.

## Impact
- Wasted compute on Pass D/E/F.
- Misleading “OK” summaries despite missing data.
- Masked root cause (tooling/config).

## Steps to Reproduce
1. Run ingest with Poppler absent.
2. Observe Pass C output = 0; pipeline still executes downstream passes.

## Expected
- Controller checks **pass output counts** after each pass:
  - If output == 0 **and** the pass is required → **fail the source** and stop further passes.
  - Record `failure_reason`, `failed_pass` in run metadata.

## Actual
- No gating; downstream passes run with empty inputs.

## Proposed Fix
- Introduce a **Guardrail policy** in orchestrator:
  - Required passes: A (ToC), C (Unstructured), D (Vectors), E (Graph).
  - Thresholds:  
    - After Pass C: `raw_chunk_count > 0`  
    - After Pass D: `vector_count > 0`
  - If threshold not met → **HALT** source, mark **FAILED**.
- Emit a **single, prominent** log line e.g.:
  - `[FATAL][job_id] Pass C produced 0 chunks — aborting source after Pass C.`

## Acceptance Criteria
- When Pass C yields 0 chunks, no D/E/F logs occur for that source.
- Job summary lists the source under **FAILED** with reason “Zero output at Pass C”.
- Metrics show zero time spent in D/E/F for failed sources.

## Testing
### Unit
- Simulate `pass_c_result.count = 0` → expect `abort_source()` called, summary FAILED.

### Functional
- Run with intentionally bad PDF: pipeline halts after C; no vector/graph artifacts created.

### Regression
- Good PDFs proceed normally; no change in success path behavior.
