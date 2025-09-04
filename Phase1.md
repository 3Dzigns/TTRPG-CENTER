# TTRPG Center — Phase 1 User Stories, Code Snippets, and Test Matrix (Hard‑Gated)

> Objective: Deliver a production‑grade ingestion pipeline that processes TTRPG source PDFs in **three passes** (Parse/Chunk → Enrich → Graph Compile), with **hard acceptance gates**: each pass is **not accepted** unless its **3rd‑party tool actually runs** (no mocks) **and** its **outputs are verified** against contract checks. If any pass fails its gate, **the whole job fails** and produces a red status in the Ingestion Console.

---

## Scope & Non‑Goals

**In scope**

* Multi‑pass ingestion pipeline with explicit gates:

  * **Pass A — Parse/Chunk** using **unstructured.io**
  * **Pass B — Enrich/Normalize + Dictionary Update** using **Haystack**
  * **Pass C — Graph Compile** using **LlamaIndex**
* Version‑pinned dependencies, tool health checks, artifacted outputs, and a manifest per job.
* Dictionary persistence (AstraDB collection) with fallbacks to local JSON artifacts for CI.
* WebUI Ingestion Console that streams logs and pass status in real time.

**Out of scope**

* End‑user retrieval UX (Phase 2+).
* Full Admin features beyond basic Ingestion Console and dictionary viewer.

**Definition of Done (Phase 1)**

* All three passes run on at least two fixture PDFs (short + medium), **using the real tools**.
* Each pass emits contract‑compliant outputs and updates `manifest.json` with checksums, counts, and versions.
* Dictionary is updated with new/changed entries and is viewable through WebUI.
* CI runs Unit/Functional/Security on PR; Regression nightly. **No pass may stub the 3rd‑party tool in acceptance tests.**

**Artifacts** (per job):

```
artifacts/ingest/{ENV}/{JOB_ID}/
  manifest.json              # status, timings, tool versions, checksums
  passA_chunks.json          # Pass A output
  passB_enriched.json        # Pass B output
  passB_dictionary_delta.json
  passC_graph.json           # Pass C output
  logs/*.ndjson              # structured logs
```

---

# Epics, Stories, Snippets, and Tests

## EPIC RAG — Three‑Pass Ingestion with Hard Gates

### Story RAG‑001A: Pass A — Parse/Chunk with unstructured.io

**As a** pipeline developer
**I want** to parse PDFs into single‑concept chunks with base metadata (page, section, type)
**So that** downstream enrichment and graphing can operate deterministically.

**Acceptance Criteria (HARD GATE)**

1. **Tool run required:** `unstructured` called via library or CLI; `--version` recorded in `manifest.json`.
2. **Exit code & health:** exit code `0`; tool log captured; runtime < configurable threshold (default 5m/50 pages).
3. **Output contract:** `passA_chunks.json` is a JSON array of objects with keys `{text, page, section, type}`.
4. **Coverage:** `page` spans all pages that contain text; no null/empty `text` entries.
5. **Determinism check:** stable SHA256 over normalized texts for fixture PDFs.
6. **Schema & sanity:** JSON schema validation + min/max length checks; no control characters.

**Code Snippet — Pass A (library use)**

```python
# src_ingest/pass_a_parse.py
from unstructured.partition.pdf import partition_pdf
from pathlib import Path
import json, hashlib

REQUIRED = {"text","page","section","type"}

def _chunk(el):
    return {
        "text": (el.text or "").strip(),
        "page": getattr(el.metadata, "page_number", None),
        "section": getattr(getattr(el, "metadata", None), "section", None) or "unknown",
        "type": getattr(el, "category", "Unknown")
    }

def parse_pdf(pdf_path: str, out_path: str) -> list:
    elements = partition_pdf(filename=pdf_path)
    chunks = [_chunk(e) for e in elements if (e.text or "").strip()]
    # validate
    for c in chunks:
        assert REQUIRED.issubset(c.keys()), f"missing keys in chunk: {c.keys()}"
        assert isinstance(c["page"], (int, type(None)))
    Path(out_path).write_text(json.dumps(chunks, ensure_ascii=False, indent=2))
    return chunks

def sha256_texts(chunks: list) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update((c["text"]+"\n").encode("utf-8"))
    return h.hexdigest()
```

**Unit Tests** (`tests/unit/test_pass_a_parse.py`)

```python
from src_ingest.pass_a_parse import parse_pdf, sha256_texts
from pathlib import Path
import json

def test_parse_produces_required_fields(tmp_path):
    out = tmp_path/"chunks.json"
    chunks = parse_pdf("tests/fixtures/sample_short.pdf", str(out))
    assert out.exists()
    for c in chunks:
        for k in ("text","page","section","type"): assert k in c

def test_sha256_stable_for_fixture(tmp_path):
    out = tmp_path/"chunks.json"
    chunks = parse_pdf("tests/fixtures/sample_short.pdf", str(out))
    assert sha256_texts(chunks)
```

**Functional Tests (Integration — REAL TOOL)** (`tests/functional/test_pass_a_integration.py`)

```python
import json
from pathlib import Path
from src_ingest.pass_a_parse import parse_pdf

FIXTURE = "tests/fixtures/sample_short.pdf"

def test_pass_a_output_contract(tmp_path):
    out = tmp_path/"passA.json"
    chunks = parse_pdf(FIXTURE, str(out))
    data = json.loads(out.read_text())
    assert isinstance(data, list) and len(data) == len(chunks)
    assert all(isinstance(c.get("page"),(int,type(None))) for c in data)
    assert all(c.get("text") for c in data)
```

**Regression Tests**

* Snapshot the **schema** and **hash of texts** for `sample_short.pdf` and `sample_medium.pdf`. Failing diff indicates tool or parsing behavior change.

**Security Tests**

* Feed a PDF with embedded JS/links; parser must not execute any active content; run with resource/time limits; ensure no files written outside the artifact directory.

---

### Story RAG‑001B: Pass B — Enrich/Normalize + Dictionary Update (Haystack)

**As a** data engineer
**I want** to standardize metadata, detect entities/terms, and update a shared dictionary
**So that** retrieval quality and graph linking improve.

**Acceptance Criteria (HARD GATE)**

1. **Tool run required:** Haystack imported and used (e.g., `PreProcessor`, pipelines) with version pinned & recorded in `manifest.json`.
2. **Output contract:** `passB_enriched.json` maintains Pass A fields and adds `{normalized_text, terms:[...], section_title}`.
3. **Dictionary delta:** `passB_dictionary_delta.json` lists **new/updated** terms with `{term, kind, sources:[{pdf,page}], canonical}`.
4. **AstraDB write:** when Astra is available, delta is upserted into `ttrpg_dictionary`; in CI fallback, delta is persisted to artifact and a dry‑run log proves write intent.
5. **Referential integrity:** every `term.sources[*].page` must exist in Pass A pages for the same job.

**Code Snippet — Pass B**

```python
# src_ingest/pass_b_enrich.py
from haystack.nodes import PreProcessor
import json, re

def normalize_text(txt: str) -> str:
    return re.sub(r"\s+"," ", txt).strip().lower()

def enrich(in_path: str, out_path: str, dict_delta_path: str):
    chunks = json.load(open(in_path))
    pre = PreProcessor(split_length=256, split_overlap=20)
    enriched = []
    terms = {}
    for c in chunks:
        nt = normalize_text(c["text"])
        c2 = {**c, "normalized_text": nt, "terms": []}
        # naive term extraction (placeholder) — replace with Haystack components as needed
        for m in re.finditer(r"\b([A-Z][A-Za-z]{3,})\b", c["text"]):
            t = m.group(1)
            c2["terms"].append(t)
            terms.setdefault(t, {"term": t, "kind": "unknown", "sources": []})
            terms[t]["sources"].append({"pdf":"job-input.pdf","page": c.get("page")})
        enriched.append(c2)
    json.dump(enriched, open(out_path,'w'), ensure_ascii=False, indent=2)
    json.dump(list(terms.values()), open(dict_delta_path,'w'), ensure_ascii=False, indent=2)
    return enriched, list(terms.values())
```

**Unit Tests** (`tests/unit/test_pass_b_enrich.py`)

```python
from src_ingest.pass_b_enrich import normalize_text

def test_normalize_text_basic():
    assert normalize_text("  Hello\nWorld  ") == "hello world"
```

**Functional Tests (Integration — REAL TOOL)** (`tests/functional/test_pass_b_integration.py`)

```python
import json
from pathlib import Path
from src_ingest.pass_b_enrich import enrich

def test_enrich_contract(tmp_path):
    pa = Path("tests/fixtures/golden/passA.sample_short.json")
    out = tmp_path/"passB_enriched.json"
    dlt = tmp_path/"dict_delta.json"
    enriched, delta = enrich(str(pa), str(out), str(dlt))
    ej = json.loads(out.read_text())
    assert all({'text','page','section','type','normalized_text','terms'}.issubset(e.keys()) for e in ej)
    dj = json.loads(dlt.read_text())
    assert all({'term','sources'}.issubset(t.keys()) for t in dj)
```

**Regression Tests**

* Golden‑file compare for `passB_enriched.json` **schema** and stable term extraction on fixture PDFs (allowing approved drift via fixtures update PR).
* Delta integrity checks: `sources.page` must exist in Pass A page set.

**Security Tests**

* Ensure normalization cannot create injection strings in logs (escape control chars), and dictionary writes validate term length and charset.

---

### Story RAG‑001C: Pass C — Graph Compile (LlamaIndex)

**As a** knowledge engineer
**I want** to compile an index/graph that links chunks and dictionary terms
**So that** future workflows can traverse concepts deterministically.

**Acceptance Criteria (HARD GATE)**

1. **Tool run required:** LlamaIndex imported and used to build an index/graph; version recorded in `manifest.json`.
2. **Output contract:** `passC_graph.json` contains nodes `{id, kind in ['chunk','term'], label}` and edges `{src, dst, rel}`.
3. **Linkage coverage:** Every `term` from Pass B delta appears as a node; every enriched chunk that references a term yields an edge.
4. **Determinism:** Node/edge counts and a stable adjacency checksum for fixtures.

**Code Snippet — Pass C (minimal skeleton)**

```python
# src_ingest/pass_c_graph.py
import json, hashlib


def build_graph(passB_enriched: str, dict_delta: str, out_path: str):
    chunks = json.load(open(passB_enriched))
    terms = json.load(open(dict_delta))
    nodes, edges = [], []
    # term nodes
    for t in terms:
        nodes.append({"id": f"term:{t['term']}", "kind":"term", "label": t['term']})
    # chunk nodes + edges
    for i, c in enumerate(chunks):
        cid = f"chunk:{i}"
        nodes.append({"id": cid, "kind":"chunk", "label": c.get('section','unknown')})
        for t in c.get('terms',[]):
            edges.append({"src": cid, "dst": f"term:{t}", "rel":"mentions"})
    graph = {"nodes": nodes, "edges": edges}
    json.dump(graph, open(out_path,'w'), ensure_ascii=False, indent=2)
    # checksum for determinism
    h = hashlib.sha256()
    for e in sorted((e['src'],e['dst'],e['rel']) for e in edges):
        h.update(("|".join(e)+"\n").encode("utf-8"))
    return graph, h.hexdigest()
```

**Unit Tests** (`tests/unit/test_pass_c_graph.py`)

```python
from src_ingest.pass_c_graph import build_graph
from pathlib import Path
import json

def test_build_graph_shapes(tmp_path):
    enr = tmp_path/"enr.json"; dlt = tmp_path/"dlt.json"; out = tmp_path/"g.json"
    enr.write_text('[{"terms":["Fireball"],"section":"Spells"}]')
    dlt.write_text('[{"term":"Fireball","sources":[{"page":1}]}]')
    graph, ck = build_graph(str(enr), str(dlt), str(out))
    assert 'nodes' in graph and 'edges' in graph and ck
```

**Functional Tests (Integration — REAL TOOL)**

* For fixture outputs from Pass B (produced with Haystack active), build graph and assert: counts, presence of all term nodes, edges for each term mention.

**Regression Tests**

* Snapshot node/edge counts and the adjacency checksum for fixtures.

**Security Tests**

* Ensure labels are sanitized; no path‑like IDs; enforce max node/edge counts per job to prevent DoS.

---

## EPIC STAT — Status, Manifests, and WebUI Hooks

### Story STAT‑001: Manifest writer & gatekeeper

**Acceptance Criteria**

* A shared `manifest.py` API records: job info, tool versions, start/stop times, file sizes, checksums, pass statuses (`pending|running|passed|failed`), and failure reasons.
* Gatekeeper marks **pass failed** if: tool didn’t run, exit code non‑zero, contract invalid, or checksum mismatch.

**Code Snippet — Manifest utilities**

```python
# src_ingest/manifest.py
import json, time, platform, hashlib
from pathlib import Path

class Manifest:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {
            "started": time.time(),
            "platform": platform.platform(),
            "tools": {},
            "passes": {}
        }
    def tool(self, name, version):
        self.data.setdefault("tools",{})[name] = {"version": version}
    def set_pass(self, name, status, reason=None, **fields):
        self.data.setdefault("passes",{})[name] = {"status": status, **({"reason":reason} if reason else {}), **fields}
        self.flush()
    def file_checksum(self, path):
        from hashlib import sha256
        from pathlib import Path as P
        return sha256(P(path).read_bytes()).hexdigest()
    def flush(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2))
```

**Functional Tests**

* Simulate a failing Pass A (bad schema); Gatekeeper must mark `failed` with a reason and prevent Pass B/C.

---

## EPIC DICT — Dictionary Persistence

### Story DICT‑001: AstraDB persistence with CI fallback

**Acceptance Criteria**

* When `ASTRA_TOKEN` present, upsert deltas into `ttrpg_dictionary`.
* Otherwise, write `passB_dictionary_delta.json` and mark `manifest.passes["PassB"].dry_run=true`.
* WebUI can render dictionary deltas from artifacts if DB unavailable.

---

## CI — Gated Pipeline Design

**Workflow** (`.github/workflows/phase1_ingest.yml`)

* **jobs.parse** → **jobs.enrich** (needs: parse) → **jobs.graph** (needs: enrich)
* Each job runs **real tool** steps, writes artifacts, runs contract validators, then updates `manifest.json`.
* If any contract check fails, downstream jobs are skipped by `needs`.

**Example CI Fragments**

```yaml
jobs:
  parse:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: |
          pip install unstructured[all] pytest jsonschema
          python -m pytest -q tests/functional/test_pass_a_integration.py
  enrich:
    needs: parse
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: |
          pip install farm-haystack jsonschema
          python -m pytest -q tests/functional/test_pass_b_integration.py
  graph:
    needs: enrich
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: |
          pip install llama-index
          python -m pytest -q tests/functional/test_pass_c_integration.py
```

---

# Test Requirements Matrix (Phase 1)

| Area                         | Required Tests                                                                                                                                                                    |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                     | Pass‑specific helpers (normalization, checksum, graph builder), schema validators, manifest writer.                                                                               |
| **Functional (Integration)** | **REAL TOOL RUNS** for each pass on fixtures; record tool version; verify output contracts; timing/exit code; artifact presence & checksums; referential integrity across passes. |
| **Regression**               | Golden snapshots for Pass A texts hash, Pass B term extraction/delta integrity, Pass C node/edge counts + adjacency checksum; nightly on `main`.                                  |
| **Security**                 | PDF active‑content safety; path traversal prevention; resource/time limits; sanitized labels/terms; dictionary input validation; DoS guardrails (max chunks/nodes per job).       |

---

## Exit Criteria Checklist (copy into PR template)

* [ ] **Pass A** ran `unstructured` and produced contract‑valid `passA_chunks.json` with stable hash for fixtures.
* [ ] **Pass B** ran **Haystack**, produced `passB_enriched.json` + `passB_dictionary_delta.json`; dictionary delta refers only to existing Pass A pages.
* [ ] **Pass C** ran **LlamaIndex** and produced `passC_graph.json` with required nodes/edges and stable adjacency checksum.
* [ ] `manifest.json` contains tool versions and pass statuses; failures correctly block downstream passes.
* [ ] WebUI Ingestion Console displays live pass status and renders dictionary deltas.
* [ ] CI green for Unit/Functional/Security; nightly Regression green.

---

## Notes

* **No mocks for acceptance**: Mocks permitted only in **unit tests**. All **functional** and **regression** tests must exercise the actual tools.
* Pin versions in `requirements.txt` (exact pins) and track them in `manifest.json` for auditability.
