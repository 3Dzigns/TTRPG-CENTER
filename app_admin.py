# app_admin.py
"""
Admin UI Application - Phase 4 Implementation
Operational tools for system management, monitoring, and configuration
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src_common.ttrpg_logging import get_logger, setup_logging
from src_common.cors_security import (
    setup_secure_cors,
    validate_cors_startup,
    get_cors_health_status,
)
from src_common.tls_security import (
    create_app_with_tls,
    validate_tls_startup,
    get_tls_health_status,
)
from src_common.jwt_service import auth_service
from src_common.admin import (
    AdminStatusService,
    AdminIngestionService,
    AdminDictionaryService,
    AdminTestingService,
    AdminCacheService
)
# OAuth integration
from src_common.oauth_endpoints import oauth_router
# Admin routes
from src_common.admin_routes import admin_router


# Initialize logging
logger = setup_logging()

# Initialize admin services
status_service = AdminStatusService()
ingestion_service = AdminIngestionService()
dictionary_service = AdminDictionaryService()
testing_service = AdminTestingService()
cache_service = AdminCacheService()


# FastAPI app
app = FastAPI(
    title="TTRPG Center - Admin Console",
    description="Administrative interface for TTRPG Center operations",
    version="0.1.0"
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
app.include_router(admin_router)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                self.disconnect(connection)


manager = ConnectionManager()


# Helper function for environment validation
def validate_environment(environment: str):
    """Validate environment parameter"""
    if environment not in ['dev', 'test', 'prod']:
        raise HTTPException(status_code=400, detail=f"Invalid environment: {environment}")


# Request/Response models
class CachePolicyUpdate(BaseModel):
    cache_enabled: Optional[bool] = None
    default_ttl_seconds: Optional[int] = None
    short_ttl_seconds: Optional[int] = None
    admin_override: Optional[bool] = None


class TestCreation(BaseModel):
    name: str
    description: str
    test_type: str
    command: str
    expected_result: str
    tags: List[str] = []


class BugCreation(BaseModel):
    title: str
    description: str
    severity: str
    steps_to_reproduce: List[str] = []
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None


class DictionaryTerm(BaseModel):
    term: str
    definition: str
    category: str
    source: str
    page_reference: Optional[str] = None
    tags: List[str] = []


# Cache control middleware
@app.middleware("http")
async def cache_control_middleware(request: Request, call_next):
    """Add appropriate cache headers based on environment and admin settings"""
    response = await call_next(request)
    
    try:
        # Get environment from request or default to dev
        environment = request.path_params.get('env', 'dev')
        
        # Get appropriate cache headers
        cache_headers = await cache_service.get_cache_headers(environment, request.url.path)
        
        for header, value in cache_headers.items():
            response.headers[header] = value
            
    except Exception as e:
        logger.error(f"Error setting cache headers: {e}")
        # Safe fallback - no cache
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    
    return response


# Routes

@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard home page"""
    try:
        # Get overview data for all environments
        system_overview = await status_service.get_system_overview()
        cache_overview = await cache_service.get_cache_overview()
        
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "system_overview": system_overview,
            "cache_overview": cache_overview,
            "current_time": time.time()
        })
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error loading dashboard")


# Security (JWT) enforcement middleware for admin APIs in production
@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    try:
        # Only enforce on API routes in production
        env = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "dev")).lower()
        if env == "prod" and request.url.path.startswith("/api/") and request.method != "OPTIONS":
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse({"detail": "Authentication required"}, status_code=401)
            token = auth_header[7:]
            # Verify token and require admin role
            try:
                user_ctx = auth_service.jwt_service.get_user_context(token)
                if not getattr(user_ctx, "is_admin", False):
                    return JSONResponse({"detail": "Admin privileges required"}, status_code=403)
            except Exception:
                return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)

        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Admin auth middleware error: {e}")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)


# System Status API
@app.get("/api/status/overview")
async def get_status_overview():
    """Get system status overview"""
    return await status_service.get_system_overview()


@app.get("/api/status/{environment}")
async def get_environment_status(environment: str):
    """Get status for specific environment"""
    validate_environment(environment)
    
    return await status_service.check_environment_health(environment)


@app.get("/api/status/{environment}/logs")
async def get_environment_logs(environment: str, lines: int = Query(100, ge=1, le=1000)):
    """Get recent logs for environment"""
    validate_environment(environment)
    
    return await status_service.get_environment_logs(environment, lines)


@app.get("/api/status/{environment}/artifacts")
async def get_environment_artifacts(environment: str):
    """Get artifacts for environment"""
    validate_environment(environment)
    
    return await status_service.get_environment_artifacts(environment)


# Ingestion Console API
@app.get("/api/ingestion/overview")
async def get_ingestion_overview():
    """Get ingestion overview"""
    return await ingestion_service.get_ingestion_overview()


@app.get("/api/ingestion/{environment}/jobs")
async def list_ingestion_jobs(environment: str, limit: int = Query(50, ge=1, le=100)):
    """List ingestion jobs for environment"""
    validate_environment(environment)
    
    return await ingestion_service.list_jobs(environment, limit)


@app.get("/api/ingestion/{environment}/jobs/{job_id}")
async def get_job_details(environment: str, job_id: str):
    """Get detailed job information"""
    validate_environment(environment)
    
    job = await ingestion_service.get_job_details(environment, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@app.post("/api/ingestion/{environment}/jobs/{job_id}/retry")
async def retry_ingestion_job(environment: str, job_id: str):
    """Retry a failed ingestion job"""
    validate_environment(environment)
    
    success = await ingestion_service.retry_job(environment, job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot retry job")
    
    return {"success": True, "message": "Job retry initiated"}


@app.delete("/api/ingestion/{environment}/jobs/{job_id}")
async def delete_ingestion_job(environment: str, job_id: str):
    """Delete an ingestion job"""
    validate_environment(environment)
    
    success = await ingestion_service.delete_job(environment, job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete job")
    
    return {"success": True, "message": "Job deleted"}


# Dictionary Management API
@app.get("/api/dictionary/overview")
async def get_dictionary_overview():
    """Get dictionary overview"""
    return await dictionary_service.get_dictionary_overview()


@app.get("/api/dictionary/{environment}/terms")
async def list_dictionary_terms(
    environment: str,
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500)
):
    """List dictionary terms"""
    validate_environment(environment)
    
    terms = await dictionary_service.list_terms(environment, category, search, limit)
    return [term.__dict__ if hasattr(term, '__dict__') else term for term in terms]


@app.get("/api/dictionary/{environment}/terms/{term}")
async def get_dictionary_term(environment: str, term: str):
    """Get specific dictionary term"""
    validate_environment(environment)
    
    dict_term = await dictionary_service.get_term(environment, term)
    if not dict_term:
        raise HTTPException(status_code=404, detail="Term not found")
    
    return dict_term.__dict__ if hasattr(dict_term, '__dict__') else dict_term


@app.post("/api/dictionary/{environment}/terms")
async def create_dictionary_term(environment: str, term_data: DictionaryTerm):
    """Create new dictionary term"""
    validate_environment(environment)
    
    try:
        created_term = await dictionary_service.create_term(environment, term_data.dict())
        return created_term.__dict__ if hasattr(created_term, '__dict__') else created_term
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/dictionary/{environment}/terms/{term}")
async def update_dictionary_term(environment: str, term: str, updates: Dict[str, Any]):
    """Update dictionary term"""
    validate_environment(environment)
    
    try:
        updated_term = await dictionary_service.update_term(environment, term, updates)
        return updated_term.__dict__ if hasattr(updated_term, '__dict__') else updated_term
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/dictionary/{environment}/terms/{term}")
async def delete_dictionary_term(environment: str, term: str):
    """Delete dictionary term"""
    validate_environment(environment)
    
    success = await dictionary_service.delete_term(environment, term)
    if not success:
        raise HTTPException(status_code=404, detail="Term not found")
    
    return {"success": True, "message": "Term deleted"}


# Testing & Bug Management API
@app.get("/api/testing/overview")
async def get_testing_overview():
    """Get testing overview"""
    return await testing_service.get_testing_overview()


@app.get("/api/testing/{environment}/tests")
async def list_tests(environment: str, test_type: Optional[str] = Query(None)):
    """List regression tests"""
    validate_environment(environment)
    
    return await testing_service.list_tests(environment, test_type)


@app.post("/api/testing/{environment}/tests")
async def create_test(environment: str, test_data: TestCreation):
    """Create new regression test"""
    validate_environment(environment)
    
    try:
        created_test = await testing_service.create_test(environment, test_data.dict())
        return created_test.__dict__ if hasattr(created_test, '__dict__') else created_test
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/testing/{environment}/tests/{test_id}/run")
async def run_test(environment: str, test_id: str):
    """Run a regression test"""
    validate_environment(environment)
    
    try:
        execution = await testing_service.run_test(environment, test_id)
        return execution.__dict__ if hasattr(execution, '__dict__') else execution
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/testing/{environment}/test-suites/run")
async def run_test_suite(environment: str, test_type: Optional[str] = Query(None)):
    """Run test suite"""
    validate_environment(environment)
    
    return await testing_service.run_test_suite(environment, test_type)


@app.get("/api/testing/{environment}/bugs")
async def list_bugs(
    environment: str,
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None)
):
    """List bug bundles"""
    validate_environment(environment)
    
    return await testing_service.list_bugs(environment, status, severity)


@app.post("/api/testing/{environment}/bugs")
async def create_bug(environment: str, bug_data: BugCreation):
    """Create new bug bundle"""
    validate_environment(environment)
    
    try:
        created_bug = await testing_service.create_bug(environment, bug_data.dict())
        return created_bug.__dict__ if hasattr(created_bug, '__dict__') else created_bug
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Cache Control API
@app.get("/api/cache/overview")
async def get_cache_overview():
    """Get cache overview"""
    return await cache_service.get_cache_overview()


@app.get("/api/cache/{environment}/policy")
async def get_cache_policy(environment: str):
    """Get cache policy for environment"""
    validate_environment(environment)
    
    policy = await cache_service.get_cache_policy(environment)
    return policy.__dict__ if hasattr(policy, '__dict__') else policy


@app.put("/api/cache/{environment}/policy")
async def update_cache_policy(environment: str, updates: CachePolicyUpdate):
    """Update cache policy"""
    validate_environment(environment)
    
    policy = await cache_service.update_cache_policy(
        environment, 
        updates.dict(exclude_unset=True)
    )
    return policy.__dict__ if hasattr(policy, '__dict__') else policy


@app.post("/api/cache/{environment}/disable")
async def disable_cache(environment: str):
    """Disable cache for environment"""
    validate_environment(environment)
    
    success = await cache_service.disable_cache(environment)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to disable cache")
    
    # Broadcast cache update to connected clients
    await manager.broadcast({
        "type": "cache_updated",
        "environment": environment,
        "enabled": False,
        "timestamp": time.time()
    })
    
    return {"success": True, "message": "Cache disabled"}


@app.post("/api/cache/{environment}/enable")
async def enable_cache(environment: str):
    """Enable cache for environment"""
    validate_environment(environment)
    
    success = await cache_service.enable_cache(environment)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to enable cache")
    
    # Broadcast cache update to connected clients
    await manager.broadcast({
        "type": "cache_updated",
        "environment": environment,
        "enabled": True,
        "timestamp": time.time()
    })
    
    return {"success": True, "message": "Cache enabled"}


@app.post("/api/cache/{environment}/clear")
async def clear_cache(environment: str, pattern: Optional[str] = Query(None)):
    """Clear cache for environment"""
    validate_environment(environment)
    
    result = await cache_service.clear_cache(environment, pattern)
    
    # Broadcast cache clear to connected clients
    await manager.broadcast({
        "type": "cache_cleared",
        "environment": environment,
        "pattern": pattern,
        "cleared_entries": result.get("cleared_entries", 0),
        "timestamp": time.time()
    })
    
    return result


@app.get("/api/cache/{environment}/compliance")
async def validate_cache_compliance(environment: str):
    """Validate cache compliance"""
    validate_environment(environment)
    
    return await cache_service.validate_compliance(environment)


# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time admin updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Send periodic status updates
            await websocket.receive_text()  # Keep connection alive
            
            # Send system overview every 30 seconds
            overview = await status_service.get_system_overview()
            await websocket.send_json({
                "type": "status_update",
                "data": overview,
                "timestamp": time.time()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Health check
@app.get("/health")
async def health_check():
    """Admin service health check"""
    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))
    return {
        "status": "ok",
        "service": "admin",
        "timestamp": time.time(),
        "environment": env,
        "cors": get_cors_health_status(env),
        "tls": get_tls_health_status(env),
    }


if __name__ == "__main__":
    import uvicorn
    import asyncio
    from src_common.tls_security import run_with_tls
    
    async def main():
        # Get port from environment
        port = int(os.getenv("ADMIN_PORT", 8090))
        env = os.getenv("APP_ENV", "dev")
        
        logger.info(f"Starting TTRPG Center Admin Console on port {port} ({env})")
        
        # Configure TLS if available
        try:
            app_with_tls, cert_path, key_path = await create_app_with_tls(app, env)
            if cert_path and key_path:
                logger.info("Starting with TLS/HTTPS support")
                run_with_tls(app_with_tls, cert_path, key_path, port)
            else:
                logger.info("Starting without TLS (development mode)")
                uvicorn.run(
                    app_with_tls,
                    host="0.0.0.0",
                    port=port,
                    log_level="info",
                    reload=env == "dev"
                )
        except Exception as e:
            logger.error(f"TLS setup failed: {e}")
            logger.info("Falling back to basic HTTP server")
            uvicorn.run(
                app,
                host="0.0.0.0",
                port=port,
                log_level="info",
                reload=env == "dev"
            )
    
    asyncio.run(main())
