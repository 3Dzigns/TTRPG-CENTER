"""
Orchestrator Service API

FastAPI service for query classification, retrieval, and orchestration.
MVP v2 Microservices Architecture - Task 03 Implementation
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config
from src_common.security import bootstrap_app_security, record_audit_event, require_roles
from src_common.auth_models import UserContext
from .classifier import Classification
from .engine import OrchestratorEngine
from .types import (
    QueryPayload,
    RetrievalRequestPayload,
    AnswerRequestPayload,
    ClassificationModel,
    RetrievalResponseModel,
    AnswerResponseModel,
    ErrorEnvelope,
    build_error,
    HealthStatus,
)


logger = get_logger(__name__)


# Legacy compatibility models - kept for backward compatibility
class QueryRequest(BaseModel):
    """Legacy query processing request."""

    query: str = Field(..., min_length=1, max_length=1000)
    context: Optional[Dict[str, str]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ClassificationResponse(BaseModel):
    """Legacy query classification response."""

    classification: Dict[str, str]
    processing_time_ms: float
    timestamp: str


# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Orchestrator Service",
    description="Query classification, retrieval, and orchestration with hybrid retrieval pipeline",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

bootstrap_app_security(app, service_name="orchestrator")

# Initialize orchestrator engine with full hybrid retrieval
engine = OrchestratorEngine()

# Idempotency key tracking for state-mutating operations
_idempotency_cache: Dict[str, Dict] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Orchestrator Service v2.0.0 with hybrid retrieval")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Policies and prompt templates are loaded by OrchestratorEngine
    logger.info("Policy and prompt registry loaded successfully")
    logger.info(f"Policy version: {engine.policy_manager.version}")
    logger.info(f"Prompt registry version: {engine.prompt_registry.version}")


@app.get("/healthz", response_model=HealthStatus)
async def health_check():
    """Health check endpoint with detailed status."""
    import datetime

    uptime_seconds = time.perf_counter() - engine._started_at

    return HealthStatus(
        status="healthy",
        service="orchestrator",
        version="2.0.0",
        environment=engine.environment,
        uptime_seconds=uptime_seconds,
        hot_reload_enabled=engine.policy_manager.hot_reload,
        timestamp=datetime.datetime.utcnow()
    )


@app.post("/classify", response_model=ClassificationResponse)
async def classify_query(request: QueryRequest):
    """Classify query intent, domain, and complexity."""
    start_time = time.perf_counter()

    try:
        logger.info(f"Classifying query: {request.query[:50]}...")

        # Use engine's classifier
        classification = engine.classifier.classify_query(request.query)
        processing_time_ms = (time.perf_counter() - start_time) * 1000

        import datetime
        response = ClassificationResponse(
            classification=classification,
            processing_time_ms=processing_time_ms,
            timestamp=datetime.datetime.utcnow().isoformat()
        )

        logger.info(f"Classification result: {classification} ({processing_time_ms:.1f}ms)")

        # Check performance requirement (sub-150ms p95)
        if processing_time_ms > 150:
            logger.warning(f"Classification exceeded p95 target: {processing_time_ms:.1f}ms")

        return response

    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        error_envelope = build_error("CLASSIFICATION_FAILED", f"Classification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_envelope.model_dump()
        )


@app.post("/v2/retrieve", response_model=RetrievalResponseModel)
async def retrieve_context_v2(request: RetrievalRequestPayload):
    """Execute hybrid retrieval strategy based on classification."""
    start_time = time.perf_counter()

    try:
        logger.info(f"Retrieving context for: {request.query[:50]}...")

        # Execute hybrid retrieval using the engine
        result = engine.retrieve(
            query=request.query,
            classification=request.classification,
            top_k=request.top_k,
            lane=request.lane
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(f"Retrieved {result.total_chunks} chunks using hybrid strategy ({processing_time_ms:.1f}ms)")

        return result

    except Exception as e:
        logger.error(f"Retrieval error: {str(e)}")
        error_envelope = build_error("RETRIEVAL_FAILED", f"Retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_envelope.model_dump()
        )


@app.post("/retrieve")
async def retrieve_context_legacy(request: QueryRequest):
    """Legacy retrieval endpoint - redirects to v2."""
    # Convert legacy request to new format
    new_request = RetrievalRequestPayload(
        query=request.query,
        context=request.context,
        user_id=request.user_id,
        session_id=request.session_id
    )
    return await retrieve_context_v2(new_request)


@app.post("/v2/answer", response_model=AnswerResponseModel)
async def generate_answer_v2(
    request: AnswerRequestPayload,
    http_request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """Generate answer using hybrid retrieval and LLM composition."""
    start_time = time.perf_counter()
    trace_id = str(uuid.uuid4())

    try:
        logger.info(f"Generating answer for: {request.query[:50]}...", extra={"trace_id": trace_id})

        # Check idempotency cache for duplicate requests
        if idempotency_key and idempotency_key in _idempotency_cache:
            cached_response = _idempotency_cache[idempotency_key]
            logger.info(f"Returning cached answer for idempotency key: {idempotency_key}")
            return AnswerResponseModel(**cached_response)

        # Use engine for complete orchestration
        result = engine.answer(
            query=request.query,
            classification=request.classification,
            model=request.model,
            include_citations=request.citations,
            top_k=request.top_k,
            lane=request.lane
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Update metadata with trace ID
        result.metadata.trace_id = trace_id
        result.metadata.latency_ms = processing_time_ms

        logger.info(f"Generated answer using {result.metadata.model_used} ({processing_time_ms:.1f}ms)")

        await record_audit_event(
            http_request,
            {
                "event": "answer.generated",
                "query_preview": request.query[:120],
                "model": result.metadata.model_used,
                "citation_count": len(result.citations),
            },
        )

        # Cache response if idempotency key provided
        if idempotency_key:
            _idempotency_cache[idempotency_key] = result.model_dump()
            # Simple cache cleanup - keep only last 100 entries
            if len(_idempotency_cache) > 100:
                oldest_key = next(iter(_idempotency_cache))
                del _idempotency_cache[oldest_key]

        return result

    except Exception as e:
        logger.error(f"Answer generation error: {str(e)}", extra={"trace_id": trace_id})
        error_envelope = build_error("ANSWER_GENERATION_FAILED", f"Answer generation failed: {str(e)}", trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_envelope.model_dump()
        )


@app.get("/policies")
async def get_policies():
    """Get current retrieval and workflow policies."""
    try:
        policy_settings = engine.policy_manager.get_policy_settings()

        return {
            "retrieval_policies": policy_settings,
            "policy_metadata": {
                "version": engine.policy_manager.version,
                "last_loaded": engine.policy_manager.last_loaded.isoformat(),
                "hot_reload_enabled": engine.policy_manager.hot_reload
            },
            "prompt_registry_metadata": {
                "version": engine.prompt_registry.version,
                "last_loaded": engine.prompt_registry.last_loaded.isoformat(),
                "hot_reload_enabled": engine.prompt_registry.hot_reload
            }
        }

    except Exception as e:
        logger.error(f"Policy retrieval error: {str(e)}")
        error_envelope = build_error("POLICY_RETRIEVAL_FAILED", f"Policy retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_envelope.model_dump()
        )


@app.post("/v2/orchestrate", response_model=AnswerResponseModel)
async def orchestrate_full_pipeline(
    request: QueryPayload,
    http_request: Request,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """Complete orchestration: classify → retrieve → answer in one call."""
    start_time = time.perf_counter()
    trace_id = str(uuid.uuid4())

    try:
        logger.info(f"Full orchestration for: {request.query[:50]}...", extra={"trace_id": trace_id})

        # Check idempotency cache
        if idempotency_key and idempotency_key in _idempotency_cache:
            cached_response = _idempotency_cache[idempotency_key]
            logger.info(f"Returning cached orchestration for idempotency key: {idempotency_key}")
            return AnswerResponseModel(**cached_response)

        # Full pipeline orchestration
        result = engine.orchestrate(
            query=request.query,
            context=request.context,
            user_id=request.user_id,
            session_id=request.session_id,
            lane=request.lane,
            idempotency_key=idempotency_key,
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Update metadata
        result.metadata.trace_id = trace_id
        result.metadata.latency_ms = processing_time_ms

        logger.info(f"Full orchestration completed ({processing_time_ms:.1f}ms)")

        await record_audit_event(
            http_request,
            {
                "event": "orchestrator.pipeline",
                "query_preview": request.query[:120],
                "classification_present": bool(request.context),
            },
        )

        # Cache if needed
        if idempotency_key:
            _idempotency_cache[idempotency_key] = result.model_dump()

        return result

    except Exception as e:
        logger.error(f"Orchestration error: {str(e)}", extra={"trace_id": trace_id})
        error_envelope = build_error("ORCHESTRATION_FAILED", f"Orchestration failed: {str(e)}", trace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_envelope.model_dump()
        )


# Legacy API support - kept for backward compatibility
@app.post("/answer")
async def generate_answer_legacy(request: QueryRequest):
    """Legacy answer endpoint - redirects to v2 orchestrate."""
    new_request = QueryPayload(
        query=request.query,
        context=request.context,
        user_id=request.user_id,
        session_id=request.session_id
    )
    return await orchestrate_full_pipeline(new_request)


# Diagnostic and management endpoints
@app.get("/diagnostics")
async def get_diagnostics():
    """Get detailed diagnostic information."""
    import datetime

    uptime_seconds = time.perf_counter() - engine._started_at

    return {
        "service": "orchestrator",
        "version": "2.0.0",
        "environment": engine.environment,
        "uptime_seconds": uptime_seconds,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "policy_manager": {
            "version": engine.policy_manager.version,
            "last_loaded": engine.policy_manager.last_loaded.isoformat(),
            "hot_reload": engine.policy_manager.hot_reload
        },
        "prompt_registry": {
            "version": engine.prompt_registry.version,
            "last_loaded": engine.prompt_registry.last_loaded.isoformat(),
            "hot_reload": engine.prompt_registry.hot_reload
        },
        "idempotency_cache_size": len(_idempotency_cache),
        "features_enabled": {
            "hybrid_retrieval": True,
            "answer_composition": True,
            "prompt_registry": True,
            "policy_management": True,
            "idempotency_support": True,
            "error_envelopes": True
        }
    }


@app.post("/admin/reload")
async def reload_configuration(_: UserContext = Depends(require_roles("admin"))):
    """Reload policies and prompt registry (admin endpoint)."""
    try:
        # Force reload of policies and prompts
        engine.policy_manager._load()
        engine.prompt_registry._load()

        return {
            "status": "reloaded",
            "policy_version": engine.policy_manager.version,
            "prompt_version": engine.prompt_registry.version,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Configuration reload failed: {str(e)}")
        error_envelope = build_error("RELOAD_FAILED", f"Configuration reload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_envelope.model_dump()
        )


if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    port_map = {"dev": 8004, "test": 8185, "prod": 8286}
    port = port_map.get(env_name, 8004)

    uvicorn.run(
        "services.orchestrator.api:app",
        host="0.0.0.0",
        port=port,
        reload=env_name == "dev"
    )