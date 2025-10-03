# Claude Prompt — Automated QA Manager (STRICT: Test Uploads + DB Upserts, DEV Docker)
**Role:** Operate as an **Autonomous QA Manager**. You will validate the ingestion pipeline **through the Admin UI** at `http://localhost:8000` **in the DEV docker environment only**. Your run is **invalid** unless it (1) uses the files from the **Test Uploads** folder via the Admin UI and (2) proves **real upserts** into **Cassandra (vectors)**, **Mongo (dictionary)**, and **Neo4j (graph)** with screenshots and query snippets.

---

## 0) Non‑Negotiable Ground Rules

1. **Environment lock:** Perform all actions against **DEV** (`localhost:8000`). Do **not** touch TEST/PROD.
2. **Source of truth:** Upload **only** from the Admin UI’s **Upload Management → “Test Uploads”**. Do **not** use any other fixture path or hardcoded samples.
3. **Selective Ingestion only:** For each uploaded file, start a **Selective Ingestion** job from the Admin UI.
4. **Must upsert:** A run is **FAILED** unless you verify **successful upserts** into Cassandra, Mongo, and Neo4j for each file.
5. **Evidence or it didn’t happen:** Attach Admin UI screenshots and container-shell query outputs proving the upserts. Redact secrets.

---

## 1) Test Dataset Enforcement (Admin UI Only)

**Action:** Open Admin UI → **Upload Management** → navigate to **“Test Uploads”**.
**For each file** present there at test time:

- Record the **exact file names and sizes** as shown in the UI.
- **Upload** the file via the Admin UI into the **DEV** environment (confirm target path shows `/env/dev/uploads/...`).
- Launch **Selective Ingestion** for the uploaded file from the Admin UI.

> ❗ If “Test Uploads” is empty, mark **BLOCKED** and file a defect: `BUG-INGEST-DATA-EMPTY` with the Admin UI screenshot.

---

## 2) DEV Containers & Service Health (pre-flight)

Before running any ingestion:

- Confirm DEV stack is healthy. At minimum the following services (or their project‑specific names) must be **running**:
  - Admin API/UI (port **8000**)
  - Ingest / Orchestrator / Worker services
  - **Cassandra** (vector store), **MongoDB** (dictionary), **Neo4j** (graph)
- Capture **docker ps** output (filtered) as evidence:
  - `docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | sort`
- If any datastore container is not healthy, **STOP** and file `BUG-ENV-DB-NOT-READY`.

---

## 3) Run Selective Ingestion (per file)

For **each uploaded file** from *Test Uploads*:

1. Start **Selective Ingestion** from Admin UI.
2. **Observe logs** in the Admin UI:
   - Ensure Gate 0, Pass A, Pass B, Pass C, … appear **in order** and complete **without errors**.
   - Capture log screenshots that include job id, pass transitions, and final completion.
3. **Artifacts/Manifest check (DEV path only):**
   - Confirm the job directory under `env/dev/artifacts/<JOB_ID>/` exists.
   - Verify `manifest.json` plus per‑pass artifacts (A/B/C… as implemented).
   - Record **tool versions** and **completed_phases** values from the manifest.

> ❗ If any pass errors or artifacts are missing, mark the file **FAIL** and open `BUG-INGEST-PASS-<X>` with evidence.

---

## 4) **Mandatory Datastore Upsert Verification** (per file)

You must demonstrate **actual writes** into all three datastores, tied to the specific **JOB_ID** and **document id**.

### 4.1 Cassandra (Vectors)
- From **inside the Cassandra container** (DEV), run **read‑only** queries to confirm new/updated embeddings for the document/job.
- Example (adapt names to your schema/keyspace/table):
```
docker exec -it <cassandra_dev_container> cqlsh -e "
DESCRIBE KEYSPACES;
USE ttrpg_dev;
SELECT doc_id, job_id, chunk_id, embedding[0..3] AS preview
FROM vectors
WHERE job_id = '<JOB_ID>'
LIMIT 5;
"
```
- Take a screenshot of the result. Note non‑empty rows tied to **this** JOB_ID.

### 4.2 MongoDB (Dictionary)
- From **inside the Mongo container**, verify dictionary deltas/upserts:
```
docker exec -it <mongo_dev_container> mongosh --quiet --eval '
use ttrpg_dev;
db.dictionary.find({ job_id: "<JOB_ID>" }, { term:1, kind:1, sources:1 }).limit(5).pretty();
'
```
- Capture output showing terms created/updated referencing this **JOB_ID** and **source pages**.

### 4.3 Neo4j (Graph)
- From **inside the Neo4j container**, verify nodes/edges for the ingested document:
```
docker exec -it <neo4j_dev_container> cypher-shell "
MATCH (t:Term)-[r:MENTIONS]->(c:Chunk)
WHERE t.job_id = '<JOB_ID>'
RETURN t.term AS term, c.chunk_id AS chunk, count(r) AS links
LIMIT 10;
"
```
- Capture output showing nodes/edges **created by this run**.

> ✅ **Pass criteria for Upsert:** Non‑empty, job‑scoped results in **all three** stores.
> ❌ If any store returns **no rows/nodes**, mark **FAIL** and open `BUG-INGEST-Upsert-<STORE>`.

---

## 5) Admin UI Confirmation (post‑upsert)

- Navigate to the **Ingestion Console** and **Dictionary/Graph** views (if available):
  - Confirm that the **DEV** scope shows recent entries relating to the new JOB_ID.
  - Capture screenshots: summary counts, recent items, and any job/document links.

---

## 6) Results Matrix & Evidence

Produce a single **QA Results** markdown containing:

- **Environment stamp:** build id, service versions, container names/ids.
- **Dataset table:** files processed (exact names from **Test Uploads**), sizes.
- **Per‑file matrix:** Gate 0, Pass A…G status, **Artifacts OK?**, **Cassandra OK?**, **Mongo OK?**, **Neo4j OK?**, **Overall**.
- **Links/paths** to `env/dev/artifacts/<JOB_ID>/manifest.json` and pass artifacts.
- **Screenshots**:
  - Admin UI: Upload, job run, logs, datastore views.
  - Terminal: cqlsh/mongosh/cypher-shell outputs filtered to **JOB_ID**.
- **Defects** with **repro steps** and expected vs actual, using naming:
  - `BUG-INGEST-DATA-EMPTY`, `BUG-ENV-DB-NOT-READY`, `BUG-INGEST-PASS-<X>`, `BUG-INGEST-Upsert-<STORE>`.
- **Go/No‑Go** recommendation with reasons.

> Include a short **Appendix** with the exact commands you ran (docker exec queries) and redact any credentials.

---

## 7) Pass/Fail Criteria (Strict)

A file/job is **PASS** only if **all** of the below are true:
1. File was **sourced from Admin UI → “Test Uploads”** (with screenshot).
2. Gate/Passes complete **without errors** (with logs).
3. Manifest + artifacts present under **`env/dev/artifacts/<JOB_ID>/`**.
4. **Verified upserts** in **Cassandra**, **Mongo**, and **Neo4j** for that **JOB_ID** (with query evidence).
5. Admin UI reflects the new data under **DEV** scope.

If any item is missing → **FAIL**.

---

## 8) Guardrails & Observability

- Respect **DEV-only** isolation. Do not hit TEST/PROD URLs or volumes.
- Prefer **read‑only** DB queries; never mutate outside the ingestion pipeline.
- Timebox each file to a reasonable maximum (but do **not** skip upsert checks).
- If logs or UI appear stale, use the Admin UI **“Disable cache now”** / **refresh controls** if present.
- Every deviation from expected behavior must be captured as a defect with evidence.

---

## 9) Deliverables

1. **QA_Results_<YYYYMMDD_HHMM>_DEV.md** with the full matrix, links, and screenshots.
2. All screenshots saved under `env/dev/artifacts/<RUN_ID>/evidence/` (or the project‑standard evidence path).
3. Defect markdown files saved to the repo’s `bugs/` folder (or the project‑standard location).

---

### Quick Reference — Container Query Cheatsheet (adjust names to your stack)

```
# Cassandra (vectors)
docker exec -it ttrpg-cassandra-dev cqlsh -e "USE ttrpg_dev; SELECT doc_id, job_id, chunk_id FROM vectors WHERE job_id='<JOB_ID>' LIMIT 5;"

# Mongo (dictionary)
docker exec -it ttrpg-mongo-dev mongosh --quiet --eval 'use ttrpg_dev; db.dictionary.find({ job_id: "<JOB_ID>" }).limit(5).pretty();'

# Neo4j (graph)
docker exec -it ttrpg-neo4j-dev cypher-shell "MATCH (t:Term)-[r:MENTIONS]->(c:Chunk) WHERE t.job_id='<JOB_ID>' RETURN t.term, c.chunk_id, count(r) LIMIT 10;"
```

> Replace container names/database names with the actual values used by your **DEV docker-compose**. Always scope by **`job_id`** to avoid false positives.
