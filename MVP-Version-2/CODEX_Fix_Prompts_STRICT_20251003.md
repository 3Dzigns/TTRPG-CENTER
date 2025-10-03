# CODEX Fix Prompts — Datastore Persistence & DEV Parity (STRICT)

These are **copy‑paste prompts** for your AI Dev (CODEX) to apply targeted fixes. Each prompt includes **goal**, **constraints**, **implementation steps**, and **acceptance tests** that must pass in the **DEV docker environment** (`localhost:8000`, keyspace/db **ttrpg_dev**).

> Use the repo’s standard branch naming (e.g., `fix/datastore-upserts-<shortdesc>`), and commit with conventional messages. Do **not** change public APIs unless stated. Keep all work in **DEV** scope.

---

## Prompt 1 — Fix Cassandra Upserts (Pass D → Vector Store Persistence)

**Goal**: Ensure Pass D writes chunk vectors to **Cassandra** table `ttrpg_dev.chunks` with correct partitioning/keys and environment scoping.

**Context**: Pass C reports `chunks_loaded > 0` but Cassandra has **0 rows**. Likely issues: wrong keyspace, dry‑run/mocks, no `execute_batch`, swallowed exceptions, or missing commit semantics in client wrapper.

**Do**:
1. Audit `src_common/pass_d_vector_enrichment.py` and the Cassandra client (e.g., `src_common/cassandra_client.py` or equivalent) for:

   - Keyspace = `ttrpg_dev`
   - Table = `chunks` with schema fields: `chunk_id` (PK), `content`, `embedding`, `embedding_model`, `environment`, `source_file`, `source_hash`, `stage`, `vector_id`.
   - Prepared statements & batched writes (`BatchStatement`) with idempotent upsert semantics (`INSERT ...` or `UPDATE ... IF EXISTS` where appropriate).
   - Explicit error handling and logging (at **WARN/ERROR** when write fails).

2. Add **write verification**: after a batch insert for the current `job_id`, run a **read‑after‑write** (`SELECT COUNT(*) FROM chunks WHERE source_hash = :source_hash ALLOW FILTERING`) and assert `> 0`. If `0`, raise and mark pass as **failed**.
3. Ensure **environment scoping** is written (`environment='DEV'`) and included in all queries.
4. Enforce **partition key** usage for scalable reads (prefer `source_hash` or a composite key over ALLOW FILTERING in app code).
5. Instrument with metrics: `pass_d.cassandra.rows_written`, `duration_ms`, `error_count`.

**Acceptance Tests** (must pass in DEV):
- Ingest `dnd_character_creation.pdf` via Admin UI Selective Ingestion.
- Post‑pass D, a query returns `COUNT(*) > 0` in `ttrpg_dev.chunks` **for this job/document**.
- Manifest remains `success: true`; logs show rows written and timing.
- Re‑ingesting same file **upserts** (no duplicates; keys stable).

---

## Prompt 2 — Fix MongoDB Dictionary Upserts (Pass A/D → Dictionary Persistence)

**Goal**: Ensure dictionary seeds/deltas are written to **MongoDB** collection `ttrpg_dev.ttrpg_dictionary_dev` with proper job/document scoping.

**Do**:
1. Audit dictionary write paths in Pass A (TOC/dictionary seed) and any delta updates in Pass D.
2. Verify Mongo client uses `db = client['ttrpg_dev']` and `collection = db['ttrpg_dictionary_dev']`.
3. Implement **upsert** with unique key on `(term, source_hash)` to avoid duplicates. Include fields: `term`, `kind`, `sources[]` (page anchors), `job_id`, `environment`, `created_at`.
4. After write, perform a **verification read**: `countDocuments({ job_id }) > 0` else raise and fail the pass.
5. Add metrics: `pass_a.mongo.terms_written`, `pass_d.mongo.deltas_written`.

**Acceptance Tests**:
- After ingesting the test PDFs, `db.ttrpg_dictionary_dev.countDocuments({ job_id }) >= 1`.
- A sample `findOne` shows `term`, `sources`, and `environment: "DEV"` populated.
- Re‑ingest same file updates existing records without duplication.

---

## Prompt 3 — Deploy Neo4j in DEV & Wire Pass E

**Goal**: Add a **Neo4j** service to `docker-compose.dev.yml`, configure credentials, and ensure **Pass E** writes graph nodes/edges.

**Do**:
1. Extend `docker-compose.dev.yml` with a `neo4j` service (image `neo4j:5`, env for `NEO4J_AUTH`, volumes, ports 7474/7687). Mark as **DEV‑only**.
2. Add env vars to worker/orchestrator for Bolt URI & credentials; load via config (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASS`, `NEO4J_DB=ttrpg_dev`).
3. Implement write path in Pass E using official driver; create indexes/constraints on `(:Term {term, source_hash})`, `(:Chunk {chunk_id})`.
4. After write, run a **verification query**: `MATCH (t:Term)-[r:MENTIONS]->(c:Chunk) WHERE t.job_id=$job_id RETURN count(r) > 0` else fail pass.

**Acceptance Tests**:
- `docker ps` shows the neo4j container healthy in DEV.
- Ingest a test file; a Cypher validation returns `count(r) > 0` for that `job_id`.
- Graph survives service restart (data volume persists).

---

## Prompt 4 — Add Datastore Write Verification to Passes

**Goal**: No pass reports success unless its **datastore writes are verified**.

**Do**:
1. For Pass D (Cassandra), Pass A/D (Mongo), and Pass E (Neo4j), add a `verify_writes(job_id, source_hash)` step with small bounded reads.
2. If verification fails, mark pass `success: false`, surface error, and stop pipeline.
3. Emit structured logs for verification (counts, duration).

**Acceptance Tests**:
- Break a connection string → pass fails with explicit datastore error.
- Normal run → pass succeeds and logs `verify_writes: ok` with counts per store.

---

## Prompt 5 — Integration Tests (End‑to‑End Data Flow)

**Goal**: Prove **pipeline → DB** continuity using Docker‑based tests runnable from Admin UI and CLI.

**Do**:
1. Add a test harness (pytest or nose) under `tests/integration/` with a target `test_ingest_to_datastores.py`.
2. Flow:
   - Upload a small fixture PDF.
   - Trigger Selective Ingestion via API (DEV).
   - Poll job completion.
   - **Assert Cassandra**: `COUNT(*) by job_id > 0`.
   - **Assert Mongo**: `countDocuments({ job_id }) > 0`.
   - **Assert Neo4j**: `MATCH (t)-[r]->(c) WHERE t.job_id=$job_id RETURN count(r)>0`.
3. Provide a Dockerized runner to execute the suite from Admin UI Test Console.

**Acceptance Tests**:
- `make test-integration-dev` passes locally.
- Admin UI can trigger and render results for the above assertions.

---

## Prompt 6 — Health Endpoint for Datastores

**Goal**: Add `/healthz/datastores` endpoint that validates **connectivity** and **basic R/W** permissions (read‑only by default).

**Do**:
1. Implement an endpoint in Admin API (DEV scope) that checks:
   - Cassandra: connect, `DESCRIBE KEYSPACES`, `SELECT COUNT(*) FROM chunks`.
   - Mongo: list dbs, list collections, count on dictionary.
   - Neo4j: simple `RETURN 1`.
2. Return a structured JSON with per‑store `status`, `latency_ms`, and any errors.

**Acceptance Tests**:
- Hitting `/healthz/datastores` returns 200 with all stores `ok` (after fixes).
- Break a credential → endpoint surfaces the failing store with error details.

---

## Prompt 7 — Transaction & Error Logging Hardening

**Goal**: Ensure failed writes can’t be mistaken as success.

**Do**:
1. Wrap all datastore writes with try/except; log **full context** (job_id, counts, first error message).
2. For Cassandra, prefer unlogged batches where safe; confirm idempotency and add retry policy (limited, with backoff).
3. For Mongo, use `writeConcern` appropriate for DEV; surface write errors.
4. For Neo4j, ensure sessions/transactions are properly closed and committed.

**Acceptance Tests**:
- Inject a transient failure → retries occur then surface a clear error.
- Logs show operation counts and failure points.

---

## Prompt 8 — Config Drift Guards (ENV Safety)

**Goal**: Prevent accidental writes to the wrong environment (e.g., TEST/PROD from DEV).

**Do**:
1. Centralize config loading; assert `ENV=DEV` in all DEV binaries.
2. Tag every write with `environment: "DEV"`; reject if mismatch.
3. Add a startup self‑check that the **keyspace/db/graph** names include `ttrpg_dev` when in DEV.

**Acceptance Tests**:
- Manually set wrong keyspace → startup fails with a clear message.
- Correct config → startup passes and logs the resolved targets.

---

## Prompt 9 — Admin UI Datastore Inspector (MVP)

**Goal**: Add a DEV‑only panel to quickly inspect last job’s datastore footprints.

**Do**:
1. Provide a read‑only panel showing (scoped by `job_id`):
   - Cassandra rows (sample 5) with `chunk_id`, `source_file`.
   - Mongo terms (sample 5) with `term`, `sources[0..2]`.
   - Neo4j relations count (`(t:Term)-[r:MENTIONS]->(c:Chunk)`).
2. Link from each job in the Ingestion Console to this panel.

**Acceptance Tests**:
- After a run, the panel shows non‑empty results for each store.
- If a store is empty/unavailable, show a red badge and actionable hint.

---

## Prompt 10 — Release Notes & Regressions

**Goal**: Lock in fixes and prevent backslides.

**Do**:
1. Add regression tests for prior bugs (e.g., Pass C `chunks_loaded`).
2. Document datastore persistence fixes in `CHANGELOG.md` with upgrade notes.
3. Add a “How we verify persistence” runbook in `/docs/ops/datastores.md`.

**Acceptance Tests**:
- CI runs unit + integration + regression suites for PRs targeting DEV.
- Docs render and link from the Admin UI Help menu (DEV only).

---

# How to Validate (QA Checklist)

1. Start DEV stack (`docker-compose -f docker-compose.dev.yml up -d`), confirm Neo4j present.
2. From Admin UI, upload 3 test PDFs from **Test Uploads** and run Selective Ingestion.
3. Confirm artifacts and manifests complete.
4. Use **Datastore Inspector** (or CLI) to verify:
   - Cassandra `COUNT(*) > 0` for `job_id`.
   - Mongo `countDocuments({ job_id }) > 0`.
   - Neo4j `count(r) > 0` for `(t)-[r]->(c)` scoped by `job_id`.
5. Run `make test-integration-dev` and ensure all green.
