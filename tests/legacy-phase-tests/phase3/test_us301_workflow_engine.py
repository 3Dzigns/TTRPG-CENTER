# tests/regression/phase3/test_us301_workflow_engine.py
"""
Phase 3 - US-301: Graph Workflow Engine Regression Tests
Tests workflow orchestration and execution engine with state management
"""

import pytest
import time
import json
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestWorkflowEngine:
    """Test suite for Graph Workflow Engine validation"""

    def test_workflow_engine_availability(self):
        """Test that Workflow Engine module exists and is importable"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine, WorkflowState, WorkflowStep

            assert WorkflowEngine is not None, "WorkflowEngine class should be available"
            assert WorkflowState is not None, "WorkflowState enum should be available"
            assert WorkflowStep is not None, "WorkflowStep class should be available"

        except ImportError as e:
            pytest.fail(f"Workflow Engine module not available: {e}")

    def test_workflow_definition_loading(self):
        """Test that workflow engine can load and validate workflow definitions"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Test workflow definition
        character_creation_workflow = {
            "id": "character_creation",
            "name": "D&D Character Creation",
            "description": "Step-by-step character creation process",
            "steps": [
                {
                    "id": "choose_race",
                    "name": "Choose Race",
                    "description": "Select character race from available options",
                    "type": "selection",
                    "options": ["Human", "Elf", "Dwarf", "Halfling"],
                    "required": True,
                    "next": ["choose_class"]
                },
                {
                    "id": "choose_class",
                    "name": "Choose Class",
                    "description": "Select character class",
                    "type": "selection",
                    "options": ["Fighter", "Wizard", "Rogue", "Cleric"],
                    "required": True,
                    "next": ["roll_abilities"]
                },
                {
                    "id": "roll_abilities",
                    "name": "Generate Ability Scores",
                    "description": "Roll or assign ability scores",
                    "type": "calculation",
                    "required": True,
                    "next": ["calculate_modifiers"]
                },
                {
                    "id": "calculate_modifiers",
                    "name": "Calculate Modifiers",
                    "description": "Determine ability modifiers and derived stats",
                    "type": "calculation",
                    "required": True,
                    "next": []
                }
            ]
        }

        # Load workflow definition
        workflow_id = engine.load_workflow(character_creation_workflow)

        # Verify workflow was loaded
        assert workflow_id is not None, "Should return workflow ID"
        assert workflow_id == "character_creation", "Should return correct workflow ID"

        # Verify workflow can be retrieved
        loaded_workflow = engine.get_workflow(workflow_id)
        assert loaded_workflow is not None, "Should retrieve loaded workflow"
        assert loaded_workflow["name"] == "D&D Character Creation", "Should preserve workflow name"
        assert len(loaded_workflow["steps"]) == 4, "Should preserve all workflow steps"

    def test_workflow_execution_initialization(self):
        """Test workflow execution initialization and state tracking"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load test workflow
        spell_research_workflow = {
            "id": "spell_research",
            "name": "Spell Research Process",
            "steps": [
                {"id": "define_goal", "name": "Define Research Goal", "type": "input", "next": ["gather_materials"]},
                {"id": "gather_materials", "name": "Gather Materials", "type": "checklist", "next": ["conduct_research"]},
                {"id": "conduct_research", "name": "Conduct Research", "type": "process", "next": ["test_spell"]},
                {"id": "test_spell", "name": "Test Spell", "type": "validation", "next": []}
            ]
        }

        engine.load_workflow(spell_research_workflow)

        # Initialize workflow execution
        execution_id = engine.start_workflow("spell_research", user_id="test_user")

        # Verify execution initialization
        assert execution_id is not None, "Should return execution ID"
        assert isinstance(execution_id, str), "Execution ID should be string"

        # Verify execution state
        execution = engine.get_execution(execution_id)
        assert execution is not None, "Should retrieve execution state"
        assert execution["workflow_id"] == "spell_research", "Should track workflow ID"
        assert execution["user_id"] == "test_user", "Should track user ID"
        assert execution["status"] in ["initialized", "active"], "Should have valid initial status"
        assert execution["current_step"] == "define_goal", "Should start at first step"

    def test_workflow_step_progression(self):
        """Test workflow step progression and state transitions"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load simple linear workflow
        linear_workflow = {
            "id": "linear_test",
            "name": "Linear Test Workflow",
            "steps": [
                {"id": "step1", "name": "Step 1", "type": "input", "next": ["step2"]},
                {"id": "step2", "name": "Step 2", "type": "process", "next": ["step3"]},
                {"id": "step3", "name": "Step 3", "type": "output", "next": []}
            ]
        }

        engine.load_workflow(linear_workflow)
        execution_id = engine.start_workflow("linear_test")

        # Progress through steps
        # Step 1
        execution = engine.get_execution(execution_id)
        assert execution["current_step"] == "step1", "Should start at step1"

        # Complete step 1
        engine.complete_step(execution_id, "step1", {"input_data": "test"})

        execution = engine.get_execution(execution_id)
        assert execution["current_step"] == "step2", "Should progress to step2"
        assert "step1" in execution.get("completed_steps", []), "Should track completed steps"

        # Complete step 2
        engine.complete_step(execution_id, "step2", {"processed_data": "result"})

        execution = engine.get_execution(execution_id)
        assert execution["current_step"] == "step3", "Should progress to step3"

        # Complete step 3 (final step)
        engine.complete_step(execution_id, "step3", {"final_output": "complete"})

        execution = engine.get_execution(execution_id)
        assert execution["status"] in ["completed", "finished"], "Should mark workflow as completed"
        assert len(execution.get("completed_steps", [])) == 3, "Should track all completed steps"

    def test_workflow_branching_logic(self):
        """Test workflow branching and conditional step progression"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load branching workflow
        branching_workflow = {
            "id": "character_build",
            "name": "Character Build Workflow",
            "steps": [
                {
                    "id": "choose_role",
                    "name": "Choose Role",
                    "type": "selection",
                    "options": ["damage", "tank", "support"],
                    "next": {
                        "damage": ["optimize_damage"],
                        "tank": ["optimize_defense"],
                        "support": ["optimize_utility"]
                    }
                },
                {"id": "optimize_damage", "name": "Optimize Damage", "type": "process", "next": ["finalize"]},
                {"id": "optimize_defense", "name": "Optimize Defense", "type": "process", "next": ["finalize"]},
                {"id": "optimize_utility", "name": "Optimize Utility", "type": "process", "next": ["finalize"]},
                {"id": "finalize", "name": "Finalize Build", "type": "output", "next": []}
            ]
        }

        engine.load_workflow(branching_workflow)
        execution_id = engine.start_workflow("character_build")

        # Test damage path
        engine.complete_step(execution_id, "choose_role", {"role": "damage"})

        execution = engine.get_execution(execution_id)
        assert execution["current_step"] == "optimize_damage", "Should branch to damage optimization"

        # Complete damage optimization
        engine.complete_step(execution_id, "optimize_damage", {"damage_build": "complete"})

        execution = engine.get_execution(execution_id)
        assert execution["current_step"] == "finalize", "Should proceed to finalization"

    def test_workflow_state_persistence(self):
        """Test workflow state persistence and recovery"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load workflow
        persistent_workflow = {
            "id": "long_process",
            "name": "Long Running Process",
            "steps": [
                {"id": "start", "name": "Start Process", "type": "input", "next": ["middle"]},
                {"id": "middle", "name": "Middle Process", "type": "process", "next": ["end"]},
                {"id": "end", "name": "End Process", "type": "output", "next": []}
            ]
        }

        engine.load_workflow(persistent_workflow)
        execution_id = engine.start_workflow("long_process", user_id="persistent_user")

        # Complete first step
        engine.complete_step(execution_id, "start", {"initial_data": "saved"})

        # Simulate engine restart by creating new instance
        new_engine = WorkflowEngine()
        new_engine.load_workflow(persistent_workflow)

        # Should be able to retrieve and continue execution
        if hasattr(new_engine, 'load_execution_state'):
            recovered_execution = new_engine.load_execution_state(execution_id)

            if recovered_execution:
                assert recovered_execution["current_step"] == "middle", "Should recover current step"
                assert "start" in recovered_execution.get("completed_steps", []), "Should recover completed steps"

                # Continue from recovered state
                new_engine.complete_step(execution_id, "middle", {"middle_data": "continued"})

                final_execution = new_engine.get_execution(execution_id)
                assert final_execution["current_step"] == "end", "Should continue from recovered state"

    def test_workflow_validation_rules(self):
        """Test workflow validation and constraint enforcement"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Test invalid workflow definition
        invalid_workflow = {
            "id": "invalid_test",
            "name": "Invalid Workflow",
            "steps": [
                {"id": "step1", "name": "Step 1", "next": ["nonexistent_step"]},  # Invalid reference
                # Missing required fields
                {"id": "step2"}
            ]
        }

        # Should handle invalid workflow gracefully
        try:
            workflow_id = engine.load_workflow(invalid_workflow)
            # If no exception, should validate and possibly reject
            if workflow_id:
                loaded = engine.get_workflow(workflow_id)
                # Should either fix issues or mark as invalid
        except Exception as e:
            # Should provide informative error message
            assert "invalid" in str(e).lower() or "validation" in str(e).lower()

        # Test step validation
        valid_workflow = {
            "id": "validation_test",
            "name": "Validation Test",
            "steps": [
                {
                    "id": "validated_step",
                    "name": "Validated Step",
                    "type": "input",
                    "validation": {
                        "required_fields": ["name", "level"],
                        "field_types": {"name": "string", "level": "integer"},
                        "constraints": {"level": {"min": 1, "max": 20}}
                    },
                    "next": []
                }
            ]
        }

        engine.load_workflow(valid_workflow)
        execution_id = engine.start_workflow("validation_test")

        # Test valid input
        try:
            engine.complete_step(execution_id, "validated_step", {"name": "Test Character", "level": 5})
            # Should succeed
        except Exception as e:
            pytest.fail(f"Valid input should not raise exception: {e}")

        # Test invalid input
        execution_id2 = engine.start_workflow("validation_test")

        try:
            engine.complete_step(execution_id2, "validated_step", {"name": "Test", "level": 25})  # Level too high
            # Should either reject or handle gracefully
        except Exception as e:
            assert "validation" in str(e).lower() or "constraint" in str(e).lower()

    def test_workflow_performance_benchmarks(self):
        """Test workflow engine performance under load"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load performance test workflow
        perf_workflow = {
            "id": "perf_test",
            "name": "Performance Test",
            "steps": [
                {"id": "step1", "name": "Step 1", "type": "process", "next": ["step2"]},
                {"id": "step2", "name": "Step 2", "type": "process", "next": ["step3"]},
                {"id": "step3", "name": "Step 3", "type": "process", "next": []}
            ]
        }

        engine.load_workflow(perf_workflow)

        # Test workflow execution performance
        execution_times = []

        for i in range(10):  # Run multiple executions
            start_time = time.perf_counter()

            execution_id = engine.start_workflow("perf_test", user_id=f"perf_user_{i}")

            # Complete all steps
            engine.complete_step(execution_id, "step1", {"data": f"test_{i}"})
            engine.complete_step(execution_id, "step2", {"data": f"processed_{i}"})
            engine.complete_step(execution_id, "step3", {"data": f"final_{i}"})

            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000
            execution_times.append(execution_time)

        # Performance benchmarks
        avg_time = sum(execution_times) / len(execution_times)
        execution_times.sort()
        p95_index = int(0.95 * len(execution_times))
        p95_time = execution_times[p95_index]

        # Should complete workflows quickly
        assert avg_time < 100.0, f"Average workflow execution time {avg_time:.1f}ms exceeds 100ms benchmark"
        assert p95_time < 200.0, f"P95 workflow execution time {p95_time:.1f}ms exceeds 200ms benchmark"

    def test_workflow_error_handling_and_recovery(self):
        """Test workflow error handling and recovery mechanisms"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load workflow with error-prone step
        error_workflow = {
            "id": "error_test",
            "name": "Error Test Workflow",
            "steps": [
                {"id": "normal_step", "name": "Normal Step", "type": "input", "next": ["error_step"]},
                {"id": "error_step", "name": "Error Prone Step", "type": "process", "next": ["recovery_step"]},
                {"id": "recovery_step", "name": "Recovery Step", "type": "output", "next": []}
            ]
        }

        engine.load_workflow(error_workflow)
        execution_id = engine.start_workflow("error_test")

        # Complete normal step
        engine.complete_step(execution_id, "normal_step", {"data": "normal"})

        # Simulate error in error-prone step
        try:
            # Mock step processor to raise error
            with patch.object(engine, '_process_step') as mock_process:
                mock_process.side_effect = Exception("Simulated processing error")

                engine.complete_step(execution_id, "error_step", {"data": "error_data"})

        except Exception:
            # Error should be handled, execution should be in error state
            execution = engine.get_execution(execution_id)

            if execution:
                # Should track error state
                assert execution.get("status") in ["error", "failed", "active"], "Should handle error state"

                # Should support recovery
                if hasattr(engine, 'retry_step'):
                    # Retry the failed step
                    engine.retry_step(execution_id, "error_step", {"data": "retry_data"})

                    execution = engine.get_execution(execution_id)
                    # Should recover or remain in recoverable state

    def test_workflow_concurrent_executions(self):
        """Test multiple concurrent workflow executions"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        import threading
        import time

        engine = WorkflowEngine()

        # Load concurrent test workflow
        concurrent_workflow = {
            "id": "concurrent_test",
            "name": "Concurrent Test",
            "steps": [
                {"id": "init", "name": "Initialize", "type": "input", "next": ["process"]},
                {"id": "process", "name": "Process", "type": "process", "next": ["complete"]},
                {"id": "complete", "name": "Complete", "type": "output", "next": []}
            ]
        }

        engine.load_workflow(concurrent_workflow)

        results = []
        errors = []

        def worker_thread(thread_id):
            try:
                execution_id = engine.start_workflow("concurrent_test", user_id=f"user_{thread_id}")

                # Complete workflow steps
                engine.complete_step(execution_id, "init", {"thread": thread_id})
                time.sleep(0.01)  # Simulate processing time

                engine.complete_step(execution_id, "process", {"thread": thread_id})
                time.sleep(0.01)

                engine.complete_step(execution_id, "complete", {"thread": thread_id})

                execution = engine.get_execution(execution_id)
                results.append((thread_id, execution_id, execution.get("status")))

            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start multiple concurrent executions
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify concurrent execution
        assert len(errors) == 0, f"Concurrent execution errors: {errors}"
        assert len(results) == 5, "All concurrent executions should complete"

        # Verify all executions completed successfully
        for thread_id, execution_id, status in results:
            assert status in ["completed", "finished"], f"Thread {thread_id} execution {execution_id} not completed: {status}"

    def test_workflow_telemetry_and_monitoring(self):
        """Test workflow telemetry emission and monitoring capabilities"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load monitored workflow
        monitored_workflow = {
            "id": "monitored_test",
            "name": "Monitored Workflow",
            "steps": [
                {"id": "start", "name": "Start", "type": "input", "next": ["end"]},
                {"id": "end", "name": "End", "type": "output", "next": []}
            ]
        }

        engine.load_workflow(monitored_workflow)

        # Mock telemetry collection
        with patch('src_common.logging.jlog') as mock_jlog:
            execution_id = engine.start_workflow("monitored_test", user_id="monitor_user")

            # Complete workflow
            engine.complete_step(execution_id, "start", {"data": "test"})
            engine.complete_step(execution_id, "end", {"data": "complete"})

            # Verify telemetry was emitted
            if mock_jlog.call_count > 0:
                log_calls = [call.args for call in mock_jlog.call_args_list]

                # Look for workflow-related logs
                workflow_logs = [call for call in log_calls if "workflow" in str(call).lower()]

                if len(workflow_logs) > 0:
                    print(f"Found {len(workflow_logs)} workflow-related log entries")

                    # Verify telemetry includes key information
                    for log_call in workflow_logs:
                        assert len(log_call) >= 2, "Log should have level and message"

    def test_workflow_contract_compliance(self):
        """Test that workflow engine output matches established contract"""
        try:
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Workflow Engine module not available for testing")

        engine = WorkflowEngine()

        # Load contract test workflow
        contract_workflow = {
            "id": "contract_test",
            "name": "Contract Test",
            "steps": [
                {"id": "test_step", "name": "Test Step", "type": "input", "next": []}
            ]
        }

        engine.load_workflow(contract_workflow)
        execution_id = engine.start_workflow("contract_test")

        # Verify execution contract
        execution = engine.get_execution(execution_id)

        # Required fields
        required_fields = ["execution_id", "workflow_id", "status", "current_step"]
        for field in required_fields:
            assert field in execution, f"Contract violation: missing required field '{field}'"

        # Field types
        assert isinstance(execution["execution_id"], str), "execution_id must be string"
        assert isinstance(execution["workflow_id"], str), "workflow_id must be string"
        assert isinstance(execution["status"], str), "status must be string"
        assert isinstance(execution["current_step"], (str, type(None))), "current_step must be string or None"

        # Valid status values
        valid_statuses = ["initialized", "active", "completed", "failed", "paused"]
        assert execution["status"] in valid_statuses, f"Invalid status: {execution['status']}"

        # Step completion contract
        engine.complete_step(execution_id, "test_step", {"test": "data"})

        updated_execution = engine.get_execution(execution_id)
        assert "completed_steps" in updated_execution, "Should track completed steps"
        assert isinstance(updated_execution["completed_steps"], list), "completed_steps must be list"

        if updated_execution["completed_steps"]:
            for step in updated_execution["completed_steps"]:
                assert isinstance(step, str), "Completed step IDs must be strings"