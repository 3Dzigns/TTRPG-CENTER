# tests/unit/test_executor.py
"""
Unit tests for Workflow Executor - Phase 3
Tests retries, idempotency, selective rerun, and state management
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from src_common.runtime.execute import WorkflowExecutor, TaskStatus, ExecutionResult, run_plan
from src_common.runtime.state import WorkflowStateStore, WorkflowState, TaskState

class TestWorkflowExecutor:
    """Test WorkflowExecutor DAG execution and retry logic"""
    
    @pytest.fixture
    def temp_state_store(self):
        """Create temporary state store"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_workflows"
            yield WorkflowStateStore(storage_path=storage_path)
    
    @pytest.fixture
    def executor(self, temp_state_store):
        """Create WorkflowExecutor instance"""
        return WorkflowExecutor(temp_state_store, max_parallel=2)
    
    @pytest.fixture
    def simple_plan(self):
        """Simple test workflow plan"""
        return {
            "id": "plan:simple",
            "goal": "Simple test workflow",
            "tasks": [
                {
                    "id": "task:1",
                    "type": "retrieval",
                    "name": "First Task",
                    "description": "Retrieve information",
                    "dependencies": [],
                    "tool": "retriever",
                    "model": "claude-3-haiku",
                    "estimated_tokens": 1000
                },
                {
                    "id": "task:2",
                    "type": "reasoning",
                    "name": "Second Task", 
                    "description": "Process information",
                    "dependencies": ["task:1"],
                    "tool": "llm",
                    "model": "claude-3-sonnet",
                    "estimated_tokens": 2000
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_simple_workflow_execution(self, executor, simple_plan):
        """Test successful execution of simple workflow"""
        
        # Mock successful task function
        async def mock_task_fn(task):
            return {"result": f"Success for {task['id']}", "artifacts": []}
        
        result = await executor.run_plan(simple_plan, mock_task_fn)
        
        # Verify execution results
        assert result["status"] == "completed"
        assert "workflow_id" in result
        assert len(result["tasks"]) == 2
        
        # Verify all tasks succeeded
        for task_id, task_result in result["tasks"].items():
            assert task_result["status"] == TaskStatus.SUCCEEDED.value
            assert task_result["error"] is None
    
    @pytest.mark.asyncio
    async def test_task_dependency_ordering(self, executor):
        """Test that tasks execute in correct dependency order"""
        
        execution_order = []
        
        async def tracking_task_fn(task):
            execution_order.append(task["id"])
            return {"result": f"Completed {task['id']}"}
        
        # Plan with clear dependencies: 1 -> 2 -> 3
        dependency_plan = {
            "id": "plan:deps",
            "goal": "Test dependencies",
            "tasks": [
                {"id": "task:1", "type": "retrieval", "dependencies": [], "name": "Task 1"},
                {"id": "task:2", "type": "reasoning", "dependencies": ["task:1"], "name": "Task 2"},
                {"id": "task:3", "type": "synthesis", "dependencies": ["task:2"], "name": "Task 3"}
            ]
        }
        
        await executor.run_plan(dependency_plan, tracking_task_fn)
        
        # Verify execution order respects dependencies
        assert execution_order.index("task:1") < execution_order.index("task:2")
        assert execution_order.index("task:2") < execution_order.index("task:3")
    
    @pytest.mark.asyncio
    async def test_retry_logic_with_eventual_success(self, executor, simple_plan):
        """Test retry mechanism with task that fails then succeeds"""
        
        call_counts = {}
        
        async def failing_then_success_task_fn(task):
            task_id = task["id"]
            call_counts[task_id] = call_counts.get(task_id, 0) + 1
            
            # First task fails twice then succeeds
            if task_id == "task:1" and call_counts[task_id] <= 2:
                raise Exception(f"Simulated failure {call_counts[task_id]}")
            
            return {"result": f"Success for {task_id} after {call_counts[task_id]} attempts"}
        
        result = await executor.run_plan(simple_plan, failing_then_success_task_fn)
        
        # Should eventually succeed
        assert result["status"] == "completed"
        assert call_counts["task:1"] == 3  # Failed twice, succeeded on third attempt
        
        # Verify retry count recorded
        task1_result = result["tasks"]["task:1"]
        assert task1_result["retries"] == 2
        assert task1_result["status"] == TaskStatus.SUCCEEDED.value
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion_and_blocking(self, executor, simple_plan):
        """Test behavior when retries are exhausted"""
        
        async def always_failing_task_fn(task):
            if task["id"] == "task:1":
                raise Exception("Always fails")
            return {"result": f"Would succeed: {task['id']}"}
        
        result = await executor.run_plan(simple_plan, always_failing_task_fn)
        
        # Workflow should fail
        assert result["status"] == "failed"
        
        # First task should be failed
        task1_result = result["tasks"]["task:1"]
        assert task1_result["status"] == TaskStatus.FAILED.value
        assert task1_result["retries"] >= 2  # Should have retried
        
        # Second task should be blocked
        task2_result = result["tasks"]["task:2"]
        assert task2_result["status"] == TaskStatus.BLOCKED.value
        assert "dependency" in task2_result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_parallel_execution(self, executor):
        """Test parallel execution of independent tasks"""
        
        execution_times = {}
        
        async def timed_task_fn(task):
            import time
            start_time = time.time()
            execution_times[task["id"]] = start_time
            
            # Simulate work
            await asyncio.sleep(0.1)
            return {"result": f"Completed {task['id']}"}
        
        # Plan with parallel tasks (no dependencies)
        parallel_plan = {
            "id": "plan:parallel",
            "goal": "Test parallel execution",
            "tasks": [
                {"id": "task:a", "type": "retrieval", "dependencies": [], "name": "Task A"},
                {"id": "task:b", "type": "retrieval", "dependencies": [], "name": "Task B"},
                {"id": "task:c", "type": "retrieval", "dependencies": [], "name": "Task C"}
            ]
        }
        
        result = await executor.run_plan(parallel_plan, timed_task_fn)
        
        # All tasks should complete successfully
        assert result["status"] == "completed"
        assert len(result["tasks"]) == 3
        
        # Tasks should start close to each other (parallel execution)
        start_times = list(execution_times.values())
        max_start_diff = max(start_times) - min(start_times)
        assert max_start_diff < 0.5  # Should start within 0.5 seconds of each other
    
    @pytest.mark.asyncio
    async def test_workflow_resume_functionality(self, executor, temp_state_store):
        """Test resuming workflow from failure point"""
        
        # Create initial workflow state with failed task
        workflow_state = WorkflowState(
            id="wf:resume:test",
            plan_id="plan:resume",
            goal="Test resume workflow",
            status="failed",
            started_at=1000.0,
            tasks={
                "task:1": TaskState("task:1", TaskStatus.SUCCEEDED, [], 0, 1000.0, 1001.0, 1002.0),
                "task:2": TaskState("task:2", TaskStatus.FAILED, ["task:1"], 2, 1002.0, 1003.0, 1004.0),
                "task:3": TaskState("task:3", TaskStatus.BLOCKED, ["task:2"], 0, 1004.0)
            }
        )
        
        # Save state
        await temp_state_store.save_workflow_state(workflow_state)
        
        # Resume with successful task function
        async def success_task_fn(task):
            return {"result": f"Resumed success: {task['id']}"}
        
        result = await executor.resume_workflow("wf:resume:test", success_task_fn)
        
        # Should show resume results
        assert "workflow_id" in result
        assert "resumed_tasks" in result
        assert "task:2" in result["resumed_tasks"]  # Failed task should be resumed
    
    @pytest.mark.asyncio
    async def test_idempotency_with_task_keys(self, executor):
        """Test idempotent task execution"""
        
        execution_counts = {}
        
        async def counting_task_fn(task):
            task_key = f"{task['id']}:{task.get('idempotency_key', 'default')}"
            execution_counts[task_key] = execution_counts.get(task_key, 0) + 1
            
            # Simulate idempotent behavior - same key returns same result
            return {"result": f"Result for {task_key}", "execution_count": execution_counts[task_key]}
        
        idempotent_plan = {
            "id": "plan:idempotent",
            "goal": "Test idempotency",
            "tasks": [
                {
                    "id": "task:idem:1",
                    "type": "computation",
                    "dependencies": [],
                    "name": "Idempotent Task",
                    "idempotency_key": "stable_key_123"
                }
            ]
        }
        
        # Execute twice
        result1 = await executor.run_plan(idempotent_plan, counting_task_fn)
        result2 = await executor.run_plan(idempotent_plan, counting_task_fn)
        
        # Should execute successfully both times
        assert result1["status"] == "completed"
        assert result2["status"] == "completed"
    
    def test_default_task_executors(self, executor):
        """Test built-in task executors for different types"""
        
        # Test all default executors exist and are callable
        assert "retrieval" in executor.task_executors
        assert "reasoning" in executor.task_executors
        assert "computation" in executor.task_executors
        assert "verification" in executor.task_executors
        assert "synthesis" in executor.task_executors
        
        # All should be callable
        for task_type, executor_fn in executor.task_executors.items():
            assert callable(executor_fn)
    
    @pytest.mark.asyncio
    async def test_artifact_collection(self, executor):
        """Test artifact collection from task execution"""
        
        async def artifact_producing_task_fn(task):
            return {
                "result": f"Completed {task['id']}",
                "artifacts": [
                    {"type": "json", "content": {"task": task["id"], "data": "test"}},
                    {"type": "text", "content": f"Log for {task['id']}"}
                ]
            }
        
        artifact_plan = {
            "id": "plan:artifacts",
            "goal": "Test artifact collection",
            "tasks": [
                {"id": "task:art:1", "type": "synthesis", "dependencies": [], "name": "Artifact Task"}
            ]
        }
        
        result = await executor.run_plan(artifact_plan, artifact_producing_task_fn)
        
        # Verify artifacts collected
        assert "artifacts" in result
        assert len(result["artifacts"]) >= 1
        
        # Check artifact structure
        artifact = result["artifacts"][0]
        assert "task_id" in artifact
        assert "artifact" in artifact
        assert artifact["task_id"] == "task:art:1"


class TestWorkflowStateStore:
    """Test WorkflowStateStore persistence and retrieval"""
    
    @pytest.fixture
    def temp_state_store(self):
        """Create temporary state store"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_state"
            yield WorkflowStateStore(storage_path=storage_path)
    
    @pytest.mark.asyncio
    async def test_save_and_load_workflow_state(self, temp_state_store):
        """Test saving and loading workflow state"""
        
        # Create test workflow state
        workflow_state = WorkflowState(
            id="wf:test:123",
            plan_id="plan:test",
            goal="Test workflow persistence",
            status="running",
            started_at=1000.0,
            tasks={
                "task:1": TaskState("task:1", TaskStatus.PENDING, [], 0, 1000.0),
                "task:2": TaskState("task:2", TaskStatus.RUNNING, ["task:1"], 1, 1001.0, 1002.0)
            }
        )
        
        # Save state
        success = await temp_state_store.save_workflow_state(workflow_state)
        assert success
        
        # Load state
        loaded_state = await temp_state_store.get_workflow_state("wf:test:123")
        
        assert loaded_state is not None
        assert loaded_state.id == "wf:test:123"
        assert loaded_state.goal == "Test workflow persistence"
        assert loaded_state.status == "running"
        assert len(loaded_state.tasks) == 2
        
        # Verify task states loaded correctly
        task1 = loaded_state.tasks["task:1"]
        assert task1.status == TaskStatus.PENDING
        assert task1.retries == 0
        
        task2 = loaded_state.tasks["task:2"]
        assert task2.status == TaskStatus.RUNNING
        assert task2.retries == 1
    
    @pytest.mark.asyncio
    async def test_list_workflows_with_filtering(self, temp_state_store):
        """Test workflow listing with status filtering"""
        
        # Create multiple workflow states
        workflows = [
            WorkflowState("wf:1", None, "Goal 1", "completed", 1000.0, 1100.0),
            WorkflowState("wf:2", None, "Goal 2", "running", 1200.0),
            WorkflowState("wf:3", None, "Goal 3", "failed", 1300.0, 1400.0)
        ]
        
        # Save all workflows
        for workflow in workflows:
            await temp_state_store.save_workflow_state(workflow)
        
        # Test listing all workflows
        all_workflows = await temp_state_store.list_workflows()
        assert len(all_workflows) == 3
        
        # Test status filtering
        completed_workflows = await temp_state_store.list_workflows("completed")
        assert len(completed_workflows) == 1
        assert completed_workflows[0]["id"] == "wf:1"
        
        running_workflows = await temp_state_store.list_workflows("running")
        assert len(running_workflows) == 1
        assert running_workflows[0]["id"] == "wf:2"
    
    @pytest.mark.asyncio
    async def test_artifact_management(self, temp_state_store):
        """Test artifact saving and retrieval"""
        
        # Save artifact
        artifact_data = {
            "type": "computation_result",
            "content": {"dc": 15, "modifiers": [{"name": "circumstance", "value": 2}]},
            "metadata": {"task": "dc_computation", "timestamp": 1500.0}
        }
        
        artifact_id = await temp_state_store.save_artifact("wf:test", "task:1", artifact_data)
        assert artifact_id != ""
        assert artifact_id.startswith("artifact:")
        
        # Retrieve artifact
        retrieved = await temp_state_store.get_artifact(artifact_id)
        assert retrieved is not None
        assert retrieved["workflow_id"] == "wf:test"
        assert retrieved["task_id"] == "task:1"
        assert retrieved["data"]["type"] == "computation_result"
        
        # Test workflow artifacts listing
        workflow_artifacts = await temp_state_store.get_workflow_artifacts("wf:test")
        assert len(workflow_artifacts) == 1
        assert workflow_artifacts[0]["id"] == artifact_id
    
    @pytest.mark.asyncio
    async def test_workflow_deletion(self, temp_state_store):
        """Test complete workflow deletion"""
        
        # Create workflow with artifacts
        workflow_state = WorkflowState("wf:delete", None, "Delete test", "completed", 1000.0)
        await temp_state_store.save_workflow_state(workflow_state)
        
        # Add artifact
        artifact_id = await temp_state_store.save_artifact("wf:delete", "task:1", {"test": "data"})
        
        # Verify workflow exists
        loaded = await temp_state_store.get_workflow_state("wf:delete")
        assert loaded is not None
        
        # Delete workflow
        success = await temp_state_store.delete_workflow("wf:delete")
        assert success
        
        # Verify deletion
        deleted_workflow = await temp_state_store.get_workflow_state("wf:delete")
        assert deleted_workflow is None
        
        deleted_artifact = await temp_state_store.get_artifact(artifact_id)
        assert deleted_artifact is None
    
    def test_task_state_duration_calculation(self):
        """Test automatic duration calculation in TaskState"""
        
        task_state = TaskState(
            id="task:duration:test",
            status=TaskStatus.COMPLETED,
            dependencies=[],
            retries=0,
            created_at=1000.0,
            started_at=1001.0,
            completed_at=1005.5
        )
        
        # Duration should be calculated automatically
        assert task_state.duration_s == 4.5
    
    def test_workflow_state_duration_calculation(self):
        """Test automatic duration calculation in WorkflowState"""
        
        workflow_state = WorkflowState(
            id="wf:duration:test",
            plan_id="plan:test",
            goal="Duration test",
            status="completed",
            started_at=2000.0,
            completed_at=2030.5
        )
        
        # Duration should be calculated automatically
        assert workflow_state.duration_s == 30.5


class TestConvenienceFunctions:
    """Test module-level convenience functions"""
    
    @pytest.mark.asyncio
    async def test_run_plan_convenience_function(self):
        """Test run_plan convenience function"""
        
        simple_plan = {
            "id": "plan:convenience",
            "goal": "Test convenience function",
            "tasks": [
                {"id": "task:1", "type": "reasoning", "dependencies": [], "name": "Simple Task"}
            ]
        }
        
        async def simple_task_fn(task):
            return {"result": "Convenience function works"}
        
        # Should create temporary state store and execute
        result = await run_plan(simple_plan, simple_task_fn)
        
        assert "workflow_id" in result
        assert result["status"] in ["completed", "failed"]
        assert "tasks" in result
    
    def test_retry_policy_delay_calculation(self):
        """Test RetryPolicy delay calculations"""
        
        from src_common.runtime.execute import RetryPolicy
        
        policy = RetryPolicy(base_delay_s=1.0, exponential_base=2.0, max_delay_s=10.0)
        
        # Test exponential backoff
        assert policy.get_delay(1) == 1.0   # First retry: base delay
        assert policy.get_delay(2) == 2.0   # Second retry: base * 2^1  
        assert policy.get_delay(3) == 4.0   # Third retry: base * 2^2
        assert policy.get_delay(5) == 10.0  # Should cap at max_delay_s
        
    @pytest.mark.asyncio
    async def test_execution_result_structure(self, executor, simple_plan):
        """Test ExecutionResult data structure completeness"""
        
        async def detailed_task_fn(task):
            return {
                "result": "Detailed result",
                "artifacts": [{"type": "test", "data": "artifact_data"}]
            }
        
        result = await executor.run_plan(simple_plan, detailed_task_fn)
        
        # Check ExecutionResult completeness for each task
        for task_id, task_result in result["tasks"].items():
            # Verify all required fields present
            required_fields = ["task_id", "status", "started_at", "completed_at", "duration_s", "retries", "tokens_used"]
            for field in required_fields:
                assert field in task_result, f"Missing field {field} in task result"
            
            # Verify field types
            assert isinstance(task_result["duration_s"], (int, float))
            assert isinstance(task_result["retries"], int)
            assert isinstance(task_result["tokens_used"], int)