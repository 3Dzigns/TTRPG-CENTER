#!/usr/bin/env python3
"""
Batch runner for Persona question evaluation.

Reads persona files under docs/Personas/Persona_*.md (excluding *_response.md),
extracts English and Profile-Language questions and expected answers, runs each
question through the system RAG + OpenAI pipeline, and writes results to
Persona_{Name}_response.md alongside the persona.

Notes:
- Requires OPENAI_API_KEY in environment (or in .env) for OpenAI calls.
- Uses the Phase 2 /rag/ask endpoint (stub classifier + retrieval) and then
  composes an OpenAI prompt with retrieved chunks (see scripts/rag_openai.py).
- Does not modify system code; only reads personas and writes response files.
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi.testclient import TestClient

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src_common.app import app
from scripts.rag_openai import load_dotenv_into_env  # reuse helper


@dataclass
class QAItem:
    lang: str         # "English" or profile language label
    question: str
    expected: str


OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


def openai_chat(model: str, system_prompt: str, user_prompt: str, api_key: str) -> str:
    model_map = {
        "gpt-5-large": "gpt-4o",  # fallback routing
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4o": "gpt-4o",
    }
    model_name = model_map.get(model, model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(OPENAI_API_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def run_rag_openai(env: str, query: str, top_k: int = 3) -> Dict[str, Any]:
    os.environ["APP_ENV"] = env
    client = TestClient(app)
    resp = client.post("/rag/ask", json={"query": query, "top_k": top_k})
    resp.raise_for_status()
    data = resp.json()
    cls = data.get("classification", {})
    model_cfg = data.get("model", {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.2})
    chunks = data.get("retrieved", [])

    # Compose prompts
    system_prompt = (
        "You are the TTRPG Center Assistant. Answer strictly using the provided context. "
        "If insufficient, say so. Include bracketed [n] citations."
    )

    context_lines: List[str] = []
    for i, c in enumerate(chunks, 1):
        snippet = (c.get("text") or "")
        if len(snippet) > 1500:
            snippet = snippet[:1500] + "…"
        src = c.get("source") or ""
        context_lines.append(f"[{i}] {snippet}\nSource: {src}")

    user_prompt = (
        ("Context:\n\n" + "\n\n".join(context_lines) + "\n\n") if context_lines else ""
    ) + f"Question: {query}\nAnswer concisely with [n] citations."

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set; load from .env or environment")

    answer = openai_chat(model_cfg.get("model", "gpt-4o-mini"), system_prompt, user_prompt, api_key)
    return {
        "classification": cls,
        "model": model_cfg,
        "retrieved": chunks,
        "answer": answer,
    }


def parse_persona_file(path: Path) -> Tuple[str, str, List[QAItem]]:
    """Return (name, profile_language_label, list of QAItem)."""
    text = path.read_text(encoding="utf-8")

    # Extract Name
    name_match = re.search(r"^-\s*Name:\s*(.+)$", text, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else path.stem.replace("Persona_", "")

    # Extract profile language label
    lang_match = re.search(r"^-\s*Language\s*\(.*?\):\s*(.+)$", text, re.MULTILINE)
    profile_lang = lang_match.group(1).strip() if lang_match else "Profile Language"

    # Extract Q&A blocks
    qa_items: List[QAItem] = []

    # English section
    en_section = re.search(r"##\s*Q&A\s*\(English\)(.*?)(?:\n---|\Z)", text, re.S)
    if en_section:
        sec = en_section.group(1)
        for block in re.split(r"\n###\s*Question\s*\d+\s*\(English\)\s*\n", sec)[1:]:
            q_match = re.search(r"^-\s*Question:\s*(.+)$", block, re.M)
            a_match = re.search(r"^-\s*(?:Expected\s+)?Answer\s*\(English\):\s*(.+)$", block, re.M)
            if q_match:
                qa_items.append(QAItem("English", q_match.group(1).strip(), (a_match.group(1).strip() if a_match else "")))

    # Profile language section
    pl_section = re.search(r"##\s*Q&A\s*\(Profile\s*Language\)(.*)\Z", text, re.S)
    if pl_section:
        sec = pl_section.group(1)
        for block in re.split(r"\n###\s*Question\s*\d+\s*\(Profile\s*Language\)\s*\n", sec)[1:]:
            q_match = re.search(r"^-\s*Question:\s*(.+)$", block, re.M)
            a_match = re.search(r"^-\s*(?:Expected\s+)?Answer\s*\(Profile\s*Language\):\s*(.+)$", block, re.M)
            if q_match:
                qa_items.append(QAItem(profile_lang, q_match.group(1).strip(), (a_match.group(1).strip() if a_match else "")))

    return name, profile_lang, qa_items


def simple_similarity(a: str, b: str) -> float:
    """A quick token Jaccard similarity (lowercased, alnum tokens)."""
    def toks(s: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", s.lower()))
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / max(1, union)


def summarize_issue(answer: str, expected: str, lang: str) -> str:
    """Heuristic ISSUE note based on mismatch."""
    if not expected:
        return "ISSUE: No expected answer provided for comparison."
    if len(answer.strip()) < 10:
        return "ISSUE: Very short or empty answer; retrieval context likely missing or model failed to respond."
    if lang != "English":
        return "ISSUE: Non-English query may reduce retrieval quality; consider translating query or adding multilingual context."
    return "ISSUE: Low overlap with expected answer; retrieval may have missed relevant chunks or prompt lacked specifics."


def render_markdown(name: str, profile_lang: str, env: str, results: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append(f"# Persona Responses — {name}")
    lines.append("")
    lines.append(f"- Environment: {env}")
    lines.append(f"- Timestamp: {int(time.time())}")
    lines.append(f"- Profile Language: {profile_lang}")
    lines.append("\n---\n")
    for idx, r in enumerate(results, 1):
        lines.append(f"## Q{idx} ({r['lang']})")
        lines.append(f"**Question:** {r['question']}")
        if r.get("expected"):
            lines.append(f"**Expected:** {r['expected']}")
        lines.append(f"**Answer:** {r['answer']}")
        if r.get("issue"):
            lines.append(f"**{r['issue']}**")
        # Citations (if any)
        cites = []
        for i, c in enumerate(r.get("retrieved", [])[:3], 1):
            src = c.get("source") or ""
            sec = (c.get("metadata") or {}).get("section_title") or (c.get("metadata") or {}).get("section")
            cites.append(f"- [{i}] {Path(src).name if src else ''}{' · '+sec if sec else ''}")
        if cites:
            lines.append("**Citations:**\n" + "\n".join(cites))
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    # Load env files to pick up OPENAI_API_KEY and any ASTRA settings
    load_dotenv_into_env(Path(".env"))
    load_dotenv_into_env(Path("env/dev/config/.env"))

    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))

    personas_dir = Path("docs/Personas")
    files = sorted([p for p in personas_dir.glob("Persona_*.md") if not p.name.endswith("_response.md")])

    # Optional whitelist via env var PERSONA_ONLY (comma-separated basenames)
    only_raw = os.getenv("PERSONA_ONLY", "").strip()
    only_set = set()
    if only_raw:
        only_set = {name.strip() for name in only_raw.split(",") if name.strip()}
        if only_set:
            files = [p for p in files if p.name in only_set or p.stem in only_set]
    if not files:
        print("No persona files found in docs/Personas")
        return 1

    out_count = 0
    # Domain filters: only English + Eberron (and optionally PF1e/3.5) topics; exclude PF2e‑specific mechanics
    EBER_KEYWORDS = {
        "eberron", "sharn", "dragonmark", "dragonmarked", "house ", "warforged",
        "mournland", "mourning", "lightning rail", "airship", "dragonshard",
        "lyrandar", "cannith", "deneith", "jorasco", "kundarak", "phiarlan",
        "thuranni", "talenta", "kalashtar", "manifest zone", "elemental binding",
    }
    PF2_BLOCKERS = {
        "pf2e", "pf2", "three-action", "three action", "treat wounds", "refocus",
        "degrees of success", "multiple attack penalty", "counteract", "focus spell",
        "class feat", "skill feat", "archetype", "assurance", "earn income",
        "strike", "flurry", "magus", "gunslinger", "inventor", "champion", "marshal",
    }

    def is_in_scope_english(q: QAItem) -> bool:
        if q.lang != "English":
            return False
        # If explicit whitelist is provided, accept any English question
        if only_set:
            return True
        ql = q.question.lower()
        # Require at least one Eberron keyword
        if not any(k in ql for k in EBER_KEYWORDS):
            return False
        # Exclude PF2e mechanics terms
        if any(b in ql for b in PF2_BLOCKERS):
            return False
        return True

    for path in files:
        try:
            name, profile_lang, qas = parse_persona_file(path)
            # Filter to in-scope English Eberron questions
            qas = [qa for qa in qas if is_in_scope_english(qa)]
            if not qas:
                print(f"No Q&A found in {path.name}; skipping")
                continue

            results: List[Dict[str, Any]] = []
            for qa in qas:
                rag = run_rag_openai(env, qa.question)
                ans = rag.get("answer", "")
                sim = simple_similarity(ans, qa.expected)
                issue_note = ""
                if sim < 0.30:  # heuristic threshold
                    issue_note = summarize_issue(ans, qa.expected, qa.lang)
                results.append({
                    "lang": qa.lang,
                    "question": qa.question,
                    "expected": qa.expected,
                    "answer": ans,
                    "retrieved": rag.get("retrieved", []),
                    "issue": issue_note,
                })

            out_md = render_markdown(name, profile_lang, env, results)
            out_path = path.with_name(f"Persona_{name.replace(' ', '_')}_response.md")
            out_path.write_text(out_md, encoding="utf-8")
            out_count += 1
            print(f"Wrote {out_path}")
        except Exception as e:
            print(f"Error processing {path.name}: {e}")

    print(f"Done. Wrote {out_count} response files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
