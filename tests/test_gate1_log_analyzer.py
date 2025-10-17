#!/usr/bin/env python3
"""
Unit tests for gate_1_log_analyzer.py response parsing logic.

Tests the robust OpenAI response parsing that handles multiple formats:
- Direct array: [{issue1}, {issue2}]
- Object with "issues" key: {"issues": [{issue1}, {issue2}]}
- Object with alternative keys: {"problems": [{issue1}], "findings": [{issue2}]}
- Single issue object: {"issue_type": "error", "severity": "high", ...}
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

from gate_1_log_analyzer import Gate1LogAnalyzerError


def parse_openai_response_logic(result):
    """
    Extracted parsing logic from gate_1_log_analyzer.py for testing.
    This mirrors the exact logic in analyze_log_with_openai() lines 233-260.
    """
    if isinstance(result, list):
        # Direct array format
        issues = result
    elif isinstance(result, dict):
        # Try multiple possible keys that might contain the issues array
        for key in ["issues", "problems", "findings", "errors", "analysis", "results"]:
            if key in result and isinstance(result[key], list):
                issues = result[key]
                break
        else:
            # No known key with array found, try to extract array values
            array_values = [v for v in result.values() if isinstance(v, list)]
            if array_values:
                # Take first array found in the response
                issues = array_values[0]
            elif all(k in result for k in ["issue_type", "severity", "summary"]):
                # Single issue object, wrap in array
                issues = [result]
            else:
                # Cannot extract issues from response structure
                raise Gate1LogAnalyzerError(
                    f"Cannot extract issues array from response. "
                    f"Response keys: {list(result.keys())}, "
                    f"Expected 'issues' key or array value."
                )
    else:
        raise Gate1LogAnalyzerError(f"Unexpected response type: {type(result)}")

    return issues


def test_direct_array_format():
    """Test parsing of direct JSON array format."""
    response = [
        {"issue_type": "error", "severity": "critical", "summary": "Test issue 1"},
        {"issue_type": "warning", "severity": "medium", "summary": "Test issue 2"}
    ]

    issues = parse_openai_response_logic(response)

    assert isinstance(issues, list)
    assert len(issues) == 2
    assert issues[0]["issue_type"] == "error"
    assert issues[1]["severity"] == "medium"
    print("[PASS] test_direct_array_format")


def test_object_with_issues_key():
    """Test parsing of object with 'issues' key."""
    response = {
        "issues": [
            {"issue_type": "error", "severity": "high", "summary": "Test issue"}
        ]
    }

    issues = parse_openai_response_logic(response)

    assert isinstance(issues, list)
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "error"
    print("[PASS] test_object_with_issues_key passed")


def test_object_with_alternative_keys():
    """Test parsing of object with alternative keys like 'problems', 'findings'."""
    test_cases = [
        {"problems": [{"issue_type": "error", "severity": "high"}]},
        {"findings": [{"issue_type": "performance", "severity": "medium"}]},
        {"errors": [{"issue_type": "error", "severity": "critical"}]},
        {"analysis": [{"issue_type": "data_quality", "severity": "low"}]},
        {"results": [{"issue_type": "configuration", "severity": "medium"}]}
    ]

    for response in test_cases:
        issues = parse_openai_response_logic(response)
        assert isinstance(issues, list)
        assert len(issues) == 1

    print("[PASS] test_object_with_alternative_keys passed")


def test_object_with_any_array_value():
    """Test parsing of object with any array value (fallback)."""
    response = {
        "metadata": {"timestamp": "2025-10-17"},
        "detected_issues": [
            {"issue_type": "error", "severity": "high", "summary": "Found issue"}
        ],
        "version": "1.0.0"
    }

    issues = parse_openai_response_logic(response)

    assert isinstance(issues, list)
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "error"
    print("[PASS] test_object_with_any_array_value passed")


def test_single_issue_object():
    """Test parsing of single issue object (wrap in array)."""
    response = {
        "issue_type": "error",
        "severity": "critical",
        "summary": "Single issue",
        "details": "Error details",
        "pass": "pass_f"
    }

    issues = parse_openai_response_logic(response)

    assert isinstance(issues, list)
    assert len(issues) == 1
    assert issues[0]["issue_type"] == "error"
    assert issues[0]["severity"] == "critical"
    print("[PASS] test_single_issue_object passed")


def test_empty_issues_array():
    """Test parsing of empty issues array (no issues found)."""
    response = {"issues": []}

    issues = parse_openai_response_logic(response)

    assert isinstance(issues, list)
    assert len(issues) == 0
    print("[PASS] test_empty_issues_array passed")


def test_invalid_response_raises_error():
    """Test that invalid responses raise appropriate errors."""
    invalid_responses = [
        {"metadata": "no arrays here", "version": "1.0"},
        {"some_key": "string value", "other_key": 123},
        123,
        "string response",
        None
    ]

    for response in invalid_responses:
        try:
            parse_openai_response_logic(response)
            assert False, f"Should have raised error for: {response}"
        except Gate1LogAnalyzerError:
            pass  # Expected

    print("[PASS] test_invalid_response_raises_error passed")


def test_real_world_openai_responses():
    """Test real-world OpenAI response patterns."""
    # Pattern 1: Structured response with metadata
    response1 = {
        "analysis_timestamp": "2025-10-17T10:00:00Z",
        "issues": [
            {"issue_type": "error", "severity": "critical", "summary": "Pass F failed"}
        ],
        "total_issues": 1
    }

    issues1 = parse_openai_response_logic(response1)
    assert len(issues1) == 1

    # Pattern 2: Response with metadata, no nested structures
    # (The current logic doesn't recurse into nested dicts, which is fine)
    response2 = {
        "timestamp": "2025-10-17",
        "analysis_results": [
                {"issue_type": "performance", "severity": "medium"}
        ],
        "metadata": {"version": "1.0"}
    }

    # This should extract the first array found at top level
    issues2 = parse_openai_response_logic(response2)
    assert len(issues2) == 1

    print("[PASS] test_real_world_openai_responses passed")


def run_all_tests():
    """Run all test cases."""
    print("\n=== Running gate_1_log_analyzer Response Parsing Tests ===\n")

    try:
        test_direct_array_format()
        test_object_with_issues_key()
        test_object_with_alternative_keys()
        test_object_with_any_array_value()
        test_single_issue_object()
        test_empty_issues_array()
        test_invalid_response_raises_error()
        test_real_world_openai_responses()

        print("\n=== All Tests Passed [SUCCESS] ===\n")
        return 0

    except AssertionError as e:
        print(f"\n=== Test Failed [FAIL] ===")
        print(f"Error: {e}\n")
        return 1
    except Exception as e:
        print(f"\n=== Test Error [ERROR] ===")
        print(f"Error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
