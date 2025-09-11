# FR-005 — Modularize Ingestion by Pass with Strict Gates (A–F)

**Date:** 2025-09-11 14:25:17  
**Status:** Proposed  
**Owner:** Platform / Ingestion

## Summary
Refactor the monolithic `bulk_ingestion.py` into **pass-scoped modules** (A–F) with **hard gates** between passes. Each pass exposes a clear interface, emits contract-defined artifacts, and **cannot begin unless the previous pass has succeeded** and produced valid outputs. Add a lightweight **orchestrator** that sequences passes, supports resume, and enforces contracts (schemas, counts, checksums).

> Passes (current 6‑pass model): **A TOC/Dictionary Prime → B Large-File Splitter → C Unstructured Parse/Chunk → D Enrich (Haystack) → E Graph Compile (LlamaIndex) → F Cleanup/Validate**.

---

## Goals
- Split `bulk_ingestion.py` into modular packages: `ttrpg.ingest.pass_a` … `pass_f` plus `ttrpg.ingest.runner`.
- Define **pass contracts** (input → output schemas, side effects, success criteria).
- Enforce **gating**: Pass N+1 runs **only if** Pass N status is `SUCCESS` and outputs validate.
- Support **resume-from-pass** and **run-subset** with idempotent writes.
- Emit **structured telemetry** (NDJSON logs, timing, counts, token usage where applicable).
- Keep artifacts under `artifacts/ingest/{env}/{job_id}/pass*.json` with a `manifest.json` index.
- Zero changes to business semantics; this is an internal refactor that **improves reliability & observability**.

## Non-Goals
- Altering the actual algorithms of chunking/enrichment/graph beyond necessary contract cleanups.
- Replacing third-party tools; existing integrations remain but are wrapped behind pass adapters.

---

## Architecture & Directory Layout
```
ttrpg/
  ingest/
    runner.py           # Orchestrator (CLI + sequencing + gates)
    contracts.py        # Pydantic/TypedDict schemas + validators
    state.py            # Job manifest, pass statuses, resume markers
    io.py               # artifact read/write helpers (atomic)
    pass_a/
      __init__.py
      pass_a.py         # run(job)
    pass_b/
      pass_b.py
    pass_c/
      pass_c.py
    pass_d/
      pass_d.py
    pass_e/
      pass_e.py
    pass_f/
      pass_f.py
```

---

## Contracts (Examples)
### Common Job Manifest (`manifest.json`)
```json
{{
  "job_id": "job_2025-09-11T02-00-00",
  "env": "dev",
  "passes": {{
    "A": {{"status": "SUCCESS|FAILED|SKIPPED", "started": "...", "ended": "...", "artifacts": ["passA_toc.json"]}},
    "B": {{"status": "PENDING"}}
  }},
  "source_sha_map": {{"<source_id>": "sha256:..."}},
  "metrics": {{"wall_s": 0, "tokens": 0}}
}}
```

### Pass Contracts (schema sketch)
- **Pass A (TOC/Prime)** → `passA_toc.json`: `[{{"source_id": "...", "sections":[{{"title":"...", "page_start": 1}}]}}]`
- **Pass B (Split)** → `passB_splits.json`: `[{{"source_id":"...", "parts":[{{"path":"...", "size_mb": 12.3}}]}}]`
- **Pass C (Chunk)** → `passC_chunks.json`: `[{{"chunk_id":"...", "source_id":"...", "page": 12, "text":"...", "metadata":{{...}}}}]`
- **Pass D (Enrich)** → `passD_enriched.json`: same IDs plus added fields (`normalized`, `entities`, …)
- **Pass E (Graph)** → `passE_graph.json`: nodes/edges referencing `chunk_id` / `source_id`
- **Pass F (Cleanup/Validate)** → `passF_cleanup.json`: `{{"stale_deleted": N, "fixes":[...]}}`

All artifacts validated with **Pydantic** (or `jsonschema`).

---

## Orchestrator Behavior (Gated Sequencing)
1. Load/create `manifest.json`, set `PENDING` for all passes.
2. For each pass in A…F:
   - **Gate check**: ensure previous pass `status == SUCCESS` and required artifacts exist + validate.
   - Run `pass_x.run(job)` with explicit inputs.
   - On success: write artifacts atomically, mark `SUCCESS` with timestamps and metrics.
   - On failure: mark `FAILED`, stop pipeline, return non‑zero exit.
3. Resume: `runner --resume-from C` runs `C..F` if A,B already `SUCCESS` and artifacts validate.

---

## Public APIs & CLI
```bash
# Full run
python -m ttrpg.ingest.runner --env dev --uploads "C:\TTRPG\uploads" --job-dir "...\artifacts\ingest\dev\job_..."

# Resume from D (after fixing an issue in C)
python -m ttrpg.ingest.runner --resume-from D --job-dir "...\job_..."

# Run a subset (A..C) for quick dev iteration
python -m ttrpg.ingest.runner --passes A,C --job-dir "...\job_..."
```

---

## Python Skeletons

### contracts.py
```python
from typing import List, Dict, Literal, Optional
from pydantic import BaseModel, Field, ValidationError

PassName = Literal["A","B","C","D","E","F"]

class PassRecord(BaseModel):
    status: Literal["PENDING","SUCCESS","FAILED","SKIPPED"]
    started: Optional[str] = None
    ended: Optional[str] = None
    artifacts: List[str] = []

class Manifest(BaseModel):
    job_id: str
    env: str
    passes: Dict[PassName, PassRecord]
    source_sha_map: Dict[str,str] = {{}}
    metrics: Dict[str, float] = {{}}
```

### runner.py
```python
from .contracts import Manifest, PassRecord
from . import pass_a, pass_b, pass_c, pass_d, pass_e, pass_f
from datetime import datetime

PASS_IMPLS = dict(A=pass_a, B=pass_b, C=pass_c, D=pass_d, E=pass_e, F=pass_f)

def run(job_dir: str, env: str, resume_from=None, subset=None) -> int:
    m = load_or_init_manifest(job_dir, env)
    order = ["A","B","C","D","E","F"]
    if subset:
        order = [p for p in order if p in subset]
    if resume_from:
        order = order[order.index(resume_from):]

    for i,p in enumerate(order):
        if i>0:
            prev = order[i-1]
            assert m.passes[prev].status == "SUCCESS", f"Gate blocked: {prev} not SUCCESS"
            assert validate_artifacts(prev, m), f"Gate blocked: {prev} artifacts invalid"
        mark_start(m, p)
        try:
            PASS_IMPLS[p].run(job_dir=job_dir, env=env, manifest=m)
            validate_artifacts(p, m)  # strict validation
            mark_success(m, p)
        except Exception as e:
            mark_failed(m, p, str(e))
            save_manifest(m, job_dir)
            return 1
        save_manifest(m, job_dir)
    return 0
```

### pass template (e.g., `pass_c/pass_c.py`)
```python
def run(job_dir: str, env: str, manifest):
    # read inputs (from A/B artifacts), process, write outputs
    # ensure idempotent: same inputs -> same outputs
    # update manifest.passes["C"].artifacts = ["passC_chunks.json"]
    return
```

---

## User Stories & Acceptance Criteria

### US‑005.1 — Modular Pass Interfaces
**As a** developer, **I want** each pass as a module with a `run(job_dir, env, manifest)` entrypoint, **so that** the pipeline is maintainable.
- **AC:** `import ttrpg.ingest.pass_c` exposes `run(...)` and writes its artifact(s).

### US‑005.2 — Hard Gating Between Passes
**As an** operator, **I want** Pass N+1 to start only after Pass N succeeds and outputs validate, **so that** data integrity is maintained.
- **AC:** Orchestrator raises a clear error if a required prior pass is not `SUCCESS` or artifacts fail schema checks.

### US‑005.3 — Resume & Subset Execution
**As a** developer, **I want** to resume from a specific pass or run a subset, **so that** I can iterate quickly.
- **AC:** `--resume-from` executes only remaining passes; `--passes A,C` runs just A and C with gates enforced for C.

### US‑005.4 — Idempotency & Atomic Writes
**As a** reliability engineer, **I want** deterministic outputs and atomic artifact writes, **so that** interrupted runs don’t leave corrupted state.
- **AC:** Re-running a pass with identical inputs produces identical artifacts; files written via temp‑rename.

### US‑005.5 — Telemetry & Metrics
**As a** QA, **I want** per‑pass timing, counts, and error summaries in NDJSON, **so that** we can debug and measure.
- **AC:** Each pass logs start/end, counts (chunks, pages), and errors; manifest aggregates totals.

---

## Test Plan

### Unit
- Contracts validate example artifacts for each pass.
- Orchestrator gate check raises when prior pass is not `SUCCESS`.
- `io.atomic_write(path, bytes)` writes via temp and rename.

### Functional
- Full A→F run produces all artifacts and `manifest.json` with `SUCCESS` for all passes.
- Inject invalid `passC_chunks.json` → D is **blocked** with clear error.
- Resume from E after C fix → runs E,F; A–D statuses unchanged.

### Regression
- Golden manifests for canonical sources; outputs diff only on intended changes.
- CLI flags stable (`--resume-from`, `--passes`).

### Security
- Input sanitization for file paths; deny `..` traversal.
- Logs redact PII; schema prevents secret leakage.
- RBAC unchanged (deferred to environment), but runner exits non‑zero on permission errors.

---

## Migration Plan
1. Create modules and move code out of `bulk_ingestion.py` in small PRs (A/B first).
2. Introduce contracts and validators; backfill schemas for existing artifacts.
3. Wire runner and gates; add `--resume-from` and `--passes`.
4. Shadow‑run new pipeline in DEV; compare artifacts/manifests against legacy.
5. Flip default to new runner; keep legacy behind a `--legacy` flag for one release cycle.
6. Remove legacy path once CI & nightly jobs are green for 2 weeks.

---

## Definition of Done
- `bulk_ingestion.py` replaced by `ttrpg.ingest.runner` + `pass_*` modules.
- All six passes **gate‑enforced** with contracts and validators.
- CI green on unit/functional/regression/security; nightly jobs succeed using the new runner.

## Implementation Tasks by User Story

### US-005.1 — Modular Pass Interfaces
- Tasks:
  - Create package structure `ttrpg/ingest/pass_{a..f}` with `run(job_dir: str, env: str, manifest)` entrypoints.
  - Extract existing logic from `bulk_ingestion.py` into the respective pass modules; remove cross-pass globals.
  - Centralize artifact IO in `ttrpg.ingest.io` with helpers to read/write artifacts.
  - Add minimal stubs for each pass that write placeholder artifacts to bootstrap testing.
- Tests:
  - Unit: each pass module is importable and exposes `run` with correct signature.
  - Functional: stub run produces pass-specific artifact and updates manifest.

### US-005.2 — Hard Gating Between Passes
- Tasks:
  - Implement `validate_artifacts(pass_name, manifest)` enforcing schema and presence before allowing next pass.
  - Enforce `SUCCESS` status and artifact validation for N → N+1 transitions with clear error messages.
- Tests:
  - Unit: gating function blocks when prior pass not `SUCCESS` or artifacts invalid.
  - Functional: injecting invalid `passC` artifacts stops `passD` with non-zero exit and readable error.

### US-005.3 — Resume & Subset Execution
- Tasks:
  - Add CLI flags `--resume-from <A..F>` and `--passes A,C` with validation and help text.
  - Orchestrator computes pass order accordingly and persists/resumes manifest state.
- Tests:
  - Functional: `--resume-from E` runs E,F only and leaves A–D statuses unchanged.
  - Functional: `--passes A,C` runs A, then gates and runs C only if A is `SUCCESS`.

### US-005.4 — Idempotency & Atomic Writes
- Tasks:
  - Ensure deterministic outputs (sorted inputs, stable UUIDs/hashes where applicable).
  - Implement `atomic_write(path, data)` using temp files + rename; guarantee fsync where available.
  - Make passes re-runnable without leftover temp artifacts or non-deterministic diffs.
- Tests:
  - Unit: `atomic_write` writes via temp and results in complete file after rename.
  - Functional: re-running a pass with same inputs yields byte-identical artifact files (hash equal).

### US-005.5 — Telemetry & Metrics
- Tasks:
  - Add NDJSON logging per pass with start/end, counts, durations, and error summaries.
  - Aggregate per-pass metrics into manifest under `metrics` and per-pass records.
  - Expose `--log-level` and `--log-file` options; default to job-local logs.
- Tests:
  - Unit: log records include required fields; manifest aggregates totals.
  - Functional: full run produces logs for all passes; timings are non-zero and ordered.
