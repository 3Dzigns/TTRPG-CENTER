# src_common/app.py
"""
Main FastAPI application for TTRPG Center.
Provides health checks, WebSocket support, and environment-aware configuration.
"""

import os
import time
import subprocess
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .ttrpg_logging import setup_logging, get_logger, LogContext
from .orchestrator.service import rag_router


# Initialize logging
logger = setup_logging()


class TTRPGApp:
    """Main application class for TTRPG Center."""
    
    def __init__(self):
        self.app = FastAPI(
            title="TTRPG Center",
            description="AI-powered tabletop RPG content management and query system",
            version="0.1.0"
        )
        self.setup_middleware()
        self.setup_routes()
        self.active_websockets = []
        # Start background scheduler (if enabled)
        self._maybe_start_scheduler()
        
    def setup_middleware(self):
        """Configure middleware for the application."""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Logging middleware
        @self.app.middleware("http")
        async def log_requests(request, call_next):
            start_time = time.time()
            
            with LogContext(
                path=str(request.url.path),
                method=request.method,
                client_ip=request.client.host if request.client else None
            ):
                logger.info(f"Request started: {request.method} {request.url.path}")
                
                response = await call_next(request)

                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Request completed: {request.method} {request.url.path}",
                    extra={
                        'status_code': response.status_code,
                        'duration_ms': duration_ms
                    }
                )
                # Apply simple Cache-Control policy (Phase 0 cache-control)
                try:
                    ttl = int(os.getenv('CACHE_TTL_SECONDS', '0') or '0')
                except Exception:
                    ttl = 0
                if ttl <= 0:
                    response.headers['Cache-Control'] = 'no-store'
                else:
                    response.headers['Cache-Control'] = f'private, max-age={ttl}'
                
            return response

    def setup_routes(self):
        """Configure application routes."""

        # Phase 2: RAG endpoints
        self.app.include_router(rag_router, prefix="/rag")

        # Phase 3: Workflow endpoints
        try:
            from app_workflow import workflow_router
            from app_plan_run import plan_router
            self.app.include_router(workflow_router, prefix="/api")
            self.app.include_router(plan_router, prefix="/api")
            logger.info("Phase 3 workflow routes loaded")
        except ImportError as e:
            logger.warning(f"Phase 3 routes not available: {e}")

        # Phase 5: User UI routes (must come first for root route precedence)
        try:
            from src_common.user_routes import user_router
            self.app.include_router(user_router)
            logger.info("Phase 5 user routes loaded")
        except ImportError as e:
            logger.warning(f"Phase 5 user routes not available: {e}")

        # Phase 4: Admin UI routes (prefixed to avoid conflicts)
        try:
            from src_common.admin_routes import admin_router
            self.app.include_router(admin_router)
            logger.info("Phase 4 admin routes loaded")
        except ImportError as e:
            logger.warning(f"Phase 4 admin routes not available: {e}")

        # Static files and templates
        static_dir = Path("static")
        templates_dir = Path("templates")

        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        if templates_dir.exists():
            from fastapi.templating import Jinja2Templates
            templates = Jinja2Templates(directory=str(templates_dir))
            # Store templates for use in routes
            self.templates = templates

        @self.app.get("/healthz")
        async def health_check():
            """Health check endpoint."""
            env = os.getenv('APP_ENV', 'unknown')
            port = os.getenv('PORT', 'unknown')
            
            health_data = {
                "status": "ok",
                "environment": env,
                "port": port,
                "timestamp": time.time(),
                "version": "0.1.0"
            }
            
            logger.info("Health check requested", extra=health_data)
            return JSONResponse(content=health_data)
        
        # Root route removed - User UI will handle the root route
        
        @self.app.get("/status")
        async def system_status():
            """Detailed system status endpoint."""
            env = os.getenv('APP_ENV', 'dev')
            
            # Check artifacts directory
            artifacts_path = Path(f"./artifacts/{env}")
            artifacts_exist = artifacts_path.exists()
            
            # Check logs directory
            logs_path = Path(f"./env/{env}/logs")
            logs_exist = logs_path.exists()
            
            status_data = {
                "environment": env,
                "timestamp": time.time(),
                "directories": {
                    "artifacts": str(artifacts_path),
                    "artifacts_exists": artifacts_exist,
                    "logs": str(logs_path),
                    "logs_exists": logs_exist
                },
                "websockets": {
                    "active_connections": len(self.active_websockets)
                },
                "configuration": {
                    "port": os.getenv('PORT'),
                    "log_level": os.getenv('LOG_LEVEL', 'INFO'),
                    "cache_ttl": os.getenv('CACHE_TTL_SECONDS', '0')
                }
            }
            
            logger.info("System status requested", extra={'environment': env})
            return JSONResponse(content=status_data)
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.active_websockets.append(websocket)
            
            logger.info("WebSocket connection established", extra={
                'active_connections': len(self.active_websockets)
            })
            
            try:
                while True:
                    # Keep connection alive and handle incoming messages
                    data = await websocket.receive_text()
                    
                    # Echo back with timestamp for testing
                    response = {
                        "type": "echo",
                        "data": data,
                        "timestamp": time.time(),
                        "environment": os.getenv('APP_ENV', 'dev')
                    }
                    
                    await websocket.send_json(response)
                    
            except WebSocketDisconnect:
                if websocket in self.active_websockets:
                    self.active_websockets.remove(websocket)
                
                logger.info("WebSocket connection closed", extra={
                    'active_connections': len(self.active_websockets)
                })
        
        @self.app.post("/broadcast")
        async def broadcast_message(message: Dict[str, Any]):
            """Broadcast message to all connected WebSocket clients."""
            if not self.active_websockets:
                return {"message": "No active WebSocket connections", "sent": 0}
            
            broadcast_data = {
                "type": "broadcast",
                "message": message,
                "timestamp": time.time(),
                "environment": os.getenv('APP_ENV', 'dev')
            }
            
            sent_count = 0
            disconnected = []
            
            for websocket in self.active_websockets:
                try:
                    await websocket.send_json(broadcast_data)
                    sent_count += 1
                except:
                    # Connection is dead, mark for removal
                    disconnected.append(websocket)
            
            # Remove disconnected clients
            for websocket in disconnected:
                if websocket in self.active_websockets:
                    self.active_websockets.remove(websocket)
            
            logger.info(f"Broadcast sent to {sent_count} clients", extra={
                'sent_count': sent_count,
                'disconnected_count': len(disconnected)
            })
            
            return {
                "message": "Broadcast sent",
                "sent": sent_count,
                "active_connections": len(self.active_websockets)
            }

        @self.app.post("/api/admin/ingestion/run")
        async def admin_run_nightly(payload: Dict[str, Any]):
            """Kick off an ad hoc nightly ingestion for the specified environment.

            Body JSON:
            - env: dev|test|prod (default: current APP_ENV)
            - uploads: optional path (defaults to UPLOADS_DIR or /data/uploads)
            - artifacts_base: optional path (defaults to ARTIFACTS_PATH or /app/artifacts)
            - max_concurrent: optional int (defaults to NIGHTLY_MAX_CONCURRENT or 2)
            """
            try:
                env = (payload or {}).get('env') or os.getenv('APP_ENV', 'dev')
                uploads = (payload or {}).get('uploads') or os.getenv('UPLOADS_DIR', '/data/uploads')
                artifacts = (payload or {}).get('artifacts_base') or os.getenv('ARTIFACTS_PATH', '/app/artifacts')
                max_conc = str((payload or {}).get('max_concurrent') or os.getenv('NIGHTLY_MAX_CONCURRENT', '2'))

                ts = time.strftime('%Y%m%d_%H%M%S')
                log_dir = os.path.join('env', env, 'logs')
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.abspath(os.path.join(log_dir, f'nightly_adhoc_{ts}.log'))

                cmd = [
                    os.getenv('PYTHON', 'python'),
                    'scripts/run_nightly_ingestion.py',
                    '--env', env,
                    '--uploads', uploads,
                    '--artifacts-base', artifacts,
                    '--log-file', log_file,
                    '--max-concurrent', max_conc
                ]

                # Spawn non-blocking so API returns immediately
                proc = subprocess.Popen(cmd)

                return JSONResponse(content={
                    'status': 'started',
                    'env': env,
                    'pid': proc.pid,
                    'log_file': log_file,
                    'command': ' '.join(cmd),
                })
            except Exception as e:
                logger.error(f"Failed to start ad hoc nightly run: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _maybe_start_scheduler(self) -> None:
        """Start APScheduler background jobs for nightly ingestion and log purge if enabled."""
        enabled = os.getenv('ENABLE_SCHEDULER', 'false').strip().lower() in ('1','true','yes')
        if not enabled:
            return
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except Exception as e:
            logger.warning(f"Scheduler requested but APScheduler not available: {e}")
            return

        scheduler = BackgroundScheduler()

        def run_nightly() -> None:
            try:
                env = os.getenv('APP_ENV', 'dev')
                uploads = os.getenv('UPLOADS_DIR', '/data/uploads')
                artifacts = os.getenv('ARTIFACTS_PATH', '/app/artifacts')
                ts = time.strftime('%Y%m%d_%H%M%S')
                log_dir = '/var/log/ttrpg'
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, f'nightly_{ts}.log')
                max_conc = os.getenv('NIGHTLY_MAX_CONCURRENT', '2')
                cmd = [
                    os.getenv('PYTHON', 'python'),
                    'scripts/run_nightly_ingestion.py',
                    '--env', env,
                    '--uploads', uploads,
                    '--artifacts-base', artifacts,
                    '--log-file', log_file,
                    '--max-concurrent', str(max_conc)
                ]
                logger.info(f"Scheduler: starting nightly ingestion: {' '.join(cmd)}")
                subprocess.run(cmd, check=False)
            except Exception as e:
                logger.error(f"Scheduler nightly ingestion failed: {e}")

        def purge_logs() -> None:
            try:
                log_dir = '/var/log/ttrpg'
                retention = int(os.getenv('LOG_RETENTION_DAYS', '5') or '5')
                now = time.time()
                if not os.path.isdir(log_dir):
                    return
                removed = 0
                for name in os.listdir(log_dir):
                    path = os.path.join(log_dir, name)
                    try:
                        if os.path.isfile(path):
                            age_days = (now - os.path.getmtime(path)) / 86400.0
                            if age_days > retention:
                                os.remove(path)
                                removed += 1
                    except Exception:
                        continue
                if removed:
                    logger.info(f"Scheduler: purged {removed} old log files from {log_dir}")
            except Exception as e:
                logger.error(f"Scheduler log purge failed: {e}")

        ing_cron = os.getenv('INGEST_CRON', '').strip()
        if ing_cron:
            try:
                parts = ing_cron.split()
                trigger = CronTrigger(minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4])
                scheduler.add_job(run_nightly, trigger, id='nightly_ingest', replace_existing=True)
            except Exception as e:
                logger.warning(f"Invalid INGEST_CRON '{ing_cron}': {e}; using default 02:00")
                scheduler.add_job(run_nightly, CronTrigger(hour=2, minute=0), id='nightly_ingest', replace_existing=True)
        else:
            scheduler.add_job(run_nightly, CronTrigger(hour=2, minute=0), id='nightly_ingest', replace_existing=True)

        scheduler.add_job(purge_logs, CronTrigger(hour=3, minute=30), id='purge_logs', replace_existing=True)
        scheduler.start()
        logger.info("Background scheduler started (nightly ingestion + log purge)")
    
    async def broadcast_to_websockets(self, message: Dict[str, Any]):
        """Utility method to broadcast messages to all WebSocket connections."""
        if not self.active_websockets:
            return
        
        disconnected = []
        for websocket in self.active_websockets:
            try:
                await websocket.send_json(message)
            except:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            if websocket in self.active_websockets:
                self.active_websockets.remove(websocket)


# Create the application instance
ttrpg_app = TTRPGApp()
app = ttrpg_app.app


# Mock ingestion job for Phase 0 testing
@app.post("/mock-ingest/{job_id}")
async def run_mock_ingestion(job_id: str):
    """Mock ingestion job for testing status flows."""
    from .mock_ingest import run_mock_job
    
    try:
        result = await run_mock_job(job_id, ttrpg_app.broadcast_to_websockets)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Mock ingestion failed: {str(e)}", extra={'job_id': job_id})
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    # Direct run configuration
    env = os.getenv('APP_ENV', 'dev')
    port = int(os.getenv('PORT', 8000))
    
    logger.info(f"Starting TTRPG Center directly in {env} environment on port {port}")
    
    uvicorn.run(
        "src_common.app:app",
        host="0.0.0.0",
        port=port,
        reload=(env == 'dev'),
        log_config=None  # We handle logging ourselves
    )
