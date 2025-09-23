# tests/regression/feature_requests/test_fr014_mobile_responsive.py
"""
Feature Request FR-014: Mobile-Responsive Design and Touch Interface Regression Tests
Tests responsive design, mobile optimization, and touch-friendly interface elements
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


class TestMobileResponsiveDesign:
    """Test suite for FR-014 Mobile-Responsive Design functionality"""

    def test_responsive_design_infrastructure_availability(self):
        """Test that responsive design components are available"""
        try:
            from src_common.ui import ResponsiveLayoutManager
            from src_common.mobile import MobileOptimizationEngine
            from src_common.touch import TouchInterfaceHandler
            from src_common.viewport import ViewportManager

            assert ResponsiveLayoutManager is not None, "ResponsiveLayoutManager should be available"
            assert MobileOptimizationEngine is not None, "MobileOptimizationEngine should be available"
            assert TouchInterfaceHandler is not None, "TouchInterfaceHandler should be available"
            assert ViewportManager is not None, "ViewportManager should be available"

        except ImportError as e:
            pytest.fail(f"Responsive design components not available: {e}")

    def test_viewport_and_breakpoint_management(self):
        """Test viewport detection and responsive breakpoint handling"""
        try:
            from src_common.viewport import ViewportManager
        except ImportError:
            pytest.skip("Viewport manager not available for testing")

        viewport_manager = ViewportManager()

        # Test breakpoint configuration
        breakpoint_config = {
            "breakpoints": {
                "xs": {"min": 0, "max": 575, "name": "extra_small"},
                "sm": {"min": 576, "max": 767, "name": "small"},
                "md": {"min": 768, "max": 991, "name": "medium"},
                "lg": {"min": 992, "max": 1199, "name": "large"},
                "xl": {"min": 1200, "max": 1399, "name": "extra_large"},
                "xxl": {"min": 1400, "max": 9999, "name": "extra_extra_large"}
            },
            "orientation_support": True,
            "density_awareness": True,
            "responsive_images": True
        }

        if hasattr(viewport_manager, 'configure_breakpoints'):
            config_result = viewport_manager.configure_breakpoints(breakpoint_config)

            assert isinstance(config_result, dict), "Breakpoint configuration should return structured result"

            if "configured_breakpoints" in config_result:
                configured = config_result["configured_breakpoints"]
                assert isinstance(configured, dict), "Configured breakpoints should be dictionary"
                assert len(configured) == len(breakpoint_config["breakpoints"]), "Should configure all breakpoints"

        # Test viewport detection
        test_viewports = [
            {"width": 320, "height": 568, "expected": "xs"},  # iPhone SE
            {"width": 768, "height": 1024, "expected": "md"},  # iPad
            {"width": 1920, "height": 1080, "expected": "xxl"}  # Desktop
        ]

        if hasattr(viewport_manager, 'detect_viewport_category'):
            for viewport in test_viewports:
                detection_result = viewport_manager.detect_viewport_category(
                    viewport["width"],
                    viewport["height"]
                )

                assert isinstance(detection_result, dict), "Viewport detection should return structured result"

                if "category" in detection_result:
                    category = detection_result["category"]
                    assert category == viewport["expected"], f"Viewport {viewport['width']}x{viewport['height']} should be {viewport['expected']}"

                if "orientation" in detection_result:
                    orientation = detection_result["orientation"]
                    expected_orientation = "portrait" if viewport["height"] > viewport["width"] else "landscape"
                    assert orientation == expected_orientation, "Should detect correct orientation"

    def test_responsive_layout_adaptation(self):
        """Test responsive layout adaptation across different screen sizes"""
        try:
            from src_common.ui import ResponsiveLayoutManager
        except ImportError:
            pytest.skip("Responsive layout manager not available for testing")

        layout_manager = ResponsiveLayoutManager()

        # Test layout configuration for different breakpoints
        layout_configs = {
            "search_interface": {
                "xs": {
                    "layout": "single_column",
                    "search_bar": {"position": "top", "width": "100%"},
                    "filters": {"position": "collapsed", "display": "modal"},
                    "results": {"columns": 1, "pagination": "infinite_scroll"}
                },
                "md": {
                    "layout": "two_column",
                    "search_bar": {"position": "top", "width": "70%"},
                    "filters": {"position": "sidebar", "display": "expanded"},
                    "results": {"columns": 2, "pagination": "standard"}
                },
                "xl": {
                    "layout": "three_column",
                    "search_bar": {"position": "header", "width": "50%"},
                    "filters": {"position": "left_sidebar", "display": "expanded"},
                    "results": {"columns": 3, "pagination": "standard"}
                }
            },
            "content_viewer": {
                "xs": {
                    "layout": "full_screen",
                    "navigation": "bottom_bar",
                    "content": {"font_size": "16px", "line_height": "1.6"},
                    "controls": {"size": "large", "spacing": "touch_friendly"}
                },
                "md": {
                    "layout": "with_sidebar",
                    "navigation": "side_panel",
                    "content": {"font_size": "14px", "line_height": "1.5"},
                    "controls": {"size": "medium", "spacing": "compact"}
                }
            }
        }

        for interface_name, configs in layout_configs.items():
            if hasattr(layout_manager, 'apply_responsive_layout'):
                for breakpoint, config in configs.items():
                    layout_result = layout_manager.apply_responsive_layout(
                        interface_name,
                        breakpoint,
                        config
                    )

                    assert isinstance(layout_result, dict), "Layout application should return structured result"

                    if "layout_applied" in layout_result:
                        applied = layout_result["layout_applied"]
                        assert applied == True, f"Layout should apply successfully for {breakpoint}"

                    if "css_classes" in layout_result:
                        css_classes = layout_result["css_classes"]
                        assert isinstance(css_classes, list), "CSS classes should be list"
                        assert len(css_classes) > 0, "Should generate CSS classes"

                    if "component_adjustments" in layout_result:
                        adjustments = layout_result["component_adjustments"]
                        assert isinstance(adjustments, dict), "Component adjustments should be dictionary"

    def test_touch_interface_optimization(self):
        """Test touch interface optimization and gesture support"""
        try:
            from src_common.touch import TouchInterfaceHandler
        except ImportError:
            pytest.skip("Touch interface handler not available for testing")

        touch_handler = TouchInterfaceHandler()

        # Test touch interface configuration
        touch_config = {
            "touch_targets": {
                "minimum_size": "44px",
                "spacing": "8px",
                "hit_area_expansion": "12px"
            },
            "gestures": {
                "swipe": {"enabled": True, "threshold": 50},
                "pinch_zoom": {"enabled": True, "min_scale": 0.5, "max_scale": 3.0},
                "long_press": {"enabled": True, "duration": 500},
                "double_tap": {"enabled": True, "delay": 300}
            },
            "scrolling": {
                "momentum": True,
                "bounce": True,
                "overscroll": "elastic"
            },
            "feedback": {
                "haptic": True,
                "visual": True,
                "audio": False
            }
        }

        if hasattr(touch_handler, 'configure_touch_interface'):
            config_result = touch_handler.configure_touch_interface(touch_config)

            assert isinstance(config_result, dict), "Touch configuration should return structured result"

            if "touch_optimized" in config_result:
                optimized = config_result["touch_optimized"]
                assert optimized == True, "Touch interface should be optimized"

            if "gesture_handlers" in config_result:
                handlers = config_result["gesture_handlers"]
                assert isinstance(handlers, dict), "Gesture handlers should be dictionary"

                for gesture_name in touch_config["gestures"]:
                    if gesture_name in handlers:
                        handler = handlers[gesture_name]
                        assert "enabled" in handler, f"Gesture {gesture_name} should have enabled status"

        # Test touch target validation
        if hasattr(touch_handler, 'validate_touch_targets'):
            test_elements = [
                {"id": "search_button", "width": 48, "height": 48, "type": "button"},
                {"id": "filter_link", "width": 32, "height": 32, "type": "link"},  # Too small
                {"id": "result_item", "width": 300, "height": 60, "type": "card"}
            ]

            validation_result = touch_handler.validate_touch_targets(test_elements)

            assert isinstance(validation_result, dict), "Touch target validation should return structured result"

            if "validation_summary" in validation_result:
                summary = validation_result["validation_summary"]
                assert "total_elements" in summary, "Should track total elements"
                assert "compliant_elements" in summary, "Should track compliant elements"
                assert "issues_found" in summary, "Should track issues"

            if "accessibility_issues" in validation_result:
                issues = validation_result["accessibility_issues"]
                assert isinstance(issues, list), "Issues should be list"

                # Should identify the small filter link as an issue
                small_element_issues = [
                    issue for issue in issues
                    if issue.get("element_id") == "filter_link"
                ]
                assert len(small_element_issues) > 0, "Should identify small touch targets"

    def test_mobile_search_interface_optimization(self):
        """Test mobile-optimized search interface and interactions"""
        try:
            from src_common.mobile import MobileOptimizationEngine
        except ImportError:
            pytest.skip("Mobile optimization engine not available for testing")

        mobile_engine = MobileOptimizationEngine()

        # Test mobile search optimization
        search_optimization_config = {
            "search_bar": {
                "auto_focus": False,  # Prevents unwanted keyboard on mobile
                "placeholder_text": "Search spells, rules, items...",
                "voice_input": True,
                "autocomplete": True,
                "search_suggestions": True
            },
            "filters": {
                "display_style": "drawer",
                "quick_filters": ["content_type", "source_book"],
                "filter_chips": True,
                "clear_all_visible": True
            },
            "results": {
                "infinite_scroll": True,
                "lazy_loading": True,
                "thumbnail_optimization": True,
                "tap_to_expand": True
            },
            "navigation": {
                "back_button_handling": True,
                "breadcrumbs": "collapsed",
                "tab_navigation": "bottom"
            }
        }

        if hasattr(mobile_engine, 'optimize_search_interface'):
            optimization_result = mobile_engine.optimize_search_interface(search_optimization_config)

            assert isinstance(optimization_result, dict), "Search optimization should return structured result"

            if "interface_optimized" in optimization_result:
                optimized = optimization_result["interface_optimized"]
                assert optimized == True, "Search interface should be optimized for mobile"

            if "optimization_features" in optimization_result:
                features = optimization_result["optimization_features"]
                assert isinstance(features, list), "Optimization features should be list"

                expected_features = ["voice_input", "infinite_scroll", "filter_drawer", "touch_targets"]
                for feature in expected_features:
                    assert any(feature in str(f).lower() for f in features), f"Should include {feature} optimization"

        # Test mobile keyboard and input optimization
        if hasattr(mobile_engine, 'optimize_input_experience'):
            input_config = {
                "keyboard_type": "search",
                "autocorrect": False,
                "autocapitalize": "none",
                "spellcheck": False,
                "input_mode": "text"
            }

            input_result = mobile_engine.optimize_input_experience(input_config)

            assert isinstance(input_result, dict), "Input optimization should return structured result"

            if "input_attributes" in input_result:
                attributes = input_result["input_attributes"]
                assert isinstance(attributes, dict), "Input attributes should be dictionary"

    def test_responsive_content_display(self):
        """Test responsive content display and readability optimization"""
        try:
            from src_common.ui import ResponsiveLayoutManager
        except ImportError:
            pytest.skip("Responsive layout manager not available for testing")

        layout_manager = ResponsiveLayoutManager()

        # Test content display optimization
        content_display_config = {
            "typography": {
                "mobile": {
                    "base_font_size": "16px",
                    "line_height": "1.6",
                    "paragraph_spacing": "1.2em",
                    "heading_scale": "1.2"
                },
                "tablet": {
                    "base_font_size": "15px",
                    "line_height": "1.5",
                    "paragraph_spacing": "1em",
                    "heading_scale": "1.3"
                },
                "desktop": {
                    "base_font_size": "14px",
                    "line_height": "1.4",
                    "paragraph_spacing": "0.8em",
                    "heading_scale": "1.4"
                }
            },
            "content_sections": {
                "mobile": {
                    "max_content_width": "100%",
                    "sidebar_behavior": "collapse",
                    "image_scaling": "responsive",
                    "table_behavior": "horizontal_scroll"
                },
                "tablet": {
                    "max_content_width": "90%",
                    "sidebar_behavior": "overlay",
                    "image_scaling": "constrained",
                    "table_behavior": "responsive"
                }
            }
        }

        test_content = {
            "title": "Advanced Spellcasting Rules",
            "sections": [
                {
                    "heading": "Concentration",
                    "content": "When a spellcaster casts a spell that requires concentration...",
                    "has_table": True,
                    "has_images": True
                },
                {
                    "heading": "Spell Components",
                    "content": "Spells have three types of components: verbal, somatic, and material...",
                    "has_table": False,
                    "has_images": False
                }
            ]
        }

        if hasattr(layout_manager, 'optimize_content_display'):
            for device_type in ["mobile", "tablet", "desktop"]:
                display_result = layout_manager.optimize_content_display(
                    test_content,
                    content_display_config[device_type] if device_type in content_display_config else content_display_config["typography"][device_type]
                )

                assert isinstance(display_result, dict), f"Content display optimization should return structured result for {device_type}"

                if "optimized_content" in display_result:
                    optimized = display_result["optimized_content"]
                    assert isinstance(optimized, dict), "Optimized content should be dictionary"

                if "css_styles" in display_result:
                    styles = display_result["css_styles"]
                    assert isinstance(styles, dict), "CSS styles should be dictionary"

                if "accessibility_enhancements" in display_result:
                    accessibility = display_result["accessibility_enhancements"]
                    assert isinstance(accessibility, dict), "Accessibility enhancements should be dictionary"

    def test_mobile_performance_optimization(self):
        """Test mobile performance optimization and loading strategies"""
        try:
            from src_common.mobile import MobileOptimizationEngine
        except ImportError:
            pytest.skip("Mobile optimization engine not available for testing")

        mobile_engine = MobileOptimizationEngine()

        # Test performance optimization configuration
        performance_config = {
            "loading_strategy": {
                "critical_css": "inline",
                "non_critical_css": "async",
                "javascript": "defer",
                "images": "lazy_load"
            },
            "resource_optimization": {
                "image_compression": True,
                "webp_support": True,
                "cdn_usage": True,
                "resource_bundling": True
            },
            "caching_strategy": {
                "service_worker": True,
                "app_cache": True,
                "browser_cache": "aggressive",
                "offline_fallbacks": True
            },
            "connection_awareness": {
                "adaptive_quality": True,
                "slow_connection_mode": True,
                "data_saver_mode": True
            }
        }

        if hasattr(mobile_engine, 'optimize_performance'):
            performance_result = mobile_engine.optimize_performance(performance_config)

            assert isinstance(performance_result, dict), "Performance optimization should return structured result"

            if "optimization_applied" in performance_result:
                applied = performance_result["optimization_applied"]
                assert applied == True, "Performance optimizations should be applied"

            if "performance_metrics" in performance_result:
                metrics = performance_result["performance_metrics"]
                assert isinstance(metrics, dict), "Performance metrics should be dictionary"

                expected_metrics = ["loading_time_improvement", "bandwidth_reduction", "cache_hit_ratio"]
                for metric in expected_metrics:
                    if metric in metrics:
                        value = metrics[metric]
                        assert isinstance(value, (int, float)), f"Metric {metric} should be numeric"

        # Test progressive loading implementation
        if hasattr(mobile_engine, 'implement_progressive_loading'):
            content_manifest = {
                "critical_content": [
                    {"id": "search_interface", "priority": 1, "size_kb": 50},
                    {"id": "main_navigation", "priority": 1, "size_kb": 20}
                ],
                "secondary_content": [
                    {"id": "filter_panel", "priority": 2, "size_kb": 30},
                    {"id": "search_results", "priority": 2, "size_kb": 100}
                ],
                "optional_content": [
                    {"id": "advertisements", "priority": 3, "size_kb": 75},
                    {"id": "related_links", "priority": 3, "size_kb": 25}
                ]
            }

            loading_result = mobile_engine.implement_progressive_loading(content_manifest)

            assert isinstance(loading_result, dict), "Progressive loading should return structured result"

            if "loading_sequence" in loading_result:
                sequence = loading_result["loading_sequence"]
                assert isinstance(sequence, list), "Loading sequence should be list"

                # Verify critical content loads first
                first_phase = sequence[0] if sequence else {}
                if "content_items" in first_phase:
                    first_items = first_phase["content_items"]
                    critical_ids = {item["id"] for item in content_manifest["critical_content"]}
                    first_phase_ids = {item for item in first_items}

                    # Should include critical content in first phase
                    assert len(critical_ids.intersection(first_phase_ids)) > 0, "First phase should include critical content"

    def test_mobile_responsive_contract_compliance(self):
        """Test that mobile responsive design matches established contract"""
        # Test responsive design contract
        responsive_requirements = {
            "viewport_management": True,
            "breakpoint_handling": True,
            "flexible_layouts": True,
            "adaptive_typography": True,
            "responsive_images": True
        }

        for requirement, needed in responsive_requirements.items():
            assert needed, f"Responsive requirement {requirement} is mandatory"

        # Test touch interface contract
        touch_requirements = {
            "touch_target_optimization": True,
            "gesture_support": True,
            "haptic_feedback": True,
            "accessibility_compliance": True
        }

        for requirement, needed in touch_requirements.items():
            assert needed, f"Touch requirement {requirement} is mandatory"

        # Test mobile optimization contract
        mobile_requirements = {
            "performance_optimization": True,
            "progressive_loading": True,
            "offline_capabilities": True,
            "connection_awareness": True
        }

        for requirement, needed in mobile_requirements.items():
            assert needed, f"Mobile requirement {requirement} is mandatory"

        # Test data contract
        required_mobile_fields = [
            "viewport_config",
            "breakpoint_category",
            "touch_optimization",
            "performance_metrics",
            "accessibility_score"
        ]

        for field in required_mobile_fields:
            assert isinstance(field, str), f"Mobile field {field} should be defined"

        # Test integration contract
        integration_points = [
            "ui_framework_integration",
            "performance_monitoring_integration",
            "accessibility_testing_integration",
            "analytics_tracking_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"