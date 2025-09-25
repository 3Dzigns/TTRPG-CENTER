"""Pydantic models and type helpers for the orchestrator service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, root_validator


class ErrorDetail(BaseModel):
    """Standard error payload detail."""

    code: str = Field(..., description="Stable application error code")
    message: str = Field(..., description="Human-readable description of the error")
    trace_id: str = Field(default_factory=lambda: uuid4().hex, description="Trace identifier for correlation")


class ErrorEnvelope(BaseModel):
    """Standard error envelope returned by the orchestrator."""

    error: ErrorDetail


class ClassificationModel(BaseModel):
    """Classification result produced by the query classifier."""

    intent: str
    domain: str
    complexity: str
    needs_tools: bool = Field(..., alias="needsTools")
    confidence: float = Field(..., ge=0.0, le=1.0)

    class Config:
        allow_population_by_field_name = True


class QueryPayload(BaseModel):
    """Incoming request body for classification or retrieval."""

    query: str = Field(..., min_length=1, max_length=2000)
    context: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = Field(None, alias="userId")
    session_id: Optional[str] = Field(None, alias="sessionId")
    lane: Optional[str] = Field(None, description="Requested content lane filter (A/B/C/ALL)")

    class Config:
        allow_population_by_field_name = True


class RetrievalRequestPayload(QueryPayload):
    """Request body for retrieval operations when classification is precomputed."""

    classification: Optional[ClassificationModel] = None
    top_k: int = Field(8, alias="topK", ge=1, le=50)
    similarity_threshold: Optional[float] = Field(0.65, alias="similarityThreshold", ge=0.0, le=1.0)

    class Config:
        allow_population_by_field_name = True


class RetrievedChunk(BaseModel):
    """Chunk of content returned from hybrid retrieval."""

    chunk_id: str = Field(..., alias="chunkId")
    content: str
    score: float
    metadata: Dict[str, Any]
    source: str
    rank: int

    class Config:
        allow_population_by_field_name = True


class RetrievalResponseModel(BaseModel):
    """Response payload for retrieval."""

    query: str
    classification: ClassificationModel
    strategy_used: Dict[str, Any] = Field(..., alias="strategyUsed")
    chunks: List[RetrievedChunk]
    total_chunks: int = Field(..., alias="totalChunks")
    processing_time_ms: float = Field(..., alias="processingTimeMs")
    trace_id: str = Field(default_factory=lambda: uuid4().hex, alias="traceId")

    class Config:
        allow_population_by_field_name = True


class AnswerRequestPayload(RetrievalRequestPayload):
    """Request payload for answer generation."""

    model: Optional[str] = None
    citations: bool = Field(True, description="Whether to include formatted citations in the response")


class Citation(BaseModel):
    """Citation entry associated with a response."""

    source: str
    label: str
    passage: Optional[str] = None


class AnswerMetadata(BaseModel):
    """Additional metadata returned alongside an answer."""

    model_used: str = Field(..., alias="modelUsed")
    confidence: float
    latency_ms: float = Field(..., alias="latencyMs")
    provider: Optional[str] = None
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    trace_id: str = Field(default_factory=lambda: uuid4().hex, alias="traceId")

    class Config:
        allow_population_by_field_name = True


class AnswerResponseModel(BaseModel):
    """Complete answer payload returned from the orchestrator."""

    answer: str
    citations: List[Citation]
    retrieved_chunks: List[RetrievedChunk] = Field(..., alias="retrievedChunks")
    metadata: AnswerMetadata

    class Config:
        allow_population_by_field_name = True


class HealthStatus(BaseModel):
    """Health probe payload."""

    status: str
    service: str
    version: str
    environment: str
    uptime_seconds: float = Field(..., alias="uptimeSeconds")
    hot_reload_enabled: bool = Field(..., alias="hotReloadEnabled")
    timestamp: datetime


class PolicySnapshot(BaseModel):
    """Snapshot of policy metadata exposed via diagnostics."""

    retrieval_policy_version: str = Field(..., alias="retrievalPolicyVersion")
    prompt_registry_version: str = Field(..., alias="promptRegistryVersion")
    last_loaded_at: datetime = Field(..., alias="lastLoadedAt")


def build_error(code: str, message: str, trace_id: Optional[str] = None) -> ErrorEnvelope:
    """Helper for constructing a standardised error response."""

    detail = ErrorDetail(code=code, message=message, trace_id=trace_id or uuid4().hex)
    return ErrorEnvelope(error=detail)
