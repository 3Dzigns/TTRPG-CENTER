# Feature Request — Ingestion & Graph Enhancements (Core Rulebook + Ultimate Magic)

**Owner:** Ingestion Team · **Stakeholders:** Retrieval/Graph, Admin UI, QA · **Phase Alignment:** Phases 1–3 (with ties to 4–6)

## Summary

This feature set closes gaps identified during the Core Rulebook and Ultimate Magic ingestions. It improves **section-aware chunking**, **table/list handling**, **dictionary quality**, and **graph usefulness for procedures**. Two additional platform capabilities are added: **(1) a pre-processor auto-threshold by file size** and **(2) multi-threaded execution** where safe.

---

## Goals

* Raise retrieval precision via better **section titles** and **chunk roles** (rule/example/table/fiction/etc.).
* Preserve **tables/lists** as self-contained, queryable chunks.
* De-clutter the **dictionary** (game terms only; consistent canonicals; provenance).
* Build a **useful workflow/knowledge graph** (procedures and steps, not just categories).
* Improve throughput and reliability with **size-based pre-processing** and **multi-threading**.

## Non-Goals

* Redesigning the Phase 2 router or Phase 5 UI (only metadata contract changes that they already accept).
* New retrieval models.

## Success Metrics

* +20–35% increase in exact/lenient match on Phase‑2 eval set (EM/F1).
* ≥0.9 citation accuracy on answers that cite rules/procedures.
* 2–4× end-to-end ingestion throughput on large PDFs with multi-threading enabled.

---

# EPIC E1 — Section-Aware Chunking (Pass A)

### US-E1.1: ToC/Heading-Aligned Section Titles

**As** the ingestion pipeline
**I want** each chunk to include a precise `section_title` derived from ToC/heading structure (e.g., `Classes > Cleric > Channel Energy`)
**So that** retrieval and dictionary updates can key off reliable sections.

**Acceptance Criteria**

* `section_title` present for ≥98% chunks with text.
* Normalized to `>`-delimited path; stable across runs.
* Fallbacks (when headings absent) use nearest prior heading + heuristic.

**Tests**

* **Unit:** heading parser maps known samples; normalization rules.
* **Functional:** sample PDFs produce stable `section_title` for repeated runs.
* **Regression:** hash of `(page, section_title, type)` stable for fixtures.
* **Security:** unmatched headings don’t cause crashes; inputs sanitized.

**Implementation Notes**

* Merge unstructured.io elements with a precomputed ToC map; backfill when OCR/structure weak.

---

# EPIC E2 — Table/List Preservation (Pass A)

### US-E2.1: Table/List Detection & Isolation

**As** a data engineer
**I want** tables and enumerated lists captured as **single self-contained chunks** with `chunk_role="table"|"list"`
**So that** they can be filtered or surfaced correctly in retrieval.

**Acceptance Criteria**

* Tables/lists are not merged into prose chunks.
* Column headers and rows preserved; list bullets kept in order.
* Contract keys: `{chunk_role, schema_hint, lines:[...]}` for tables/lists.

**Tests**

* **Unit:** detector identifies known equipment/spell/feat tables.
* **Functional:** sample chapters output ≥95% of true tables as `chunk_role=table`.
* **Regression:** schema snapshot of a known table remains compatible.
* **Security:** no arbitrary HTML; safe plaintext with minimal markup.

**Implementation Notes**

* Use layout cues + keywords (e.g., “Spell List”, “Feat Descriptions”) to force boundaries when layout detection is weak.

---

# EPIC E3 — Dictionary Quality (Pass B)

### US-E3.1: Domain Term Filter & Canonicalization

**As** the enrichment step
**I want** to **exclude non-game** terms (credits, staff, addresses, boilerplate) and normalize **game terms** into canonical entries
**So that** the dictionary drives better linking and retrieval.

**Acceptance Criteria**

* Drop/ignore: names/emails/addresses/printing/OGL boilerplate.
* For each game term, store `{term, kind, canonical, aliases, sources:[{doc,page,section_title}]}`.
* Deduplication: no duplicate canonical keys in a single run; levenshtein/heuristic merge of near-duplicates (e.g., “arcane discovery” vs “arcane discoveries”).

**Tests**

* **Unit:** filter removes credits; canonicalization merges variants.
* **Functional:** dictionary delta shows only spells/feats/classes/mechanics/procedures.
* **Regression:** previously fixed duplicates remain merged; idempotent upsert.
* **Security:** provenance redacted of PII.

**Implementation Notes**

* Maintain a small denylist (credits/boilerplate) + allowlist patterns (spells, feats, archetypes, mechanics, procedures).

---

# EPIC E4 — Procedure-Centric Graph (Pass C)

### US-E4.1: Procedure & Step Nodes with Edges

**As** the graph compiler
**I want** to extract **procedures** (e.g., *Binding Outsiders*, *Spell Duels*, *Designing Spells*, *Craft/Modify Construct*, *Words of Power casting*) and their **steps** with `prereq/part_of/depends_on` edges
**So that** Phase‑3 workflows are actionable.

**Acceptance Criteria**

* Node types: `Procedure`, `Step`, `Rule`, `Concept`, `SourceDoc`.
* Edges: `part_of` (procedure→step), `prereq` (step→step), `cites` (to `SourceDoc`), `implements` (rule→procedure).
* Each procedure cites at least one chunk with page + section.

**Tests**

* **Unit:** builder extracts steps from ordered headings/lists.
* **Functional:** known procedures present with ≥2 steps and citations.
* **Regression:** IDs deterministic for same text; edges stable.
* **Security:** max depth/size guards during build.

**Implementation Notes**

* Start heuristic (headings/lists), optional LLM labeling guarded by token budget; prefer deterministic extraction.

---

# EPIC E5 — Provenance & Consistency (Pass B/C QA)

### US-E5.1: Page/Chunk Back-Links & Integrity

**As** QA
**I want** every dictionary term and graph node to reference **existing Pass A pages/chunks**
**So that** provenance is verifiable.

**Acceptance Criteria**

* 100% referential integrity: all `sources[*].page` exist in Pass A.
* Duplicate terms collapsed; graph nodes de-duplicated by `(title_hash, doc)`.

**Tests**

* **Unit:** integrity validator catches broken refs.
* **Functional:** run validator → zero errors on fixtures.
* **Regression:** integrity remains clean after deltas.
* **Security:** validator ignores external links.

---

# EPIC E6 — Pre-Processor Threshold by File Size (NEW)

### US-E6.1: Auto-Split Trigger by File Size

**As** an ingestion operator
**I want** the pre-processor to **automatically split** very large PDFs into logical chunks **when the file exceeds a configurable size**
**So that** unstructured.io remains performant and reliable.

**Acceptance Criteria**

* Config key: `preprocessor.size_threshold_mb` (default: 40 MB) with env overrides per DEV/TEST/PROD.
* If file ≥ threshold → apply chapter/ToC split; else pass through.
* Logs show: original size, threshold, split strategy, number of parts.
* Manifest records split details and per-part checksums.

**Tests**

* **Unit:** threshold logic (edge cases: =, <, > threshold).
* **Functional:** large fixture triggers split; small fixture does not.
* **Regression:** stable split counts for known PDFs.
* **Security:** threshold cannot be overridden to negative/zero.

**Implementation Notes**

* Prefer **semantic splits** (chapters/ToC) before page-count windows; fall back to page windows when structure missing.

---

# EPIC E7 — Multi-Threaded Ingestion (NEW)

### US-E7.1: Parallel Pass A/B/C Where Safe

**As** a platform engineer
**I want** multi-threading for independent tasks (file part parsing, chunk enrichment, graph compilation per section)
**So that** throughput increases without breaking determinism.

**Acceptance Criteria**

* Config keys: `concurrency.passA`, `concurrency.passB`, `concurrency.passC` with sane defaults (e.g., 4/6/2) and per-env caps.
* Work partitioning is **idempotent**; retries do not duplicate outputs.
* Deterministic merge order (sorted by `(doc, chapter_index, page, element_index)`).
* Rate limits for 3rd-party tools respected; backoff on 429/5xx.

**Tests**

* **Unit:** task scheduler splits/merges deterministically.
* **Functional:** wall-clock time decreases on multi-core machines while output digests remain unchanged compared to single-threaded run.
* **Regression:** concurrency changes do not alter chunk counts or IDs.
* **Security:** no cross-tenant bleed; per-env queues and temp dirs.

**Implementation Notes**

* Python `concurrent.futures`/`ThreadPoolExecutor`; bounded queues; per-env temp workspace (`env/<name>/data/tmp/<job>`).

---

## Contracts & Schemas (Additions)

* **Pass A chunk**: `{text, page, section_title, type, chunk_role?, schema_hint?, lines?}`
* **Pass B dictionary delta**: `{term, kind, canonical, aliases[], sources[{doc,page,section_title,chunk_id}]}`
* **Graph node**: `{id, node_type, title, cites[{doc,page,chunk_id}], section_title}`

---

## Telemetry & Admin UI Hooks

* Ingestion Console displays threshold events and concurrency settings used per job.
* Dictionary view gains filters for `kind` and doc.
* Graph preview shows procedures with steps and citations.

---

## Rollout Plan

1. Implement E6 (threshold) and E7 (multi-threading) guarded by feature flags; verify stability on fixtures.
2. Ship E1–E2 changes to Pass A; update schema validators.
3. Ship E3 (dictionary) and E5 (integrity validator); confirm Phase‑2 eval gains.
4. Ship E4 (procedures) and expose in Graph Console.

---

## Definition of Done

* All epics’ acceptance tests pass in CI; DEV gates (Phase 6) enforce.
* Phase‑2 eval metrics improved vs baseline; no regression in latency p95.
* Admin UI surfaces new metadata and shows split/concurrency details.
