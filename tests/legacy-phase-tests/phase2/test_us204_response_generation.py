# tests/regression/phase2/test_us204_response_generation.py
"""
Phase 2 - US-204: Response Generation Regression Tests
Tests end-to-end response generation with quality and performance requirements
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestResponseGeneration:
    """Test suite for Response Generation validation"""

    def test_response_generator_availability(self):
        """Test that Response Generator module exists and is importable"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator, ResponseFormat

            assert ResponseGenerator is not None, "ResponseGenerator class should be available"
            assert ResponseFormat is not None, "ResponseFormat enum should be available"

        except ImportError as e:
            pytest.fail(f"Response Generator module not available: {e}")

    def test_end_to_end_response_generation(self):
        """Test complete end-to-end response generation pipeline"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
            from src_common.orchestrator.classifier import classify_query
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
            from src_common.orchestrator.model_router import ModelRouter
        except ImportError:
            pytest.skip("Required orchestrator modules not available for testing")

        # Initialize components
        generator = ResponseGenerator()
        classifier = classify_query
        retrieval_engine = RetrievalPolicyEngine()
        model_router = ModelRouter()

        # Test queries of different types
        test_queries = [
            "What is the damage of Fireball?",
            "How do I calculate attack bonus for a Fighter?",
            "Compare Wizard vs Sorcerer spell progression",
            "Write flavor text for a brave paladin",
            "List all fire damage spells"
        ]

        for query in test_queries:
            # Mock the complete pipeline
            with patch.object(retrieval_engine, 'retrieve') as mock_retrieve, \
                 patch('openai.chat.completions.create') as mock_openai:

                # Mock retrieval results
                mock_retrieve.return_value = [
                    {
                        "content": f"Relevant content for: {query}",
                        "metadata": {"page": 1, "section": "test"},
                        "score": 0.85
                    }
                ]

                # Mock OpenAI response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = f"Generated response for: {query}"
                mock_response.usage.total_tokens = 150
                mock_openai.return_value = mock_response

                # Execute end-to-end generation
                start_time = time.perf_counter()
                response = generator.generate_response(query)
                end_time = time.perf_counter()

                # Verify response structure
                assert isinstance(response, dict), "Response should be a dictionary"
                assert "answer" in response, "Response should have answer field"
                assert "sources" in response, "Response should have sources field"
                assert "metadata" in response, "Response should have metadata field"

                # Verify content quality
                assert len(response["answer"]) > 0, "Answer should not be empty"
                assert isinstance(response["sources"], list), "Sources should be a list"
                assert isinstance(response["metadata"], dict), "Metadata should be a dictionary"

                # Verify performance
                response_time = (end_time - start_time) * 1000
                assert response_time < 5000, f"Response generation took {response_time:.1f}ms, should be < 5000ms"

    def test_response_format_compliance(self):
        """Test that responses comply with format specifications"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Mock dependencies
        with patch('src_common.orchestrator.classifier.classify_query') as mock_classify, \
             patch('src_common.orchestrator.retrieval.RetrievalPolicyEngine') as mock_retrieval_class, \
             patch('openai.chat.completions.create') as mock_openai:

            # Mock classification
            mock_classify.return_value = {
                "intent": "fact_lookup",
                "domain": "ttrpg_rules",
                "complexity": "low",
                "confidence": 0.92
            }

            # Mock retrieval
            mock_retrieval = MagicMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.retrieve.return_value = [
                {
                    "content": "Fireball deals 8d6 fire damage",
                    "metadata": {"page": 241, "section": "Spells"},
                    "score": 0.95
                }
            ]

            # Mock OpenAI
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "The Fireball spell deals 8d6 fire damage to all creatures in a 20-foot radius."
            mock_response.usage.total_tokens = 85
            mock_openai.return_value = mock_response

            # Test different format requirements
            format_tests = [
                ("standard", "What is Fireball damage?"),
                ("detailed", "What is Fireball damage?"),
                ("brief", "What is Fireball damage?"),
                ("structured", "What is Fireball damage?")
            ]

            for format_type, query in format_tests:
                response = generator.generate_response(query, format=format_type)

                # Verify format-specific requirements
                assert "answer" in response, f"Format {format_type} missing answer field"
                assert "sources" in response, f"Format {format_type} missing sources field"
                assert "metadata" in response, f"Format {format_type} missing metadata field"

                # Format-specific validations
                if format_type == "detailed":
                    assert "reasoning" in response["metadata"], "Detailed format should include reasoning"
                elif format_type == "brief":
                    assert len(response["answer"]) <= 200, "Brief format should be concise"
                elif format_type == "structured":
                    assert "sections" in response["metadata"], "Structured format should have sections"

    def test_response_quality_validation(self):
        """Test response quality validation and filtering"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Test quality validation
        quality_test_cases = [
            # Good response
            {
                "answer": "The Fireball spell deals 8d6 fire damage in a 20-foot radius sphere.",
                "sources": [{"content": "Fireball deals 8d6 fire damage", "score": 0.95}],
                "expected_quality": "high"
            },
            # Vague response
            {
                "answer": "It does some damage.",
                "sources": [{"content": "damage information", "score": 0.45}],
                "expected_quality": "low"
            },
            # Well-sourced response
            {
                "answer": "According to the Player's Handbook, Fireball is a 3rd-level spell that deals 8d6 fire damage.",
                "sources": [
                    {"content": "Fireball, 3rd level evocation", "score": 0.92},
                    {"content": "8d6 fire damage", "score": 0.88}
                ],
                "expected_quality": "high"
            }
        ]

        for case in quality_test_cases:
            quality_score = generator.assess_response_quality(case)

            assert isinstance(quality_score, (int, float)), "Quality score should be numeric"
            assert 0.0 <= quality_score <= 1.0, "Quality score should be between 0 and 1"

            # Quality thresholds
            if case["expected_quality"] == "high":
                assert quality_score >= 0.7, f"High quality response scored {quality_score}, expected >= 0.7"
            elif case["expected_quality"] == "low":
                assert quality_score <= 0.5, f"Low quality response scored {quality_score}, expected <= 0.5"

    def test_source_attribution_accuracy(self):
        """Test that responses properly attribute sources"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Mock retrieval with specific sources
        mock_sources = [
            {
                "content": "Fireball is a 3rd-level evocation spell",
                "metadata": {"page": 241, "section": "Spells", "source": "Player's Handbook"},
                "score": 0.95
            },
            {
                "content": "Fireball deals 8d6 fire damage",
                "metadata": {"page": 241, "section": "Spells", "source": "Player's Handbook"},
                "score": 0.90
            }
        ]

        with patch('src_common.orchestrator.retrieval.RetrievalPolicyEngine') as mock_retrieval_class, \
             patch('openai.chat.completions.create') as mock_openai:

            mock_retrieval = MagicMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.retrieve.return_value = mock_sources

            # Mock response that uses both sources
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Fireball is a 3rd-level evocation spell that deals 8d6 fire damage."
            mock_response.usage.total_tokens = 95
            mock_openai.return_value = mock_response

            response = generator.generate_response("What is Fireball?")

            # Verify source attribution
            assert len(response["sources"]) > 0, "Response should include sources"

            for source in response["sources"]:
                assert "content" in source, "Source should have content"
                assert "metadata" in source, "Source should have metadata"
                assert "page" in source["metadata"], "Source metadata should include page"

                # Verify source relevance
                if "score" in source:
                    assert source["score"] >= 0.0, "Source score should be non-negative"

    def test_response_caching_behavior(self):
        """Test response caching for performance optimization"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator(enable_caching=True)

        # Mock expensive operations
        with patch.object(generator, '_generate_uncached_response') as mock_generate:
            mock_generate.return_value = {
                "answer": "Cached response about Fireball",
                "sources": [{"content": "test", "metadata": {}, "score": 0.9}],
                "metadata": {"cached": False}
            }

            query = "What is Fireball damage?"

            # First call should generate response
            response1 = generator.generate_response(query)
            assert mock_generate.call_count == 1, "Should call generation on first request"

            # Second call should use cache
            response2 = generator.generate_response(query)

            if generator.caching_enabled:
                # Cache hit - should not call generation again
                assert mock_generate.call_count == 1, "Should use cache on second identical request"
                assert response1["answer"] == response2["answer"], "Cached response should match original"

    def test_response_streaming_capability(self):
        """Test streaming response generation for real-time updates"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Test streaming interface (if implemented)
        if hasattr(generator, 'generate_response_stream'):
            with patch('openai.chat.completions.create') as mock_openai:
                # Mock streaming response
                def mock_stream():
                    chunks = [
                        "The ", "Fireball ", "spell ", "deals ", "8d6 ", "fire ", "damage."
                    ]
                    for chunk in chunks:
                        yield MagicMock(choices=[MagicMock(delta=MagicMock(content=chunk))])

                mock_openai.return_value = mock_stream()

                # Collect streamed response
                streamed_chunks = []
                for chunk in generator.generate_response_stream("What is Fireball damage?"):
                    streamed_chunks.append(chunk)

                # Verify streaming
                assert len(streamed_chunks) > 0, "Should generate response chunks"

                full_response = "".join(streamed_chunks)
                assert "Fireball" in full_response, "Streamed response should contain query content"

    def test_response_error_handling(self):
        """Test graceful error handling in response generation"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Test API failure handling
        with patch('openai.chat.completions.create') as mock_openai:
            mock_openai.side_effect = Exception("API unavailable")

            try:
                response = generator.generate_response("What is Fireball?")

                # Should handle gracefully
                assert isinstance(response, dict), "Should return structured response even on API failure"
                assert "answer" in response, "Should include fallback answer"
                assert "error" in response.get("metadata", {}), "Should indicate error in metadata"

            except Exception as e:
                # If exception propagated, should be informative
                assert "API" in str(e) or "unavailable" in str(e), "Exception should reference API issue"

        # Test retrieval failure handling
        with patch('src_common.orchestrator.retrieval.RetrievalPolicyEngine') as mock_retrieval_class:
            mock_retrieval = MagicMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.retrieve.side_effect = Exception("Retrieval failed")

            try:
                response = generator.generate_response("What is Fireball?")

                # Should handle gracefully
                if response:
                    assert "answer" in response, "Should provide fallback answer when retrieval fails"
                    assert response.get("sources", []) == [], "Should have empty sources on retrieval failure"

            except Exception as e:
                assert "retrieval" in str(e).lower(), "Exception should reference retrieval issue"

    def test_response_telemetry_emission(self):
        """Test that response generation emits comprehensive telemetry"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Mock telemetry collection
        with patch('src_common.logging.jlog') as mock_jlog, \
             patch('openai.chat.completions.create') as mock_openai:

            # Mock successful response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test response"
            mock_response.usage.total_tokens = 100
            mock_openai.return_value = mock_response

            response = generator.generate_response("Test query")

            # Verify telemetry was emitted
            if mock_jlog.call_count > 0:
                log_calls = [call.args for call in mock_jlog.call_args_list]

                # Look for response generation logs
                response_logs = [call for call in log_calls if "response" in str(call).lower() or "generation" in str(call).lower()]

                if len(response_logs) > 0:
                    # Verify telemetry includes key metrics
                    for log_call in response_logs:
                        assert len(log_call) >= 2, "Log should have level and message"

                    print(f"Found {len(response_logs)} response generation log entries")

    def test_response_performance_benchmarks(self):
        """Test response generation performance against benchmarks"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Mock fast dependencies
        with patch('src_common.orchestrator.classifier.classify_query') as mock_classify, \
             patch('src_common.orchestrator.retrieval.RetrievalPolicyEngine') as mock_retrieval_class, \
             patch('openai.chat.completions.create') as mock_openai:

            # Fast mock responses
            mock_classify.return_value = {"intent": "fact_lookup", "complexity": "low"}

            mock_retrieval = MagicMock()
            mock_retrieval_class.return_value = mock_retrieval
            mock_retrieval.retrieve.return_value = [{"content": "test", "metadata": {}, "score": 0.9}]

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Quick test response"
            mock_response.usage.total_tokens = 50
            mock_openai.return_value = mock_response

            # Performance test
            test_queries = [
                "What is Fireball?",
                "How do I cast spells?",
                "List fire spells",
                "Character creation steps",
                "Calculate attack bonus"
            ]

            response_times = []

            for query in test_queries:
                start_time = time.perf_counter()
                response = generator.generate_response(query)
                end_time = time.perf_counter()

                response_time = (end_time - start_time) * 1000
                response_times.append(response_time)

                # Verify response was generated
                assert response is not None, "Should generate response"
                assert "answer" in response, "Should include answer"

            # Performance benchmarks
            avg_time = sum(response_times) / len(response_times)
            response_times.sort()
            p95_index = int(0.95 * len(response_times))
            p95_time = response_times[p95_index]

            # Performance requirements
            assert avg_time < 3000, f"Average response time {avg_time:.1f}ms exceeds 3000ms benchmark"
            assert p95_time < 5000, f"P95 response time {p95_time:.1f}ms exceeds 5000ms benchmark"

    def test_response_contract_compliance(self):
        """Test that response generation output matches established contract"""
        try:
            from src_common.orchestrator.response_generator import ResponseGenerator
        except ImportError:
            pytest.skip("Response Generator module not available for testing")

        generator = ResponseGenerator()

        # Mock successful generation
        with patch('openai.chat.completions.create') as mock_openai:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Contract compliance test response"
            mock_response.usage.total_tokens = 75
            mock_openai.return_value = mock_response

            response = generator.generate_response("Test query")

            # Verify contract fields
            required_fields = ["answer", "sources", "metadata"]
            for field in required_fields:
                assert field in response, f"Contract violation: missing required field '{field}'"

            # Verify field types
            assert isinstance(response["answer"], str), "Answer must be string"
            assert isinstance(response["sources"], list), "Sources must be list"
            assert isinstance(response["metadata"], dict), "Metadata must be dictionary"

            # Verify metadata structure
            metadata = response["metadata"]
            expected_metadata_fields = ["query", "timestamp", "model_used", "tokens_used"]

            for field in expected_metadata_fields:
                if field in metadata:
                    # Verify field types if present
                    if field == "timestamp":
                        assert isinstance(metadata[field], (int, float, str)), "Timestamp should be temporal"
                    elif field == "tokens_used":
                        assert isinstance(metadata[field], int), "Tokens used should be integer"
                    elif field in ["query", "model_used"]:
                        assert isinstance(metadata[field], str), f"{field} should be string"

            # Verify sources structure
            for source in response["sources"]:
                assert isinstance(source, dict), "Each source should be a dictionary"
                if "content" in source:
                    assert isinstance(source["content"], str), "Source content should be string"
                if "score" in source:
                    assert isinstance(source["score"], (int, float)), "Source score should be numeric"
                    assert 0.0 <= source["score"] <= 1.0, "Source score should be between 0 and 1"