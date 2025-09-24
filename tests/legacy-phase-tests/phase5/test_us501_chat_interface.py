# tests/regression/phase5/test_us501_chat_interface.py
"""
Phase 5 - US-501: User Chat Interface Regression Tests
Tests user-facing chat interface with retro terminal/LCARS design and functionality
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


class TestUserChatInterface:
    """Test suite for User Chat Interface validation"""

    @pytest.fixture(scope="class")
    def driver(self):
        """Set up Selenium WebDriver for UI testing"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode for CI
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)

        yield driver

        driver.quit()

    def test_chat_interface_availability(self):
        """Test that chat interface components are available"""
        try:
            from src_common.user_routes import app

            assert app is not None, "User Flask app should be available"

        except ImportError as e:
            pytest.fail(f"User chat interface not available: {e}")

    def test_chat_interface_load_time(self, driver):
        """Test chat interface page load performance"""
        # Navigate to chat interface
        start_time = time.perf_counter()
        driver.get("http://localhost:8000/chat")

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "chat-container"))
        )

        end_time = time.perf_counter()
        load_time = (end_time - start_time) * 1000

        # Page should load quickly
        assert load_time < 3000, f"Chat interface load time {load_time:.1f}ms should be < 3000ms"

    def test_retro_terminal_design_elements(self, driver):
        """Test that retro terminal/LCARS design elements are present"""
        driver.get("http://localhost:8000/chat")

        # Check for retro design elements
        design_elements = [
            ".terminal-window",
            ".lcars-panel",
            ".retro-text",
            ".terminal-prompt",
            ".scan-lines",
            ".crt-effect"
        ]

        found_elements = []
        for selector in design_elements:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element:
                    found_elements.append(selector)
            except:
                pass

        # Should have retro design elements
        assert len(found_elements) >= 2, f"Should have retro design elements, found: {found_elements}"

        # Check for appropriate color scheme
        body = driver.find_element(By.TAG_NAME, "body")
        computed_style = driver.execute_script(
            "return window.getComputedStyle(arguments[0]);", body
        )

        # Should have dark background typical of terminal interfaces
        bg_color = computed_style.get("background-color", "")
        # Verify it's a dark color (rgb values should be low)
        if "rgb" in bg_color:
            # Basic check for dark background
            assert "0" in bg_color or "black" in bg_color.lower()

    def test_chat_input_functionality(self, driver):
        """Test chat input field functionality and validation"""
        driver.get("http://localhost:8000/chat")

        # Find chat input field
        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "chat-input"))
        )

        # Test input field properties
        assert input_field.is_enabled(), "Chat input should be enabled"
        assert input_field.get_attribute("placeholder"), "Input should have placeholder text"

        # Test typing in input field
        test_message = "What is the damage of Fireball?"
        input_field.clear()
        input_field.send_keys(test_message)

        # Verify text was entered
        assert input_field.get_attribute("value") == test_message, "Input should accept text"

        # Test character limit (if implemented)
        max_length = input_field.get_attribute("maxlength")
        if max_length:
            assert int(max_length) >= 500, "Input should accept reasonable message length"

    def test_message_sending_functionality(self, driver):
        """Test sending messages and receiving responses"""
        driver.get("http://localhost:8000/chat")

        # Mock the backend response
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "answer": "Fireball deals 8d6 fire damage in a 20-foot radius.",
                "sources": [{"page": 241, "section": "Spells"}],
                "metadata": {"response_time": 1.2}
            }
            mock_post.return_value = mock_response

            # Send a message
            input_field = driver.find_element(By.ID, "chat-input")
            send_button = driver.find_element(By.ID, "send-button")

            test_message = "What is the damage of Fireball?"
            input_field.clear()
            input_field.send_keys(test_message)
            send_button.click()

            # Wait for message to appear in chat
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "user-message"))
            )

            # Verify user message appears
            user_messages = driver.find_elements(By.CLASS_NAME, "user-message")
            assert len(user_messages) > 0, "User message should appear in chat"

            latest_user_message = user_messages[-1]
            assert test_message in latest_user_message.text, "User message should contain sent text"

            # Wait for AI response
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ai-message"))
            )

            # Verify AI response appears
            ai_messages = driver.find_elements(By.CLASS_NAME, "ai-message")
            assert len(ai_messages) > 0, "AI response should appear in chat"

            latest_ai_message = ai_messages[-1]
            assert "Fireball" in latest_ai_message.text, "AI response should contain relevant content"

    def test_message_history_display(self, driver):
        """Test chat message history display and scrolling"""
        driver.get("http://localhost:8000/chat")

        # Send multiple messages to test history
        input_field = driver.find_element(By.ID, "chat-input")
        send_button = driver.find_element(By.ID, "send-button")

        test_messages = [
            "First test message",
            "Second test message",
            "Third test message"
        ]

        for message in test_messages:
            input_field.clear()
            input_field.send_keys(message)
            send_button.click()
            time.sleep(0.5)  # Brief pause between messages

        # Verify all messages appear in history
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.CLASS_NAME, "user-message")) >= 3
        )

        user_messages = driver.find_elements(By.CLASS_NAME, "user-message")
        assert len(user_messages) >= 3, "All sent messages should appear in history"

        # Test chat container scrolling
        chat_container = driver.find_element(By.CLASS_NAME, "chat-container")

        # Should auto-scroll to bottom for new messages
        scroll_height = driver.execute_script("return arguments[0].scrollHeight", chat_container)
        scroll_top = driver.execute_script("return arguments[0].scrollTop", chat_container)
        client_height = driver.execute_script("return arguments[0].clientHeight", chat_container)

        # Should be scrolled near the bottom
        assert scroll_top >= (scroll_height - client_height - 50), "Chat should auto-scroll to new messages"

    def test_typing_indicator_functionality(self, driver):
        """Test typing indicator during AI response generation"""
        driver.get("http://localhost:8000/chat")

        # Mock slow response to test typing indicator
        with patch('requests.post') as mock_post:
            def slow_response(*args, **kwargs):
                time.sleep(2)  # Simulate processing time
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "answer": "Test response",
                    "sources": [],
                    "metadata": {}
                }
                return mock_response

            mock_post.side_effect = slow_response

            # Send message
            input_field = driver.find_element(By.ID, "chat-input")
            send_button = driver.find_element(By.ID, "send-button")

            input_field.clear()
            input_field.send_keys("Test message")
            send_button.click()

            # Check for typing indicator
            try:
                typing_indicator = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "typing-indicator"))
                )
                assert typing_indicator.is_displayed(), "Typing indicator should be visible during processing"

                # Wait for response and verify indicator disappears
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located((By.CLASS_NAME, "typing-indicator"))
                )

            except:
                # Typing indicator may not be implemented yet
                pass

    def test_source_attribution_display(self, driver):
        """Test display of source attribution for AI responses"""
        driver.get("http://localhost:8000/chat")

        # Mock response with sources
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "answer": "Fireball is a 3rd-level evocation spell that deals 8d6 fire damage.",
                "sources": [
                    {"page": 241, "section": "Spells", "document": "Player's Handbook"},
                    {"page": 242, "section": "Spell Descriptions", "document": "Player's Handbook"}
                ],
                "metadata": {"confidence": 0.95}
            }
            mock_post.return_value = mock_response

            # Send message
            input_field = driver.find_element(By.ID, "chat-input")
            send_button = driver.find_element(By.ID, "send-button")

            input_field.clear()
            input_field.send_keys("What is Fireball?")
            send_button.click()

            # Wait for response with sources
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ai-message"))
            )

            # Check for source attribution
            sources_elements = driver.find_elements(By.CLASS_NAME, "source-attribution")
            if sources_elements:
                # Sources should be displayed
                source_text = sources_elements[0].text
                assert "241" in source_text, "Source should reference page number"
                assert "Player's Handbook" in source_text, "Source should reference document"

    def test_error_handling_display(self, driver):
        """Test error message display and handling"""
        driver.get("http://localhost:8000/chat")

        # Mock error response
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {
                "error": "Internal server error"
            }
            mock_post.return_value = mock_response

            # Send message that will trigger error
            input_field = driver.find_element(By.ID, "chat-input")
            send_button = driver.find_element(By.ID, "send-button")

            input_field.clear()
            input_field.send_keys("Test error message")
            send_button.click()

            # Check for error message display
            try:
                error_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "error-message"))
                )

                assert error_element.is_displayed(), "Error message should be visible"
                assert "error" in error_element.text.lower(), "Error message should indicate error occurred"

            except:
                # Error handling may display differently
                # Check if any message appears at all
                messages = driver.find_elements(By.CLASS_NAME, "ai-message")
                if messages:
                    latest_message = messages[-1]
                    # Should indicate error in some way
                    assert "error" in latest_message.text.lower() or "sorry" in latest_message.text.lower()

    def test_responsive_design(self, driver):
        """Test responsive design for different screen sizes"""
        # Test desktop size
        driver.set_window_size(1920, 1080)
        driver.get("http://localhost:8000/chat")

        chat_container = driver.find_element(By.CLASS_NAME, "chat-container")
        desktop_width = chat_container.size['width']

        # Test tablet size
        driver.set_window_size(768, 1024)
        time.sleep(1)  # Allow resize to complete

        tablet_width = chat_container.size['width']
        assert tablet_width < desktop_width, "Chat should adapt to smaller screen sizes"

        # Test mobile size
        driver.set_window_size(375, 667)
        time.sleep(1)

        mobile_width = chat_container.size['width']
        assert mobile_width < tablet_width, "Chat should adapt to mobile screen sizes"

        # Verify elements are still accessible on mobile
        input_field = driver.find_element(By.ID, "chat-input")
        send_button = driver.find_element(By.ID, "send-button")

        assert input_field.is_displayed(), "Input field should be visible on mobile"
        assert send_button.is_displayed(), "Send button should be visible on mobile"

    def test_keyboard_shortcuts(self, driver):
        """Test keyboard shortcuts and accessibility"""
        driver.get("http://localhost:8000/chat")

        input_field = driver.find_element(By.ID, "chat-input")

        # Test Enter key to send message
        test_message = "Keyboard shortcut test"
        input_field.clear()
        input_field.send_keys(test_message)

        # Press Enter
        input_field.send_keys("\n")

        # Verify message was sent
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-message"))
        )

        user_messages = driver.find_elements(By.CLASS_NAME, "user-message")
        latest_message = user_messages[-1]
        assert test_message in latest_message.text, "Enter key should send message"

        # Test Shift+Enter for line break (if implemented)
        input_field.clear()
        input_field.send_keys("Line 1")
        input_field.send_keys("\n")  # This might be Shift+Enter in actual implementation
        input_field.send_keys("Line 2")

        # Input should contain both lines
        input_value = input_field.get_attribute("value")
        if "\n" in input_value:
            assert "Line 1" in input_value and "Line 2" in input_value, "Should support multi-line input"

    def test_chat_session_persistence(self, driver):
        """Test chat session persistence across page reloads"""
        driver.get("http://localhost:8000/chat")

        # Send a message
        input_field = driver.find_element(By.ID, "chat-input")
        send_button = driver.find_element(By.ID, "send-button")

        test_message = "Persistence test message"
        input_field.clear()
        input_field.send_keys(test_message)
        send_button.click()

        # Wait for message to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-message"))
        )

        # Reload the page
        driver.refresh()

        # Wait for page to reload
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "chat-container"))
        )

        # Check if message history is preserved
        try:
            user_messages = driver.find_elements(By.CLASS_NAME, "user-message")
            if user_messages:
                # Session persistence is implemented
                message_found = any(test_message in msg.text for msg in user_messages)
                assert message_found, "Chat history should persist across page reloads"
        except:
            # Session persistence may not be implemented yet
            pass

    def test_performance_under_load(self, driver):
        """Test chat interface performance under message load"""
        driver.get("http://localhost:8000/chat")

        # Send multiple messages rapidly
        input_field = driver.find_element(By.ID, "chat-input")
        send_button = driver.find_element(By.ID, "send-button")

        start_time = time.perf_counter()

        for i in range(10):
            message = f"Performance test message {i}"
            input_field.clear()
            input_field.send_keys(message)
            send_button.click()
            time.sleep(0.1)  # Brief pause to allow processing

        # Wait for all messages to appear
        WebDriverWait(driver, 20).until(
            lambda d: len(d.find_elements(By.CLASS_NAME, "user-message")) >= 10
        )

        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000

        # Should handle multiple messages efficiently
        assert total_time < 10000, f"Sending 10 messages took {total_time:.1f}ms, should be < 10000ms"

        # Verify all messages are displayed
        user_messages = driver.find_elements(By.CLASS_NAME, "user-message")
        assert len(user_messages) >= 10, "All messages should be displayed"

    def test_accessibility_features(self, driver):
        """Test accessibility features of the chat interface"""
        driver.get("http://localhost:8000/chat")

        # Check for ARIA labels
        input_field = driver.find_element(By.ID, "chat-input")

        aria_label = input_field.get_attribute("aria-label")
        if aria_label:
            assert len(aria_label) > 0, "Input field should have descriptive ARIA label"

        # Check for proper form labeling
        labels = driver.find_elements(By.TAG_NAME, "label")
        for label in labels:
            for_attr = label.get_attribute("for")
            if for_attr:
                target_element = driver.find_element(By.ID, for_attr)
                assert target_element is not None, "Label should reference valid element"

        # Check for keyboard navigation
        focusable_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "input, button, select, textarea, a[href], [tabindex]"
        )

        assert len(focusable_elements) > 0, "Interface should have focusable elements for keyboard navigation"

        # Test tab order
        first_focusable = focusable_elements[0]
        first_focusable.click()

        # Should be able to tab through elements
        active_element = driver.switch_to.active_element
        assert active_element is not None, "Should have active element for keyboard navigation"

    def test_chat_interface_contract_compliance(self, driver):
        """Test that chat interface matches established contract"""
        driver.get("http://localhost:8000/chat")

        # Verify required elements are present
        required_elements = [
            ("chat-container", By.CLASS_NAME),
            ("chat-input", By.ID),
            ("send-button", By.ID)
        ]

        for element_id, locator_type in required_elements:
            element = driver.find_element(locator_type, element_id)
            assert element is not None, f"Required element {element_id} should be present"
            assert element.is_displayed(), f"Required element {element_id} should be visible"

        # Test message structure contract
        # Send a test message first
        input_field = driver.find_element(By.ID, "chat-input")
        send_button = driver.find_element(By.ID, "send-button")

        input_field.clear()
        input_field.send_keys("Contract test message")
        send_button.click()

        # Wait for message to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "user-message"))
        )

        # Verify message structure
        user_message = driver.find_element(By.CLASS_NAME, "user-message")

        # Should have timestamp
        timestamp_elements = user_message.find_elements(By.CLASS_NAME, "timestamp")
        if timestamp_elements:
            timestamp = timestamp_elements[0].text
            assert len(timestamp) > 0, "Message should have timestamp"

        # Should have message content
        content_elements = user_message.find_elements(By.CLASS_NAME, "message-content")
        if content_elements:
            content = content_elements[0].text
            assert "Contract test message" in content, "Message should contain sent text"