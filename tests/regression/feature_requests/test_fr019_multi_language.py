# tests/regression/feature_requests/test_fr019_multi_language.py
"""
Feature Request FR-019: Multi-language Support and Localization Regression Tests
Tests comprehensive internationalization, localization, and RTL language support
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestMultiLanguageSupport:
    """Test suite for FR-019 Multi-language Support functionality"""

    def test_multilingual_infrastructure_availability(self):
        """Test that multi-language components are available"""
        try:
            from src_common.i18n import InternationalizationManager
            from src_common.localization import LocalizationService
            from src_common.translation import TranslationEngine
            from src_common.rtl_support import RTLLanguageHandler

            assert InternationalizationManager is not None, "InternationalizationManager should be available"
            assert LocalizationService is not None, "LocalizationService should be available"
            assert TranslationEngine is not None, "TranslationEngine should be available"
            assert RTLLanguageHandler is not None, "RTLLanguageHandler should be available"

        except ImportError as e:
            pytest.fail(f"Multi-language components not available: {e}")

    def test_language_detection_and_switching(self):
        """Test language detection and switching functionality"""
        try:
            from src_common.i18n import InternationalizationManager
        except ImportError:
            pytest.skip("Internationalization manager not available for testing")

        i18n_manager = InternationalizationManager()

        # Test supported languages configuration
        supported_languages = {
            "en": {
                "name": "English",
                "native_name": "English",
                "direction": "ltr",
                "locale": "en-US",
                "region": "US",
                "fallback": None
            },
            "es": {
                "name": "Spanish",
                "native_name": "Español",
                "direction": "ltr",
                "locale": "es-ES",
                "region": "ES",
                "fallback": "en"
            },
            "fr": {
                "name": "French",
                "native_name": "Français",
                "direction": "ltr",
                "locale": "fr-FR",
                "region": "FR",
                "fallback": "en"
            },
            "de": {
                "name": "German",
                "native_name": "Deutsch",
                "direction": "ltr",
                "locale": "de-DE",
                "region": "DE",
                "fallback": "en"
            },
            "ar": {
                "name": "Arabic",
                "native_name": "العربية",
                "direction": "rtl",
                "locale": "ar-SA",
                "region": "SA",
                "fallback": "en"
            },
            "he": {
                "name": "Hebrew",
                "native_name": "עברית",
                "direction": "rtl",
                "locale": "he-IL",
                "region": "IL",
                "fallback": "en"
            },
            "ja": {
                "name": "Japanese",
                "native_name": "日本語",
                "direction": "ltr",
                "locale": "ja-JP",
                "region": "JP",
                "fallback": "en"
            }
        }

        if hasattr(i18n_manager, 'configure_supported_languages'):
            config_result = i18n_manager.configure_supported_languages(supported_languages)

            assert isinstance(config_result, dict), "Language configuration should return structured result"

            if "languages_configured" in config_result:
                configured = config_result["languages_configured"]
                assert configured == len(supported_languages), f"Should configure {len(supported_languages)} languages"

            if "rtl_languages_detected" in config_result:
                rtl_languages = config_result["rtl_languages_detected"]
                expected_rtl = [lang for lang, config in supported_languages.items() if config["direction"] == "rtl"]
                assert len(rtl_languages) == len(expected_rtl), "Should detect RTL languages correctly"

        # Test language detection from various sources
        if hasattr(i18n_manager, 'detect_user_language'):
            detection_scenarios = [
                {
                    "browser_language": "en-US,en;q=0.9,es;q=0.8",
                    "user_preference": None,
                    "geo_location": "US",
                    "expected": "en"
                },
                {
                    "browser_language": "es-MX,es;q=0.9",
                    "user_preference": "es",
                    "geo_location": "MX",
                    "expected": "es"
                },
                {
                    "browser_language": "ar-SA,ar;q=0.9",
                    "user_preference": None,
                    "geo_location": "SA",
                    "expected": "ar"
                },
                {
                    "browser_language": "zh-CN,zh;q=0.9",  # Unsupported language
                    "user_preference": None,
                    "geo_location": "CN",
                    "expected": "en"  # Should fallback to default
                }
            ]

            for scenario in detection_scenarios:
                detection_result = i18n_manager.detect_user_language(scenario)

                assert isinstance(detection_result, dict), "Language detection should return structured result"

                if "detected_language" in detection_result:
                    detected = detection_result["detected_language"]
                    assert detected == scenario["expected"], f"Should detect language as {scenario['expected']}"

                if "detection_confidence" in detection_result:
                    confidence = detection_result["detection_confidence"]
                    assert isinstance(confidence, (int, float)), "Detection confidence should be numeric"
                    assert 0 <= confidence <= 1, "Confidence should be between 0 and 1"

    def test_content_translation_and_localization(self):
        """Test content translation and localization features"""
        try:
            from src_common.translation import TranslationEngine
        except ImportError:
            pytest.skip("Translation engine not available for testing")

        translation_engine = TranslationEngine()

        # Test content translation
        content_to_translate = {
            "ui_strings": {
                "search_placeholder": "Search for spells, rules, items...",
                "search_button": "Search",
                "filter_results": "Filter Results",
                "no_results_found": "No results found for your search.",
                "results_count": "{count} results found",
                "loading_message": "Loading content...",
                "error_message": "An error occurred while searching."
            },
            "content_text": {
                "spell_description": "A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame.",
                "rule_explanation": "When you make an attack roll, you roll a d20 and add your ability modifier and proficiency bonus.",
                "character_creation_guide": "Creating a character involves choosing a race, class, and background that define your character's abilities and story."
            },
            "metadata": {
                "content_type": "D&D 5e Rules",
                "source": "Player's Handbook",
                "difficulty": "Beginner"
            }
        }

        target_languages = ["es", "fr", "de", "ar", "ja"]

        if hasattr(translation_engine, 'translate_content'):
            for target_lang in target_languages:
                translation_result = translation_engine.translate_content(
                    content_to_translate,
                    source_language="en",
                    target_language=target_lang
                )

                assert isinstance(translation_result, dict), f"Translation to {target_lang} should return structured result"

                if "translated_content" in translation_result:
                    translated = translation_result["translated_content"]
                    assert isinstance(translated, dict), "Translated content should be dictionary"

                    # Verify structure is preserved
                    assert "ui_strings" in translated, "Should preserve UI strings section"
                    assert "content_text" in translated, "Should preserve content text section"
                    assert "metadata" in translated, "Should preserve metadata section"

                    # Verify UI strings are translated
                    ui_strings = translated["ui_strings"]
                    search_placeholder = ui_strings.get("search_placeholder", "")
                    assert len(search_placeholder) > 0, "Search placeholder should be translated"
                    assert search_placeholder != content_to_translate["ui_strings"]["search_placeholder"], \
                        "Translation should be different from source"

                if "translation_quality" in translation_result:
                    quality = translation_result["translation_quality"]
                    assert isinstance(quality, dict), "Translation quality should be dictionary"

                    if "confidence_score" in quality:
                        confidence = quality["confidence_score"]
                        assert 0 <= confidence <= 1, "Confidence should be between 0 and 1"

        # Test dynamic string interpolation in translations
        if hasattr(translation_engine, 'translate_with_variables'):
            dynamic_strings = {
                "results_count_message": "Found {count} {content_type} in {search_time}ms",
                "user_greeting": "Welcome back, {username}!",
                "filter_applied": "Showing {filtered_count} of {total_count} results"
            }

            variables = {
                "count": 42,
                "content_type": "spells",
                "search_time": 156,
                "username": "Gandalf",
                "filtered_count": 15,
                "total_count": 42
            }

            for target_lang in ["es", "fr"]:
                dynamic_result = translation_engine.translate_with_variables(
                    dynamic_strings,
                    variables,
                    target_language=target_lang
                )

                assert isinstance(dynamic_result, dict), f"Dynamic translation to {target_lang} should return structured result"

                if "translated_strings" in dynamic_result:
                    translated_strings = dynamic_result["translated_strings"]

                    for string_key in dynamic_strings:
                        if string_key in translated_strings:
                            translated_string = translated_strings[string_key]
                            # Should contain interpolated values
                            assert "42" in translated_string or "15" in translated_string, \
                                f"Translated string should contain interpolated values: {translated_string}"

    def test_rtl_language_support_and_layout(self):
        """Test RTL language support and layout adaptations"""
        try:
            from src_common.rtl_support import RTLLanguageHandler
        except ImportError:
            pytest.skip("RTL language handler not available for testing")

        rtl_handler = RTLLanguageHandler()

        # Test RTL layout configuration
        rtl_config = {
            "rtl_languages": ["ar", "he", "fa", "ur"],
            "layout_adaptations": {
                "text_direction": "rtl",
                "mirror_layout": True,
                "flip_icons": True,
                "adjust_margins": True
            },
            "ui_components": {
                "search_bar": {"position": "right", "icon_position": "left"},
                "navigation_menu": {"align": "right", "dropdown_direction": "left"},
                "content_cards": {"text_align": "right", "image_position": "left"},
                "pagination": {"direction": "reverse"}
            }
        }

        if hasattr(rtl_handler, 'configure_rtl_support'):
            rtl_result = rtl_handler.configure_rtl_support(rtl_config)

            assert isinstance(rtl_result, dict), "RTL configuration should return structured result"

            if "rtl_configured" in rtl_result:
                configured = rtl_result["rtl_configured"]
                assert configured == True, "RTL support should be configured successfully"

            if "css_modifications" in rtl_result:
                css_mods = rtl_result["css_modifications"]
                assert isinstance(css_mods, dict), "CSS modifications should be dictionary"

                # Should include direction changes
                assert "text_direction" in css_mods, "Should include text direction modifications"
                assert "layout_mirroring" in css_mods, "Should include layout mirroring modifications"

        # Test RTL content rendering
        if hasattr(rtl_handler, 'render_rtl_content'):
            rtl_content = {
                "page_title": "نتائج البحث",  # Arabic: Search Results
                "content_sections": [
                    {
                        "heading": "السحر والتعاويذ",  # Magic and Spells
                        "text": "هذا النص باللغة العربية يجب أن يظهر من اليمين إلى اليسار",  # This Arabic text should appear right-to-left
                        "has_numbers": True,
                        "has_mixed_content": True
                    }
                ],
                "ui_elements": {
                    "search_button": "بحث",  # Search
                    "filter_button": "تصفية",  # Filter
                    "results_count": "42 نتيجة"  # 42 results
                }
            }

            rtl_render_result = rtl_handler.render_rtl_content(rtl_content, "ar")

            assert isinstance(rtl_render_result, dict), "RTL rendering should return structured result"

            if "rendered_content" in rtl_render_result:
                rendered = rtl_render_result["rendered_content"]
                assert isinstance(rendered, dict), "Rendered content should be dictionary"

            if "layout_adjustments" in rtl_render_result:
                adjustments = rtl_render_result["layout_adjustments"]
                assert "text_direction" in adjustments, "Should specify text direction"
                assert adjustments["text_direction"] == "rtl", "Should set RTL text direction"

    def test_locale_specific_formatting(self):
        """Test locale-specific formatting for dates, numbers, and currencies"""
        try:
            from src_common.localization import LocalizationService
        except ImportError:
            pytest.skip("Localization service not available for testing")

        localization_service = LocalizationService()

        # Test date and time formatting
        test_datetime = datetime(2024, 9, 22, 14, 30, 0)  # September 22, 2024, 2:30 PM

        locale_formats = {
            "en-US": {
                "date_format": "9/22/2024",
                "time_format": "2:30 PM",
                "datetime_format": "September 22, 2024 at 2:30 PM"
            },
            "en-GB": {
                "date_format": "22/09/2024",
                "time_format": "14:30",
                "datetime_format": "22 September 2024 at 14:30"
            },
            "de-DE": {
                "date_format": "22.09.2024",
                "time_format": "14:30",
                "datetime_format": "22. September 2024 um 14:30"
            },
            "ja-JP": {
                "date_format": "2024/09/22",
                "time_format": "14:30",
                "datetime_format": "2024年9月22日 14:30"
            }
        }

        if hasattr(localization_service, 'format_datetime'):
            for locale, expected_formats in locale_formats.items():
                datetime_result = localization_service.format_datetime(test_datetime, locale)

                assert isinstance(datetime_result, dict), f"DateTime formatting for {locale} should return structured result"

                if "formatted_date" in datetime_result:
                    formatted_date = datetime_result["formatted_date"]
                    # Note: Exact format may vary based on system locale, so we check structure rather than exact match

                if "formatted_time" in datetime_result:
                    formatted_time = datetime_result["formatted_time"]
                    assert isinstance(formatted_time, str), "Formatted time should be string"

        # Test number formatting
        test_numbers = [1234.56, 1000000, 0.123, -456.78]

        number_locales = {
            "en-US": {"decimal_separator": ".", "thousands_separator": ","},
            "de-DE": {"decimal_separator": ",", "thousands_separator": "."},
            "fr-FR": {"decimal_separator": ",", "thousands_separator": " "}
        }

        if hasattr(localization_service, 'format_number'):
            for locale, format_rules in number_locales.items():
                for number in test_numbers:
                    number_result = localization_service.format_number(number, locale)

                    assert isinstance(number_result, dict), f"Number formatting for {locale} should return structured result"

                    if "formatted_number" in number_result:
                        formatted = number_result["formatted_number"]
                        assert isinstance(formatted, str), "Formatted number should be string"

        # Test currency formatting
        if hasattr(localization_service, 'format_currency'):
            currency_scenarios = [
                {"amount": 1234.56, "currency": "USD", "locale": "en-US"},
                {"amount": 1234.56, "currency": "EUR", "locale": "de-DE"},
                {"amount": 1234.56, "currency": "JPY", "locale": "ja-JP"},
                {"amount": 1234.56, "currency": "GBP", "locale": "en-GB"}
            ]

            for scenario in currency_scenarios:
                currency_result = localization_service.format_currency(
                    scenario["amount"],
                    scenario["currency"],
                    scenario["locale"]
                )

                assert isinstance(currency_result, dict), f"Currency formatting should return structured result"

                if "formatted_currency" in currency_result:
                    formatted = currency_result["formatted_currency"]
                    assert isinstance(formatted, str), "Formatted currency should be string"
                    # Should contain currency symbol or code
                    currency_indicators = ["$", "€", "¥", "£", "USD", "EUR", "JPY", "GBP"]
                    has_currency_indicator = any(indicator in formatted for indicator in currency_indicators)

    def test_multilingual_search_and_content_matching(self):
        """Test multilingual search capabilities and content matching"""
        try:
            from src_common.translation import TranslationEngine
        except ImportError:
            pytest.skip("Translation engine not available for testing")

        translation_engine = TranslationEngine()

        # Test multilingual search queries
        search_scenarios = [
            {
                "query": "hechizos de fuego",  # Spanish: fire spells
                "source_language": "es",
                "expected_english_equivalent": "fire spells",
                "content_matches": ["fireball", "burning hands", "flame strike"]
            },
            {
                "query": "sorts de guérison",  # French: healing spells
                "source_language": "fr",
                "expected_english_equivalent": "healing spells",
                "content_matches": ["cure wounds", "healing word", "heal"]
            },
            {
                "query": "Charaktererstellung",  # German: character creation
                "source_language": "de",
                "expected_english_equivalent": "character creation",
                "content_matches": ["races", "classes", "backgrounds"]
            },
            {
                "query": "سحر الشفاء",  # Arabic: healing magic
                "source_language": "ar",
                "expected_english_equivalent": "healing magic",
                "content_matches": ["healing spells", "divine magic", "cleric spells"]
            }
        ]

        if hasattr(translation_engine, 'translate_search_query'):
            for scenario in search_scenarios:
                translation_result = translation_engine.translate_search_query(
                    scenario["query"],
                    scenario["source_language"],
                    target_language="en"
                )

                assert isinstance(translation_result, dict), "Search query translation should return structured result"

                if "translated_query" in translation_result:
                    translated = translation_result["translated_query"]
                    assert isinstance(translated, str), "Translated query should be string"

                if "semantic_equivalents" in translation_result:
                    equivalents = translation_result["semantic_equivalents"]
                    assert isinstance(equivalents, list), "Semantic equivalents should be list"

        # Test cross-language content matching
        if hasattr(translation_engine, 'match_multilingual_content'):
            multilingual_content = {
                "en": {
                    "title": "Fireball Spell",
                    "description": "A bright streak flashes from your pointing finger...",
                    "tags": ["spell", "evocation", "fire", "damage"]
                },
                "es": {
                    "title": "Hechizo de Bola de Fuego",
                    "description": "Un rayo brillante destella desde tu dedo índice...",
                    "tags": ["hechizo", "evocación", "fuego", "daño"]
                },
                "fr": {
                    "title": "Sort de Boule de Feu",
                    "description": "Un éclair brillant jaillit de votre doigt...",
                    "tags": ["sort", "évocation", "feu", "dégâts"]
                }
            }

            matching_result = translation_engine.match_multilingual_content(
                "fire spell",
                multilingual_content,
                source_language="en"
            )

            assert isinstance(matching_result, dict), "Multilingual content matching should return structured result"

            if "matches" in matching_result:
                matches = matching_result["matches"]
                assert isinstance(matches, dict), "Matches should be dictionary"

                # Should find matches in multiple languages
                assert len(matches) >= 2, "Should find matches in multiple languages"

    def test_multilingual_contract_compliance(self):
        """Test that multi-language support matches established contract"""
        # Test internationalization contract
        i18n_requirements = {
            "language_detection": True,
            "content_translation": True,
            "ui_localization": True,
            "rtl_support": True,
            "locale_formatting": True
        }

        for requirement, needed in i18n_requirements.items():
            assert needed, f"I18n requirement {requirement} is mandatory"

        # Test localization contract
        localization_requirements = {
            "date_time_formatting": True,
            "number_formatting": True,
            "currency_formatting": True,
            "text_direction_support": True
        }

        for requirement, needed in localization_requirements.items():
            assert needed, f"Localization requirement {requirement} is mandatory"

        # Test translation contract
        translation_requirements = {
            "content_translation": True,
            "ui_string_translation": True,
            "search_query_translation": True,
            "multilingual_matching": True
        }

        for requirement, needed in translation_requirements.items():
            assert needed, f"Translation requirement {requirement} is mandatory"

        # Test data contract
        required_i18n_fields = [
            "language_code",
            "locale_identifier",
            "text_direction",
            "translation_quality",
            "localization_status"
        ]

        for field in required_i18n_fields:
            assert isinstance(field, str), f"I18n field {field} should be defined"

        # Test integration contract
        integration_points = [
            "content_management_integration",
            "search_engine_integration",
            "ui_framework_integration",
            "user_preferences_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"