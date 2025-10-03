# ROLE
You are **CODEX (AI Dev)** for the TTRPG Center ingestion stack.

# OBJECTIVE
Fix and prevent a **Pass B** crash caused by `expected an indented block after function definition` in `src_common/pass_b_logical_splitter.py` (error reported at line ~351 inside the packaged image). Then **rebuild**, **redeploy**, **rerun selective ingestion** for the two PDFs, and **verify persistence** in Cassandra, Mongo, and Neo4J via the Admin UI.

# CONTEXT (from latest run)
- **PF1E Core Rulebook (6th Printing)** selective job `selective_1759425732_dev` ran Gate 0 and Pass A, then failed in **Pass B** with the indentation/syntax error; see `env/dev/logs/selective_ingestion_1759425732.log:17`. No writes occurred (Cassandra/Mongo/Neo4J).  
- **Cyberpunk v3 – CP4110 Core Rulebook** selective job `selective_1759426685_dev` hit the same **Pass B** failure; see `env/dev/logs/selective_ingestion_1759426685.log:17`.  
- Containers (`ttrpg-pipeline-worker-dev`, `ttrpg-ingest-dev`, `ttrpg-orchestrator-dev`) only showed routine `/healthz` during the window; exception surfaces only in job logs.  
- Source inventory shows both PDFs still `status=uploaded` with no `available_for_reingestion`—ingestion never reached persistence.  

# REQUIREMENTS & GUARDRAILS (tie into existing phases)
1. **Environment Isolation:** All work must stay under the `env/dev/*` code/config/data/logs tree and respect fixed port conventions (8000/8181/8282). Do **not** contaminate TEST/PROD.  
2. **Phase-1 Hard Gates:** Pass A/B/C must run their real tools, write contract artifacts, and update `manifest.json`. Fail fast if a contract breaks. (No mocks in acceptance.)  
3. **Admin/UI Ops:** Post-fix, Admin UI should reflect pass status and dictionary/graph artifacts per env and respect cache policy.  
4. **Phase-6 DEV Gates:** Add a regression test that **fails** on syntax/indentation errors in Pass B and blocks promotion in DEV CI. Thumbs-down should generate a bug bundle; thumbs-up produces a regression fixture.  

# DELIVERABLES
- A **one-commit PR** titled: `FIX: Pass B logical splitter syntax error + tests + image rebuild`
- Updated **code** in `src_common/pass_b_logical_splitter.py` with the indentation/syntax fix.
- New/updated **tests** that catch this class of failure (import/parse/exec of Pass B module).
- CI green in DEV with Phase-6 gate enforcing the new test.
- Rebuilt **images** for DEV, redeployed, stale artifacts cleared, selective jobs rerun successfully for both PDFs.
- Verified **Pass G** completion and **DB persistence** (Cassandra vectors, Mongo dictionary, Neo4J graph) visible in Admin UI.

# TASKS
## 1) Reproduce & Localize
- Tail logs to confirm the precise failure locus:
  - `grep -n "expected an indented block" env/dev/logs/selective_ingestion_*.log`
- Inspect the packaged file **inside the running/built image** to confirm line numbers drift:
  - `docker exec -it ttrpg-ingest-dev bash -lc 'nl -ba /app/src_common/pass_b_logical_splitter.py | sed -n "330,380p"'`
- In the **repo working copy**, open the same file and compare:
  - `nl -ba src_common/pass_b_logical_splitter.py | sed -n "330,380p"`

## 2) Fix the Syntax/Indentation Defect
- Identify the function starting near line ~350 with a missing/empty block (e.g., `def split_logically(...):` followed by a docstring/comment and no indented body).
- Provide a minimal, correct body (even if it just raises `NotImplementedError` in unreachable branches) and ensure **all branches** have indented suites.
- Run a local syntax check:
  - `python -m py_compile src_common/pass_b_logical_splitter.py`
- Add/ensure linter in dev CI (ruff/flake8) flags empty blocks and bad indents:
  - Example ruff config: `E701,E901,E902`, `F401–F403` as appropriate.

## 3) Add Tests to Prevent Regression (Phase-6 Gate)
- **Unit smoke import:** `tests/unit/test_pass_b_import.py`
  - Asserts module imports without `SyntaxError`.
- **Functional contract hook:** `tests/functional/test_pass_b_splitter_contract.py`
  - Provides a tiny fake Pass A chunk set and asserts the splitter returns **non-empty** or **well-typed** segments (shape only; no external tools).
- Wire tests into DEV gate so that any **SyntaxError** or **ImportError** in Pass B fails CI and blocks promotion (per Phase-6).  

## 4) Rebuild & Redeploy (DEV only)
- Clean and rebuild ingestion/orchestrator/worker images **for DEV**:
  - `docker compose -f env/dev/docker-compose.yml build --no-cache ttrpg-ingest-dev ttrpg-orchestrator-dev ttrpg-pipeline-worker-dev`
  - `docker compose -f env/dev/docker-compose.yml up -d`
- Verify `/healthz` on the DEV port and ensure only `env/dev/*` paths are touched (Phase-0 isolation).  

## 5) Clear Stale Job Artifacts
- Remove prior selective artifacts/logs to avoid false positives:
  - `rm -rf env/dev/artifacts/selective_*`
  - Optionally rotate logs: `find env/dev/logs -type f -name "selective_ingestion_*.log" -delete`

## 6) Rerun the Two Selective Jobs
- Trigger **PF1E Core Rulebook (6th Printing)** and **Cyberpunk v3 – CP4110** selective runs via your usual Admin action or CLI, ensuring Gate 0 → Pass A → **Pass B** now proceeds to **C–G**.
- Stream logs and confirm gate statuses update in `manifest.json` and the Ingestion Console (Phase-1 acceptance).  

## 7) Post-Run Validation (DBs + UI)
- **Cassandra (vectors):** Confirm new embeddings for both job IDs exist in the DEV keyspace/collection.
- **Mongo (dictionary):** Confirm dictionary deltas from Pass B were **upserted** and visible in Admin UI dictionary view. (Phase-1 DICT acceptance.)  
- **Neo4J (graph):** Confirm Pass C→G produced nodes/edges and they appear in Admin graph views and/or API.
- **UI cache behavior:** Admin UI reflects new state promptly, respecting Phase-5 cache policy for fast retests.  

# ACCEPTANCE CRITERIA
1. **No Syntax/Indentation Errors**: `python -m py_compile src_common/pass_b_logical_splitter.py` passes; unit test `test_pass_b_import.py` is green. (Phase-6 gate enforces.)  
2. **Pass-B Succeeds** for both selective jobs; **Passes C–G** complete; `manifest.json` shows `status: passed` for all passes and records tool versions/timings.  
3. **Artifacts Present**: `passB_enriched.json`, dictionary delta, graph outputs, plus structured logs under `env/dev/artifacts/<job_id>/`.  
4. **Persistence Verified**: New rows/docs/nodes visible in Cassandra/Mongo/Neo4J via Admin UI.  
5. **Environment Isolation** respected: only `env/dev/*` paths/ports touched during the fix & reruns.  
6. **Regression Shield** added: breaking the indentation again **fails CI** and blocks promotion automatically (DEV gates).  

# COMMAND CHEATSHEET (DEV)
```bash
# Inspect packaged file in container
docker exec -it ttrpg-ingest-dev bash -lc 'nl -ba /app/src_common/pass_b_logical_splitter.py | sed -n "330,380p"'

# Local syntax check
python -m py_compile src_common/pass_b_logical_splitter.py

# Run tests (focus + full)
pytest -q tests/unit/test_pass_b_import.py
pytest -q tests/unit tests/functional

# Rebuild & restart DEV services
docker compose -f env/dev/docker-compose.yml build --no-cache ttrpg-ingest-dev ttrpg-orchestrator-dev ttrpg-pipeline-worker-dev
docker compose -f env/dev/docker-compose.yml up -d

# Clear stale artifacts/logs
rm -rf env/dev/artifacts/selective_*
find env/dev/logs -type f -name "selective_ingestion_*.log" -delete
```

# PR CHECKLIST (fill before submit)
- [ ] Syntax fix applied; module imports cleanly.
- [ ] New unit & functional tests added and green; DEV gate blocks on failure.  
- [ ] Manifest entries updated during selective reruns; artifacts present.  
- [ ] Admin UI shows updated statuses and dictionary/graph data; cache behavior aligns with Phase-5.  
- [ ] Verified only `env/dev/*` touched; ports match Phase-0 map.  
