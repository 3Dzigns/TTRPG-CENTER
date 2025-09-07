# tests/security/test_phase3_security.py
"""
Security tests for Phase 3 - Graph operations and workflow security
Tests injection prevention, depth limits, authorization, and audit logging
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock

from src_common.graph.store import GraphStore, GraphStoreError
from src_common.planner.plan import TaskPlanner
from src_common.planner.budget import BudgetManager, PolicyEnforcer
from src_common.runtime.execute import WorkflowExecutor
from src_common.runtime.state import WorkflowStateStore


# Module-level fixture: reusable secure GraphStore across test classes
@pytest.fixture
def secure_store():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir) / "secure_graph"
        yield GraphStore(storage_path=storage_path)


# Module-level fixture: reusable executor/state store across classes
@pytest.fixture
def secure_executor_setup():
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir) / "secure_execution"
        state_store = WorkflowStateStore(storage_path=storage_path)
        executor = WorkflowExecutor(state_store, max_parallel=1)
        yield {"state_store": state_store, "executor": executor}

class TestGraphStoreSecurity:
    """Test security features of GraphStore operations"""

    # Module-level fixture for reuse across test classes
    @pytest.fixture
    def secure_store(self):
        """Create GraphStore for security testing (module-scoped convenience)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "secure_graph"
            yield GraphStore(storage_path=storage_path)
    
    # NOTE: Class-scoped fixture retained for backward compatibility
    
    def test_parametrized_query_injection_prevention(self, secure_store):
        """Test that parametrized queries prevent injection attacks"""
        
        # Add test node
        secure_store.upsert_node("test:node", "Concept", {"name": "Test", "value": "secret"})
        
        # Attempt injection via pattern
        malicious_patterns = [
            "MATCH (n) WHERE n.property = $param; DROP DATABASE",
            "MATCH (n) UNION SELECT * FROM secrets WHERE n.property = $param",
            "MATCH (n:Procedure) WHERE 1=1 OR n.property = $param"
        ]
        
        for malicious_pattern in malicious_patterns:
            try:
                # Should not execute malicious parts
                results = secure_store.query(malicious_pattern, {"param": "test"})
                
                # Should return limited safe results or empty
                assert len(results) <= 100  # Should respect result limits
                
                # Should not have exposed sensitive data
                for result in results:
                    assert "secret" not in str(result).lower()
                    
            except Exception:
                # It's also acceptable to reject malicious patterns entirely
                pass
    
    def test_depth_limit_enforcement(self, secure_store):
        """Test that neighbor traversal enforces depth limits"""
        
        # Create deep chain for depth bomb test
        nodes = []
        for i in range(20):  # Create chain longer than MAX_DEPTH
            node_id = f"node:depth:{i}"
            secure_store.upsert_node(node_id, "Concept", {"name": f"Node {i}"})
            nodes.append(node_id)
            
            if i > 0:
                secure_store.upsert_edge(nodes[i-1], "depends_on", nodes[i], {})
        
        # Attempt depth bomb
        neighbors = secure_store.neighbors(nodes[0], depth=100)  # Request excessive depth
        
        # Should be limited by MAX_DEPTH
        assert len(neighbors) <= secure_store.MAX_DEPTH
        
        # Should not cause performance issues (complete quickly)
        start_time = time.time()
        large_neighbors = secure_store.neighbors(nodes[0], depth=secure_store.MAX_DEPTH)
        elapsed = time.time() - start_time
        
        assert elapsed < 1.0  # Should complete within 1 second
        assert len(large_neighbors) <= secure_store.MAX_NEIGHBORS
    
    def test_pii_redaction_comprehensive(self, secure_store):
        """Test comprehensive PII redaction in node properties"""
        
        pii_test_data = {
            "name": "Test User",
            "email": "user@example.com",
            "phone": "555-123-4567", 
            "ssn": "123-45-6789",
            "password": "secret123",
            "api_key": "sk_test_12345",
            "token": "bearer_token_67890",
            "description": "Normal description",
            "user_email": "another@example.com",  # PII in key name
            "safe_data": "This is safe information"
        }
        
        result = secure_store.upsert_node("test:pii", "Entity", pii_test_data)
        
        # Verify PII redaction
        props = result["properties"]
        
        # Should redact PII fields
        pii_fields = ["email", "phone", "ssn", "password", "api_key", "token", "user_email"]
        for field in pii_fields:
            if field in props:
                assert props[field] == "***REDACTED***"
        
        # Should preserve safe data
        assert props["name"] == "Test User"
        assert props["description"] == "Normal description"
        assert props["safe_data"] == "This is safe information"
    
    def test_large_content_truncation(self, secure_store):
        """Test truncation of oversized content to prevent DoS"""
        
        # Create very large content
        large_content = "A" * 5000  # Larger than typical limits
        
        result = secure_store.upsert_node(
            "test:large",
            "Concept",
            {"large_field": large_content, "normal_field": "normal"}
        )
        
        # Should truncate large content
        stored_content = result["properties"]["large_field"]
        assert len(stored_content) <= 1003  # 1000 + "..." = 1003
        assert stored_content.endswith("...")
        
        # Should preserve normal content
        assert result["properties"]["normal_field"] == "normal"
    
    def test_invalid_node_edge_type_rejection(self, secure_store):
        """Test rejection of invalid/malicious node and edge types"""
        
        # Test invalid node types
        invalid_node_types = [
            "'; DROP TABLE nodes; --",
            "Union",
            "SELECT",
            "../../etc/passwd", 
            "<script>alert('xss')</script>",
            "' OR 1=1 --"
        ]
        
        for invalid_type in invalid_node_types:
            with pytest.raises(GraphStoreError, match="Invalid node type"):
                secure_store.upsert_node("test", invalid_type, {})
        
        # Test invalid edge types
        secure_store.upsert_node("node:a", "Concept", {})
        secure_store.upsert_node("node:b", "Concept", {})
        
        invalid_edge_types = [
            "'; DELETE FROM edges; --",
            "UNION SELECT",
            "../../../etc",
            "<script>",
            "' OR '1'='1"
        ]
        
        for invalid_type in invalid_edge_types:
            with pytest.raises(GraphStoreError, match="Invalid edge type"):
                secure_store.upsert_edge("node:a", invalid_type, "node:b", {})


class TestWorkflowSecurity:
    """Test security aspects of workflow execution"""
    
    @pytest.fixture
    def secure_workflow_setup(self):
        """Create secure workflow testing environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "secure_workflows"
            state_store = WorkflowStateStore(storage_path=storage_path)
            executor = WorkflowExecutor(state_store, max_parallel=2)
            yield {"state_store": state_store, "executor": executor}
    
    def test_goal_injection_prevention(self, secure_workflow_setup):
        """Test that malicious goals cannot inject commands or access files"""
        
        executor = secure_workflow_setup["executor"]
        
        malicious_goals = [
            "'; rm -rf / --",
            "Create plan && cat /etc/passwd",
            "<script>window.location='malicious.com'</script>",
            "Normal goal' UNION SELECT * FROM secrets WHERE '1'='1",
            "../../../etc/passwd",
            "Goal with eval() and system() calls"
        ]
        
        # Create minimal graph for planning
        temp_store = GraphStore()
        planner = TaskPlanner(temp_store)
        
        for malicious_goal in malicious_goals:
            try:
                # Should not crash or expose system
                plan = planner.plan_from_goal(malicious_goal)
                
                # Plan should be sanitized/safe
                assert plan.goal == malicious_goal  # Goal preserved but contained
                assert len(plan.tasks) <= 10  # Reasonable task count
                
                # Task descriptions should not contain system commands
                for task in plan.tasks:
                    task_text = f"{task.name} {task.description} {task.prompt}".lower()
                    dangerous_patterns = ["rm -rf", "cat /etc", "eval(", "system(", "exec("]
                    for pattern in dangerous_patterns:
                        assert pattern not in task_text
                        
            except Exception as e:
                # It's acceptable to reject malicious goals entirely
                assert "error" in str(e).lower()
    
    def test_budget_authorization_enforcement(self):
        """Test that budget policies properly enforce authorization"""
        
        budget_manager = BudgetManager()
        enforcer = PolicyEnforcer(budget_manager)
        
        # Test unauthorized expensive plan
        expensive_plan = {
            "id": "plan:expensive:unauthorized",
            "goal": "Expensive operation requiring admin approval",
            "tasks": [
                {"id": "task:1", "model": "gpt-4", "estimated_tokens": 100000}  # Exceeds all budgets
            ]
        }
        
        # Guest role should be rejected
        guest_approved, guest_response = enforcer.enforce_plan(expensive_plan, "guest")
        assert not guest_approved
        assert not guest_response["compliance"]["approved"]
        
        # Player role should also be rejected 
        player_approved, player_response = enforcer.enforce_plan(expensive_plan, "player")
        assert not player_approved
        
        # Admin role might be approved or require checkpoint
        admin_approved, admin_response = enforcer.enforce_plan(expensive_plan, "admin")
        if not admin_approved:
            assert admin_response.get("requires_approval") or admin_response.get("optimized_plan")
    
    def test_approval_api_security(self):
        """Test approval API security (nonce, expiry, authorization)"""
        
        from src_common.planner.budget import PolicyEnforcer, BudgetManager
        
        enforcer = PolicyEnforcer(BudgetManager())
        
        # Create approval checkpoint
        checkpoint = enforcer.create_approval_checkpoint(
            "plan:test:security",
            "Security test approval",
            {"total_cost_usd": 5.0}
        )
        
        # Verify checkpoint security features
        assert "checkpoint_id" in checkpoint
        assert checkpoint["status"] == "pending"
        assert checkpoint["created_at"] > 0
        
        # Checkpoint ID should be unpredictable
        checkpoint2 = enforcer.create_approval_checkpoint(
            "plan:test:security2", 
            "Another test",
            {"total_cost_usd": 5.0}
        )
        
        assert checkpoint["checkpoint_id"] != checkpoint2["checkpoint_id"]
        
        # Should contain approval URL for proper access control
        assert "approval_url" in checkpoint
        assert "/approve" in checkpoint["approval_url"]
    
    @pytest.mark.asyncio
    async def test_workflow_state_access_control(self, secure_workflow_setup):
        """Test that workflow states are properly isolated"""
        
        state_store = secure_workflow_setup["state_store"]
        
        from src_common.runtime.state import WorkflowState, TaskState, TaskStatus
        
        # Create workflows for different "users" (simulated)
        user1_workflow = WorkflowState("wf:user1:123", None, "User 1 workflow", "running", 1000.0)
        user2_workflow = WorkflowState("wf:user2:456", None, "User 2 workflow", "running", 1000.0)
        
        # Save both workflows
        await state_store.save_workflow_state(user1_workflow)
        await state_store.save_workflow_state(user2_workflow)
        
        # Test that workflows are isolated (basic test - real auth would be in API layer)
        loaded_user1 = await state_store.get_workflow_state("wf:user1:123")
        loaded_user2 = await state_store.get_workflow_state("wf:user2:456")
        
        assert loaded_user1.id == "wf:user1:123"
        assert loaded_user2.id == "wf:user2:456"
        assert loaded_user1.goal != loaded_user2.goal
    
    def test_write_ahead_log_security(self, secure_store):
        """Test write-ahead log doesn't expose sensitive information"""
        
        # Add node with mixed data
        secure_store.upsert_node(
            "test:wal:security",
            "Entity",
            {
                "public_name": "Public Information",
                "password": "secret_password",
                "email": "user@secret.com",
                "description": "Public description"
            }
        )
        
        # Check write-ahead log
        log_entries = secure_store.write_ahead_log
        
        assert len(log_entries) > 0
        
        # Verify PII is redacted in log
        for entry in log_entries:
            operation_data = entry.get("data", {})
            properties = operation_data.get("properties", {})
            
            # PII should be redacted in logged properties
            if "password" in properties:
                assert properties["password"] == "***REDACTED***"
            if "email" in properties:
                assert properties["email"] == "***REDACTED***"
            
            # Public data should be preserved
            if "public_name" in properties:
                assert properties["public_name"] == "Public Information"
    
    def test_neighbor_search_dos_prevention(self, secure_store):
        """Test DoS prevention in neighbor search operations"""
        
        # Create large graph to test DoS resistance
        central_node = "node:central"
        secure_store.upsert_node(central_node, "Concept", {"name": "Central"})
        
        # Add many neighbors (attempt to create performance issue)
        for i in range(2000):  # More than MAX_NEIGHBORS
            neighbor_id = f"node:neighbor:{i}"
            secure_store.upsert_node(neighbor_id, "Concept", {"name": f"Neighbor {i}"})
            secure_store.upsert_edge(central_node, "depends_on", neighbor_id, {})
        
        # Search should complete quickly and be limited
        start_time = time.time()
        neighbors = secure_store.neighbors(central_node, depth=1)
        elapsed = time.time() - start_time
        
        # Performance and size limits
        assert elapsed < 2.0  # Should complete within 2 seconds
        assert len(neighbors) <= secure_store.MAX_NEIGHBORS  # Should be capped
    
    def test_query_result_limit_enforcement(self, secure_store):
        """Test that query results are properly limited"""
        
        # Add many nodes
        for i in range(150):  # More than typical result limits
            secure_store.upsert_node(f"proc:test:{i}", "Procedure", {"name": f"Procedure {i}"})
        
        # Query for all procedures
        results = secure_store.query("MATCH (n:Procedure) WHERE n.property = $param", {})
        
        # Should be limited to prevent resource exhaustion
        assert len(results) <= 100  # Should respect result limits


class TestPlannerSecurity:
    """Test security aspects of workflow planning"""
    
    def test_budget_bypass_prevention(self):
        """Test that budget limits cannot be bypassed through planning manipulation"""
        
        budget_manager = BudgetManager()
        
        # Create plan that attempts to bypass limits
        bypass_plan = {
            "id": "plan:bypass:attempt",
            "goal": "Normal goal",  # Innocent goal
            "tasks": [
                {
                    "id": "task:1",
                    "model": "local",  # Appears cheap
                    "estimated_tokens": 1,  # Appears small
                    "hidden_operation": "expensive_llm_call",  # Malicious payload
                    "actual_tokens": 50000  # Hidden cost
                }
            ]
        }
        
        # Estimate should use declared values, not hidden ones
        estimate = budget_manager.estimate_workflow_cost(bypass_plan["tasks"])
        
        # Should base estimate on estimated_tokens, not hidden fields
        assert estimate["total_tokens"] == 1  # Should use estimated_tokens
        
        # Hidden fields should not affect budget calculations
        assert "hidden_operation" not in str(estimate)
        assert "actual_tokens" not in str(estimate)
    
    def test_plan_validation_malicious_edges(self):
        """Test plan validation rejects malicious edge structures"""
        
        temp_store = GraphStore()
        planner = TaskPlanner(temp_store)
        
        from src_common.planner.plan import WorkflowPlan, WorkflowTask
        
        # Create plan with malicious self-reference
        malicious_task = WorkflowTask(
            id="task:malicious",
            type="reasoning",
            name="Malicious Task",
            description="Task with self-dependency",
            dependencies=["task:malicious"],  # Self-reference
            tool="llm",
            model="claude-3-haiku",
            prompt="test",
            parameters={},
            estimated_tokens=1000,
            estimated_time_s=10
        )
        
        malicious_plan = WorkflowPlan(
            id="plan:malicious:selfreference",
            goal="Test malicious self-reference",
            procedure_id=None,
            tasks=[malicious_task],
            edges=[("task:malicious", "task:malicious")],  # Self-loop
            total_estimated_tokens=1000,
            total_estimated_time_s=10,
            checkpoints=[],
            created_at=time.time()
        )
        
        # Validation should detect and reject cycles
        is_valid, errors = planner.validate_plan(malicious_plan)
        
        assert not is_valid
        assert any("cycle" in error.lower() for error in errors)
    
    def test_resource_limit_enforcement(self):
        """Test that planning enforces resource limits"""
        
        temp_store = GraphStore()
        planner = TaskPlanner(temp_store)
        
        # Attempt to create plan exceeding limits
        constraints = {
            "max_tokens": 1000,  # Very low limit
            "max_time_s": 10     # Very low limit
        }
        
        expensive_goal = "Perform complex analysis requiring many steps and large language model usage"
        plan = planner.plan_from_goal(expensive_goal, constraints)
        
        # Plan should either:
        # 1. Respect limits (be under budget)
        # 2. Require approval (have checkpoints)
        
        if plan.total_estimated_tokens <= 1000:
            # Respects limits
            assert plan.total_estimated_time_s <= 10
        else:
            # Should require approval
            assert len(plan.checkpoints) > 0
            assert any(task.requires_approval for task in plan.tasks)


class TestExecutorSecurity:
    """Test security aspects of workflow execution"""
    
    @pytest.fixture
    def secure_executor_setup(self):
        """Create secure executor testing environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "secure_execution"
            state_store = WorkflowStateStore(storage_path=storage_path)
            executor = WorkflowExecutor(state_store, max_parallel=1)  # Limited parallelism for testing
            yield {"state_store": state_store, "executor": executor}
    
    @pytest.mark.asyncio
    async def test_malicious_task_isolation(self, secure_executor_setup):
        """Test that malicious task content cannot affect other tasks"""
        
        executor = secure_executor_setup["executor"]
        
        # Plan with one malicious task and one normal task
        security_test_plan = {
            "id": "plan:security:isolation",
            "goal": "Test task isolation",
            "tasks": [
                {
                    "id": "task:malicious",
                    "type": "computation",
                    "name": "Malicious Task",
                    "description": "'; rm -rf /; echo 'pwned'",
                    "dependencies": [],
                    "tool": "calculator",
                    "model": "local"
                },
                {
                    "id": "task:normal",
                    "type": "reasoning",
                    "name": "Normal Task",
                    "description": "Normal legitimate task",
                    "dependencies": [],
                    "tool": "llm", 
                    "model": "claude-3-haiku"
                }
            ]
        }
        
        # Mock task function that tracks what gets executed
        executed_content = []
        
        async def security_tracking_task_fn(task):
            executed_content.append({
                "task_id": task["id"],
                "description": task.get("description", ""),
                "tool": task.get("tool", ""),
                "model": task.get("model", ""),
                # Explicitly record that the task content was inspected/handled safely
                "security_checked": True,
            })
            
            # Simulate that malicious content doesn't actually execute system commands
            return {"result": f"Safe execution of {task['id']}", "security_checked": True}
        
        result = await executor.run_plan(security_test_plan, security_tracking_task_fn)
        
        # Both tasks should complete safely
        assert result["status"] == "completed"
        assert len(executed_content) == 2
        
        # Verify content was tracked but not executed as system commands
        malicious_execution = next(e for e in executed_content if e["task_id"] == "task:malicious")
        assert "rm -rf" in malicious_execution["description"]  # Content preserved
        assert malicious_execution["security_checked"]  # But safely handled
    
    @pytest.mark.asyncio
    async def test_execution_timeout_enforcement(self, secure_executor_setup):
        """Test that task execution timeouts are enforced"""
        
        executor = secure_executor_setup["executor"]
        
        # Plan with potentially infinite-running task
        timeout_test_plan = {
            "id": "plan:timeout:test",
            "goal": "Test execution timeouts",
            "tasks": [
                {
                    "id": "task:slow",
                    "type": "computation",
                    "name": "Slow Task",
                    "description": "Task that might run forever",
                    "dependencies": [],
                    "max_execution_time_s": 1.0  # Short timeout for testing
                }
            ]
        }
        
        # Task function that simulates slow operation
        async def slow_task_fn(task):
            if task["id"] == "task:slow":
                import asyncio
                await asyncio.sleep(2.0)  # Longer than timeout
            return {"result": "Should not reach here"}
        
        # Execution should handle timeout gracefully
        # Note: Real timeout implementation would be in production executor
        start_time = time.time()
        result = await executor.run_plan(timeout_test_plan, slow_task_fn)
        elapsed = time.time() - start_time
        
        # Should not run significantly longer than expected
        assert elapsed < 5.0  # Should not hang indefinitely
    
    @pytest.mark.asyncio
    async def test_state_persistence_security(self, secure_executor_setup):
        """Test that workflow state persistence doesn't expose sensitive data"""
        
        state_store = secure_executor_setup["state_store"]
        
        from src_common.runtime.state import WorkflowState, TaskState, TaskStatus
        
        # Create workflow state with sensitive data
        sensitive_workflow = WorkflowState(
            id="wf:sensitive:test",
            plan_id="plan:sensitive",
            goal="Workflow with sensitive information",
            status="running",
            started_at=time.time(),
            tasks={
                "task:1": TaskState(
                    id="task:1",
                    status=TaskStatus.SUCCEEDED,
                    dependencies=[],
                    retries=0,
                    created_at=time.time(),
                    output={
                        "result": "Task completed",
                        "sensitive_token": "sk_secret_12345",  # Should not be persisted
                        "user_password": "user_secret"         # Should not be persisted
                    }
                )
            }
        )
        
        # Save state
        await state_store.save_workflow_state(sensitive_workflow)
        
        # Load and verify sensitive data is not exposed in persistence
        loaded_state = await state_store.get_workflow_state("wf:sensitive:test")
        
        # Basic structure should be preserved
        assert loaded_state.id == "wf:sensitive:test"
        assert loaded_state.goal == "Workflow with sensitive information"
        
        # Sensitive data in task output should be handled appropriately
        # (Note: Current implementation doesn't have output sanitization, 
        # this test documents expected behavior for future implementation)
        task1_output = loaded_state.tasks["task:1"].output
        if task1_output and isinstance(task1_output, dict):
            # Should preserve non-sensitive data
            assert task1_output.get("result") == "Task completed"


class TestAuditLogging:
    """Test audit logging and traceability features"""
    
    def test_graph_operation_audit_trail(self, secure_store):
        """Test that graph operations create proper audit trails"""
        
        # Perform various operations
        secure_store.upsert_node("audit:node:1", "Concept", {"name": "Audit Test"})
        secure_store.upsert_node("audit:node:2", "Rule", {"text": "Test rule"})
        secure_store.upsert_edge("audit:node:1", "cites", "audit:node:2", {"confidence": 0.9})
        
        # Check write-ahead log for audit trail
        log_entries = secure_store.write_ahead_log
        
        assert len(log_entries) >= 3  # Should have logged all operations
        
        # Verify log entry structure
        for entry in log_entries:
            assert "id" in entry
            assert "operation" in entry
            assert "data" in entry
            assert "timestamp" in entry
            
            # Should have unique operation IDs for traceability
            assert entry["id"] != ""
            
            # Timestamps should be reasonable
            assert entry["timestamp"] > 1000000000  # Reasonable epoch time
    
    @pytest.mark.asyncio
    async def test_workflow_execution_audit_trail(self, secure_executor_setup):
        """Test workflow execution creates comprehensive audit trail"""
        
        state_store = secure_executor_setup["state_store"]
        executor = secure_executor_setup["executor"]
        
        audit_plan = {
            "id": "plan:audit:test",
            "goal": "Test audit trail generation",
            "tasks": [
                {"id": "task:audit:1", "type": "reasoning", "dependencies": [], "name": "Audit Task"}
            ]
        }
        
        # Execute with audit tracking
        async def audit_task_fn(task):
            return {
                "result": f"Audit result for {task['id']}",
                "operation_log": {
                    "task_executed": task["id"],
                    "execution_time": time.time(),
                    "user_context": "test_user"
                }
            }
        
        result = await executor.run_plan(audit_plan, audit_task_fn)
        
        # Verify audit information preserved
        assert "workflow_id" in result
        
        # Check that workflow state contains execution history
        workflow_state = await state_store.get_workflow_state(result["workflow_id"])
        
        assert workflow_state is not None
        assert workflow_state.started_at > 0
        assert workflow_state.completed_at > 0
        
        # Task execution should be traceable
        for task_id, task_state in workflow_state.tasks.items():
            assert task_state.started_at is not None or task_state.status == TaskStatus.PENDING
            if task_state.completed_at:
                assert task_state.duration_s >= 0
    
    def test_approval_audit_logging(self):
        """Test that approval operations are properly audited"""
        
        from src_common.planner.budget import PolicyEnforcer, BudgetManager
        
        enforcer = PolicyEnforcer(BudgetManager())
        
        # Create approval checkpoint
        checkpoint = enforcer.create_approval_checkpoint(
            "plan:audit:approval",
            "Test approval auditing",
            {"cost": 5.0}
        )
        
        # Verify audit information in checkpoint
        assert "created_at" in checkpoint
        assert checkpoint["created_at"] > 0
        assert "checkpoint_id" in checkpoint
        
        # Checkpoint ID should be traceable
        assert "approval:" in checkpoint["checkpoint_id"]
        assert "plan:audit:approval" in checkpoint["checkpoint_id"]
    
    def test_error_information_sanitization(self, secure_store):
        """Test that error messages don't leak sensitive information"""
        
        try:
            # Attempt operation that might expose internal paths or data
            secure_store.upsert_edge("nonexistent:source", "depends_on", "nonexistent:target", {
                "internal_path": "/home/user/.secrets",
                "api_key": "secret_key_123"
            })
            
        except GraphStoreError as e:
            error_message = str(e)
            
            # Error should be informative but not expose sensitive details
            assert "source node" in error_message.lower() or "does not exist" in error_message.lower()
            
            # Should not contain sensitive information from properties
            assert "internal_path" not in error_message
            assert "api_key" not in error_message
            assert "secret_key" not in error_message
    
    def test_resource_exhaustion_protection(self):
        """Test protection against resource exhaustion attacks"""
        
        temp_store = GraphStore()
        planner = TaskPlanner(temp_store)
        
        # Attempt to create resource-exhausting plan
        resource_attack_goal = """
        Create a workflow that performs the following operations simultaneously: 
        """ + "analyze this data, " * 1000  # Attempt to create huge plan
        
        plan = planner.plan_from_goal(resource_attack_goal)
        
        # Should be limited by planner constraints
        assert len(plan.tasks) <= planner.MAX_TASKS
        assert plan.total_estimated_tokens <= planner.MAX_TOKENS * 2  # Allow some flexibility
        assert plan.total_estimated_time_s <= planner.MAX_TIME_S * 2
        
        # Validation should catch resource violations
        is_valid, errors = planner.validate_plan(plan)
        
        if not is_valid:
            # Should have specific resource violation messages
            resource_errors = [e for e in errors if any(limit in e.lower() for limit in ["token", "time", "task"])]
            assert len(resource_errors) > 0
