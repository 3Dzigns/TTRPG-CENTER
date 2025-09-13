# src_common/admin_routes.py
"""
Admin UI Routes - Phase 4 Implementation
Extracted routes from app_admin.py to be included in main application
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .logging import get_logger
from .admin import (
    AdminStatusService,
    AdminIngestionService,
    AdminDictionaryService,
    AdminTestingService,
    AdminCacheService
)

# Initialize logging and services
logger = get_logger(__name__)
status_service = AdminStatusService()
ingestion_service = AdminIngestionService()
dictionary_service = AdminDictionaryService()
testing_service = AdminTestingService()
cache_service = AdminCacheService()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Create router
admin_router = APIRouter()

# Pydantic models for request/response
class CacheSettings(BaseModel):
    ttl: int
    max_size: Optional[int] = None

class TestRunRequest(BaseModel):
    test_type: str
    environment: Optional[str] = "dev"

class IngestionJobRequest(BaseModel):
    source_path: str
    job_type: Optional[str] = "full"

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:  # Create a copy to avoid modification during iteration
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# Routes
@admin_router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render the admin dashboard."""
    try:
        context = {
            "request": request,
            "title": "TTRPG Center - Admin Dashboard",
            "environment": os.getenv("APP_ENV", "dev"),
            "version": "0.1.0",
            "timestamp": time.time()
        }
        return templates.TemplateResponse("admin_dashboard.html", context)
    except Exception as e:
        logger.error(f"Error rendering admin dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to render admin dashboard")

# Root route removed - User UI should handle the root route

# API endpoints
@admin_router.get("/api/status/overview")
async def get_status_overview():
    """Get system status overview across all environments."""
    try:
        return await status_service.get_system_overview()
    except Exception as e:
        logger.error(f"Status overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/status/{environment}")
async def get_environment_status(environment: str):
    """Get detailed status for specific environment."""
    try:
        return await status_service.check_environment_health(environment)
    except Exception as e:
        logger.error(f"Environment status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/status/{environment}/logs")
async def get_environment_logs(environment: str, limit: int = Query(100, ge=1, le=1000)):
    """Get recent log entries for environment."""
    try:
        return await status_service.get_environment_logs(environment, limit)
    except Exception as e:
        logger.error(f"Logs retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/status/{environment}/artifacts")
async def get_environment_artifacts(environment: str):
    """Get artifacts summary for environment."""
    try:
        return await status_service.get_environment_artifacts(environment)
    except Exception as e:
        logger.error(f"Artifacts retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/ingestion/overview")
async def get_ingestion_overview():
    """Get ingestion status overview."""
    try:
        return await ingestion_service.get_ingestion_overview()
    except Exception as e:
        logger.error(f"Ingestion overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/ingestion/{environment}/jobs/{job_id}")
async def get_ingestion_job_details(environment: str, job_id: str):
    """Get detailed job information."""
    try:
        return await ingestion_service.get_job_details(environment, job_id)
    except Exception as e:
        logger.error(f"Job details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/dictionary/overview")
async def get_dictionary_overview():
    """Get dictionary status overview."""
    try:
        return await dictionary_service.get_dictionary_overview()
    except Exception as e:
        logger.error(f"Dictionary overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/dictionary/{environment}/terms/{term}")
async def get_dictionary_term_details(environment: str, term: str):
    """Get detailed information about a specific term."""
    try:
        return await dictionary_service.get_term(environment, term)
    except Exception as e:
        logger.error(f"Term details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/cache/overview")
async def get_cache_overview():
    """Get cache status overview."""
    try:
        return await cache_service.get_cache_overview()
    except Exception as e:
        logger.error(f"Cache overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint
@admin_router.websocket("/ws/admin")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time admin updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received WebSocket data: {data}")

            # Echo back with server timestamp
            response = {
                "type": "echo",
                "data": data,
                "timestamp": time.time(),
                "server": "admin"
            }
            await manager.send_personal_message(str(response), websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# Additional utility endpoints
@admin_router.get("/api/admin/health")
async def admin_health_check():
    """Health check specific to admin functionality."""
    try:
        return {
            "status": "healthy",
            "environment": os.getenv("APP_ENV", "dev"),
            "services": {
                "status": "available",
                "ingestion": "available",
                "dictionary": "available",
                "testing": "available",
                "cache": "available"
            },
            "websocket_connections": len(manager.active_connections),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Admin health check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))