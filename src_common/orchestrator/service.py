from __future__ import annotations

import os
import time
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..ttrpg_logging import get_logger
from ..metadata_utils import safe_metadata_get
from .classifier import classify_query
from .policies import load_policies, choose_plan
from .router import pick_model
from .prompts import load_prompt, render_prompt, PromptError
from .retriever import retrieve

logger = get_logger(__name__)

rag_router = APIRouter()


@rag_router.get("/ping")
async def rag_ping():
    return {"status": "ok", "component": "rag", "environment": os.getenv("APP_ENV", "dev")}


@rag_router.post("/ask")
async def rag_ask(payload: Dict[str, Any]):
    t0 = time.time()
    env = os.getenv("APP_ENV", "dev")
    q = (payload or {}).get("query", "").strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    # 1) Classify
    cls = classify_query(q)

    # 2) Plan selection
    policies = load_policies()
    plan = choose_plan(policies, cls)

    # 3) Model routing
    model_cfg = pick_model(cls, plan)

    # 4) Prompt template
    tmpl = load_prompt(cls["intent"], cls["domain"])  # best-effort
    try:
        rendered_prompt = render_prompt(
            tmpl,
            {
                "TASK_BRIEF": q,
                "STYLE": "concise, cite sources",
                "POLICY_SNIPPET": "Use only retrieved chunks; include concise citations.",
            },
        )
    except PromptError as e:
        rendered_prompt = f"You are the TTRPG Center Assistant. TASK: {q}"

    # 5) Retrieve top chunks
    top_chunks = retrieve(plan, q, env, limit=payload.get("top_k", 3))

    # 6) Synthesize stub answers (no external network)
    def _synth(prefix: str) -> str:
        parts = []
        if top_chunks:
            parts.append("Answer (from retrieved context):")
            parts.append(top_chunks[0].text[:300])
        else:
            parts.append("No relevant chunks found in the current environment artifacts.")
        parts.append("\nCitations:")
        for ch in top_chunks[:3]:
            meta_page = safe_metadata_get(ch.metadata, "page") or safe_metadata_get(ch.metadata, "page_number")
            sec = safe_metadata_get(ch.metadata, "section") or safe_metadata_get(ch.metadata, "section_title")
            cite = f"[{PathSafe(ch.source).name}{' p.'+str(meta_page) if meta_page else ''}{' · '+sec if sec else ''}]"
            parts.append(f"- {cite}")
        return f"{prefix}: " + "\n".join(parts)

    openai_answer = _synth("OpenAI_stub")
    claude_answer = _synth("Claude_stub")

    # 7) Heuristic selector (prefer longer context)
    heuristic = "openai" if len(openai_answer) >= len(claude_answer) else "claude"

    elapsed_ms = int((time.time() - t0) * 1000)
    approx_tokens = max(1, len(q.split()) + sum(len(c.text.split()) for c in top_chunks))

    response = {
        "query": q,
        "environment": env,
        "classification": cls,
        "plan": plan,
        "model": model_cfg,
        "metrics": {
            "timer_ms": elapsed_ms,
            "token_count": approx_tokens,
            "model_badge": model_cfg.get("model"),
        },
        "retrieved": [
            {
                "id": c.id,
                "text": c.text,
                "source": c.source,
                "score": c.score,
                "metadata": c.metadata,
            }
            for c in top_chunks
        ],
        "answers": {
            "openai": openai_answer,
            "claude": claude_answer,
            "selected": heuristic,
        },
        "used_stub_llm": True,
    }

    logger.info(
        "RAG ask handled",
        extra={
            "component": "rag",
            "duration_ms": elapsed_ms,
            "env": env,
            "top_chunks": len(top_chunks),
            "intent": cls.get("intent"),
        },
    )
    return JSONResponse(content=response)


class PathSafe(str):
    @property
    def name(self) -> str:
        try:
            from pathlib import Path as _P

            return _P(self).name
        except Exception:
            return str(self)
