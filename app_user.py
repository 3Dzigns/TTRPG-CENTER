# app_user.py
"""
Phase 5: User UI FastAPI Application
TTRPG Center User Interface with retro terminal/LCARS theming

Provides:
- US-501: Themed interface with LCARS/retro terminal design
- US-502: Text response area with markdown support
- US-503: Image response slot (future-ready)
- US-504: Session memory management
- US-505: User memory persistence
- US-507: Cache-respecting queries with fast retest
"""

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import Phase 2 RAG functionality
from src_common.ttrpg_logging import get_logger

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - User UI",
    description="Phase 5 User Interface with retro terminal/LCARS theming",
    version="5.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates and static files
templates = Jinja2Templates(directory="templates/user")
app.mount("/static", StaticFiles(directory="static/user"), name="static")

# In-memory stores (would be replaced with proper database in production)
session_store: Dict[str, Dict[str, Any]] = {}
user_store: Dict[str, Dict[str, Any]] = {}


# Pydantic Models
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    memory_mode: str = "session"  # session, user, party
    theme: str = "lcars"  # lcars, terminal, classic


class QueryResponse(BaseModel):
    answer: str
    metadata: Dict[str, Any]
    image_url: Optional[str] = None
    session_id: str
    timestamp: float
    cached: bool = False


class SessionMemory(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    created_at: float
    updated_at: float


class UserPreferences(BaseModel):
    user_id: str
    theme: str = "lcars"
    memory_enabled: bool = True
    preferred_sources: List[str] = []
    tone: str = "helpful"
    created_at: float
    updated_at: float


# Memory Management
class MemoryManager:
    """Manage session and user memory"""
    
    def __init__(self):
        self.sessions = session_store
        self.users = user_store
    
    def get_session_memory(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages from session memory"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "messages": [],
                "created_at": time.time(),
                "updated_at": time.time()
            }
        return self.sessions[session_id]["messages"]
    
    def add_to_session_memory(self, session_id: str, query: str, response: str):
        """Add query/response pair to session memory"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "messages": [],
                "created_at": time.time(),
                "updated_at": time.time()
            }
        
        self.sessions[session_id]["messages"].append({
            "timestamp": time.time(),
            "query": query,
            "response": response,
            "type": "qa_pair"
        })
        self.sessions[session_id]["updated_at"] = time.time()
    
    def clear_session_memory(self, session_id: str):
        """Clear session memory"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get user preferences"""
        if user_id not in self.users:
            self.users[user_id] = UserPreferences(
                user_id=user_id,
                created_at=time.time(),
                updated_at=time.time()
            ).__dict__
        
        return UserPreferences(**self.users[user_id])
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """Update user preferences"""
        if user_id not in self.users:
            self.users[user_id] = UserPreferences(
                user_id=user_id,
                created_at=time.time(),
                updated_at=time.time()
            ).__dict__
        
        self.users[user_id].update(preferences)
        self.users[user_id]["updated_at"] = time.time()


# Cache Policy Manager
class CachePolicyManager:
    """Manage cache policies per environment (from Phase 0)"""
    
    def __init__(self):
        self.environment = "dev"  # Default, should be from env var
    
    def get_cache_headers(self, request_path: str) -> Dict[str, str]:
        """Get appropriate cache headers based on environment"""
        if self.environment == "dev":
            return {
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        elif self.environment == "test":
            return {
                "Cache-Control": "max-age=5, must-revalidate"
            }
        else:  # prod
            return {
                "Cache-Control": "max-age=300, must-revalidate"
            }


# Initialize managers
memory_manager = MemoryManager()
cache_manager = CachePolicyManager()


# Mock RAG function (would integrate with Phase 2)
async def mock_rag_query(query: str, context: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mock RAG query - would integrate with actual Phase 2 implementation"""
    await asyncio.sleep(0.5)  # Simulate processing time
    
    return {
        "answer": f"This is a mock answer for: {query}",
        "metadata": {
            "model": "mock-model",
            "tokens": 42,
            "processing_time_ms": 500,
            "intent": "question",
            "domain": "general"
        },
        "retrieved_chunks": [
            {"source": "Mock Source", "score": 0.95, "text": "Mock retrieved text..."}
        ],
        "image_url": None  # Future multimodal support
    }


# WebSocket for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:  # Copy to avoid modification during iteration
            try:
                await connection.send_json(message)
            except:
                self.disconnect(connection)


manager = ConnectionManager()


# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "user-ui",
        "timestamp": time.time(),
        "phase": "5"
    }


@app.get("/", response_class=HTMLResponse)
async def user_interface(request: Request):
    """Main user interface page"""
    try:
        # Generate default session ID
        session_id = str(uuid.uuid4())
        
        return templates.TemplateResponse("main.html", {
            "request": request,
            "session_id": session_id,
            "title": "TTRPG Center",
            "version": "Phase 5"
        })
    except Exception as e:
        logger.error(f"Error loading user interface: {e}")
        raise HTTPException(status_code=500, detail="Error loading interface")


@app.post("/api/query", response_model=QueryResponse)
async def process_query(query_request: QueryRequest):
    """Process user query with memory and caching"""
    try:
        start_time = time.time()
        
        # Generate session ID if not provided
        session_id = query_request.session_id or str(uuid.uuid4())
        
        # Get context from memory if applicable
        context = []
        if query_request.memory_mode == "session":
            context = memory_manager.get_session_memory(session_id)
        elif query_request.memory_mode == "user" and query_request.user_id:
            # Would integrate with user memory in production
            pass
        
        # Process query (integrate with Phase 2 RAG)
        rag_result = await mock_rag_query(query_request.query, context)
        
        # Create response
        response = QueryResponse(
            answer=rag_result["answer"],
            metadata=rag_result["metadata"],
            image_url=rag_result.get("image_url"),
            session_id=session_id,
            timestamp=time.time(),
            cached=False  # Would check cache in production
        )
        
        # Store in memory if session mode
        if query_request.memory_mode == "session":
            memory_manager.add_to_session_memory(
                session_id, 
                query_request.query, 
                response.answer
            )
        
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "query_response",
            "session_id": session_id,
            "query": query_request.query,
            "response": response.answer,
            "timestamp": response.timestamp
        })
        
        processing_time = (time.time() - start_time) * 1000
        logger.info(f"Query processed in {processing_time:.2f}ms for session {session_id}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {e}")


@app.get("/api/session/{session_id}/memory")
async def get_session_memory(session_id: str):
    """Get session memory"""
    try:
        messages = memory_manager.get_session_memory(session_id)
        return {
            "session_id": session_id,
            "messages": messages,
            "count": len(messages)
        }
    except Exception as e:
        logger.error(f"Error retrieving session memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session memory")


@app.delete("/api/session/{session_id}/memory")
async def clear_session_memory(session_id: str):
    """Clear session memory"""
    try:
        memory_manager.clear_session_memory(session_id)
        return {"success": True, "message": f"Memory cleared for session {session_id}"}
    except Exception as e:
        logger.error(f"Error clearing session memory: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear session memory")


@app.get("/api/user/{user_id}/preferences")
async def get_user_preferences(user_id: str):
    """Get user preferences"""
    try:
        preferences = memory_manager.get_user_preferences(user_id)
        return preferences
    except Exception as e:
        logger.error(f"Error retrieving user preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user preferences")


@app.put("/api/user/{user_id}/preferences")
async def update_user_preferences(user_id: str, preferences: Dict[str, Any]):
    """Update user preferences"""
    try:
        memory_manager.update_user_preferences(user_id, preferences)
        return {"success": True, "message": "Preferences updated"}
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user preferences")


@app.get("/api/themes")
async def get_available_themes():
    """Get available UI themes"""
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
                "description": "Classic terminal interface"
            },
            {
                "id": "classic",
                "name": "Classic",
                "description": "Clean modern interface"
            }
        ]
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Echo back with session info
            await websocket.send_json({
                "type": "echo",
                "session_id": session_id,
                "message": message,
                "timestamp": time.time()
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Cache control middleware
@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    """Add cache control headers based on environment"""
    response = await call_next(request)
    
    # Add cache headers
    cache_headers = cache_manager.get_cache_headers(request.url.path)
    for header, value in cache_headers.items():
        response.headers[header] = value
    
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)