"""
Orchestrator Service API

FastAPI service for query classification, retrieval, and orchestration.
MVP v2 Microservices Architecture
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config
from .classifier import Classification, QueryClassifier


logger = get_logger(__name__)


class QueryRequest(BaseModel):
    """Query processing request."""

    query: str = Field(..., min_length=1, max_length=1000)
    context: Optional[Dict[str, str]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class ClassificationResponse(BaseModel):
    """Query classification response."""

    classification: Classification
    processing_time_ms: float
    timestamp: str


class RetrievalRequest(BaseModel):
    """Retrieval request with classification."""

    query: str
    classification: Classification
    top_k: Optional[int] = Field(8, ge=1, le=50)
    similarity_threshold: Optional[float] = Field(0.7, ge=0.0, le=1.0)


class RetrievalChunk(BaseModel):
    """Individual retrieved content chunk."""

    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, str]
    source: str


class RetrievalResponse(BaseModel):
    """Retrieval results response."""

    chunks: List[RetrievalChunk]
    total_chunks: int
    strategy_used: str
    processing_time_ms: float


class AnswerRequest(BaseModel):
    """Answer generation request."""

    query: str
    context_chunks: List[RetrievalChunk]
    classification: Classification
    model: Optional[str] = None


class AnswerResponse(BaseModel):
    """Generated answer response."""

    answer: str
    confidence: float
    sources_used: List[str]
    model_used: str
    processing_time_ms: float


# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Orchestrator Service",
    description="Query classification, retrieval, and orchestration",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Initialize classifier
classifier = QueryClassifier()


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting Orchestrator Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Load policies and prompt templates
    # TODO: Implement policy and prompt loading from config files


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "orchestrator",
            "version": "2.0.0",
            "environment": os.getenv("TARGET_ENV", "dev"),
            "classifier_ready": True
        }
    )


@app.post("/classify", response_model=ClassificationResponse)
async def classify_query(request: QueryRequest):
    """Classify query intent, domain, and complexity."""

    start_time = time.perf_counter()

    try:
        logger.info(f"Classifying query: {request.query[:50]}...")

        # Perform classification
        classification = classifier.classify_query(request.query)

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}"
        )


@app.post("/retrieve", response_model=RetrievalResponse)
async def retrieve_context(request: RetrievalRequest):
    """Execute retrieval strategy based on classification."""

    start_time = time.perf_counter()

    try:
        logger.info(f"Retrieving context for: {request.query[:50]}...")

        # Select retrieval strategy based on classification
        strategy = _select_retrieval_strategy(request.classification)
        logger.info(f"Using retrieval strategy: {strategy}")

        # Mock retrieval for now (would integrate with vector store, graph, etc.)
        chunks = _mock_retrieve_chunks(
            request.query,
            request.classification,
            request.top_k,
            request.similarity_threshold
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        response = RetrievalResponse(
            chunks=chunks,
            total_chunks=len(chunks),
            strategy_used=strategy,
            processing_time_ms=processing_time_ms
        )

        logger.info(f"Retrieved {len(chunks)} chunks using {strategy} ({processing_time_ms:.1f}ms)")

        return response

    except Exception as e:
        logger.error(f"Retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {str(e)}"
        )


@app.post("/answer", response_model=AnswerResponse)
async def generate_answer(request: AnswerRequest):
    """Generate answer using context and classification."""

    start_time = time.perf_counter()

    try:
        logger.info(f"Generating answer for: {request.query[:50]}...")

        # Select model based on classification
        model = _select_model(request.classification, request.model)
        logger.info(f"Using model: {model}")

        # Mock answer generation (would integrate with OpenAI/Claude APIs)
        answer = _mock_generate_answer(
            request.query,
            request.context_chunks,
            request.classification,
            model
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        response = AnswerResponse(
            answer=answer,
            confidence=0.85,  # Mock confidence
            sources_used=[chunk.source for chunk in request.context_chunks[:3]],
            model_used=model,
            processing_time_ms=processing_time_ms
        )

        logger.info(f"Generated answer using {model} ({processing_time_ms:.1f}ms)")

        return response

    except Exception as e:
        logger.error(f"Answer generation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Answer generation failed: {str(e)}"
        )


@app.get("/policies")
async def get_policies():
    """Get current retrieval and workflow policies."""

    try:
        # Load policies from config files
        # TODO: Implement policy loading from YAML files

        policies = {
            "retrieval_policies": {
                "fact_lookup": {
                    "strategy": "vector_similarity",
                    "top_k": 5,
                    "similarity_threshold": 0.8
                },
                "procedural_howto": {
                    "strategy": "hybrid",
                    "top_k": 8,
                    "vector_weight": 0.6,
                    "metadata_weight": 0.4
                }
            },
            "workflow_policies": {
                "passes": {
                    "pass_b": {
                        "split_threshold_mb": 10
                    }
                }
            },
            "model_policies": {
                "classification": "gpt-4",
                "simple_queries": "gpt-3.5-turbo",
                "complex_queries": "gpt-4"
            }
        }

        return policies

    except Exception as e:
        logger.error(f"Policy retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Policy retrieval failed: {str(e)}"
        )


def _select_retrieval_strategy(classification: Classification) -> str:
    """Select retrieval strategy based on classification."""

    strategy_map = {
        'fact_lookup': 'vector_similarity',
        'procedural_howto': 'hybrid',
        'creative_write': 'diverse_sampling',
        'code_help': 'semantic_search',
        'summarize': 'comprehensive',
        'multi_hop_reasoning': 'graph_traversal'
    }

    return strategy_map.get(classification['intent'], 'hybrid')


def _select_model(classification: Classification, requested_model: Optional[str]) -> str:
    """Select model based on classification and request."""

    if requested_model:
        return requested_model

    # Model selection based on complexity and intent
    if classification['complexity'] == 'high' or classification['intent'] == 'multi_hop_reasoning':
        return 'gpt-4'
    elif classification['intent'] == 'code_help':
        return 'gpt-4'
    else:
        return 'gpt-3.5-turbo'


def _mock_retrieve_chunks(
    query: str,
    classification: Classification,
    top_k: int,
    similarity_threshold: float
) -> List[RetrievalChunk]:
    """Mock chunk retrieval (placeholder for real implementation)."""

    # Generate mock chunks based on classification
    chunks = []

    if classification['domain'] == 'ttrpg_rules':
        chunks = [
            RetrievalChunk(
                chunk_id="chunk_001",
                content="Combat mechanics: Initiative is rolled using 1d20 + Dexterity modifier...",
                score=0.92,
                metadata={"source": "PHB", "page": "189", "section": "Combat"},
                source="Player's Handbook p.189"
            ),
            RetrievalChunk(
                chunk_id="chunk_002",
                content="Armor Class (AC) represents how difficult it is to land an effective blow...",
                score=0.88,
                metadata={"source": "PHB", "page": "14", "section": "Armor Class"},
                source="Player's Handbook p.14"
            )
        ]
    elif classification['domain'] == 'ttrpg_lore':
        chunks = [
            RetrievalChunk(
                chunk_id="chunk_lore_001",
                content="The ancient kingdom of Eldoria was founded by the dragon riders...",
                score=0.85,
                metadata={"source": "Campaign Guide", "chapter": "History", "region": "Eldoria"},
                source="Campaign Guide - Eldoria History"
            )
        ]

    return chunks[:top_k]


def _mock_generate_answer(
    query: str,
    context_chunks: List[RetrievalChunk],
    classification: Classification,
    model: str
) -> str:
    """Mock answer generation (placeholder for real implementation)."""

    # Generate mock answer based on classification and context
    if classification['intent'] == 'fact_lookup':
        return f"Based on the game rules, {query.lower()} refers to a specific game mechanic. " \
               f"According to the sources, this involves rolling dice and applying modifiers as specified."

    elif classification['intent'] == 'procedural_howto':
        return f"Here's how to {query.lower()}: \n" \
               f"1. First, determine the relevant ability score\n" \
               f"2. Roll 1d20 and add your modifier\n" \
               f"3. Compare the result to the target number\n" \
               f"This process is detailed in the referenced rulebooks."

    else:
        return f"Regarding {query}, the available information suggests that this topic is covered " \
               f"in the retrieved sources. The specific details depend on your campaign setting and " \
               f"the rules system you're using."


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