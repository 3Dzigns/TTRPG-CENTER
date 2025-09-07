# tests/functional/test_phase3_workflows.py
"""
Functional tests for Phase 3 - Graph-centered workflows
End-to-end testing of planning, execution, and reasoning
"""

import pytest
import asyncio
from pathlib import Path
import tempfile

from src_common.graph.store import GraphStore
from src_common.graph.build import GraphBuilder
from src_common.planner.plan import TaskPlanner, plan_from_goal
from src_common.runtime.execute import WorkflowExecutor, run_plan
from src_common.runtime.state import WorkflowStateStore
from src_common.reason.graphwalk import GraphGuidedReasoner

class TestPhase3Workflows:
    """End-to-end tests for Phase 3 workflow capabilities"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            yield workspace
    
    @pytest.fixture
    def graph_store(self, temp_workspace):
        """Create graph store with test data"""
        store = GraphStore(storage_path=temp_workspace / "graph")
        
        # Add test procedure: Craft Healing Potion
        store.upsert_node(
            "proc:craft:healing_potion",
            "Procedure",
            {
                "name": "Craft Healing Potion",
                "procedure_type": "crafting",
                "description": "Create a healing potion using alchemical methods",
                "difficulty": "medium"
            }
        )
        
        # Add steps
        steps = [
            {"id": "step:gather:reagents", "name": "Gather Reagents", "step_number": 1},
            {"id": "step:prepare:workspace", "name": "Prepare Workspace", "step_number": 2},
            {"id": "step:mix:ingredients", "name": "Mix Ingredients", "step_number": 3},
            {"id": "step:apply:heat", "name": "Apply Heat", "step_number": 4},
            {"id": "step:test:potency", "name": "Test Potency", "step_number": 5}
        ]
        
        for step in steps:
            store.upsert_node(
                step["id"],
                "Step",
                {
                    "name": step["name"],
                    "step_number": step["step_number"],
                    "procedure_id": "proc:craft:healing_potion"
                }
            )
            
            # Link step to procedure
            store.upsert_edge("proc:craft:healing_potion", "part_of", step["id"], {"order": step["step_number"]})
            
            # Link sequential dependencies
            if step["step_number"] > 1:
                prev_step_id = f"step:{steps[step['step_number']-2]['id'].split(':')[1]}:{steps[step['step_number']-2]['id'].split(':')[2]}"
                store.upsert_edge(step["id"], "prereq", prev_step_id, {"sequence": step["step_number"]})
        
        # Add rules and concepts
        store.upsert_node(
            "rule:alchemy:dc", 
            "Rule",
            {
                "text": "Alchemy checks require DC 15 + item level",
                "rule_type": "mechanical"
            }
        )
        
        store.upsert_node(
            "concept:healing_potion",
            "Concept", 
            {
                "name": "Healing Potion",
                "category": "consumable",
                "description": "Magical liquid that restores hit points"
            }
        )
        
        # Link procedure to rule and concept
        store.upsert_edge("proc:craft:healing_potion", "implements", "rule:alchemy:dc", {})
        store.upsert_edge("proc:craft:healing_potion", "produces", "concept:healing_potion", {})
        
        return store
    
    @pytest.fixture 
    def state_store(self, temp_workspace):
        """Create workflow state store"""
        return WorkflowStateStore(storage_path=temp_workspace / "workflows")
    
    def test_craft_potion_planning(self, graph_store):
        """Test planning workflow for crafting procedure"""
        planner = TaskPlanner(graph_store)
        
        goal = "Craft a healing potion for a level 3 character"
        plan = planner.plan_from_goal(goal)
        
        # Verify plan structure
        assert plan.goal == goal
        assert plan.procedure_id == "proc:craft:healing_potion"
        assert len(plan.tasks) >= 5  # Should have tasks for each step
        assert plan.total_estimated_tokens > 0
        assert plan.total_estimated_time_s > 0
        
        # Verify plan is valid
        is_valid, errors = planner.validate_plan(plan)
        assert is_valid, f"Plan validation failed: {errors}"
    
    @pytest.mark.asyncio
    async def test_workflow_execution(self, graph_store, state_store):
        """Test complete workflow execution with state tracking"""
        
        # Create plan
        planner = TaskPlanner(graph_store)
        plan = planner.plan_from_goal("Craft a healing potion")
        
        # Execute workflow
        executor = WorkflowExecutor(state_store, max_parallel=2)
        result = await executor.run_plan(plan.to_dict())
        
        # Verify execution results
        assert "workflow_id" in result
        assert result["status"] in ["completed", "failed"]
        assert "tasks" in result
        assert len(result["tasks"]) >= 1
        
        # Verify state persistence
        workflow_state = await state_store.get_workflow_state(result["workflow_id"])
        assert workflow_state is not None
        assert workflow_state.goal == plan.goal
    
    @pytest.mark.asyncio
    async def test_graph_guided_reasoning(self, graph_store):
        """Test multi-hop reasoning using graph guidance"""
        
        def mock_retriever(query):
            return [
                {
                    "id": f"chunk:mock:{hash(query) % 100}",
                    "content": f"Retrieved information about {query}",
                    "score": 0.85,
                    "metadata": {"page": 156, "section": "Crafting Rules"}
                }
            ]
        
        reasoner = GraphGuidedReasoner(graph_store, mock_retriever)
        
        goal = "What are the requirements for crafting a healing potion?"
        trace = reasoner.graph_guided_answer(goal, max_hops=3)
        
        # Verify reasoning trace
        assert trace.goal == goal
        assert trace.seed_node is not None
        assert len(trace.hops) >= 1
        assert trace.total_confidence > 0
        assert len(trace.sources) > 0
        assert trace.duration_s > 0
        
        # Verify answer content
        assert len(trace.answer) > 50  # Non-trivial answer
        assert "craft" in trace.answer.lower() or "potion" in trace.answer.lower()
    
    def test_procedure_from_chunks(self, graph_store):
        """Test building procedure graph from chunks"""
        
        # Mock chunks from ingestion
        chunks = [
            {
                "id": "chunk:1",
                "content": "To craft a healing potion, first gather the required reagents: 2 units of healing herbs and 1 vial of purified water.",
                "metadata": {"page": 156, "section": "Alchemy Basics"}
            },
            {
                "id": "chunk:2", 
                "content": "Step 2: Prepare your alchemical workspace with proper ventilation and heat source.",
                "metadata": {"page": 156, "section": "Alchemy Basics"}
            },
            {
                "id": "chunk:3",
                "content": "Step 3: Mix the ingredients carefully, then apply gentle heat for 10 minutes.",
                "metadata": {"page": 157, "section": "Alchemy Basics"}
            }
        ]
        
        builder = GraphBuilder(graph_store)
        result = builder.build_procedure_from_chunks(chunks)
        
        # Verify procedure extraction
        assert result.procedure["type"] == "Procedure"
        assert "healing" in result.procedure["properties"]["name"].lower()
        assert len(result.steps) >= 2  # Should extract at least 2 steps
        assert len(result.edges) > 0  # Should have relationships
        assert len(result.source_docs) > 0  # Should reference sources
    
    @pytest.mark.asyncio 
    async def test_workflow_resume(self, graph_store, state_store):
        """Test workflow resume functionality"""
        
        # Create and start workflow
        planner = TaskPlanner(graph_store)
        plan = planner.plan_from_goal("Test resumable workflow")
        
        executor = WorkflowExecutor(state_store)
        
        # Mock a task function that fails on first task
        call_count = 0
        async def failing_task_fn(task):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated failure")
            return {"result": f"Success for {task['id']}"}
        
        # First execution should fail
        result1 = await executor.run_plan(plan.to_dict(), failing_task_fn)
        assert result1["status"] in ["failed", "error"]
        
        # Resume should succeed
        result2 = await executor.resume_workflow(result1["workflow_id"], failing_task_fn)
        assert result2["status"] == "completed" or "resumed_tasks" in result2
    
    def test_budget_enforcement(self, graph_store):
        """Test budget constraint enforcement"""
        from src_common.planner.budget import BudgetManager, PolicyEnforcer, BudgetConstraints
        
        budget_manager = BudgetManager()
        enforcer = PolicyEnforcer(budget_manager)
        
        # Create expensive plan
        expensive_plan = {
            "id": "plan:expensive",
            "goal": "Complex expensive task",
            "tasks": [
                {
                    "id": "task:1",
                    "model": "gpt-4",
                    "estimated_tokens": 50000  # Exceeds typical budgets
                }
            ]
        }
        
        # Test with guest role (low budget)
        is_approved, response = enforcer.enforce_plan(expensive_plan, "guest")
        
        # Should not be approved due to budget
        assert not is_approved
        assert "violations" in response["compliance"]
        assert len(response["compliance"]["violations"]) > 0
    
    def test_rules_verification(self):
        """Test rules verification for procedure compliance"""
        from src_common.reason.executors import RulesVerifier
        
        verifier = RulesVerifier()
        
        # Test valid action
        result = verifier.verify_against_rules(
            "Craft healing potion using proper alchemy workspace",
            ["rule:alchemy:dc"],
            {"level": 3, "workspace": "properly_equipped"}
        )
        
        assert result.success
        assert len(result.errors) == 0
        assert len(result.sources) > 0
    
    def test_dc_computation(self):
        """Test DC computation for various scenarios"""
        from src_common.reason.executors import ComputeDCExecutor
        
        dc_executor = ComputeDCExecutor()
        
        # Test basic crafting DC
        result = dc_executor.compute_dc(
            "Craft a healing potion",
            {
                "level": 3,
                "circumstances": ["proper workspace"],
                "environment": "calm workshop"
            }
        )
        
        assert result.success
        assert result.result["final_dc"] >= 10  # Should be reasonable DC
        assert result.result["base_dc"] in [10, 15, 20]  # Standard DC values
        assert len(result.result["modifiers"]) >= 0  # May have modifiers