from __future__ import annotations

import os
import time
import uuid
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
from ..aehrl.evaluator import AEHRLEvaluator
from ..aehrl.metrics_tracker import MetricsTracker
from ..personas.manager import PersonaManager
from ..personas.validator import PersonaResponseValidator
from ..personas.metrics import PersonaMetricsTracker

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

    # 0) Persona context extraction (if enabled)
    persona_enabled = os.getenv("PERSONA_TESTING_ENABLED", "true").lower() == "true"
    persona_context = None
    persona_manager = None

    if persona_enabled:
        try:
            persona_manager = PersonaManager()
            persona_context = persona_manager.extract_persona_context_from_request(payload)
            if persona_context:
                logger.info(f"Extracted persona context: {persona_context.persona_profile.id}")
        except Exception as e:
            logger.warning(f"Failed to extract persona context: {e}")
            persona_context = None

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
    selected_answer = openai_answer if heuristic == "openai" else claude_answer

    # 8) AEHRL Evaluation (if enabled)
    aehrl_enabled = os.getenv("AEHRL_ENABLED", "true").lower() == "true"
    aehrl_report = None
    hallucination_warnings = []
    persona_metrics = None

    if aehrl_enabled:
        try:
            query_id = str(uuid.uuid4())
            evaluator = AEHRLEvaluator(environment=env)

            # Prepare retrieved chunks for AEHRL
            chunk_data = [
                {
                    "chunk_id": c.id,
                    "content": c.text,
                    "source_file": c.source,
                    "page_number": safe_metadata_get(c.metadata, "page") or safe_metadata_get(c.metadata, "page_number"),
                    "metadata": c.metadata
                }
                for c in top_chunks
            ]

            # Evaluate the selected answer with persona context
            aehrl_report = evaluator.evaluate_query_response(
                query_id=query_id,
                model_response=selected_answer,
                retrieved_chunks=chunk_data,
                persona_context=persona_context
            )

            # Generate user warnings for high-priority flags
            for flag in aehrl_report.get_high_priority_flags():
                hallucination_warnings.append({
                    "message": f"⚠️ Unsupported statement — please verify: {flag.claim.text}",
                    "confidence": flag.claim.confidence,
                    "severity": flag.severity.value,
                    "recommendation": flag.recommended_action
                })

            # Record metrics
            if aehrl_report.metrics:
                metrics_tracker = MetricsTracker(environment=env)
                metrics_tracker.record_metrics(aehrl_report)

            logger.info(f"AEHRL evaluation completed for query {query_id}")

        except Exception as e:
            logger.warning(f"AEHRL evaluation failed: {str(e)}")
            aehrl_report = None

    # 9) Persona Response Validation (if persona context available)
    if persona_enabled and persona_context:
        try:
            validator = PersonaResponseValidator()
            persona_metrics = validator.validate_response_appropriateness(
                response=selected_answer,
                persona_context=persona_context,
                query=q
            )

            # Update with actual response time
            current_elapsed_ms = int((time.time() - t0) * 1000)
            persona_metrics.response_time_ms = current_elapsed_ms

            # Record persona metrics
            persona_tracker = PersonaMetricsTracker(environment=env)
            persona_tracker.record_metrics(persona_metrics)

            logger.info(f"Persona validation completed for {persona_context.persona_profile.id}")

        except Exception as e:
            logger.warning(f"Persona validation failed: {str(e)}")
            persona_metrics = None

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
        "aehrl": {
            "enabled": aehrl_enabled,
            "warnings": hallucination_warnings,
            "metrics": {
                "support_rate": aehrl_report.metrics.support_rate if aehrl_report and aehrl_report.metrics else None,
                "hallucination_rate": aehrl_report.metrics.hallucination_rate if aehrl_report and aehrl_report.metrics else None,
                "total_claims": aehrl_report.metrics.total_claims if aehrl_report and aehrl_report.metrics else None,
                "flagged_claims": aehrl_report.metrics.flagged_claims if aehrl_report and aehrl_report.metrics else None
            } if aehrl_report and aehrl_report.metrics else None,
            "query_id": aehrl_report.query_id if aehrl_report else None
        },
        "persona": {
            "enabled": persona_enabled,
            "context": {
                "persona_id": persona_context.persona_profile.id if persona_context else None,
                "persona_name": persona_context.persona_profile.name if persona_context else None,
                "persona_type": persona_context.persona_profile.persona_type.value if persona_context else None,
                "experience_level": persona_context.persona_profile.experience_level.value if persona_context else None,
                "session_context": persona_context.session_context.value if persona_context else None
            } if persona_context else None,
            "validation": {
                "appropriateness_score": persona_metrics.appropriateness_score if persona_metrics else None,
                "detail_level_match": persona_metrics.detail_level_match if persona_metrics else None,
                "user_satisfaction_predicted": persona_metrics.user_satisfaction_predicted if persona_metrics else None,
                "response_appropriate": persona_metrics.appropriateness_score >= 0.7 if persona_metrics else None
            } if persona_metrics else None
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
