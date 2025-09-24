# tests/regression/phase0/test_log001_structured.py
"""
Phase 0 - US LOG-001: Structured JSON Logging Regression Tests
Tests the structured JSON logging utility functionality
"""

import json
import pytest
import os
import sys
import time
import tempfile
from pathlib import Path
from io import StringIO


class TestStructuredLogging:
    """Test suite for structured JSON logging validation"""

    def test_jlog_basic_functionality(self):
        """Test that jlog function produces valid JSON output"""
        # Import the logging module
        try:
            from src_common.logging import jlog
        except ImportError:
            # Fallback if module structure is different
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Test basic logging
            jlog("INFO", "test message")

            # Get the output
            output = captured_output.getvalue().strip()

            # Verify it's valid JSON
            log_entry = json.loads(output)

            # Verify required fields
            assert "ts" in log_entry, "Log entry missing timestamp field"
            assert "level" in log_entry, "Log entry missing level field"
            assert "msg" in log_entry, "Log entry missing message field"
            assert "env" in log_entry, "Log entry missing environment field"

            # Verify field values
            assert log_entry["level"] == "INFO", f"Expected level INFO, got {log_entry['level']}"
            assert log_entry["msg"] == "test message", f"Expected message 'test message', got '{log_entry['msg']}'"
            assert isinstance(log_entry["ts"], (int, float)), "Timestamp should be numeric"

        finally:
            sys.stdout = old_stdout

    def test_jlog_with_additional_fields(self):
        """Test that jlog accepts and includes additional fields"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Test logging with additional fields
            jlog("ERROR", "test error", step="validation", code=500, success=False)

            output = captured_output.getvalue().strip()
            log_entry = json.loads(output)

            # Verify base fields
            assert log_entry["level"] == "ERROR"
            assert log_entry["msg"] == "test error"

            # Verify additional fields
            assert log_entry["step"] == "validation"
            assert log_entry["code"] == 500
            assert log_entry["success"] is False

        finally:
            sys.stdout = old_stdout

    def test_jlog_environment_context(self):
        """Test that jlog includes correct environment context"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        current_env = os.getenv("ENV", "dev")

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            jlog("DEBUG", "environment test")

            output = captured_output.getvalue().strip()
            log_entry = json.loads(output)

            # Verify environment is correctly captured
            assert log_entry["env"] == current_env, f"Expected env '{current_env}', got '{log_entry['env']}'"

        finally:
            sys.stdout = old_stdout

    def test_jlog_timestamp_format(self):
        """Test that jlog produces valid timestamps"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            before_time = time.time()
            jlog("INFO", "timestamp test")
            after_time = time.time()

            output = captured_output.getvalue().strip()
            log_entry = json.loads(output)

            timestamp = log_entry["ts"]

            # Verify timestamp is within reasonable range
            assert isinstance(timestamp, (int, float)), "Timestamp should be numeric"
            assert before_time <= timestamp <= after_time, "Timestamp should be between before and after times"

            # Verify timestamp precision (should have decimal places for sub-second precision)
            if isinstance(timestamp, float):
                assert timestamp != int(timestamp), "Timestamp should have sub-second precision"

        finally:
            sys.stdout = old_stdout

    def test_jlog_security_no_secrets_leak(self):
        """Test that jlog does not inadvertently include secrets in logs"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Set up environment with mock secrets
        original_api_key = os.environ.get("API_KEY")
        original_secret_key = os.environ.get("SECRET_KEY")

        try:
            os.environ["API_KEY"] = "sk-test-secret-key-123"
            os.environ["SECRET_KEY"] = "super-secret-password"

            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()

            try:
                # Log a message without explicitly passing secrets
                jlog("INFO", "processing request", user_id="user123", action="login")

                output = captured_output.getvalue().strip()
                log_entry = json.loads(output)

                # Verify secrets are not automatically included
                assert "API_KEY" not in str(log_entry), "API_KEY should not appear in log output"
                assert "SECRET_KEY" not in str(log_entry), "SECRET_KEY should not appear in log output"
                assert "sk-test-secret-key-123" not in str(log_entry), "Secret value should not appear in log output"
                assert "super-secret-password" not in str(log_entry), "Secret value should not appear in log output"

                # Verify that explicitly passed fields are included
                assert log_entry["user_id"] == "user123"
                assert log_entry["action"] == "login"

            finally:
                sys.stdout = old_stdout

        finally:
            # Restore original environment
            if original_api_key is not None:
                os.environ["API_KEY"] = original_api_key
            elif "API_KEY" in os.environ:
                del os.environ["API_KEY"]

            if original_secret_key is not None:
                os.environ["SECRET_KEY"] = original_secret_key
            elif "SECRET_KEY" in os.environ:
                del os.environ["SECRET_KEY"]

    def test_jlog_multiple_calls_valid_json(self):
        """Test that multiple jlog calls each produce valid JSON lines"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Multiple log calls
            jlog("INFO", "first message", seq=1)
            jlog("WARNING", "second message", seq=2)
            jlog("ERROR", "third message", seq=3)

            output = captured_output.getvalue().strip()
            lines = output.split('\n')

            # Should have exactly 3 lines
            assert len(lines) == 3, f"Expected 3 log lines, got {len(lines)}"

            # Each line should be valid JSON
            for i, line in enumerate(lines, 1):
                try:
                    log_entry = json.loads(line)
                    assert log_entry["seq"] == i, f"Line {i} should have seq={i}"
                except json.JSONDecodeError:
                    pytest.fail(f"Line {i} is not valid JSON: {line}")

        finally:
            sys.stdout = old_stdout

    def test_jlog_error_handling(self):
        """Test that jlog handles edge cases gracefully"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Test with empty message
            jlog("INFO", "")

            # Test with None values
            jlog("DEBUG", "test with none", none_field=None)

            # Test with complex data types
            jlog("INFO", "complex data", data={"key": "value", "list": [1, 2, 3]})

            output = captured_output.getvalue().strip()
            lines = output.split('\n')

            # All lines should be valid JSON
            for line in lines:
                try:
                    log_entry = json.loads(line)
                    assert "level" in log_entry
                    assert "msg" in log_entry
                    assert "ts" in log_entry
                    assert "env" in log_entry
                except json.JSONDecodeError:
                    pytest.fail(f"Invalid JSON line: {line}")

        finally:
            sys.stdout = old_stdout

    def test_jlog_unicode_handling(self):
        """Test that jlog handles Unicode characters correctly"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Test with Unicode characters
            unicode_message = "Unicode test: 🎲 ⚔️ 🏰 café naïve résumé"
            jlog("INFO", unicode_message, unicode_field="测试")

            output = captured_output.getvalue().strip()
            log_entry = json.loads(output)

            # Verify Unicode is preserved
            assert log_entry["msg"] == unicode_message
            assert log_entry["unicode_field"] == "测试"

        finally:
            sys.stdout = old_stdout

    def test_jlog_performance_baseline(self):
        """Test that jlog performs within acceptable time limits"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout to null to avoid I/O overhead in timing
        old_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

        try:
            # Time multiple log calls
            start_time = time.time()

            for i in range(100):
                jlog("INFO", f"performance test {i}", iteration=i, batch="performance")

            end_time = time.time()
            total_time = end_time - start_time

            # 100 log calls should complete in under 1 second
            assert total_time < 1.0, f"100 log calls took {total_time:.3f}s, expected < 1.0s"

        finally:
            sys.stdout.close()
            sys.stdout = old_stdout

    def test_jlog_contract_stability(self):
        """Test that jlog output format matches the established contract"""
        try:
            from src_common.logging import jlog
        except ImportError:
            sys.path.append(str(Path(__file__).parent.parent.parent.parent / "src_common"))
            from logging import jlog

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Test the Phase 0 contract: jlog should produce JSON with ts, level, msg, env
            jlog("INFO", "contract test", test_field="test_value")

            output = captured_output.getvalue().strip()
            log_entry = json.loads(output)

            # Verify contract-required fields
            contract_fields = ["ts", "level", "msg", "env"]
            for field in contract_fields:
                assert field in log_entry, f"Contract violation: missing required field '{field}'"

            # Verify field types
            assert isinstance(log_entry["ts"], (int, float)), "ts field should be numeric"
            assert isinstance(log_entry["level"], str), "level field should be string"
            assert isinstance(log_entry["msg"], str), "msg field should be string"
            assert isinstance(log_entry["env"], str), "env field should be string"

            # Verify additional fields are preserved
            assert log_entry["test_field"] == "test_value", "Additional fields should be preserved"

        finally:
            sys.stdout = old_stdout