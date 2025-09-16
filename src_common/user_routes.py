# src_common/user_routes.py
"""
User UI Routes - Phase 5 Implementation
Extracted routes from app_user.py to be included in main application
LCARS/retro terminal themed user interface
"""

import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

from fastapi import APIRouter, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .ttrpg_logging import get_logger

# Initialize logging
logger = get_logger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Create router
user_router = APIRouter()

# Pydantic models for user interface
class QueryRequest(BaseModel):
    query: str
    use_memory: bool = True
    theme: Optional[str] = "lcars"
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    response: str
    sources: List[Dict[str, Any]]
    session_id: str
    timestamp: float
    processing_time_ms: int

class SessionInfo(BaseModel):
    session_id: str
    created_at: float
    query_count: int
    theme: str
    memory_enabled: bool

# Session management
active_sessions: Dict[str, SessionInfo] = {}

# WebSocket connection manager for user interface
class UserConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"User WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"User WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user WebSocket: {e}")
                self.disconnect(connection)

manager = UserConnectionManager()

# Routes
@user_router.get("/", response_class=HTMLResponse)
async def root_user_interface(request: Request):
    """Root route - redirect to user interface."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui", status_code=302)

@user_router.get("/ui", response_class=HTMLResponse)
async def user_interface(request: Request):
    """Render the main user interface with LCARS/retro terminal theme."""
    try:
        # Generate session ID if not provided
        session_id = str(uuid.uuid4())

        # Create session info
        session_info = SessionInfo(
            session_id=session_id,
            created_at=time.time(),
            query_count=0,
            theme="lcars",
            memory_enabled=True
        )
        active_sessions[session_id] = session_info

        context = {
            "request": request,
            "title": "TTRPG Center - Query Interface",
            "session_id": session_id,
            "environment": os.getenv("APP_ENV", "dev"),
            "version": "0.1.0",
            "timestamp": time.time(),
            "theme": "lcars"
        }
        return templates.TemplateResponse("user/main.html", context)
    except Exception as e:
        logger.error(f"Error rendering user interface: {e}")
        raise HTTPException(status_code=500, detail="Failed to render user interface")

@user_router.get("/ui", response_class=HTMLResponse)
async def user_interface_alt(request: Request):
    """Alternative UI endpoint."""
    return await user_interface(request)

# API endpoints for user queries
@user_router.post("/api/query")
async def process_query(query_request: QueryRequest):
    """Process a user query through the RAG system."""
    try:
        start_time = time.time()

        # Get or create session
        session_id = query_request.session_id or str(uuid.uuid4())
        if session_id not in active_sessions:
            active_sessions[session_id] = SessionInfo(
                session_id=session_id,
                created_at=time.time(),
                query_count=0,
                theme=query_request.theme or "lcars",
                memory_enabled=query_request.use_memory
            )

        session = active_sessions[session_id]
        session.query_count += 1

        # For now, return a mock response until RAG system is fully connected
        # TODO: Integrate with actual RAG system from src_common.orchestrator
        mock_response = f"Query processed: '{query_request.query}'. This is a mock response until the RAG system is fully integrated."
        mock_sources = [
            {
                "title": "Mock Source",
                "content": "Sample content for demonstration",
                "relevance_score": 0.85,
                "source_type": "document"
            }
        ]

        processing_time = int((time.time() - start_time) * 1000)

        response = QueryResponse(
            response=mock_response,
            sources=mock_sources,
            session_id=session_id,
            timestamp=time.time(),
            processing_time_ms=processing_time
        )

        # Broadcast query update to connected WebSocket clients
        await manager.broadcast({
            "type": "query_processed",
            "session_id": session_id,
            "query": query_request.query,
            "timestamp": time.time()
        })

        logger.info(f"Query processed for session {session_id}: {query_request.query[:50]}...")
        return response

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Failed to process query")

@user_router.get("/api/session/{session_id}")
async def get_session_info(session_id: str):
    """Get information about a user session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return active_sessions[session_id]

@user_router.post("/api/session/{session_id}/theme")
async def update_session_theme(session_id: str, theme_data: Dict[str, str]):
    """Update the theme for a user session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    theme = theme_data.get("theme", "lcars")
    if theme not in ["lcars", "terminal", "classic"]:
        raise HTTPException(status_code=400, detail="Invalid theme")

    active_sessions[session_id].theme = theme

    # Broadcast theme update
    await manager.broadcast({
        "type": "theme_updated",
        "session_id": session_id,
        "theme": theme,
        "timestamp": time.time()
    })

    return {"status": "success", "theme": theme}

@user_router.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a user session and its memory."""
    if session_id in active_sessions:
        del active_sessions[session_id]
        logger.info(f"Session cleared: {session_id}")

    return {"status": "session_cleared", "session_id": session_id}

# WebSocket endpoint for user interface real-time updates
@user_router.websocket("/ws/user")
async def user_websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time user interface updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                logger.info(f"Received user WebSocket message: {message.get('type', 'unknown')}")

                # Echo back with server timestamp and user context
                response = {
                    "type": "echo",
                    "data": message,
                    "timestamp": time.time(),
                    "server": "user_interface",
                    "active_sessions": len(active_sessions)
                }
                await manager.send_personal_message(response, websocket)

            except json.JSONDecodeError:
                # Handle plain text messages
                response = {
                    "type": "text_echo",
                    "data": data,
                    "timestamp": time.time(),
                    "server": "user_interface"
                }
                await manager.send_personal_message(response, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"User WebSocket error: {e}")
        manager.disconnect(websocket)

# Utility endpoints for the user interface
@user_router.get("/api/themes")
async def get_available_themes():
    """Get list of available UI themes."""
    return {
        "themes": [
            {
                "id": "lcars",
                "name": "LCARS",
                "description": "Star Trek LCARS-inspired interface"
            },
            {
                "id": "terminal",
                "name": "Retro Terminal",
                "description": "Classic computer terminal aesthetic"
            },
            {
                "id": "classic",
                "name": "Classic",
                "description": "Traditional web interface"
            }
        ],
        "default": "lcars"
    }

@user_router.get("/api/user/health")
async def user_health_check():
    """Health check specific to user interface functionality."""
    return {
        "status": "healthy",
        "environment": os.getenv("APP_ENV", "dev"),
        "active_sessions": len(active_sessions),
        "websocket_connections": len(manager.active_connections),
        "available_themes": ["lcars", "terminal", "classic"],
        "timestamp": time.time()
    }