# src_common/admin_routes.py
"""
Admin UI Routes - Phase 4 Implementation
Extracted routes from app_admin.py to be included in main application
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import shutil
import contextlib

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

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        # Send structured JSON to match frontend JSON.parse expectations
        await websocket.send_json(message)

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
            "timestamp": time.time(),
            "active_nav": "dashboard",
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
            await manager.send_personal_message(response, websocket)

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

# -------------------------
# Uploads management (Admin)
# -------------------------

def _uploads_dir(env: Optional[str] = None) -> str:
    base = os.getenv("UPLOADS_DIR", "/data/uploads")
    # Future: if env-specific upload roots are desired, compute here
    os.makedirs(base, exist_ok=True)
    return base

@admin_router.get("/api/uploads")
async def list_uploads(env: Optional[str] = Query(None)):
    """List files in uploads directory with basic metadata."""
    try:
        root = _uploads_dir(env)
        files: List[Dict[str, Any]] = []
        for entry in os.scandir(root):
            if not entry.is_file():
                continue
            stat = entry.stat()
            files.append({
                "name": entry.name,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            })
        files.sort(key=lambda x: x["modified_at"], reverse=True)
        return {"path": root, "count": len(files), "files": files}
    except Exception as e:
        logger.error(f"List uploads failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/uploads")
async def upload_files(files: List[UploadFile] = File(...), env: Optional[str] = Form(None)):
    """Upload one or more files to the uploads directory."""
    try:
        root = _uploads_dir(env)
        saved: List[str] = []
        for f in files:
            name = os.path.basename(f.filename or "")
            if not name:
                continue
            dest = os.path.join(root, name)
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            saved.append(name)
        return {"saved": saved, "path": root}
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for f in files:
            with contextlib.suppress(Exception):
                f.file.close()

@admin_router.delete("/api/uploads")
async def delete_upload(name: str, env: Optional[str] = Query(None)):
    """Delete a file from the uploads directory by name."""
    try:
        root = _uploads_dir(env)
        safe_name = os.path.basename(name)
        target = os.path.join(root, safe_name)
        if not os.path.isfile(target):
            raise HTTPException(status_code=404, detail="File not found")
        os.remove(target)
        return {"deleted": safe_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Artifacts viewing / download
# -------------------------

def _artifacts_dir_for_env(environment: str) -> Path:
    curr_env = os.getenv("APP_ENV", "dev")
    if environment == curr_env:
        base = Path("/app/artifacts")
    else:
        base = Path(f"artifacts/{environment}")
    base.mkdir(parents=True, exist_ok=True)
    return base

def _safe_join(base: Path, name: str) -> Path:
    target = (base / name).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    return target

@admin_router.get("/api/artifacts/{environment}/file")
async def download_artifact(environment: str, name: str):
    try:
        root = _artifacts_dir_for_env(environment)
        target = _safe_join(root, name)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path=str(target), filename=target.name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download artifact failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/artifacts/{environment}/view")
async def view_artifact(environment: str, name: str):
    try:
        root = _artifacts_dir_for_env(environment)
        target = _safe_join(root, name)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        # Try JSON parse for .json
        if target.suffix.lower() in {".json", ".ndjson"}:
            import json as _json
            try:
                data = _json.loads(target.read_text(encoding="utf-8", errors="ignore"))
                return JSONResponse(content={"name": target.name, "json": data})
            except Exception:
                pass
        # Fallback: return text
        text = target.read_text(encoding="utf-8", errors="ignore")
        return JSONResponse(content={"name": target.name, "text": text})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View artifact failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Logs listing / viewing
# -------------------------

def _log_dirs_for_env(environment: str) -> List[Path]:
    return [
        Path(f"env/{environment}/logs"),
        Path("/var/log/ttrpg"),
    ]

@admin_router.get("/api/logs/{environment}/list")
async def list_logs(environment: str):
    try:
        results: List[Dict[str, Any]] = []
        for base, prefix in ((Path(f"env/{environment}/logs"), "env"), (Path("/var/log/ttrpg"), "var")):
            if base.exists() and base.is_dir():
                for p in base.glob("*.log"):
                    try:
                        st = p.stat()
                        results.append({
                            "name": p.name,
                            "rel": f"{prefix}/{p.name}",
                            "size_bytes": st.st_size,
                            "modified_at": st.st_mtime,
                        })
                    except Exception:
                        continue
        results.sort(key=lambda x: x["modified_at"], reverse=True)
        return {"environment": environment, "logs": results}
    except Exception as e:
        logger.error(f"List logs failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _resolve_log_path(environment: str, rel: str) -> Path:
    if rel.startswith("var/"):
        base = Path("/var/log/ttrpg")
        name = rel[len("var/"):]
    elif rel.startswith("env/"):
        base = Path(f"env/{environment}/logs")
        name = rel[len("env/"):]
    else:
        # Fallback: try both bases
        base = None
        for b in _log_dirs_for_env(environment):
            cand = (b / rel).resolve()
            if cand.exists():
                return cand
        raise HTTPException(status_code=400, detail="Invalid log path")
    target = (base / name).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Invalid log path")
    return target

@admin_router.get("/api/logs/{environment}/view")
async def view_log(environment: str, name: str, lines: int = 500):
    try:
        target = _resolve_log_path(environment, name)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Log not found")
        # Tail last N lines
        with open(target, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return JSONResponse(content={"name": target.name, "rel": name, "text": ''.join(recent)})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"View log failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/logs/{environment}/file")
async def download_log(environment: str, name: str):
    try:
        target = _resolve_log_path(environment, name)
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="Log not found")
        return FileResponse(path=str(target), filename=target.name)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download log failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Cache control endpoints used by the Admin UI
@admin_router.post("/api/cache/{environment}/enable")
async def enable_cache(environment: str):
    try:
        ok = await cache_service.enable_cache(environment)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to enable cache")
        return {"status": "enabled", "environment": environment}
    except Exception as e:
        logger.error(f"Enable cache error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/cache/{environment}/disable")
async def disable_cache(environment: str):
    try:
        ok = await cache_service.disable_cache(environment)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to disable cache")
        return {"status": "disabled", "environment": environment}
    except Exception as e:
        logger.error(f"Disable cache error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/cache/{environment}/clear")
async def clear_cache(environment: str):
    try:
        result = await cache_service.clear_cache(environment)
        return result
    except Exception as e:
        logger.error(f"Clear cache error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Source Health Monitoring (Enhanced Ingestion Console)
# -------------------------

@admin_router.get("/api/ingestion/{environment}/sources")
async def get_ingestion_sources(environment: str):
    """Get ingested sources with health indicators and chunk counts."""
    try:
        sources_data = await ingestion_service.get_sources_health(environment)
        return {"sources": sources_data}
    except Exception as e:
        logger.error(f"Get ingestion sources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.delete("/api/ingestion/{environment}/source")
async def remove_ingestion_source(environment: str, name: str = Query(...)):
    """Remove an ingested source and all its artifacts."""
    try:
        success = await ingestion_service.remove_source(environment, name)
        if success:
            return {"message": f"Source {name} removed successfully", "removed": name}
        else:
            raise HTTPException(status_code=404, detail="Source not found or could not be removed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove ingestion source error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/admin/ingestion", response_class=HTMLResponse)
async def admin_ingestion_page(request: Request):
    context = {
        "request": request,
        "title": "Ingestion Console",
        "active_nav": "ingestion",
    }
    return templates.TemplateResponse("admin/ingestion.html", context)

@admin_router.get("/admin/dictionary", response_class=HTMLResponse)
async def admin_dictionary_page(request: Request):
    context = {
        "request": request,
        "title": "Dictionary Management",
        "active_nav": "dictionary",
    }
    return templates.TemplateResponse("admin/dictionary.html", context)

@admin_router.get("/admin/testing", response_class=HTMLResponse)
async def admin_testing_page(request: Request):
    context = {
        "request": request,
        "title": "Testing & Bugs",
        "active_nav": "testing",
    }
    return templates.TemplateResponse("admin/testing.html", context)

@admin_router.get("/admin/cache", response_class=HTMLResponse)
async def admin_cache_page(request: Request):
    context = {
        "request": request,
        "title": "Cache Control",
        "active_nav": "cache",
    }
    return templates.TemplateResponse("admin/cache.html", context)
