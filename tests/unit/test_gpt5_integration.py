#!/usr/bin/env python3
"""
Unit tests for GPT-5 integration in TTRPG Center.

Tests the model router updates, environment configuration,
graceful fallback handling, and telemetry.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import httpx

# Add src_common to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src_common"))

from orchestrator.router import pick_model


class TestGPT5ModelRouter:
    """Test GPT-5 integration in the model router."""

    def test_pick_model_gpt5_for_multi_hop_reasoning_high_complexity(self):
        """Test that high complexity multi-hop reasoning uses gpt-5-large."""
        classification = {"intent": "multi_hop_reasoning", "complexity": "high"}
        plan = {}

        result = pick_model(classification, plan)

        assert result["model"] == "gpt-5-large"
        assert result["max_tokens"] == 8000
        assert result["temperature"] == 0.1

    def test_pick_model_gpt5_for_creative_write(self):
        """Test that creative writing tasks use gpt-5-large."""
        classification = {"intent": "creative_write", "complexity": "medium"}
        plan = {}

        result = pick_model(classification, plan)

        assert result["model"] == "gpt-5-large"
        assert result["max_tokens"] == 6000
        assert result["temperature"] == 0.9

    def test_pick_model_fallback_for_other_intents(self):
        """Test that other intents still use appropriate models."""
        # Test code_help uses gpt-4o-mini
        classification = {"intent": "code_help", "complexity": "low"}
        plan = {}
        result = pick_model(classification, plan)
        assert result["model"] == "gpt-4o-mini"

        # Test summarize uses gpt-4o-mini
        classification = {"intent": "summarize", "complexity": "low"}
        result = pick_model(classification, plan)
        assert result["model"] == "gpt-4o-mini"

        # Test default fallback
        classification = {"intent": "unknown", "complexity": "medium"}
        result = pick_model(classification, plan)
        assert result["model"] == "gpt-4o-mini"


class TestGPT5EnvironmentConfiguration:
    """Test GPT-5 environment configuration."""

    def test_gpt5_enabled_environment_variable_true(self):
        """Test GPT-5 is used when OPENAI_GPT5_ENABLED=true."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
                mock_response.raise_for_status = Mock()
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response

                # Should use GPT-5 when enabled
                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Verify it called with GPT-5
                call_args = mock_client.return_value.__enter__.return_value.post.call_args
                assert call_args[1]["json"]["model"] == "gpt-5"

    def test_gpt5_disabled_environment_variable_false(self):
        """Test GPT-4o fallback when OPENAI_GPT5_ENABLED=false."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "false"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
                mock_response.raise_for_status = Mock()
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response

                # Should use GPT-4o fallback when disabled
                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Verify it called with GPT-4o
                call_args = mock_client.return_value.__enter__.return_value.post.call_args
                assert call_args[1]["json"]["model"] == "gpt-4o"

    def test_gpt5_default_disabled_when_env_not_set(self):
        """Test GPT-4o fallback when OPENAI_GPT5_ENABLED is not set."""
        with patch.dict(os.environ, {}, clear=True):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
                mock_response.raise_for_status = Mock()
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response

                # Should default to GPT-4o when env var not set
                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Verify it called with GPT-4o
                call_args = mock_client.return_value.__enter__.return_value.post.call_args
                assert call_args[1]["json"]["model"] == "gpt-4o"


class TestGPT5GracefulFallback:
    """Test graceful fallback handling for GPT-5 unavailability."""

    def test_gpt5_fallback_on_404_error(self):
        """Test GPT-4o fallback when GPT-5 returns 404."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_context = mock_client.return_value.__enter__.return_value

                # First call (GPT-5) returns 404, second call (GPT-4o) succeeds
                mock_404_response = Mock()
                mock_404_response.status_code = 404

                mock_success_response = Mock()
                mock_success_response.json.return_value = {
                    "choices": [{"message": {"content": "Fallback response"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
                mock_success_response.raise_for_status = Mock()

                # First call raises HTTPStatusError, second succeeds
                mock_context.post.side_effect = [
                    httpx.HTTPStatusError("Not Found", request=Mock(), response=mock_404_response),
                    mock_success_response
                ]

                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Should return fallback response
                assert result == "Fallback response"

                # Verify two calls were made
                assert mock_context.post.call_count == 2

                # First call with GPT-5, second with GPT-4o
                first_call = mock_context.post.call_args_list[0]
                second_call = mock_context.post.call_args_list[1]

                assert first_call[1]["json"]["model"] == "gpt-5"
                assert second_call[1]["json"]["model"] == "gpt-4o"

    def test_gpt5_fallback_on_400_error(self):
        """Test GPT-4o fallback when GPT-5 returns 400."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_context = mock_client.return_value.__enter__.return_value

                # First call (GPT-5) returns 400, second call (GPT-4o) succeeds
                mock_400_response = Mock()
                mock_400_response.status_code = 400

                mock_success_response = Mock()
                mock_success_response.json.return_value = {
                    "choices": [{"message": {"content": "Fallback response"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
                mock_success_response.raise_for_status = Mock()

                # First call raises HTTPStatusError, second succeeds
                mock_context.post.side_effect = [
                    httpx.HTTPStatusError("Bad Request", request=Mock(), response=mock_400_response),
                    mock_success_response
                ]

                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Should return fallback response
                assert result == "Fallback response"

                # Verify fallback was triggered
                assert mock_context.post.call_count == 2

    def test_gpt5_error_propagation_for_non_fallback_cases(self):
        """Test that non-fallback errors are properly propagated."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_context = mock_client.return_value.__enter__.return_value

                # 500 error should not trigger fallback
                mock_500_response = Mock()
                mock_500_response.status_code = 500

                mock_context.post.side_effect = httpx.HTTPStatusError(
                    "Internal Server Error",
                    request=Mock(),
                    response=mock_500_response
                )

                with pytest.raises(httpx.HTTPStatusError):
                    openai_chat("gpt-5-large", "system", "user", "test_key")

                # Should only make one call (no fallback)
                assert mock_context.post.call_count == 1


class TestGPT5Telemetry:
    """Test telemetry and logging for GPT-5 usage."""

    @patch('sys.stderr')
    def test_model_usage_telemetry_logging(self, mock_stderr):
        """Test that model usage is logged with telemetry."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
                }
                mock_response.raise_for_status = Mock()
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response

                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Verify telemetry was logged
                mock_stderr.write.assert_called()

                # Check that usage info was written
                written_content = "".join([call[0][0] for call in mock_stderr.write.call_args_list])
                assert "Model usage: gpt-5" in written_content
                assert "prompt_tokens: 100" in written_content
                assert "completion_tokens: 50" in written_content
                assert "total_tokens: 150" in written_content

    @patch('sys.stderr')
    def test_fallback_telemetry_logging(self, mock_stderr):
        """Test that fallback usage is logged with telemetry."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.rag_openai import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_context = mock_client.return_value.__enter__.return_value

                # First call fails, second succeeds
                mock_404_response = Mock()
                mock_404_response.status_code = 404

                mock_success_response = Mock()
                mock_success_response.json.return_value = {
                    "choices": [{"message": {"content": "Fallback response"}}],
                    "usage": {"prompt_tokens": 75, "completion_tokens": 25, "total_tokens": 100}
                }
                mock_success_response.raise_for_status = Mock()

                mock_context.post.side_effect = [
                    httpx.HTTPStatusError("Not Found", request=Mock(), response=mock_404_response),
                    mock_success_response
                ]

                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Verify both fallback message and telemetry were logged
                mock_stderr.write.assert_called()

                written_content = "".join([call[0][0] for call in mock_stderr.write.call_args_list])
                assert "GPT-5 unavailable" in written_content
                assert "falling back to GPT-4o" in written_content
                assert "Fallback model usage: gpt-4o" in written_content
                assert "prompt_tokens: 75" in written_content


class TestGPT5PersonaScript:
    """Test GPT-5 integration in persona responses script."""

    def test_persona_script_gpt5_integration(self):
        """Test that persona script also supports GPT-5."""
        with patch.dict(os.environ, {"OPENAI_GPT5_ENABLED": "true"}):
            from scripts.run_persona_responses import openai_chat

            # Mock the httpx client
            with patch('httpx.Client') as mock_client:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Persona response"}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}
                }
                mock_response.raise_for_status = Mock()
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response

                result = openai_chat("gpt-5-large", "system", "user", "test_key")

                # Verify it called with GPT-5
                call_args = mock_client.return_value.__enter__.return_value.post.call_args
                assert call_args[1]["json"]["model"] == "gpt-5"
                assert result == "Persona response"


if __name__ == "__main__":
    pytest.main([__file__])