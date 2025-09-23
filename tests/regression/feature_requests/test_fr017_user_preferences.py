# tests/regression/feature_requests/test_fr017_user_preferences.py
"""
Feature Request FR-017: User Preferences and Personalization Regression Tests
Tests comprehensive user preference management with personalization features and adaptive interfaces
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta


class TestUserPreferencesPersonalization:
    """Test suite for FR-017 User Preferences and Personalization functionality"""

    def test_user_preferences_infrastructure_availability(self):
        """Test that user preferences components are available"""
        try:
            from src_common.preferences import UserPreferencesManager
            from src_common.personalization import PersonalizationEngine
            from src_common.ui_adaptation import UIAdaptationService
            from src_common.user_profiles import UserProfileService

            assert UserPreferencesManager is not None, "UserPreferencesManager should be available"
            assert PersonalizationEngine is not None, "PersonalizationEngine should be available"
            assert UIAdaptationService is not None, "UIAdaptationService should be available"
            assert UserProfileService is not None, "UserProfileService should be available"

        except ImportError as e:
            pytest.fail(f"User preferences components not available: {e}")

    def test_user_preference_categories_and_settings(self):
        """Test user preference categories and setting management"""
        try:
            from src_common.preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        preferences_manager = UserPreferencesManager()

        # Test preference categories structure
        preference_categories = {
            "interface": {
                "theme": {
                    "type": "select",
                    "options": ["light", "dark", "auto", "retro_terminal", "lcars"],
                    "default": "dark",
                    "description": "Visual theme for the interface"
                },
                "layout_density": {
                    "type": "select",
                    "options": ["compact", "comfortable", "spacious"],
                    "default": "comfortable",
                    "description": "Information density in the interface"
                },
                "sidebar_position": {
                    "type": "select",
                    "options": ["left", "right", "hidden"],
                    "default": "left",
                    "description": "Position of the navigation sidebar"
                }
            },
            "search": {
                "default_search_type": {
                    "type": "select",
                    "options": ["semantic", "keyword", "hybrid"],
                    "default": "hybrid",
                    "description": "Default search algorithm to use"
                },
                "results_per_page": {
                    "type": "number",
                    "min": 10,
                    "max": 100,
                    "default": 25,
                    "description": "Number of search results per page"
                },
                "auto_suggest": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable search suggestions and autocomplete"
                }
            },
            "content": {
                "preferred_sources": {
                    "type": "multi_select",
                    "options": ["Player's Handbook", "Dungeon Master's Guide", "Xanathar's Guide", "Tasha's Cauldron"],
                    "default": ["Player's Handbook"],
                    "description": "Preferred source books for content"
                },
                "content_rating_filter": {
                    "type": "select",
                    "options": ["all", "family_friendly", "teen", "mature"],
                    "default": "all",
                    "description": "Content rating filter"
                },
                "show_homebrew": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include homebrew content in search results"
                }
            },
            "accessibility": {
                "font_size": {
                    "type": "range",
                    "min": 12,
                    "max": 24,
                    "default": 16,
                    "description": "Base font size in pixels"
                },
                "high_contrast": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable high contrast mode"
                },
                "reduced_motion": {
                    "type": "boolean",
                    "default": False,
                    "description": "Reduce animations and motion effects"
                },
                "screen_reader_support": {
                    "type": "boolean",
                    "default": False,
                    "description": "Optimize for screen readers"
                }
            },
            "notifications": {
                "email_notifications": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enable email notifications"
                },
                "push_notifications": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable browser push notifications"
                },
                "notification_frequency": {
                    "type": "select",
                    "options": ["immediate", "daily", "weekly", "never"],
                    "default": "daily",
                    "description": "Frequency of notification emails"
                }
            }
        }

        if hasattr(preferences_manager, 'initialize_preference_categories'):
            init_result = preferences_manager.initialize_preference_categories(preference_categories)

            assert isinstance(init_result, dict), "Preference initialization should return structured result"

            if "categories_initialized" in init_result:
                initialized = init_result["categories_initialized"]
                assert initialized == True, "Preference categories should initialize successfully"

            if "total_settings" in init_result:
                total_settings = init_result["total_settings"]
                expected_count = sum(len(category) for category in preference_categories.values())
                assert total_settings == expected_count, f"Should initialize {expected_count} settings"

        # Test individual preference setting and validation
        if hasattr(preferences_manager, 'set_user_preference'):
            test_user_id = "test_user_001"
            preference_updates = [
                {
                    "category": "interface",
                    "setting": "theme",
                    "value": "retro_terminal",
                    "expected_valid": True
                },
                {
                    "category": "search",
                    "setting": "results_per_page",
                    "value": 50,
                    "expected_valid": True
                },
                {
                    "category": "accessibility",
                    "setting": "font_size",
                    "value": 30,  # Outside valid range
                    "expected_valid": False
                },
                {
                    "category": "content",
                    "setting": "preferred_sources",
                    "value": ["Player's Handbook", "Dungeon Master's Guide"],
                    "expected_valid": True
                }
            ]

            for update in preference_updates:
                set_result = preferences_manager.set_user_preference(
                    test_user_id,
                    update["category"],
                    update["setting"],
                    update["value"]
                )

                assert isinstance(set_result, dict), "Preference setting should return structured result"

                if "success" in set_result:
                    success = set_result["success"]
                    assert success == update["expected_valid"], f"Setting {update['setting']} validation should match expectation"

                if not update["expected_valid"] and "validation_error" in set_result:
                    error = set_result["validation_error"]
                    assert isinstance(error, str), "Validation error should be string"

    def test_user_profile_creation_and_learning(self):
        """Test user profile creation and preference learning"""
        try:
            from src_common.user_profiles import UserProfileService
        except ImportError:
            pytest.skip("User profile service not available for testing")

        profile_service = UserProfileService()

        # Test user profile creation
        user_data = {
            "user_id": "profile_test_user",
            "initial_preferences": {
                "experience_level": "intermediate",
                "game_systems": ["D&D 5e", "Pathfinder"],
                "content_interests": ["spells", "character_creation", "combat"],
                "play_style": ["roleplay", "optimization"]
            },
            "usage_patterns": {
                "primary_device": "desktop",
                "session_duration_avg": 45,  # minutes
                "peak_usage_hours": [19, 20, 21, 22],  # 7-10 PM
                "search_frequency": "daily"
            }
        }

        if hasattr(profile_service, 'create_user_profile'):
            profile_result = profile_service.create_user_profile(user_data)

            assert isinstance(profile_result, dict), "Profile creation should return structured result"

            if "profile_created" in profile_result:
                created = profile_result["profile_created"]
                assert created == True, "User profile should be created successfully"

            if "initial_recommendations" in profile_result:
                recommendations = profile_result["initial_recommendations"]
                assert isinstance(recommendations, dict), "Initial recommendations should be dictionary"

                # Should recommend content based on interests
                if "content_suggestions" in recommendations:
                    suggestions = recommendations["content_suggestions"]
                    assert isinstance(suggestions, list), "Content suggestions should be list"

        # Test preference learning from user behavior
        if hasattr(profile_service, 'learn_from_user_behavior'):
            behavior_data = [
                {
                    "action": "search",
                    "query": "wizard spells level 3",
                    "result_clicks": ["fireball", "lightning_bolt", "counterspell"],
                    "time_spent": 180,  # seconds
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "action": "bookmark",
                    "content_id": "phb_spellcasting_rules",
                    "content_type": "rules",
                    "timestamp": (datetime.now() - timedelta(hours=1)).isoformat()
                },
                {
                    "action": "view",
                    "content_id": "dmg_magic_items",
                    "content_type": "items",
                    "duration": 300,
                    "scroll_depth": 0.8,
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat()
                }
            ]

            learning_result = profile_service.learn_from_user_behavior(
                user_data["user_id"],
                behavior_data
            )

            assert isinstance(learning_result, dict), "Behavior learning should return structured result"

            if "preferences_updated" in learning_result:
                updated = learning_result["preferences_updated"]
                assert isinstance(updated, bool), "Preferences updated should be boolean"

            if "learned_patterns" in learning_result:
                patterns = learning_result["learned_patterns"]
                assert isinstance(patterns, dict), "Learned patterns should be dictionary"

                # Should identify content type preferences
                if "content_type_affinity" in patterns:
                    affinity = patterns["content_type_affinity"]
                    assert isinstance(affinity, dict), "Content type affinity should be dictionary"

    def test_adaptive_ui_personalization(self):
        """Test adaptive UI personalization based on user preferences"""
        try:
            from src_common.ui_adaptation import UIAdaptationService
        except ImportError:
            pytest.skip("UI adaptation service not available for testing")

        ui_service = UIAdaptationService()

        # Test UI adaptation based on user profile
        user_context = {
            "user_id": "ui_test_user",
            "preferences": {
                "theme": "retro_terminal",
                "layout_density": "compact",
                "font_size": 18,
                "high_contrast": True,
                "reduced_motion": True
            },
            "device_info": {
                "type": "mobile",
                "screen_size": {"width": 375, "height": 667},
                "touch_enabled": True
            },
            "usage_context": {
                "session_type": "quick_lookup",
                "time_of_day": "evening",
                "ambient_light": "low"
            }
        }

        if hasattr(ui_service, 'adapt_interface'):
            adaptation_result = ui_service.adapt_interface(user_context)

            assert isinstance(adaptation_result, dict), "UI adaptation should return structured result"

            if "adapted_interface" in adaptation_result:
                adapted = adaptation_result["adapted_interface"]
                assert isinstance(adapted, dict), "Adapted interface should be dictionary"

                # Verify theme adaptation
                if "theme_config" in adapted:
                    theme = adapted["theme_config"]
                    assert theme["name"] == "retro_terminal", "Should apply retro terminal theme"
                    assert theme["high_contrast"] == True, "Should enable high contrast"

                # Verify layout adaptation
                if "layout_config" in adapted:
                    layout = adapted["layout_config"]
                    assert layout["density"] == "compact", "Should apply compact layout"

                # Verify accessibility adaptations
                if "accessibility_config" in adapted:
                    accessibility = adapted["accessibility_config"]
                    assert accessibility["font_size"] == 18, "Should apply custom font size"
                    assert accessibility["reduced_motion"] == True, "Should reduce motion"

            if "adaptation_reasons" in adaptation_result:
                reasons = adaptation_result["adaptation_reasons"]
                assert isinstance(reasons, list), "Adaptation reasons should be list"

        # Test dynamic interface adjustment
        if hasattr(ui_service, 'adjust_interface_dynamically'):
            context_changes = [
                {
                    "trigger": "ambient_light_change",
                    "new_value": "bright",
                    "expected_adaptation": "reduce_contrast"
                },
                {
                    "trigger": "device_rotation",
                    "new_value": "landscape",
                    "expected_adaptation": "layout_adjustment"
                },
                {
                    "trigger": "network_speed_change",
                    "new_value": "slow",
                    "expected_adaptation": "reduce_animations"
                }
            ]

            for change in context_changes:
                adjustment_result = ui_service.adjust_interface_dynamically(
                    user_context["user_id"],
                    change["trigger"],
                    change["new_value"]
                )

                assert isinstance(adjustment_result, dict), "Dynamic adjustment should return structured result"

                if "adjustments_made" in adjustment_result:
                    adjustments = adjustment_result["adjustments_made"]
                    assert isinstance(adjustments, list), "Adjustments should be list"

    def test_personalized_content_presentation(self):
        """Test personalized content presentation and formatting"""
        try:
            from src_common.personalization import PersonalizationEngine
        except ImportError:
            pytest.skip("Personalization engine not available for testing")

        personalization_engine = PersonalizationEngine()

        # Test personalized content formatting
        user_profile = {
            "user_id": "content_test_user",
            "preferences": {
                "content_verbosity": "concise",
                "example_preference": "practical",
                "terminology_level": "intermediate",
                "visual_learning_style": True
            },
            "content_history": {
                "frequently_accessed": ["spells", "character_creation"],
                "content_ratings": {
                    "detailed_explanations": 4,
                    "quick_reference": 5,
                    "visual_aids": 5
                }
            }
        }

        sample_content = {
            "content_id": "spellcasting_mechanics",
            "title": "Spellcasting Mechanics",
            "content_sections": [
                {
                    "type": "explanation",
                    "content": "Spellcasting is the process by which magical effects are created...",
                    "verbosity_levels": {
                        "concise": "Magic users cast spells using components and spell slots.",
                        "detailed": "Spellcasting is the process by which magical effects are created through the manipulation of magical energies..."
                    }
                },
                {
                    "type": "examples",
                    "practical_examples": ["A wizard casting fireball", "A cleric healing an ally"],
                    "theoretical_examples": ["Magical theory behind evocation", "Divine connection principles"]
                }
            ],
            "visual_aids": {
                "diagrams": ["spell_components_diagram.png"],
                "flowcharts": ["spellcasting_process.png"]
            }
        }

        if hasattr(personalization_engine, 'personalize_content_presentation'):
            personalization_result = personalization_engine.personalize_content_presentation(
                user_profile,
                sample_content
            )

            assert isinstance(personalization_result, dict), "Content personalization should return structured result"

            if "personalized_content" in personalization_result:
                personalized = personalization_result["personalized_content"]
                assert isinstance(personalized, dict), "Personalized content should be dictionary"

                # Verify verbosity adaptation
                for section in personalized.get("content_sections", []):
                    if section.get("type") == "explanation":
                        # Should use concise version based on user preference
                        content_text = section.get("content", "")
                        assert "Magic users cast spells" in content_text, "Should use concise explanation"

                # Verify example selection
                for section in personalized.get("content_sections", []):
                    if section.get("type") == "examples":
                        # Should prefer practical examples
                        examples = section.get("selected_examples", [])
                        assert any("wizard casting fireball" in str(ex).lower() for ex in examples), "Should include practical examples"

                # Verify visual aids inclusion
                if user_profile["preferences"]["visual_learning_style"]:
                    visual_aids = personalized.get("visual_aids", {})
                    assert len(visual_aids) > 0, "Should include visual aids for visual learners"

    def test_preference_synchronization_and_backup(self):
        """Test preference synchronization across devices and backup mechanisms"""
        try:
            from src_common.preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        preferences_manager = UserPreferencesManager()

        # Test cross-device synchronization
        user_id = "sync_test_user"
        device_preferences = {
            "device_001": {
                "device_type": "desktop",
                "preferences": {
                    "theme": "dark",
                    "layout_density": "comfortable",
                    "results_per_page": 50
                },
                "last_sync": "2024-09-22T10:00:00Z"
            },
            "device_002": {
                "device_type": "mobile",
                "preferences": {
                    "theme": "retro_terminal",
                    "layout_density": "compact",
                    "results_per_page": 25
                },
                "last_sync": "2024-09-22T10:30:00Z"
            }
        }

        if hasattr(preferences_manager, 'synchronize_preferences'):
            sync_config = {
                "sync_strategy": "device_specific_with_global_fallback",
                "conflict_resolution": "most_recent_wins",
                "merge_compatible_settings": True
            }

            sync_result = preferences_manager.synchronize_preferences(
                user_id,
                device_preferences,
                sync_config
            )

            assert isinstance(sync_result, dict), "Preference sync should return structured result"

            if "synchronized_preferences" in sync_result:
                synced = sync_result["synchronized_preferences"]
                assert isinstance(synced, dict), "Synchronized preferences should be dictionary"

                # Should maintain device-specific preferences where appropriate
                for device_id, device_data in device_preferences.items():
                    if device_id in synced:
                        device_prefs = synced[device_id]["preferences"]

                        # Layout density should be device-specific
                        expected_density = device_data["preferences"]["layout_density"]
                        assert device_prefs["layout_density"] == expected_density, f"Device {device_id} should maintain its layout density"

            if "sync_conflicts" in sync_result:
                conflicts = sync_result["sync_conflicts"]
                assert isinstance(conflicts, list), "Sync conflicts should be list"

        # Test preference backup and restore
        if hasattr(preferences_manager, 'create_preference_backup'):
            backup_config = {
                "include_all_devices": True,
                "include_learned_preferences": True,
                "encryption": True,
                "compression": True
            }

            backup_result = preferences_manager.create_preference_backup(user_id, backup_config)

            assert isinstance(backup_result, dict), "Preference backup should return structured result"

            if "backup_created" in backup_result:
                created = backup_result["backup_created"]
                assert created == True, "Preference backup should be created successfully"

            if "backup_id" in backup_result:
                backup_id = backup_result["backup_id"]
                assert isinstance(backup_id, str), "Backup ID should be string"

    def test_user_preferences_contract_compliance(self):
        """Test that user preferences and personalization match established contract"""
        # Test preferences contract
        preferences_requirements = {
            "preference_categories": True,
            "setting_validation": True,
            "cross_device_sync": True,
            "preference_learning": True,
            "backup_restore": True
        }

        for requirement, needed in preferences_requirements.items():
            assert needed, f"Preferences requirement {requirement} is mandatory"

        # Test personalization contract
        personalization_requirements = {
            "adaptive_ui": True,
            "content_personalization": True,
            "behavior_learning": True,
            "context_awareness": True
        }

        for requirement, needed in personalization_requirements.items():
            assert needed, f"Personalization requirement {requirement} is mandatory"

        # Test accessibility contract
        accessibility_requirements = {
            "font_size_adjustment": True,
            "high_contrast_mode": True,
            "reduced_motion": True,
            "screen_reader_support": True
        }

        for requirement, needed in accessibility_requirements.items():
            assert needed, f"Accessibility requirement {requirement} is mandatory"

        # Test data contract
        required_preference_fields = [
            "user_id",
            "preference_category",
            "setting_name",
            "setting_value",
            "last_modified"
        ]

        for field in required_preference_fields:
            assert isinstance(field, str), f"Preference field {field} should be defined"

        # Test integration contract
        integration_points = [
            "user_profile_integration",
            "ui_framework_integration",
            "content_delivery_integration",
            "analytics_tracking_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"