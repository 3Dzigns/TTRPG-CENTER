# tests/regression/phase3/test_us302_interactive_workflows.py
"""
Phase 3 - US-302: Interactive Workflow Regression Tests
Tests user interaction capabilities and real-time workflow guidance
"""

import pytest
import time
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock


class TestInteractiveWorkflows:
    """Test suite for Interactive Workflow validation"""

    def test_interactive_workflow_availability(self):
        """Test that Interactive Workflow module exists and is importable"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager, UserInteraction

            assert InteractiveWorkflowManager is not None, "InteractiveWorkflowManager class should be available"
            assert UserInteraction is not None, "UserInteraction class should be available"

        except ImportError as e:
            pytest.fail(f"Interactive Workflow module not available: {e}")

    def test_user_prompt_generation(self):
        """Test generation of contextual user prompts and questions"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Test character creation prompts
        character_step = {
            "id": "choose_race",
            "name": "Choose Character Race",
            "type": "selection",
            "description": "Select your character's race",
            "options": ["Human", "Elf", "Dwarf", "Halfling", "Dragonborn"],
            "context": {
                "racial_traits": {
                    "Human": "Versatile with extra skill",
                    "Elf": "Darkvision and keen senses",
                    "Dwarf": "Hardy with poison resistance"
                }
            }
        }

        prompt = manager.generate_user_prompt(character_step)

        # Verify prompt structure
        assert isinstance(prompt, dict), "Prompt should be a dictionary"
        assert "question" in prompt, "Prompt should have question field"
        assert "options" in prompt, "Prompt should have options field"
        assert "context" in prompt, "Prompt should have context field"

        # Verify content quality
        assert len(prompt["question"]) > 0, "Question should not be empty"
        assert len(prompt["options"]) > 0, "Should have option choices"

        # Verify options include descriptions
        for option in prompt["options"]:
            assert "value" in option, "Option should have value"
            assert "description" in option, "Option should have description"

    def test_user_input_validation(self):
        """Test validation of user input against step requirements"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Test input validation for different step types
        validation_tests = [
            # Selection validation
            {
                "step": {
                    "type": "selection",
                    "options": ["option1", "option2", "option3"],
                    "required": True
                },
                "valid_inputs": ["option1", "option2"],
                "invalid_inputs": ["option4", "", None]
            },
            # Numeric input validation
            {
                "step": {
                    "type": "numeric",
                    "constraints": {"min": 1, "max": 20},
                    "required": True
                },
                "valid_inputs": [1, 10, 20],
                "invalid_inputs": [0, 21, -5, "not_a_number", None]
            },
            # Text input validation
            {
                "step": {
                    "type": "text",
                    "constraints": {"min_length": 3, "max_length": 50},
                    "required": True
                },
                "valid_inputs": ["abc", "valid name", "character description"],
                "invalid_inputs": ["", "ab", "x" * 51, None]
            }
        ]

        for test_case in validation_tests:
            step = test_case["step"]

            # Test valid inputs
            for valid_input in test_case["valid_inputs"]:
                result = manager.validate_user_input(step, valid_input)
                assert result["valid"] == True, f"Input {valid_input} should be valid for step {step['type']}"

            # Test invalid inputs
            for invalid_input in test_case["invalid_inputs"]:
                result = manager.validate_user_input(step, invalid_input)
                assert result["valid"] == False, f"Input {invalid_input} should be invalid for step {step['type']}"
                assert "error" in result, "Invalid input should include error message"

    def test_real_time_guidance_generation(self):
        """Test real-time contextual guidance and help"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Test guidance for complex decision
        spell_selection_step = {
            "id": "choose_spells",
            "name": "Choose Starting Spells",
            "type": "multi_selection",
            "description": "Select your starting spells",
            "constraints": {"count": 2, "level": 1},
            "context": {
                "available_spells": [
                    {"name": "Magic Missile", "school": "evocation", "damage": "1d4+1"},
                    {"name": "Shield", "school": "abjuration", "ac_bonus": "+5"},
                    {"name": "Detect Magic", "school": "divination", "utility": "high"}
                ],
                "character": {"class": "Wizard", "level": 1}
            }
        }

        guidance = manager.generate_guidance(spell_selection_step)

        # Verify guidance structure
        assert isinstance(guidance, dict), "Guidance should be a dictionary"
        assert "tips" in guidance, "Guidance should include tips"
        assert "recommendations" in guidance, "Guidance should include recommendations"

        # Verify content quality
        assert len(guidance["tips"]) > 0, "Should provide helpful tips"
        assert len(guidance["recommendations"]) > 0, "Should provide recommendations"

        # Test contextual help based on user progress
        user_progress = {
            "character_class": "Wizard",
            "selected_race": "Human",
            "current_step": "choose_spells"
        }

        contextual_guidance = manager.generate_contextual_guidance(spell_selection_step, user_progress)

        # Should be tailored to user's choices
        assert isinstance(contextual_guidance, dict), "Contextual guidance should be a dictionary"
        if "character_class" in contextual_guidance:
            assert "Wizard" in str(contextual_guidance["character_class"]), "Should reference user's class choice"

    def test_workflow_progress_tracking(self):
        """Test progress tracking and visual indicators"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Initialize workflow execution
        workflow_definition = {
            "id": "character_creation",
            "steps": [
                {"id": "race", "name": "Choose Race"},
                {"id": "class", "name": "Choose Class"},
                {"id": "abilities", "name": "Assign Abilities"},
                {"id": "skills", "name": "Choose Skills"},
                {"id": "equipment", "name": "Select Equipment"}
            ]
        }

        execution_id = manager.start_interactive_workflow(workflow_definition, user_id="test_user")

        # Get initial progress
        progress = manager.get_progress(execution_id)

        # Verify progress structure
        assert isinstance(progress, dict), "Progress should be a dictionary"
        assert "total_steps" in progress, "Progress should include total steps"
        assert "completed_steps" in progress, "Progress should include completed steps"
        assert "current_step" in progress, "Progress should include current step"
        assert "percentage" in progress, "Progress should include percentage"

        # Verify initial state
        assert progress["total_steps"] == 5, "Should track total steps"
        assert progress["completed_steps"] == 0, "Should start with no completed steps"
        assert progress["current_step"] == "race", "Should start at first step"
        assert progress["percentage"] == 0.0, "Should start at 0% progress"

        # Complete a step and verify progress update
        manager.complete_interactive_step(execution_id, "race", {"race": "Human"})

        updated_progress = manager.get_progress(execution_id)
        assert updated_progress["completed_steps"] == 1, "Should track completed step"
        assert updated_progress["current_step"] == "class", "Should advance to next step"
        assert updated_progress["percentage"] == 20.0, "Should update percentage (1/5 = 20%)"

    def test_step_navigation_and_backtracking(self):
        """Test ability to navigate between steps and modify previous choices"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Load workflow that supports backtracking
        backtrack_workflow = {
            "id": "revisable_creation",
            "allow_backtrack": True,
            "steps": [
                {"id": "step1", "name": "First Choice", "revisable": True},
                {"id": "step2", "name": "Second Choice", "revisable": True},
                {"id": "step3", "name": "Final Choice", "revisable": False}
            ]
        }

        execution_id = manager.start_interactive_workflow(backtrack_workflow)

        # Progress through steps
        manager.complete_interactive_step(execution_id, "step1", {"choice1": "valueA"})
        manager.complete_interactive_step(execution_id, "step2", {"choice2": "valueB"})

        # Get current state
        execution = manager.get_execution(execution_id)
        assert execution["current_step"] == "step3", "Should be at step3"

        # Test backtracking to step1
        if hasattr(manager, 'navigate_to_step'):
            success = manager.navigate_to_step(execution_id, "step1")

            if success:
                updated_execution = manager.get_execution(execution_id)
                assert updated_execution["current_step"] == "step1", "Should navigate back to step1"

                # Modify previous choice
                manager.complete_interactive_step(execution_id, "step1", {"choice1": "valueC"})

                # Should be able to progress forward again
                manager.complete_interactive_step(execution_id, "step2", {"choice2": "valueD"})

                final_execution = manager.get_execution(execution_id)
                assert final_execution["current_step"] == "step3", "Should progress back to step3"

                # Verify updated choices are preserved
                step_data = final_execution.get("step_data", {})
                assert step_data.get("step1", {}).get("choice1") == "valueC", "Should preserve updated choice"

    def test_dynamic_step_generation(self):
        """Test dynamic generation of workflow steps based on user choices"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Load workflow with conditional step generation
        dynamic_workflow = {
            "id": "dynamic_character",
            "dynamic_steps": True,
            "steps": [
                {
                    "id": "choose_class",
                    "name": "Choose Class",
                    "type": "selection",
                    "options": ["Wizard", "Fighter", "Rogue"]
                }
                # Additional steps generated based on class choice
            ]
        }

        execution_id = manager.start_interactive_workflow(dynamic_workflow)

        # Choose Wizard class
        manager.complete_interactive_step(execution_id, "choose_class", {"class": "Wizard"})

        # Should generate class-specific steps
        execution = manager.get_execution(execution_id)

        if hasattr(manager, 'generate_dynamic_steps'):
            # Should have generated wizard-specific steps
            available_steps = execution.get("available_steps", [])

            wizard_specific_steps = ["choose_spellbook", "select_cantrips", "choose_school"]
            for step_id in wizard_specific_steps:
                if any(step["id"] == step_id for step in available_steps):
                    # Dynamic step generation is working
                    break
            else:
                # If no specific steps found, verify general dynamic behavior
                assert len(available_steps) > 1, "Should generate additional steps based on class choice"

    def test_workflow_validation_and_completion_checking(self):
        """Test workflow validation and completion requirements"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Load workflow with validation requirements
        validated_workflow = {
            "id": "validated_creation",
            "validation_rules": {
                "character_level_consistency": True,
                "equipment_weight_limit": True,
                "spell_slot_compatibility": True
            },
            "steps": [
                {"id": "basic_info", "name": "Basic Info", "required_fields": ["name", "level"]},
                {"id": "abilities", "name": "Abilities", "validation": "ability_scores_valid"},
                {"id": "equipment", "name": "Equipment", "validation": "weight_limit_check"}
            ]
        }

        execution_id = manager.start_interactive_workflow(validated_workflow)

        # Complete steps with valid data
        manager.complete_interactive_step(execution_id, "basic_info", {
            "name": "Test Character",
            "level": 5
        })

        manager.complete_interactive_step(execution_id, "abilities", {
            "strength": 15,
            "dexterity": 14,
            "constitution": 13,
            "intelligence": 12,
            "wisdom": 10,
            "charisma": 8
        })

        # Test completion validation
        validation_result = manager.validate_workflow_completion(execution_id)

        assert isinstance(validation_result, dict), "Validation result should be a dictionary"
        assert "valid" in validation_result, "Should indicate if workflow is valid"
        assert "issues" in validation_result, "Should list any validation issues"

        # If validation is implemented, should check consistency
        if validation_result.get("valid") is False:
            assert len(validation_result["issues"]) > 0, "Should list specific validation issues"

    def test_workflow_save_and_resume(self):
        """Test ability to save workflow progress and resume later"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Start workflow
        save_workflow = {
            "id": "saveable_workflow",
            "steps": [
                {"id": "step1", "name": "First Step"},
                {"id": "step2", "name": "Second Step"},
                {"id": "step3", "name": "Third Step"}
            ]
        }

        execution_id = manager.start_interactive_workflow(save_workflow, user_id="save_user")

        # Make progress
        manager.complete_interactive_step(execution_id, "step1", {"data": "saved_progress"})

        # Save workflow state
        if hasattr(manager, 'save_workflow_state'):
            save_result = manager.save_workflow_state(execution_id)

            assert save_result.get("success") == True, "Should successfully save workflow state"

            # Simulate session restart
            new_manager = InteractiveWorkflowManager()

            # Resume workflow
            if hasattr(new_manager, 'resume_workflow'):
                resumed_execution_id = new_manager.resume_workflow("save_user", "saveable_workflow")

                if resumed_execution_id:
                    resumed_execution = new_manager.get_execution(resumed_execution_id)

                    # Should preserve progress
                    assert resumed_execution["current_step"] == "step2", "Should resume at correct step"

                    # Should preserve step data
                    step_data = resumed_execution.get("step_data", {})
                    assert step_data.get("step1", {}).get("data") == "saved_progress", "Should preserve step data"

    def test_multi_user_workflow_collaboration(self):
        """Test collaborative workflows with multiple users"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Load collaborative workflow
        collab_workflow = {
            "id": "party_creation",
            "collaborative": True,
            "max_participants": 4,
            "steps": [
                {"id": "party_composition", "name": "Plan Party", "collaborative": True},
                {"id": "role_assignment", "name": "Assign Roles", "collaborative": True},
                {"id": "coordination", "name": "Coordinate Builds", "collaborative": True}
            ]
        }

        # Start collaborative session
        if hasattr(manager, 'start_collaborative_workflow'):
            session_id = manager.start_collaborative_workflow(collab_workflow, organizer_id="user1")

            if session_id:
                # Add participants
                manager.add_participant(session_id, "user2")
                manager.add_participant(session_id, "user3")

                # Get session info
                session = manager.get_collaborative_session(session_id)

                assert len(session["participants"]) == 3, "Should track all participants"
                assert session["organizer"] == "user1", "Should track organizer"

                # Test collaborative input
                manager.submit_collaborative_input(session_id, "user1", "party_composition", {
                    "suggestion": "Tank, Healer, DPS, Support"
                })

                manager.submit_collaborative_input(session_id, "user2", "party_composition", {
                    "agreement": True,
                    "role_preference": "Tank"
                })

                # Check collaborative progress
                collab_progress = manager.get_collaborative_progress(session_id)

                assert "inputs" in collab_progress, "Should track collaborative inputs"
                assert len(collab_progress["inputs"]) >= 2, "Should collect inputs from multiple users"

    def test_interactive_workflow_performance(self):
        """Test interactive workflow performance and responsiveness"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Load performance test workflow
        perf_workflow = {
            "id": "perf_interactive",
            "steps": [
                {"id": "quick_step", "name": "Quick Step", "type": "selection"},
                {"id": "complex_step", "name": "Complex Step", "type": "multi_selection"},
                {"id": "final_step", "name": "Final Step", "type": "text"}
            ]
        }

        # Test prompt generation performance
        start_time = time.perf_counter()

        execution_id = manager.start_interactive_workflow(perf_workflow)

        for step_id in ["quick_step", "complex_step", "final_step"]:
            prompt_start = time.perf_counter()
            prompt = manager.generate_user_prompt({"id": step_id, "type": "selection"})
            prompt_end = time.perf_counter()

            prompt_time = (prompt_end - prompt_start) * 1000
            assert prompt_time < 50.0, f"Prompt generation for {step_id} took {prompt_time:.1f}ms, should be < 50ms"

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000

        # Should be responsive for real-time interaction
        assert total_time < 200.0, f"Interactive workflow initialization took {total_time:.1f}ms, should be < 200ms"

    def test_interactive_workflow_contract_compliance(self):
        """Test that interactive workflow output matches established contract"""
        try:
            from src_common.graph.interactive_workflows import InteractiveWorkflowManager
        except ImportError:
            pytest.skip("Interactive Workflow module not available for testing")

        manager = InteractiveWorkflowManager()

        # Test prompt generation contract
        test_step = {
            "id": "test_step",
            "name": "Test Step",
            "type": "selection",
            "options": ["option1", "option2"]
        }

        prompt = manager.generate_user_prompt(test_step)

        # Verify prompt contract
        required_prompt_fields = ["question", "options", "step_id", "step_type"]
        for field in required_prompt_fields:
            assert field in prompt, f"Prompt contract violation: missing field '{field}'"

        # Verify field types
        assert isinstance(prompt["question"], str), "Question must be string"
        assert isinstance(prompt["options"], list), "Options must be list"
        assert isinstance(prompt["step_id"], str), "Step ID must be string"

        # Test validation contract
        validation_result = manager.validate_user_input(test_step, "option1")

        required_validation_fields = ["valid", "value"]
        for field in required_validation_fields:
            assert field in validation_result, f"Validation contract violation: missing field '{field}'"

        assert isinstance(validation_result["valid"], bool), "Valid field must be boolean"

        if not validation_result["valid"]:
            assert "error" in validation_result, "Invalid result must include error message"

        # Test progress contract
        workflow = {"id": "contract_test", "steps": [{"id": "step1"}]}
        execution_id = manager.start_interactive_workflow(workflow)

        progress = manager.get_progress(execution_id)

        required_progress_fields = ["total_steps", "completed_steps", "current_step", "percentage"]
        for field in required_progress_fields:
            assert field in progress, f"Progress contract violation: missing field '{field}'"

        # Verify field types and constraints
        assert isinstance(progress["total_steps"], int), "Total steps must be integer"
        assert isinstance(progress["completed_steps"], int), "Completed steps must be integer"
        assert isinstance(progress["percentage"], (int, float)), "Percentage must be numeric"
        assert 0.0 <= progress["percentage"] <= 100.0, "Percentage must be between 0 and 100"