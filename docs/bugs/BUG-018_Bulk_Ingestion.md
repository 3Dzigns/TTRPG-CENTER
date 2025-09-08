# BUG-018: Bulk Ingestion — Pass B fails with JSON parse error; unsafe SSL bypass; noisy DB upserts

**Reported:** 2025-09-08 03:34 UTC  
**Environment:** DEV (`env\dev`)  
**Components:** `bulk_ingest`, `pass_b_enricher`, `toc_parser`, `dictionary_initializer`, `astra_loader`  
**Datastore:** AstraDB collections `ttrpg_chunks_dev`, `ttrpg_dictionary_dev`

---

## Summary

During a bulk ingestion run, **Pass B enrichment repeatedly fails** with `Expecting value: line 1 column 1 (char 0)` when reading the Pass A chunks JSON for multiple titles (e.g., *Dungeon Master's Guide.pdf*, *Monster Manual.pdf*, *Player's Handbook.pdf*). The run also logs **SSL verification bypass** as active, and produces **extremely chatty** repeated `findOneAndReplace` calls for dictionary terms, which may be harming throughput.

---

## Evidence (log excerpts)

- Pass B failure on multiple books (empty/invalid JSON?):  
  `pass_b_enricher - ERROR - Pass B enrichment failed: Expecting value: line 1 column 1 (char 0)`  
  followed by ingest marked as `FAIL` for each affected title.

- SSL bypass in effect (unsafe outside DEV):  
  `ssl_bypass - WARNING - DEVELOPMENT MODE: Bypassing SSL certificate verification for external APIs` and  
  `ssl_bypass - WARNING - SSL certificate verification bypass ACTIVE - development only`

- Potentially misleading deletion count when emptying Astra collection:  
  `Collection ttrpg_chunks_dev emptied successfully (deleted -1 documents)`

- Very high volume of `findOneAndReplace` calls on `ttrpg_dictionary_dev`, often overlapping timestamps, indicating low batching or missing dedupe.

> Full log file: `bulk_ingest_20250907_222630.log`

---

## Affected Titles Observed
- *Dungeon Master's Guide.pdf* — Pass B fail
- *Monster Manual.pdf* — Pass B fail
- *Player's Handbook.pdf* — Pass B fail
- *Cyberpunk v3 - CP4110 Core Rulebook.pdf* — Dictionary init OK; Pass A restarted later
- *Eberron Campaign Setting.pdf* — Dictionary init OK; Pass A started

---

## Steps to Reproduce

1. Run bulk ingestion in DEV with existing artifact directories present (resume mode enabled).
2. Ensure Pass A output files exist for several titles (so Pass A is skipped on resume).
3. Observe Pass B starting with the path like:  
   `artifacts\ingest\dev\job_<title>_<timestamp>\..._pass_a_chunks.json`
4. Pass B raises JSON parse error at line 1, col 1 for multiple titles.

---

## Expected vs Actual

- **Expected:**  
  - Pass B reads a **valid, non-empty** `*_pass_a_chunks.json` produced by Pass A and enriches chunks.  
  - Optional: If Pass A output is missing/corrupt, the system **recomputes Pass A** or **fails gracefully** with a clear cause.

- **Actual:**  
  - Pass B attempts to read a file that appears **empty or invalid**, then fails with a generic JSON parse error.  
  - The orchestrator marks each book as `FAIL` but does **not attempt auto-recovery** (e.g., re-run Pass A).  
  - Parallel dictionary upserts run very noisily, possibly contending for bandwidth/limits.

---

## Impact

- **High:** Bulk ingestion pipeline cannot progress beyond Pass B for multiple core titles; dictionary noise may **throttle** network/API throughput; SSL bypass is risky if config accidentally leaks into higher environments.

---

## Triage & Suspected Root Causes

1. **Stale/empty Pass A artifacts on resume**
   - Pass A is skipped due to “output exists,” but the JSON may be **empty, truncated, or from an older schema**.
   - The error at column 1 suggests **0-byte or non-JSON** content.

2. **Race condition / partial writes**
   - Pass A might write the JSON asynchronously without atomic rename, letting Pass B open a **half-written** file.

3. **Path encoding or quoting issues**
   - Titles with apostrophes/parentheses (e.g., `Dungeon Master's Guide.pdf`) may cause **path mishandling** or sanitizer bugs that lead to the wrong file being opened.

4. **Over-aggressive cleanup or pre-run emptying**
   - Collections are emptied at start; if resume state references artifacts that were cleaned or moved, the pipeline may mis-detect readiness.

5. **Dictionary upsert flood**
   - Excessive `findOneAndReplace` calls imply **missing batching** and may contribute to **rate-limit collisions** elsewhere.

---

## Proposed Fixes

1. **Artifact validation gate before Pass B**
   - Verify `*_pass_a_chunks.json` exists, **size > 0**, and **valid JSON schema** before starting Pass B.
   - If invalid, **auto re-run Pass A** (force recompute) and overwrite artifacts atomically.

2. **Atomic file writes for Pass A outputs**
   - Write to `*.tmp` then `os.replace()` to final name to avoid Pass B reading partial files.

3. **Resume integrity check**
   - On resume, compute a quick checksum/mtime and compare against a small `manifest.json` per job to ensure artifacts are **consistent** and from this build version. If mismatch, re-run Pass A.

4. **Path sanitizer & quoting**
   - Normalize titles to filesystem-safe IDs and handle apostrophes/parentheses consistently across all passes.

5. **Dictionary batching and deduplication**
   - Batch term upserts; use `bulk_write`/`updateMany` style where possible; dedupe terms per document before DB round-trips. Add a **rate limiter** or queue.

6. **Accurate deletion reporting**
   - Fix delete-many result handling to avoid returning `deleted -1`; surface real counts or “unknown.”

7. **Config guardrails**
   - Ensure SSL bypass can **never** be enabled outside DEV. Add a **hard assert** on environment plus a big banner in logs.

8. **Retry with backoff for transient JSON reads**
   - If JSON read fails at column 1, wait 250–500 ms and retry up to N times in case of racing writes.

---

## Acceptance Criteria

- Pass B **never** starts unless the Pass A JSON is valid by schema.  
- On encountering invalid/empty Pass A JSON, the orchestrator **re-runs Pass A automatically** and succeeds end-to-end on the same input set.  
- Dictionary inserts occur via **batched, deduped** operations; total DB calls per doc reduced by ≥80%.  
- Collection emptying reports **correct deletion counts**.  
- SSL bypass is **impossible** in TEST/PROD (guardrails tested).  
- A regression test simulates **resume with corrupt/0-byte Pass A JSON** and confirms auto-heal.  

---

## Attachments / Notes

- Log file: `bulk_ingest_20250907_222630.log` (DEV)  
- Titles affected: DMG, Monster Manual, Player’s Handbook (Pass B failures); others show dictionary init OK.

---

## Update (2025-09-08 03:43 UTC): Pass Redefinition, Upsert/Enrich Plan, and Concurrency Barrier

### New Pass Definitions
- **Pass A — Initial ToC Parse (Prime Dictionary):**
  - Parse Table of Contents and high-confidence headings to build a **seed dictionary** of section names, page ranges, and canonical spell/feat/class names.
  - **Writes:** Upsert **dictionary terms** only (idempotent, deduped). No chunk upserts.
  - **Artifacts:** `*_pass_a_dict.json`, `manifest.json` (with checksums/mtime).

- **Pass B — Logical Split (>25 MB):**
  - If source PDF exceeds **25 MB**, split by **logical sections** (chapters/parts) guided by Pass A’s ToC; otherwise skip.
  - **Writes:** Upsert/update **job manifest** only; no chunks. Store split parts in artifacts dir with content hashes.
  - **Artifacts:** `*_parts/*.pdf`, `split_index.json` (maps sections→parts), updated `manifest.json`.

- **Pass C — Unstructured.io (Extraction):**
  - Run Unstructured.io on each part (or whole file if not split) to extract **section-aware blocks** at paragraph/small-section granularity.
  - **Writes:** Upsert **RAW chunks** into `ttrpg_chunks_dev` with flags `stage:"raw"`, `('source_id', 'section_id', 'page_span', 'toc_path')`. No embeddings yet.
  - **Artifacts:** `*_pass_c_raw_chunks.jsonl` with schema-validated records.

- **Pass D — Haystack (Vector & Lite Enrichment):**
  - Perform **embedding/vectorization**, light **NER/keyword** extraction, dedupe/merge small fragments, attach **vector_ids**.
  - **Writes:** **Upsert** chunks with vectors (`stage:"vectorized"`), add `entities`, `keywords`, `embedding_model`, `chunk_hash`. Batch **bulk_write** with retry/backoff.
  - **Artifacts:** `*_pass_d_vectors.jsonl`, `enrichment_report.json` (counts, reductions, dedupe ratios).

- **Pass E — LlamaIndex (Graph & Cross-Refs):**
  - Build **document graph** (sections→subsections→chunks), **cross-references** (spells ↔ classes/feats/rules), and ToC lineage.
  - **Writes:** Upsert **graph metadata** to `ttrpg_dictionary_dev` (terms, aliases, relations) and update chunks with `graph_refs`, `toc_lineage`, `related_ids`; mark `stage:"graph_enriched"`.
  - **Artifacts:** `graph_snapshot.json`, `alias_map.json`, `relationship_edges.jsonl`.

- **Pass F — Clean Up (Finalize):**
  - Validate manifests, **atomically** move temp files, purge partials, and write accurate **deletion counts**.
  - **Writes:** Finalize `manifest.json` with `completed_passes`, `checksums`, and `run_summary`.

### Upsert / Enrichment Responsibilities (TL;DR)
- **Dictionary upserts:** Pass A (seed), Pass E (aliases/relations).  
- **Chunk upserts:** Pass C (raw text+metadata), Pass D (vector & light enrichment), Pass E (graph fields).  
- **No DB writes:** Pass B (except manifest updates), Pass F only housekeeping.

### Concurrency & Race-Condition Controls
- **Per-Source Barrier:** A given `source_id` **cannot advance** to its next Pass until **all threads** for the current pass **complete** and **artifacts validate** (size>0, schema OK, checksum matches).
- **Atomic Writes:** Each pass writes to `*.tmp` and finalizes with `os.replace()`; readers use **retry with jitter** when encountering empty/invalid files.
- **Resume Integrity:** On resume, verify `manifest.json` (build version, checksums) before skipping a pass. If invalid/missing, **re-run** the pass for that `source_id`.
- **Batching & Rate Limits:** Use **bulk_write** for dictionary/chunk upserts with dedupe by `chunk_hash`/`term_key`; enforce **rate limiter** (token bucket) per collection.

### Acceptance Criteria Addendum
- A single `source_id` never enters Pass D/E while any Pass C threads for that `source_id` are running.  
- When a 0‑byte or invalid artifact is detected, the pipeline auto-heals by **re-running** the producing pass and proceeds without manual intervention.  
- Dictionary/chunk write calls reduced by **≥80%** versus current (per log sampling).  
- Deletion logging shows **accurate** counts (no “deleted -1”).  
- SSL bypass is **blocked** outside DEV at process start.

> Evidence of the current issues and behaviors is present in the run log (e.g., SSL bypass notices, dictionary upsert chatter, Pass B JSON parse failures). See BUG-018 original body for details.
