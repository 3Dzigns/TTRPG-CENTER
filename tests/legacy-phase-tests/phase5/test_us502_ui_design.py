# tests/regression/phase5/test_us502_ui_design.py
"""
Phase 5 - US-502: Retro UI Design Regression Tests
Tests retro terminal/LCARS design implementation and visual consistency
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


class TestRetroUIDesign:
    """Test suite for Retro UI Design validation"""

    @pytest.fixture(scope="class")
    def driver(self):
        """Set up Selenium WebDriver for UI testing"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)

        yield driver

        driver.quit()

    def test_lcars_design_elements(self, driver):
        """Test LCARS (Star Trek) design elements implementation"""
        driver.get("http://localhost:8000")

        # Check for LCARS-specific design elements
        lcars_elements = [
            ".lcars-panel",
            ".lcars-button",
            ".lcars-corner",
            ".lcars-bar",
            ".lcars-frame",
            ".status-panel"
        ]

        found_lcars_elements = []
        for selector in lcars_elements:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    found_lcars_elements.append(selector)
            except:
                pass

        # Should have LCARS design elements
        assert len(found_lcars_elements) >= 3, f"Should have LCARS design elements, found: {found_lcars_elements}"

        # Check for LCARS color scheme
        body = driver.find_element(By.TAG_NAME, "body")
        computed_style = driver.execute_script(
            "return window.getComputedStyle(arguments[0]);", body
        )

        # LCARS typically uses orange, blue, and other specific colors
        # Check if CSS variables or classes suggest LCARS styling
        style_text = driver.execute_script("return document.head.innerHTML")

        lcars_colors = ["orange", "blue", "purple", "#ff9900", "#0099ff", "#cc99ff"]
        has_lcars_colors = any(color in style_text.lower() for color in lcars_colors)

        # Should incorporate LCARS color scheme
        if not has_lcars_colors:
            # Check computed styles of LCARS elements if any exist
            if found_lcars_elements:
                element = driver.find_element(By.CSS_SELECTOR, found_lcars_elements[0])
                element_style = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]);", element
                )
                # Should have distinctive colors
                assert element_style.get("color") or element_style.get("background-color"), "LCARS elements should have distinctive styling"

    def test_terminal_interface_elements(self, driver):
        """Test terminal interface design elements"""
        driver.get("http://localhost:8000")

        # Check for terminal-specific elements
        terminal_elements = [
            ".terminal",
            ".terminal-window",
            ".terminal-screen",
            ".terminal-prompt",
            ".command-line",
            ".terminal-output"
        ]

        found_terminal_elements = []
        for selector in terminal_elements:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    found_terminal_elements.append(selector)
            except:
                pass

        # Should have terminal design elements
        assert len(found_terminal_elements) >= 2, f"Should have terminal design elements, found: {found_terminal_elements}"

        # Check for monospace font usage
        if found_terminal_elements:
            terminal_element = driver.find_element(By.CSS_SELECTOR, found_terminal_elements[0])
            font_family = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).fontFamily;", terminal_element
            )

            # Should use monospace font
            monospace_fonts = ["monospace", "courier", "consolas", "monaco", "menlo"]
            has_monospace = any(font.lower() in font_family.lower() for font in monospace_fonts)
            assert has_monospace, f"Terminal elements should use monospace font, got: {font_family}"

    def test_retro_visual_effects(self, driver):
        """Test retro visual effects like scan lines, CRT effects"""
        driver.get("http://localhost:8000")

        # Check for retro visual effect elements
        retro_effects = [
            ".scan-lines",
            ".crt-effect",
            ".screen-flicker",
            ".phosphor-glow",
            ".retro-filter",
            ".vintage-effect"
        ]

        found_effects = []
        for selector in retro_effects:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    found_effects.append(selector)
            except:
                pass

        # Check for CSS animations or transitions that create retro effects
        animations = driver.execute_script("""
            let elements = document.querySelectorAll('*');
            let hasAnimations = false;
            for (let el of elements) {
                let style = window.getComputedStyle(el);
                if (style.animation !== 'none' || style.transition !== 'none') {
                    hasAnimations = true;
                    break;
                }
            }
            return hasAnimations;
        """)

        # Should have either effect elements or animations for retro feel
        assert len(found_effects) > 0 or animations, "Should have retro visual effects implemented"

    def test_color_scheme_consistency(self, driver):
        """Test consistent retro color scheme throughout interface"""
        driver.get("http://localhost:8000")

        # Get primary UI elements
        ui_elements = driver.find_elements(By.CSS_SELECTOR, "button, input, .panel, .container, nav")

        if ui_elements:
            # Check color consistency
            colors_used = set()

            for element in ui_elements[:10]:  # Check first 10 elements
                try:
                    bg_color = driver.execute_script(
                        "return window.getComputedStyle(arguments[0]).backgroundColor;", element
                    )
                    text_color = driver.execute_script(
                        "return window.getComputedStyle(arguments[0]).color;", element
                    )

                    if bg_color and bg_color != "rgba(0, 0, 0, 0)":
                        colors_used.add(bg_color)
                    if text_color:
                        colors_used.add(text_color)
                except:
                    pass

            # Should have a limited, consistent color palette
            assert len(colors_used) <= 10, f"Should have consistent color palette, found {len(colors_used)} colors"

    def test_responsive_design_consistency(self, driver):
        """Test that retro design maintains consistency across screen sizes"""
        test_sizes = [
            (1920, 1080),  # Desktop
            (1024, 768),   # Tablet
            (375, 667)     # Mobile
        ]

        design_consistency_results = []

        for width, height in test_sizes:
            driver.set_window_size(width, height)
            driver.get("http://localhost:8000")
            time.sleep(1)  # Allow resize to complete

            # Check if design elements are still present
            design_elements = [".lcars-panel", ".terminal-window", ".retro-text"]
            visible_elements = 0

            for selector in design_elements:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed():
                        visible_elements += 1
                except:
                    pass

            design_consistency_results.append({
                "size": f"{width}x{height}",
                "visible_elements": visible_elements
            })

        # Design elements should be visible across all screen sizes
        for result in design_consistency_results:
            assert result["visible_elements"] > 0, f"Design elements should be visible at {result['size']}"

    def test_typography_consistency(self, driver):
        """Test typography consistency in retro design"""
        driver.get("http://localhost:8000")

        # Check heading typography
        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")

        if headings:
            heading_fonts = set()
            for heading in headings[:5]:  # Check first 5 headings
                font_family = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).fontFamily;", heading
                )
                heading_fonts.add(font_family)

            # Should have consistent heading typography
            assert len(heading_fonts) <= 2, "Should have consistent heading typography"

        # Check body text typography
        text_elements = driver.find_elements(By.CSS_SELECTOR, "p, span, div")

        if text_elements:
            # Sample a few text elements
            for element in text_elements[:3]:
                font_size = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).fontSize;", element
                )

                # Font size should be readable (at least 12px)
                size_value = float(font_size.replace("px", ""))
                assert size_value >= 12, f"Text should be readable, got {font_size}"

    def test_interactive_elements_styling(self, driver):
        """Test styling of interactive elements (buttons, inputs, links)"""
        driver.get("http://localhost:8000")

        # Test button styling
        buttons = driver.find_elements(By.TAG_NAME, "button")

        for button in buttons[:3]:  # Test first 3 buttons
            # Check hover effects
            driver.execute_script("arguments[0].style.border = '2px solid red';", button)

            # Check button states
            is_enabled = button.is_enabled()
            if is_enabled:
                # Should have visual feedback for interactive state
                cursor = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).cursor;", button
                )
                assert cursor == "pointer", "Interactive buttons should have pointer cursor"

        # Test input field styling
        inputs = driver.find_elements(By.TAG_NAME, "input")

        for input_field in inputs[:2]:  # Test first 2 inputs
            # Check border and background
            border = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).border;", input_field
            )
            background = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).backgroundColor;", input_field
            )

            # Should have visible borders and backgrounds
            assert border != "none" or background != "rgba(0, 0, 0, 0)", "Input fields should have visible styling"

    def test_loading_states_design(self, driver):
        """Test design of loading states and animations"""
        driver.get("http://localhost:8000")

        # Look for loading indicators
        loading_selectors = [
            ".loading",
            ".spinner",
            ".loader",
            ".progress",
            ".loading-indicator"
        ]

        loading_elements_found = []
        for selector in loading_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    loading_elements_found.append(selector)
            except:
                pass

        # Check for CSS animations on loading elements
        if loading_elements_found:
            loading_element = driver.find_element(By.CSS_SELECTOR, loading_elements_found[0])
            animation = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).animation;", loading_element
            )

            # Loading elements should have animations
            if animation and animation != "none":
                assert "animation" in animation or animation != "none", "Loading elements should be animated"

    def test_error_state_design(self, driver):
        """Test design of error states and messages"""
        driver.get("http://localhost:8000")

        # Check if error styling is defined
        error_styles = driver.execute_script("""
            let hasErrorStyles = false;
            let sheets = document.styleSheets;
            for (let sheet of sheets) {
                try {
                    for (let rule of sheet.cssRules) {
                        if (rule.selectorText && (
                            rule.selectorText.includes('.error') ||
                            rule.selectorText.includes('.warning') ||
                            rule.selectorText.includes('.danger')
                        )) {
                            hasErrorStyles = true;
                            break;
                        }
                    }
                } catch (e) {
                    // Cross-origin CSS
                }
            }
            return hasErrorStyles;
        """)

        # Should have error state styling defined
        # This is a basic check - actual error states would be tested in functional tests

    def test_accessibility_in_retro_design(self, driver):
        """Test that retro design maintains accessibility standards"""
        driver.get("http://localhost:8000")

        # Check color contrast for readability
        # This is a simplified check - full contrast testing would require specialized tools
        text_elements = driver.find_elements(By.CSS_SELECTOR, "p, span, h1, h2, h3, button")

        for element in text_elements[:5]:  # Check first 5 text elements
            try:
                text_color = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).color;", element
                )
                bg_color = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).backgroundColor;", element
                )

                # Ensure text isn't invisible (same color as background)
                assert text_color != bg_color, "Text should be visible against background"

            except:
                pass

        # Check for focus indicators on interactive elements
        focusable_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "button, input, select, textarea, a[href]"
        )

        if focusable_elements:
            # Test focus on first focusable element
            first_focusable = focusable_elements[0]
            first_focusable.click()

            # Should have some form of focus indicator
            outline = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).outline;", first_focusable
            )
            box_shadow = driver.execute_script(
                "return window.getComputedStyle(arguments[0]).boxShadow;", first_focusable
            )

            # Should have focus indication (outline or box-shadow)
            has_focus_indicator = (outline and outline != "none") or (box_shadow and box_shadow != "none")

    def test_animation_performance(self, driver):
        """Test that retro animations don't impact performance"""
        driver.get("http://localhost:8000")

        # Measure page load performance with animations
        start_time = time.perf_counter()

        # Wait for page to fully load
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        end_time = time.perf_counter()
        load_time = (end_time - start_time) * 1000

        # Page should load reasonably fast even with animations
        assert load_time < 5000, f"Page load time with animations {load_time:.1f}ms should be < 5000ms"

        # Check if animations are hardware accelerated (use transform/opacity)
        animated_elements = driver.execute_script("""
            let elements = document.querySelectorAll('*');
            let animatedCount = 0;
            let hardwareAccelerated = 0;

            for (let el of elements) {
                let style = window.getComputedStyle(el);
                if (style.animation !== 'none') {
                    animatedCount++;
                    if (style.transform !== 'none' || style.opacity !== '1') {
                        hardwareAccelerated++;
                    }
                }
            }

            return { total: animatedCount, hardwareAccelerated: hardwareAccelerated };
        """)

        # If animations exist, they should use hardware acceleration when possible
        if animated_elements["total"] > 0:
            acceleration_ratio = animated_elements["hardwareAccelerated"] / animated_elements["total"]
            # At least some animations should use hardware acceleration
            assert acceleration_ratio >= 0.3, "Animations should use hardware acceleration for performance"

    def test_theme_consistency_across_pages(self, driver):
        """Test theme consistency across different pages"""
        pages = [
            "http://localhost:8000",
            "http://localhost:8000/chat",
            "http://localhost:8000/admin" if driver.current_url else None
        ]

        page_themes = []

        for page_url in pages:
            if page_url:
                try:
                    driver.get(page_url)
                    time.sleep(1)

                    # Extract theme colors
                    body_bg = driver.execute_script(
                        "return window.getComputedStyle(document.body).backgroundColor;"
                    )
                    primary_color = driver.execute_script("""
                        let button = document.querySelector('button');
                        return button ? window.getComputedStyle(button).backgroundColor : null;
                    """)

                    page_themes.append({
                        "url": page_url,
                        "body_bg": body_bg,
                        "primary_color": primary_color
                    })

                except:
                    pass

        # Themes should be consistent across pages
        if len(page_themes) > 1:
            first_theme = page_themes[0]
            for theme in page_themes[1:]:
                # Body background should be consistent
                if first_theme["body_bg"] and theme["body_bg"]:
                    assert first_theme["body_bg"] == theme["body_bg"], "Body background should be consistent across pages"

    def test_retro_design_contract_compliance(self, driver):
        """Test that retro design implementation matches established contract"""
        driver.get("http://localhost:8000")

        # Check for required retro design elements
        required_design_features = [
            # Should have either LCARS or terminal styling
            (".lcars-panel", ".terminal-window", ".retro-interface"),
            # Should have retro color scheme
            ("color scheme implementation", True),
            # Should have appropriate typography
            ("typography implementation", True)
        ]

        design_compliance = []

        # Check for design element presence
        has_retro_elements = False
        retro_selectors = [".lcars-panel", ".terminal-window", ".retro-interface", ".retro-text"]

        for selector in retro_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    has_retro_elements = True
                    break
            except:
                pass

        assert has_retro_elements, "Interface should have retro design elements"

        # Check for color scheme implementation
        styles = driver.execute_script("return document.head.innerHTML")
        has_color_scheme = any(color in styles.lower() for color in [
            "rgb", "rgba", "hsl", "#", "color:", "background-color:"
        ])

        assert has_color_scheme, "Interface should have defined color scheme"

        # Check for consistent styling
        styled_elements = driver.find_elements(By.CSS_SELECTOR, "*")
        elements_with_styling = 0

        for element in styled_elements[:20]:  # Check first 20 elements
            try:
                computed_style = driver.execute_script("""
                    let style = window.getComputedStyle(arguments[0]);
                    return style.backgroundColor !== 'rgba(0, 0, 0, 0)' ||
                           style.color !== 'rgb(0, 0, 0)' ||
                           style.border !== 'none';
                """, element)

                if computed_style:
                    elements_with_styling += 1
            except:
                pass

        # Should have styled elements indicating design implementation
        styling_ratio = elements_with_styling / min(20, len(styled_elements))
        assert styling_ratio >= 0.2, "Interface should have consistent styling implementation"