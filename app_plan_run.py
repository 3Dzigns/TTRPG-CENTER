# app_plan_run.py
"""
Plan & Run API - Phase 3 Planning and Execution Endpoints  
US-314: /plan & /run Endpoints implementation
"""

import os
import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src_common.logging import get_logger
from src_common.graph.store import GraphStore
from src_common.planner.plan import TaskPlanner, plan_from_goal
from src_common.planner.budget import BudgetManager, PolicyEnforcer
from src_common.runtime.execute import WorkflowExecutor
from src_common.runtime.state import WorkflowStateStore

logger = get_logger(__name__)

# Initialize components
plan_router = APIRouter()

# Global instances (in production, would use dependency injection)
graph_store = GraphStore()
budget_manager = BudgetManager()
policy_enforcer = PolicyEnforcer(budget_manager)
state_store = WorkflowStateStore()
task_planner = TaskPlanner(graph_store)
executor = WorkflowExecutor(state_store)

# Request/Response models
class PlanRequest(BaseModel):
    goal: str
    constraints: Optional[Dict[str, Any]] = None
    user_role: str = "player"

class RunRequest(BaseModel):
    goal: Optional[str] = None
    plan_id: Optional[str] = None
    user_role: str = "player"

@plan_router.get("/ping")
async def plan_ping():
    """Health check for planning service"""
    return {
        "status": "ok",
        "component": "planning", 
        "environment": os.getenv("APP_ENV", "dev")
    }

@plan_router.post("/plan")
async def create_plan(request: PlanRequest):
    """
    Create workflow plan from goal with cost estimation and checkpoints
    
    Args:
        request: Plan request with goal and constraints
        
    Returns:
        Workflow plan with estimates and checkpoints
    """
    
    try:
        logger.info(f"Creating plan for goal: {request.goal[:100]}...")
        
        # Create workflow plan
        plan = task_planner.plan_from_goal(request.goal, request.constraints)
        
        # Validate plan structure
        is_valid, validation_errors = task_planner.validate_plan(plan)
        if not is_valid:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid plan generated",
                    "validation_errors": validation_errors,
                    "goal": request.goal
                }
            )
        
        # Check budget compliance
        is_approved, policy_response = policy_enforcer.enforce_plan(plan.to_dict(), request.user_role)
        
        # Estimate costs
        estimate = budget_manager.estimate_workflow_cost([asdict(task) for task in plan.tasks])
        
        response = {
            "plan": plan.to_dict(),
            "estimate": estimate,
            "checkpoints": plan.checkpoints,
            "budget_analysis": policy_response,
            "validation": {
                "is_valid": is_valid,
                "errors": validation_errors
            }
        }
        
        # Add approval checkpoint if needed
        if not is_approved:
            checkpoint = policy_enforcer.create_approval_checkpoint(
                plan.id, 
                "Budget limits exceeded", 
                estimate
            )
            response["approval_checkpoint"] = checkpoint
        
        logger.info(f"Plan {plan.id} created successfully with {len(plan.tasks)} tasks")
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@plan_router.post("/run")
async def run_workflow(request: RunRequest):
    """
    Execute workflow from goal or existing plan
    
    Args:
        request: Run request with goal or plan_id
        
    Returns:
        Workflow execution ID and initial status
    """
    
    try:
        # Determine what to run
        if request.plan_id:
            # Load existing plan (simplified - would load from plan store)
            logger.info(f"Running existing plan: {request.plan_id}")
            
            # For now, create a simple plan structure
            # In production, this would load the actual stored plan
            plan_dict = {
                "id": request.plan_id,
                "goal": "Loaded plan execution",
                "tasks": [
                    {
                        "id": "task:loaded:1",
                        "type": "reasoning",
                        "name": "Execute Loaded Plan",
                        "description": "Execute previously created plan",
                        "dependencies": [],
                        "tool": "llm",
                        "model": "claude-3-haiku",
                        "prompt": "Execute loaded workflow plan",
                        "parameters": {},
                        "estimated_tokens": 1000,
                        "estimated_time_s": 10
                    }
                ]
            }
            
        elif request.goal:
            # Create new plan from goal
            logger.info(f"Creating and running new plan for: {request.goal[:100]}...")
            
            plan = task_planner.plan_from_goal(request.goal, request.constraints or {})
            
            # Check budget compliance
            is_approved, policy_response = policy_enforcer.enforce_plan(plan.to_dict(), request.user_role)
            
            if not is_approved and not policy_response.get("optimized_plan"):
                # Return approval requirement instead of running
                return JSONResponse(
                    status_code=402,  # Payment Required (budget exceeded)
                    content={
                        "error": "Plan requires approval due to budget constraints",
                        "plan_id": plan.id,
                        "approval_checkpoint": policy_enforcer.create_approval_checkpoint(
                            plan.id,
                            "Budget approval required",
                            policy_response["estimate"]
                        ),
                        "budget_analysis": policy_response
                    }
                )
            
            # Use optimized plan if available
            plan_dict = policy_response.get("optimized_plan", plan.to_dict())
            
        else:
            raise HTTPException(status_code=400, detail="Either goal or plan_id must be provided")
        
        # Execute workflow
        execution_result = await executor.run_plan(plan_dict)
        
        response = {
            "workflow_id": execution_result["workflow_id"],
            "status": execution_result["status"],
            "started_at": execution_result.get("started_at"),
            "plan_id": plan_dict.get("id"),
            "goal": plan_dict.get("goal"),
            "message": "Workflow execution started",
            "monitor_url": f"/workflow/{execution_result['workflow_id']}"
        }
        
        # Include execution details if completed quickly
        if execution_result["status"] in ["completed", "failed", "error"]:
            response.update({
                "completed_at": execution_result.get("completed_at"),
                "duration_s": execution_result.get("duration_s"),
                "task_results": len(execution_result.get("tasks", {})),
                "artifacts": len(execution_result.get("artifacts", []))
            })
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@plan_router.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    """
    Retrieve stored plan by ID
    
    Args:
        plan_id: Plan ID to retrieve
        
    Returns:
        Stored plan data
    """
    
    # Simplified implementation - in production would have plan persistence
    return JSONResponse(content={
        "plan_id": plan_id,
        "message": "Plan retrieval not yet implemented - plans are ephemeral",
        "status": "not_found"
    })

@plan_router.post("/plan/{plan_id}/estimate")
async def estimate_plan_cost(plan_id: str):
    """
    Re-estimate costs for an existing plan
    
    Args:
        plan_id: Plan ID to estimate
        
    Returns:
        Updated cost estimates
    """
    
    # Simplified implementation
    return JSONResponse(content={
        "plan_id": plan_id,
        "message": "Plan cost estimation not yet implemented",
        "estimate": {
            "tokens": 0,
            "cost_usd": 0.0,
            "time_s": 0
        }
    })

@plan_router.get("/models")
async def list_available_models():
    """
    List available models and their characteristics
    
    Returns:
        Available models with cost and performance data
    """
    
    try:
        models_info = []
        
        for model_name, model_config in budget_manager.models.items():
            models_info.append({
                "name": model_config.name,
                "provider": model_config.provider,
                "cost_per_1k_tokens": model_config.cost_per_1k_tokens,
                "latency_ms": model_config.latency_ms,
                "context_window": model_config.context_window,
                "capabilities": model_config.capabilities
            })
        
        return JSONResponse(content={
            "models": models_info,
            "total_models": len(models_info)
        })
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@plan_router.get("/budget/roles")
async def get_budget_roles():
    """
    Get budget constraints by user role
    
    Returns:
        Budget limits for different user roles
    """
    
    try:
        roles_info = {}
        
        for role, budget in budget_manager.default_budgets.items():
            roles_info[role] = {
                "max_total_tokens": budget.max_total_tokens,
                "max_total_cost_usd": budget.max_total_cost_usd,
                "max_time_s": budget.max_time_s,
                "max_parallel_tasks": budget.max_parallel_tasks
            }
        
        return JSONResponse(content={
            "roles": roles_info,
            "default_role": "player"
        })
        
    except Exception as e:
        logger.error(f"Error getting budget roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))
