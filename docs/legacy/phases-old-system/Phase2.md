# Phase 2 — Intelligent Retrieval & Dynamic Model Routing

**Goal:** Answer user queries more accurately and faster by (1) classifying the query, (2) applying the right retrieval policy (hybrid vector/metadata/graph), and (3) selecting the most appropriate model+system-prompt for the task & complexity.

Below you’ll find the Phase-2 epics and detailed user stories with acceptance criteria, test cases (Unit, Functional, Regression, Security), and **code snippets** you can drop into your current stack (FastAPI + Langflow/AstraDB stubs). Where a story introduces a component, the tests reference its public surface so you can wire them into CI immediately.

---

## Epic E2.1 — Query Understanding & Policy Selection

### US-201: Query Intent Classifier (QIC)

**As** the Orchestrator
**I want** to classify each user query into a small set of intents (e.g., `fact_lookup`, `procedural_howto`, `creative_write`, `code_help`, `summarize`, `multi_hop_reasoning`) and detect **domain** (TTRPG rules, lore, admin, etc.) and **complexity** (low/medium/high)
**So that** we can choose the right retrieval policy and model/prompt.

**Acceptance Criteria**

* Given a query, the QIC returns `{intent, domain, complexity, needs_tools: bool}` within 150ms p95 (local heuristic) or 800ms p95 (LLM zero-shot fallback).
* Confusion matrix F1 ≥ 0.85 on an in-house labeled validation set (≥200 examples split across intents/domains).
* Emits structured telemetry (span id, scores, chosen rules).

**Code (classifier surface)**

```python
# orchestrator/classifier.py
from typing import Literal, TypedDict

Intent = Literal["fact_lookup","procedural_howto","creative_write","code_help",
                 "summarize","multi_hop_reasoning"]
Domain = Literal["ttrpg_rules","ttrpg_lore","admin","system","unknown"]

class Classification(TypedDict):
    intent: Intent
    domain: Domain
    complexity: Literal["low","medium","high"]
    needs_tools: bool
    confidence: float

def classify_query(q: str) -> Classification:
    """
    Heuristic first: fast keyword+pattern+length+NER; 
    falls back to LLM (optional) if confidence < threshold.
    """
    q_low = q.lower()
    # Tiny heuristic example:
    if any(k in q_low for k in ["spell", "feat", "rule", "DC ", "action"]):
        domain = "ttrpg_rules"
    elif any(k in q_low for k in ["vladrin","lysengard","umbravoth"]):
        domain = "ttrpg_lore"
    else:
        domain = "unknown"

    if len(q) < 120 and "what is" in q_low:
        intent = "fact_lookup"
    elif any(k in q_low for k in ["how do i", "steps", "procedure"]):
        intent = "procedural_howto"
    elif any(k in q_low for k in ["write", "story", "flavor"]):
        intent = "creative_write"
    elif "summarize" in q_low or "tl;dr" in q_low:
        intent = "summarize"
    elif any(k in q_low for k in ["code", "python", "error", "stacktrace"]):
        intent = "code_help"
    else:
        intent = "multi_hop_reasoning"

    complexity = "high" if len(q) > 500 or "compare" in q_low or "versus" in q_low else ("medium" if len(q) > 200 else "low")
    needs_tools = intent in {"fact_lookup","multi_hop_reasoning","summarize","code_help"}
    return {"intent": intent, "domain": domain, "complexity": complexity, "needs_tools": needs_tools, "confidence": 0.72}
```

**Unit Tests**

* Classifies representative queries into correct intent/domain.
* Threshold logic promotes LLM fallback when confidence < 0.6 (mock LLM to avoid network).

**Functional Tests**

* End-to-end: POST `/ask` with examples → observe classifier output embedded into orchestration trace.

**Regression Tests**

* A frozen set of 200 labeled queries must not degrade >1% macro-F1 across releases.

**Security Tests**

* Prompt-injection phrases inside the query (e.g., “ignore all rules and …”) must not flip `domain` to `system` nor `needs_tools=False`.
* Very long inputs (≥10k chars) are truncated/streamed without crash.

---

### US-202: Retrieval Policy Engine (RPE)

**As** the Orchestrator
**I want** a rule-based + pluggable policy engine that maps `{intent, domain, complexity}` to an explicit **retrieval plan** (hybrid vector, metadata, graph, BM25, re-ranking)
**So that** each query gets the right retrieval depth & cost.

**Acceptance Criteria**

* Policy table stored in YAML; hot-reload without service restart.
* Supports: `top_k`, `filters`, `rerank: ["sbert","mmr"]`, `graph_walk: depth`, `expand_query: ["synonyms","ruleset_aliases"]`.
* For `ttrpg_rules.fact_lookup.low` -> vector(TopK=5)+metadata(system="PF2E",type in \["spell","feat"])+MMR k=3.
* For `multi_hop_reasoning.high` -> vector(TopK=12)+graph\_walk(depth=2)+re-rank(SBERT)+self-consistency=3.

**Policy Config (example)**

```yaml
# config/retrieval_policies.yaml
ttrpg_rules:
  fact_lookup:
    low:    { vector_top_k: 5,  filters: {system: "PF2E"}, types: ["spell","feat"], rerank: "mmr", expand: ["ruleset_aliases"] }
    medium: { vector_top_k: 8,  filters: {system: "PF2E"}, rerank: "sbert", graph_depth: 1 }
    high:   { vector_top_k: 12, filters: {system: "PF2E"}, rerank: "sbert", graph_depth: 2, self_consistency: 3 }
ttrpg_lore:
  summarize:
    low:    { vector_top_k: 8, rerank: "sbert" }
  multi_hop_reasoning:
    high:   { vector_top_k: 15, graph_depth: 2, rerank: "sbert", self_consistency: 3 }
unknown:
  multi_hop_reasoning:
    medium: { vector_top_k: 10, rerank: "mmr" }
```

**Code (policy loader)**

```python
# orchestrator/policy.py
import yaml, pathlib

class RetrievalPlan(dict): pass

def load_policies(path="config/retrieval_policies.yaml"):
    return yaml.safe_load(pathlib.Path(path).read_text())

def choose_plan(policies, classification):
    d = classification["domain"]; i = classification["intent"]; c = classification["complexity"]
    # Graceful fallback:
    return (policies.get(d, {}).get(i, {}).get(c) or
            policies.get("unknown", {}).get(i, {}).get(c) or
            {"vector_top_k": 8, "rerank": "mmr"})
```

**Tests (Unit/Functional/Regression/Security)**

* Unit: policy selection exact-match + fallback; YAML hot-reload; invalid YAML handled.
* Functional: For 6 canonical classifications, verify issued retrieval calls (mock vector/graph).
* Regression: Golden JSON outputs for plans (snapshot tests).
* Security: Reject policies that try to set `graph_depth>3` or `vector_top_k>50` (cost guard).

---

## Epic E2.2 — Model Routing & Prompting

### US-203: Model Router (MR)

**As** the Orchestrator
**I want** to select the appropriate **model family** and **context window** based on classification & plan
**So that** we balance accuracy, latency, and cost.

**Acceptance Criteria**

* Routing matrix supports at least: `gpt-5-large` (reasoning), `gpt-4o-mini` (fast), a local small model (mockable), and a code-specialist for `code_help`.
* Complexity `high` + `multi_hop_reasoning` ⇒ `gpt-5-large` with chain-of-thought **hidden**.
* Creative tasks ⇒ a style-biased system prompt and temperature bump.
* Fallback on quota/timeout with deterministic degrade path.

**Routing Matrix (example)**

```python
# orchestrator/router.py
def pick_model(classification: dict, plan: dict):
    intent, complexity = classification["intent"], classification["complexity"]
    if intent == "code_help":
        return {"model": "gpt-4o-mini", "max_tokens": 2000, "temperature": 0.2}
    if intent in {"multi_hop_reasoning"} and complexity in {"high","medium"}:
        return {"model": "gpt-5-large", "max_tokens": 8000, "temperature": 0.1}
    if intent in {"creative_write"}:
        return {"model": "gpt-5-large", "max_tokens": 6000, "temperature": 0.9}
    if intent in {"summarize"}:
        return {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.0}
    return {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.2}
```

**Unit Tests**

* Inputs across {intent×complexity} map to expected model choices.
* Fallback path triggers on “quota\_exceeded” (simulated).

**Security**

* Temperature/Top-p bounded; max\_tokens guarded to avoid runaway spend.

---

### US-204: Prompt Template Library (PTL)

**As** a Prompt Engineer
**I want** reusable, versioned system prompts per intent/domain
**So that** outputs are consistent, cite sources, and follow house style.

**Acceptance Criteria**

* Prompts live in `config/prompts/<intent>_<domain>.txt`, with placeholder tokens: `{TASK_BRIEF}`, `{CITATION_MODE}`, `{STYLE}`, `{POLICY_SNIPPET}`.
* Lint check ensures no leaking dev secrets; placeholders must be filled or removed.
* **Citations required** for fact/rules answers (IDs+page/section when available).

**Example Prompt**

```
# config/prompts/fact_lookup_ttrpg_rules.txt
You are the TTRPG Center Rules Assistant.
Goal: Provide a precise answer with PF2E citations (book, section/page). 
Constraints: 
- Only use retrieved passages. If insufficient, say so and ask for permission to broaden.
Style: {STYLE}
Output: 
1) Short direct answer (<=120 words).
2) Bullet citations [Book §Section p.Page].
3) If ambiguity exists, list clarifying questions.
Policy: {POLICY_SNIPPET}
```

**Unit/Functional Tests**

* Template loader fills placeholders; missing token → explicit error.
* Golden snapshot: same inputs → same rendered prompt (deterministic).

**Security Tests**

* Prompt-injection strings placed into `{TASK_BRIEF}` must be neutralized by policy footer.

---

## Epic E2.3 — Retrieval Execution & Re-Ranking

### US-205: Hybrid Retriever (HR)

**As** the Orchestrator
**I want** a single `retrieve(plan, query)` function that coordinates vector search, metadata filters, optional graph walk, MMR/SBERT re-rank + dedup
**So that** downstream LLMs get clean, ordered context.

**Acceptance Criteria**

* Returns `List[DocChunk]` with fields: `id, text, source, score, metadata`.
* De-duplicates highly similar chunks (cosine > 0.95).
* Total tokens of concatenated context obey `model.max_context * 0.6`.

**Code (retriever facade, stubs OK)**

```python
# orchestrator/retrieve.py
from typing import List, Dict
class DocChunk(dict): pass

def retrieve(query: str, plan: Dict) -> List[DocChunk]:
    # 1) Expand
    expanded = expand_query(query, plan.get("expand", []))
    # 2) Vector search (stub to AstraDB/Chroma)
    vec = vector_search(expanded, top_k=plan.get("vector_top_k", 8), filters=plan.get("filters"))
    # 3) Optional graph walk
    if plan.get("graph_depth"):
        vec += graph_expand(vec, depth=plan["graph_depth"])
    # 4) Re-rank
    ranked = rerank(vec, method=plan.get("rerank","mmr"))
    # 5) Dedup + budget
    return budget(dedup(ranked))
```

**Tests**

* Unit: dedup logic, token budgeting, filter merging.
* Functional: given canned store, a `spell DC` query returns spell chunks first.
* Regression: snapshot ranked IDs for canonical queries.
* Security: no PII leakage if a chunk contains secrets (redaction filter hook).

---

## Epic E2.4 — Answering, Self-Checking, and Observability

### US-206: Answer Composer with Self-Consistency (AC)

**As** the Orchestrator
**I want** to compose an answer using retrieved context, run n-samples for high-complexity tasks, and pick the best via scoring
**So that** reasoning answers improve reliability.

**Acceptance Criteria**

* `self_consistency` parameter triggers n parallel generations with an entailment/overlap scorer; best wins.
* Answers include a **Sources** section with chunk IDs and human-friendly citations.

**Code (composer)**

```python
# orchestrator/answer.py
def compose_answer(model_cfg, prompt, context_chunks, self_consistency: int = 1):
    ctx = "\n\n".join(f"[{c['id']}] {c['text']}" for c in context_chunks)
    def one():
        return call_llm(model_cfg, prompt, ctx)  # stubbed
    samples = [one() for _ in range(self_consistency)]
    return pick_best(samples)  # heuristic overlap/entailment
```

**Tests**

* Unit: `pick_best` chooses the most internally consistent sample.
* Functional: with noisy contexts, self-consistency improves factual score on benchmark set.

---

### US-207: Telemetry & Tracing (OBS)

**As** an Operator
**I want** structured logs and OpenTelemetry spans for classification → policy → retrieval → routing → answer
**So that** we can debug and tune.

**Acceptance Criteria**

* Each request has a correlation id; each component logs inputs/outputs (sizes, durations, top-k).
* Redaction of user PII & secrets enforced in logs.

**Tests**

* Functional: Trace includes all spans; durations sum ≈ wall time.
* Security: Redaction verified with strings like `sk-…`, `AZURE_…`.

---

### US-208: Fallbacks & Guardrails

**As** the Orchestrator
**I want** graceful degradation on timeouts/quota and injection/unsafe content checks
**So that** UX stays robust and safe.

**Acceptance Criteria**

* If model call fails: degrade model or reduce `self_consistency`; if retrieval empty: ask to broaden scope.
* Prompt-injection patterns flagged; response switches to safe refusal template.
* Rate limiting per IP/user.

**Tests**

* Unit: simulated errors trigger fallback path.
* Security: injection tries (“Ignore instructions...”) → safe refusal text and incident counter.

---

## Epic E2.5 — API Surface & Dev Harness

### US-209: `/ask` Endpoint (FastAPI)

**As** a Client (Web UI/Discord)
**I want** a single endpoint that performs classify → plan → retrieve → route → prompt → answer
**So that** Phase-2 services are consumable.

**Acceptance Criteria**

* POST `/ask` accepts `{query, user_id?, session_id?}`; returns `{answer, sources, trace_id}`.
* Streams partial tokens when available (optional).

**Code (minimal FastAPI app)**

```python
# app.py
from fastapi import FastAPI
from orchestrator.classifier import classify_query
from orchestrator.policy import load_policies, choose_plan
from orchestrator.router import pick_model
from orchestrator.retrieve import retrieve
from orchestrator.answer import compose_answer
from orchestrator.prompts import render_prompt  # simple loader

app = FastAPI()
POLICIES = load_policies()

@app.post("/ask")
def ask(payload: dict):
    q = payload["query"]
    cls = classify_query(q)
    plan = choose_plan(POLICIES, cls)
    model = pick_model(cls, plan)
    chunks = retrieve(q, plan)
    prompt = render_prompt(cls, task_brief=q, style="concise", policy_snippet="Follow house rules.")
    ans = compose_answer(model, prompt, chunks, self_consistency=plan.get("self_consistency",1))
    return {"answer": ans["text"], "sources": ans.get("sources",[]), "trace_id": ans.get("trace_id")}
```

**Unit/Functional Tests**

* 200 OK with minimal body; empty retrieval triggers clarification message; citations included for rules queries.

---

## Test Plan (Phase-2)

Below is how tests should be organized and run in CI (pytest + coverage). **All acceptance is code-verified**—no story is “Done” without passing tests.

### 1) Unit Tests (examples)

* `tests/unit/test_classifier.py`

  * `test_intent_rules()`, `test_fallback_to_llm_when_low_confidence()`
* `tests/unit/test_policy.py`

  * `test_choose_exact_and_fallback()`, `test_cost_guards()`
* `tests/unit/test_router.py`

  * `test_model_matrix()`, `test_quota_fallback()`
* `tests/unit/test_retrieve.py`

  * `test_dedup_and_budget()`, `test_filters_applied()`
* `tests/unit/test_answer.py`

  * `test_self_consistency_pick_best()`, `test_citation_block_format()`
* `tests/unit/test_prompts.py`

  * `test_render_prompt_placeholders()`, `test_prompt_injection_footer()`

### 2) Functional Tests (end-to-end, mocked externals)

* `tests/functional/test_ask_endpoint.py`

  * **Scenario A (rules lookup, low):** “What is the action cost for Cast a Spell (PF2E)?”

    * Expect: `intent=fact_lookup`, domain=`ttrpg_rules`, model=`gpt-4o-mini`, citations include Core Rulebook section.
  * **Scenario B (multi-hop, high):** “Compare the Triskele Brute’s reach vs a Large Ogre’s and advise optimal positioning.”

    * Expect: `multi_hop_reasoning.high` → plan with graph depth 2, `gpt-5-large`, 3 self-consistency samples.
  * **Scenario C (summarize lore):** “Summarize Lysengard’s political structure in 5 bullets.”

    * Expect: summarize route, re-rank sbert, concise output.

### 3) Regression Tests

* `tests/regression/fixtures/*` — 20 canonical queries

  * Golden JSON covering: classification, plan, chosen model, top-3 chunk IDs, answer hash (stable seed).
* CI fails if macro-F1 or golden diffs exceed thresholds.

### 4) Security Tests

* Prompt-injection suite (15 patterns) → ensure refusal or safe handling.
* Oversized inputs (1MB text) → streaming/truncation, no crash.
* Redaction: secrets in docs never appear in output; check log files.

---

## Code Snippets — Utilities You’ll Likely Reuse

**Prompt renderer**

```python
# orchestrator/prompts.py
import pathlib

def render_prompt(classification, task_brief: str, style: str, policy_snippet: str) -> str:
    name = f"{classification['intent']}_{classification['domain']}.txt"
    path = pathlib.Path("config/prompts")/name
    tmpl = path.read_text()
    return (tmpl
            .replace("{TASK_BRIEF}", task_brief)
            .replace("{STYLE}", style)
            .replace("{POLICY_SNIPPET}", policy_snippet)
            .replace("{CITATION_MODE}", "strict"))
```

**MMR re-rank (simple)**

```python
# orchestrator/rerank.py
import numpy as np

def mmr(cand, query_vec, k=5, lambda_=0.7):
    selected, rest = [], cand[:]
    while rest and len(selected) < k:
        best, best_score = None, -1e9
        for d in rest:
            rel = float(np.dot(d["vec"], query_vec))
            div = max([np.dot(d["vec"], s["vec"]) for s in selected], default=0.0)
            score = lambda_*rel - (1-lambda_)*div
            if score > best_score:
                best, best_score = d, score
        selected.append(best); rest.remove(best)
    return selected
```

**Mockable LLM call**

```python
# orchestrator/llm.py
def call_llm(model_cfg, prompt, context):
    # glue to OpenAI/Bedrock/etc. Here: return deterministic stub for tests
    return {"text": f"{prompt}\n\nCONTEXT:\n{context}\n\n[stubbed answer]", "sources": [], "trace_id": "trace-123"}
```

---

## Definition of Done (Phase-2)

* All US-201 … US-209 pass **Unit/Functional/Regression/Security** test suites.
* **Policy & Prompt repositories** versioned and documented (README in each folder).
* **Latency p95** targets on local/dev: classify ≤150ms (heuristic), retrieve ≤400ms for TopK≤10.
* **Observability**: End-to-end traces visible with correlation IDs; PII redaction verified.
* **Safety**: Injection suite green; refusal templates hooked.

---

## How this plugs into your existing stack

* **Langflow/AstraDB**: keep using your vector store; `vector_search` is a drop-in adapter. If you maintain graphs in Astra or a side store, wire `graph_expand`.
* **Discord/Front-end**: keep POSTing `/ask`; the trace id helps attach logs to UI status (“Classifying… Retrieving… Composing…”).
* **Phase-1 Passes (A/B/C)**: Phase-2 sits *after* ingestion quality gates. If documents aren’t in the store or fail validation, RPE will short-circuit with a “broaden scope or re-ingest” message.

---

## Quick Start Checklist

1. Create folders:

   ```
   orchestrator/{classifier,policy,router,retrieve,answer,rerank,prompts,llm}.py
   config/{retrieval_policies.yaml,prompts/*.txt}
   tests/{unit,functional,regression,security}/
   ```
2. Paste code snippets and tests; stub external calls.
3. Add CI: `pytest -q --maxfail=1 --disable-warnings --cov=orchestrator`.
4. Seed 200 labeled queries for classifier metrics and regression snapshots.
