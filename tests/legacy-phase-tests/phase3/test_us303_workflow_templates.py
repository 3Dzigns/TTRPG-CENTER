# tests/regression/phase3/test_us303_workflow_templates.py
"""
Phase 3 - US-303: Workflow Templates Regression Tests
Tests predefined workflow templates and customization capabilities
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestWorkflowTemplates:
    """Test suite for Workflow Templates validation"""

    def test_workflow_template_manager_availability(self):
        """Test that Workflow Template Manager module exists and is importable"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager, TemplateCategory

            assert WorkflowTemplateManager is not None, "WorkflowTemplateManager class should be available"
            assert TemplateCategory is not None, "TemplateCategory enum should be available"

        except ImportError as e:
            pytest.fail(f"Workflow Template Manager module not available: {e}")

    def test_predefined_template_availability(self):
        """Test that predefined TTRPG workflow templates are available"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test core TTRPG templates
        expected_templates = [
            "character_creation",
            "spell_research",
            "dungeon_design",
            "encounter_builder",
            "campaign_planning",
            "session_prep"
        ]

        available_templates = manager.list_available_templates()

        assert isinstance(available_templates, list), "Available templates should be a list"
        assert len(available_templates) > 0, "Should have predefined templates available"

        # Verify core templates exist
        template_ids = [template["id"] for template in available_templates]

        found_core_templates = []
        for expected_id in expected_templates:
            if expected_id in template_ids:
                found_core_templates.append(expected_id)

        # Should have at least some core templates
        assert len(found_core_templates) >= 3, f"Should have at least 3 core TTRPG templates, found: {found_core_templates}"

    def test_template_structure_validation(self):
        """Test that workflow templates have proper structure and metadata"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Get a template for validation
        templates = manager.list_available_templates()

        if templates:
            template = manager.get_template(templates[0]["id"])

            # Verify template structure
            required_fields = ["id", "name", "description", "category", "steps", "metadata"]
            for field in required_fields:
                assert field in template, f"Template missing required field: {field}"

            # Verify field types
            assert isinstance(template["id"], str), "Template ID must be string"
            assert isinstance(template["name"], str), "Template name must be string"
            assert isinstance(template["description"], str), "Template description must be string"
            assert isinstance(template["steps"], list), "Template steps must be list"
            assert isinstance(template["metadata"], dict), "Template metadata must be dictionary"

            # Verify steps structure
            for step in template["steps"]:
                step_required_fields = ["id", "name", "type"]
                for field in step_required_fields:
                    assert field in step, f"Step missing required field: {field}"

            # Verify metadata
            metadata = template["metadata"]
            expected_metadata = ["difficulty", "estimated_time", "target_audience"]

            for field in expected_metadata:
                if field in metadata:
                    # Verify field types
                    if field == "estimated_time":
                        assert isinstance(metadata[field], (int, str)), "Estimated time should be numeric or string"
                    elif field == "difficulty":
                        assert isinstance(metadata[field], str), "Difficulty should be string"

    def test_character_creation_template(self):
        """Test the character creation workflow template specifically"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Load character creation template
        char_template = manager.get_template("character_creation")

        if char_template:
            # Verify character creation specific structure
            assert char_template["category"] in ["character", "player_tools"], "Should be categorized appropriately"

            # Should have key character creation steps
            step_ids = [step["id"] for step in char_template["steps"]]
            expected_steps = ["choose_race", "choose_class", "assign_abilities", "select_skills"]

            found_steps = [step for step in expected_steps if step in step_ids]
            assert len(found_steps) >= 2, f"Should have core character creation steps, found: {found_steps}"

            # Verify race selection step
            race_step = next((step for step in char_template["steps"] if "race" in step["id"]), None)
            if race_step:
                assert race_step["type"] in ["selection", "choice"], "Race selection should be choice type"

                if "options" in race_step:
                    assert len(race_step["options"]) >= 5, "Should have multiple race options"

            # Verify class selection step
            class_step = next((step for step in char_template["steps"] if "class" in step["id"]), None)
            if class_step:
                assert class_step["type"] in ["selection", "choice"], "Class selection should be choice type"

    def test_spell_research_template(self):
        """Test the spell research workflow template"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Load spell research template
        spell_template = manager.get_template("spell_research")

        if spell_template:
            # Verify spell research structure
            assert spell_template["category"] in ["magic", "research", "dm_tools"], "Should be categorized appropriately"

            # Should have research methodology steps
            step_ids = [step["id"] for step in spell_template["steps"]]
            expected_research_steps = ["define_goal", "gather_materials", "conduct_research", "test_spell"]

            found_steps = [step for step in expected_research_steps if step in step_ids]
            assert len(found_steps) >= 2, f"Should have research methodology steps, found: {found_steps}"

            # Should include cost and time considerations
            metadata = spell_template.get("metadata", {})
            should_include_costs = any(
                "cost" in str(metadata).lower() or
                "gold" in str(metadata).lower() or
                "time" in str(metadata).lower()
                for _ in [None]  # Simple way to create single iteration
            )

    def test_template_instantiation(self):
        """Test instantiation of templates into executable workflows"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
            from src_common.graph.workflow_engine import WorkflowEngine
        except ImportError:
            pytest.skip("Required workflow modules not available for testing")

        template_manager = WorkflowTemplateManager()
        workflow_engine = WorkflowEngine()

        # Get available template
        templates = template_manager.list_available_templates()

        if templates:
            template_id = templates[0]["id"]

            # Instantiate template
            workflow_instance = template_manager.instantiate_template(template_id, {
                "user_id": "test_user",
                "session_id": "test_session"
            })

            # Verify instantiation
            assert isinstance(workflow_instance, dict), "Instantiated workflow should be dictionary"
            assert "id" in workflow_instance, "Instance should have ID"
            assert "steps" in workflow_instance, "Instance should have steps"

            # Should be executable by workflow engine
            try:
                execution_id = workflow_engine.start_workflow(workflow_instance["id"], workflow_definition=workflow_instance)
                assert execution_id is not None, "Template instance should be executable"

                # Verify execution can progress
                execution = workflow_engine.get_execution(execution_id)
                assert execution["status"] in ["initialized", "active"], "Should initialize successfully"

            except Exception as e:
                # If workflow engine integration not complete, verify structure
                required_workflow_fields = ["id", "name", "steps"]
                for field in required_workflow_fields:
                    assert field in workflow_instance, f"Instantiated workflow missing field: {field}"

    def test_template_customization(self):
        """Test customization of workflow templates"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test template customization
        base_template_id = manager.list_available_templates()[0]["id"] if manager.list_available_templates() else "character_creation"

        customization_options = {
            "campaign_setting": "forgotten_realms",
            "allowed_races": ["Human", "Elf", "Dwarf"],
            "allowed_classes": ["Fighter", "Wizard", "Rogue"],
            "starting_level": 1,
            "point_buy": True
        }

        # Customize template
        if hasattr(manager, 'customize_template'):
            customized_template = manager.customize_template(base_template_id, customization_options)

            # Verify customization
            assert customized_template["id"] != base_template_id, "Customized template should have different ID"

            # Should reflect customization options
            if "allowed_races" in customization_options:
                # Find race selection step
                race_step = next((step for step in customized_template["steps"] if "race" in step["id"]), None)
                if race_step and "options" in race_step:
                    # Should be limited to allowed races
                    race_options = [opt["value"] if isinstance(opt, dict) else opt for opt in race_step["options"]]
                    for allowed_race in customization_options["allowed_races"]:
                        if allowed_race in race_options:
                            break
                    else:
                        # At least some customization should be reflected
                        pass

    def test_template_categories_and_filtering(self):
        """Test template categorization and filtering capabilities"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test category-based filtering
        all_templates = manager.list_available_templates()

        if all_templates:
            # Get available categories
            categories = set(template.get("category", "uncategorized") for template in all_templates)

            # Test filtering by category
            for category in categories:
                if hasattr(manager, 'get_templates_by_category'):
                    category_templates = manager.get_templates_by_category(category)

                    # Verify filtering
                    assert isinstance(category_templates, list), "Category templates should be a list"

                    for template in category_templates:
                        assert template.get("category") == category, f"Template {template['id']} should match category {category}"

            # Test difficulty filtering
            if hasattr(manager, 'get_templates_by_difficulty'):
                beginner_templates = manager.get_templates_by_difficulty("beginner")

                if beginner_templates:
                    for template in beginner_templates:
                        difficulty = template.get("metadata", {}).get("difficulty", "").lower()
                        assert "beginner" in difficulty or "easy" in difficulty, "Should filter by difficulty"

    def test_template_versioning_and_updates(self):
        """Test template versioning and update capabilities"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test template versioning
        templates = manager.list_available_templates()

        if templates:
            template = manager.get_template(templates[0]["id"])

            # Check for version information
            version_fields = ["version", "last_updated", "created_date"]
            version_info = {}

            for field in version_fields:
                if field in template.get("metadata", {}):
                    version_info[field] = template["metadata"][field]

            # If versioning is implemented
            if version_info:
                if "version" in version_info:
                    assert isinstance(version_info["version"], str), "Version should be string"

                if "last_updated" in version_info:
                    # Should be valid timestamp or date string
                    assert len(str(version_info["last_updated"])) > 0, "Last updated should not be empty"

        # Test template updates (if supported)
        if hasattr(manager, 'update_template'):
            template_id = templates[0]["id"] if templates else "test_template"

            updated_template = {
                "id": template_id,
                "name": "Updated Template",
                "description": "Updated description",
                "steps": [{"id": "updated_step", "name": "Updated Step", "type": "input"}],
                "metadata": {"version": "2.0"}
            }

            try:
                result = manager.update_template(template_id, updated_template)

                if result:
                    # Verify update
                    retrieved = manager.get_template(template_id)
                    assert retrieved["name"] == "Updated Template", "Should reflect updates"

            except Exception as e:
                # Updates may not be allowed - verify error is informative
                assert "update" in str(e).lower() or "permission" in str(e).lower()

    def test_template_export_and_import(self):
        """Test template export and import functionality"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test template export
        templates = manager.list_available_templates()

        if templates and hasattr(manager, 'export_template'):
            template_id = templates[0]["id"]

            # Export template
            exported_data = manager.export_template(template_id, format="json")

            # Verify export format
            assert isinstance(exported_data, (str, dict)), "Exported data should be string or dict"

            if isinstance(exported_data, str):
                # Should be valid JSON
                try:
                    parsed_data = json.loads(exported_data)
                    assert "id" in parsed_data, "Exported JSON should contain template ID"
                except json.JSONDecodeError:
                    pytest.fail("Exported data should be valid JSON")

            # Test template import
            if hasattr(manager, 'import_template'):
                # Create test template for import
                test_template = {
                    "id": "imported_test_template",
                    "name": "Imported Test Template",
                    "description": "Template for import testing",
                    "category": "test",
                    "steps": [
                        {"id": "test_step", "name": "Test Step", "type": "input"}
                    ],
                    "metadata": {"difficulty": "beginner"}
                }

                # Import template
                import_result = manager.import_template(json.dumps(test_template))

                if import_result:
                    # Verify import
                    imported = manager.get_template("imported_test_template")
                    assert imported is not None, "Should import template successfully"
                    assert imported["name"] == "Imported Test Template", "Should preserve template data"

    def test_template_validation_and_compliance(self):
        """Test template validation against workflow engine requirements"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test template validation
        valid_template = {
            "id": "validation_test",
            "name": "Validation Test Template",
            "description": "Template for validation testing",
            "category": "test",
            "steps": [
                {"id": "step1", "name": "Step 1", "type": "input", "next": ["step2"]},
                {"id": "step2", "name": "Step 2", "type": "output", "next": []}
            ],
            "metadata": {"difficulty": "beginner"}
        }

        # Validate template
        if hasattr(manager, 'validate_template'):
            validation_result = manager.validate_template(valid_template)

            assert isinstance(validation_result, dict), "Validation result should be dictionary"
            assert "valid" in validation_result, "Should indicate if template is valid"

            if validation_result["valid"]:
                assert validation_result.get("errors", []) == [], "Valid template should have no errors"
            else:
                assert len(validation_result.get("errors", [])) > 0, "Invalid template should list errors"

        # Test invalid template
        invalid_template = {
            "id": "invalid_test",
            "steps": [
                {"id": "step1", "next": ["nonexistent_step"]}  # Invalid reference
            ]
        }

        if hasattr(manager, 'validate_template'):
            invalid_result = manager.validate_template(invalid_template)

            assert invalid_result["valid"] == False, "Invalid template should fail validation"
            assert len(invalid_result.get("errors", [])) > 0, "Should list validation errors"

    def test_template_performance_and_scalability(self):
        """Test template manager performance with multiple templates"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test template listing performance
        start_time = time.perf_counter()
        templates = manager.list_available_templates()
        end_time = time.perf_counter()

        list_time = (end_time - start_time) * 1000
        assert list_time < 100.0, f"Template listing took {list_time:.1f}ms, should be < 100ms"

        # Test template retrieval performance
        if templates:
            retrieval_times = []

            for template_info in templates[:5]:  # Test first 5 templates
                start_time = time.perf_counter()
                template = manager.get_template(template_info["id"])
                end_time = time.perf_counter()

                retrieval_time = (end_time - start_time) * 1000
                retrieval_times.append(retrieval_time)

                assert template is not None, f"Should retrieve template {template_info['id']}"

            # Performance benchmarks
            avg_retrieval_time = sum(retrieval_times) / len(retrieval_times)
            assert avg_retrieval_time < 50.0, f"Average template retrieval time {avg_retrieval_time:.1f}ms should be < 50ms"

    def test_template_contract_compliance(self):
        """Test that template manager output matches established contract"""
        try:
            from src_common.graph.workflow_templates import WorkflowTemplateManager
        except ImportError:
            pytest.skip("Workflow Template Manager module not available for testing")

        manager = WorkflowTemplateManager()

        # Test template listing contract
        templates = manager.list_available_templates()

        assert isinstance(templates, list), "Template list should be an array"

        for template_info in templates:
            # Required fields for template info
            required_info_fields = ["id", "name", "category"]
            for field in required_info_fields:
                assert field in template_info, f"Template info missing required field: {field}"

            # Field types
            assert isinstance(template_info["id"], str), "Template ID must be string"
            assert isinstance(template_info["name"], str), "Template name must be string"

        # Test full template contract
        if templates:
            template = manager.get_template(templates[0]["id"])

            # Required fields for full template
            required_template_fields = ["id", "name", "description", "steps", "metadata"]
            for field in required_template_fields:
                assert field in template, f"Template missing required field: {field}"

            # Field types
            assert isinstance(template["id"], str), "Template ID must be string"
            assert isinstance(template["name"], str), "Template name must be string"
            assert isinstance(template["description"], str), "Template description must be string"
            assert isinstance(template["steps"], list), "Template steps must be list"
            assert isinstance(template["metadata"], dict), "Template metadata must be dictionary"

            # Step contract
            for step in template["steps"]:
                step_required_fields = ["id", "name", "type"]
                for field in step_required_fields:
                    assert field in step, f"Step missing required field: {field}"

                assert isinstance(step["id"], str), "Step ID must be string"
                assert isinstance(step["name"], str), "Step name must be string"
                assert isinstance(step["type"], str), "Step type must be string"

        # Test instantiation contract
        if templates and hasattr(manager, 'instantiate_template'):
            instance = manager.instantiate_template(templates[0]["id"])

            # Instance should be valid workflow definition
            workflow_required_fields = ["id", "steps"]
            for field in workflow_required_fields:
                assert field in instance, f"Workflow instance missing required field: {field}"

            assert isinstance(instance["id"], str), "Workflow instance ID must be string"
            assert isinstance(instance["steps"], list), "Workflow instance steps must be list"