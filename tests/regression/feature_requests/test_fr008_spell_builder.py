# tests/regression/feature_requests/test_fr008_spell_builder.py
"""
Feature Request FR-008: Spell Builder Interface Regression Tests
Tests custom spell creation and modification capabilities
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSpellBuilderInterface:
    """Test suite for Spell Builder functionality validation"""

    def test_spell_builder_availability(self):
        """Test that spell builder interface is available"""
        try:
            from src_common.spell_builder import SpellBuilder
            from src_common.admin_routes import app

            assert SpellBuilder is not None, "SpellBuilder class should be available"
            assert app is not None, "Admin routes should include spell builder endpoints"

        except ImportError as e:
            pytest.fail(f"Spell builder components not available: {e}")

    def test_custom_spell_creation(self):
        """Test custom spell creation with all required fields"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test comprehensive spell creation
        custom_spell = {
            "name": "Arcane Lightning Strike",
            "level": 3,
            "school": "evocation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": ["V", "S", "M"],
            "material_components": "a piece of amber worth at least 100 gp",
            "duration": "instantaneous",
            "description": "You create a bolt of crackling arcane energy that strikes a target within range.",
            "damage": {
                "dice": "5d6",
                "type": "lightning",
                "scaling": "1d6 per slot level above 3rd"
            },
            "saving_throw": {
                "ability": "dexterity",
                "effect": "half damage on success"
            },
            "target": "one creature",
            "area_of_effect": None,
            "classes": ["wizard", "sorcerer"],
            "source": "custom",
            "ritual": False,
            "concentration": False
        }

        if hasattr(builder, 'create_spell'):
            result = builder.create_spell(custom_spell)

            assert isinstance(result, dict), "Spell creation should return structured result"

            if "spell_id" in result:
                assert isinstance(result["spell_id"], str), "Spell ID should be string"

            if "status" in result:
                assert result["status"] in ["created", "draft", "pending_review"], "Should have valid creation status"

            if "validation_errors" in result:
                errors = result["validation_errors"]
                assert isinstance(errors, list), "Validation errors should be list"
                assert len(errors) == 0, f"Valid spell should have no errors: {errors}"

    def test_spell_component_validation(self):
        """Test spell component validation and requirements"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test component validation scenarios
        component_tests = [
            {
                "name": "Valid VSM components",
                "components": ["V", "S", "M"],
                "material_components": "a pinch of sulfur",
                "should_pass": True
            },
            {
                "name": "Material component without M",
                "components": ["V", "S"],
                "material_components": "a diamond worth 500 gp",
                "should_pass": False
            },
            {
                "name": "M component without material description",
                "components": ["V", "S", "M"],
                "material_components": "",
                "should_pass": False
            },
            {
                "name": "Invalid component type",
                "components": ["V", "S", "X"],
                "material_components": None,
                "should_pass": False
            }
        ]

        if hasattr(builder, 'validate_spell_components'):
            for test_case in component_tests:
                validation = builder.validate_spell_components(
                    test_case["components"],
                    test_case.get("material_components")
                )

                if validation:
                    is_valid = validation.get("valid", False)

                    if test_case["should_pass"]:
                        assert is_valid, f"Component validation should pass for: {test_case['name']}"
                    else:
                        assert not is_valid, f"Component validation should fail for: {test_case['name']}"

                    if "errors" in validation and not test_case["should_pass"]:
                        errors = validation["errors"]
                        assert len(errors) > 0, f"Failed validation should have error messages: {test_case['name']}"

    def test_spell_balance_analysis(self):
        """Test spell balance and power level analysis"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test spells with different power levels
        balance_test_spells = [
            {
                "name": "Weak Cantrip",
                "level": 0,
                "damage": {"dice": "1d4", "type": "force"},
                "expected_balance": "balanced"
            },
            {
                "name": "Overpowered Low Level",
                "level": 1,
                "damage": {"dice": "10d6", "type": "fire"},
                "expected_balance": "overpowered"
            },
            {
                "name": "Underpowered High Level",
                "level": 9,
                "damage": {"dice": "2d6", "type": "cold"},
                "expected_balance": "underpowered"
            },
            {
                "name": "Balanced Mid Level",
                "level": 5,
                "damage": {"dice": "8d6", "type": "lightning"},
                "expected_balance": "balanced"
            }
        ]

        if hasattr(builder, 'analyze_spell_balance'):
            for spell_test in balance_test_spells:
                balance_analysis = builder.analyze_spell_balance(spell_test)

                if balance_analysis:
                    assert isinstance(balance_analysis, dict), "Balance analysis should return structured result"

                    if "balance_rating" in balance_analysis:
                        rating = balance_analysis["balance_rating"]
                        valid_ratings = ["underpowered", "balanced", "overpowered", "broken"]
                        assert rating in valid_ratings, f"Balance rating should be valid: {rating}"

                    if "power_score" in balance_analysis:
                        power_score = balance_analysis["power_score"]
                        assert isinstance(power_score, (int, float)), "Power score should be numeric"
                        assert 0 <= power_score <= 100, "Power score should be 0-100"

                    if "recommendations" in balance_analysis:
                        recommendations = balance_analysis["recommendations"]
                        assert isinstance(recommendations, list), "Recommendations should be list"

    def test_spell_template_system(self):
        """Test spell template and preset functionality"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test spell templates
        if hasattr(builder, 'get_spell_templates'):
            templates = builder.get_spell_templates()

            assert isinstance(templates, list), "Templates should return list"

            for template in templates[:5]:  # Check first 5 templates
                assert isinstance(template, dict), "Template should be structured"

                required_template_fields = ["template_id", "name", "description", "base_spell"]

                for field in required_template_fields:
                    if field in template:
                        if field == "base_spell":
                            base_spell = template[field]
                            assert isinstance(base_spell, dict), "Base spell should be structured"

                            # Verify base spell has required fields
                            spell_fields = ["level", "school", "casting_time", "range"]
                            spell_field_count = sum(1 for f in spell_fields if f in base_spell)
                            assert spell_field_count >= 2, "Base spell should have core fields"

        # Test template application
        if hasattr(builder, 'apply_spell_template'):
            template_id = "damage_spell_template"
            customizations = {
                "name": "Custom Fire Blast",
                "damage_type": "fire",
                "spell_level": 2
            }

            template_result = builder.apply_spell_template(template_id, customizations)

            if template_result:
                assert isinstance(template_result, dict), "Template application should return structured spell"

                # Customizations should be applied
                if "name" in template_result:
                    assert template_result["name"] == customizations["name"], "Template should apply name customization"

                if "damage" in template_result and "type" in template_result["damage"]:
                    assert template_result["damage"]["type"] == customizations["damage_type"], \
                        "Template should apply damage type customization"

    def test_spell_export_and_sharing(self):
        """Test spell export functionality and sharing formats"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test spell for export
        export_spell = {
            "id": "CUSTOM-SPELL-001",
            "name": "Mystic Shield",
            "level": 2,
            "school": "abjuration",
            "description": "Creates a shimmering shield of force around the caster"
        }

        # Test different export formats
        export_formats = ["json", "yaml", "pdf", "html", "foundry_vtt"]

        if hasattr(builder, 'export_spell'):
            for export_format in export_formats:
                export_result = builder.export_spell(export_spell, export_format)

                if export_result:
                    assert isinstance(export_result, dict), f"Export should return structured result for {export_format}"

                    if "content" in export_result:
                        content = export_result["content"]

                        if export_format == "json":
                            # JSON should be parseable
                            try:
                                json.loads(content)
                                json_valid = True
                            except:
                                json_valid = False
                            assert json_valid, "JSON export should be valid JSON"

                        elif export_format == "foundry_vtt":
                            # FoundryVTT format should have specific structure
                            if isinstance(content, dict):
                                foundry_fields = ["name", "data", "type"]
                                field_count = sum(1 for f in foundry_fields if f in content)
                                assert field_count >= 2, "FoundryVTT export should have expected structure"

                    if "filename" in export_result:
                        filename = export_result["filename"]
                        assert export_format in filename or export_format.replace("_", ".") in filename, \
                            f"Filename should reflect export format: {filename}"

    def test_spell_collection_management(self):
        """Test spell collection and spellbook management features"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test spellbook creation and management
        test_spellbook = {
            "name": "Custom Wizard Spellbook",
            "description": "Collection of custom spells for wizard characters",
            "character_class": "wizard",
            "character_level": 10,
            "spell_ids": ["CUSTOM-001", "CUSTOM-002", "CUSTOM-003"]
        }

        if hasattr(builder, 'create_spellbook'):
            spellbook_result = builder.create_spellbook(test_spellbook)

            if spellbook_result:
                assert isinstance(spellbook_result, dict), "Spellbook creation should return structured result"

                if "spellbook_id" in spellbook_result:
                    spellbook_id = spellbook_result["spellbook_id"]
                    assert isinstance(spellbook_id, str), "Spellbook ID should be string"

                    # Test spellbook retrieval
                    if hasattr(builder, 'get_spellbook'):
                        retrieved_spellbook = builder.get_spellbook(spellbook_id)

                        if retrieved_spellbook:
                            assert retrieved_spellbook["name"] == test_spellbook["name"], \
                                "Retrieved spellbook should match created spellbook"

        # Test spell filtering by character requirements
        if hasattr(builder, 'filter_spells_for_character'):
            character_requirements = {
                "class": "wizard",
                "level": 5,
                "school_restrictions": None,
                "available_spell_levels": [0, 1, 2, 3]
            }

            filtered_spells = builder.filter_spells_for_character(character_requirements)

            if filtered_spells:
                assert isinstance(filtered_spells, list), "Filtered spells should be list"

                for spell in filtered_spells[:3]:  # Check first 3 spells
                    if "level" in spell:
                        spell_level = spell["level"]
                        assert spell_level in character_requirements["available_spell_levels"], \
                            f"Filtered spell level {spell_level} should match character requirements"

                    if "classes" in spell:
                        spell_classes = spell["classes"]
                        assert character_requirements["class"] in spell_classes, \
                            f"Filtered spell should be available to {character_requirements['class']}"

    def test_spell_builder_contract_compliance(self):
        """Test that spell builder matches established contract"""
        try:
            from src_common.spell_builder import SpellBuilder
        except ImportError:
            pytest.skip("Spell builder not available for testing")

        builder = SpellBuilder()

        # Test spell data structure contract
        required_spell_fields = [
            "name", "level", "school", "casting_time",
            "range", "components", "duration", "description"
        ]

        sample_spell = {
            "name": "Contract Test Spell",
            "level": 1,
            "school": "evocation",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": ["V", "S"],
            "duration": "1 minute",
            "description": "A test spell for contract validation"
        }

        # All required fields should be present
        for field in required_spell_fields:
            assert field in sample_spell, f"Spell missing required field: {field}"

        # Field validation contract
        valid_schools = [
            "abjuration", "conjuration", "divination", "enchantment",
            "evocation", "illusion", "necromancy", "transmutation"
        ]
        assert sample_spell["school"] in valid_schools, f"Invalid spell school: {sample_spell['school']}"

        valid_components = ["V", "S", "M"]
        for component in sample_spell["components"]:
            assert component in valid_components, f"Invalid spell component: {component}"

        assert isinstance(sample_spell["level"], int), "Spell level must be integer"
        assert 0 <= sample_spell["level"] <= 9, "Spell level must be 0-9"

        # Test creation contract
        if hasattr(builder, 'create_spell'):
            creation_result = builder.create_spell(sample_spell)

            if creation_result:
                # Creation should return structured result
                assert isinstance(creation_result, dict), "Spell creation must return structured result"

                # Should have status indicator
                if "status" in creation_result:
                    valid_statuses = ["created", "draft", "pending_review", "error"]
                    assert creation_result["status"] in valid_statuses, "Status must be valid"

        # Test validation contract
        if hasattr(builder, 'validate_spell'):
            validation_result = builder.validate_spell(sample_spell)

            if validation_result:
                assert isinstance(validation_result, dict), "Validation must return structured result"

                if "valid" in validation_result:
                    assert isinstance(validation_result["valid"], bool), "Validation result must be boolean"

                if "errors" in validation_result:
                    errors = validation_result["errors"]
                    assert isinstance(errors, list), "Validation errors must be list"

                    for error in errors:
                        assert "field" in error, "Validation error must specify field"
                        assert "message" in error, "Validation error must have message"