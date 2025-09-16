# app_workflow.py
"""
Workflow State API - Phase 3 Workflow Management Endpoints
US-306: Workflow State & Artifacts API implementation
"""

import os
import time
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse

from src_common.ttrpg_logging import get_logger
from src_common.runtime.state import WorkflowStateStore
from src_common.runtime.execute import WorkflowExecutor

logger = get_logger(__name__)

# Initialize workflow components
workflow_router = APIRouter()
state_store = WorkflowStateStore()
executor = WorkflowExecutor(state_store)

@workflow_router.get("/ping")
async def workflow_ping():
    """Health check for workflow service"""
    return {
        "status": "ok", 
        "component": "workflow",
        "environment": os.getenv("APP_ENV", "dev")
    }

@workflow_router.get("/workflow/{workflow_id}")
async def get_workflow(workflow_id: str):
    """
    Get workflow status, progress, and artifacts
    
    Returns:
        Workflow state with task statuses and artifact links
    """
    
    try:
        workflow_state = await state_store.get_workflow_state(workflow_id)
        
        if not workflow_state:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        
        # Get artifacts
        artifacts = await state_store.get_workflow_artifacts(workflow_id)
        
        # Build response
        response = {
            "workflow_id": workflow_state.id,
            "plan_id": workflow_state.plan_id,
            "goal": workflow_state.goal,
            "status": workflow_state.status,
            "started_at": workflow_state.started_at,
            "completed_at": workflow_state.completed_at,
            "duration_s": workflow_state.duration_s,
            "tasks": {},
            "artifacts": [],
            "checkpoints": workflow_state.checkpoints
        }
        
        # Add task information
        for task_id, task_state in workflow_state.tasks.items():
            response["tasks"][task_id] = {
                "id": task_state.id,
                "status": task_state.status.value if hasattr(task_state.status, 'value') else str(task_state.status),
                "dependencies": task_state.dependencies,
                "started_at": task_state.started_at,
                "completed_at": task_state.completed_at,
                "duration_s": task_state.duration_s,
                "retries": task_state.retries,
                "error": task_state.error
            }
        
        # Add artifact information
        for artifact in artifacts:
            response["artifacts"].append({
                "id": artifact["id"],
                "task_id": artifact["task_id"],
                "created_at": artifact["created_at"],
                "download_url": f"/workflow/{workflow_id}/artifacts/{artifact['id']}"
            })
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@workflow_router.get("/workflow/{workflow_id}/artifacts/{artifact_id}")
async def download_artifact(workflow_id: str, artifact_id: str):
    """
    Download workflow artifact
    
    Returns:
        Artifact file or JSON data
    """
    
    try:
        artifact = await state_store.get_artifact(artifact_id)
        
        if not artifact:
            raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")
        
        # Verify artifact belongs to requested workflow
        if artifact.get("workflow_id") != workflow_id:
            raise HTTPException(status_code=403, detail="Artifact does not belong to specified workflow")
        
        # Return artifact data as JSON
        return JSONResponse(content=artifact["data"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading artifact {artifact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@workflow_router.post("/workflow/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    """
    Resume a failed workflow from last checkpoint
    
    Returns:
        Resume execution results
    """
    
    try:
        # Check if workflow exists
        workflow_state = await state_store.get_workflow_state(workflow_id)
        if not workflow_state:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        
        # Check if workflow can be resumed
        if workflow_state.status in ["completed", "running"]:
            return JSONResponse(content={
                "workflow_id": workflow_id,
                "message": f"Workflow is already {workflow_state.status}",
                "can_resume": False
            })
        
        # Resume execution
        result = await executor.resume_workflow(workflow_id)
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@workflow_router.post("/workflow/{workflow_id}/approve")
async def approve_checkpoint(
    workflow_id: str, 
    checkpoint: str = Query(...),
    choice: str = Query(..., regex="^[AB]$")
):
    """
    Approve workflow checkpoint decision
    
    Args:
        workflow_id: Workflow ID
        checkpoint: Checkpoint ID requiring approval
        choice: Decision choice (A or B)
        
    Returns:
        Approval confirmation
    """
    
    try:
        # Load workflow state
        workflow_state = await state_store.get_workflow_state(workflow_id)
        if not workflow_state:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        
        # Find checkpoint
        checkpoint_data = None
        for cp in workflow_state.checkpoints:
            if cp.get("checkpoint_id") == checkpoint:
                checkpoint_data = cp
                break
        
        if not checkpoint_data:
            raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint} not found")
        
        # Record approval
        approval_record = {
            "checkpoint_id": checkpoint,
            "choice": choice,
            "approved_at": time.time(),
            "approver": "user"  # In production, would extract from auth
        }
        
        # Update checkpoint status
        checkpoint_data["status"] = "approved"
        checkpoint_data["approval"] = approval_record
        
        # Save updated state
        await state_store.save_workflow_state(workflow_state)
        
        logger.info(f"Approved checkpoint {checkpoint} for workflow {workflow_id} with choice {choice}")
        
        return JSONResponse(content={
            "workflow_id": workflow_id,
            "checkpoint_id": checkpoint,
            "choice": choice,
            "status": "approved",
            "message": f"Checkpoint approved with choice {choice}"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving checkpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@workflow_router.get("/workflows")
async def list_workflows(
    status: Optional[str] = Query(None, regex="^(running|completed|failed|error)$"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List workflows with optional filtering
    
    Args:
        status: Optional status filter
        limit: Maximum number of workflows to return
        
    Returns:
        List of workflow summaries
    """
    
    try:
        workflows = await state_store.list_workflows(status_filter=status)
        
        # Apply limit
        limited_workflows = workflows[:limit]
        
        return JSONResponse(content={
            "workflows": limited_workflows,
            "total": len(workflows),
            "filtered": len(limited_workflows),
            "filter": {"status": status, "limit": limit}
        })
        
    except Exception as e:
        logger.error(f"Error listing workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@workflow_router.delete("/workflow/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """
    Delete workflow and all associated data
    
    Args:
        workflow_id: Workflow to delete
        
    Returns:
        Deletion confirmation
    """
    
    try:
        # Check if workflow exists
        workflow_state = await state_store.get_workflow_state(workflow_id)
        if not workflow_state:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        
        # Prevent deletion of running workflows
        if workflow_state.status == "running":
            raise HTTPException(status_code=400, detail="Cannot delete running workflow")
        
        # Delete workflow
        success = await state_store.delete_workflow(workflow_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete workflow")
        
        return JSONResponse(content={
            "workflow_id": workflow_id,
            "deleted": True,
            "message": "Workflow and artifacts deleted successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@workflow_router.get("/workflow/{workflow_id}/statistics")
async def get_workflow_statistics(workflow_id: str):
    """
    Get detailed statistics for workflow execution
    
    Returns:
        Execution statistics and performance metrics
    """
    
    try:
        workflow_state = await state_store.get_workflow_state(workflow_id)
        
        if not workflow_state:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
        
        # Calculate statistics
        task_statuses = {}
        total_retries = 0
        total_task_time = 0.0
        
        for task_state in workflow_state.tasks.values():
            status = task_state.status.value if hasattr(task_state.status, 'value') else str(task_state.status)
            task_statuses[status] = task_statuses.get(status, 0) + 1
            total_retries += task_state.retries
            if task_state.duration_s:
                total_task_time += task_state.duration_s
        
        artifacts = await state_store.get_workflow_artifacts(workflow_id)
        
        statistics = {
            "workflow_id": workflow_id,
            "goal": workflow_state.goal,
            "overall_status": workflow_state.status,
            "total_duration_s": workflow_state.duration_s,
            "task_statistics": {
                "total_tasks": len(workflow_state.tasks),
                "status_breakdown": task_statuses,
                "total_retries": total_retries,
                "average_task_time_s": total_task_time / len(workflow_state.tasks) if workflow_state.tasks else 0
            },
            "artifact_statistics": {
                "total_artifacts": len(artifacts),
                "artifact_types": {}
            },
            "checkpoints": {
                "total_checkpoints": len(workflow_state.checkpoints),
                "approved_checkpoints": len([cp for cp in workflow_state.checkpoints if cp.get("status") == "approved"])
            }
        }
        
        # Artifact type breakdown
        for artifact in artifacts:
            artifact_type = artifact.get("data", {}).get("type", "unknown")
            statistics["artifact_statistics"]["artifact_types"][artifact_type] = \
                statistics["artifact_statistics"]["artifact_types"].get(artifact_type, 0) + 1
        
        return JSONResponse(content=statistics)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))