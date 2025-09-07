"""
Ingestion Primer

Generates or loads a domain TagSpec ("primer") for a given source title to guide
ingestion (roles/categories/procedures) and retrieval weighting. Falls back to a
generic TagSpec when the model is unavailable.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List
import httpx

from .logging import get_logger

logger = get_logger(__name__)


def _primer_cache_path(env: str, system_key: str) -> Path:
    root = Path("artifacts") / "primers" / env
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{system_key}.json"


def _system_key_from_title(title: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return key or "unknown_system"


def _generic_tagspec(title: str) -> Dict[str, Any]:
    return {
        "system_id": _system_key_from_title(title),
        "categories": [
            "rules.action_resolution",
            "rules.combat",
            "procedures.general",
            "gear.equipment",
            "vehicles.general",
        ],
        "entities": [
            {"name": "difficulty_class", "regex": "\\bDC\\s*\\d+\\b"},
            {"name": "hit_points", "regex": "\\bHP\\s*\\d+\\b"},
        ],
        "chunk_roles": [
            {"role": "table", "schema_hint": "generic_table", "headers_like": ["Name", "Type", "Notes"]},
            {"role": "list", "schema_hint": "generic_list", "headers_like": []},
        ],
        "procedures": {"cues": ["Procedure", "Steps", "Sequence"], "list_patterns": ["^\\d+\\.", "^- "]},
        "synonyms": [],
        "retrieval_weights": {"procedures.general": 1.2, "table": 1.1},
        "version": {"source": "generic", "model": None},
    }


def _openai_chat_json(prompt: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You produce concise JSON only. No prose, no code fences."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    with httpx.Client(timeout=40) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "{}").strip()
    try:
        return json.loads(text)
    except Exception:
        # Last resort: extract JSON substring
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise


def load_or_create_primer(env: str, title: str, toc_text: str, sample_texts: List[str]) -> Dict[str, Any]:
    """Load primer from cache or create via OpenAI; fallback to generic."""
    system_key = _system_key_from_title(title)
    cache_path = _primer_cache_path(env or "dev", system_key)
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            logger.warning(f"Primer cache read failed: {e}")

    # Build prompt (bounded)
    toc = (toc_text or "")[:3000]
    sample = "\n\n".join((s or "")[:1500] for s in (sample_texts or [])[:2])
    prompt = (
        "Title: " + title + "\n\n"
        "Given the title and ToC/sample excerpts, produce a JSON TagSpec for this TTRPG system: "
        "{system_id, categories[], entities[{name,regex}], chunk_roles[{role,schema_hint,headers_like/keys_like}], "
        "procedures{cues,list_patterns}, synonyms[], retrieval_weights{}, version{model}}."
        "Keep it concise and generic."
        f"\n\nToC/Preface (excerpt):\n{toc}\n\nSample (excerpt):\n{sample}"
    )

    try:
        tagspec = _openai_chat_json(prompt)
        # Minimal shape check
        if not isinstance(tagspec, dict) or not tagspec.get("categories"):
            raise ValueError("Invalid TagSpec shape")
        cache_path.write_text(json.dumps(tagspec, indent=2), encoding="utf-8")
        logger.info(f"Primer generated and cached: {cache_path}")
        return tagspec
    except Exception as e:
        logger.warning(f"Primer generation failed, using generic: {e}")
        tagspec = _generic_tagspec(title)
        try:
            cache_path.write_text(json.dumps(tagspec, indent=2), encoding="utf-8")
        except Exception:
            pass
        return tagspec

