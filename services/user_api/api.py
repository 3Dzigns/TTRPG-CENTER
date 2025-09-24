"""
User API Service

FastAPI service for user-facing query processing and session management.
MVP v2 Microservices Architecture
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config


logger = get_logger(__name__)


class AskRequest(BaseModel):
    """Ask endpoint request."""

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    stream: bool = Field(False, description="Whether to stream the response")
    context: Optional[Dict[str, str]] = None


class AskResponse(BaseModel):
    """Ask endpoint response."""

    answer: str
    session_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: List[str]
    processing_time_ms: float
    classification: Optional[Dict] = None


class PlanRequest(BaseModel):
    """Plan endpoint request."""

    request: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    complexity_limit: Optional[str] = Field("medium", description="low, medium, or high")


class PlanStep(BaseModel):
    """Individual plan step."""

    step_id: str
    description: str
    estimated_duration_seconds: int
    dependencies: List[str]
    resources_required: List[str]


class PlanResponse(BaseModel):
    """Plan endpoint response."""

    plan_id: str
    session_id: str
    steps: List[PlanStep]
    total_estimated_duration_seconds: int
    complexity: str
    validated: bool


class RunRequest(BaseModel):
    """Run endpoint request."""

    plan_id: str
    session_id: str
    execute_all: bool = Field(True, description="Execute all steps or just validate")


class RunStatus(BaseModel):
    """Run execution status."""

    run_id: str
    plan_id: str
    session_id: str
    status: str  # queued, running, completed, failed, cancelled
    current_step: Optional[str] = None
    progress: float = Field(ge=0.0, le=1.0)
    results: Dict = Field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SessionInfo(BaseModel):
    """Session information."""

    session_id: str
    created_at: str
    last_activity_at: str
    query_count: int
    context: Dict[str, str]


# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - User API",
    description="User-facing query processing and session management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global storage (in production, this would be Redis/database)
_sessions: Dict[str, SessionInfo] = {}
_plans: Dict[str, PlanResponse] = {}
_runs: Dict[str, RunStatus] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    logger.info("Starting User API Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Verify orchestrator service connectivity
    await _verify_orchestrator_connection()


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "user_api",
            "version": "2.0.0",
            "environment": os.getenv("TARGET_ENV", "dev"),
            "active_sessions": len(_sessions)
        }
    )


@app.post("/ask", response_model=AskResponse)
async def ask_query(request: AskRequest):
    """
    Process user query and return answer.

    Main user-facing endpoint for natural language queries.
    """

    start_time = time.perf_counter()

    try:
        logger.info(f"Processing ask query: {request.query[:50]}...")

        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        session = await _get_or_create_session(session_id)

        # Update session activity
        import datetime
        session.last_activity_at = datetime.datetime.utcnow().isoformat()
        session.query_count += 1

        # Call orchestrator service for classification and processing
        orchestrator_response = await _call_orchestrator(request.query, session_id)

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        response = AskResponse(
            answer=orchestrator_response.get("answer", "I'm not sure how to answer that."),
            session_id=session_id,
            confidence=orchestrator_response.get("confidence", 0.5),
            sources=orchestrator_response.get("sources", []),
            processing_time_ms=processing_time_ms,
            classification=orchestrator_response.get("classification")
        )

        logger.info(f"Ask query completed in {processing_time_ms:.1f}ms")

        return response

    except Exception as e:
        logger.error(f"Ask query error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@app.post("/ask/stream")
async def ask_query_stream(request: AskRequest):
    """Stream response for long-running queries."""

    try:
        logger.info(f"Streaming ask query: {request.query[:50]}...")

        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        session = await _get_or_create_session(session_id)

        async def generate_response():
            """Generate streaming response."""

            yield f"data: {{'status': 'processing', 'session_id': '{session_id}'}}\n\n"

            # Simulate progressive response
            response_parts = [
                "Let me think about that...",
                "Searching for relevant information...",
                "Found some relevant sources...",
                "Generating comprehensive answer...",
                "Here's what I found: This is a mock streaming response for demonstration."
            ]

            for i, part in enumerate(response_parts):
                import json
                yield f"data: {json.dumps({'chunk': part, 'progress': (i+1)/len(response_parts)})}\n\n"
                await asyncio.sleep(1)

            # Final response
            final_response = {
                "status": "completed",
                "session_id": session_id,
                "answer": "This is the complete streamed response.",
                "confidence": 0.85,
                "sources": ["Mock Source 1", "Mock Source 2"]
            }
            yield f"data: {json.dumps(final_response)}\n\n"

        return StreamingResponse(
            generate_response(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )

    except Exception as e:
        logger.error(f"Streaming ask error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming failed: {str(e)}"
        )


@app.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest):
    """
    Generate execution plan for complex request.

    Breaks down multi-step workflows into manageable components.
    """

    try:
        logger.info(f"Creating plan for: {request.request[:50]}...")

        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())
        session = await _get_or_create_session(session_id)

        # Generate plan ID
        plan_id = str(uuid.uuid4())

        # Mock plan generation (would integrate with orchestrator for real planning)
        steps = _generate_mock_plan_steps(request.request, request.complexity_limit)

        total_duration = sum(step.estimated_duration_seconds for step in steps)

        plan_response = PlanResponse(
            plan_id=plan_id,
            session_id=session_id,
            steps=steps,
            total_estimated_duration_seconds=total_duration,
            complexity=request.complexity_limit or "medium",
            validated=True
        )

        _plans[plan_id] = plan_response

        logger.info(f"Created plan {plan_id} with {len(steps)} steps ({total_duration}s)")

        return plan_response

    except Exception as e:
        logger.error(f"Plan creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan creation failed: {str(e)}"
        )


@app.post("/run", response_model=RunStatus)
async def execute_plan(request: RunRequest):
    """
    Execute a validated plan.

    Coordinates workflow execution across multiple services.
    """

    try:
        logger.info(f"Starting plan execution: {request.plan_id}")

        # Validate plan exists
        if request.plan_id not in _plans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {request.plan_id} not found"
            )

        plan = _plans[request.plan_id]

        # Validate session
        if request.session_id != plan.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session mismatch for plan execution"
            )

        # Create run execution
        run_id = str(uuid.uuid4())
        import datetime

        run_status = RunStatus(
            run_id=run_id,
            plan_id=request.plan_id,
            session_id=request.session_id,
            status="queued",
            progress=0.0,
            started_at=datetime.datetime.utcnow().isoformat()
        )

        _runs[run_id] = run_status

        # Start execution asynchronously
        if request.execute_all:
            asyncio.create_task(_execute_plan_steps(run_id, plan))

        return run_status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plan execution error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan execution failed: {str(e)}"
        )


@app.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """Get session information."""

    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    return _sessions[session_id]


@app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear session data."""

    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    del _sessions[session_id]
    logger.info(f"Cleared session {session_id}")

    return {"message": f"Session {session_id} cleared", "session_id": session_id}


@app.get("/runs/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str):
    """Get execution run status."""

    if run_id not in _runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )

    return _runs[run_id]


async def _get_or_create_session(session_id: str) -> SessionInfo:
    """Get existing session or create new one."""

    if session_id in _sessions:
        return _sessions[session_id]

    import datetime
    now = datetime.datetime.utcnow().isoformat()

    session = SessionInfo(
        session_id=session_id,
        created_at=now,
        last_activity_at=now,
        query_count=0,
        context={}
    )

    _sessions[session_id] = session
    logger.info(f"Created new session: {session_id}")

    return session


async def _call_orchestrator(query: str, session_id: str) -> Dict:
    """Call orchestrator service for query processing."""

    try:
        # Get orchestrator service URL
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        port_map = {"dev": 8004, "test": 8185, "prod": 8286}
        orchestrator_port = port_map.get(env_name, 8004)

        orchestrator_url = f"http://localhost:{orchestrator_port}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, classify the query
            classify_response = await client.post(
                f"{orchestrator_url}/classify",
                json={"query": query, "session_id": session_id}
            )

            if classify_response.status_code != 200:
                raise Exception(f"Classification failed: {classify_response.text}")

            classification_data = classify_response.json()
            classification = classification_data["classification"]

            # Then retrieve context
            retrieve_response = await client.post(
                f"{orchestrator_url}/retrieve",
                json={
                    "query": query,
                    "classification": classification,
                    "top_k": 8
                }
            )

            if retrieve_response.status_code != 200:
                raise Exception(f"Retrieval failed: {retrieve_response.text}")

            retrieval_data = retrieve_response.json()

            # Finally, generate answer
            answer_response = await client.post(
                f"{orchestrator_url}/answer",
                json={
                    "query": query,
                    "context_chunks": retrieval_data["chunks"],
                    "classification": classification
                }
            )

            if answer_response.status_code != 200:
                raise Exception(f"Answer generation failed: {answer_response.text}")

            answer_data = answer_response.json()

            return {
                "answer": answer_data["answer"],
                "confidence": answer_data["confidence"],
                "sources": answer_data["sources_used"],
                "classification": classification
            }

    except Exception as e:
        logger.error(f"Orchestrator call failed: {str(e)}")
        # Return fallback response
        return {
            "answer": f"I apologize, but I'm having trouble processing your query right now. Error: {str(e)}",
            "confidence": 0.1,
            "sources": [],
            "classification": None
        }


def _generate_mock_plan_steps(request: str, complexity: str) -> List[PlanStep]:
    """Generate mock plan steps based on request."""

    if "character" in request.lower():
        return [
            PlanStep(
                step_id="step_001",
                description="Determine character concept and background",
                estimated_duration_seconds=300,
                dependencies=[],
                resources_required=["PHB", "background tables"]
            ),
            PlanStep(
                step_id="step_002",
                description="Assign ability scores using point buy",
                estimated_duration_seconds=180,
                dependencies=["step_001"],
                resources_required=["PHB", "point buy calculator"]
            ),
            PlanStep(
                step_id="step_003",
                description="Select race and apply racial bonuses",
                estimated_duration_seconds=120,
                dependencies=["step_002"],
                resources_required=["PHB", "race descriptions"]
            ),
            PlanStep(
                step_id="step_004",
                description="Choose class and starting equipment",
                estimated_duration_seconds=240,
                dependencies=["step_003"],
                resources_required=["PHB", "class descriptions"]
            )
        ]
    else:
        return [
            PlanStep(
                step_id="step_001",
                description="Research and analyze the request",
                estimated_duration_seconds=180,
                dependencies=[],
                resources_required=["knowledge base"]
            ),
            PlanStep(
                step_id="step_002",
                description="Generate comprehensive response",
                estimated_duration_seconds=120,
                dependencies=["step_001"],
                resources_required=["AI models", "templates"]
            )
        ]


async def _execute_plan_steps(run_id: str, plan: PlanResponse):
    """Execute plan steps asynchronously."""

    try:
        run_status = _runs[run_id]
        run_status.status = "running"

        total_steps = len(plan.steps)

        for i, step in enumerate(plan.steps):
            run_status.current_step = step.step_id
            run_status.progress = i / total_steps

            logger.info(f"Executing step {step.step_id}: {step.description}")

            # Simulate step execution
            await asyncio.sleep(step.estimated_duration_seconds / 10)  # Speed up for demo

            # Store step result
            run_status.results[step.step_id] = {
                "status": "completed",
                "output": f"Mock output for {step.description}"
            }

        # Complete execution
        import datetime
        run_status.status = "completed"
        run_status.progress = 1.0
        run_status.current_step = None
        run_status.completed_at = datetime.datetime.utcnow().isoformat()

        logger.info(f"Plan execution {run_id} completed successfully")

    except Exception as e:
        logger.error(f"Plan execution {run_id} failed: {str(e)}")
        run_status.status = "failed"
        run_status.results["error"] = str(e)


async def _verify_orchestrator_connection():
    """Verify orchestrator service is available."""

    try:
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        port_map = {"dev": 8004, "test": 8185, "prod": 8286}
        orchestrator_port = port_map.get(env_name, 8004)

        orchestrator_url = f"http://localhost:{orchestrator_port}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{orchestrator_url}/healthz")
            if response.status_code == 200:
                logger.info("Orchestrator service connection verified")
            else:
                logger.warning(f"Orchestrator service unhealthy: {response.status_code}")

    except Exception as e:
        logger.warning(f"Could not connect to orchestrator service: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    port_map = {"dev": 8002, "test": 8183, "prod": 8284}
    port = port_map.get(env_name, 8002)

    uvicorn.run(
        "services.user_api.api:app",
        host="0.0.0.0",
        port=port,
        reload=env_name == "dev"
    )