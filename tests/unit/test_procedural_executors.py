# tests/unit/test_procedural_executors.py
"""
Unit tests for Procedural Executors - Phase 3
Tests checklist execution, DC computation, and rules verification
"""

import pytest
import tempfile
from pathlib import Path

from src_common.graph.store import GraphStore
from src_common.reason.executors import ChecklistExecutor, ComputeDCExecutor, RulesVerifier, ProcedureExecutor, ExecutorResult

class TestChecklistExecutor:
    """Test ChecklistExecutor step-by-step procedure execution"""
    
    @pytest.fixture
    def temp_store(self):
        """Create graph store with checklist test data"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_graph"
            store = GraphStore(storage_path=storage_path)
            
            # Add test procedure
            store.upsert_node("proc:checklist:test", "Procedure", {
                "name": "Checklist Test Procedure",
                "description": "Test procedure for checklist execution"
            })
            
            # Add checklist steps
            steps = [
                {"id": "step:gather", "name": "Gather Materials", "required": True, "step_number": 1},
                {"id": "step:prepare", "name": "Prepare Workspace", "required": True, "step_number": 2},
                {"id": "step:execute", "name": "Execute Procedure", "required": True, "step_number": 3},
                {"id": "step:verify", "name": "Verify Results", "required": False, "step_number": 4}
            ]
            
            for step in steps:
                store.upsert_node(step["id"], "Step", step)
                store.upsert_edge("proc:checklist:test", "part_of", step["id"], {"order": step["step_number"]})
            
            yield store
    
    @pytest.fixture
    def checklist_executor(self, temp_store):
        """Create ChecklistExecutor with test graph store"""
        return ChecklistExecutor(temp_store)
    
    def test_execute_checklist_all_steps_complete(self, checklist_executor):
        """Test checklist execution with all steps completed"""
        
        context = {
            "materials": ["herb", "water"],  # Materials provided
            "workspace": "prepared",         # Workspace ready
            "execution": "completed"         # Execution done
        }
        
        result = checklist_executor.execute_checklist("proc:checklist:test", context)
        
        # Verify successful execution
        assert isinstance(result, ExecutorResult)
        assert result.success
        assert len(result.errors) == 0
        
        # Verify result structure
        checklist_data = result.result
        assert checklist_data["procedure_id"] == "proc:checklist:test"
        assert checklist_data["total_steps"] == 4
        assert checklist_data["completed_steps"] == 4  # All steps should complete
        assert checklist_data["success_rate"] == 1.0
        
        # Verify individual step results
        checklist = checklist_data["checklist"]
        assert len(checklist) == 4
        
        for step_result in checklist:
            assert step_result["completed"]
            assert "name" in step_result
            assert "details" in step_result
    
    def test_execute_checklist_missing_materials(self, checklist_executor):
        """Test checklist execution with missing required materials"""
        
        context = {
            "materials": [],  # No materials provided
            "workspace": "prepared"
        }
        
        result = checklist_executor.execute_checklist("proc:checklist:test", context)
        
        # Should fail due to missing materials
        assert not result.success
        assert len(result.errors) > 0
        
        # Should identify materials step as failed
        checklist = result.result["checklist"]
        gather_step = next((step for step in checklist if "gather" in step["name"].lower()), None)
        assert gather_step is not None
        assert not gather_step["completed"]
    
    def test_execute_checklist_optional_steps(self, checklist_executor):
        """Test handling of optional vs required steps"""
        
        context = {
            "materials": ["herb", "water"],
            "workspace": "prepared",
            "execution": "completed"
            # Missing verification context - optional step should be skipped
        }
        
        result = checklist_executor.execute_checklist("proc:checklist:test", context)
        
        # Should succeed even with optional step issues
        assert result.success or len(result.errors) == 0
        
        checklist = result.result["checklist"]
        
        # Required steps should be completed
        required_steps = [step for step in checklist if step["required"]]
        completed_required = [step for step in required_steps if step["completed"]]
        assert len(completed_required) == len(required_steps)
    
    def test_execute_checklist_no_procedure(self, checklist_executor):
        """Test checklist execution with non-existent procedure"""
        
        result = checklist_executor.execute_checklist("proc:nonexistent", {})
        
        # Should fail gracefully
        assert not result.success
        assert len(result.errors) > 0
        assert "no steps found" in result.errors[0].lower()
    
    def test_mock_procedure_steps_generation(self, checklist_executor):
        """Test mock step generation for procedures without graph data"""
        
        # Test with crafting procedure
        craft_steps = checklist_executor._mock_procedure_steps("proc:craft:something")
        
        assert len(craft_steps) == 4  # Should generate craft-specific steps
        assert any("gather" in step["name"].lower() for step in craft_steps)
        assert any("prepare" in step["name"].lower() for step in craft_steps)
        
        # Test with generic procedure
        generic_steps = checklist_executor._mock_procedure_steps("proc:generic:task")
        
        assert len(generic_steps) == 2  # Should generate generic steps
        assert all(step["required"] for step in generic_steps)  # All should be required


class TestComputeDCExecutor:
    """Test ComputeDCExecutor difficulty calculation"""
    
    @pytest.fixture
    def dc_executor(self):
        """Create ComputeDCExecutor instance"""
        return ComputeDCExecutor()
    
    def test_compute_dc_basic_difficulties(self, dc_executor):
        """Test DC computation for standard difficulty levels"""
        
        test_cases = [
            ("Trivial task that anyone can do", "trivial", 5),
            ("Easy task for beginners", "easy", 10),
            ("Medium difficulty standard task", "medium", 15),
            ("Hard challenging task", "hard", 20),
            ("Very hard expert-level task", "very_hard", 25),
            ("Extreme legendary difficulty", "extreme", 30)
        ]
        
        for task_desc, expected_difficulty, expected_base_dc in test_cases:
            result = dc_executor.compute_dc(task_desc, {})
            
            assert result.success
            dc_data = result.result
            assert dc_data["difficulty_assessment"] == expected_difficulty
            assert dc_data["base_dc"] == expected_base_dc
            assert dc_data["final_dc"] >= expected_base_dc  # May have modifiers
    
    def test_compute_dc_with_modifiers(self, dc_executor):
        """Test DC computation with various modifiers"""
        
        context = {
            "level": 2,  # Low level = easier
            "circumstances": ["proper tools", "good conditions"],
            "environment": "calm workshop"
        }
        
        result = dc_executor.compute_dc("Medium difficulty crafting task", context)
        
        assert result.success
        dc_data = result.result
        
        # Should have low level modifier
        modifiers = dc_data["modifiers"]
        low_level_mod = next((mod for mod in modifiers if "low level" in mod["name"].lower()), None)
        assert low_level_mod is not None
        assert low_level_mod["value"] < 0  # Should reduce DC
        
        # Final DC should be base DC + modifiers
        expected_dc = dc_data["base_dc"] + sum(mod["value"] for mod in modifiers)
        assert dc_data["final_dc"] == max(5, min(expected_dc, 40))  # Clamped
    
    def test_compute_dc_combat_modifiers(self, dc_executor):
        """Test DC computation in combat/stressful situations"""
        
        context = {
            "level": 10,  # High level
            "environment": "combat situation",
            "circumstances": ["time pressure", "disadvantageous position"]
        }
        
        result = dc_executor.compute_dc("Cast spell under pressure", context)
        
        assert result.success
        modifiers = result.result["modifiers"]
        
        # Should have combat modifier
        combat_mod = next((mod for mod in modifiers if "combat" in mod["name"].lower()), None)
        assert combat_mod is not None
        assert combat_mod["value"] > 0  # Should increase DC
    
    def test_dc_clamping_bounds(self, dc_executor):
        """Test DC value clamping to reasonable bounds"""
        
        # Test extreme low case
        low_context = {
            "level": 1,
            "circumstances": ["perfect conditions"] * 5,  # Many advantages
            "environment": "ideal laboratory"
        }
        
        result = dc_executor.compute_dc("Trivial task with many advantages", low_context)
        assert result.result["final_dc"] >= 5  # Should not go below 5
        
        # Test extreme high case
        high_context = {
            "level": 20,
            "circumstances": ["terrible conditions"] * 5,  # Many disadvantages
            "environment": "combat rushed stressed"
        }
        
        result = dc_executor.compute_dc("Extreme task with many disadvantages", high_context)
        assert result.result["final_dc"] <= 40  # Should not exceed 40
    
    def test_dc_explanation_generation(self, dc_executor):
        """Test DC explanation text generation"""
        
        result = dc_executor.compute_dc("Medium task", {
            "level": 3,
            "circumstances": ["advantage"]
        })
        
        explanation = result.result["explanation"]
        
        # Should contain base DC
        assert "DC 15" in explanation  # Medium base
        
        # Should mention modifiers if present
        if result.result["modifiers"]:
            for modifier in result.result["modifiers"]:
                assert modifier["name"] in explanation
        
        # Should show final DC
        assert f"DC {result.result['final_dc']}" in explanation


class TestRulesVerifier:
    """Test RulesVerifier compliance checking"""
    
    @pytest.fixture
    def rules_verifier(self):
        """Create RulesVerifier instance"""
        return RulesVerifier()
    
    def test_verify_against_rules_success(self, rules_verifier):
        """Test successful rules verification"""
        
        action = "Cast fireball spell using spell slot"
        cited_rules = ["rule:spell:components", "rule:spell:slots"]
        context = {"spell_slot": 3, "components": ["verbal", "somatic", "material"]}
        
        result = rules_verifier.verify_against_rules(action, cited_rules, context)
        
        # Should succeed with mock rules
        assert isinstance(result, ExecutorResult)
        assert result.success
        assert len(result.errors) == 0
        assert len(result.sources) > 0  # Should cite rules
    
    def test_verify_rules_violation_detection(self, rules_verifier):
        """Test detection of rule violations"""
        
        # Override rule loading to provide test rules
        def mock_load_rules(cited_rules, context):
            return [
                {
                    "id": "rule:prohibition",
                    "text": "Characters cannot cast spells while unconscious",
                    "rule_type": "prohibition"
                },
                {
                    "id": "rule:requirement",
                    "text": "Spells must have required components available",
                    "rule_type": "requirement"
                }
            ]
        
        rules_verifier._load_rules = mock_load_rules
        
        # Test action that violates prohibition
        action = "Cast spell while unconscious"
        result = rules_verifier.verify_against_rules(action, ["rule:prohibition"], {})
        
        # Should detect violation
        assert not result.success
        assert len(result.errors) > 0
        assert "violates rule" in result.errors[0].lower()
    
    def test_rules_loading_from_graph(self):
        """Test loading rules from graph store"""
        
        # Create graph store with rules
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "rules_graph"
            store = GraphStore(storage_path=storage_path)
            
            # Add test rule
            store.upsert_node("rule:test:1", "Rule", {
                "text": "Test rule text for verification",
                "rule_type": "mechanical"
            })
            
            verifier = RulesVerifier(store)
            
            # Load rules
            rules_data = verifier._load_rules(["rule:test:1"], {})
            
            assert len(rules_data) == 1
            assert rules_data[0]["id"] == "rule:test:1"
            assert rules_data[0]["text"] == "Test rule text for verification"
            assert rules_data[0]["source"] == "graph_store"
    
    def test_rule_compliance_prohibition_patterns(self, rules_verifier):
        """Test detection of prohibition rule violations"""
        
        prohibition_rule = {
            "id": "rule:no_magic",
            "text": "Characters cannot cast spells in antimagic field",
            "rule_type": "prohibition"
        }
        
        # Should detect violation
        violation = rules_verifier._check_rule_compliance(
            "Cast fireball spell in antimagic field",
            prohibition_rule,
            {}
        )
        
        assert violation is not None
        assert violation["severity"] == "critical"
        assert "violates rule" in violation["description"]
        assert "cast" in violation["prohibited_element"] or "spell" in violation["prohibited_element"]
    
    def test_rule_compliance_requirement_patterns(self, rules_verifier):
        """Test detection of requirement rule violations"""
        
        requirement_rule = {
            "id": "rule:components",
            "text": "Spells must have material components available",
            "rule_type": "requirement"
        }
        
        # Should detect missing requirement
        violation = rules_verifier._check_rule_compliance(
            "Cast lightning bolt",  # No mention of components
            requirement_rule,
            {}
        )
        
        assert violation is not None
        assert violation["severity"] == "warning"
        assert "may not meet requirement" in violation["description"]


class TestComputeDCExecutor:
    """Test DC computation logic and modifiers"""
    
    @pytest.fixture
    def dc_executor(self):
        """Create ComputeDCExecutor instance"""
        return ComputeDCExecutor()
    
    def test_difficulty_assessment_keywords(self, dc_executor):
        """Test difficulty assessment from description keywords"""
        
        test_cases = [
            ("Simple basic task", "trivial"),
            ("Easy straightforward action", "easy"), 
            ("Standard medium difficulty", "medium"),
            ("Hard challenging endeavor", "hard"),
            ("Very difficult very hard task", "very_hard"),
            ("Extreme impossible legendary feat", "extreme")
        ]
        
        for description, expected_difficulty in test_cases:
            assessed = dc_executor._assess_difficulty(description)
            assert assessed == expected_difficulty
    
    def test_level_based_modifiers(self, dc_executor):
        """Test level-based DC modifications"""
        
        # Low level character
        low_level_context = {"level": 3}
        modifiers_low = dc_executor._calculate_modifiers("Test task", low_level_context)
        
        low_level_mod = next((mod for mod in modifiers_low if "low level" in mod["name"].lower()), None)
        assert low_level_mod is not None
        assert low_level_mod["value"] < 0  # Should reduce DC
        
        # High level character
        high_level_context = {"level": 18}
        modifiers_high = dc_executor._calculate_modifiers("Test task", high_level_context)
        
        high_level_mod = next((mod for mod in modifiers_high if "high level" in mod["name"].lower()), None)
        assert high_level_mod is not None
        assert high_level_mod["value"] > 0  # Should increase DC
    
    def test_circumstance_modifiers(self, dc_executor):
        """Test circumstance-based modifications"""
        
        context = {
            "circumstances": [
                "advantageous position with good lighting",
                "disadvantageous timing and poor weather"
            ]
        }
        
        modifiers = dc_executor._calculate_modifiers("Test task", context)
        
        # Should have both advantage and disadvantage modifiers
        advantage_mods = [mod for mod in modifiers if "advantage" in mod["name"].lower()]
        disadvantage_mods = [mod for mod in modifiers if "disadvantage" in mod["name"].lower()]
        
        assert len(advantage_mods) >= 1
        assert len(disadvantage_mods) >= 1
        
        # Advantage should reduce DC, disadvantage should increase
        assert advantage_mods[0]["value"] < 0
        assert disadvantage_mods[0]["value"] > 0
    
    def test_environmental_modifiers(self, dc_executor):
        """Test environment-based DC modifications"""
        
        # Combat environment
        combat_context = {"environment": "active combat situation"}
        combat_modifiers = dc_executor._calculate_modifiers("Cast spell", combat_context)
        
        combat_mod = next((mod for mod in combat_modifiers if "combat" in mod["name"].lower()), None)
        assert combat_mod is not None
        assert combat_mod["value"] > 0  # Combat should increase DC
        
        # Rushed environment
        rushed_context = {"environment": "rushed and hurried"}
        rushed_modifiers = dc_executor._calculate_modifiers("Craft item", rushed_context)
        
        rushed_mod = next((mod for mod in rushed_modifiers if "rushed" in mod["name"].lower()), None)
        assert rushed_mod is not None
        assert rushed_mod["value"] > 0  # Rush should increase DC
    
    def test_dc_explanation_formatting(self, dc_executor):
        """Test DC explanation text formatting"""
        
        explanation = dc_executor._generate_dc_explanation(
            "medium", 15,
            [
                {"name": "Low Level", "value": -2},
                {"name": "Combat", "value": +3}
            ],
            16
        )
        
        # Should format as: "Base DC 15 (medium) -2 Low Level +3 Combat = DC 16"
        assert "Base DC 15" in explanation
        assert "(medium)" in explanation
        assert "-2 Low Level" in explanation
        assert "+3 Combat" in explanation
        assert "= DC 16" in explanation


class TestProcedureExecutor:
    """Test ProcedureExecutor orchestration of complete procedures"""
    
    @pytest.fixture
    def procedure_executor(self):
        """Create ProcedureExecutor instance"""
        return ProcedureExecutor()
    
    def test_complete_procedure_execution(self, procedure_executor):
        """Test orchestrated execution of complete procedure"""
        
        parameters = {
            "materials": ["healing_herb", "purified_water"],
            "workspace": "prepared",
            "dc_required": True,
            "dc_task": "Craft healing potion",
            "cited_rules": ["rule:alchemy:basic"]
        }
        
        result = procedure_executor.execute_procedure("proc:test:crafting", parameters)
        
        # Verify complete execution
        assert "procedure_id" in result
        assert "success" in result
        assert "execution_log" in result
        assert "artifacts" in result
        assert "sources" in result
        
        # Should have executed all three phases
        log_steps = [entry["step"] for entry in result["execution_log"]]
        assert "checklist" in log_steps
        assert "dc_computation" in log_steps
        assert "verification" in log_steps
        
        # Should have computed DC
        assert "computed_dc" in result["parameters"]
    
    def test_procedure_execution_without_dc(self, procedure_executor):
        """Test procedure execution without DC computation"""
        
        parameters = {
            "materials": ["item1", "item2"],
            "workspace": "ready"
            # No dc_required or cited_rules
        }
        
        result = procedure_executor.execute_procedure("proc:simple", parameters)
        
        # Should execute successfully with just checklist
        log_steps = [entry["step"] for entry in result["execution_log"]]
        assert "checklist" in log_steps
        assert "dc_computation" not in log_steps  # Should skip DC step
        assert "verification" not in log_steps     # Should skip verification
    
    def test_error_handling_in_procedure_execution(self, procedure_executor):
        """Test error handling during procedure execution"""
        
        # Empty parameters should cause checklist failures
        result = procedure_executor.execute_procedure("proc:test:failing", {})
        
        # Should complete execution but report issues
        assert "procedure_id" in result
        assert "execution_log" in result
        
        # Should have error information from failed steps
        if not result.get("success", True):
            assert "error" in result or any("errors" in entry["result"].__dict__ for entry in result["execution_log"])


class TestExecutorResult:
    """Test ExecutorResult data structure"""
    
    def test_executor_result_structure(self):
        """Test ExecutorResult contains all required fields"""
        
        result = ExecutorResult(
            success=True,
            result={"test": "data"},
            errors=[],
            warnings=["minor warning"],
            sources=[{"source": "test", "page": 1}],
            execution_time_s=1.5
        )
        
        # Verify all fields accessible
        assert result.success is True
        assert result.result["test"] == "data"
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert len(result.sources) == 1
        assert result.execution_time_s == 1.5
    
    def test_executor_result_error_case(self):
        """Test ExecutorResult in error scenarios"""
        
        error_result = ExecutorResult(
            success=False,
            result=None,
            errors=["Critical error occurred", "Secondary error"],
            warnings=[],
            sources=[],
            execution_time_s=0.1
        )
        
        assert not error_result.success
        assert error_result.result is None
        assert len(error_result.errors) == 2
        assert error_result.execution_time_s > 0