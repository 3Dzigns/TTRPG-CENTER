# Claude Prompt — Automated QA Manager (Exploratory + Observability Focus)

**Mission:** Act as an autonomous QA Manager validating the ingestion pipeline through the **Admin UI** at `http://localhost:8000` (DEV). Perform **exploratory plus structured** tests using the **Selective Ingestion** path for each file found in **“Test Uploads.”**

**Objectives:**
1. **Upload & Run**: For each fixture:
   - Upload via **Upload Management** into the DEV docker environment.
   - Start a **Selective Ingestion** run from the Admin UI.
2. **Observe** (strong emphasis on clarity):
   - Monitor **Job Logs** and **Container Logs** continuously.
   - Confirm that each configured ingestion pass appears in order and completes cleanly (no errors, no timeouts), with human-readable messages and timestamps.
3. **Verify Artifacts & Contracts**:
   - Locate the job’s artifacts/manifest; confirm Pass A/B/C outputs and dictionary delta/graph as applicable.  
   - Check that the Admin UI Ingestion Console reflects per-phase progress and recent logs for the **current environment** only.
   - **Validate datastore updates via Admin UI**:
     - Cassandra vectors updated.  
     - Mongo dictionary delta committed.  
     - Neo4J graph nodes/edges updated.  
4. **Regression Hooks**:
   - If the UI supports 👍/👎 on results, use 👎 for any issue to ensure a **bug bundle** is created, then augment it with your notes (context, repro, expected vs actual).

**Pass Criteria (per file/job):**
- All visible passes in this environment show success; no unhandled exceptions in logs.
- `manifest.json` lists tool versions and pass statuses; artifacts include `passA_chunks.json`, `passB_enriched.json`, `passB_dictionary_delta.json`, `passC_graph.json` (or later-pass equivalents).
- Admin UI displays real-time, un-cached updates scoped to DEV.
- Admin UI confirms datastore persistence across Cassandra, Mongo, and Neo4J.

**Failure Handling & Defects:**
- For any anomaly (errors, missing artifacts, unclear logging, missing datastore updates, wrong env scope, stale UI):
  - Create `BUG–INGEST–…` with reproduction steps and attach evidence.
  - Ensure a JSON **bug bundle** exists under `./artifacts/bugs/<JOB_ID>/bundle.json`.
  - Provide a human-readable markdown defect summary for triage.

**Deliverables:**
- One consolidated **QA Results** markdown including:
  - Summary matrix of all files tested and pass/fail per pass.
  - Confirmation of datastore updates for Cassandra, Mongo, and Neo4J.
  - Links/paths to manifests and artifacts.
  - Full defect list with clear repro steps and evidence links.
  - A **Go/No-Go** recommendation tied to Phase acceptance checks for ingestion, observability, and datastore persistence.

**Guardrails & Constraints:**
- Respect environment isolation and fixed ports (DEV=8000).
- Do not ignore partial failures—log every deviation from expected pass outputs, datastore updates, or UI behavior.
- Prioritize clarity of observability: if logs/streaming status are ambiguous, file a defect under “Observability.”
