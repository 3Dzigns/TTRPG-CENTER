# src_common/admin_routes.py
"""
Admin UI Routes - Phase 4 Implementation
Extracted routes from app_admin.py to be included in main application
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends, Query, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import shutil
import contextlib

from .ttrpg_logging import get_logger
from .admin import (
    AdminStatusService,
    AdminIngestionService,
    AdminDictionaryService,
    AdminTestingService,
    AdminCacheService,
    AdminLogService
)
from .admin.testing import BugSeverity, BugPriority, BugStatus, BugComponent

# Initialize logging and services
logger = get_logger(__name__)
status_service = AdminStatusService()
ingestion_service = AdminIngestionService()
dictionary_service = AdminDictionaryService(use_mongodb=True)  # FR-015: Enable MongoDB by default
testing_service = AdminTestingService()
cache_service = AdminCacheService()
log_service = AdminLogService()

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

# Root route removed - User UI will handle the root route

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

@admin_router.delete("/api/ingestion/{environment}/jobs/{job_id}")
async def kill_ingestion_job(environment: str, job_id: str):
    """Kill/cancel a running or pending ingestion job."""
    try:
        result = await ingestion_service.kill_job(environment, job_id)
        if result:
            await notify_all_admins({
                "type": "job_killed",
                "data": {
                    "job_id": job_id,
                    "environment": environment,
                    "timestamp": datetime.now().isoformat()
                }
            })
            return {"success": True, "message": f"Job {job_id} killed successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or already completed")
    except Exception as e:
        logger.error(f"Job kill error: {e}")
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
        result = await dictionary_service.get_term(environment, term)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Term '{term}' not found in {environment}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Term details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Dictionary Management API - FR-015 MongoDB Integration
# -------------------------

@admin_router.get("/api/dictionary/{environment}/terms")
async def list_dictionary_terms(
    environment: str,
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
):
    """List dictionary terms with optional filtering."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        terms = await dictionary_service.list_terms(
            environment=environment,
            category=category,
            search=search,
            limit=limit
        )

        # Convert to dict format for JSON response
        return {
            "environment": environment,
            "total": len(terms),
            "terms": [asdict(term) for term in terms],
            "filters": {
                "category": category,
                "search": search,
                "limit": limit
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List dictionary terms error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/dictionary/{environment}/terms")
async def create_dictionary_term(environment: str, term_data: dict):
    """Create a new dictionary term."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        # Validate required fields
        required_fields = ['term', 'definition', 'category', 'source']
        missing_fields = [field for field in required_fields if field not in term_data]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )

        term = await dictionary_service.create_term(environment, term_data)

        return {
            "status": "created",
            "term": asdict(term),
            "environment": environment
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create dictionary term error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.put("/api/dictionary/{environment}/terms/{term_name}")
async def update_dictionary_term(environment: str, term_name: str, updates: dict):
    """Update an existing dictionary term."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        updated_term = await dictionary_service.update_term(environment, term_name, updates)

        return {
            "status": "updated",
            "term": asdict(updated_term),
            "environment": environment
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update dictionary term error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.delete("/api/dictionary/{environment}/terms/{term_name}")
async def delete_dictionary_term(environment: str, term_name: str):
    """Delete a dictionary term."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        success = await dictionary_service.delete_term(environment, term_name)

        if not success:
            raise HTTPException(status_code=404, detail=f"Term '{term_name}' not found in {environment}")

        return {
            "status": "deleted",
            "term": term_name,
            "environment": environment
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete dictionary term error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/dictionary/{environment}/search")
async def search_dictionary_terms(
    environment: str,
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """Search dictionary terms with full-text search capabilities."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        # Record search start time for performance monitoring (AC2)
        start_time = time.time()

        terms = await dictionary_service.search_terms(
            environment=environment,
            query=q,
            category=category
        )

        # Apply limit
        terms = terms[:limit]

        search_time = time.time() - start_time

        return {
            "environment": environment,
            "query": q,
            "category": category,
            "total": len(terms),
            "terms": [asdict(term) for term in terms],
            "search_time_seconds": round(search_time, 3),
            "performance_target_met": search_time <= 1.5  # AC2 requirement
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search dictionary terms error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/dictionary/{environment}/stats")
async def get_dictionary_stats(environment: str):
    """Get dictionary statistics for a specific environment."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        stats = await dictionary_service.get_environment_stats(environment)

        return {
            "environment": environment,
            "stats": asdict(stats),
            "backend": "mongodb" if dictionary_service.use_mongodb else "file_based"
        }

    except Exception as e:
        logger.error(f"Dictionary stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/dictionary/{environment}/import")
async def import_dictionary_terms(environment: str, file: UploadFile = File(...)):
    """Bulk import dictionary terms from JSON file."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Only JSON files are supported")

        # Read and parse file
        content = await file.read()
        try:
            import json
            data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON format: {e}")

        # Extract terms data
        if isinstance(data, dict) and 'terms' in data:
            terms_data = data['terms']
        elif isinstance(data, list):
            terms_data = data
        else:
            raise HTTPException(status_code=400, detail="JSON must contain 'terms' array or be an array")

        # Bulk import
        results = await dictionary_service.bulk_import(environment, terms_data)

        return {
            "status": "imported",
            "environment": environment,
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import dictionary terms error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/dictionary/{environment}/export")
async def export_dictionary_terms(environment: str, format: str = Query("json", regex="^(json|csv)$")):
    """Export dictionary terms in JSON or CSV format."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        export_data = await dictionary_service.export_terms(environment, format)

        if format == "json":
            from fastapi.responses import JSONResponse
            import json
            return JSONResponse(
                content=json.loads(export_data),
                headers={"Content-Disposition": f"attachment; filename=dictionary_{environment}.json"}
            )
        else:  # CSV
            from fastapi.responses import Response
            return Response(
                content=export_data,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=dictionary_{environment}.csv"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export dictionary terms error: {e}")
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

@admin_router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(request: Request):
    context = {
        "request": request,
        "title": "Log Management",
        "active_nav": "logs",
    }
    return templates.TemplateResponse("admin/logs.html", context)

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

# -------------------------
# Testing API Endpoints
# -------------------------

class TestRunRequest(BaseModel):
    environment: str
    test_type: Optional[str] = None

class TestCreateRequest(BaseModel):
    name: str
    description: str
    test_type: str
    command: str
    expected_result: str
    tags: Optional[List[str]] = None
    created_by: Optional[str] = "admin"

class BugCreateRequest(BaseModel):
    title: str
    description: str
    severity: str
    priority: Optional[str] = "medium"
    status: Optional[str] = "open"
    component: Optional[str] = "other"
    environment: str
    assigned_to: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    steps_to_reproduce: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    related_bugs: Optional[List[str]] = None
    test_failure_id: Optional[str] = None
    estimation_hours: Optional[float] = None
    milestone: Optional[str] = None
    version_found: Optional[str] = None
    created_by: Optional[str] = "admin"

class BugUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    component: Optional[str] = None
    resolution: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    steps_to_reproduce: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    related_bugs: Optional[List[str]] = None
    estimation_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    milestone: Optional[str] = None
    version_found: Optional[str] = None
    version_fixed: Optional[str] = None

class BugBulkUpdateRequest(BaseModel):
    bug_ids: List[str]
    updates: Dict[str, Any]
    updated_by: Optional[str] = "admin"

class BugSearchRequest(BaseModel):
    query: str
    environment: str
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 50

class BugFilterRequest(BaseModel):
    environment: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    component: Optional[str] = None
    assigned_to: Optional[str] = None
    created_by: Optional[str] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None
    limit: Optional[int] = 100
    offset: Optional[int] = 0

@admin_router.get("/api/admin/testing/overview")
async def get_testing_overview():
    """Get testing overview with statistics across all environments"""
    try:
        overview = await testing_service.get_testing_overview()
        return JSONResponse(content=overview)
    except Exception as e:
        logger.error(f"Error getting testing overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/tests")
async def list_tests(environment: Optional[str] = None, test_type: Optional[str] = None):
    """List tests, optionally filtered by environment and test type"""
    try:
        if environment and environment != 'all':
            tests = await testing_service.list_tests(environment, test_type)
        else:
            # Aggregate tests from all environments
            all_tests = []
            for env in ['dev', 'test', 'prod']:
                env_tests = await testing_service.list_tests(env, test_type)
                all_tests.extend(env_tests)
            tests = all_tests

        return JSONResponse(content=tests)
    except Exception as e:
        logger.error(f"Error listing tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/test/{test_id}")
async def get_test_details(test_id: str, environment: str):
    """Get detailed information about a specific test"""
    try:
        test = await testing_service.get_test(environment, test_id)
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")
        return JSONResponse(content=test)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/tests")
async def create_test(request: TestCreateRequest):
    """Create a new test"""
    try:
        test_data = request.dict()
        environment = test_data.pop('environment', 'dev')

        test = await testing_service.create_test(environment, test_data)

        # Convert TestStatus enum to string for JSON serialization
        test_dict = asdict(test)
        test_dict['status'] = test.status.value

        return JSONResponse(content=test_dict)
    except Exception as e:
        logger.error(f"Error creating test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/run-test/{test_id}")
async def run_single_test(test_id: str, request: TestRunRequest):
    """Run a single test"""
    try:
        execution = await testing_service.run_test(request.environment, test_id)
        return JSONResponse(content={"execution_id": execution.execution_id, "status": execution.status.value})
    except Exception as e:
        logger.error(f"Error running test {test_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/run-suite")
async def run_test_suite(request: TestRunRequest):
    """Run a test suite"""
    try:
        result = await testing_service.run_test_suite(request.environment, request.test_type)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error running test suite: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/run-all")
async def run_all_tests(request: TestRunRequest):
    """Run all test suites"""
    try:
        # Run each test type
        all_results = {
            "suite_id": f"all-{int(time.time())}",
            "environment": request.environment,
            "started_at": time.time(),
            "suites": []
        }

        for test_type in ['unit', 'functional', 'security', 'regression']:
            try:
                result = await testing_service.run_test_suite(request.environment, test_type)
                all_results["suites"].append(result)
            except Exception as e:
                logger.error(f"Error running {test_type} tests: {e}")

        all_results["completed_at"] = time.time()
        all_results["duration_seconds"] = all_results["completed_at"] - all_results["started_at"]

        return JSONResponse(content=all_results)
    except Exception as e:
        logger.error(f"Error running all tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/stop-all")
async def stop_all_tests(environment: str = "dev"):
    """Stop all running tests"""
    try:
        success = await testing_service.stop_all_tests(environment)
        return JSONResponse(content={"success": success})
    except Exception as e:
        logger.error(f"Error stopping tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/bugs")
async def list_bugs(
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    component: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    created_by: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(100),
    offset: Optional[int] = Query(0)
):
    """List bugs with comprehensive filtering support"""
    try:
        if environment and environment != 'all':
            bugs = await testing_service.list_bugs(
                environment=environment,
                status=status,
                severity=severity,
                priority=priority,
                component=component,
                assigned_to=assigned_to,
                created_by=created_by,
                search=search,
                limit=limit,
                offset=offset
            )
        else:
            # Aggregate bugs from all environments
            all_bugs = []
            env_limit = limit // 3 if limit else None  # Distribute limit across environments
            for env in ['dev', 'test', 'prod']:
                env_bugs = await testing_service.list_bugs(
                    environment=env,
                    status=status,
                    severity=severity,
                    priority=priority,
                    component=component,
                    assigned_to=assigned_to,
                    created_by=created_by,
                    search=search,
                    limit=env_limit,
                    offset=offset
                )
                all_bugs.extend(env_bugs)
            bugs = all_bugs[:limit] if limit else all_bugs

        return JSONResponse(content={
            "bugs": bugs,
            "total": len(bugs),
            "offset": offset,
            "limit": limit
        })
    except Exception as e:
        logger.error(f"Error listing bugs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/bug/{bug_id}")
async def get_bug_details(bug_id: str, environment: str):
    """Get detailed information about a specific bug"""
    try:
        bug = await testing_service.get_bug(environment, bug_id)
        if not bug:
            raise HTTPException(status_code=404, detail="Bug not found")
        return JSONResponse(content=bug)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bug details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/bugs")
async def create_bug(request: BugCreateRequest):
    """Create a new bug report"""
    try:
        bug_data = request.dict()
        environment = bug_data.pop('environment')

        bug = await testing_service.create_bug(environment, bug_data)

        # Convert BugSeverity enum to string for JSON serialization
        bug_dict = asdict(bug)
        bug_dict['severity'] = bug.severity.value

        return JSONResponse(content=bug_dict)
    except Exception as e:
        logger.error(f"Error creating bug: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.put("/api/admin/testing/bug/{bug_id}")
async def update_bug(bug_id: str, request: BugUpdateRequest, environment: str = Query(...), updated_by: str = Query("admin")):
    """Update an existing bug report with activity tracking"""
    try:
        updates = request.dict(exclude_unset=True)
        bug = await testing_service.update_bug(environment, bug_id, updates, updated_by)
        if not bug:
            raise HTTPException(status_code=404, detail="Bug not found")

        return JSONResponse(content=testing_service._serialize_bug(bug))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bug: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/execution-history")
async def get_execution_history(environment: Optional[str] = None, limit: int = 50):
    """Get test execution history"""
    try:
        if environment and environment != 'all':
            executions = await testing_service.get_recent_executions(environment, limit)
        else:
            # Aggregate executions from all environments
            all_executions = []
            for env in ['dev', 'test', 'prod']:
                env_executions = await testing_service.get_recent_executions(env, limit // 3)
                all_executions.extend([testing_service._serialize_execution(exec) for exec in env_executions])

            # Sort by start time and apply limit
            all_executions.sort(key=lambda x: x['started_at'], reverse=True)
            return JSONResponse(content=all_executions[:limit])

        executions_dict = [testing_service._serialize_execution(exec) for exec in executions]
        return JSONResponse(content=executions_dict)
    except Exception as e:
        logger.error(f"Error getting execution history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/export-results")
async def export_test_results(environment: Optional[str] = None):
    """Export test results and execution history"""
    try:
        export_data = await testing_service.export_test_results(environment)

        # Create a downloadable file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"

        return JSONResponse(
            content=export_data,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting test results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------
# Enhanced Bug Management API - FR-017
# -------------------------

@admin_router.post("/api/admin/testing/bugs/search")
async def search_bugs(request: BugSearchRequest):
    """Advanced search across bug data with relevance scoring"""
    try:
        results = await testing_service.search_bugs(
            environment=request.environment,
            query=request.query,
            filters=request.filters
        )

        # Apply limit
        if request.limit:
            results = results[:request.limit]

        return JSONResponse(content={
            "query": request.query,
            "environment": request.environment,
            "results": results,
            "total_matches": len(results)
        })
    except Exception as e:
        logger.error(f"Error searching bugs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/bugs/bulk-update")
async def bulk_update_bugs(request: BugBulkUpdateRequest):
    """Perform bulk updates on multiple bugs"""
    try:
        if not request.bug_ids:
            raise HTTPException(status_code=400, detail="No bug IDs provided")

        if not request.updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Extract environment from the first bug (assuming all bugs are in same environment)
        # In a real implementation, you might want to validate this
        environment = request.updates.get('environment', 'dev')

        results = await testing_service.bulk_update_bugs(
            environment=environment,
            bug_ids=request.bug_ids,
            updates=request.updates,
            updated_by=request.updated_by
        )

        return JSONResponse(content=results)
    except Exception as e:
        logger.error(f"Error in bulk update: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/bugs/bulk-assign")
async def bulk_assign_bugs(
    bug_ids: List[str],
    assignee: str,
    environment: str = Query(...),
    assigned_by: str = Query("admin")
):
    """Bulk assign multiple bugs to a user"""
    try:
        if not bug_ids:
            raise HTTPException(status_code=400, detail="No bug IDs provided")

        results = await testing_service.bulk_assign_bugs(
            environment=environment,
            bug_ids=bug_ids,
            assignee=assignee,
            assigned_by=assigned_by
        )

        return JSONResponse(content=results)
    except Exception as e:
        logger.error(f"Error in bulk assignment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/create-bug-from-test-failure")
async def create_bug_from_test_failure(
    test_id: str,
    execution_id: str,
    environment: str,
    created_by: str = Query("admin")
):
    """Automatically create a bug from a test failure"""
    try:
        # Get test execution details
        executions = await testing_service.get_recent_executions(environment, limit=1000)
        test_execution = None
        for exec in executions:
            if exec.execution_id == execution_id:
                test_execution = exec
                break

        if not test_execution:
            raise HTTPException(status_code=404, detail="Test execution not found")

        # Get test definition
        test_def = await testing_service.get_test(environment, test_id)
        if not test_def:
            raise HTTPException(status_code=404, detail="Test definition not found")

        # Create bug from failure
        bug = await testing_service.create_bug_from_test_failure(
            environment=environment,
            test_execution=test_execution,
            test_definition=test_def,
            created_by=created_by
        )

        return JSONResponse(content=testing_service._serialize_bug(bug))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating bug from test failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/bugs/analytics/{environment}")
async def get_bug_analytics(
    environment: str,
    date_from: Optional[float] = Query(None),
    date_to: Optional[float] = Query(None)
):
    """Get comprehensive analytics for bug data"""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        analytics = await testing_service.get_bug_analytics(
            environment=environment,
            date_from=date_from,
            date_to=date_to
        )

        return JSONResponse(content=analytics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating bug analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/bugs/filters/options")
async def get_bug_filter_options(environment: Optional[str] = Query(None)):
    """Get available filter options for bug management UI"""
    try:

        # Get all bugs to extract dynamic options
        all_assignees = set()
        all_creators = set()
        all_tags = set()
        all_labels = set()
        all_milestones = set()

        environments = [environment] if environment and environment != 'all' else ['dev', 'test', 'prod']

        for env in environments:
            bugs = await testing_service.list_bugs(env)
            for bug in bugs:
                if bug.get('assigned_to'):
                    all_assignees.add(bug['assigned_to'])
                if bug.get('created_by'):
                    all_creators.add(bug['created_by'])
                if bug.get('tags'):
                    all_tags.update(bug['tags'])
                if bug.get('labels'):
                    all_labels.update(bug['labels'])
                if bug.get('milestone'):
                    all_milestones.add(bug['milestone'])

        return JSONResponse(content={
            "static_options": {
                "severities": [s.value for s in BugSeverity],
                "priorities": [p.value for p in BugPriority],
                "statuses": [s.value for s in BugStatus],
                "components": [c.value for c in BugComponent],
                "environments": ['dev', 'test', 'prod']
            },
            "dynamic_options": {
                "assignees": sorted(list(all_assignees)),
                "creators": sorted(list(all_creators)),
                "tags": sorted(list(all_tags)),
                "labels": sorted(list(all_labels)),
                "milestones": sorted(list(all_milestones))
            }
        })
    except Exception as e:
        logger.error(f"Error getting filter options: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/api/admin/testing/bugs/{bug_id}/activity")
async def get_bug_activity(bug_id: str, environment: str = Query(...)):
    """Get activity log for a specific bug"""
    try:
        bug = await testing_service.get_bug(environment, bug_id)
        if not bug:
            raise HTTPException(status_code=404, detail="Bug not found")

        activity_log = bug.get('activity_log', [])
        return JSONResponse(content={
            "bug_id": bug_id,
            "activity_log": activity_log,
            "total_activities": len(activity_log)
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bug activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/api/admin/testing/bugs/{bug_id}/comment")
async def add_bug_comment(
    bug_id: str,
    comment: str,
    environment: str = Query(...),
    user: str = Query("admin")
):
    """Add a comment to a bug's activity log"""
    try:
        # This would require extending the update_bug method to handle comments
        # For now, we'll add it as a custom activity
        bugs = await testing_service._load_environment_bugs(environment)

        for bug in bugs:
            if bug.bug_id == bug_id:
                from ..admin.testing import BugActivity

                activity = BugActivity(
                    activity_id=str(uuid.uuid4()),
                    bug_id=bug_id,
                    activity_type='commented',
                    user=user,
                    timestamp=time.time(),
                    description=f"Added comment: {comment[:50]}{'...' if len(comment) > 50 else ''}",
                    details={'comment': comment}
                )

                bug.activity_log.append(activity)
                bug.last_updated = time.time()
                bug.last_updated_by = user

                await testing_service._save_bug(bug)

                return JSONResponse(content={
                    "status": "success",
                    "activity_id": activity.activity_id,
                    "message": "Comment added successfully"
                })

        raise HTTPException(status_code=404, detail="Bug not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding bug comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/admin/cache", response_class=HTMLResponse)
async def admin_cache_page(request: Request):
    context = {
        "request": request,
        "title": "Cache Control",
        "active_nav": "cache",
    }
    return templates.TemplateResponse("admin/cache.html", context)

# -------------------------
# Ingestion Job Management
# -------------------------

class IngestionRunRequest(BaseModel):
    env: str
    source_files: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None
    job_type: Optional[str] = "ad_hoc"  # "ad_hoc" or "nightly"

@admin_router.post("/api/admin/ingestion/run")
async def run_ingestion_job(request: IngestionRunRequest):
    """Start an ingestion job for the specified environment."""
    try:
        # Determine source file based on job type
        if request.job_type == "nightly":
            source_file = "nightly_run"
        else:
            # For ad-hoc jobs, use first source file if provided, otherwise placeholder
            source_file = (request.source_files[0] if request.source_files
                          else "ad_hoc_run")

        # Start the ingestion job
        job_id = await ingestion_service.start_ingestion_job(
            environment=request.env,
            source_file=source_file,
            options=request.options or {},
            job_type=request.job_type or "ad_hoc"
        )

        # Broadcast job start via WebSocket
        await manager.broadcast({
            "type": "ingestion_job_started",
            "job_id": job_id,
            "environment": request.env,
            "timestamp": time.time()
        })

        # Simulate process ID for compatibility with frontend expectations
        import os
        pid = os.getpid()

        return {
            "job_id": job_id,
            "env": request.env,
            "pid": pid,
            "status": "started",
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Failed to start ingestion job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# Log Management - FR-008
# -------------------------

@admin_router.get("/api/admin/logs/list")
async def get_logs_list(
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None)
):
    """Get list of log files with filtering"""
    try:
        return await log_service.get_logs_overview(
            environment=environment,
            status=status,
            job_type=job_type,
            search=search,
            date_from=date_from,
            date_to=date_to
        )
    except Exception as e:
        logger.error(f"Error getting logs list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/logs/content")
async def get_log_content(
    job_id: str = Query(...),
    env: str = Query(...),
    lines: int = Query(1000)
):
    """Get content of a specific log file"""
    try:
        return await log_service.get_log_content(job_id, env, lines)
    except Exception as e:
        logger.error(f"Error getting log content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/logs/status")
async def get_log_job_status(
    job_id: str = Query(...),
    env: str = Query(...)
):
    """Get status of a specific job"""
    try:
        return await log_service.get_job_status(job_id, env)
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/logs/download")
async def download_log_file(
    job_id: str = Query(...),
    env: str = Query(...)
):
    """Download a specific log file"""
    try:
        # Find the log file
        env_log_dir = Path("env") / env / "logs"
        log_files = list(env_log_dir.glob("*.log"))

        target_file = None
        for log_file in log_files:
            if job_id in str(log_file):
                target_file = log_file
                break

        if not target_file or not target_file.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        return FileResponse(
            path=target_file,
            filename=target_file.name,
            media_type='text/plain'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading log file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/logs/export")
async def export_all_logs(environment: Optional[str] = Query(None)):
    """Export all logs as ZIP file"""
    try:
        zip_data = await log_service.export_logs(environment)

        # Create a temporary file for the ZIP
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
            tmp_file.write(zip_data)
            tmp_file_path = tmp_file.name

        filename = f"logs-export-{environment or 'all'}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        return FileResponse(
            path=tmp_file_path,
            filename=filename,
            media_type='application/zip'
        )

    except Exception as e:
        logger.error(f"Error exporting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# AstraDB Health Status
# -------------------------

@admin_router.get("/api/admin/astradb/sources/{environment}")
async def get_astradb_sources(environment: str):
    """Get sources with chunk counts directly from AstraDB for the specified environment."""
    try:
        # Import AstraLoader to query the database
        from .astra_loader import AstraLoader

        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        loader = AstraLoader(env=environment)
        sources_data = loader.get_sources_with_chunk_counts()

        return {
            "status": "success",
            "environment": environment,
            "data": sources_data,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error getting AstraDB sources for {environment}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/sources/health/{environment}")
async def get_sources_health_status(environment: str):
    """Get comprehensive health status combining local artifacts and AstraDB sources."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        sources_health = await ingestion_service.get_sources_health(environment)

        return {
            "status": "success",
            "environment": environment,
            "sources": sources_health,
            "timestamp": time.time(),
            "total_sources": len(sources_health)
        }

    except Exception as e:
        logger.error(f"Error getting sources health for {environment}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/ingestion/recent")
async def get_recent_ingestion_jobs(limit: int = 3):
    """Get the most recent ingestion jobs across all environments with standardized status."""
    try:
        if limit < 1 or limit > 10:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 10")

        recent_jobs = await ingestion_service.get_recent_jobs(limit=limit)

        return {
            "status": "success",
            "jobs": recent_jobs,
            "total_returned": len(recent_jobs),
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error getting recent ingestion jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# MongoDB Dictionary Status - FR-015 Integration
# -------------------------

@admin_router.get("/api/admin/mongodb/health")
async def get_mongodb_health():
    """Get overall MongoDB health status across all environments."""
    try:
        health_results = {}
        overall_healthy = True

        for env in ['dev', 'test', 'prod']:
            try:
                # Get MongoDB adapter for each environment
                adapter = dictionary_service._get_adapter(env)

                if adapter:
                    # Get health check from MongoDB service
                    health = adapter.mongo_service.health_check()
                    circuit_stats = adapter.get_circuit_breaker_stats()

                    health_results[env] = {
                        "status": health.get("status", "unknown"),
                        "database": health.get("database"),
                        "collection": health.get("collection"),
                        "estimated_documents": health.get("estimated_documents", 0),
                        "circuit_breaker": {
                            "state": circuit_stats.get("state", "unknown"),
                            "failure_count": circuit_stats.get("failure_count", 0),
                            "last_failure_time": circuit_stats.get("last_failure_time")
                        },
                        "error": health.get("error")
                    }

                    if health.get("status") != "healthy":
                        overall_healthy = False
                else:
                    health_results[env] = {
                        "status": "unavailable",
                        "error": "MongoDB adapter not initialized"
                    }
                    overall_healthy = False

            except Exception as e:
                health_results[env] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "environments": health_results,
            "backend_active": dictionary_service.use_mongodb,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error getting MongoDB health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get("/api/admin/mongodb/status/{environment}")
async def get_mongodb_status(environment: str):
    """Get detailed MongoDB status for a specific environment."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        adapter = dictionary_service._get_adapter(environment)

        if not adapter:
            return {
                "status": "unavailable",
                "environment": environment,
                "error": "MongoDB adapter not initialized",
                "backend_active": dictionary_service.use_mongodb,
                "timestamp": time.time()
            }

        # Get comprehensive status including performance metrics
        health = adapter.mongo_service.health_check()
        stats = adapter.mongo_service.get_stats()
        circuit_stats = adapter.get_circuit_breaker_stats()

        # Perform a test query to measure performance (AC2 requirement)
        start_time = time.time()
        try:
            # Test query - get one document from collection
            if adapter.mongo_service.collection:
                test_result = adapter.mongo_service.collection.find_one()
                query_time_ms = (time.time() - start_time) * 1000
                performance_ok = query_time_ms <= 1500  # FR-015 AC2 requirement
            else:
                query_time_ms = None
                performance_ok = False
        except Exception:
            query_time_ms = None
            performance_ok = False

        return {
            "status": health.get("status", "unknown"),
            "environment": environment,
            "connection": {
                "database": health.get("database"),
                "collection": health.get("collection"),
                "estimated_documents": health.get("estimated_documents", 0)
            },
            "statistics": {
                "entries": stats.get("total_entries", 0),
                "categories": len(stats.get("category_distribution", {})),
                "category_distribution": stats.get("category_distribution", {})
            },
            "performance": {
                "avg_query_time": query_time_ms,
                "performance_target_met": performance_ok,
                "target_threshold_ms": 1500
            },
            "circuit_breaker": {
                "state": circuit_stats.get("state", "unknown"),
                "failure_count": circuit_stats.get("failure_count", 0),
                "success_count": circuit_stats.get("success_count", 0),
                "last_failure_time": circuit_stats.get("last_failure_time"),
                "last_success_time": circuit_stats.get("last_success_time")
            },
            "backend_active": dictionary_service.use_mongodb,
            "error": health.get("error") or stats.get("error"),
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error getting MongoDB status for {environment}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/api/admin/mongodb/{environment}/reset-circuit-breaker")
async def reset_mongodb_circuit_breaker(environment: str):
    """Reset the circuit breaker for MongoDB dictionary service in specified environment."""
    try:
        if environment not in ['dev', 'test', 'prod']:
            raise HTTPException(status_code=400, detail="Invalid environment")

        adapter = dictionary_service._get_adapter(environment)

        if not adapter:
            raise HTTPException(status_code=404, detail="MongoDB adapter not found for environment")

        # Reset the circuit breaker
        adapter.reset_circuit_breaker()

        # Force a health check to verify recovery
        health_ok = adapter.force_health_check()

        return {
            "status": "reset",
            "environment": environment,
            "health_check_passed": health_ok,
            "message": f"Circuit breaker reset for MongoDB dictionary in {environment}",
            "timestamp": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting MongoDB circuit breaker for {environment}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
