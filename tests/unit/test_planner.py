# tests/unit/test_planner.py
"""
Unit tests for Task Planner - Phase 3
Tests DAG creation, cycle detection, and budget enforcement
"""

import pytest
import tempfile
from pathlib import Path

from src_common.graph.store import GraphStore
from src_common.planner.plan import TaskPlanner, WorkflowTask, WorkflowPlan, plan_from_goal
from src_common.planner.budget import BudgetManager, BudgetConstraints, ModelSelector, PolicyEnforcer

class TestTaskPlanner:
    """Test TaskPlanner workflow planning and validation"""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary graph store with test data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_graph"
            store = GraphStore(storage_path=storage_path)
            
            # Add test procedure
            store.upsert_node(
                "proc:test:crafting",
                "Procedure",
                {"name": "Test Crafting", "procedure_type": "crafting", "description": "Test crafting procedure"}
            )
            
            # Add steps
            for i in range(1, 4):
                step_id = f"step:test:{i}"
                store.upsert_node(
                    step_id,
                    "Step", 
                    {"name": f"Step {i}", "step_number": i, "description": f"Test step {i}"}
                )
                store.upsert_edge("proc:test:crafting", "part_of", step_id, {"order": i})
            
            yield store
    
    @pytest.fixture
    def planner(self, temp_store):
        """Create TaskPlanner instance"""
        return TaskPlanner(temp_store)
    
    def test_plan_from_goal_with_procedure(self, planner):
        """Test planning when matching procedure exists in graph"""
        
        goal = "Execute test crafting procedure"
        plan = planner.plan_from_goal(goal)
        
        # Verify plan structure
        assert isinstance(plan, WorkflowPlan)
        assert plan.goal == goal
        assert plan.procedure_id == "proc:test:crafting"
        assert len(plan.tasks) == 3  # Should have task for each step
        assert plan.total_estimated_tokens > 0
        assert plan.total_estimated_time_s > 0
        
        # Verify tasks are properly structured
        for task in plan.tasks:
            assert isinstance(task, WorkflowTask)
            assert task.id.startswith("task:")
            assert task.tool != ""
            assert task.model != ""
            assert task.estimated_tokens > 0
    
    def test_plan_from_goal_without_procedure(self, planner):
        """Test planning when no matching procedure exists"""
        
        goal = "Answer a question about dragons"
        plan = planner.plan_from_goal(goal)
        
        # Should create generic task sequence
        assert plan.goal == goal
        assert plan.procedure_id is None
        assert len(plan.tasks) == 3  # Generic: retrieve, reason, synthesize
        
        # Verify generic task structure
        task_types = [task.type for task in plan.tasks]
        assert "retrieval" in task_types
        assert "reasoning" in task_types  
        assert "synthesis" in task_types
    
    def test_plan_validation_success(self, planner):
        """Test validation of valid plan"""
        
        goal = "Valid test goal"
        plan = planner.plan_from_goal(goal)
        
        is_valid, errors = planner.validate_plan(plan)
        
        assert is_valid
        assert len(errors) == 0
    
    def test_plan_validation_cycle_detection(self, planner):
        """Test cycle detection in task dependencies"""
        
        # Create plan with circular dependency
        task1 = WorkflowTask("task:1", "reasoning", "Task 1", "First task", ["task:2"], "", "", "", {}, 100, 10)
        task2 = WorkflowTask("task:2", "reasoning", "Task 2", "Second task", ["task:1"], "", "", "", {}, 100, 10)
        
        plan = WorkflowPlan(
            id="plan:cycle",
            goal="Test cycle detection",
            procedure_id=None,
            tasks=[task1, task2],
            edges=[("task:1", "task:2"), ("task:2", "task:1")],  # Circular
            total_estimated_tokens=200,
            total_estimated_time_s=20,
            checkpoints=[],
            created_at=0
        )
        
        is_valid, errors = planner.validate_plan(plan)
        
        assert not is_valid
        assert any("cycle" in error.lower() for error in errors)
    
    def test_plan_validation_budget_limits(self, planner):
        """Test budget limit validation"""
        
        # Create plan exceeding limits
        expensive_tasks = []
        for i in range(25):  # Exceed MAX_TASKS
            task = WorkflowTask(
                f"task:expensive:{i}", "reasoning", f"Task {i}", f"Expensive task {i}",
                [], "", "", "", {}, 10000, 100  # High token cost
            )
            expensive_tasks.append(task)
        
        plan = WorkflowPlan(
            id="plan:expensive",
            goal="Expensive test plan",
            procedure_id=None,
            tasks=expensive_tasks,
            edges=[],
            total_estimated_tokens=250000,  # Exceed MAX_TOKENS
            total_estimated_time_s=2500,   # Exceed MAX_TIME_S
            checkpoints=[],
            created_at=0
        )
        
        is_valid, errors = planner.validate_plan(plan)
        
        assert not is_valid
        assert any("task" in error for error in errors)  # Too many tasks
        assert any("token" in error for error in errors)  # Token budget
        assert any("time" in error for error in errors)   # Time budget
    
    def test_task_type_classification(self, planner):
        """Test classification of steps into task types"""
        
        test_cases = [
            ("Gather healing herbs from the forest", "retrieval"),
            ("Calculate the DC for this alchemy check", "computation"),  
            ("Roll 2d6+3 for damage", "computation"),
            ("Verify that all requirements are met", "verification"),
            ("Choose between fire or ice enchantment", "reasoning"),
            ("Create final answer with all sources", "synthesis")
        ]
        
        for step_name, expected_type in test_cases:
            actual_type = planner._classify_step_type(step_name, "")
            assert actual_type == expected_type, f"Expected {expected_type} for '{step_name}', got {actual_type}"
    
    def test_tool_and_model_assignment(self, planner):
        """Test tool and model assignment based on task types"""
        
        # Create plan with various task types
        goal = "Test tool assignment"
        plan = planner.plan_from_goal(goal)
        
        # Check that tasks have appropriate tools/models assigned
        for task in plan.tasks:
            assert task.tool != ""
            assert task.model != ""
            assert task.prompt != ""
            
            # Verify tool mappings
            if task.type == "retrieval":
                assert task.tool == "retriever"
                assert task.model == "claude-3-haiku"
            elif task.type == "computation":
                assert task.tool == "calculator"
                assert task.model == "local"
            elif task.type == "synthesis":
                assert task.tool == "llm"
                assert task.model == "claude-3-sonnet"
    
    def test_cost_estimation_and_checkpoints(self, planner):
        """Test cost estimation and checkpoint identification"""
        
        goal = "Complex reasoning task requiring analysis"
        plan = planner.plan_from_goal(goal)
        
        # Should have reasonable estimates
        assert plan.total_estimated_tokens > 0
        assert plan.total_estimated_time_s > 0
        
        # Should identify checkpoints for expensive tasks
        expensive_tasks = [task for task in plan.tasks if task.estimated_tokens > 5000]
        checkpoint_tasks = [task for task in plan.tasks if task.requires_approval]
        
        # High-cost tasks should require approval
        for task in expensive_tasks:
            assert task.requires_approval
            assert task.id in plan.checkpoints
    
    def test_convenience_function(self, temp_store):
        """Test plan_from_goal convenience function"""
        
        result = plan_from_goal("Test convenience function", temp_store)
        
        # Should return dictionary format
        assert isinstance(result, dict)
        assert "id" in result
        assert "goal" in result
        assert "tasks" in result
        assert "total_estimated_tokens" in result
        
        # Verify task structure in dict format
        tasks = result["tasks"]
        assert len(tasks) > 0
        for task in tasks:
            assert "id" in task
            assert "type" in task
            assert "estimated_tokens" in task


class TestBudgetManager:
    """Test BudgetManager cost tracking and model selection"""
    
    @pytest.fixture
    def budget_manager(self):
        """Create BudgetManager instance"""
        return BudgetManager()
    
    def test_model_selection_by_task_type(self, budget_manager):
        """Test model selection based on task type and requirements"""
        
        # Test speed priority
        speed_model = budget_manager.select_model("retrieval", 1000, "speed")
        assert speed_model in budget_manager.models
        
        # Test cost priority
        cost_model = budget_manager.select_model("computation", 1000, "cost")
        assert cost_model == "local"  # Cheapest option
        
        # Test quality priority
        quality_model = budget_manager.select_model("synthesis", 5000, "quality")
        assert budget_manager.models[quality_model].cost_per_1k_tokens > 1.0  # Should pick expensive model
    
    def test_context_window_constraint(self, budget_manager):
        """Test model selection respects context window limits"""
        
        # Request model for very large context
        large_context_model = budget_manager.select_model("reasoning", 150000, "balanced")
        
        selected_model = budget_manager.models[large_context_model]
        assert selected_model.context_window >= 150000 * 1.1  # Should handle with margin
    
    def test_budget_constraints_by_role(self, budget_manager):
        """Test budget constraints for different user roles"""
        
        admin_budget = budget_manager.get_budget_for_role("admin")
        player_budget = budget_manager.get_budget_for_role("player") 
        guest_budget = budget_manager.get_budget_for_role("guest")
        
        # Admin should have highest limits
        assert admin_budget.max_total_tokens > player_budget.max_total_tokens
        assert admin_budget.max_total_cost_usd > player_budget.max_total_cost_usd
        assert admin_budget.max_time_s > player_budget.max_time_s
        
        # Player should have higher limits than guest
        assert player_budget.max_total_tokens > guest_budget.max_total_tokens
        assert player_budget.max_total_cost_usd > guest_budget.max_total_cost_usd
    
    def test_workflow_cost_estimation(self, budget_manager):
        """Test cost estimation for complete workflows"""
        
        test_tasks = [
            {"id": "task:1", "model": "claude-3-haiku", "estimated_tokens": 1000},
            {"id": "task:2", "model": "claude-3-sonnet", "estimated_tokens": 3000},
            {"id": "task:3", "model": "local", "estimated_tokens": 500}
        ]
        
        estimate = budget_manager.estimate_workflow_cost(test_tasks)
        
        # Verify estimate structure
        assert "total_cost_usd" in estimate
        assert "total_time_s" in estimate
        assert "total_tokens" in estimate
        assert "task_breakdown" in estimate
        
        assert estimate["total_tokens"] == 4500
        assert estimate["total_cost_usd"] > 0
        assert len(estimate["task_breakdown"]) == 3
    
    def test_budget_compliance_check(self, budget_manager):
        """Test budget compliance validation"""
        
        # Create estimate that exceeds guest budget
        expensive_estimate = {
            "total_tokens": 50000,  # Exceeds guest limit
            "total_cost_usd": 10.0,  # Exceeds guest limit
            "total_time_s": 300,     # Exceeds guest limit
            "task_breakdown": [{"task_id": "task:1"}] * 10  # Too many tasks for guest
        }
        
        guest_budget = budget_manager.get_budget_for_role("guest")
        is_compliant, violations = budget_manager.check_budget_compliance(expensive_estimate, guest_budget)
        
        assert not is_compliant
        assert len(violations) >= 3  # Should violate tokens, cost, and tasks limits
        
        # Test with admin budget (should pass)
        admin_budget = budget_manager.get_budget_for_role("admin")
        admin_compliant, admin_violations = budget_manager.check_budget_compliance(expensive_estimate, admin_budget)
        
        assert admin_compliant or len(admin_violations) < len(violations)  # Should be better


class TestModelSelector:
    """Test ModelSelector optimization capabilities"""
    
    @pytest.fixture
    def model_selector(self):
        """Create ModelSelector with BudgetManager"""
        budget_manager = BudgetManager()
        return ModelSelector(budget_manager)
    
    def test_select_for_task_complexity(self, model_selector):
        """Test model selection based on task complexity"""
        
        # Low complexity should use cheap models
        low_model = model_selector.select_for_task("retrieval", "low", {})
        low_cost = model_selector.budget_manager.models[low_model].cost_per_1k_tokens
        
        # High complexity should use better models
        high_model = model_selector.select_for_task("reasoning", "high", {})
        high_cost = model_selector.budget_manager.models[high_model].cost_per_1k_tokens
        
        assert high_cost >= low_cost  # Higher complexity should cost more or equal
    
    def test_select_for_task_constraints(self, model_selector):
        """Test model selection with specific constraints"""
        
        # Speed constraint
        speed_model = model_selector.select_for_task(
            "reasoning", "medium", {"max_latency_ms": 500}
        )
        speed_latency = model_selector.budget_manager.models[speed_model].latency_ms
        assert speed_latency <= 1000  # Should prioritize speed
        
        # Cost constraint
        cost_model = model_selector.select_for_task(
            "computation", "low", {"max_cost_usd": 0.001}
        )
        assert cost_model == "local"  # Should pick cheapest
    
    def test_optimize_plan_models(self, model_selector):
        """Test plan optimization to meet budget constraints"""
        
        # Create expensive plan
        expensive_plan = {
            "id": "plan:expensive",
            "tasks": [
                {"id": "task:1", "type": "reasoning", "model": "gpt-4", "estimated_tokens": 10000},
                {"id": "task:2", "type": "synthesis", "model": "gpt-4", "estimated_tokens": 15000},
                {"id": "task:3", "type": "retrieval", "model": "claude-3-sonnet", "estimated_tokens": 5000}
            ]
        }
        
        # Optimize for guest budget
        guest_budget = model_selector.budget_manager.get_budget_for_role("guest")
        optimized_plan = model_selector.optimize_plan_models(expensive_plan, guest_budget)
        
        # Should have cheaper models
        optimized_estimate = model_selector.budget_manager.estimate_workflow_cost(optimized_plan["tasks"])
        original_estimate = model_selector.budget_manager.estimate_workflow_cost(expensive_plan["tasks"])
        
        assert optimized_estimate["total_cost_usd"] <= original_estimate["total_cost_usd"]


class TestPolicyEnforcer:
    """Test PolicyEnforcer budget validation and approval workflows"""
    
    @pytest.fixture
    def policy_enforcer(self):
        """Create PolicyEnforcer instance"""
        budget_manager = BudgetManager()
        return PolicyEnforcer(budget_manager)
    
    def test_enforce_plan_within_budget(self, policy_enforcer):
        """Test plan enforcement for compliant plans"""
        
        compliant_plan = {
            "id": "plan:compliant",
            "goal": "Simple task within budget",
            "tasks": [
                {"id": "task:1", "model": "claude-3-haiku", "estimated_tokens": 1000}
            ]
        }
        
        is_approved, response = policy_enforcer.enforce_plan(compliant_plan, "player")
        
        assert is_approved
        assert response["compliance"]["approved"]
        assert len(response["compliance"]["violations"]) == 0
    
    def test_enforce_plan_exceeds_budget(self, policy_enforcer):
        """Test plan enforcement for non-compliant plans"""
        
        expensive_plan = {
            "id": "plan:expensive", 
            "goal": "Expensive task exceeding budget",
            "tasks": [
                {"id": "task:1", "model": "gpt-4", "estimated_tokens": 50000}  # Exceeds guest budget
            ]
        }
        
        is_approved, response = policy_enforcer.enforce_plan(expensive_plan, "guest")
        
        # Should not be approved initially
        assert not is_approved
        assert not response["compliance"]["approved"]
        assert len(response["compliance"]["violations"]) > 0
        
        # Should attempt optimization
        assert response.get("optimization_attempted", False)
        
        # May have optimized plan that passes
        if "optimized_plan" in response:
            assert response["optimized_compliance"]["approved"]
    
    def test_create_approval_checkpoint(self, policy_enforcer):
        """Test approval checkpoint creation"""
        
        checkpoint = policy_enforcer.create_approval_checkpoint(
            "plan:test",
            "Budget exceeded",
            {"total_cost_usd": 5.0, "total_tokens": 25000}
        )
        
        # Verify checkpoint structure
        assert checkpoint["plan_id"] == "plan:test"
        assert checkpoint["type"] == "budget_approval"
        assert checkpoint["reason"] == "Budget exceeded"
        assert checkpoint["status"] == "pending"
        assert "approval_url" in checkpoint
        assert checkpoint["checkpoint_id"].startswith("approval:")
    
    def test_policy_hot_reload(self):
        """Test policy configuration hot reload"""
        
        # Create temporary config
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_policies.yaml"
            
            # Write test config
            config_content = """
models:
  test-model:
    name: test-model
    provider: test
    cost_per_1k_tokens: 1.5
    latency_ms: 500
    context_window: 8000
    capabilities: ["reasoning", "retrieval"]

budgets:
  test_role:
    max_total_tokens: 15000
    max_total_cost_usd: 5.0
    max_time_s: 180
    max_parallel_tasks: 5
"""
            
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            # Load with custom config
            budget_manager = BudgetManager(config_path)
            
            # Verify custom model loaded
            assert "test-model" in budget_manager.models
            test_model = budget_manager.models["test-model"]
            assert test_model.cost_per_1k_tokens == 1.5
            assert test_model.latency_ms == 500
            
            # Verify custom budget loaded
            assert "test_role" in budget_manager.default_budgets
            test_budget = budget_manager.default_budgets["test_role"]
            assert test_budget.max_total_tokens == 15000
            assert test_budget.max_total_cost_usd == 5.0
    
    def test_dependency_validation(self, planner):
        """Test validation of task dependencies"""
        
        # Create plan with missing dependency
        task1 = WorkflowTask("task:1", "reasoning", "Task 1", "First task", ["task:missing"], "", "", "", {}, 100, 10)
        
        plan = WorkflowPlan(
            id="plan:bad_deps",
            goal="Test bad dependencies",
            procedure_id=None,
            tasks=[task1],
            edges=[],
            total_estimated_tokens=100,
            total_estimated_time_s=10,
            checkpoints=[],
            created_at=0
        )
        
        is_valid, errors = planner.validate_plan(plan)
        
        assert not is_valid
        assert any("non-existent task" in error for error in errors)