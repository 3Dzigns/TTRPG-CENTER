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
import os
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
from src_common.cors_security import (
    setup_secure_cors,
    validate_cors_startup,
    get_cors_health_status,
)
from src_common.tls_security import (
    create_app_with_tls,
    validate_tls_startup,
    get_tls_health_status,
    run_with_tls,
)
# OAuth integration
from src_common.oauth_endpoints import oauth_router
# Authentication
from src_common.auth_models import AuthUser
from src_common.auth_database import auth_db
from src_common.jwt_service import auth_service
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - User UI",
    description="Phase 5 User Interface with retro terminal/LCARS theming",
    version="5.0.0"
)

# Security configuration - FR-SEC-402 & FR-SEC-403
try:
    # Validate security configurations on startup
    validate_cors_startup()
    validate_tls_startup()
    
    # Setup secure CORS instead of wildcard configuration
    setup_secure_cors(app)
    
    logger.info("Security configuration initialized successfully")
except Exception as e:
    logger.error(f"Security configuration failed: {e}")
    if os.getenv("ENVIRONMENT") == "prod":
        raise  # Fail hard in production
    else:
        logger.warning("Continuing with basic CORS for development")
        # Fallback CORS for development only
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Requested-With"]
        )

# Include OAuth router
app.include_router(oauth_router)

# Direct OAuth test endpoint for debugging
@app.get("/test-oauth-redirect")
async def test_oauth_redirect():
    """Test direct OAuth redirect without router"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="https://google.com", status_code=302)

# Authentication setup
bearer_scheme = HTTPBearer(auto_error=False)

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


# Real RAG function using existing infrastructure
async def real_rag_query(query: str, context: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Real RAG query using AstraDB and OpenAI"""
    try:
        # Load environment for AstraDB and OpenAI
        from pathlib import Path
        from dotenv import load_dotenv
        
        # Load environment variables
        env_file = Path("env/dev/config/.env")
        if env_file.exists():
            load_dotenv(env_file)
        
        # Import the existing RAG infrastructure
        from fastapi.testclient import TestClient
        from src_common.app import app as rag_app
        
        start_time = time.time()
        
        # Use the existing RAG endpoint
        with TestClient(rag_app) as client:
            response = client.post("/rag/ask", json={"query": query})
            
            if response.status_code == 200:
                data = response.json()
                processing_time = (time.time() - start_time) * 1000
                
                # Import RAG script functions for OpenAI integration
                import sys
                sys.path.append(str(Path(__file__).parent / "scripts"))
                
                from scripts.rag_openai import openai_chat
                from src_common.orchestrator.prompts import load_prompt, render_prompt
                
                cls = data.get("classification", {})
                chunks = data.get("retrieved", [])
                model_cfg = data.get("model", {"model": "gpt-4o-mini", "max_tokens": 3000, "temperature": 0.2})
                
                if chunks:
                    # Build prompt using existing infrastructure
                    tmpl = load_prompt(cls.get("intent", "question"), cls.get("domain", "general"))
                    system_prompt = render_prompt(
                        tmpl,
                        {
                            "TASK_BRIEF": query,
                            "STYLE": "concise, cite sources in [id] format",
                            "POLICY_SNIPPET": "Use only the provided context. If insufficient, say so. Include citations [id] for each claim.",
                        },
                    )
                    
                    # Assemble context from retrieved chunks
                    context_lines = []
                    for i, c in enumerate(chunks, 1):
                        snippet = (c.get("text") or "")[:1500]  # Truncate long snippets
                        if len(c.get("text", "")) > 1500:
                            snippet += "…"
                        context_lines.append(f"[{i}] {snippet}\nSource: {c.get('source')}")
                    
                    user_prompt = f"Context:\n\n" + "\n\n".join(context_lines) + f"\n\nQuestion: {query}\nAnswer concisely with [n] citations."
                    
                    # Call OpenAI
                    api_key = os.getenv("OPENAI_API_KEY")
                    if not api_key:
                        raise RuntimeError("OPENAI_API_KEY not set in environment")
                    
                    answer = openai_chat(model_cfg["model"], system_prompt, user_prompt, api_key)
                    
                    return {
                        "answer": answer,
                        "metadata": {
                            "model": model_cfg["model"],
                            "tokens": model_cfg.get("max_tokens", 3000),
                            "processing_time_ms": processing_time,
                            "intent": cls.get("intent", "question"),
                            "domain": cls.get("domain", "general")
                        },
                        "retrieved_chunks": [
                            {"source": c.get("source"), "score": c.get("score", 0.0), "text": c.get("text", "")}
                            for c in chunks
                        ],
                        "image_url": None  # Future multimodal support
                    }
                else:
                    # No chunks retrieved
                    return {
                        "answer": "I couldn't find relevant information in the knowledge base to answer your question. Please try rephrasing or asking about a different topic.",
                        "metadata": {
                            "model": "no-retrieval",
                            "tokens": 0,
                            "processing_time_ms": processing_time,
                            "intent": cls.get("intent", "question"),
                            "domain": cls.get("domain", "general")
                        },
                        "retrieved_chunks": [],
                        "image_url": None
                    }
            else:
                # RAG service error
                logger.error(f"RAG service error: {response.status_code} - {response.text}")
                return {
                    "answer": f"I encountered an error while processing your query. Please try again.",
                    "metadata": {
                        "model": "error",
                        "tokens": 0,
                        "processing_time_ms": (time.time() - start_time) * 1000,
                        "intent": "error",
                        "domain": "system"
                    },
                    "retrieved_chunks": [],
                    "image_url": None
                }
                
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {
            "answer": f"I encountered a technical error: {str(e)}. Please try again.",
            "metadata": {
                "model": "error",
                "tokens": 0,
                "processing_time_ms": 0,
                "intent": "error",
                "domain": "system"
            },
            "retrieved_chunks": [],
            "image_url": None
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
    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))
    return {
        "status": "ok",
        "service": "user-ui",
        "timestamp": time.time(),
        "phase": "5",
        "cors": get_cors_health_status(env),
        "tls": get_tls_health_status(env),
    }


@app.get("/api/auth/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """Verify JWT token and return user info"""
    if not credentials:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        claims = auth_service.jwt_service.verify_token(credentials.credentials, "access")
        auth_database = auth_db
        user = auth_database.get_user_by_id(claims.user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


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
        rag_result = await real_rag_query(query_request.query, context)
        
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
    import asyncio

    async def main():
        env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))
        port = int(os.getenv("USER_PORT", 8080))

        try:
            app_with_tls, cert_path, key_path = await create_app_with_tls(app, env)
            if cert_path and key_path:
                run_with_tls(app_with_tls, cert_path, key_path, port)
            else:
                uvicorn.run(app_with_tls, host="0.0.0.0", port=port, reload=(env == "dev"))
        except Exception as e:
            logger.error(f"TLS setup failed: {e}")
            uvicorn.run(app, host="0.0.0.0", port=port, reload=(env == "dev"))

    asyncio.run(main())
