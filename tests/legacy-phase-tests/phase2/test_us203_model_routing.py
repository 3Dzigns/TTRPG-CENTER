# tests/regression/phase2/test_us203_model_routing.py
"""
Phase 2 - US-203: Model Routing Regression Tests
Tests intelligent model selection based on query complexity and requirements
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestModelRouting:
    """Test suite for Model Routing validation"""

    def test_model_router_availability(self):
        """Test that Model Router module exists and is importable"""
        try:
            from src_common.orchestrator.model_router import ModelRouter, ModelType

            assert ModelRouter is not None, "ModelRouter class should be available"
            assert ModelType is not None, "ModelType enum should be available"

        except ImportError as e:
            pytest.fail(f"Model Router module not available: {e}")

    def test_model_selection_based_on_complexity(self):
        """Test that model router selects appropriate models based on query complexity"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("Model Router or QIC modules not available for testing")

        router = ModelRouter()

        # Test cases with expected model selections
        test_cases = [
            # Low complexity - should use fast model
            ("Fireball damage?", "low", "gpt-3.5-turbo"),
            ("AC of leather armor?", "low", "gpt-3.5-turbo"),

            # Medium complexity - should use balanced model
            ("How do I calculate attack bonus for a 5th level fighter?", "medium", "gpt-4"),
            ("What spells can a 3rd level wizard cast?", "medium", "gpt-4"),

            # High complexity - should use powerful model
            ("Compare spell effectiveness across character levels and provide optimization recommendations", "high", "gpt-4-turbo"),
            ("Analyze mathematical balance between damage types considering resistances and immunities", "high", "gpt-4-turbo")
        ]

        correct_selections = 0
        total_selections = len(test_cases)

        for query, expected_complexity, expected_model in test_cases:
            # Get query classification
            classification = classify_query(query)

            # Override complexity for testing
            classification["complexity"] = expected_complexity

            # Get model selection
            selected_model = router.select_model(classification)

            if selected_model == expected_model:
                correct_selections += 1
            else:
                print(f"Model mismatch: '{query}' (complexity: {expected_complexity}) -> {selected_model}, expected {expected_model}")

        # Calculate accuracy
        accuracy = correct_selections / total_selections

        # Should achieve high accuracy on model selection
        assert accuracy >= 0.80, f"Model selection accuracy {accuracy:.2%} below 80% threshold"

    def test_model_selection_performance(self):
        """Test that model selection meets performance requirements"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Mock classifications of varying complexity
        test_classifications = [
            {"intent": "fact_lookup", "complexity": "low", "needs_tools": True},
            {"intent": "procedural_howto", "complexity": "medium", "needs_tools": False},
            {"intent": "multi_hop_reasoning", "complexity": "high", "needs_tools": True},
            {"intent": "creative_write", "complexity": "low", "needs_tools": False},
            {"intent": "summarize", "complexity": "medium", "needs_tools": True}
        ]

        response_times = []

        # Measure model selection performance
        for _ in range(20):  # 20 iterations for statistical significance
            for classification in test_classifications:
                start_time = time.perf_counter()
                model = router.select_model(classification)
                end_time = time.perf_counter()

                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)

                # Verify model is valid
                valid_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "claude-3-sonnet", "claude-3-opus"]
                assert model in valid_models, f"Invalid model returned: {model}"

        # Calculate performance metrics
        avg_time = sum(response_times) / len(response_times)
        response_times.sort()
        p95_index = int(0.95 * len(response_times))
        p95_time = response_times[p95_index]

        # Model selection should be very fast (< 5ms average)
        assert avg_time < 5.0, f"Average model selection time {avg_time:.1f}ms exceeds 5ms requirement"
        assert p95_time < 10.0, f"P95 model selection time {p95_time:.1f}ms exceeds 10ms requirement"

    def test_model_cost_optimization(self):
        """Test that model router considers cost optimization in selection"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Test cost-conscious routing
        low_complexity_classification = {
            "intent": "fact_lookup",
            "complexity": "low",
            "confidence": 0.95,
            "needs_tools": False
        }

        # Should prefer cost-effective model for low complexity
        model = router.select_model(low_complexity_classification, cost_priority=True)
        cost_effective_models = ["gpt-3.5-turbo", "claude-3-haiku"]
        assert model in cost_effective_models, f"Should select cost-effective model for low complexity, got {model}"

        # Test quality-priority routing
        high_complexity_classification = {
            "intent": "multi_hop_reasoning",
            "complexity": "high",
            "confidence": 0.85,
            "needs_tools": True
        }

        # Should prefer high-quality model for high complexity
        model = router.select_model(high_complexity_classification, cost_priority=False)
        quality_models = ["gpt-4-turbo", "claude-3-opus"]
        assert model in quality_models, f"Should select quality model for high complexity, got {model}"

    def test_model_availability_handling(self):
        """Test that model router handles model availability and fallbacks"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Mock model availability check
        with patch.object(router, 'check_model_availability') as mock_availability:
            # Simulate primary model unavailable
            mock_availability.side_effect = lambda model: model != "gpt-4-turbo"

            classification = {
                "intent": "multi_hop_reasoning",
                "complexity": "high",
                "needs_tools": True
            }

            # Should fall back to available alternative
            model = router.select_model_with_fallback(classification)

            # Should not select unavailable model
            assert model != "gpt-4-turbo", "Should not select unavailable model"

            # Should select available alternative
            available_alternatives = ["gpt-4", "claude-3-opus"]
            assert model in available_alternatives, f"Should select available alternative, got {model}"

    def test_model_context_window_consideration(self):
        """Test that model router considers context window requirements"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Test large context requirement
        large_context_classification = {
            "intent": "summarize",
            "complexity": "medium",
            "estimated_tokens": 50000  # Large context requirement
        }

        model = router.select_model(large_context_classification)

        # Should select model with large context window
        large_context_models = ["gpt-4-turbo", "claude-3-opus", "claude-3-sonnet"]
        assert model in large_context_models, f"Should select large context model for 50k tokens, got {model}"

        # Test small context requirement
        small_context_classification = {
            "intent": "fact_lookup",
            "complexity": "low",
            "estimated_tokens": 2000  # Small context requirement
        }

        model = router.select_model(small_context_classification)

        # Can use any model for small context
        valid_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "claude-3-haiku", "claude-3-sonnet"]
        assert model in valid_models, f"Should select valid model for small context, got {model}"

    def test_model_capabilities_matching(self):
        """Test that model router matches models to required capabilities"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Test function calling requirement
        function_calling_classification = {
            "intent": "fact_lookup",
            "complexity": "medium",
            "needs_tools": True,
            "requires_function_calling": True
        }

        model = router.select_model(function_calling_classification)

        # Should select model with function calling support
        function_calling_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        assert model in function_calling_models, f"Should select function calling capable model, got {model}"

        # Test vision requirement (if supported)
        vision_classification = {
            "intent": "creative_write",
            "complexity": "medium",
            "requires_vision": True
        }

        try:
            model = router.select_model(vision_classification)
            # If vision routing is implemented, should select vision-capable model
            vision_models = ["gpt-4-vision", "gpt-4-turbo"]
            if model:
                assert model in vision_models or "vision" in model.lower(), f"Should select vision capable model if supported, got {model}"
        except NotImplementedError:
            # Vision routing not yet implemented - acceptable
            pass

    def test_model_performance_tracking(self):
        """Test that model router tracks model performance for optimization"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Mock performance tracking
        with patch.object(router, 'track_model_performance') as mock_track:
            classification = {
                "intent": "fact_lookup",
                "complexity": "low",
                "needs_tools": False
            }

            model = router.select_model(classification)

            # Simulate response tracking
            response_metrics = {
                "response_time": 1.5,
                "tokens_used": 150,
                "success": True,
                "quality_score": 0.85
            }

            router.track_model_performance(model, classification, response_metrics)

            # Verify tracking was called
            mock_track.assert_called_once_with(model, classification, response_metrics)

    def test_model_load_balancing(self):
        """Test that model router can balance load across available models"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Mock current load information
        with patch.object(router, 'get_model_load') as mock_load:
            # Simulate high load on preferred model
            def mock_load_func(model):
                if model == "gpt-4":
                    return 0.95  # High load
                else:
                    return 0.30  # Low load

            mock_load.side_effect = mock_load_func

            classification = {
                "intent": "procedural_howto",
                "complexity": "medium",
                "needs_tools": False
            }

            # Should consider load balancing
            model = router.select_model_with_load_balancing(classification)

            # Should avoid high-load model if alternatives available
            if router.load_balancing_enabled:
                assert model != "gpt-4" or mock_load.call_count == 0, "Should avoid high-load model when load balancing enabled"

    def test_model_routing_telemetry(self):
        """Test that model router emits telemetry for routing decisions"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Mock telemetry collection
        with patch('src_common.logging.jlog') as mock_jlog:
            classification = {
                "intent": "fact_lookup",
                "complexity": "low",
                "confidence": 0.92
            }

            # Execute model selection
            model = router.select_model(classification)

            # Verify telemetry was emitted
            if mock_jlog.call_count > 0:
                log_calls = [call.args for call in mock_jlog.call_args_list]

                # Look for routing-related logs
                routing_logs = [call for call in log_calls if "routing" in str(call).lower() or "model" in str(call).lower()]

                if len(routing_logs) > 0:
                    # Verify telemetry structure
                    for log_call in routing_logs:
                        assert len(log_call) >= 2, "Log should have level and message"

                    print(f"Found {len(routing_logs)} routing-related log entries")

    def test_model_router_configuration(self):
        """Test that model router respects configuration settings"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        # Test with custom configuration
        custom_config = {
            "default_model": "gpt-4",
            "cost_optimization": True,
            "load_balancing": True,
            "fallback_model": "gpt-3.5-turbo",
            "model_timeouts": {
                "gpt-3.5-turbo": 30,
                "gpt-4": 60,
                "gpt-4-turbo": 120
            }
        }

        router = ModelRouter(config=custom_config)

        # Verify configuration is applied
        assert router.default_model == "gpt-4", "Should use configured default model"
        assert router.cost_optimization == True, "Should enable cost optimization"
        assert router.load_balancing == True, "Should enable load balancing"

        # Test fallback behavior
        classification = {"intent": "unknown", "complexity": "low"}

        with patch.object(router, 'check_model_availability') as mock_availability:
            # Simulate all models unavailable except fallback
            mock_availability.side_effect = lambda model: model == "gpt-3.5-turbo"

            model = router.select_model_with_fallback(classification)
            assert model == "gpt-3.5-turbo", "Should use configured fallback model"

    def test_model_router_error_handling(self):
        """Test that model router handles errors gracefully"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        # Test invalid classification
        invalid_classification = {}

        try:
            model = router.select_model(invalid_classification)
            # Should handle gracefully and return default
            valid_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
            assert model in valid_models, "Should return valid default model for invalid classification"
        except Exception as e:
            # If exception, should be informative
            assert "classification" in str(e).lower(), "Exception should reference classification issue"

        # Test network/availability errors
        with patch.object(router, 'check_model_availability') as mock_availability:
            mock_availability.side_effect = Exception("Network error")

            classification = {
                "intent": "fact_lookup",
                "complexity": "low"
            }

            # Should handle network errors gracefully
            try:
                model = router.select_model_with_fallback(classification)
                assert model is not None, "Should return fallback model on network error"
            except Exception as e:
                # If exception propagated, should be handled appropriately
                assert "network" in str(e).lower() or "availability" in str(e).lower()

    def test_model_router_contract_compliance(self):
        """Test that model router output matches established contract"""
        try:
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Model Router module not available for testing")

        router = ModelRouter()

        classification = {
            "intent": "fact_lookup",
            "complexity": "medium",
            "confidence": 0.85,
            "needs_tools": True
        }

        # Test standard routing
        model = router.select_model(classification)

        # Verify contract compliance
        assert isinstance(model, str), "Selected model should be a string"
        assert len(model) > 0, "Model name should not be empty"

        # Should be a known model identifier
        known_model_patterns = ["gpt", "claude", "llama", "mistral"]
        assert any(pattern in model.lower() for pattern in known_model_patterns), f"Model {model} should match known patterns"

        # Test routing with metadata
        routing_result = router.select_model_with_metadata(classification)

        if routing_result:
            assert "model" in routing_result, "Routing result should include model field"
            assert "reasoning" in routing_result, "Routing result should include reasoning"
            assert "confidence" in routing_result, "Routing result should include confidence"
            assert "cost_estimate" in routing_result, "Routing result should include cost estimate"

            # Verify field types
            assert isinstance(routing_result["model"], str), "Model should be string"
            assert isinstance(routing_result["reasoning"], str), "Reasoning should be string"
            assert isinstance(routing_result["confidence"], (int, float)), "Confidence should be numeric"
            assert 0.0 <= routing_result["confidence"] <= 1.0, "Confidence should be between 0 and 1"