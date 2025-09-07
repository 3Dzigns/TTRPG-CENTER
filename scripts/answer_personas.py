"""
Answer Persona Questions using Phase 2/4 retrieval:
- Prefer AstraDB chunks when configured
- Fall back to local artifacts (dev/test ingest JSON)
- If still insufficient, note why and recommend ingestion/graph steps

Output: artifacts/reports/persona_answers_dev.md
"""

from __future__ import annotations

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env_from_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for line in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and v:
            os.environ.setdefault(k, v)


def iter_persona_files(personas_dir: Path) -> List[Path]:
    files = []
    for p in personas_dir.glob("*.md"):
        files.append(p)
    return sorted(files)


def extract_english_qas(text: str) -> List[Tuple[str, str]]:
    qas: List[Tuple[str, str]] = []
    lines = text.splitlines()
    current_q: str | None = None
    for ln in lines:
        if ln.strip().startswith("- **English Q:**"):
            current_q = ln.split("**English Q:**", 1)[1].strip().lstrip(":").strip()
        elif ln.strip().startswith("- **English A:**") and current_q is not None:
            ans = ln.split("**English A:**", 1)[1].strip().lstrip(":").strip()
            qas.append((current_q, ans))
            current_q = None
    return qas


def _tokenize(s: str) -> List[str]:
    return re.findall(r"\w+", (s or "").lower())


def synthesize_answer(question: str, chunk_texts: List[str]) -> str:
    if not chunk_texts:
        return ""
    # Build keyword set from question (drop obvious stopwords)
    stop = {"how", "what", "the", "a", "an", "do", "does", "in", "pf1e", "pf1", "work", "works", "to", "for", "of", "is"}
    kws = [w for w in _tokenize(question) if w not in stop and len(w) > 2]
    # Search sentences containing 2+ keywords
    for text in chunk_texts:
        # Normalize whitespace
        txt = re.sub(r"\s+", " ", text).strip()
        # Split into pseudo-sentences
        sents = re.split(r"(?<=[.!?])\s+", txt)
        scored = []
        for s in sents:
            score = sum(1 for k in kws if k in s.lower())
            scored.append((score, s))
        scored.sort(key=lambda t: t[0], reverse=True)
        best = [s for sc, s in scored if sc >= 2][:2]
        if best:
            ans = " ".join(best)
            # Trim long answers
            return ans[:600]
    # Fallback: return first 2 sentences of the top chunk
    txt = re.sub(r"\s+", " ", chunk_texts[0]).strip()
    sents = re.split(r"(?<=[.!?])\s+", txt)
    return " ".join(sents[:2])[:600]


def main() -> None:
    # Ensure env loaded for Astra
    load_env_from_dotenv(REPO_ROOT / ".env")
    os.environ.setdefault("APP_ENV", "dev")
    env = os.getenv("APP_ENV", "dev")

    # Import project root for local imports
    import sys
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

try:
    from astrapy import DataAPIClient  # type: ignore
except Exception:
    DataAPIClient = None  # type: ignore

@dataclass
class DocChunk:
    id: str
    text: str
    source: str
    score: float
    metadata: Dict[str, Any]

def _simple_score(query: str, text: str) -> float:
    q = set(_tokenize(query))
    t = set(_tokenize(text))
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))

def _keyword_boost_score(query: str, text: str, metadata: Dict[str, Any]) -> float:
    base = _simple_score(query, text)
    ql = (query or "").lower()
    tx = (text or "").lower()
    boost = 0.0
    if "spells per day" in ql and "spells per day" in tx:
        boost += 2.0
    if "dodge" in ql and "dodge" in tx:
        boost += 1.5
    if "paladin" in ql and "paladin" in tx:
        boost += 1.0
    mtype = (metadata or {}).get("chunk_type") or (metadata or {}).get("type")
    if mtype and str(mtype).lower() in {"table", "list", "table_row"}:
        boost += 0.5
    return base + boost

def _retrieve_from_astra(query: str, env: str, top_k: int = 5) -> List[DocChunk]:
    if DataAPIClient is None:
        return []
    endpoint = os.getenv("ASTRA_DB_API_ENDPOINT", "")
    token = os.getenv("ASTRA_DB_APPLICATION_TOKEN", "")
    if not (endpoint and token):
        return []
    try:
        client = DataAPIClient(token)  # nosec
        db = client.get_database_by_api_endpoint(endpoint)
        collection_name = f"ttrpg_chunks_{env}"
        col = db.get_collection(collection_name)
        projection = {"content": 1, "metadata": 1, "chunk_id": 1}
        cursor = col.find({}, projection=projection, limit=2000)
        candidates: List[DocChunk] = []
        for d in cursor:
            text = (d.get("content") or "")
            cid = d.get("chunk_id") or str(d.get("_id"))
            meta = d.get("metadata") or {}
            score = _keyword_boost_score(query, text, meta)
            if score > 0:
                src = f"astra:{collection_name}:{cid}"
                candidates.append(DocChunk(id=str(cid), text=text, source=src, score=score, metadata=meta))
        if not candidates:
            return []
        candidates.sort(key=lambda c: c.score, reverse=True)
        seen = set()
        results: List[DocChunk] = []
        for c in candidates:
            sig = " ".join(_tokenize(c.text))[:200]
            if sig in seen:
                continue
            seen.add(sig)
            results.append(c)
            if len(results) >= max(1, top_k):
                break
        return results
    except Exception:
        return []

def _iter_candidate_chunks_local(env: str) -> List[DocChunk]:
    roots = [REPO_ROOT / f"artifacts/ingest/{env}", REPO_ROOT / f"artifacts/{env}"]
    out: List[DocChunk] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict) and "chunks" in data and isinstance(data["chunks"], list):
                for ch in data["chunks"]:
                    text = ch.get("content") or ch.get("text") or ""
                    cid = ch.get("id") or ch.get("chunk_id") or str(path)
                    meta = ch.get("metadata") or {}
                    out.append(DocChunk(id=str(cid), text=text, source=str(path), score=0.0, metadata=meta))
            elif isinstance(data, dict) and "enriched_chunks" in data:
                for ch in data["enriched_chunks"]:
                    text = ch.get("enhanced_content") or ch.get("original_content") or ""
                    cid = ch.get("chunk_id") or str(path)
                    meta = {
                        "entities": ch.get("entities", []),
                        "categories": ch.get("categories", []),
                        "complexity": ch.get("complexity", "unknown"),
                        **({"page": ch.get("page_number")} if ch.get("page_number") else {}),
                    }
                    out.append(DocChunk(id=str(cid), text=text, source=str(path), score=0.0, metadata=meta))
    return out

def retrieve(query: str, env: str, limit: int = 3, top_k: int = 5) -> List[DocChunk]:
    # Prefer Astra
    astra = _retrieve_from_astra(query, env, top_k)
    if astra:
        return astra[:limit]
    # Fallback local
    cands = _iter_candidate_chunks_local(env)
    for i, ch in enumerate(cands):
        cands[i].score = _simple_score(query, ch.text)
    cands.sort(key=lambda c: c.score, reverse=True)
    seen = set()
    out: List[DocChunk] = []
    for ch in cands:
        if len(out) >= max(1, limit):
            break
        sig = " ".join(_tokenize(ch.text))[:200]
        if sig in seen:
            continue
        seen.add(sig)
        out.append(ch)
    return out

    
    # Orchestrate persona processing
    personas_dir = REPO_ROOT / "Personas"
    out_dir = REPO_ROOT / "artifacts" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"persona_answers_{env}.md"

    # Debug log
    try:
        with (out_dir / "run.log").open("w", encoding="utf-8") as dbg:
            dbg.write(f"start env={env}\n")
    except Exception:
        pass

    files = iter_persona_files(personas_dir)
    results: List[Dict[str, Any]] = []

    for fp in files:
        text = fp.read_text(encoding="utf-8", errors="ignore")
        qas = extract_english_qas(text)
        for q, expected in qas:
            # Retrieve context
            try:
                chunks = retrieve(q, env, limit=3, top_k=8)
            except Exception as e:
                chunks = []
                retrieve_error = str(e)
            else:
                retrieve_error = None

            answer = ""
            citations: List[Dict[str, Any]] = []
            source_mode = "astra" if chunks and str(chunks[0].source).startswith("astra:") else "local"
            if chunks:
                answer = synthesize_answer(q, [c.text for c in chunks if c and c.text])
                for c in chunks:
                    meta = c.metadata or {}
                    page = meta.get("page") or meta.get("page_number")
                    citations.append({
                        "source": c.source,
                        "page": page,
                        "score": c.score,
                    })

            issue = None
            recommendation = None
            if not chunks or not answer:
                issue = "Insufficient retrieved context to answer precisely"
                # Heuristic recommendations
                ql = q.lower()
                if "magebred" in ql or "eberron" in ql:
                    recommendation = (
                        "Ingest Eberron Campaign Setting (Magebred section) into AstraDB/pass A/B, "
                        "then re-run. Map 3.5e template to PF1e stat adjustments and animal companion rules."
                    )
                elif any(k in ql for k in ["domain", "cleric"]):
                    recommendation = (
                        "Ensure Cleric class pages (Domains, Channel Energy) from PF1e Core Rulebook are in the corpus; "
                        "verify pass_b_enriched includes the 'Domains' paragraph and table."
                    )
                else:
                    recommendation = (
                        "Add relevant sections from PF1e Core/Ultimate Magic to the corpus; "
                        "rerun ingest and verify retrieval scoring captures key terms."
                    )

            results.append({
                "file": str(fp.relative_to(REPO_ROOT)),
                "question": q,
                "expected": expected,
                "answer": answer,
                "citations": citations,
                "source_mode": source_mode if chunks else None,
                "retrieve_error": retrieve_error,
                "issue": issue,
                "recommendation": recommendation,
            })

    # Write Markdown report
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"# Persona Answers Report ({env})\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"## {i}. {r['question']}\n")
            f.write(f"- File: `{r['file']}`\n")
            f.write(f"- Expected: {r['expected']}\n")
            if r["answer"]:
                f.write(f"- Answer: {r['answer']}\n")
            if r["citations"]:
                f.write("- Citations:\n")
                for c in r["citations"]:
                    src = Path(c["source"]).name if c["source"] else ""
                    pg = f" p.{c['page']}" if c.get("page") else ""
                    f.write(f"  - {src}{pg}\n")
            if r.get("source_mode"):
                f.write(f"- Source: {r['source_mode']}\n")
            if r.get("issue"):
                f.write(f"- Issue: {r['issue']}\n")
            if r.get("recommendation"):
                f.write(f"- Recommendation: {r['recommendation']}\n")
            if r.get("retrieve_error"):
                f.write(f"- Retrieval Error: {r['retrieve_error']}\n")
            f.write("\n")

    # Also save JSON sidecar for tooling
    (out_dir / f"persona_answers_{env}.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    try:
        print(str(out_path))
    except Exception:
        pass


if __name__ == "__main__":
    main()
