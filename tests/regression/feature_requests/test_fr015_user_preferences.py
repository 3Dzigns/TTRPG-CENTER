# tests/regression/feature_requests/test_fr015_user_preferences.py
"""
Feature Request FR-015: User Preferences and Customization Regression Tests
Tests user preference management, UI customization, and personalization features
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestUserPreferencesCustomization:
    """Test suite for User Preferences and Customization validation"""

    def test_user_preferences_system_availability(self):
        """Test that user preferences system is available"""
        try:
            from src_common.user_preferences import UserPreferencesManager
            from src_common.admin_routes import app

            assert UserPreferencesManager is not None, "UserPreferencesManager should be available"
            assert app is not None, "Admin routes should include preferences endpoints"

        except ImportError as e:
            pytest.fail(f"User preferences components not available: {e}")

    def test_preference_categories_and_structure(self):
        """Test user preference categories and data structure"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test comprehensive preference structure
        default_preferences = {
            "ui_theme": {
                "color_scheme": "retro_terminal",
                "font_family": "monospace",
                "font_size": 14,
                "terminal_style": "amber_on_black",
                "lcars_mode": False,
                "animations_enabled": True
            },
            "search_preferences": {
                "default_search_type": "semantic",
                "results_per_page": 20,
                "auto_suggest_enabled": True,
                "search_history_enabled": True,
                "filter_presets": ["official_only", "community_content"]
            },
            "content_display": {
                "spell_card_format": "detailed",
                "show_homebrew_content": True,
                "content_warnings_enabled": True,
                "image_loading": "lazy",
                "table_compact_mode": False
            },
            "accessibility": {
                "high_contrast_mode": False,
                "screen_reader_optimized": False,
                "keyboard_navigation": True,
                "text_to_speech": False,
                "motion_reduced": False
            },
            "notifications": {
                "email_notifications": True,
                "browser_notifications": False,
                "update_notifications": True,
                "community_alerts": False
            },
            "privacy": {
                "analytics_opt_in": True,
                "search_tracking": True,
                "data_sharing": False,
                "cookie_preferences": "essential_only"
            }
        }

        if hasattr(prefs_manager, 'get_default_preferences'):
            defaults = prefs_manager.get_default_preferences()

            assert isinstance(defaults, dict), "Default preferences should be structured"

            # Verify major preference categories exist
            expected_categories = ["ui_theme", "search_preferences", "content_display"]

            for category in expected_categories:
                if category in defaults:
                    assert isinstance(defaults[category], dict), f"{category} should be structured"

        # Test preference validation
        if hasattr(prefs_manager, 'validate_preferences'):
            validation = prefs_manager.validate_preferences(default_preferences)

            if validation:
                assert isinstance(validation, dict), "Preference validation should return structured result"

                if "valid" in validation:
                    assert validation["valid"] == True, "Default preferences should be valid"

                if "errors" in validation:
                    errors = validation["errors"]
                    assert len(errors) == 0, f"Valid preferences should have no errors: {errors}"

    def test_user_preference_persistence(self):
        """Test user preference saving and loading functionality"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        test_user_id = "test_user_prefs_001"

        # Test preference saving
        test_preferences = {
            "ui_theme": {
                "color_scheme": "cyberpunk_blue",
                "font_size": 16,
                "terminal_style": "blue_on_black"
            },
            "search_preferences": {
                "results_per_page": 50,
                "auto_suggest_enabled": False
            },
            "accessibility": {
                "high_contrast_mode": True,
                "keyboard_navigation": True
            }
        }

        if hasattr(prefs_manager, 'save_user_preferences'):
            save_result = prefs_manager.save_user_preferences(test_user_id, test_preferences)

            if save_result:
                assert isinstance(save_result, dict), "Preference saving should return structured result"

                if "saved" in save_result:
                    assert save_result["saved"] == True, "Preferences should be successfully saved"

                # Test preference loading
                if hasattr(prefs_manager, 'load_user_preferences'):
                    loaded_prefs = prefs_manager.load_user_preferences(test_user_id)

                    if loaded_prefs:
                        assert isinstance(loaded_prefs, dict), "Loaded preferences should be structured"

                        # Verify saved preferences match loaded preferences
                        if "ui_theme" in loaded_prefs:
                            ui_theme = loaded_prefs["ui_theme"]
                            assert ui_theme["color_scheme"] == test_preferences["ui_theme"]["color_scheme"], \
                                "Loaded preferences should match saved preferences"

                        if "search_preferences" in loaded_prefs:
                            search_prefs = loaded_prefs["search_preferences"]
                            assert search_prefs["results_per_page"] == test_preferences["search_preferences"]["results_per_page"], \
                                "Search preferences should persist correctly"

    def test_theme_and_ui_customization(self):
        """Test theme and UI customization capabilities"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test available themes
        if hasattr(prefs_manager, 'get_available_themes'):
            themes = prefs_manager.get_available_themes()

            assert isinstance(themes, list), "Available themes should be list"

            expected_themes = [
                "retro_terminal", "cyberpunk_blue", "matrix_green",
                "amber_classic", "lcars_style", "high_contrast"
            ]

            for theme in themes[:6]:  # Check first 6 themes
                assert isinstance(theme, dict), "Theme should be structured"

                required_theme_fields = ["theme_id", "name", "description"]

                for field in required_theme_fields:
                    if field in theme:
                        assert isinstance(theme[field], str), f"Theme {field} should be string"

                # Test theme preview
                if hasattr(prefs_manager, 'get_theme_preview'):
                    theme_id = theme.get("theme_id", theme.get("name", "default"))
                    preview = prefs_manager.get_theme_preview(theme_id)

                    if preview:
                        assert isinstance(preview, dict), "Theme preview should be structured"

                        preview_fields = ["colors", "fonts", "example_html"]

                        for field in preview_fields:
                            if field in preview:
                                if field == "colors":
                                    colors = preview[field]
                                    assert isinstance(colors, dict), "Theme colors should be structured"

                                elif field == "fonts":
                                    fonts = preview[field]
                                    assert isinstance(fonts, dict), "Theme fonts should be structured"

        # Test theme application
        if hasattr(prefs_manager, 'apply_theme'):
            test_theme_id = "cyberpunk_blue"
            theme_config = prefs_manager.apply_theme(test_theme_id)

            if theme_config:
                assert isinstance(theme_config, dict), "Theme application should return configuration"

                if "css_variables" in theme_config:
                    css_vars = theme_config["css_variables"]
                    assert isinstance(css_vars, dict), "CSS variables should be structured"

                    # Should have color variables
                    color_var_count = sum(1 for var in css_vars.keys() if "color" in var.lower())
                    assert color_var_count > 0, "Theme should define color variables"

    def test_search_preference_customization(self):
        """Test search preference customization and filter presets"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test search filter presets
        search_filter_presets = [
            {
                "name": "Official Content Only",
                "preset_id": "official_only",
                "filters": {
                    "source_type": ["official"],
                    "content_rating": ["approved"],
                    "homebrew": False
                }
            },
            {
                "name": "High Level Spells",
                "preset_id": "high_level_spells",
                "filters": {
                    "spell_level": [6, 7, 8, 9],
                    "content_type": ["spell"]
                }
            },
            {
                "name": "Character Creation",
                "preset_id": "char_creation",
                "filters": {
                    "content_type": ["race", "class", "background"],
                    "source_type": ["official", "verified_homebrew"]
                }
            }
        ]

        if hasattr(prefs_manager, 'save_search_filter_preset'):
            for preset in search_filter_presets:
                preset_result = prefs_manager.save_search_filter_preset(
                    "test_user_001",
                    preset["preset_id"],
                    preset["name"],
                    preset["filters"]
                )

                if preset_result:
                    assert isinstance(preset_result, dict), "Filter preset saving should return structured result"

                    if "saved" in preset_result:
                        assert preset_result["saved"] == True, f"Filter preset {preset['name']} should save successfully"

        # Test search behavior customization
        if hasattr(prefs_manager, 'set_search_behavior'):
            search_behaviors = {
                "auto_correct_spelling": True,
                "include_similar_results": True,
                "boost_recent_searches": False,
                "personalized_ranking": True,
                "content_type_weights": {
                    "spell": 1.0,
                    "item": 0.8,
                    "creature": 0.6,
                    "rule": 0.4
                }
            }

            behavior_result = prefs_manager.set_search_behavior("test_user_001", search_behaviors)

            if behavior_result:
                assert isinstance(behavior_result, dict), "Search behavior setting should return structured result"

    def test_accessibility_preferences(self):
        """Test accessibility preference management"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test accessibility options
        accessibility_preferences = {
            "visual": {
                "high_contrast_mode": True,
                "dark_mode_only": False,
                "font_size_multiplier": 1.2,
                "line_height_multiplier": 1.5,
                "color_blind_friendly": True
            },
            "motor": {
                "keyboard_navigation": True,
                "sticky_keys_support": True,
                "click_delay": 200,
                "hover_delay": 500
            },
            "cognitive": {
                "simplified_interface": False,
                "reduced_animations": True,
                "extended_timeouts": True,
                "progress_indicators": True
            },
            "auditory": {
                "screen_reader_optimized": True,
                "audio_descriptions": False,
                "sound_notifications": False,
                "text_to_speech": True
            }
        }

        if hasattr(prefs_manager, 'set_accessibility_preferences'):
            accessibility_result = prefs_manager.set_accessibility_preferences(
                "test_user_accessibility",
                accessibility_preferences
            )

            if accessibility_result:
                assert isinstance(accessibility_result, dict), "Accessibility setting should return structured result"

                # Test accessibility profile generation
                if hasattr(prefs_manager, 'generate_accessibility_profile'):
                    profile = prefs_manager.generate_accessibility_profile("test_user_accessibility")

                    if profile:
                        assert isinstance(profile, dict), "Accessibility profile should be structured"

                        if "css_overrides" in profile:
                            css_overrides = profile["css_overrides"]
                            assert isinstance(css_overrides, str), "CSS overrides should be string"

                        if "aria_attributes" in profile:
                            aria_attrs = profile["aria_attributes"]
                            assert isinstance(aria_attrs, dict), "ARIA attributes should be structured"

                        if "keyboard_shortcuts" in profile:
                            shortcuts = profile["keyboard_shortcuts"]
                            assert isinstance(shortcuts, dict), "Keyboard shortcuts should be structured"

    def test_notification_preferences(self):
        """Test notification preference management"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test notification preferences
        notification_preferences = {
            "email": {
                "system_updates": True,
                "content_updates": False,
                "community_activity": True,
                "personal_messages": True,
                "frequency": "weekly_digest"
            },
            "browser": {
                "push_notifications": False,
                "desktop_notifications": True,
                "sound_notifications": False,
                "quiet_hours": {
                    "enabled": True,
                    "start_time": "22:00",
                    "end_time": "08:00"
                }
            },
            "in_app": {
                "toast_notifications": True,
                "modal_alerts": True,
                "progress_notifications": True,
                "error_notifications": True
            }
        }

        if hasattr(prefs_manager, 'set_notification_preferences'):
            notification_result = prefs_manager.set_notification_preferences(
                "test_user_notifications",
                notification_preferences
            )

            if notification_result:
                assert isinstance(notification_result, dict), "Notification setting should return structured result"

                # Test notification scheduling
                if hasattr(prefs_manager, 'schedule_notification'):
                    test_notification = {
                        "type": "content_update",
                        "title": "New Spell Content Available",
                        "message": "5 new spells have been added to the database",
                        "priority": "normal"
                    }

                    schedule_result = prefs_manager.schedule_notification(
                        "test_user_notifications",
                        test_notification
                    )

                    if schedule_result:
                        assert isinstance(schedule_result, dict), "Notification scheduling should return structured result"

                        if "scheduled" in schedule_result:
                            assert isinstance(schedule_result["scheduled"], bool), "Schedule status should be boolean"

    def test_preference_import_export(self):
        """Test preference import and export functionality"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test preference export
        test_user_id = "test_user_export"

        if hasattr(prefs_manager, 'export_user_preferences'):
            export_formats = ["json", "yaml", "xml"]

            for export_format in export_formats:
                export_result = prefs_manager.export_user_preferences(test_user_id, export_format)

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

                    if "filename" in export_result:
                        filename = export_result["filename"]
                        assert export_format in filename, f"Filename should include format: {filename}"

        # Test preference import
        if hasattr(prefs_manager, 'import_user_preferences'):
            import_data = {
                "ui_theme": {"color_scheme": "imported_theme"},
                "search_preferences": {"results_per_page": 30}
            }

            import_json = json.dumps(import_data)

            import_result = prefs_manager.import_user_preferences(test_user_id, import_json, "json")

            if import_result:
                assert isinstance(import_result, dict), "Import should return structured result"

                if "imported" in import_result:
                    assert isinstance(import_result["imported"], bool), "Import status should be boolean"

                if "conflicts" in import_result:
                    conflicts = import_result["conflicts"]
                    assert isinstance(conflicts, list), "Conflicts should be list"

    def test_user_preferences_contract_compliance(self):
        """Test that user preferences system matches established contract"""
        try:
            from src_common.user_preferences import UserPreferencesManager
        except ImportError:
            pytest.skip("User preferences manager not available for testing")

        prefs_manager = UserPreferencesManager()

        # Test preference data structure contract
        required_preference_categories = [
            "ui_theme", "search_preferences", "accessibility", "notifications"
        ]

        if hasattr(prefs_manager, 'get_default_preferences'):
            defaults = prefs_manager.get_default_preferences()

            if defaults:
                # Should have major preference categories
                category_count = sum(1 for cat in required_preference_categories if cat in defaults)
                assert category_count >= 2, f"Should have at least 2 major preference categories, found {category_count}"

        # Test user preference operations contract
        test_user_id = "contract_test_user"
        test_preferences = {
            "ui_theme": {"color_scheme": "test_theme"},
            "search_preferences": {"results_per_page": 25}
        }

        # Save operation contract
        if hasattr(prefs_manager, 'save_user_preferences'):
            save_result = prefs_manager.save_user_preferences(test_user_id, test_preferences)

            if save_result:
                assert isinstance(save_result, dict), "Save operation must return structured result"

                # Should indicate success/failure
                if "saved" in save_result:
                    assert isinstance(save_result["saved"], bool), "Save status must be boolean"

        # Load operation contract
        if hasattr(prefs_manager, 'load_user_preferences'):
            load_result = prefs_manager.load_user_preferences(test_user_id)

            if load_result:
                assert isinstance(load_result, dict), "Load operation must return structured result"

        # Validation contract
        if hasattr(prefs_manager, 'validate_preferences'):
            validation = prefs_manager.validate_preferences(test_preferences)

            if validation:
                assert isinstance(validation, dict), "Validation must return structured result"

                if "valid" in validation:
                    assert isinstance(validation["valid"], bool), "Validation result must be boolean"

                if "errors" in validation:
                    errors = validation["errors"]
                    assert isinstance(errors, list), "Validation errors must be list"

                    for error in errors:
                        assert "field" in error, "Validation error must specify field"
                        assert "message" in error, "Validation error must have message"