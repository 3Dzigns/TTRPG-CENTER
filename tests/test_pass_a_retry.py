#!/usr/bin/env python3
"""
Unit tests for pass_a_unstructured.py retry logic.

Tests the exponential backoff retry mechanism for handling
Unstructured API timeouts on large documents.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

from pass_a_unstructured import (
    process_document_with_retry,
    UnstructuredProcessorError
)


def test_retry_config_values():
    """Test that retry configuration values are correctly applied."""
    from config import IngestionConfig

    # Verify config defaults
    assert IngestionConfig.UNSTRUCTURED_TIMEOUT == 900, "Default timeout should be 900s (15 minutes)"
    assert IngestionConfig.UNSTRUCTURED_MAX_RETRIES == 3, "Default max retries should be 3"
    assert IngestionConfig.UNSTRUCTURED_RETRY_BACKOFF == 2.0, "Default backoff multiplier should be 2.0"
    assert IngestionConfig.UNSTRUCTURED_INITIAL_WAIT == 30, "Default initial wait should be 30s"

    print("[PASS] test_retry_config_values")


def test_successful_first_attempt():
    """Test successful processing on first attempt (no retries needed)."""
    import tempfile
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock document
        doc_path = Path(tmpdir) / "test.pdf"
        doc_path.write_bytes(b"fake pdf content")

        output_dir = Path(tmpdir) / "output"

        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {"type": "Title", "text": "Test Title"},
            {"type": "Text", "text": "Test content"}
        ]
        mock_response.status_code = 200

        with patch('pass_a_unstructured.requests.post', return_value=mock_response):
            with patch('pass_a_unstructured.check_unstructured_health', return_value=True):
                result = process_document_with_retry(
                    document_path=doc_path,
                    output_dir=output_dir,
                    strategy="hi_res",
                    timeout=60,
                    max_retries=3
                )

        assert result['element_count'] == 2
        assert Path(result['output_file']).exists()

    print("[PASS] test_successful_first_attempt")


def test_retry_on_timeout():
    """Test retry mechanism with exponential backoff on timeout."""
    import tempfile
    import requests

    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "test.pdf"
        doc_path.write_bytes(b"fake pdf content")
        output_dir = Path(tmpdir) / "output"

        # Mock: First attempt times out, second succeeds
        call_count = {'value': 0}

        def mock_post(*args, **kwargs):
            call_count['value'] += 1
            if call_count['value'] == 1:
                raise requests.Timeout("Read timed out")
            else:
                mock_response = Mock()
                mock_response.json.return_value = [{"type": "Title", "text": "Success"}]
                mock_response.status_code = 200
                return mock_response

        # Track sleep calls to verify exponential backoff
        sleep_times = []

        def mock_sleep(seconds):
            sleep_times.append(seconds)

        with patch('pass_a_unstructured.requests.post', side_effect=mock_post):
            with patch('pass_a_unstructured.check_unstructured_health', return_value=True):
                with patch('pass_a_unstructured.time.sleep', side_effect=mock_sleep):
                    result = process_document_with_retry(
                        document_path=doc_path,
                        output_dir=output_dir,
                        strategy="hi_res",
                        timeout=60,
                        max_retries=3
                    )

        # Verify retry happened
        assert call_count['value'] == 2, "Should have made 2 attempts (1 timeout + 1 success)"

        # Verify exponential backoff (30s * 2.0^0 = 30s for first retry)
        assert len(sleep_times) == 1, "Should have slept once between retries"
        assert sleep_times[0] == 30, f"First retry wait should be 30s, got {sleep_times[0]}s"

        # Verify success
        assert result['element_count'] == 1

    print("[PASS] test_retry_on_timeout")


def test_exponential_backoff_calculation():
    """Test exponential backoff timing calculations."""
    import tempfile
    import requests

    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "test.pdf"
        doc_path.write_bytes(b"fake pdf content")
        output_dir = Path(tmpdir) / "output"

        # Mock: All attempts timeout
        def mock_post(*args, **kwargs):
            raise requests.Timeout("Read timed out")

        sleep_times = []

        def mock_sleep(seconds):
            sleep_times.append(seconds)

        with patch('pass_a_unstructured.requests.post', side_effect=mock_post):
            with patch('pass_a_unstructured.check_unstructured_health', return_value=True):
                with patch('pass_a_unstructured.time.sleep', side_effect=mock_sleep):
                    try:
                        process_document_with_retry(
                            document_path=doc_path,
                            output_dir=output_dir,
                            strategy="hi_res",
                            timeout=60,
                            max_retries=3
                        )
                    except UnstructuredProcessorError:
                        pass  # Expected after all retries exhausted

        # Verify exponential backoff: 30s * 2^0, 30s * 2^1
        # (max_retries=3 means 3 attempts, so 2 waits between attempts)
        assert len(sleep_times) == 2, "Should have 2 sleep calls for 3 attempts"
        assert sleep_times[0] == 30, f"First wait: 30s * 2^0 = 30s, got {sleep_times[0]}s"
        assert sleep_times[1] == 60, f"Second wait: 30s * 2^1 = 60s, got {sleep_times[1]}s"

    print("[PASS] test_exponential_backoff_calculation")


def test_all_retries_exhausted():
    """Test that error is raised after all retries are exhausted."""
    import tempfile
    import requests

    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "test.pdf"
        doc_path.write_bytes(b"fake pdf content")
        output_dir = Path(tmpdir) / "output"

        # Mock: All attempts timeout
        def mock_post(*args, **kwargs):
            raise requests.Timeout("Read timed out")

        with patch('pass_a_unstructured.requests.post', side_effect=mock_post):
            with patch('pass_a_unstructured.check_unstructured_health', return_value=True):
                with patch('pass_a_unstructured.time.sleep'):
                    try:
                        process_document_with_retry(
                            document_path=doc_path,
                            output_dir=output_dir,
                            strategy="hi_res",
                            timeout=60,
                            max_retries=3
                        )
                        assert False, "Should have raised UnstructuredProcessorError"
                    except UnstructuredProcessorError as e:
                        assert "API timeout after 3 attempts" in str(e)

    print("[PASS] test_all_retries_exhausted")


def test_http_error_no_retry():
    """Test that HTTP errors (non-timeout) do NOT trigger retry."""
    import tempfile
    import requests

    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "test.pdf"
        doc_path.write_bytes(b"fake pdf content")
        output_dir = Path(tmpdir) / "output"

        call_count = {'value': 0}

        def mock_post(*args, **kwargs):
            call_count['value'] += 1
            # Raise HTTP error (e.g., 500 Internal Server Error)
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            error = requests.HTTPError("500 Server Error")
            error.response = mock_response
            raise error

        with patch('pass_a_unstructured.requests.post', side_effect=mock_post):
            with patch('pass_a_unstructured.check_unstructured_health', return_value=True):
                try:
                    process_document_with_retry(
                        document_path=doc_path,
                        output_dir=output_dir,
                        strategy="hi_res",
                        timeout=60,
                        max_retries=3
                    )
                    assert False, "Should have raised UnstructuredProcessorError"
                except UnstructuredProcessorError as e:
                    assert "API request failed" in str(e)

        # Verify NO retry for HTTP errors
        assert call_count['value'] == 1, "HTTP errors should NOT trigger retry"

    print("[PASS] test_http_error_no_retry")


def test_timeout_increase_from_300_to_900():
    """Test that timeout was increased from 300s to 900s."""
    from config import IngestionConfig

    # Verify new timeout is 900s (15 minutes) vs old 300s (5 minutes)
    assert IngestionConfig.UNSTRUCTURED_TIMEOUT == 900, \
        f"Timeout should be 900s (15 min), got {IngestionConfig.UNSTRUCTURED_TIMEOUT}s"

    # Calculate expected total time with retries
    # Attempt 1: 900s (fail) + 30s wait
    # Attempt 2: 900s (fail) + 60s wait
    # Attempt 3: 900s (fail or success)
    # Total worst case: 2700s + 90s = 2790s (46.5 minutes)
    worst_case_time = (IngestionConfig.UNSTRUCTURED_TIMEOUT * IngestionConfig.UNSTRUCTURED_MAX_RETRIES) + \
                      (IngestionConfig.UNSTRUCTURED_INITIAL_WAIT * (2 ** 0)) + \
                      (IngestionConfig.UNSTRUCTURED_INITIAL_WAIT * (2 ** 1))

    assert worst_case_time == 2790, f"Worst case time should be 2790s, got {worst_case_time}s"

    # Previous configuration: 300s * 3 = 900s max (no retries between failures)
    # New configuration: 2790s max (with retries and backoff)
    # Improvement: 3.1x longer allowance for large documents

    print("[PASS] test_timeout_increase_from_300_to_900")


def run_all_tests():
    """Run all test cases."""
    print("\n=== Running pass_a_unstructured Retry Logic Tests ===\n")

    try:
        test_retry_config_values()
        test_successful_first_attempt()
        test_retry_on_timeout()
        test_exponential_backoff_calculation()
        test_all_retries_exhausted()
        test_http_error_no_retry()
        test_timeout_increase_from_300_to_900()

        print("\n=== All Tests Passed [SUCCESS] ===\n")
        return 0

    except AssertionError as e:
        print(f"\n=== Test Failed [FAIL] ===")
        print(f"Error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n=== Test Error [ERROR] ===")
        print(f"Error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
