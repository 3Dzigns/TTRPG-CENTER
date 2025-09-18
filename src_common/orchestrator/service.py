from __future__ import annotations

import os
import time
import uuid
from types import SimpleNamespace
from typing import Any, Dict, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..ttrpg_logging import get_logger
from ..metadata_utils import safe_metadata_get
from .classifier import classify_query
from .policies import load_policies, choose_plan
from .router import pick_model
from .query_planner import get_planner
from .llm_runtime import generate_rag_answers
from .prompts import load_prompt, render_prompt, PromptError
from .retriever import retrieve
from ..aehrl.evaluator import AEHRLEvaluator
from ..aehrl.metrics_tracker import MetricsTracker
from ..personas.manager import PersonaManager
from ..personas.validator import PersonaResponseValidator
from ..personas.metrics import PersonaMetricsTracker

logger = get_logger(__name__)

rag_router = APIRouter()

LANE_CHOICES = {"A", "B", "C", "ALL"}


def _normalize_lane(value: Optional[str]) -> str:
    lane = (value or "A").strip().upper()
    if lane not in LANE_CHOICES:
        return "A"
    return lane


def _resolve_query_plan(env: str, query: str, classification: Optional[Dict[str, Any]] = None):
    """Return classification, query plan, retrieval plan, and model config."""
    classification = classification or classify_query(query)
    planner = get_planner(env)
    try:
        query_plan = planner.get_plan(query)
    except Exception:
        query_plan = None

    plan = getattr(query_plan, "retrieval_strategy", None) if query_plan else None
    model_cfg = getattr(query_plan, "model_config", None) if query_plan else None

    if not plan or not model_cfg:
        policies = load_policies()
        plan = choose_plan(policies, classification)
        model_cfg = pick_model(classification, plan)
        query_plan = SimpleNamespace(
            retrieval_strategy=plan,
            model_config=model_cfg,
            graph_expansion=None,
            performance_hints={},
            query_hash=None,
            hit_count=0,
        )

    return classification, query_plan, plan, model_cfg


@rag_router.get("/ping")
async def rag_ping():
    return {"status": "ok", "component": "rag", "environment": os.getenv("APP_ENV", "dev")}

@rag_router.post("/classify")
async def rag_classify(payload: Dict[str, Any]):
    env = os.getenv("APP_ENV", "dev")
    q = (payload or {}).get("query", "").strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    classification = classify_query(q)

    return {
        "query": q,
        "environment": env,
        "classification": classification,
    }


@rag_router.post("/retrieve")
async def rag_retrieve(payload: Dict[str, Any]):
    env = os.getenv("APP_ENV", "dev")
    q = (payload or {}).get("query", "").strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    lane = _normalize_lane((payload or {}).get("lane"))
    lane_filter = None if lane == "ALL" else lane
    top_k = int(payload.get("top_k", 3) or 3)

    classification, query_plan, plan, model_cfg = _resolve_query_plan(env, q)

    chunks = retrieve(plan, q, env, limit=top_k, lane=lane_filter)
    chunk_payload = [
        {
            "id": c.id,
            "text": c.text,
            "source": c.source,
            "score": c.score,
            "metadata": c.metadata,
        }
        for c in chunks
    ]

    model_meta: Dict[str, Any] = {}
    if isinstance(model_cfg, dict):
        model_meta.update(model_cfg)
    elif hasattr(model_cfg, "items"):
        try:
            model_meta.update(dict(model_cfg))
        except Exception:
            pass

    if isinstance(plan, dict):
        retrieval_plan = plan
    elif hasattr(plan, "items"):
        try:
            retrieval_plan = dict(plan)
        except Exception:
            retrieval_plan = {"value": str(plan)}
    else:
        retrieval_plan = {"value": str(plan)}

    return {
        "query": q,
        "environment": env,
        "lane": lane,
        "top_k": top_k,
        "classification": classification,
        "retrieval_plan": retrieval_plan,
        "model": model_meta,
        "chunks": chunk_payload,
        "trace_id": str(uuid.uuid4()),
    }



@rag_router.post("/ask")
async def rag_ask(payload: Dict[str, Any]):
    t0 = time.time()
    env = os.getenv("APP_ENV", "dev")
    q = (payload or {}).get("query", "").strip()
    if not q:
        return JSONResponse(status_code=400, content={"error": "query is required"})

    trace_id = str(uuid.uuid4())

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

    lane = _normalize_lane((payload or {}).get("lane"))
    lane_filter = None if lane == "ALL" else lane

    classification, query_plan, plan, model_cfg = _resolve_query_plan(env, q)

    # 4) Prompt template
    tmpl = load_prompt(classification["intent"], classification["domain"])  # best-effort
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
    top_chunks = retrieve(plan, q, env, limit=payload.get("top_k", 3), lane=lane_filter)


    # 6) Compose stub answers and attempt live generation when permitted
    def _synth(prefix: str) -> str:
        parts = []
        if top_chunks:
            parts.append("Answer (from retrieved context):")
            parts.append(top_chunks[0].text[:300])
        else:
            parts.append("No relevant chunks found in the current environment artifacts.")
        parts.append("")
        parts.append("Citations:")
        for ch in top_chunks[:3]:
            meta_page = safe_metadata_get(ch.metadata, "page") or safe_metadata_get(ch.metadata, "page_number")
            sec = safe_metadata_get(ch.metadata, "section") or safe_metadata_get(ch.metadata, "section_title")
            cite = f"[{PathSafe(ch.source).name}{' p.' + str(meta_page) if meta_page else ''}{' :: ' + sec if sec else ''}]"
            parts.append(f"- {cite}")
        return f"{prefix}: " + "\n".join(parts)

    def _build_provider_prompt(base_prompt: str) -> str:
        if not top_chunks:
            return base_prompt
        segments = [base_prompt, "", "Retrieved context:"]
        for idx, chunk in enumerate(top_chunks[:5], start=1):
            snippet = chunk.text.strip().replace("\n", " ")[:500]
            segments.append(f"{idx}. {PathSafe(chunk.source).name}: {snippet}")
        segments.append("")
        segments.append("Use the retrieved context when forming answers and cite sources succinctly.")
        return "\n".join(segments)

    stub_answers = {"openai": _synth("OpenAI_stub"), "claude": _synth("Claude_stub")}
    provider_prompt = _build_provider_prompt(rendered_prompt)
    llm_result = generate_rag_answers(
        prompt=provider_prompt,
        model_cfg=model_cfg if isinstance(model_cfg, dict) else model_cfg,
        stub_answers=stub_answers,
    )
    selected_answer = llm_result.answers.get(llm_result.selected, next(iter(stub_answers.values()), ""))

    answers_payload = dict(llm_result.answers)
    answers_payload["selected"] = llm_result.selected
    used_stub_llm = llm_result.used_stub_llm
    degraded = llm_result.degraded
    degraded_reason = llm_result.degraded_reason
    provider_metadata = llm_result.provider_metadata

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
                    "message": f"[WARN] Unsupported statement - please verify: {flag.claim.text}",
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

    model_meta: Dict[str, Any] = {}
    if isinstance(model_cfg, dict):
        model_meta.update(model_cfg)
    elif hasattr(model_cfg, 'items'):
        try:
            model_meta.update(dict(model_cfg))
        except Exception:
            pass
    if provider_metadata:
        for key, value in provider_metadata.items():
            if value is not None:
                model_meta[key] = value

    response = {
        "query": q,
        "environment": env,
        "lane": lane,
        "classification": classification,
        "plan": plan,
        "model": model_meta,
        "query_planning": {
            "enabled": True,
            "plan_cached": query_plan.hit_count > 0 if 'query_plan' in locals() else False,
            "plan_hash": query_plan.query_hash if 'query_plan' in locals() else None,
            "cache_hit_count": query_plan.hit_count if 'query_plan' in locals() else 0,
            "performance_hints": query_plan.performance_hints if 'query_plan' in locals() else {}
        },
        "metrics": {
            "timer_ms": elapsed_ms,
            "token_count": approx_tokens,
            "model_badge": model_meta.get("model"),
            "mode": "live" if not used_stub_llm else "stub",
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
        "answers": answers_payload,
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
        "used_stub_llm": used_stub_llm,
        "degraded": degraded,
        "trace_id": trace_id,
        "answer": selected_answer,
        "sources": [c.source for c in top_chunks],
    }
    if degraded and degraded_reason:
        response["degraded_reason"] = degraded_reason


    logger.info(
        "RAG ask handled",
        extra={
            "component": "rag",
            "duration_ms": elapsed_ms,
            "env": env,
            "top_chunks": len(top_chunks),
            "intent": classification.get("intent"),
            "used_stub_llm": used_stub_llm,
            "degraded": degraded,
            "llm_provider": llm_result.provider,
            "lane": lane,
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


