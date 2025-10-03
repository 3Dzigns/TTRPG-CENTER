# CODEX Prompt — Automated QA Manager (Ingestion via Admin UI)

**Role:** Senior Automated QA Manager for TTRPG Center. You operate the Admin UI end-to-end and verify that the ingestion pipeline works with clear observability and zero errors in this DEV environment.

**System Context (follow exactly):**
- Target UI: `http://localhost:8000` (DEV env; ports are env-scoped).  
- Expected ingestion passes for MVP: at minimum Pass A (unstructured.io), Pass B (Haystack), Pass C (LlamaIndex) with manifest + artifacts; later passes may exist—treat them as required if present.  
- Admin UI must show Ingestion Console progress/logs and dictionary visibility.  
- Thumbs-down (👎) should create a bug bundle; defects must be logged for triage.  

**Test Scope:**
1. Launch Admin UI → **Upload Management**.
2. In “Test Uploads”, locate all fixture files. For each file:
   - Upload into the DEV dockerized environment via Upload Management (preserve original filenames).
   - Start a **Selective Ingestion** job for that single file.
   - Open **Job detail** → watch live **Job Logs** and **Container Logs**.
   - Verify every configured pass runs and **finishes without errors**; status must stream phase-by-phase with clear messages.
   - Confirm artifacts/manifest entries exist for the job (chunks, enriched, graph, dictionary delta where applicable).
   - **Validate in Admin UI that updates landed in all three datastores:**
     - Cassandra: new/updated vector embeddings present.  
     - MongoDB: dictionary terms/metadata delta visible.  
     - Neo4J: graph nodes/edges updated for ingested content.  
3. Repeat until **each** test file has completed a selective ingestion run.

**Pass/Fail & Evidence (for each job):**
- **PASS** if:
  - All passes present in this environment show `passed`/green with no stack traces or non-zero exits.
  - `manifest.json` includes tool versions and pass statuses; artifacts directory contains pass outputs (A/B/C at minimum).
  - Admin UI surfaced progress logs clearly (no missing or stale updates).
  - Admin UI datastore views confirm successful persistence into Cassandra, Mongo, and Neo4J.
- **FAIL** if any pass errors, logs are unclear/stale, artifacts or dictionary deltas are missing, or persistence into any datastore is missing or incorrect.

**Defect Logging (every failure or anomaly):**
- Create a **defect bundle** with:
  - Title: `BUG–INGEST–<short-problem>`  
  - Fields: `{env, job_id, file_name, observed, expected, reproduction_steps, screenshots?, job_logs_excerpt, container_logs_excerpt, artifacts_listing}`
  - Save bundle JSON under `./artifacts/bugs/<JOB_ID>/bundle.json`.
- Also produce a short markdown defect note per bug (for human review) summarizing the issue and linking to the bundle.

**Report Output (single consolidated QA report in markdown):**
- Run header: env, date/time, agent, Admin UI version (if shown).
- A table per tested file: {File, Job ID, Passes Run, Result, Artifacts Found, Datastore Updates, Notes}
- A defects section listing all BUGs with reproduction steps and links to bundles.
- A final **Readiness Verdict**: Ready/Not Ready for Phase acceptance.
