from __future__ import annotations

"""
Dictionary Initializer

Creates a base concept framework per source by:
- parsing the ToC
- extracting the first N pages
- asking OpenAI to propose dictionary entries (term, definition, category)
- upserting results into Astra dictionary collection via DictionaryLoader

Outputs an artifact JSON for traceability.
"""

import json
import os
import time
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pypdf

from .ttrpg_logging import get_logger
from .toc_parser import TocParser
from .dictionary_loader import DictionaryLoader, DictEntry
from .ttrpg_secrets import get_openai_client_config, _load_env_file


logger = get_logger(__name__)


@dataclass
class DictionaryInitResult:
    terms_upserted: int
    elapsed_ms: int
    artifact_file: Path


def _extract_first_pages_text(pdf_path: Path, num_pages: int = 5) -> str:
    texts: List[str] = []
    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            n = min(num_pages, len(reader.pages))
            for i in range(n):
                try:
                    t = reader.pages[i].extract_text() or ""
                    texts.append(t.strip())
                except Exception as e:
                    logger.warning(f"Failed extracting page {i+1}: {e}")
    except Exception as e:
        logger.warning(f"Opening PDF for first-pages extract failed: {e}")
    return "\n\n".join([t for t in texts if t])[:5000]


def _build_prompt(toc_outline: Dict[str, Any], sample_text: str, source_name: str) -> Dict[str, str]:
    system_prompt = (
        "You are a knowledge engineer indexing TTRPG rulebooks. "
        "Given a Table of Contents and sample pages, produce a compact JSON array of dictionary entries. "
        "Each entry must include: term, definition (<= 200 chars), category. "
        "Use TTRPG categories like mechanics, spells, feats, classes, races, equipment, combat, exploration, general. "
        "Prefer mechanics and definitional terms that appear in the ToC or the early pages. "
        "Do not add fields besides term/definition/category. Return JSON only."
    )

    # Summarize ToC top-level entries to keep prompt small
    toc_lines: List[str] = []
    try:
        entries = toc_outline.get("entries", [])
        for e in entries[:30]:
            title = str(e.get("title", "")).strip()
            page = e.get("page", 0)
            level = e.get("level", 1)
            if not title:
                continue
            indent = "  " * (max(0, int(level) - 1))
            toc_lines.append(f"{indent}- p{page}: {title}")
    except Exception:
        pass

    user_prompt = (
        f"Source: {source_name}\n\n"
        f"Table of Contents (first entries):\n" + "\n".join(toc_lines) + "\n\n"
        "Sample pages (first few pages, trimmed):\n" + sample_text + "\n\n"
        "Return a JSON array of 10-30 entries."
    )
    return {"system": system_prompt, "user": user_prompt}


def _call_openai_json(system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
    """Call OpenAI Chat Completions; tolerate DEV CA issues if SSL_NO_VERIFY set."""
    cfg = get_openai_client_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing; ensure .env is loaded")

    import httpx
    from .ssl_bypass import get_httpx_verify_setting

    verify = get_httpx_verify_setting()

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = "https://api.openai.com/v1/chat/completions"
    with httpx.Client(timeout=60, verify=verify) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    raw = data["choices"][0]["message"]["content"].strip()

    # Try to parse as JSON directly; if not, extract the first JSON block
    def _extract_json(text: str) -> str:
        m = re.search(r"\[.*\]", text, flags=re.DOTALL)
        return m.group(0) if m else text

    payload = _extract_json(raw)
    try:
        data = json.loads(payload)
        if isinstance(data, list):
            return data
        else:
            return []
    except Exception:
        logger.warning("OpenAI dictionary response was not valid JSON")
        return []


def initialize_dictionary_from_source(pdf_path: Path, output_dir: Path, env: str = "dev", pages: int = 5) -> DictionaryInitResult:
    start = time.time()

    # Ensure .env is loaded for OPENAI (root-level .env)
    project_root = Path(__file__).resolve().parents[1]
    root_env = project_root / ".env"
    if root_env.exists():
        _load_env_file(root_env)
    env_env = project_root / "env" / env / "config" / ".env"
    if env_env.exists():
        _load_env_file(env_env)

    # ToC and sample text
    parser = TocParser()
    outline = parser.parse_document_structure(pdf_path)
    sample = _extract_first_pages_text(pdf_path, pages)

    prompts = _build_prompt(
        {
            "entries": [
                {
                    "title": e.title,
                    "page": e.page,
                    "level": e.level,
                    "section_id": e.section_id,
                    "parent_id": e.parent_id,
                }
                for e in (outline.entries or [])
            ]
        },
        sample,
        source_name=pdf_path.name,
    )

    entries_json = _call_openai_json(prompts["system"], prompts["user"]) if sample else []

    # Normalize and upsert
    loader = DictionaryLoader(env)
    normalized: List[DictEntry] = []
    for obj in entries_json:
        try:
            term = str(obj.get("term", "")).strip()
            definition = str(obj.get("definition", "")).strip()
            category = str(obj.get("category", "general")).strip().lower() or "general"
            if not term or not definition:
                continue
            normalized.append(
                DictEntry(
                    term=term,
                    definition=definition[:400],
                    category=category,
                    sources=[{"source": pdf_path.name, "method": "init", "page_hint": 1}],
                )
            )
        except Exception:
            continue

    upserted = loader.upsert_entries(normalized) if normalized else 0

    # Write artifact for audit
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / "dictionary_init.json"
    try:
        with open(artifact, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "source": pdf_path.name,
                    "toc_count": len(outline.entries or []),
                    "entries_proposed": entries_json,
                    "entries_upserted": upserted,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
    except Exception as e:
        logger.warning(f"Failed to write dictionary init artifact: {e}")

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(f"Dictionary initialized for {pdf_path.name}: upserted {upserted} terms in {elapsed_ms}ms")
    return DictionaryInitResult(terms_upserted=upserted, elapsed_ms=elapsed_ms, artifact_file=artifact)
