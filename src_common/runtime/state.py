# src_common/runtime/state.py
"""
Workflow State Management - Phase 3 State Persistence
US-306: Workflow State & Artifacts implementation
"""

import json
import re
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

from ..ttrpg_logging import get_logger

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
class TaskState:
    """State of individual task execution"""
    id: str
    status: TaskStatus
    dependencies: List[str]
    retries: int
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_s: Optional[float] = None
    output: Any = None
    error: Optional[str] = None
    artifacts: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
        
        # Calculate duration if both timestamps available
        if self.started_at and self.completed_at:
            self.duration_s = self.completed_at - self.started_at

@dataclass
class WorkflowState:
    """Complete workflow execution state"""
    id: str
    plan_id: Optional[str]
    goal: str
    status: str  # running, completed, failed, error
    started_at: float
    completed_at: Optional[float] = None
    duration_s: Optional[float] = None
    tasks: Dict[str, TaskState] = None
    artifacts: List[Dict[str, Any]] = None
    error: Optional[str] = None
    resumed_at: Optional[float] = None
    checkpoints: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tasks is None:
            self.tasks = {}
        if self.artifacts is None:
            self.artifacts = []
        if self.checkpoints is None:
            self.checkpoints = []
        
        # Calculate duration if both timestamps available
        if self.started_at and self.completed_at:
            self.duration_s = self.completed_at - self.started_at

class WorkflowStateStore:
    """
    Persistent storage for workflow state and artifacts
    
    Provides CRUD operations for workflow states, task states, and artifacts
    with JSON persistence and optional database backend
    """
    
    def __init__(self, storage_path: Optional[Path] = None, client=None):
        """
        Initialize state store
        
        Args:
            storage_path: Local storage path for development
            client: Database client for production (AstraDB, etc.)
        """
        self.client = client
        self.storage_path = storage_path or Path("artifacts/workflows") 
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Artifact storage
        self.artifacts_path = self.storage_path / "artifacts"
        self.artifacts_path.mkdir(exist_ok=True)
        
        logger.info(f"Workflow state store initialized at {self.storage_path}")

    def _safe_name(self, s: str) -> str:
        """Sanitize identifiers for filesystem safety across OSes.
        Replaces disallowed characters with '_'.
        """
        return re.sub(r"[^A-Za-z0-9._-]", "_", s or "")
    
    async def save_workflow_state(self, workflow_state: WorkflowState) -> bool:
        """
        Save workflow state to persistent storage
        
        Args:
            workflow_state: Workflow state to save
            
        Returns:
            Success status
        """
        
        try:
            # Prepare serializable data
            state_data = asdict(workflow_state)
            
            # Convert enum values to strings
            for task_id, task_state in state_data["tasks"].items():
                if hasattr(task_state["status"], "value"):
                    task_state["status"] = task_state["status"].value
                else:
                    task_state["status"] = str(task_state["status"])
            
            # Save to file (use filesystem-safe name)
            safe_id = self._safe_name(workflow_state.id)
            state_file = self.storage_path / f"{safe_id}.json"
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, default=str)
            
            logger.debug(f"Saved workflow state for {workflow_state.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving workflow state {workflow_state.id}: {e}")
            return False
    
    async def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """
        Load workflow state from storage
        
        Args:
            workflow_id: Workflow ID to load
            
        Returns:
            WorkflowState object or None if not found
        """
        
        try:
            safe_id = self._safe_name(workflow_id)
            state_file = self.storage_path / f"{safe_id}.json"
            
            if not state_file.exists():
                return None
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Reconstruct task states
            tasks = {}
            for task_id, task_data in state_data.get("tasks", {}).items():
                # Convert status back to enum
                if isinstance(task_data["status"], str):
                    task_data["status"] = TaskStatus(task_data["status"])
                
                tasks[task_id] = TaskState(**task_data)
            
            # Reconstruct workflow state
            state_data["tasks"] = tasks
            workflow_state = WorkflowState(**state_data)
            
            logger.debug(f"Loaded workflow state for {workflow_id}")
            return workflow_state
            
        except Exception as e:
            logger.error(f"Error loading workflow state {workflow_id}: {e}")
            return None
    
    async def list_workflows(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List workflows with optional status filtering
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of workflow summary dictionaries
        """
        
        workflows = []
        
        try:
            for state_file in self.storage_path.glob("*.json"):
                if state_file.name.endswith(".json"):
                    try:
                        with open(state_file, 'r', encoding='utf-8') as f:
                            state_data = json.load(f)
                        
                        # Filter by status if requested
                        if status_filter and state_data.get("status") != status_filter:
                            continue
                        
                        # Create summary
                        summary = {
                            "id": state_data.get("id"),
                            "goal": state_data.get("goal", "")[:100],  # Truncate for summary
                            "status": state_data.get("status"),
                            "started_at": state_data.get("started_at"),
                            "completed_at": state_data.get("completed_at"),
                            "duration_s": state_data.get("duration_s"),
                            "task_count": len(state_data.get("tasks", {})),
                            "artifact_count": len(state_data.get("artifacts", []))
                        }
                        
                        workflows.append(summary)
                        
                    except Exception as e:
                        logger.warning(f"Could not read workflow state file {state_file}: {e}")
                        continue
            
            # Sort by start time (most recent first)
            workflows.sort(key=lambda w: w.get("started_at", 0), reverse=True)
            
            return workflows
            
        except Exception as e:
            logger.error(f"Error listing workflows: {e}")
            return []
    
    async def save_artifact(self, workflow_id: str, task_id: str, artifact_data: Dict[str, Any]) -> str:
        """
        Save task artifact to storage
        
        Args:
            workflow_id: Workflow ID
            task_id: Task ID that produced artifact
            artifact_data: Artifact data to save
            
        Returns:
            Artifact ID/path
        """
        
        try:
            # Generate artifact ID (logical id retains original; file uses safe name)
            artifact_id = f"artifact:{workflow_id}:{task_id}:{int(time.time())}"
            
            # Determine storage path
            safe_wf = self._safe_name(workflow_id)
            workflow_artifacts_dir = self.artifacts_path / safe_wf
            workflow_artifacts_dir.mkdir(exist_ok=True)
            
            safe_artifact_id = self._safe_name(artifact_id)
            artifact_file = workflow_artifacts_dir / f"{safe_artifact_id}.json"
            
            # Add metadata
            artifact_with_meta = {
                "id": artifact_id,
                "workflow_id": workflow_id,
                "task_id": task_id,
                "created_at": time.time(),
                "data": artifact_data
            }
            
            # Save to file
            with open(artifact_file, 'w', encoding='utf-8') as f:
                json.dump(artifact_with_meta, f, indent=2, default=str)
            
            logger.debug(f"Saved artifact {artifact_id} for workflow {workflow_id}")
            return artifact_id
            
        except Exception as e:
            logger.error(f"Error saving artifact for workflow {workflow_id}: {e}")
            return ""
    
    async def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve artifact by ID
        
        Args:
            artifact_id: Artifact ID to retrieve
            
        Returns:
            Artifact data or None if not found
        """
        
        try:
            # Search for artifact file (brute force for development)
            # Look for sanitized filename
            safe_artifact = self._safe_name(artifact_id)
            for artifact_file in self.artifacts_path.rglob(f"{safe_artifact}.json"):
                with open(artifact_file, 'r', encoding='utf-8') as f:
                    artifact_data = json.load(f)
                
                return artifact_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving artifact {artifact_id}: {e}")
            return None
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete workflow and all associated artifacts
        
        Args:
            workflow_id: Workflow ID to delete
            
        Returns:
            Success status
        """
        
        try:
            # Delete state file
            safe_id = self._safe_name(workflow_id)
            state_file = self.storage_path / f"{safe_id}.json"
            if state_file.exists():
                state_file.unlink()
            
            # Delete artifacts directory
            artifacts_dir = self.artifacts_path / self._safe_name(workflow_id)
            if artifacts_dir.exists():
                import shutil
                shutil.rmtree(artifacts_dir)
            
            logger.info(f"Deleted workflow {workflow_id} and artifacts")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting workflow {workflow_id}: {e}")
            return False
    
    async def get_workflow_artifacts(self, workflow_id: str) -> List[Dict[str, Any]]:
        """
        Get all artifacts for a workflow
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            List of artifact dictionaries
        """
        
        artifacts = []
        
        try:
            artifacts_dir = self.artifacts_path / workflow_id
            
            if artifacts_dir.exists():
                for artifact_file in artifacts_dir.glob("*.json"):
                    with open(artifact_file, 'r', encoding='utf-8') as f:
                        artifact_data = json.load(f)
                    artifacts.append(artifact_data)
            
            # Sort by creation time
            artifacts.sort(key=lambda a: a.get("created_at", 0))
            
            return artifacts
            
        except Exception as e:
            logger.error(f"Error getting artifacts for workflow {workflow_id}: {e}")
            return []
