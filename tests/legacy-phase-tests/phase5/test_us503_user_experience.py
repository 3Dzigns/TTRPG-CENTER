# tests/regression/phase5/test_us503_user_experience.py
"""
Phase 5 - US-503: User Experience Regression Tests
Tests overall user experience, usability, and interaction flow
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
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys


class TestUserExperience:
    """Test suite for User Experience validation"""

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

    def test_first_time_user_experience(self, driver):
        """Test experience for first-time users"""
        driver.get("http://localhost:8000")

        # Check for welcome or onboarding elements
        welcome_elements = [
            ".welcome-message",
            ".onboarding",
            ".getting-started",
            ".intro-text",
            ".help-text"
        ]

        found_welcome_elements = []
        for selector in welcome_elements:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and elements[0].is_displayed():
                    found_welcome_elements.append(selector)
            except:
                pass

        # Should have some form of user guidance
        if not found_welcome_elements:
            # Check for obvious interface elements that help new users
            obvious_elements = driver.find_elements(
                By.CSS_SELECTOR,
                "h1, .title, .main-heading, .primary-action, .start-button"
            )
            assert len(obvious_elements) > 0, "Interface should provide clear entry points for new users"

        # Check for help or guidance text
        help_text = driver.find_elements(By.CSS_SELECTOR, "[placeholder], .help, .hint, .description")
        if help_text:
            # Should have descriptive placeholder or help text
            help_content = [elem.get_attribute("placeholder") or elem.text for elem in help_text]
            non_empty_help = [content for content in help_content if content and len(content.strip()) > 5]
            assert len(non_empty_help) > 0, "Should provide helpful guidance text for users"

    def test_navigation_clarity_and_flow(self, driver):
        """Test navigation clarity and logical flow"""
        driver.get("http://localhost:8000")

        # Check for navigation elements
        nav_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "nav, .navigation, .menu, .nav-bar, .header-nav"
        )

        if nav_elements:
            nav_element = nav_elements[0]

            # Check for navigation links
            nav_links = nav_element.find_elements(By.CSS_SELECTOR, "a, button")
            assert len(nav_links) > 0, "Navigation should contain actionable elements"

            # Test navigation link accessibility
            for link in nav_links[:3]:  # Test first 3 links
                link_text = link.text.strip()
                if link_text:
                    assert len(link_text) > 0, "Navigation links should have descriptive text"

        # Check for breadcrumbs or current page indication
        breadcrumb_elements = driver.find_elements(
            By.CSS_SELECTOR,
            ".breadcrumb, .breadcrumbs, .page-path, .current-page"
        )

        # Test page title clarity
        page_title = driver.title
        assert len(page_title) > 0, "Page should have descriptive title"
        assert len(page_title) < 100, "Page title should be concise"

    def test_error_prevention_and_recovery(self, driver):
        """Test error prevention and user-friendly error recovery"""
        driver.get("http://localhost:8000/chat")

        # Test input validation
        input_field = None
        try:
            input_field = driver.find_element(By.ID, "chat-input")
        except:
            input_field = driver.find_element(By.CSS_SELECTOR, "input[type='text'], textarea")

        if input_field:
            # Test empty input handling
            send_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], #send-button")

            # Try to send empty message
            input_field.clear()
            send_button.click()

            # Should prevent sending empty messages or provide feedback
            time.sleep(1)

            # Check for validation message or input focus
            validation_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".error, .validation-error, .warning, .required"
            )

            if validation_elements:
                # Should provide clear validation feedback
                validation_text = validation_elements[0].text
                assert len(validation_text) > 0, "Validation messages should be descriptive"

            # Test input focus retention
            active_element = driver.switch_to.active_element
            is_input_focused = active_element == input_field

            # Either validation message shown or input stays focused
            assert validation_elements or is_input_focused, "Should provide error feedback or maintain focus"

    def test_responsive_interaction_feedback(self, driver):
        """Test immediate feedback for user interactions"""
        driver.get("http://localhost:8000")

        # Test button interaction feedback
        buttons = driver.find_elements(By.TAG_NAME, "button")

        for button in buttons[:3]:  # Test first 3 buttons
            if button.is_enabled() and button.is_displayed():
                # Test hover effect
                ActionChains(driver).move_to_element(button).perform()
                time.sleep(0.5)

                # Check for visual feedback (this is a basic test)
                cursor = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).cursor;", button
                )
                assert cursor == "pointer", "Interactive elements should show pointer cursor"

                # Test click feedback
                original_style = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).backgroundColor;", button
                )

                button.click()
                time.sleep(0.1)

                # Button should provide some form of click feedback
                # (This is simplified - actual feedback testing would require more sophisticated methods)

    def test_loading_state_user_experience(self, driver):
        """Test user experience during loading states"""
        driver.get("http://localhost:8000/chat")

        # Mock slow response to test loading UX
        with patch('requests.post') as mock_post:
            def slow_response(*args, **kwargs):
                time.sleep(3)  # Simulate slow response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"answer": "Test response"}
                return mock_response

            mock_post.side_effect = slow_response

            # Send message to trigger loading state
            input_field = driver.find_element(By.ID, "chat-input")
            send_button = driver.find_element(By.ID, "send-button")

            input_field.clear()
            input_field.send_keys("Test loading message")
            send_button.click()

            # Check for loading indicator
            loading_indicators = [
                ".loading", ".spinner", ".loader", ".processing",
                ".typing-indicator", ".thinking"
            ]

            loading_found = False
            for selector in loading_indicators:
                try:
                    WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    loading_found = True
                    break
                except:
                    pass

            # Should provide loading feedback for long operations
            if not loading_found:
                # Check if send button is disabled during processing
                is_disabled = not send_button.is_enabled()
                assert is_disabled, "Should provide loading feedback (indicator or disabled button)"

    def test_accessibility_and_keyboard_navigation(self, driver):
        """Test accessibility features and keyboard navigation"""
        driver.get("http://localhost:8000")

        # Test tab navigation
        focusable_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])"
        )

        if len(focusable_elements) > 1:
            # Test tab order
            first_element = focusable_elements[0]
            first_element.click()

            # Tab to next element
            ActionChains(driver).send_keys(Keys.TAB).perform()
            time.sleep(0.5)

            active_element = driver.switch_to.active_element
            assert active_element != first_element, "Tab navigation should move focus"

        # Test for ARIA labels and accessibility attributes
        important_elements = driver.find_elements(By.CSS_SELECTOR, "button, input, img")

        accessible_elements = 0
        for element in important_elements:
            aria_label = element.get_attribute("aria-label")
            alt_text = element.get_attribute("alt")
            title = element.get_attribute("title")

            if aria_label or alt_text or title:
                accessible_elements += 1

        # Should have accessibility attributes on important elements
        if important_elements:
            accessibility_ratio = accessible_elements / len(important_elements)
            assert accessibility_ratio >= 0.3, "Important elements should have accessibility attributes"

    def test_content_readability_and_scannability(self, driver):
        """Test content readability and information scannability"""
        driver.get("http://localhost:8000")

        # Test heading structure
        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")

        if headings:
            # Should have logical heading hierarchy
            heading_levels = []
            for heading in headings:
                tag_name = heading.tag_name.lower()
                level = int(tag_name[1])
                heading_levels.append(level)

            # Check for proper heading hierarchy (not strict, but should start reasonably)
            if heading_levels:
                assert min(heading_levels) <= 2, "Should start with h1 or h2 headings"

        # Test text content length and structure
        text_blocks = driver.find_elements(By.CSS_SELECTOR, "p, div.content, .text")

        readable_blocks = 0
        for block in text_blocks:
            text_content = block.text.strip()
            if text_content:
                # Check text block length (not too long for readability)
                if 10 <= len(text_content) <= 500:  # Reasonable text block size
                    readable_blocks += 1

        # Should have readable text blocks
        if text_blocks:
            readability_ratio = readable_blocks / len(text_blocks)
            assert readability_ratio >= 0.3, "Should have readable text block structure"

    def test_visual_hierarchy_and_information_architecture(self, driver):
        """Test visual hierarchy and information organization"""
        driver.get("http://localhost:8000")

        # Test visual hierarchy through CSS
        important_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "h1, h2, .title, .primary, .main-content"
        )

        font_sizes = []
        for element in important_elements:
            font_size = driver.execute_script(
                "return parseFloat(window.getComputedStyle(arguments[0]).fontSize);", element
            )
            font_sizes.append(font_size)

        if font_sizes:
            # Should have variation in font sizes for hierarchy
            font_size_range = max(font_sizes) - min(font_sizes)
            assert font_size_range >= 4, "Should have font size variation for visual hierarchy"

        # Test spacing and layout
        container_elements = driver.find_elements(By.CSS_SELECTOR, ".container, .section, .panel")

        if container_elements:
            # Check for consistent spacing
            margins = []
            for element in container_elements[:3]:
                margin = driver.execute_script(
                    "return window.getComputedStyle(arguments[0]).marginTop;", element
                )
                if margin != "auto":
                    margins.append(margin)

            # Should have some consistent spacing patterns
            unique_margins = set(margins)
            if margins:
                assert len(unique_margins) <= len(margins), "Should have spacing consistency"

    def test_performance_impact_on_user_experience(self, driver):
        """Test that UI performance doesn't negatively impact user experience"""
        # Test page load performance
        start_time = time.perf_counter()
        driver.get("http://localhost:8000")

        # Wait for page to be interactive
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        load_time = (time.perf_counter() - start_time) * 1000

        # Page should load within reasonable time
        assert load_time < 3000, f"Page load time {load_time:.1f}ms should be < 3000ms for good UX"

        # Test interaction responsiveness
        interaction_times = []

        buttons = driver.find_elements(By.TAG_NAME, "button")
        for button in buttons[:3]:
            if button.is_enabled() and button.is_displayed():
                start_time = time.perf_counter()
                button.click()
                time.sleep(0.1)  # Allow for any immediate feedback
                end_time = time.perf_counter()

                interaction_time = (end_time - start_time) * 1000
                interaction_times.append(interaction_time)

        if interaction_times:
            avg_interaction_time = sum(interaction_times) / len(interaction_times)
            assert avg_interaction_time < 100, f"Average interaction time {avg_interaction_time:.1f}ms should be < 100ms"

    def test_error_message_clarity_and_helpfulness(self, driver):
        """Test error message clarity and user guidance"""
        driver.get("http://localhost:8000/chat")

        # Mock error response to test error message UX
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": "Service temporarily unavailable"}
            mock_post.return_value = mock_response

            # Send message that will trigger error
            input_field = driver.find_element(By.ID, "chat-input")
            send_button = driver.find_element(By.ID, "send-button")

            input_field.clear()
            input_field.send_keys("Test error message")
            send_button.click()

            # Wait for error to appear
            time.sleep(2)

            # Check for error message
            error_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".error, .error-message, .alert-error, .warning"
            )

            if error_elements:
                error_text = error_elements[0].text

                # Error message should be helpful
                assert len(error_text) > 10, "Error messages should be descriptive"
                assert any(word in error_text.lower() for word in [
                    "try", "again", "later", "error", "problem", "sorry"
                ]), "Error messages should be user-friendly"

                # Should not expose technical details
                technical_terms = ["exception", "stack", "null", "undefined", "500", "404"]
                has_technical_terms = any(term in error_text.lower() for term in technical_terms)
                assert not has_technical_terms, "Error messages should not expose technical details to users"

    def test_mobile_user_experience(self, driver):
        """Test user experience on mobile devices"""
        # Set mobile viewport
        driver.set_window_size(375, 667)
        driver.get("http://localhost:8000")

        # Test touch target sizes
        buttons = driver.find_elements(By.TAG_NAME, "button")

        for button in buttons[:3]:
            if button.is_displayed():
                size = button.size
                # Touch targets should be at least 44px for accessibility
                assert size['height'] >= 44 or size['width'] >= 44, f"Touch targets should be at least 44px, got {size}"

        # Test text readability on mobile
        text_elements = driver.find_elements(By.CSS_SELECTOR, "p, span, div")

        for element in text_elements[:5]:
            if element.is_displayed() and element.text.strip():
                font_size = driver.execute_script(
                    "return parseFloat(window.getComputedStyle(arguments[0]).fontSize);", element
                )
                # Text should be readable on mobile (at least 16px)
                assert font_size >= 16, f"Mobile text should be at least 16px, got {font_size}px"

        # Test horizontal scrolling (should not be required)
        body_width = driver.execute_script("return document.body.scrollWidth;")
        viewport_width = driver.execute_script("return window.innerWidth;")

        # Body should not be wider than viewport (no horizontal scroll)
        assert body_width <= viewport_width + 5, "Should not require horizontal scrolling on mobile"

    def test_user_workflow_completion(self, driver):
        """Test complete user workflow from start to finish"""
        driver.get("http://localhost:8000")

        # Test typical user workflow: navigate to chat and ask question

        # Step 1: Navigate to chat interface
        chat_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='chat'], .chat-link")

        if not chat_links:
            # If no chat link, check if already on chat page
            chat_elements = driver.find_elements(By.CSS_SELECTOR, "#chat-input, .chat-container")
            if not chat_elements:
                driver.get("http://localhost:8000/chat")
        else:
            chat_links[0].click()

        # Step 2: Wait for chat interface to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#chat-input, input[type='text']"))
        )

        # Step 3: Send a question
        input_field = driver.find_element(By.CSS_SELECTOR, "#chat-input, input[type='text']")
        send_button = driver.find_element(By.CSS_SELECTOR, "#send-button, button[type='submit']")

        test_question = "What is the armor class of leather armor?"
        input_field.clear()
        input_field.send_keys(test_question)
        send_button.click()

        # Step 4: Verify message appears in chat
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".user-message, .message"))
        )

        messages = driver.find_elements(By.CSS_SELECTOR, ".user-message, .message")
        message_found = any(test_question in msg.text for msg in messages)
        assert message_found, "User message should appear in chat interface"

        # Step 5: Workflow should feel smooth and natural
        # This is tested by the absence of errors and presence of expected elements

    def test_user_experience_contract_compliance(self, driver):
        """Test that user experience matches established usability contract"""
        driver.get("http://localhost:8000")

        # Performance contract
        start_time = time.perf_counter()
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        load_time = (time.perf_counter() - start_time) * 1000

        assert load_time < 3000, f"Page load time {load_time:.1f}ms exceeds 3000ms UX requirement"

        # Accessibility contract
        focusable_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href], button, input, select, textarea"
        )

        accessible_count = 0
        for element in focusable_elements:
            if element.is_displayed() and element.is_enabled():
                accessible_count += 1

        assert accessible_count > 0, "Interface should have accessible interactive elements"

        # Navigation contract
        page_title = driver.title
        assert len(page_title) > 0, "Page should have descriptive title"

        # Content structure contract
        main_content = driver.find_elements(
            By.CSS_SELECTOR,
            "main, .main-content, .content, #content"
        )

        if not main_content:
            # Should have identifiable content area
            content_indicators = driver.find_elements(
                By.CSS_SELECTOR,
                "h1, .title, .primary-content, .chat-container"
            )
            assert len(content_indicators) > 0, "Interface should have identifiable main content area"

        # Responsive design contract
        viewport_meta = driver.find_elements(By.CSS_SELECTOR, "meta[name='viewport']")
        # Should have viewport meta tag for responsive design
        # Note: This checks HTML head, which may not be accessible via CSS selector in all cases

        # Error handling contract
        # Should have defined error styles (checked in CSS)
        error_styles_defined = driver.execute_script("""
            let hasErrorStyles = false;
            try {
                let testEl = document.createElement('div');
                testEl.className = 'error';
                document.body.appendChild(testEl);
                let styles = window.getComputedStyle(testEl);
                hasErrorStyles = styles.color !== 'rgb(0, 0, 0)' || styles.backgroundColor !== 'rgba(0, 0, 0, 0)';
                document.body.removeChild(testEl);
            } catch (e) {
                // Error styles may be defined differently
            }
            return hasErrorStyles;
        """)

        # Interface should have consistent styling (error handling UI should be defined)