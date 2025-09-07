# src_common/app.py
"""
Main FastAPI application for TTRPG Center.
Provides health checks, WebSocket support, and environment-aware configuration.
"""

import os
import time
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from .logging import setup_logging, get_logger, LogContext
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

        # Minimal WebUI: static assets under /ui
        static_dir = Path("static")
        if static_dir.exists():
            self.app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")

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
        
        @self.app.get("/")
        async def root():
            """Root endpoint with basic information."""
            return {
                "message": "TTRPG Center API",
                "environment": os.getenv('APP_ENV', 'dev'),
                "version": "0.1.0",
                "health_check": "/healthz"
            }
        
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
