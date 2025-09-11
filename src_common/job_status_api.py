"""
P2.1: Job Status API Endpoints

FastAPI endpoints for real-time job status queries and WebSocket updates.
Provides REST API for job monitoring and real-time dashboard integration.
"""

from __future__ import annotations

import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .job_status_store import JobStatusStore, JobStatusRecord, get_job_store
from .ttrpg_logging import get_logger


class JobStatusResponse(BaseModel):
    """API response model for job status"""
    job_id: str
    source_path: str
    environment: str
    status: str
    
    # Timing
    queued_time: float
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    processing_time: Optional[float] = None
    wait_time: Optional[float] = None
    
    # Progress
    current_pass: Optional[str] = None
    progress_percentage: float = 0.0
    estimated_completion_time: Optional[float] = None
    
    # Details
    passes: Dict[str, Dict[str, Any]] = {}
    error_message: Optional[str] = None
    artifacts_path: Optional[str] = None
    thread_name: Optional[str] = None
    created_at: str


class JobStatisticsResponse(BaseModel):
    """API response model for job statistics"""
    active_jobs: int
    total_completed: int
    successful: int
    failed: int
    success_rate: float
    average_processing_time: float
    environment: Optional[str] = None


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = get_logger(__name__)
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected, total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.logger.info(f"WebSocket disconnected, remaining connections: {len(self.active_connections)}")
    
    async def broadcast_job_update(self, job_status: JobStatusRecord):
        """Broadcast job status update to all connected clients"""
        if not self.active_connections:
            return
            
        message = {
            "type": "job_update",
            "data": {
                "job_id": job_status.job_id,
                "status": job_status.status,
                "progress_percentage": job_status.progress_percentage,
                "current_pass": job_status.current_pass,
                "estimated_completion_time": job_status.estimated_completion_time,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        # Send to all connections, remove failed ones
        failed_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                self.logger.error(f"Failed to send WebSocket message: {e}")
                failed_connections.append(connection)
        
        # Clean up failed connections
        for connection in failed_connections:
            self.disconnect(connection)
    
    async def broadcast_statistics_update(self, stats: Dict[str, Any]):
        """Broadcast job statistics update"""
        if not self.active_connections:
            return
            
        message = {
            "type": "statistics_update",
            "data": {
                **stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        failed_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                failed_connections.append(connection)
        
        for connection in failed_connections:
            self.disconnect(connection)


# Global WebSocket manager
websocket_manager = WebSocketManager()


def create_job_status_api(app: FastAPI):
    """Add job status API endpoints to FastAPI app"""
    
    logger = get_logger(__name__)
    
    @app.get("/api/jobs/status/{job_id}", response_model=JobStatusResponse)
    async def get_job_status(job_id: str):
        """Get status for a specific job"""
        store = await get_job_store()
        job_status = store.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return JobStatusResponse(
            job_id=job_status.job_id,
            source_path=job_status.source_path,
            environment=job_status.environment,
            status=job_status.status,
            queued_time=job_status.queued_time,
            start_time=job_status.start_time,
            end_time=job_status.end_time,
            processing_time=job_status.processing_time,
            wait_time=job_status.wait_time,
            current_pass=job_status.current_pass,
            progress_percentage=job_status.progress_percentage,
            estimated_completion_time=job_status.estimated_completion_time,
            passes=job_status.passes or {},
            error_message=job_status.error_message,
            artifacts_path=job_status.artifacts_path,
            thread_name=job_status.thread_name,
            created_at=job_status.created_at
        )
    
    @app.get("/api/jobs/active", response_model=List[JobStatusResponse])
    async def get_active_jobs(environment: Optional[str] = Query(None)):
        """Get all currently active jobs"""
        store = await get_job_store()
        active_jobs = store.get_active_jobs()
        
        # Filter by environment if specified
        if environment:
            active_jobs = [job for job in active_jobs if job.environment == environment]
        
        return [
            JobStatusResponse(
                job_id=job.job_id,
                source_path=job.source_path,
                environment=job.environment,
                status=job.status,
                queued_time=job.queued_time,
                start_time=job.start_time,
                end_time=job.end_time,
                processing_time=job.processing_time,
                wait_time=job.wait_time,
                current_pass=job.current_pass,
                progress_percentage=job.progress_percentage,
                estimated_completion_time=job.estimated_completion_time,
                passes=job.passes or {},
                error_message=job.error_message,
                artifacts_path=job.artifacts_path,
                thread_name=job.thread_name,
                created_at=job.created_at
            )
            for job in active_jobs
        ]
    
    @app.get("/api/jobs/history", response_model=List[JobStatusResponse])
    async def get_job_history(
        limit: int = Query(50, ge=1, le=200),
        environment: Optional[str] = Query(None)
    ):
        """Get recent job execution history"""
        store = await get_job_store()
        history = store.get_job_history(limit=limit, environment=environment)
        
        return [
            JobStatusResponse(
                job_id=job.job_id,
                source_path=job.source_path,
                environment=job.environment,
                status=job.status,
                queued_time=job.queued_time,
                start_time=job.start_time,
                end_time=job.end_time,
                processing_time=job.processing_time,
                wait_time=job.wait_time,
                current_pass=job.current_pass,
                progress_percentage=job.progress_percentage,
                estimated_completion_time=job.estimated_completion_time,
                passes=job.passes or {},
                error_message=job.error_message,
                artifacts_path=job.artifacts_path,
                thread_name=job.thread_name,
                created_at=job.created_at
            )
            for job in history
        ]
    
    @app.get("/api/jobs/statistics", response_model=JobStatisticsResponse)
    async def get_job_statistics(environment: Optional[str] = Query(None)):
        """Get job execution statistics"""
        store = await get_job_store()
        stats = store.get_job_statistics(environment=environment)
        
        return JobStatisticsResponse(**stats)
    
    @app.websocket("/ws/jobs")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time job status updates"""
        await websocket_manager.connect(websocket)
        
        try:
            # Send initial data
            store = await get_job_store()
            active_jobs = store.get_active_jobs()
            stats = store.get_job_statistics()
            
            await websocket.send_text(json.dumps({
                "type": "initial_data",
                "data": {
                    "active_jobs": len(active_jobs),
                    "statistics": stats,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }))
            
            # Keep connection alive and handle messages
            while True:
                data = await websocket.receive_text()
                # Echo back for now - can be extended for client commands
                await websocket.send_text(f"Received: {data}")
                
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            websocket_manager.disconnect(websocket)


class JobStatusProgressCallback:
    """Progress callback that updates job status store and broadcasts updates"""
    
    def __init__(self, store: JobStatusStore):
        self.store = store
        self.logger = get_logger(__name__)
    
    async def on_job_start(self, job_progress):
        """Update job status when job starts"""
        try:
            self.store.update_job_from_progress(job_progress)
            job_status = self.store.get_job_status(job_progress.job_id)
            if job_status:
                await websocket_manager.broadcast_job_update(job_status)
        except Exception as e:
            self.logger.error(f"Failed to update job start status: {e}")
    
    async def on_pass_start(self, job_progress, pass_progress):
        """Update job status when pass starts"""
        try:
            self.store.update_job_from_progress(job_progress)
            job_status = self.store.get_job_status(job_progress.job_id)
            if job_status:
                await websocket_manager.broadcast_job_update(job_status)
        except Exception as e:
            self.logger.error(f"Failed to update pass start status: {e}")
    
    async def on_pass_progress(self, job_progress, pass_progress, **metrics):
        """Update job status during pass execution"""
        try:
            self.store.update_job_from_progress(job_progress)
            job_status = self.store.get_job_status(job_progress.job_id)
            if job_status:
                await websocket_manager.broadcast_job_update(job_status)
        except Exception as e:
            self.logger.error(f"Failed to update pass progress status: {e}")
    
    async def on_pass_complete(self, job_progress, pass_progress):
        """Update job status when pass completes"""
        try:
            self.store.update_job_from_progress(job_progress)
            job_status = self.store.get_job_status(job_progress.job_id)
            if job_status:
                await websocket_manager.broadcast_job_update(job_status)
        except Exception as e:
            self.logger.error(f"Failed to update pass completion status: {e}")
    
    async def on_pass_failed(self, job_progress, pass_progress):
        """Update job status when pass fails"""
        try:
            self.store.update_job_from_progress(job_progress)
            job_status = self.store.get_job_status(job_progress.job_id)
            if job_status:
                await websocket_manager.broadcast_job_update(job_status)
        except Exception as e:
            self.logger.error(f"Failed to update pass failure status: {e}")
    
    async def on_job_complete(self, job_progress):
        """Update job status when job completes"""
        try:
            self.store.update_job_from_progress(job_progress)
            job_status = self.store.get_job_status(job_progress.job_id)
            if job_status:
                await websocket_manager.broadcast_job_update(job_status)
            
            # Broadcast updated statistics
            stats = self.store.get_job_statistics()
            await websocket_manager.broadcast_statistics_update(stats)
            
        except Exception as e:
            self.logger.error(f"Failed to update job completion status: {e}")