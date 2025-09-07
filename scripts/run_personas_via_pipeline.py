"""
Run persona questions through the existing Phase-2 RAG pipeline.
This exercises: classifier → policies/plan → model routing → retriever → synthesis (stub).

Output: artifacts/reports/persona_answers_pipeline_{env}.md (and .json)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path
import argparse
from typing import List, Tuple, Dict, Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env():
    dot = REPO_ROOT / ".env"
    if dot.exists():
        for line in dot.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    os.environ.setdefault("APP_ENV", "dev")


def _clean_quotes(s: str) -> str:
    # Remove odd leading artifacts and smart quotes
    s = s.strip()
    s = s.replace("\uFFFD", "").replace("\u201C", '"').replace("\u201D", '"')
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")
    s = s.replace("�?o", "").replace("�??", "")
    return s.strip().strip('"').strip()


def extract_english_qas(text: str) -> List[Tuple[str, str]]:
    """Extract question/expected pairs from multiple supported formats.

    Supported:
    - Legacy: '- **English Q:** ...' followed by '- **English A:** ...'
    - Eberron personas: numbered italic question lines with a following '* **Expected Outcome:** ...'
    - Bilingual blocks: '**EN:** *...*' with a following Expected Outcome line
    """
    qas: List[Tuple[str, str]] = []
    lines = text.splitlines()

    # Pass 1: legacy format
    cur_q: str | None = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("- **English Q:**"):
            cur_q = s.split("**English Q:**", 1)[1].strip().lstrip(":").strip()
        elif s.startswith("- **English A:**") and cur_q is not None:
            a = s.split("**English A:**", 1)[1].strip().lstrip(":").strip()
            qas.append((_clean_quotes(cur_q), _clean_quotes(a)))
            cur_q = None
    if qas:
        return qas

    # Pass 2: bilingual EN lines + Expected Outcome
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if "**EN:**" in s:
            m = re.search(r"\*\*EN:\*\*\s*\*(.+?)\*", s)
            if m:
                q = _clean_quotes(m.group(1))
            else:
                # Fallback: take text after label
                q = _clean_quotes(s.split("**EN:**", 1)[1])
            # look ahead for Expected Outcome
            expected = ""
            for j in range(1, 6):
                if i + j >= len(lines):
                    break
                sj = lines[i + j].strip()
                if sj.startswith("* **Expected Outcome:**") or sj.startswith("- **Expected Outcome:**"):
                    expected = _clean_quotes(sj.split("**Expected Outcome:**", 1)[1])
                    break
            if q:
                qas.append((q, expected))
                i += max(1, j)
                continue
        i += 1
    if qas:
        return qas

    # Pass 3: numbered italic question + Expected Outcome following
    for idx, ln in enumerate(lines):
        s = ln.strip()
        m = re.match(r"^\d+\.[\s\t]*\*(.+?)\*\s*$", s)
        if m:
            q = _clean_quotes(m.group(1))
            expected = ""
            for j in range(1, 6):
                if idx + j >= len(lines):
                    break
                sj = lines[idx + j].strip()
                if sj.startswith("* **Expected Outcome:**") or sj.startswith("- **Expected Outcome:**"):
                    expected = _clean_quotes(sj.split("**Expected Outcome:**", 1)[1])
                    break
            qas.append((q, expected))

    return qas


async def ask_pipeline(question: str) -> Dict[str, Any]:
    # Ensure stdlib logging stays bound to 'logging' to avoid name shadowing
    import logging as _stdlib_logging  # noqa: F401
    import logging.config as _stdlib_logging_config  # noqa: F401
    sys.modules['logging'] = _stdlib_logging  # type: ignore

    # Import rag_ask lazily to avoid early import of src_common.logging wrapper
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from src_common.orchestrator.service import rag_ask  # type: ignore

    payload = {"query": question, "top_k": 3}
    res = await rag_ask(payload)
    # FastAPI JSONResponse returns a Response; ensure dict
    if hasattr(res, "body"):
        try:
            return json.loads(res.body.decode("utf-8"))
        except Exception:
            pass
    return res  # already dict


def main(argv: list[str] | None = None) -> None:
    load_env()
    env = os.getenv("APP_ENV", "dev")
    personas_dir = REPO_ROOT / "Personas"
    out_dir = REPO_ROOT / "artifacts" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ap = argparse.ArgumentParser(description="Run persona questions via pipeline")
    ap.add_argument("--files", nargs="*", default=[], help="Specific persona markdown files to process")
    ap.add_argument("--glob", default=None, help="Glob pattern under Personas/ to filter files (e.g., 'Eberron*.md')")
    args = ap.parse_args(argv or [])

    suffix = "filtered" if (args.files or args.glob) else None
    md_name = f"persona_answers_pipeline_{env}{'_'+suffix if suffix else ''}.md"
    json_name = f"persona_answers_pipeline_{env}{'_'+suffix if suffix else ''}.json"
    md_path = out_dir / md_name
    json_path = out_dir / json_name

    files: list[Path]
    if args.files:
        tmp: list[Path] = []
        for f in args.files:
            p = Path(f)
            if not p.is_absolute():
                p = (REPO_ROOT / p).resolve()
            tmp.append(p)
        files = tmp
    elif args.glob:
        files = sorted(personas_dir.glob(args.glob))
    else:
        files = sorted(personas_dir.glob("*.md"))
    results: List[Dict[str, Any]] = []

    for fp in files:
        if not fp.exists():
            continue
        text = fp.read_text(encoding="utf-8", errors="ignore")
        qas = extract_english_qas(text)
        if not qas:
            # Emit a placeholder entry indicating no questions found
            results.append({
                "file": str(fp.relative_to(REPO_ROOT)) if str(fp).startswith(str(REPO_ROOT)) else str(fp),
                "question": "(no English Q/A pairs found)",
                "expected": "",
                "answer": None,
                "citations": [],
                "source_mode": None,
                "issue": None,
                "recommendation": "Add '- **English Q:**' and '- **English A:**' pairs to the file.",
                "raw": None,
            })
            continue
        for q, expected in qas:
            try:
                res = asyncio.run(ask_pipeline(q))
            except Exception as e:
                res = {"error": str(e)}

            # Extract selected answer and citations
            answer = None
            citations: List[Dict[str, Any]] = []
            source_mode = None
            issue = None
            recommendation = None

            if isinstance(res, dict) and not res.get("error"):
                ans_pack = res.get("answers") or {}
                selected = ans_pack.get("selected")
                answer = ans_pack.get(selected) if selected else None
                retrieved = res.get("retrieved", [])
                for ch in retrieved[:3]:
                    src = ch.get("source")
                    meta = ch.get("metadata") or {}
                    page = meta.get("page") or meta.get("page_number")
                    citations.append({"source": src, "page": page, "score": ch.get("score")})
                if retrieved:
                    source_mode = "astra" if str(retrieved[0].get("source")).startswith("astra:") else "local"
            else:
                issue = "Pipeline error"
                recommendation = "Check Astra credentials and local artifacts; verify retriever can open JSON files."

            if not answer:
                issue = issue or "Insufficient context to synthesize answer from retrieved chunks"
                ql = q.lower()
                if "magebred" in ql or "eberron" in ql:
                    recommendation = (
                        "Ingest Eberron Campaign Setting (Magebred section) via pass A/B so retriever can cite it."
                    )
                elif any(k in ql for k in ["domain", "cleric"]):
                    recommendation = (
                        "Verify Cleric 'Domains' page from CRB is in the corpus and retriever scoring surfaces it."
                    )

            results.append({
                "file": str(fp.relative_to(REPO_ROOT)),
                "question": q,
                "expected": expected,
                "answer": answer,
                "citations": citations,
                "source_mode": source_mode,
                "issue": issue,
                "recommendation": recommendation,
                "raw": res if isinstance(res, dict) else None,
            })

    # Write outputs
    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# Persona Answers via Pipeline ({env})\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"## {i}. {r['question']}\n")
            f.write(f"- File: `{r['file']}`\n")
            f.write(f"- Expected: {r['expected']}\n")
            if r.get("answer"):
                f.write(f"- Answer: {r['answer']}\n")
            if r.get("citations"):
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
            f.write("\n")

    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(md_path))


if __name__ == "__main__":
    import sys as _sys
    main(_sys.argv[1:])
