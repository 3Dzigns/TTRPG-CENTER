# Phase 3 — Graph-Centered Long-Horizon Reasoning & Multi-Step Workflows

**Goal:** Enable reliable multi-step tasks by (1) representing rules, entities, and procedures in a **knowledge & workflow graph**, (2) planning across that graph, (3) executing stepwise with retries, (4) tracking provenance & state, and (5) exposing human-in-the-loop checkpoints.
**Key idea:** Retrieval still happens, but **the Graph becomes the backbone** for decomposition, guardrails, and source-aware answers.

Below are epics and detailed user stories with acceptance criteria, **tests (Unit, Functional, Regression, Security)**, and **drop-in Python snippets** (FastAPI + your current stack stubs: AstraDB/Chroma, etc.). Naming matches Phase-2 style.

---

## Epic E3.1 — Graph Data Model & APIs

### US-301: Graph Schema & Store

**As** a Systems Architect
**I want** a normalized schema for **Knowledge Graph (KG)** and **Workflow Graph (WG)**
**So that** entities, rules, procedures, and tasks are linkable and traversable.

**Acceptance Criteria**

* **Node types (min):** `Rule`, `Concept`, `Procedure`, `Step`, `Entity`, `SourceDoc`, `Artifact`, `Decision`.
* **Edge types (min):** `depends_on`, `part_of`, `implements`, `cites`, `produces`, `variant_of`, `prereq`.
* Graph store adapter with CRUD + param queries; all operations versioned (write-ahead log).
* Ingest pipeline from Phase-1/2 can upsert nodes/edges with stable IDs referencing chunk IDs.

**Code (schema + adapter)**

```python
# graph/store.py
from typing import Dict, List, Literal, Optional
NodeType = Literal["Rule","Concept","Procedure","Step","Entity","SourceDoc","Artifact","Decision"]
EdgeType = Literal["depends_on","part_of","implements","cites","produces","variant_of","prereq"]

class GraphStore:
    def __init__(self, client=None): self.client = client  # stub to DB/Neo4j/Astra Graph
    def upsert_node(self, node_id: str, ntype: NodeType, props: Dict) -> Dict: ...
    def upsert_edge(self, src: str, etype: EdgeType, dst: str, props: Dict) -> Dict: ...
    def get_node(self, node_id: str) -> Optional[Dict]: ...
    def neighbors(self, node_id: str, etypes: Optional[List[EdgeType]]=None, depth: int=1) -> List[Dict]: ...
    def query(self, pattern: str, params: Dict) -> List[Dict]: ...  # param-safe, no string concat
```

**Unit Tests**

* Node/edge upsert idempotent; invalid types rejected; depth-limited neighbors capped.

**Security**

* Parametrized queries; max depth/config guard; PII redaction on node props.

---

### US-302: Graph Builder from Retrieval

**As** the Ingestion Service
**I want** to convert retrieved chunks and detected procedures into KG/WG nodes/edges
**So that** long tasks have explicit steps & dependencies.

**Acceptance Criteria**

* Heuristics/LLM tags `Procedure` + `Step` with `prereq/part_of` edges.
* `SourceDoc` attaches to `Rule/Procedure` via `cites` with book/page when available.
* Duplicate detection by normalized titles + hash of canonical text.

**Code (builder stub)**

```python
# graph/build.py
def build_procedure_from_chunks(chunks) -> dict:
    """Return {'procedure': node, 'steps':[nodes], 'edges':[edges]}"""
    # heuristics: ordered headings → steps; bullet lists → substeps
    return {"procedure": {"id":"proc:craft-potion","type":"Procedure"},
            "steps":[{"id":"step:1","type":"Step","props":{"name":"Gather reagents"}},
                     {"id":"step:2","type":"Step","props":{"name":"Check DC"}}],
            "edges":[("proc:craft-potion","part_of","step:1",{}),
                     ("proc:craft-potion","part_of","step:2",{})]}
```

**Tests**

* Functional: feed known “Craft Potion” chunks → 2+ steps created, cites edges preserved.

---

## Epic E3.2 — Planner & Workflow Decomposition

### US-303: Task Planner (Graph-Aware)

**As** the Orchestrator
**I want** a planner that maps a **user goal** to a **workflow plan (DAG)** using the graph
**So that** multi-step processes are explicit, resumable, and checkable.

**Acceptance Criteria**

* Input: `{goal, context}` → Output: `Plan {nodes: [Tasks], edges: [depends_on]}`.
* Uses KG/WG to pick **Procedure** and **Steps**; fills step **parameters** (e.g., DC, system).
* Produces **checkpoints** after key `Decision` nodes; respects `prereq`.

**Code (planner outline)**

```python
# planner/plan.py
from typing import Dict, List
def plan_from_goal(goal: str, graph, constraints: Dict) -> Dict:
    proc = select_procedure(goal, graph)            # graph search + scoring
    steps = expand_steps(proc, graph)               # traverse 'part_of'
    dag   = linearize_with_dependencies(steps)      # topological order
    return {"procedure": proc, "tasks": dag["tasks"], "edges": dag["edges"]}
```

**Unit Tests**

* Deterministic DAG for same inputs; cycles detected and rejected with helpful error.

**Functional Tests**

* Goal: “Build a PF2e character using ABP, level 5” → plan selects Procedure + steps (choose ancestry, assign boosts, pick feats, compute ABP bonuses).

---

### US-304: Cost-/Latency-Aware Action Selection

**As** a Systems Engineer
**I want** planner hooks to choose **tool/model** per task (small vs. large model, local tools)
**So that** complex plans stay fast and within budget.

**Acceptance Criteria**

* Each task node carries `{tool, model, prompt}` chosen via rules using Phase-2 router + step type.
* Budget caps: max parallelism, total expected tokens, fail-open degrade path defined.

**Unit/Security Tests**

* Enforce configured max budget; if exceeded → planner emits “needs approval” checkpoint.

---

## Epic E3.3 — Executor, State & Provenance

### US-305: DAG Executor with Retries

**As** the Runtime
**I want** to execute the plan DAG with **retries, backoff, and partial re-runs**
**So that** flaky steps don’t abort the whole workflow.

**Acceptance Criteria**

* Executor supports statuses: `pending/running/succeeded/failed/skipped`.
* Per-task retry policy (max\_attempts, backoff); idempotent side-effects (via task keys).
* Emits `workflow_id`, `task_id` and writes **State** to a store.

**Code (executor skeleton)**

```python
# runtime/execute.py
import time
def run_plan(plan, task_fn, state_store, max_parallel=3):
    ready = [t for t in plan["tasks"] if not t["deps"]]
    while ready:
        t = ready.pop(0)
        try:
            state_store.start(t["id"])
            res = task_fn(t)                      # tool/model call
            state_store.finish(t["id"], res)
        except Exception as e:
            if t.get("retries",0) < t.get("max_attempts",2):
                t["retries"] = t.get("retries",0)+1
                time.sleep(min(2**t["retries"], 8))
                ready.append(t)
            else:
                state_store.fail(t["id"], str(e))
                # downstream tasks that depend on t → skipped or blocked
        # enqueue newly unblocked tasks...
```

**Unit Tests**

* Retry/backoff counters; blocked tasks never run; idempotency key honored.

---

### US-306: Workflow State & Artifacts

**As** the Web UI/Discord client
**I want** a **state API** to fetch current status and artifacts (tables, JSON, files)
**So that** users can observe progress and download results.

**Acceptance Criteria**

* `/workflow/{id}` returns graph of tasks with status, timestamps, and links to artifacts.
* Artifacts include `Artifact` nodes linked by `produces` edges; checksums stored.

**Code (FastAPI surface)**

```python
# app_workflow.py
from fastapi import FastAPI
app = FastAPI()

@app.get("/workflow/{wid}")
def get_workflow(wid: str):
    # read from state store; return statuses + artifacts (stub)
    return {"workflow_id": wid, "tasks": [], "artifacts": []}
```

**Functional Tests**

* Start long plan; poll endpoint; see statuses change; download at least one artifact.

---

### US-307: Provenance & Citation Stitching

**As** a Compliance Officer
**I want** end-to-end provenance with **source citations per step and final answer**
**So that** results are auditable and reproducible.

**Acceptance Criteria**

* Every step records: inputs, retrieved chunk IDs, graph nodes visited, model+prompt hash, outputs.
* Final answer includes **Sources** aggregated and deduped; mismatch triggers warning banner.

**Unit/Regression Tests**

* Stable provenance schema; golden tests compare citation sets for canonical workflows.

---

## Epic E3.4 — Graph-Centered Reasoning Patterns

### US-308: Multi-Hop QA via Graph Walk + Re-Grounding

**As** the Reasoner
**I want** to alternate: graph walk → targeted retrieval → compact reasoning
**So that** long chains stay grounded.

**Acceptance Criteria**

* For tasks with `complexity=high`, executor inserts **re-grounding steps** after each 2–3 hops.
* If retrieval confidence drops below θ, planner requests human checkpoint.

**Code (reasoning loop)**

```python
# reason/graphwalk.py
def graph_guided_answer(goal, graph, retriever, llm, hops=3):
    node = seed_from_goal(goal, graph)
    context = []
    for i in range(hops):
        nbrs = graph.neighbors(node["id"], depth=1)
        focus = select_next(nbrs)           # scoring function
        ctx = retriever(focus)              # targeted
        context.extend(ctx)
        if low_confidence(context): break
        node = focus
    return llm(context)                      # final compose
```

**Tests**

* Functional: complex rules question improves EM/F1 vs non-graph baseline on local eval set.

---

### US-309: Procedural Executors (Checklists & Guards)

**As** the Workflow Runner
**I want** typed executors for `Procedure/Step` nodes (checklists, calculators, verifiers)
**So that** rule-bound tasks (e.g., crafting, leveling) are consistent.

**Acceptance Criteria**

* Built-in executors: `ChecklistExecutor`, `ComputeDCExecutor`, `RulesVerifier`.
* Each returns structured outputs (e.g., `{"dc": 23, "modifiers":[...]}`).
* Verifier fails step if cited rule not present in context.

**Unit/Security Tests**

* Executor cannot proceed if citations missing; malicious prompt attempts ignored.

---

## Epic E3.5 — HITL, Reviews, and Recovery

### US-310: Human-in-the-Loop Checkpoints

**As** a Power User/GM
**I want** optional approval on `Decision` nodes or over-budget plans
**So that** expensive/ambiguous branches are confirmed.

**Acceptance Criteria**

* Planner marks `Decision` nodes with `requires_approval=True` when ambiguity or budget > threshold.
* `/workflow/{id}/approve?task={tid}&choice={A|B}` API unblocks.

**Functional/Security Tests**

* Unauthorized approvals rejected; audit log records approver, choice, and time.

---

### US-311: Failure Recovery & Partial Replay

**As** an Operator
**I want** to **resume** failed workflows from the last good checkpoint
**So that** long runs are salvageable.

**Acceptance Criteria**

* `/workflow/{id}/resume` re-plans only failed subtree and respects existing artifacts.
* Executor supports **selective re-run**: `rerun(task_id)`.

**Unit/Functional Tests**

* Kill mid-run → resume completes without repeating succeeded steps.

---

## Epic E3.6 — Observability, Budgets & Policies

### US-312: Budget & Policy Enforcement

**As** a FinOps Owner
**I want** per-workflow **token/time budget** and policy enforcement
**So that** long tasks don’t run away.

**Acceptance Criteria**

* Planner estimates token/time; executor checks cumulative usage; hard stop at limits.
* Policy file (YAML) with per-role caps (Admin vs. Player), per-model ceilings.

**Unit/Security Tests**

* Exceeding limits → graceful halt with summary; policies hot-reload, validated at load.

---

### US-313: Tracing (End-to-End Spans)

**As** an Engineer
**I want** OpenTelemetry spans from plan → execute → answer
**So that** I can debug slowness and bottlenecks.

**Acceptance Criteria**

* Correlation ID through all steps; per-task latencies & token counts logged.
* Redaction on logs for secrets/PII.

**Tests**

* Functional: spans cover >95% of wall time; log redaction unit tests.

---

## Epic E3.7 — Public API & UI Hooks

### US-314: `/plan` & `/run` Endpoints

**As** a Client
**I want** to plan first (preview) and then run, or run directly
**So that** I can inspect cost, steps, and approvals.

**Acceptance Criteria**

* `POST /plan {goal, constraints?}` → `{plan, estimate, checkpoints}`
* `POST /run {goal|plan_id}` → `{workflow_id}`
* Webhooks (optional) for task status changes.

**Code (FastAPI surface)**

```python
# app_plan_run.py
from fastapi import FastAPI
from planner.plan import plan_from_goal
app = FastAPI()

@app.post("/plan")
def plan(payload: dict):
    plan = plan_from_goal(payload["goal"], graph=None, constraints=payload.get("constraints",{}))
    return {"plan": plan, "estimate": {"tokens": 12000, "time_s": 90}, "checkpoints": []}

@app.post("/run")
def run(payload: dict):
    # create workflow_id and dispatch executor (stub)
    return {"workflow_id": "wf_12345"}
```

**Functional Tests**

* Planning shows non-empty steps; running yields a valid `workflow_id`.

---

## Test Plan (Phase-3)

### 1) Unit Tests (examples)

* `tests/unit/test_graph_store.py`: upserts, neighbors depth cap, param queries.
* `tests/unit/test_graph_build.py`: procedure extraction from text.
* `tests/unit/test_planner.py`: DAG creation, cycle detection, budget gating.
* `tests/unit/test_executor.py`: retries, idempotency, selective rerun.
* `tests/unit/test_provenance.py`: citation stitching, schema validation.
* `tests/unit/test_reason_graphwalk.py`: hop selection & re-grounding cadence.

### 2) Functional Tests (end-to-end, mocked externals)

* **Scenario A (Crafting Procedure):** “Craft a healing potion given DC X; show steps & rolls.”

  * Expect: Procedure with Steps; `ComputeDCExecutor` invoked; sources include rule citations.
* **Scenario B (Character Build, ABP):** “Create a level 7 PF2e character with ABP, sword & board.”

  * Expect: WG with decisions; HITL for feat choices; artifacts: JSON stat block.
* **Scenario C (Lore-Rules Blend):** “Prepare a 3-session quest outline and required checks.”

  * Expect: Graph walk across lore + rules; re-grounding every 2 hops; sources aggregated.

### 3) Regression Tests

* **Golden workflows**: store planned DAGs for 10 canonical goals and compare node/edge IDs + step labels (allow minor tolerance on prompts).
* **Answer diff guard**: final citations set must be a superset of Phase-2 for the same queries.

### 4) Security Tests

* Injection attempts inside `goal` cannot add/alter graph policies or bypass checkpoints.
* Depth bombs (hops > allowed) safely truncated; planner refuses with actionable message.
* Approval API: authz required; replay attacks blocked (nonce + expiry).

---

## Definition of Done (Phase-3)

* US-301 … US-314 all **Green** on Unit/Functional/Regression/Security in CI.
* Graph schema & adapters documented; migration scripts provided.
* Long-horizon tasks demonstrably improved on internal evals (≥15% EM/F1 for complex multi-hop vs Phase-2).
* **Observability:** trace IDs per workflow; per-task token/time; budgets enforced.
* **Provenance:** every output has step-level citations and a downloadable run log (JSON).
* **HITL:** approvals work; resume/replay tested; artifacts downloadable.

---

## Quick Start Checklist

1. Create modules:

   ```
   graph/{store.py,build.py}
   planner/{plan.py}
   runtime/{execute.py,state.py}
   reason/{graphwalk.py}
   app_{workflow,plan_run}.py
   tests/{unit,functional,regression,security}/
   ```
2. Wire the graph adapter to your chosen backend (Astra Graph/Neo4j/etc.).
3. Seed a few Procedures (e.g., Crafting, Character Creation, Downtime Actions) to demo.
4. Turn on budgets & HITL in `config/policies.yaml`.
5. Add CI: `pytest -q --maxfail=1 --disable-warnings --cov`.
