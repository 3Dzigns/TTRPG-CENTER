
# Refactor Prompt: Upgrade `pass_f_consistency_check.py` into a Consistency **and** Chunk-Quality Coach

**Target file:** `pass_f_consistency_check.py` (Pass F HGRN)  
**Version currently in repo:** 2.1.0  
**Objective:** Keep all current consistency checks, and extend Pass F to (1) perform evidence-backed source grounding with fuzz, (2) assign section titles/breadcrumbs per chunk, (3) score & prescribe chunk-shaping actions (split/merge/retype), (4) normalize noisy dictionary terms, and (5) enforce graph invariants. Produce two artifacts: a DB remediations JSON and a pipeline suggestions MD—already present but expand their content as detailed below.

---

## 0) Guardrails & Style

- Maintain CLI compatibility (existing args & exit codes).  
- Keep current outputs (manifest + remediation JSON) and **add** new fields rather than breaking existing ones.  
- Follow existing patterns: evidence arrays are small, actions capped to ~10 examples per component, human-readable reasons.
- Avoid heavy external deps beyond those already used (`pypdf`, `pymongo`, `cassandra-driver`, `neo4j`, `python-dotenv`). If you create helpers, keep them in the same file.

---

## 1) Page-Grounding Validator: Fuzzy + Evidence

### Why
We need fewer false negatives when matching TOC titles and chunk text to source pages, and we want minimal evidence to display in the Admin UI.

### Requirements
- Enhance `_page_contains_text` / `_page_token_overlap` by adding **windowed fuzzy search** for page±1. Use: token trigram overlap or normalized token Jaccard against the page text tokens; threshold 0.85 default.
- When a miss occurs, attempt fuzzy on `page-1` and `page+1`. If matched, add an **auto-suggestion** to nudge page references by ±1 with rationale.
- Record a short **evidence excerpt**: `{page, start_idx, end_idx, excerpt}` (max 160 chars, elide with `…` if needed). Add to `self.evidence["source_grounding"]`.

### Implementation Hints
- Add config constants:
  ```python
  DEFAULT_FUZZY_THRESHOLD = 0.85
  DEFAULT_PAGE_WINDOW = 1  # check ±1
  ```
- Add helper: `_fuzzy_contains(page_number: int, text: str, threshold: float) -> Optional[Dict]` returning evidence dict or `None`.
- Update `_run_source_checks` and Cassandra text checks to record evidence and generate pipeline suggestions:
  - `Pass A: TOC entry 'X' not found on page N; found fuzzy match on page N±1.`
  - `Pass C: Chunk {chunk_id} text fuzzy-matched to page N±1; verify page metadata.`

### Acceptance
- When TOC title exists on page+1 only, a suggestion to correct to page+1 is produced, with an evidence excerpt.
- Evidence table `source_grounding` appears in final JSON with ≤10 entries.


---

## 2) Section Assigner + Breadcrumb Normalizer

### Why
Each chunk should carry a `section_title` and a `section_path` breadcrumb to improve retrieval and UI filtering.

### Requirements
- From `pass_a_metadata.data["toc_structure"]`, build an in-memory tree of sections: each node `{title, page_start, page_end?}`.
- For each chunk (from Cassandra rows), **assign `section_title`** based on the closest ancestor section where `page_start <= page_number < next_section.page_start`.
- Create a human-readable **breadcrumb** `section_path` e.g. `"Book › Part II › Combat Actions › Reactions"`.
- Add **chunk remediation** suggestion if section cannot be resolved (e.g., page_number missing): `"assign_section": "unknown"` and pipeline suggestion to fix pagination.
- Extend remediation bundle `chunks.actions` with per-chunk updates: `{op:"set_metadata", fields: {"section_title": ..., "section_path": ...}}` (non-destructive proposal).

### Implementation Hints
- Add `_build_toc_index(toc_entries) -> List[Dict]` sorted by page_start with `page_end` inferred from next sibling.
- Add `_resolve_section_for_page(page: int) -> Tuple[Optional[str], Optional[str]]` returning `(section_title, section_path)`.
- In `_run_cassandra_checks`, annotate per-chunk resolution and append to `self.remediation["chunks"]` under a single batched action list.

### Acceptance
- For chunks with valid pages, section fields are populated in remediation proposals.
- For unknown sections, a pipeline suggestion is emitted.


---

## 3) Chunk-Shape Scorer + Prescriptions

### Why
We need to **score** chunk fitness and generate actionable prescriptions: split/merge/retype/drop-noise.

### Metrics (per chunk)
- `length_tokens` (approx: whitespace tokens count).
- `sentence_ends` (count of `.?!` occurrences).
- `pct_nonalpha` (ratio of non-alphanumeric chars).
- `bullet_density` (lines starting with `-`, `•`, `*`, digits+`.`).
- `table_span` (heuristic: many `|`, tabs, consistent column-like spacing).
- `duplicate_sim` (optional: cosine between minhash signatures of neighboring chunks’ shingles).

### Target Heuristics & Actions
- If `length_tokens > 450`: propose `split_at` indices, prefer sentence boundaries around 300–380 tokens.
- If `length_tokens < 120` and same section as neighbor: propose `merge_with: previous_or_next`.
- If `table_span` likely and spans multi-page: flag `retype_as: "table"` and suggest re-extract table single-page.
- If `pct_nonalpha > 0.35` or `sentence_ends == 0`: `drop_noise: true` or re-extract with OCR cleanup.
- If near-duplicate (`duplicate_sim >= 0.95`): propose tombstone of one duplicate.

### Implementation Hints
- Add `DEFAULT_TOKEN_TARGET_MIN = 250`, `DEFAULT_TOKEN_TARGET_MAX = 400`.
- Add helpers:
  ```python
  def _chunk_metrics(text: str) -> Dict[str, float]: ...
  def _split_suggestions(text: str, preferred_len=(300,380)) -> List[int]: ...
  def _duplicate_similarity(a: str, b: str) -> float: ...
  ```
- Extend `self.remediation["chunks"]` with a new action record:
  ```python
  {
    "tenant_id": self.tenant_id,
    "document_id": document_id,
    "recommendation": "reshape_chunks",
    "chunks": [ { "chunk_id": "...", "actions": [ {...}, ... ], "metrics": {...} } ],
    "reason": "Chunk fitness improvements"
  }
  ```

### Acceptance
- For a too-long chunk: a `split_at` proposal with 1–3 candidate indices is present.
- For very short adjacent chunks in same section: a `merge_with` proposal is present.


---

## 4) Dictionary Term Normalizer

### Why
Reduce noise in Mongo terms (spaced letters, ligatures, broken numbers/units). Do **not** auto-insert—propose merges to canonical forms.

### Requirements
- Add normalization pipeline for candidate terms in Mongo loop:
  - Collapse intra-term spaces (`"a r m o r"` → `"armor"`).
  - Fix common ligatures (`ﬁ`→`fi`, `ﬂ`→`fl`).
  - Merge split numbers/units (`"10 ft"` → `"10 ft"` normalized consistently).
  - Strip trailing artifacts like `")1"`.
- Emit `{term_raw, term_norm, confidence, evidence_chunks[]}` in a **new** `self.remediation["mongodb"]` action type `"NormalizeTerm"`, with `dry_run: True`.
- Add pipeline suggestion: `"Pass C: Add term normalization rules for pattern …"` (one per pattern family).

### Implementation Hints
- Add helper `_normalize_term(raw: str) -> Tuple[str, float]` returning normalized + confidence.
- Record first two `evidence_chunks` where the normalized form appears in source (use `_search_document`).

### Acceptance
- For a spaced/ligatured term, a `"NormalizeTerm"` action with `term_norm` and confidence ≥0.8 appears.


---

## 5) Graph Invariants & Linkage Tests (Neo4j)

### Why
Ensure no orphaned terms or chunks, reasonable `SIMILAR_TO` degrees, and acyclic `PART_OF` chains.

### Requirements
- Keep current orphan-chunk, degree-cap, and cycle breakers.
- **Add** term-node linkage check:
  - Query: for `(:Term {document_id})` ensure each has at least one incoming `MENTIONS` from a `Chunk` or a `DEFINES` from `Document/Section`.
  - Orphan Terms → evidence + actions: either delete or attach to best matching chunk by text fuzzy evidence (dry-run).
- **Add** part_of chain root validation:
  - Ensure every `(c:Chunk {document_id})-[:PART_OF*]->(x)` eventually reaches a `Document {document_id}` or `Section` node; otherwise flag and propose linking to nearest `Section` by page.

### Implementation Hints
- Add two new queries and cap evidence to ≤10.
- Reuse section resolution by page from Section Assigner.

### Acceptance
- Orphan `Term` and broken `PART_OF` chains produce actions and evidence entries.


---

## 6) Output Artifacts: Enrich & Keep Compatibility

### Requirements
- **`hgrn_db_remediations.json`**: already written—add:
  - `"source_grounding": self.evidence["source_grounding"]`
  - `"chunk_shape": { "targets": {"min": 250, "max": 400} }`
  - `"section_assignments": count stats (assigned, unknown) `
  - `"term_normalizations": count with examples`
- **`hgrn_pipeline_suggestions.md`**: convert list to grouped sections with headings:
  - `## Pass A (TOC)`, `## Pass C (Extraction)`, `## Pass D (Embeddings)`, `## Pass E (Graph)`, `## Global`
  - Deduplicate and sort suggestions. Keep bullets short; include file/field names when possible.
- **Manifest**: add:
  - `validation.component_scores["source"]` for source checks (checked, violations, score).
  - `inputs["chunk_quality_targets"]` (min/max tokens).

### Implementation Hints
- Add a new `ValidationComponentResult` for **source** checks and include it in overall score averaging.
- Update `_write_hgrn_outputs()` to write grouped MD rather than flat bullets.

### Acceptance
- JSON contains new sections; MD is grouped by pass; CLI prints the two enriched output paths.


---

## 7) Tests & Limits

### Requirements
- Do not blow up runtime: keep Pass F < ~120s on a 400-page PDF with 2k chunks.
- Cap evidence/action samples as the file does now (≤10 per category).  
- Add basic unit-ish helpers at the bottom guarded by `if __name__ == "__main__":` `--selftest` flag:
  - Run metrics on 3 synthetic strings.
  - Run `_normalize_term` on a few noisy samples and print results.
  - Smoke-test `_fuzzy_contains` with small synthetic pages array (no external IO).

### Acceptance
- `python pass_f_consistency_check.py --selftest` returns 0 and prints short diagnostics.


---

## 8) Deliverables

1) Updated `pass_f_consistency_check.py` implementing all above changes, with version bumped to **2.2.0**.  
2) New or updated docstrings for all added helpers.  
3) Enriched `hgrn_db_remediations.json` and `hgrn_pipeline_suggestions.md` formats as specified.  
4) Backward-compatible CLI and exit codes.


---

## 9) Suggested Patch Points (Search Anchors)

- `__version__ = "2.1.0"` → bump to `2.2.0`
- `DEFAULT_*` constants block → add fuzzy & token target constants
- `_page_contains_text`, `_page_token_overlap` → integrate `_fuzzy_contains()`
- `_run_source_checks()` → add evidence + suggestions; return a `ValidationComponentResult` (new component “source”)
- `_run_cassandra_checks()` → compute metrics, section assignment, and chunk prescriptions
- `_run_mongo_checks()` → integrate term normalizer & normalize actions
- `_run_neo4j_checks()` → add orphan Term and PART_OF root validation
- `_write_hgrn_outputs()` → enrich JSON, group MD output
- `_build_manifest()` → include new inputs & source component score


---

## 10) Acceptance Test Script (Manual)

- Run against a known doc with off-by-one TOC pages and a handful of OCR-spaced terms.
- Confirm:
  - `source_grounding` evidence contains excerpts and fuzzy page corrections.
  - Chunks get section titles + breadcrumbs.
  - Overlong chunks show `split_at`; very short neighbors produce `merge_with`.
  - Mongo actions include `NormalizeTerm` dry-run proposals.
  - Neo4j actions include orphan Term fixes and PART_OF root links.
  - Outputs updated and CLI prints paths to the two enriched artifacts.

---

## Done Criteria (Checklist)

- [ ] Version bumped to 2.2.0
- [ ] Fuzzy source grounding with evidence (+/- 1 page window)
- [ ] Section assignment & breadcrumb generation
- [ ] Chunk metrics + prescriptions (split/merge/retype/drop-noise/duplicate)
- [ ] Mongo term normalization actions
- [ ] Neo4j invariants: orphan Terms & PART_OF root checks
- [ ] Enriched JSON + grouped MD outputs
- [ ] Self-test flag implemented and passing
