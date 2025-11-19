
# TTRPG Center — Ingestion Pipeline Change Prompts
**Scope:** Pass A–G (focus on C/D/E) + HGRN signals.  
**Goal:** Implement contextualized embeddings, multivector indexing, TOC pre-filter assets, Neo4j similarity edges, and evaluation traces **without** breaking existing interfaces.

---

## How to Use These Prompts
- Each block is written for an **AI Dev / code agent** working in your repo.
- Copy a block as-is into your agent (or ticket). Each block returns **diffs, scripts, and tests**.
- Follow order: **C → D → E → Migrations → Tests → HGRN → Rollout**.

---

## 0) Repo & Environment Checks (once)
**Prompt:**
You are an AI Dev working on the TTRPG Center ingestion engine. 
Task: Verify local dev environment, Python version, and that Docker services (Cassandra, Neo4j, Postgres) are reachable from the ingestion container.
Steps:
1. Print `python --version`, list installed packages, and confirm `cassio`, `neo4j`, `psycopg2/asyncpg` availability.
2. Confirm Cassandra keyspace/table exist; if not, stage a CQL migration (do **not** apply).
3. Confirm Neo4j bolt connection and version.
4. Output a short markdown status report and a `make target` proposal to run end-to-end smoke tests.

**Deliverables (JSON):**
{
  "checks": {"python":"x.y.z","packages":["cassio","neo4j","…"]},
  "cassandra": {"reachable": true, "keyspace":"ttrpg_vectors", "tables":["embeddings"]},
  "neo4j": {"reachable": true, "version":"x.y"},
  "postgres": {"reachable": true, "extensions":["pg_trgm (if used)"]},
  "proposed_make_targets": ["make ingest-smoke", "make e2e-mini"]
}

---

## 1) Pass C — Context Headers & TOC Node Summaries
**Prompt:**
You are modifying **Pass C** to emit compact **context headers** and **section summaries**.
Requirements:
- Build a `context_header` string per chunk from existing metadata (system, edition, book title, strict TOC path, page range, version/copyright year). Max 400 chars.
- Example format (do not add quotes inside fields):
  [System={system}|Edition={edition}|Book={title}|TOC={toc_path}|Pages={p_start}-{p_end}|Version={version_date}]
- Emit `section_summary` per Section node: first 1–2 sentences from the section + headings. Truncate to 400 chars.
- Produce a small **primer file** per book for CAG warming: `primers/{book_id}.md` containing high-level rules bullets (use headings + bolded rules names gleaned from TOC). Keep under 8 KB.
- Update Pass C outputs to include:
  - `context_header` at chunk level
  - `section_summary` at section level
  - `primer_path` at document level
- Backward compatibility: existing fields unchanged.

**Deliverables:**
- Code diffs (Python) for Pass C module(s).
- Updated JSON schema examples.
- Unit tests: verify header length constraints, TOC path correctness, and primer size.
- A sample generated `primer` for one document in fixtures.

---

## 2) Pass D — Contextualized & Multivector Embeddings
**Prompt:**
Update **Pass D** to compute embeddings from a synthetic field `embedding_text = context_header + "\n" + raw_text`. Retain `raw_text` unchanged.
Add **multivector** representations without LLM calls:
- `vector_main` from `embedding_text`.
- `vector_title` from TOC path string only (section/book headings).
- `vector_keywords` from deterministic keyword extraction (KeyBERT/RAKE; fall back to top-N tf-idf terms). Store extracted keywords in `keywords` array.
Performance constraints:
- Batch embeddings.
- Respect model dim=1536 (or configure via ENV).
Outputs:
- Write vectors to Cassandra per existing PK: (document_id, element_id, chunk_index).
- New columns: `embedding_text`, `vector_title`, `vector_keywords`, `keywords`.
- Emit a retrieval-side **candidate-union manifest** for each chunk ID listing which indices it lives in: ["main","title","keywords"].

**Deliverables:**
- Code diffs and configuration flags (env): `EMBED_DIM`, `EMBED_MODEL`.
- Migration stubs (CQL) to add new columns (do not apply).
- Micro-benchmarks on 500 chunks (throughput, latency).

---

## 3) Pass E — Graph Upserts & Offline Similarity Edges
**Prompt:**
Enhance **Pass E** (Neo4j) to:
- Ensure nodes: `Book`, `Section`, `Term`, `Chunk` with existing properties.
- Upsert relationships:
  - `(:Chunk)-[:IN_SECTION]->(:Section)`
  - `(:Section)-[:CONTAINS]->(:Chunk)`
  - `(:Section)-[:REFERS_TO]->(:Term)` (from citations/dictionary)
  - `(:Term)-[:ALIAS_OF]->(:Term{canonical:true})` (from dictionary)
- New: create nightly `(:Section)-[:SIMILAR_TO {w:float}]->(:Section)` edges:
  - For each Section, retrieve top-5 nearest neighbors by cosine using **Cassandra** section-level vectors (derive by averaging child chunk vectors or storing a section vector in D).
  - Persist only if w ≥ 0.78 and sections are not identical.
- Idempotent upsert; maintain `updated_at`, and keep last 3 versions (via `:Snapshot` or properties).

**Deliverables:**
- Neo4j cypher upsert templates.
- Python job `pass_e_similarity_edges.py` with CLI args (doc_id filter, threshold).
- Unit/integration tests using a tiny in-memory graph (neo4j test harness).

---

## 4) CQL Migrations (staged, not applied)
**Prompt:**
Generate **CQL** to alter `ttrpg_vectors.embeddings`:
```sql
ALTER TABLE ttrpg_vectors.embeddings 
ADD embedding_text text;
ALTER TABLE ttrpg_vectors.embeddings 
ADD vector_title vector<float, 1536>;
ALTER TABLE ttrpg_vectors.embeddings 
ADD vector_keywords vector<float, 1536>;
ALTER TABLE ttrpg_vectors.embeddings 
ADD keywords list<text>;
```
- Include rollback notes (drop columns) recognizing Cassandra’s limitations (requires table rebuild for some drops).
- Provide a **shadow table** DDL for zero-downtime migration: `embeddings_v2` with all columns; include `INSERT...SELECT` copy script and cutover plan.

**Deliverables:**
- `migrations/001_add_multivector.cql` (staged)
- `migrations/001_shadow_cutover.cql`
- `ops/run_migration.md` with manual steps and validation queries.

---

## 5) Test Harness & Golden Datasets
**Prompt:**
Create a minimal test corpus and harness to validate retrieval quality deltas.
- Fixtures: 3 rulebooks (ABP-heavy, creatures, conditions), 50–200 chunks each.
- Metrics computed offline:
  - Recall@k for gold QA pairs
  - Rerank NDCG (placeholder if reranker not available here)
  - Header ablation study: main vs. raw_text embeddings
Outputs:
- `tests/retrieval_harness.py` with CLI:
  - `--with-context-headers/--no-context-headers`
  - `--index=main|title|keywords|all`
  - `--k=50`
- Markdown report with tables comparing variants.

**Deliverables:**
- Code, fixtures, and sample report under `reports/retrieval/`.

---

## 6) HGRN Signals (ingestion-side only)
**Prompt:**
Extend HGRN to emit two artifacts per run, stored in Mongo and written to `/Transfer_Station/admin_reports/`:
- `db_suggestions.json`: missing edges/aliases, weak sections (few/low-sim hits), candidate re-OCR flags.
- `pipeline_suggestions.json`: chunking size issues by book, sections lacking summaries, missing keywords, primer quality warnings.
Each suggestion must include: `doc_id`, `section_path`, `evidence` (ids, scores), and a `proposed_fix` field.

**Deliverables:**
- HGRN module diffs and JSON schemas.
- One sample output per test corpus.

---

## 7) Rollout Plan & Backfill
**Prompt:**
Produce a safe rollout:
1. Add columns via shadow table, backfill multivectors for last 20 books.
2. Enable Pass D to write both legacy + new columns for 1 week.
3. Enable graph similarity edges nightly; monitor edge counts and average weight.
4. Turn on context headers for new embeddings; start re-embedding backlog by priority (high-traffic docs first).
5. Document operational dashboards and alert thresholds (embedding error rates, Neo4j write latency, backfill throughput).

**Deliverables:**
- `ops/rollout_plan.md` with checklists.
- Simple Grafana/SQL panels or queries to monitor progress.

---

## Acceptance Criteria (summary)
- Context headers present and bounded for ≥95% of chunks.
- Multivector fields populated for new ingests; backfill started.
- Section summaries available; primers generated under 8 KB.
- Neo4j `SIMILAR_TO` edges present with sane degree (≤7 on avg).
- Test harness shows ≥20% improvement in Recall@50 on gold set.
- HGRN emits the two suggestion files with actionable items.

---

## One-Shot Commit Template
**Prompt:**
Generate a conventional commit message for the changes completed in this task set, including scope `ingest` and bullet-pointed implementation notes, plus a brief migration note and test summary.

Output:
- `type(scope): subject` line
- Body with what/why/how
- “Migration:” and “Tests:” sections

---

## Appendix — Env Flags
- EMBED_DIM=1536
- EMBED_MODEL=<your_model_name>
- MULTIVECTOR=true
- CONTEXT_HEADERS=true
- SECTION_SIM_THRESHOLD=0.78
- BACKFILL_BATCH=500
- PRIMER_MAX_BYTES=8192
