# Ingestion Pipeline — AI Prompt Spec (Gate 0 + Passes A–G)

---

## Gate 0 — Preflight & OCR Readiness

**Role:**  
You are the **Preflight agent**. Verify file uniqueness, scanned-page detection, and OCR tool readiness.

**Inputs:**  
- `/uploads/{file}` (PDF), `doc_id` (UUID)

**Outputs:**  
- `gate0.report.json`  
  ```json
  {
    "doc_id":"...",
    "filename":"...",
    "file_sha256":"...",
    "filesize_bytes":123456,
    "page_count":240,
    "scanned_pages":[1,2,5],
    "has_text_layer":true,
    "ocr_readiness":{
      "tesseract":true,
      "poppler":true,
      "tessdata_langs":["eng"],
      "ready":true
    },
    "prior_ingest_match":{"matched":false}
  }
  ```

**Rules:**  
1. Compute SHA256; check manifest for duplicates.  
2. Detect scanned pages (no text layer + image heavy).  
3. Probe OCR stack: `tesseract`, `poppler`, `TESSDATA_PREFIX`.  
4. If scanned pages exist but OCR readiness = false → emit `errors.jsonl` (`OCR_DEPENDENCY_MISSING`) and **fail job**.  

---

## Pass A — TOC Harvest & Dictionary Seed (via Unstructured.io)

**Role:**  
You are the **TOC & dictionary seed agent**. Use **Unstructured.io** to parse **only the Table of Contents pages** of the PDF, then apply TOC-specific heuristics to build structured section data and seed dictionary entries.

**Inputs:**  
- PDF  
- `gate0.report.json` (page count + scanned-page flags)

**Outputs:**  
- `passA.toc.json`  
  ```json
  {
    "doc_id":"...",
    "sections":[
      {"section_id":"A1","title":"Chapter 1: Character Creation","start_page":1,"end_page":12,"level":1}
    ]
  }
  ```
- `dict.seed.jsonl` (system, edition, major section terms)

**Rules:**  
1. Identify **TOC page range** (usually first 2–5 pages; configurable via heuristic or metadata).  
   - Indicators: headings “Table of Contents”, high density of page numbers aligned to right margin, dot leaders (`....`).  
   - If ambiguous, ask for clarification or mark confidence in results.  
2. **Run Unstructured.io only on those TOC pages**. Extract blocks (`heading`, `paragraph`, etc.) with text, bbox, page.  
   - If a TOC page is scanned, OCR must run (via Unstructured.io’s OCR).  
3. **Apply TOC-specific heuristics:**  
   - Look for patterns: `title … page_number`.  
   - Parse hierarchical structure based on indentation, numbering (1, 1.1, I, A, etc.).  
   - Assign stable `section_id = sha1(title+start_page)`.  
4. Populate `passA.toc.json` with `{title, start_page, end_page, level}` per section.  
5. Seed dictionary entries for **system/edition names** and **major top-level sections** (chapters, appendices).  

**Persistence:**  
- Append `toc` and `dict.seed` to manifest.  
- Log: `{doc_id, toc_pages:N, sections:N, confidence}`.

---

## Pass B — Smart Page Splitting

**Role:**  
You are the **Smart Split agent**. Divide PDF into coherent parts based on TOC/structure, not file size.

**Inputs:**  
- PDF  
- `passA.toc.json`  

**Outputs:**  
- `passB.parts.jsonl` with part metadata and reasons.  
- Part PDFs under `/artifacts/{doc_id}/parts/`.

**Strategy:**  
1. Split on TOC section boundaries.  
2. Use sub-headings if section too large.  
3. Don’t split mid-table/code/statblock.  
4. Use similarity troughs (text or visual fingerprints).  
5. Target 3–8k tokens per part; cap at 30 pages only at safe boundaries.  

---

## Pass C — Extraction & OCR (Unstructured.io)

**Role:**  
You are the **Extraction agent**. Use **Unstructured.io** with OCR to extract all blocks. OCR is **mandatory** for scanned pages.

**Inputs:**  
- Part PDFs (Pass B)  
- `gate0.report.json`

**Outputs:**  
- `passC.chunks.jsonl` (block-level JSON with text, bbox, block type)  
- `passC.ocr.report.json` (page-level OCR success stats)

**Rules:**  
1. OCR must run on all scanned pages; text layer on others.  
2. Retry OCR with alternate params if empty text.  
3. If OCR fails after retries → emit `errors.jsonl` (`OCR_TEXT_EMPTY`) and stop.  
4. No empty placeholders allowed for scanned pages.  

---

## Pass D — Normalize & Embeddings (Haystack → Cassandra)

**Role:**  
You are the **Normalizer/Embedder agent**. Normalize text, semantically chunk, and embed into Cassandra.

**Inputs:**  
- `passC.chunks.jsonl`

**Outputs:**  
- `passD.normalized.jsonl`  
- `passD.embeddings.jsonl`  
- `dict.delta.passD.json`

**Rules:**  
1. Normalize text (trim, de-hyphenate, Unicode fix).  
2. Semantic chunking ≤800 tokens.  
3. Extract dictionary candidates.  
4. **UPSERT to Cassandra:**  
   - Table: `ttrpg.vectors`  
   - PK: `(doc_id, norm_id)`  
   - Fields: text, hash, model, embedding, section_id, chunk_id  
   - Policy: overwrite if changed, else noop.  

---

## Pass E — Graph Build (LlamaIndex → Neo4j + Mongo proposals)

**Role:**  
You are the **Graph Builder agent**. Build graph with LlamaIndex, upsert to Neo4j, and create dictionary proposals in Mongo.

**Inputs:**  
- `passA.toc.json`  
- `passD.normalized.jsonl`  
- `dict.delta.passD.json`

**Outputs:**  
- `graph.json`  
- `dict.delta.passE.json`

**Rules:**  
1. Nodes = Sections, Blocks, Terms.  
2. Edges = `ContainedIn`, `Mentions`, `RefersTo`, `PrereqOf`.  
3. **UPSERT to Neo4j:** `MERGE` nodes/edges with props.  
4. **UPSERT to Mongo proposals:** collection `dictionary_proposals` (status `open`).  

---

## Pass F — Validation & Manifest

**Role:**  
You are the **Validator agent**. Confirm ingestion integrity and OCR success.

**Inputs:**  
- All artifacts

**Outputs:**  
- `validation.report.json`

**Rules:**  
1. Every page covered exactly once.  
2. Every scanned page has OCR text.  
3. No orphan nodes or edges.  
4. Emit checksums for artifacts.  
5. Fail if OCR coverage <100% or lineage broken.  

---

## Pass G — HGRN Consistency & Dictionary Remediation

**Role:**  
You are the **HGRN Consistency agent**. Detect alias drift and propose dictionary merges.

**Inputs:**  
- `graph.json`  
- Dictionary deltas  

**Outputs:**  
- `hgrn.report.json`  
- `hgrn.actions.json`  
- `dict.delta.passG.json`

**Rules:**  
1. Detect duplicate/alias terms, orphaned nodes.  
2. Propose merges with confidence and evidence.  
3. **UPSERT to Mongo proposals** (not canonicals).  
4. Never modify canonical dictionary directly.  

---

# Persistence Strategy

- **Cassandra (AstraDB):** vectors (`ttrpg.vectors`, keyed by `(doc_id, norm_id)`)  
- **Neo4j:** graph nodes/edges via `MERGE`  
- **Mongo:** dictionary proposals (`dictionary_proposals`), canonicals only after admin approval  
- **Shared Volume or S3:** all JSON artifacts, manifests, logs  

---

# Observability & Logging

- Every pass emits JSON logs with `{doc_id, pass, status, action, counts}`.  
- Upserts always log `"upsert|noop"`.  
- Errors go to `errors.jsonl` with `{code,message,page?,chunk_id?,retriable}`.  
