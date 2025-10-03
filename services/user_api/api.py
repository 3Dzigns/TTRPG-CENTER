"""
User API Service

FastAPI service for user-facing query processing and session management.
MVP v2 Microservices Architecture
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Dict, List, Optional

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request, status, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config
from src_common.security import bootstrap_app_security, record_audit_event


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

bootstrap_app_security(app, service_name="user_api")

# Setup cache headers middleware based on environment
config = get_environment_config()
env_name = config.get("environment", "dev")

@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)

    # Apply environment-specific cache headers
    if env_name == "dev":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif env_name == "test":
        response.headers["Cache-Control"] = "public, max-age=5"
    elif env_name == "prod":
        # Allow longer caching in production for static content
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            response.headers["Cache-Control"] = "public, max-age=3600"
        else:
            response.headers["Cache-Control"] = "public, max-age=60"

    return response

# Redis client for session storage
_redis: Optional[redis.Redis] = None

# Local fallback storage for development
_local_sessions: Dict[str, SessionInfo] = {}
_local_plans: Dict[str, PlanResponse] = {}
_local_runs: Dict[str, RunStatus] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup."""
    global _redis

    logger.info("Starting User API Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Initialize Redis connection
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))

    try:
        _redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        await _redis.ping()
        logger.info(f"Redis connection established: {redis_host}:{redis_port}/{redis_db}")
    except Exception as e:
        logger.warning(f"Redis connection failed, using local storage: {e}")
        _redis = None

    # Verify orchestrator service connectivity
    await _verify_orchestrator_connection()


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    # Count active sessions from Redis or local storage
    session_count = 0
    try:
        if _redis:
            session_keys = await _redis.keys("session:*")
            session_count = len(session_keys)
        else:
            session_count = len(_local_sessions)
    except Exception as e:
        logger.warning(f"Failed to count sessions: {e}")

    health_data = {
        "status": "healthy",
        "service": "user_api",
        "version": "2.0.0",
        "environment": os.getenv("TARGET_ENV", "dev"),
        "active_sessions": session_count,
        "redis_connected": _redis is not None
    }

    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content=health_data
    )

    # Apply cache headers based on environment
    _apply_cache_headers(response)
    return response


@app.post("/ask", response_model=AskResponse)
async def ask_query(
    ask_request: AskRequest,
    http_request: Request,
):
    """
    Process user query and return answer.

    Main user-facing endpoint for natural language queries.
    """

    start_time = time.perf_counter()

    try:
        logger.info(f"Processing ask query: {ask_request.query[:50]}...")

        # Get or create session
        session_id = ask_request.session_id or str(uuid.uuid4())
        session = await _get_or_create_session(session_id)

        # Update session activity
        import datetime
        session.last_activity_at = datetime.datetime.utcnow().isoformat()
        session.query_count += 1

        # Call orchestrator v2 service for complete pipeline
        orchestrator_response = await _call_orchestrator_v2(
            ask_request.query,
            session_id,
            ask_request.context or {},
        )

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

        await record_audit_event(
            http_request,
            {
                "event": "user.ask",
                "session_id": session_id,
                "latency_ms": round(processing_time_ms, 2),
                "source_count": len(response.sources),
            },
        )

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


@app.get("/plan", response_model=PlanResponse)
async def create_plan(
    request: str,
    session_id: Optional[str] = None,
    complexity_limit: Optional[str] = "medium"
):
    """
    Generate execution plan for complex request.

    Breaks down multi-step workflows into manageable components.
    """

    try:
        logger.info(f"Creating plan for: {request[:50]}...")

        # Get or create session
        session_id = session_id or str(uuid.uuid4())
        session = await _get_or_create_session(session_id)

        # Generate plan ID
        plan_id = str(uuid.uuid4())

        # Mock plan generation (would integrate with orchestrator for real planning)
        steps = _generate_mock_plan_steps(request, complexity_limit)

        total_duration = sum(step.estimated_duration_seconds for step in steps)

        plan_response = PlanResponse(
            plan_id=plan_id,
            session_id=session_id,
            steps=steps,
            total_estimated_duration_seconds=total_duration,
            complexity=complexity_limit or "medium",
            validated=True
        )

        # Store plan in Redis or local storage
        await _store_plan(plan_response)

        logger.info(f"Created plan {plan_id} with {len(steps)} steps ({total_duration}s)")

        return plan_response

    except Exception as e:
        logger.error(f"Plan creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan creation failed: {str(e)}"
        )


@app.post("/run", response_model=RunStatus)
async def execute_plan(
    run_request: RunRequest,
    http_request: Request,
):
    """
    Execute a validated plan.

    Coordinates workflow execution across multiple services.
    """

    try:
        logger.info(f"Starting plan execution: {run_request.plan_id}")

        # Validate plan exists
        plan = await _get_plan(run_request.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {run_request.plan_id} not found"
            )

        # Validate session
        if run_request.session_id != plan.session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session mismatch for plan execution"
            )

        # Create run execution
        run_id = str(uuid.uuid4())
        import datetime

        run_status = RunStatus(
            run_id=run_id,
            plan_id=run_request.plan_id,
            session_id=run_request.session_id,
            status="queued",
            progress=0.0,
            started_at=datetime.datetime.utcnow().isoformat()
        )

        # Store run status
        await _store_run(run_status)

        # Start execution asynchronously
        if run_request.execute_all:
            asyncio.create_task(_execute_plan_steps(run_id, plan))

        await record_audit_event(
            http_request,
            {
                "event": "user.run",
                "plan_id": run_request.plan_id,
                "run_id": run_id,
                "execute_all": run_request.execute_all,
            },
        )

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

    run_status = await _get_run(run_id)
    if not run_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found"
        )

    return run_status


async def _get_or_create_session(session_id: str) -> SessionInfo:
    """Get existing session or create new one from Redis or local storage."""

    try:
        if _redis:
            # Try to get from Redis
            session_data = await _redis.get(f"session:{session_id}")
            if session_data:
                session_dict = json.loads(session_data)
                return SessionInfo(**session_dict)
        else:
            # Use local storage
            if session_id in _local_sessions:
                return _local_sessions[session_id]

        # Create new session
        import datetime
        now = datetime.datetime.utcnow().isoformat()

        session = SessionInfo(
            session_id=session_id,
            created_at=now,
            last_activity_at=now,
            query_count=0,
            context={}
        )

        # Store in Redis or local storage
        await _store_session(session)
        logger.info(f"Created new session: {session_id}")

        return session

    except Exception as e:
        logger.error(f"Error managing session {session_id}: {e}")
        # Fallback to in-memory session
        import datetime
        return SessionInfo(
            session_id=session_id,
            created_at=datetime.datetime.utcnow().isoformat(),
            last_activity_at=datetime.datetime.utcnow().isoformat(),
            query_count=0,
            context={}
        )


async def _call_orchestrator_v2(query: str, session_id: str, context: Optional[Dict] = None) -> Dict:
    """Call orchestrator v2 service for complete pipeline processing."""

    try:
        # Get orchestrator service URL
        config = get_environment_config()
        env_name = config.get("environment", "dev")

        port_map = {"dev": 8004, "test": 8185, "prod": 8286}
        orchestrator_port = port_map.get(env_name, 8004)
        orchestrator_url = f"http://localhost:{orchestrator_port}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Use the v2 orchestrate endpoint for complete pipeline
            orchestrate_payload = {
                "query": query,
                "userId": session_id,
                "sessionId": session_id,
                "context": context or {},
                "lane": "A"  # Default to Lane A content
            }

            response = await client.post(
                f"{orchestrator_url}/v2/orchestrate",
                json=orchestrate_payload,
                headers={
                    "Content-Type": "application/json",
                    "Idempotency-Key": str(uuid.uuid4())  # For safe retries
                }
            )

            if response.status_code != 200:
                raise Exception(f"Orchestration failed: {response.status_code} - {response.text}")

            orchestration_data = response.json()

            # Extract sources from retrieved chunks
            sources = []
            if "retrievedChunks" in orchestration_data:
                sources = [chunk.get("source", "Unknown") for chunk in orchestration_data["retrievedChunks"]]

            # Extract confidence from metadata
            confidence = 0.8  # Default confidence
            if "metadata" in orchestration_data:
                confidence = orchestration_data["metadata"].get("confidence", 0.8)

            return {
                "answer": orchestration_data.get("answer", "I'm not sure how to answer that."),
                "confidence": confidence,
                "sources": list(set(sources))[:5],  # Deduplicate and limit to 5 sources
                "citations": orchestration_data.get("citations", []),
                "metadata": orchestration_data.get("metadata", {}),
                "classification": None  # Could extract from metadata if needed
            }

    except Exception as e:
        logger.error(f"Orchestrator v2 call failed: {str(e)}")
        # Return fallback response
        return {
            "answer": f"I apologize, but I'm having trouble processing your query right now. Please try again later.",
            "confidence": 0.1,
            "sources": [],
            "citations": [],
            "metadata": {"error": str(e)},
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
        run_status = await _get_run(run_id)
        if not run_status:
            logger.error(f"Run {run_id} not found for execution")
            return

        run_status.status = "running"
        await _store_run(run_status)

        total_steps = len(plan.steps)

        for i, step in enumerate(plan.steps):
            run_status.current_step = step.step_id
            run_status.progress = i / total_steps
            await _store_run(run_status)  # Update progress in storage

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

        await _store_run(run_status)  # Final update
        logger.info(f"Plan execution {run_id} completed successfully")

    except Exception as e:
        logger.error(f"Plan execution {run_id} failed: {str(e)}")

        # Try to update status with error
        try:
            run_status = await _get_run(run_id)
            if run_status:
                run_status.status = "failed"
                run_status.results["error"] = str(e)
                await _store_run(run_status)
        except:
            pass  # Don't fail if we can't update error status


async def _store_session(session: SessionInfo):
    """Store session in Redis or local storage."""
    try:
        if _redis:
            # Store in Redis with TTL based on environment
            config = get_environment_config()
            env_name = config.get("environment", "dev")

            # Environment-specific TTL settings
            ttl_map = {"dev": 3600, "test": 300, "prod": 86400}  # 1hr, 5min, 24hr
            ttl = ttl_map.get(env_name, 3600)

            await _redis.setex(
                f"session:{session.session_id}",
                ttl,
                json.dumps(session.dict())
            )
        else:
            # Store locally
            _local_sessions[session.session_id] = session

    except Exception as e:
        logger.error(f"Failed to store session {session.session_id}: {e}")




def _apply_cache_headers(response: Response):
    """Apply cache headers based on current environment."""
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    if env_name == "dev":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    elif env_name == "test":
        response.headers["Cache-Control"] = "public, max-age=5"
    else:  # prod
        response.headers["Cache-Control"] = "public, max-age=60"


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


async def _store_plan(plan: PlanResponse):
    """Store plan in Redis or local storage."""
    try:
        if _redis:
            await _redis.setex(
                f"plan:{plan.plan_id}",
                3600,  # 1 hour TTL
                json.dumps(plan.dict())
            )
        else:
            _local_plans[plan.plan_id] = plan
    except Exception as e:
        logger.error(f"Failed to store plan {plan.plan_id}: {e}")


async def _store_run(run_status: RunStatus):
    """Store run status in Redis or local storage."""
    try:
        if _redis:
            await _redis.setex(
                f"run:{run_status.run_id}",
                7200,  # 2 hour TTL
                json.dumps(run_status.dict())
            )
        else:
            _local_runs[run_status.run_id] = run_status
    except Exception as e:
        logger.error(f"Failed to store run {run_status.run_id}: {e}")


async def _get_plan(plan_id: str) -> Optional[PlanResponse]:
    """Get plan from Redis or local storage."""
    try:
        if _redis:
            plan_data = await _redis.get(f"plan:{plan_id}")
            if plan_data:
                return PlanResponse(**json.loads(plan_data))
        else:
            return _local_plans.get(plan_id)
    except Exception as e:
        logger.error(f"Failed to get plan {plan_id}: {e}")
    return None


async def _get_run(run_id: str) -> Optional[RunStatus]:
    """Get run status from Redis or local storage."""
    try:
        if _redis:
            run_data = await _redis.get(f"run:{run_id}")
            if run_data:
                return RunStatus(**json.loads(run_data))
        else:
            return _local_runs.get(run_id)
    except Exception as e:
        logger.error(f"Failed to get run {run_id}: {e}")
    return None


if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    env_name = config.get("environment", "dev")

    port_map = {"dev": 8002, "test": 8181, "prod": 8284}
    port = port_map.get(env_name, 8002)

    uvicorn.run(
        "services.user_api.api:app",
        host="0.0.0.0",
        port=port,
        reload=env_name == "dev"
    )
