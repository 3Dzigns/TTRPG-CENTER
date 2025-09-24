# Phase 4 — Continuous Improvement, Freshness, Personalization & Governance

**Goal:** Move from “it works” to “it continually gets better.” Phase 4 adds (1) continuous eval + canary rollouts, (2) feedback → auto-tuning, (3) knowledge freshness & delta ingestion, (4) caching & performance, (5) safe personalization & multi-tenant controls, (6) stronger observability & auditability.
This builds directly on Phase 2 (routing/retrieval) and Phase 3 (graph workflows).

---

## Epic E4.1 — Continuous Evaluation & Quality Gates

### US-401: Eval Dataset & Metrics Harness

**As** an Engineer
**I want** a repeatable offline eval over canonical queries/goals
**So that** every change is quality-gated.

**Acceptance Criteria**

* Dataset format supports: input, expected facts/citations, allowed books, scoring rubric.
* Metrics: EM, F1 (facts), Citation Accuracy, Hallucination Rate, Latency p95, Token Cost.
* CLI `eval:run` produces JSON + HTML report; past runs stored for trend charts.

**Code — minimal evaluator**

```python
# eval/harness.py
from typing import List, Dict
import time, json, pathlib

def score_answer(ans: str, gold: Dict) -> Dict:
    em = int(ans.strip().lower() == gold["expected"].strip().lower())
    f1 = _f1(ans, gold["expected"])
    cit = _citation_ok(ans, gold.get("citations", []))
    return {"em": em, "f1": f1, "cit": cit}

def run_eval(cases: List[Dict], ask_fn) -> Dict:
    out = []
    t0 = time.time()
    for c in cases:
        t1 = time.time()
        res = ask_fn(c["input"])  # wraps Phase-2/3 pipeline
        dt = time.time() - t1
        s = score_answer(res["answer"], c["gold"])
        out.append({**s, "latency_s": dt, "id": c["id"]})
    rep = {
        "n": len(out),
        "em": sum(x["em"] for x in out)/len(out),
        "f1": sum(x["f1"] for x in out)/len(out),
        "cit": sum(x["cit"] for x in out)/len(out),
        "latency_p95": sorted(x["latency_s"] for x in out)[int(.95*len(out))-1],
        "cases": out, "wall_s": time.time() - t0
    }
    pathlib.Path("eval/reports/latest.json").write_text(json.dumps(rep, indent=2))
    return rep
```

**Tests**

* Unit: scorer correctness; citation parsing.
* Functional: 5-case smoke run returns report with all keys.
* Regression: Golden thresholds (e.g., EM/F1 must not drop by >1%).

**Security**

* Ensure eval harness redacts secrets in captured logs.

---

### US-402: CI Quality Gate

**As** a Release Manager
**I want** CI to fail on quality regressions
**So that** only improvements are promoted.

**Acceptance Criteria**

* GitHub Action `eval.yml` runs harness on PR; compares to baseline.
* Gate rules (configurable): `EM >= base-1%`, `CIT >= 0.9`, `HallucRate <= base`.

**Tests**

* Functional: simulate regression → CI fails with clear diff.
* Security: workflow cannot leak dataset or secrets in logs.

---

## Epic E4.2 — Feedback → Rewarding → Auto-Tuning

### US-403: Feedback Capture API

**As** a User/GM
**I want** to thumbs-up/down, annotate issues, and mark “useful/incorrect/unsafe/slow”
**So that** the system learns from real use.

**Acceptance Criteria**

* `POST /feedback {trace_id, rating: up|down, tags:[…], note}` → stored with provenance (model, prompt, plan, chunks).
* Visible in analytics; exportable CSV.

**Code — endpoint stub**

```python
# app_feedback.py
from fastapi import FastAPI
from pydantic import BaseModel
app = FastAPI()

class FeedbackIn(BaseModel):
    trace_id: str; rating: str; tags: list[str] = []; note: str = ""

@app.post("/feedback")
def feedback(body: FeedbackIn):
    # persist: feedback/{trace_id}.json (stub)
    return {"ok": True}
```

**Tests**

* Unit: validates payload; rejects oversized notes.
* Security: sanitize HTML; auth required for private tenants.

---

### US-404: Reward Scoring & Prompt Variant Selector

**As** a Prompt Engineer
**I want** feedback + offline eval to produce a reward score per prompt/model/policy variant
**So that** the router picks better defaults over time.

**Acceptance Criteria**

* Thompson Sampling or ε-greedy bandit over prompt variants per (intent, domain).
* Bandit respects safety/quality floors (from US-402).
* Dashboard shows traffic split and lift vs. baseline.

**Code — tiny bandit**

```python
# tuning/bandit.py
import random
class EpsilonGreedy:
    def __init__(self, eps=0.1): self.eps, self.stats = eps, {}  # {key:{n,mean}}
    def update(self, key, reward: float):
        s = self.stats.setdefault(key, {"n":0,"mean":0.0})
        s["n"] += 1; s["mean"] += (reward - s["mean"])/s["n"]
    def choose(self, key, arms):
        if random.random() < self.eps: return random.choice(arms)
        best = max(arms, key=lambda a: self.stats.get((key,a), {"mean":0})["mean"])
        return best
```

**Tests**

* Unit: update/choose math; cold-start uses exploration.
* Functional: simulated rewards → convergence to best arm.
* Security: guardrails prevent choosing variants below safety floor.

---

## Epic E4.3 — Knowledge Freshness & Delta Ingestion

### US-405: Change Detector & Incremental Re-Index

**As** the Ingestion Service
**I want** to detect changed pages/sections and re-chunk only deltas
**So that** indexes stay fresh with minimal cost.

**Acceptance Criteria**

* Content hashing per section/page; diff → re-embed only changed chunks.
* Emits “corpus version” (monotonic) for cache invalidation.
* Graph delta: add/update affected nodes/edges; mark obsolete with `replaced_by`.

**Code — change detector (simplified)**

```python
# ingest/change_detect.py
import hashlib
def section_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def diff_sections(old: dict, new: dict) -> list[str]:
    """Return section ids that changed."""
    changed = []
    for sid, ntext in new.items():
        if old.get(sid) != section_hash(ntext):
            changed.append(sid)
    return changed
```

**Tests**

* Unit: stable hashes; diffs detect adds/edits/deletes.
* Functional: pipeline only re-embeds changed sids; corpus version increments.

---

### US-406: Post-Update Consistency Check

**As** QA
**I want** automatic checks after updates
**So that** regressions are caught immediately.

**Acceptance Criteria**

* After re-index: run small eval subset for impacted areas; alert if metrics drop.
* Graph invariants: no broken `part_of` chains; no orphan citations.

**Tests**

* Functional: inject synthetic change → invariants OK → eval subset passes.

---

## Epic E4.4 — Performance: Semantic Cache & Memoization

### US-407: Semantic Answer Cache

**As** the Orchestrator
**I want** a TTL’d, corpus-versioned cache keyed by normalized query + plan
**So that** repeated questions are instant.

**Acceptance Criteria**

* Cache key includes: `intent/domain`, normalized query, filters, policy hash, **corpus\_version**, tenant id.
* TTL configurable; invalidated on corpus\_version change or policy/prompt hash change.

**Code — cache facade (Redis/LMDB stub)**

```python
# perf/cache.py
import json, time
class Cache:
    def __init__(self): self.mem = {}
    def key(self, tenant, q_norm, plan_hash, corpus_ver): 
        return f"{tenant}:{q_norm}:{plan_hash}:{corpus_ver}"
    def get(self, k):
        v = self.mem.get(k); 
        return None if not v or v["exp"] < time.time() else v["val"]
    def set(self, k, val, ttl=600):
        self.mem[k] = {"val": val, "exp": time.time()+ttl}
```

**Tests**

* Unit: TTL expiry; version invalidation.
* Security: tenant id in key prevents cross-tenant leakage.

---

### US-408: Artifact & Subtask Memoization

**As** the DAG Executor
**I want** to reuse intermediate artifacts across runs
**So that** repeated Step outcomes aren’t recomputed.

**Acceptance Criteria**

* Idempotency keys per task from (inputs hash, graph node id, version).
* Executor checks artifact store before running; on hit → skip & attach artifact.

**Tests**

* Functional: re-run long workflow; unchanged steps are skipped and reported.

---

## Epic E4.5 — Personalization & Multi-Tenant Safety

### US-409: User/Tenant Profiles & Preferences

**As** an Admin
**I want** per-tenant and per-user settings (style, allowed sources, model limits)
**So that** responses match policy and taste.

**Acceptance Criteria**

* Profile store: `{tenant_id, user_id, prefs:{style, tone, citations_required, max_model}, scopes:[sources]}`.
* Orchestrator merges prefs into prompt/policy and filters retrieval to allowed scopes.

**Code — profile merge**

```python
# auth/profile.py
def build_context(base: dict, profile: dict) -> dict:
    out = base.copy()
    out["style"] = profile["prefs"].get("style", out.get("style","concise"))
    out["allowed_sources"] = profile.get("scopes", [])
    out["max_model"] = profile["prefs"].get("max_model","gpt-5-large")
    return out
```

**Tests**

* Unit: merge precedence; missing keys; defaults.
* Security: retrieval must respect `allowed_sources` (enforced by filter tests).

---

### US-410: Isolation in Cache, Logs & Graph

**As** a Security Engineer
**I want** hard separation between tenants
**So that** no data leaks.

**Acceptance Criteria**

* Tenant-tag all artifacts, cache entries, logs, graph nodes (namespace/label).
* Queries must include tenant filter; CI security test enforces it.

**Tests**

* Security: simulate two tenants with same query → different cache keys, filtered retrieval, isolated artifacts.

---

## Epic E4.6 — Observability, Alerts & Runbooks

### US-411: Streaming Status & UX Events

**As** a Front-End Dev
**I want** SSE/WebSocket events for classify→plan→retrieve→compose
**So that** UI shows real-time progress.

**Acceptance Criteria**

* Event names and payload schema documented; correlation id included.
* Backpressure & rate limiting; disconnect safe.

**Tests**

* Functional: client receives ordered events; latency budget accurate.

---

### US-412: Budget/Anomaly Alerts & Runbooks

**As** an Operator
**I want** alerts when spend spikes or hallucinations increase
**So that** we react fast.

**Acceptance Criteria**

* Alert rules: token spend/day, error rate, eval metric drop, unusual cache miss rate.
* Each alert links to a runbook entry with known fixes.

**Code — simple alert checker**

```python
# ops/alerts.py
def check_alerts(metrics: dict) -> list[str]:
    out=[]
    if metrics["token_spend_usd"] > metrics["limits"]["usd_per_day"]: out.append("BUDGET")
    if metrics["halluc_rate"] > 0.05: out.append("HALLUC")
    return out
```

**Tests**

* Unit: thresholds; hysteresis to avoid flapping.

---

## Epic E4.7 — Compliance & Auditability

### US-413: Version Pinning & Reproducibility

**As** a Compliance Officer
**I want** each answer to pin exact versions (policy, prompt, model, corpus)
**So that** we can reproduce outputs later.

**Acceptance Criteria**

* Response metadata includes: `policy_hash`, `prompt_hash`, `model_name+version`, `corpus_version`, `router_version`.
* `/runs/{trace_id}` returns full run log (sanitized) + downloadable JSON.

**Tests**

* Regression: re-run with same versions → identical answer hash (within stochastic tolerance).

---

### US-414: Export & Data Retention Controls

**As** an Admin
**I want** to export/delete a tenant’s data on request
**So that** we meet compliance.

**Acceptance Criteria**

* Export bundles: feedback, runs, artifacts, logs (sanitized).
* Retention policy enforced with background sweeper.

**Tests**

* Security/Functional: export contains only tenant’s data; delete removes cache/log/artifacts.

---

## Epic E4.8 — Public Controls & Rollouts

### US-415: Feature Flags & Canary Rollouts

**As** a Release Manager
**I want** flaggable changes (policies, prompts, retrievers) and %-based canaries
**So that** we de-risk production.

**Acceptance Criteria**

* Flags defined in `config/flags.yaml`; scoped by tenant/user.
* Canary controller: routes X% to new variant; monitors eval-like metrics; auto-rollback if below floor.

**Code — tiny flag reader**

```python
# ops/flags.py
import yaml, pathlib
def flags():
    return yaml.safe_load(pathlib.Path("config/flags.yaml").read_text())
def is_enabled(flag: str, tenant: str) -> bool:
    f = flags().get(flag, {})
    return tenant in f.get("tenants", []) or f.get("global", False)
```

**Tests**

* Unit: tenant scoping; default off; hot reload.
* Functional: canary split honored; rollback triggers on threshold breach.

---

## Test Plan (Phase 4)

### Unit

* Evaluator scoring; bandit math; change detector; cache TTL; profile merge; flag reader; alert thresholds; version pinning.

### Functional (end-to-end with mocks)

* Feedback in → reward updates → variant selection shifts over time.
* Change in a source page triggers delta re-embed; cache invalidated; new answer cites updated page.
* Tenant isolation across cache/retrieval/artifacts.
* SSE stream shows all pipeline stages.

### Regression

* Golden eval on 30 canonical queries/goals; gates enforced.
* Reproducibility with pinned versions.

### Security

* Cross-tenant cache leakage tests.
* Prompt-injection via feedback notes rejected/sanitized.
* Export/delete adheres to tenant boundaries; logs/PII redacted.

---

## Definition of Done (Phase 4)

* All US-401 … US-415 green across Unit/Functional/Regression/Security in CI.
* CI quality gate running per PR; dashboards show weekly trends.
* Delta ingestion live with corpus\_versioning; caches tied to version.
* A/B or bandit routing active with safety floors; automatic rollback working.
* Tenant isolation verified; version-pinned run logs exportable.
* Alerts wired (stub transport acceptable), runbooks documented.

---

## Quick Start Checklist

1. Create modules:

   ```
   eval/harness.py
   tuning/bandit.py
   ingest/change_detect.py
   perf/cache.py
   auth/profile.py
   ops/{flags.py,alerts.py}
   app_{feedback}.py
   ```
2. Add CI job `eval.yml` to run the harness on a small dataset per PR.
3. Seed `config/flags.yaml`, `config/policies.yaml` safety floors, and a 30-case eval set.
4. Turn on cache with corpus\_version invalidation; add tenant scoping.
5. Start with canary (10%) for one prompt variant; watch lift and rollback thresholds.
