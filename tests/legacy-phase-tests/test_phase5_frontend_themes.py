# tests/unit/test_phase5_frontend_themes.py
"""
Unit tests for Phase 5 Frontend Theme System
Tests theme loading, switching, and UI component theming (US-501)
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the FastAPI app
from app_user import app


class TestThemeFiles:
    """Test theme CSS files and structure (US-501)"""
    
    def test_theme_files_exist(self):
        """Test that all required theme files exist"""
        theme_dir = Path("static/user/css/themes")
        
        required_themes = ["lcars.css", "terminal.css", "classic.css"]
        
        for theme_file in required_themes:
            theme_path = theme_dir / theme_file
            assert theme_path.exists(), f"Theme file {theme_file} should exist"
            
            # Verify file is not empty
            assert theme_path.stat().st_size > 0, f"Theme file {theme_file} should not be empty"
    
    def test_lcars_theme_css_structure(self):
        """Test LCARS theme CSS has required structure"""
        lcars_path = Path("static/user/css/themes/lcars.css")
        
        with open(lcars_path, 'r') as file:
            css_content = file.read()
        
        # Check for LCARS-specific color variables
        required_variables = [
            "--lcars-orange",
            "--lcars-red", 
            "--lcars-blue",
            "--lcars-purple",
            "--primary-bg",
            "--primary-text",
            "--accent-text"
        ]
        
        for variable in required_variables:
            assert variable in css_content, f"LCARS theme should define {variable}"
        
        # Check for theme class
        assert ".theme-lcars" in css_content, "LCARS theme should have theme-lcars class"
        
        # Check for LCARS-specific styling
        lcars_indicators = [
            "#ff9900",  # LCARS orange
            "Orbitron",  # LCARS font
            "LCARS"  # LCARS comment/reference
        ]
        
        found_indicators = 0
        for indicator in lcars_indicators:
            if indicator in css_content:
                found_indicators += 1
        
        assert found_indicators >= 2, "LCARS theme should have LCARS-specific styling elements"
    
    def test_terminal_theme_css_structure(self):
        """Test Terminal theme CSS has required structure"""
        terminal_path = Path("static/user/css/themes/terminal.css")
        
        with open(terminal_path, 'r') as file:
            css_content = file.read()
        
        # Check for terminal-specific elements
        terminal_indicators = [
            "--terminal-green",
            ".theme-terminal",
            "monospace",
            "terminal",
            "#00ff00"  # Classic terminal green
        ]
        
        found_indicators = 0
        for indicator in terminal_indicators:
            if indicator.lower() in css_content.lower():
                found_indicators += 1
        
        assert found_indicators >= 3, "Terminal theme should have terminal-specific styling elements"
    
    def test_classic_theme_css_structure(self):
        """Test Classic theme CSS has required structure"""
        classic_path = Path("static/user/css/themes/classic.css")
        
        with open(classic_path, 'r') as file:
            css_content = file.read()
        
        # Check for classic theme elements
        classic_indicators = [
            ".theme-classic",
            "--primary-bg",
            "--primary-text",
            "classic"
        ]
        
        found_indicators = 0
        for indicator in classic_indicators:
            if indicator.lower() in css_content.lower():
                found_indicators += 1
        
        assert found_indicators >= 2, "Classic theme should have classic theme styling elements"


class TestThemeAPI:
    """Test theme-related API endpoints (US-501)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_themes_api_endpoint(self, client):
        """Test /api/themes endpoint returns correct theme data"""
        response = client.get("/api/themes")
        
        assert response.status_code == 200
        data = response.json()
        assert "themes" in data
        
        themes = data["themes"]
        assert len(themes) >= 3  # At least lcars, terminal, classic
        
        # Check theme structure
        for theme in themes:
            assert "id" in theme
            assert "name" in theme  
            assert "description" in theme
            
            # Verify required themes are present
            theme_ids = [t["id"] for t in themes]
            assert "lcars" in theme_ids
            assert "terminal" in theme_ids
            assert "classic" in theme_ids
    
    def test_lcars_theme_api_data(self, client):
        """Test LCARS theme API data is correct"""
        response = client.get("/api/themes")
        data = response.json()
        
        lcars_theme = next((t for t in data["themes"] if t["id"] == "lcars"), None)
        
        assert lcars_theme is not None
        assert lcars_theme["name"] == "LCARS"
        assert "Star Trek" in lcars_theme["description"] or "LCARS" in lcars_theme["description"]
    
    def test_terminal_theme_api_data(self, client):
        """Test Terminal theme API data is correct"""
        response = client.get("/api/themes")
        data = response.json()
        
        terminal_theme = next((t for t in data["themes"] if t["id"] == "terminal"), None)
        
        assert terminal_theme is not None
        assert terminal_theme["name"] == "Retro Terminal"
        assert "terminal" in terminal_theme["description"].lower()
    
    def test_classic_theme_api_data(self, client):
        """Test Classic theme API data is correct"""
        response = client.get("/api/themes")
        data = response.json()
        
        classic_theme = next((t for t in data["themes"] if t["id"] == "classic"), None)
        
        assert classic_theme is not None
        assert classic_theme["name"] == "Classic"
        assert "modern" in classic_theme["description"].lower() or "clean" in classic_theme["description"].lower()


class TestThemeJavaScript:
    """Test theme-related JavaScript functionality"""
    
    def test_theme_manager_js_exists(self):
        """Test theme manager JavaScript file exists"""
        theme_js_path = Path("static/user/js/theme-manager.js")
        
        assert theme_js_path.exists(), "theme-manager.js should exist"
        assert theme_js_path.stat().st_size > 0, "theme-manager.js should not be empty"
    
    def test_theme_manager_js_structure(self):
        """Test theme manager JavaScript has required functions"""
        theme_js_path = Path("static/user/js/theme-manager.js")
        
        with open(theme_js_path, 'r') as file:
            js_content = file.read()
        
        # Check for theme management functions
        required_functions = [
            "ThemeManager",
            "setTheme",
            "getTheme",
            "loadTheme",
            "theme"
        ]
        
        found_functions = 0
        for function in required_functions:
            if function in js_content:
                found_functions += 1
        
        assert found_functions >= 3, "Theme manager should have core theme functions"
        
        # Check for theme references
        theme_references = ["lcars", "terminal", "classic"]
        found_themes = 0
        for theme in theme_references:
            if theme in js_content.lower():
                found_themes += 1
        
        assert found_themes >= 2, "Theme manager should reference available themes"
    
    def test_main_js_theme_integration(self):
        """Test main.js integrates with theme system"""
        main_js_path = Path("static/user/js/main.js")
        
        with open(main_js_path, 'r') as file:
            js_content = file.read()
        
        # Check for theme initialization
        theme_indicators = [
            "theme",
            "initializeThemeSystem",
            "ThemeManager"
        ]
        
        found_indicators = 0
        for indicator in theme_indicators:
            if indicator in js_content:
                found_indicators += 1
        
        assert found_indicators >= 1, "Main.js should integrate with theme system"


class TestThemeUserPreferences:
    """Test theme preferences integration with user system (US-505)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_user_theme_preference_storage(self, client):
        """Test user theme preferences can be stored and retrieved"""
        user_id = "theme_test_user"
        
        # Set theme preference
        preferences = {"theme": "terminal"}
        response = client.put(f"/api/user/{user_id}/preferences", json=preferences)
        
        assert response.status_code == 200
        
        # Retrieve preferences
        response = client.get(f"/api/user/{user_id}/preferences")
        
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "terminal"
    
    def test_default_theme_preference(self, client):
        """Test default theme preference is LCARS"""
        user_id = "default_theme_user"
        
        # Get preferences for new user
        response = client.get(f"/api/user/{user_id}/preferences")
        
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "lcars"  # Default theme
    
    def test_invalid_theme_preference_handling(self, client):
        """Test handling of invalid theme preferences"""
        user_id = "invalid_theme_user"
        
        # Try to set invalid theme
        preferences = {"theme": "nonexistent_theme"}
        response = client.put(f"/api/user/{user_id}/preferences", json=preferences)
        
        # Should accept any string (validation would be on frontend)
        assert response.status_code == 200
        
        # Verify it was stored
        response = client.get(f"/api/user/{user_id}/preferences")
        data = response.json()
        assert data["theme"] == "nonexistent_theme"
    
    def test_theme_preference_persistence(self, client):
        """Test theme preferences persist across requests"""
        user_id = "persistent_theme_user"
        
        # Set terminal theme
        client.put(f"/api/user/{user_id}/preferences", json={"theme": "terminal"})
        
        # Make other preference changes
        client.put(f"/api/user/{user_id}/preferences", json={"tone": "casual"})
        
        # Verify theme preference is still there
        response = client.get(f"/api/user/{user_id}/preferences")
        data = response.json()
        assert data["theme"] == "terminal"
        assert data["tone"] == "casual"
    
    def test_theme_preference_update_workflow(self, client):
        """Test complete theme preference update workflow"""
        user_id = "workflow_theme_user"
        
        # Start with default
        response = client.get(f"/api/user/{user_id}/preferences")
        initial_data = response.json()
        assert initial_data["theme"] == "lcars"
        initial_updated = initial_data["updated_at"]
        
        # Update to terminal
        client.put(f"/api/user/{user_id}/preferences", json={"theme": "terminal"})
        
        response = client.get(f"/api/user/{user_id}/preferences")
        terminal_data = response.json()
        assert terminal_data["theme"] == "terminal"
        assert terminal_data["updated_at"] > initial_updated
        
        # Update to classic
        client.put(f"/api/user/{user_id}/preferences", json={"theme": "classic"})
        
        response = client.get(f"/api/user/{user_id}/preferences")
        classic_data = response.json()
        assert classic_data["theme"] == "classic"
        assert classic_data["updated_at"] > terminal_data["updated_at"]


class TestThemeUIIntegration:
    """Test theme integration with UI components"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_main_page_includes_theme_css(self, client):
        """Test main page includes theme CSS files"""
        response = client.get("/")
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for theme CSS includes
        assert "css/themes/" in html_content or "theme" in html_content.lower()
    
    def test_main_page_theme_configuration(self, client):
        """Test main page includes theme configuration"""
        response = client.get("/")
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for theme-related JavaScript configuration
        theme_indicators = [
            "theme",
            "lcars",
            "TTRPG_CONFIG"
        ]
        
        found_indicators = 0
        for indicator in theme_indicators:
            if indicator in html_content:
                found_indicators += 1
        
        assert found_indicators >= 1, "Main page should include theme configuration"
    
    def test_ui_components_have_theme_classes(self, client):
        """Test UI components have theme-related CSS classes"""
        response = client.get("/")
        
        assert response.status_code == 200
        html_content = response.text
        
        # Check for theme-aware components
        theme_classes = [
            "panel-header",
            "primary-btn", 
            "response-container",
            "query-input"
        ]
        
        found_classes = 0
        for theme_class in theme_classes:
            if theme_class in html_content:
                found_classes += 1
        
        assert found_classes >= 3, "UI should have theme-aware component classes"


class TestThemeAccessibility:
    """Test theme accessibility features"""
    
    def test_theme_css_has_accessibility_features(self):
        """Test theme CSS files include accessibility considerations"""
        theme_files = [
            "static/user/css/themes/lcars.css",
            "static/user/css/themes/terminal.css", 
            "static/user/css/themes/classic.css"
        ]
        
        for theme_file in theme_files:
            theme_path = Path(theme_file)
            if theme_path.exists():
                with open(theme_path, 'r') as file:
                    css_content = file.read()
                
                # Check for accessibility features
                accessibility_features = [
                    "focus",
                    "outline",
                    "contrast",
                    ":hover",
                    ":focus"
                ]
                
                found_features = 0
                for feature in accessibility_features:
                    if feature in css_content.lower():
                        found_features += 1
                
                # At least some accessibility considerations should be present
                assert found_features >= 2, f"Theme {theme_file} should have accessibility features"
    
    def test_main_css_accessibility_support(self):
        """Test main CSS includes accessibility support"""
        main_css_path = Path("static/user/css/main.css")
        
        with open(main_css_path, 'r') as file:
            css_content = file.read()
        
        # Check for accessibility-specific CSS
        accessibility_rules = [
            "@media (prefers-reduced-motion",
            "@media (prefers-contrast",
            ":focus",
            "outline",
            "aria-",
            "sr-only"
        ]
        
        found_rules = 0
        for rule in accessibility_rules:
            if rule in css_content:
                found_rules += 1
        
        assert found_rules >= 3, "Main CSS should include accessibility support"


class TestThemePerformance:
    """Test theme performance characteristics"""
    
    def test_theme_css_file_sizes(self):
        """Test theme CSS files are reasonably sized"""
        theme_files = [
            "static/user/css/themes/lcars.css",
            "static/user/css/themes/terminal.css",
            "static/user/css/themes/classic.css"
        ]
        
        max_size = 50 * 1024  # 50KB max per theme file
        
        for theme_file in theme_files:
            theme_path = Path(theme_file)
            if theme_path.exists():
                file_size = theme_path.stat().st_size
                assert file_size < max_size, f"Theme file {theme_file} should be under {max_size} bytes"
    
    def test_theme_css_optimization(self):
        """Test theme CSS is optimized (no obvious inefficiencies)"""
        theme_files = [
            "static/user/css/themes/lcars.css",
            "static/user/css/themes/terminal.css",
            "static/user/css/themes/classic.css"
        ]
        
        for theme_file in theme_files:
            theme_path = Path(theme_file)
            if theme_path.exists():
                with open(theme_path, 'r') as file:
                    css_content = file.read()
                
                # Check for potential inefficiencies
                lines = css_content.split('\n')
                
                # Should not have excessive empty lines
                empty_lines = sum(1 for line in lines if line.strip() == '')
                total_lines = len(lines)
                
                if total_lines > 0:
                    empty_ratio = empty_lines / total_lines
                    assert empty_ratio < 0.3, f"Theme {theme_file} has too many empty lines"
                
                # Should not have obvious duplicated selectors (basic check)
                selectors = []
                for line in lines:
                    if line.strip().endswith('{') and not line.strip().startswith('/*'):
                        selector = line.strip()[:-1].strip()
                        selectors.append(selector)
                
                unique_selectors = set(selectors)
                if len(selectors) > 10:  # Only check if substantial content
                    duplication_ratio = 1 - (len(unique_selectors) / len(selectors))
                    assert duplication_ratio < 0.2, f"Theme {theme_file} may have too much selector duplication"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])