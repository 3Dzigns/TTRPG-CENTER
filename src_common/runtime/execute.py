# src_common/runtime/execute.py
"""
DAG Executor with Retries - Phase 3 Workflow Execution
US-305: DAG Executor with Retries implementation
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from ..ttrpg_logging import get_logger
from .state import WorkflowStateStore, WorkflowState, TaskState as StateTaskState

logger = get_logger(__name__)

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"

@dataclass
class ExecutionResult:
    """Result of task execution"""
    task_id: str
    status: TaskStatus
    output: Any
    error: Optional[str]
    started_at: float
    completed_at: float
    duration_s: float
    retries: int
    tokens_used: int
    artifacts: List[Dict[str, Any]]

@dataclass
class RetryPolicy:
    """Retry configuration for tasks"""
    max_attempts: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 30.0
    exponential_base: float = 2.0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay before retry attempt"""
        delay = self.base_delay_s * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay_s)

class WorkflowExecutor:
    """
    Executes workflow plans with DAG dependencies, retries, and state tracking
    
    Supports:
    - Parallel execution of independent tasks
    - Retry with exponential backoff
    - State persistence and recovery
    - Idempotent task execution
    """
    
    def __init__(self, state_store: WorkflowStateStore, max_parallel: int = 3):
        self.state_store = state_store
        self.max_parallel = max_parallel
        self.default_retry_policy = RetryPolicy()
        
        # Task executors for different types
        self.task_executors = {
            "retrieval": self._execute_retrieval_task,
            "reasoning": self._execute_reasoning_task, 
            "computation": self._execute_computation_task,
            "verification": self._execute_verification_task,
            "synthesis": self._execute_synthesis_task
        }
    
    async def run_plan(self, plan: Dict[str, Any], task_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Execute a workflow plan with dependency management and retries
        
        Args:
            plan: Workflow plan dictionary
            task_fn: Optional custom task execution function
            
        Returns:
            Execution results dictionary
        """
        
        workflow_id = plan.get("id", f"wf:{uuid.uuid4().hex[:16]}")
        logger.info(f"Starting workflow execution: {workflow_id}")
        
        try:
            # Initialize workflow state
            workflow_state = WorkflowState(
                id=workflow_id,
                plan_id=plan.get("id"),
                goal=plan.get("goal", ""),
                status="running",
                started_at=time.time(),
                tasks={}
            )
            
            # Initialize task states
            tasks = plan.get("tasks", [])
            task_states = {}
            
            for task in tasks:
                task_state = StateTaskState(
                    id=task["id"],
                    status=TaskStatus.PENDING,
                    dependencies=task.get("dependencies", []),
                    retries=0,
                    created_at=time.time()
                )
                task_states[task["id"]] = task_state
                workflow_state.tasks[task["id"]] = task_state
            
            # Save initial state
            await self.state_store.save_workflow_state(workflow_state)
            
            # Execute DAG
            execution_results = await self._execute_dag(workflow_id, tasks, task_states, task_fn)
            
            # Update final workflow state
            all_succeeded = all(r.status == TaskStatus.SUCCEEDED for r in execution_results.values())
            workflow_state.status = "completed" if all_succeeded else "failed"
            workflow_state.completed_at = time.time()
            workflow_state.duration_s = workflow_state.completed_at - workflow_state.started_at
            
            await self.state_store.save_workflow_state(workflow_state)
            
            # Compile final results
            results = {
                "workflow_id": workflow_id,
                "status": workflow_state.status,
                "started_at": workflow_state.started_at,
                "completed_at": workflow_state.completed_at,
                "duration_s": workflow_state.duration_s,
                "tasks": {task_id: asdict(result) for task_id, result in execution_results.items()},
                "artifacts": self._collect_artifacts(execution_results)
            }
            
            logger.info(f"Workflow {workflow_id} completed with status: {workflow_state.status}")
            return results
            
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_id}: {e}")
            # Save error state
            workflow_state.status = "error"
            workflow_state.error = str(e)
            workflow_state.completed_at = time.time()
            await self.state_store.save_workflow_state(workflow_state)
            
            return {
                "workflow_id": workflow_id,
                "status": "error",
                "error": str(e),
                "started_at": workflow_state.started_at,
                "completed_at": time.time()
            }
    
    async def _execute_dag(self, workflow_id: str, tasks: List[Dict], task_states: Dict[str, StateTaskState], 
                          task_fn: Optional[Callable] = None) -> Dict[str, ExecutionResult]:
        """Execute DAG with dependency management"""
        
        execution_results = {}
        running_tasks = set()
        
        # Main execution loop
        while True:
            # Find ready tasks (dependencies satisfied)
            ready_tasks = self._find_ready_tasks(tasks, task_states, running_tasks)
            
            if not ready_tasks and not running_tasks:
                break  # All done
            
            # Start new tasks (respecting parallelism limit)
            while ready_tasks and len(running_tasks) < self.max_parallel:
                task = ready_tasks.pop(0)
                task_id = task["id"]
                
                # Skip if already completed
                if task_states[task_id].status in [TaskStatus.SUCCEEDED, TaskStatus.SKIPPED]:
                    continue
                
                # Start task execution
                running_tasks.add(task_id)
                task_states[task_id].status = TaskStatus.RUNNING
                task_states[task_id].started_at = time.time()
                
                # Execute task asynchronously
                asyncio.create_task(self._execute_single_task(
                    workflow_id, task, task_states[task_id], task_fn, execution_results, running_tasks
                ))
            
            # Brief wait before checking for more ready tasks
            await asyncio.sleep(0.1)
        
        return execution_results
    
    def _find_ready_tasks(self, tasks: List[Dict], task_states: Dict[str, StateTaskState], 
                         running_tasks: set) -> List[Dict]:
        """Find tasks ready for execution (dependencies satisfied)"""
        
        ready = []
        
        for task in tasks:
            task_id = task["id"]
            task_state = task_states[task_id]
            
            # Skip if already running or completed
            if (task_state.status != TaskStatus.PENDING or 
                task_id in running_tasks):
                continue
            
            # Check dependencies
            dependencies_satisfied = True
            for dep_id in task.get("dependencies", []):
                if (dep_id not in task_states or 
                    task_states[dep_id].status != TaskStatus.SUCCEEDED):
                    dependencies_satisfied = False
                    break
            
            if dependencies_satisfied:
                ready.append(task)
        
        return ready
    
    async def _execute_single_task(self, workflow_id: str, task: Dict, task_state: StateTaskState,
                                  custom_task_fn: Optional[Callable], results: Dict[str, ExecutionResult],
                                  running_tasks: set):
        """Execute a single task with retry logic"""
        
        task_id = task["id"]
        
        try:
            # Determine retry policy
            retry_policy = RetryPolicy(
                max_attempts=task.get("max_attempts", 3),
                base_delay_s=task.get("retry_delay_s", 1.0)
            )
            
            # Retry loop
            for attempt in range(1, retry_policy.max_attempts + 1):
                try:
                    task_state.retries = attempt - 1
                    
                    # Execute task
                    if custom_task_fn:
                        result = await custom_task_fn(task)
                    else:
                        result = await self._default_task_execution(task)
                    
                    # Success
                    execution_result = ExecutionResult(
                        task_id=task_id,
                        status=TaskStatus.SUCCEEDED,
                        output=result,
                        error=None,
                        started_at=task_state.started_at,
                        completed_at=time.time(),
                        duration_s=time.time() - task_state.started_at,
                        retries=attempt - 1,
                        tokens_used=task.get("estimated_tokens", 0),
                        artifacts=result.get("artifacts", []) if isinstance(result, dict) else []
                    )
                    
                    task_state.status = TaskStatus.SUCCEEDED
                    task_state.completed_at = execution_result.completed_at
                    task_state.output = result
                    
                    results[task_id] = execution_result
                    running_tasks.discard(task_id)
                    
                    logger.info(f"Task {task_id} completed successfully in {execution_result.duration_s:.1f}s")
                    return
                    
                except Exception as task_error:
                    logger.warning(f"Task {task_id} attempt {attempt} failed: {task_error}")
                    
                    if attempt < retry_policy.max_attempts:
                        # Wait before retry
                        delay = retry_policy.get_delay(attempt)
                        await asyncio.sleep(delay)
                    else:
                        # Final failure
                        execution_result = ExecutionResult(
                            task_id=task_id,
                            status=TaskStatus.FAILED,
                            output=None,
                            error=str(task_error),
                            started_at=task_state.started_at,
                            completed_at=time.time(),
                            duration_s=time.time() - task_state.started_at,
                            retries=retry_policy.max_attempts - 1,
                            tokens_used=0,
                            artifacts=[]
                        )
                        
                        task_state.status = TaskStatus.FAILED
                        task_state.completed_at = execution_result.completed_at
                        task_state.error = str(task_error)
                        
                        results[task_id] = execution_result
                        running_tasks.discard(task_id)
                        
                        # Mark dependent tasks as blocked
                        self._mark_dependents_blocked(task_id, task_states, results)
                        
                        logger.error(f"Task {task_id} failed after {retry_policy.max_attempts} attempts")
                        return
        
        except Exception as e:
            logger.error(f"Unexpected error executing task {task_id}: {e}")
            running_tasks.discard(task_id)
    
    async def _default_task_execution(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Default task execution logic"""
        
        task_type = task.get("type", "reasoning")
        executor_fn = self.task_executors.get(task_type, self._execute_reasoning_task)
        
        return await executor_fn(task)
    
    async def _execute_retrieval_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute retrieval task"""
        
        # Simulate retrieval (in real implementation, this would call the retriever)
        query = task.get("parameters", {}).get("query", task.get("description", ""))
        
        return {
            "type": "retrieval_result",
            "query": query,
            "chunks": [
                {"id": "chunk:1", "content": f"Retrieved content for: {query}", "score": 0.85}
            ],
            "total_chunks": 1
        }
    
    async def _execute_reasoning_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reasoning task"""
        
        # Simulate reasoning (in real implementation, this would call LLM)
        prompt = task.get("prompt", task.get("description", ""))
        
        return {
            "type": "reasoning_result",
            "prompt": prompt,
            "reasoning": f"Analyzed: {prompt}",
            "conclusion": f"Result for task: {task.get('name', 'Unknown')}"
        }
    
    async def _execute_computation_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute computation task"""
        
        # Simulate computation (dice rolls, DC calculations, etc.)
        params = task.get("parameters", {})
        
        return {
            "type": "computation_result",
            "inputs": params,
            "calculation": "Computed using task parameters", 
            "result": {"value": 42, "confidence": 0.95}  # Placeholder
        }
    
    async def _execute_verification_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute verification task"""
        
        # Simulate rule verification
        description = task.get("description", "")
        
        return {
            "type": "verification_result",
            "verified": description,
            "status": "passed",
            "violations": [],
            "rule_citations": [{"rule": "sample_rule", "page": 123}]
        }
    
    async def _execute_synthesis_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute synthesis task"""
        
        # Simulate final synthesis
        goal = task.get("parameters", {}).get("goal", task.get("description", ""))
        
        return {
            "type": "synthesis_result",
            "goal": goal,
            "answer": f"Synthesized answer for: {goal}",
            "sources": [{"source": "sample_source", "page": 456}],
            "artifacts": [{"type": "json", "content": {"result": "synthesized"}}]
        }
    
    def _mark_dependents_blocked(self, failed_task_id: str, task_states: Dict[str, StateTaskState], 
                                results: Dict[str, ExecutionResult]):
        """Mark tasks dependent on failed task as blocked"""
        
        for task_id, task_state in task_states.items():
            if (failed_task_id in task_state.dependencies and 
                task_state.status == TaskStatus.PENDING):
                
                task_state.status = TaskStatus.BLOCKED
                task_state.error = f"Dependency {failed_task_id} failed"
                task_state.completed_at = time.time()
                
                # Create blocked result
                blocked_result = ExecutionResult(
                    task_id=task_id,
                    status=TaskStatus.BLOCKED,
                    output=None,
                    error=f"Blocked by failed dependency: {failed_task_id}",
                    started_at=task_state.created_at,
                    completed_at=time.time(),
                    duration_s=0,
                    retries=0,
                    tokens_used=0,
                    artifacts=[]
                )
                
                results[task_id] = blocked_result
                logger.warning(f"Task {task_id} blocked by failed dependency {failed_task_id}")
    
    def _collect_artifacts(self, execution_results: Dict[str, ExecutionResult]) -> List[Dict[str, Any]]:
        """Collect all artifacts produced during workflow execution"""
        
        artifacts = []
        
        for result in execution_results.values():
            for artifact in result.artifacts:
                artifacts.append({
                    "task_id": result.task_id,
                    "artifact": artifact,
                    "created_at": result.completed_at
                })
        
        return artifacts
    
    async def resume_workflow(self, workflow_id: str, task_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Resume a failed workflow from last successful checkpoint
        
        Args:
            workflow_id: ID of workflow to resume
            task_fn: Optional custom task execution function
            
        Returns:
            Execution results for resumed workflow
        """
        
        logger.info(f"Resuming workflow: {workflow_id}")
        
        try:
            # Load workflow state
            workflow_state = await self.state_store.get_workflow_state(workflow_id)
            if not workflow_state:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            # Find failed/blocked tasks to retry
            failed_tasks = []
            for task_id, task_state in workflow_state.tasks.items():
                if task_state.status in [TaskStatus.FAILED, TaskStatus.BLOCKED]:
                    task_state.status = TaskStatus.PENDING  # Reset for retry
                    task_state.retries = 0  # Reset retry count
                    task_state.error = None
                    failed_tasks.append(task_id)
            
            if not failed_tasks:
                logger.info(f"No failed tasks found in workflow {workflow_id}")
                return {"workflow_id": workflow_id, "status": "already_completed"}
            
            # Get original plan (simplified - would load from state store)
            # For now, create minimal task list for failed tasks
            tasks_to_retry = []
            for task_id in failed_tasks:
                tasks_to_retry.append({
                    "id": task_id,
                    "type": "reasoning",  # Default type
                    "name": f"Retry {task_id}",
                    "description": f"Retry execution of {task_id}",
                    "dependencies": [],
                    "estimated_tokens": 1000
                })
            
            # Re-execute failed portion
            execution_results = await self._execute_dag(workflow_id, tasks_to_retry, workflow_state.tasks, task_fn)
            
            # Update workflow state
            all_succeeded = all(
                task_state.status == TaskStatus.SUCCEEDED 
                for task_state in workflow_state.tasks.values()
            )
            workflow_state.status = "completed" if all_succeeded else "partial_failure"
            workflow_state.resumed_at = time.time()
            
            await self.state_store.save_workflow_state(workflow_state)
            
            return {
                "workflow_id": workflow_id,
                "status": workflow_state.status,
                "resumed_tasks": list(failed_tasks),
                "execution_results": {task_id: asdict(result) for task_id, result in execution_results.items()}
            }
            
        except Exception as e:
            logger.error(f"Error resuming workflow {workflow_id}: {e}")
            return {
                "workflow_id": workflow_id,
                "status": "resume_error",
                "error": str(e)
            }


# Convenience function for simple workflow execution
async def run_plan(plan: Dict[str, Any], task_fn: Optional[Callable] = None, 
                  state_store: Optional[WorkflowStateStore] = None, max_parallel: int = 3) -> Dict[str, Any]:
    """
    Execute a workflow plan (convenience function)
    
    Args:
        plan: Workflow plan dictionary
        task_fn: Optional custom task execution function
        state_store: Optional state store (creates temporary if None)
        max_parallel: Maximum parallel tasks
        
    Returns:
        Execution results
    """
    
    if state_store is None:
        from .state import WorkflowStateStore
        state_store = WorkflowStateStore()
    
    executor = WorkflowExecutor(state_store, max_parallel)
    return await executor.run_plan(plan, task_fn)