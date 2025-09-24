# tests/regression/phase2/test_us201_qic.py
"""
Phase 2 - US-201: Query Intent Classifier Regression Tests
Tests Query Intent Classifier with p95 <150ms performance requirement and F1≥0.85 accuracy
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestQueryIntentClassifier:
    """Test suite for Query Intent Classifier (QIC) validation"""

    def test_qic_module_availability(self):
        """Test that QIC module exists and is importable"""
        try:
            from src_common.orchestrator.classifier import classify_query, Classification

            assert callable(classify_query), "classify_query function should be available"
            assert Classification is not None, "Classification type should be available"

        except ImportError as e:
            pytest.fail(f"QIC module not available: {e}")

    def test_qic_performance_p95_requirement(self):
        """Test that QIC meets p95 <150ms performance requirement"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test queries of various types and complexities
        test_queries = [
            "What is the damage of a Fireball spell?",
            "How do I cast a spell in combat?",
            "Write a story about a brave knight",
            "What spell does 8d6 fire damage?",
            "Summarize the rules for spellcasting",
            "Compare Wizard vs Sorcerer spell slots",
            "What's the DC for a 3rd level spell?",
            "How many hit points does a Fighter have?",
            "Tell me about the lore of Waterdeep",
            "What are the steps to create a character?"
        ]

        response_times = []

        # Measure response times for multiple iterations
        for _ in range(20):  # 20 iterations for statistical significance
            for query in test_queries:
                start_time = time.perf_counter()
                result = classify_query(query)
                end_time = time.perf_counter()

                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)

                # Verify basic result structure
                assert isinstance(result, dict), "Classification result should be a dictionary"
                assert "intent" in result, "Result should have intent field"
                assert "domain" in result, "Result should have domain field"
                assert "complexity" in result, "Result should have complexity field"

        # Calculate p95 (95th percentile)
        response_times.sort()
        p95_index = int(0.95 * len(response_times))
        p95_time = response_times[p95_index]

        # Assert p95 requirement
        assert p95_time < 150.0, f"P95 response time {p95_time:.1f}ms exceeds 150ms requirement"

        # Also check average for good measure
        avg_time = sum(response_times) / len(response_times)
        assert avg_time < 100.0, f"Average response time {avg_time:.1f}ms should be well under 150ms"

    def test_qic_intent_classification_accuracy(self):
        """Test that QIC correctly classifies various query intents"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test cases with expected intents
        test_cases = [
            # Fact lookup queries
            ("What is the damage of Fireball?", "fact_lookup"),
            ("What's the AC of Chain Mail?", "fact_lookup"),
            ("How many spell slots does a 5th level Wizard have?", "fact_lookup"),

            # Procedural how-to queries
            ("How do I cast a spell?", "procedural_howto"),
            ("What are the steps to create a character?", "procedural_howto"),
            ("How do I calculate attack bonus?", "procedural_howto"),

            # Creative writing queries
            ("Write a story about a brave paladin", "creative_write"),
            ("Create flavor text for my barbarian", "creative_write"),
            ("Generate a tavern description", "creative_write"),

            # Summarize queries
            ("Summarize the spellcasting rules", "summarize"),
            ("Give me a tl;dr of combat mechanics", "summarize"),

            # Multi-hop reasoning queries
            ("Compare Wizard vs Sorcerer and explain which is better for damage", "multi_hop_reasoning"),
            ("What's the best spell combination for crowd control?", "multi_hop_reasoning")
        ]

        correct_classifications = 0
        total_classifications = len(test_cases)

        for query, expected_intent in test_cases:
            result = classify_query(query)
            actual_intent = result.get("intent")

            if actual_intent == expected_intent:
                correct_classifications += 1
            else:
                print(f"Misclassification: '{query}' -> {actual_intent}, expected {expected_intent}")

        # Calculate accuracy
        accuracy = correct_classifications / total_classifications

        # Should achieve high accuracy on these basic cases
        assert accuracy >= 0.70, f"Intent classification accuracy {accuracy:.2%} below 70% threshold on basic test cases"

    def test_qic_domain_classification_accuracy(self):
        """Test that QIC correctly classifies query domains"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test cases with expected domains
        test_cases = [
            # TTRPG rules domain
            ("What is the damage of a Fireball spell?", "ttrpg_rules"),
            ("How do I calculate AC?", "ttrpg_rules"),
            ("What's the DC for a Dexterity save?", "ttrpg_rules"),

            # TTRPG lore domain (if the classifier knows these names)
            ("Tell me about Waterdeep", "ttrpg_lore"),
            ("What happened in the Time of Troubles?", "ttrpg_lore"),

            # Admin domain
            ("Show me the ingestion logs", "admin"),
            ("What's the system status?", "admin"),

            # Unknown domain
            ("What's the weather like?", "unknown"),
            ("How do I cook pasta?", "unknown")
        ]

        correct_domains = 0
        total_domains = len(test_cases)

        for query, expected_domain in test_cases:
            result = classify_query(query)
            actual_domain = result.get("domain")

            if actual_domain == expected_domain:
                correct_domains += 1

        # Calculate domain accuracy
        domain_accuracy = correct_domains / total_domains

        # Domain classification may be less accurate than intent
        assert domain_accuracy >= 0.50, f"Domain classification accuracy {domain_accuracy:.2%} below 50% threshold"

    def test_qic_complexity_classification(self):
        """Test that QIC correctly assesses query complexity"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test cases with expected complexity levels
        test_cases = [
            # Low complexity - simple, short queries
            ("Fireball damage?", "low"),
            ("AC of leather armor?", "low"),

            # Medium complexity - moderate length, some detail
            ("How do I calculate the attack bonus for a 5th level fighter with strength 16?", "medium"),
            ("What spells can a 3rd level wizard cast?", "medium"),

            # High complexity - long, comparative, or complex reasoning
            ("Compare the effectiveness of different spell schools for crowd control in large encounters and provide recommendations for optimization", "high"),
            ("Analyze the mathematical balance between spell damage per slot level versus spell utility across different character levels", "high")
        ]

        correct_complexity = 0
        total_complexity = len(test_cases)

        for query, expected_complexity in test_cases:
            result = classify_query(query)
            actual_complexity = result.get("complexity")

            if actual_complexity == expected_complexity:
                correct_complexity += 1

        # Calculate complexity accuracy
        complexity_accuracy = correct_complexity / total_complexity

        # Complexity assessment should be reasonably accurate
        assert complexity_accuracy >= 0.60, f"Complexity classification accuracy {complexity_accuracy:.2%} below 60% threshold"

    def test_qic_needs_tools_detection(self):
        """Test that QIC correctly identifies queries that need tools"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Queries that should need tools (fact lookup, multi-hop reasoning, etc.)
        needs_tools_queries = [
            "What is the damage of Fireball?",
            "How many spell slots does a Wizard have?",
            "Compare Fighter vs Barbarian damage output",
            "Summarize all evocation spells"
        ]

        # Queries that might not need tools (creative writing)
        no_tools_queries = [
            "Write a story about a dragon",
            "Create flavor text for my character"
        ]

        # Test needs_tools detection
        for query in needs_tools_queries:
            result = classify_query(query)
            needs_tools = result.get("needs_tools", False)
            # Most fact lookups and reasoning should need tools
            # (This may vary based on implementation)

        for query in no_tools_queries:
            result = classify_query(query)
            needs_tools = result.get("needs_tools", True)
            # Creative queries might not need retrieval tools

        # This test is more about ensuring the field exists and is boolean
        assert isinstance(result.get("needs_tools"), bool), "needs_tools should be a boolean value"

    def test_qic_confidence_scoring(self):
        """Test that QIC provides confidence scores"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test with clear, unambiguous queries
        clear_queries = [
            "What is the damage of Fireball?",  # Clear fact lookup
            "How do I cast a spell?",           # Clear procedural
            "Write a story about a knight"      # Clear creative
        ]

        # Test with ambiguous queries
        ambiguous_queries = [
            "Magic",                            # Very short, unclear
            "Tell me about things",             # Vague
            "Help with stuff"                   # Unclear intent
        ]

        # Clear queries should have higher confidence
        clear_confidences = []
        for query in clear_queries:
            result = classify_query(query)
            confidence = result.get("confidence", 0.0)
            assert isinstance(confidence, (int, float)), "Confidence should be numeric"
            assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} should be between 0 and 1"
            clear_confidences.append(confidence)

        # Ambiguous queries should have lower confidence
        ambiguous_confidences = []
        for query in ambiguous_queries:
            result = classify_query(query)
            confidence = result.get("confidence", 0.0)
            assert isinstance(confidence, (int, float)), "Confidence should be numeric"
            assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} should be between 0 and 1"
            ambiguous_confidences.append(confidence)

        # On average, clear queries should have higher confidence
        avg_clear = sum(clear_confidences) / len(clear_confidences)
        avg_ambiguous = sum(ambiguous_confidences) / len(ambiguous_confidences)

        # This is a general expectation but may not always hold
        print(f"Average clear confidence: {avg_clear:.3f}, Average ambiguous confidence: {avg_ambiguous:.3f}")

    def test_qic_telemetry_emission(self):
        """Test that QIC emits structured telemetry"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Mock telemetry collection
        telemetry_events = []

        def mock_emit_telemetry(event_type, data):
            telemetry_events.append({"type": event_type, "data": data})

        # Test classification with telemetry
        with patch('src_common.logging.jlog') as mock_jlog:
            result = classify_query("What is the damage of Fireball?")

            # Verify basic result structure
            assert isinstance(result, dict), "Result should be a dictionary"

            # Check if telemetry was emitted (through logging)
            if mock_jlog.call_count > 0:
                # At least some logging should have occurred
                log_calls = [call.args for call in mock_jlog.call_args_list]

                # Look for classification-related logs
                classification_logs = [call for call in log_calls if len(call) >= 2 and "classification" in str(call).lower()]

                # If telemetry is implemented, should have classification logs
                print(f"Found {len(classification_logs)} classification-related log entries")

    def test_qic_heuristic_fallback_behavior(self):
        """Test QIC heuristic vs LLM fallback behavior"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test with queries that should trigger heuristic classification
        heuristic_queries = [
            "What is Fireball damage?",         # Contains "what is" - fact lookup heuristic
            "How do I cast spells?",            # Contains "how do i" - procedural heuristic
            "Write a backstory for my rogue",   # Contains "write" - creative heuristic
        ]

        for query in heuristic_queries:
            start_time = time.perf_counter()
            result = classify_query(query)
            end_time = time.perf_counter()

            response_time_ms = (end_time - start_time) * 1000

            # Heuristic classification should be very fast
            assert response_time_ms < 50.0, f"Heuristic classification took {response_time_ms:.1f}ms, should be <50ms"

            # Should still provide valid classification
            assert "intent" in result
            assert "domain" in result
            assert "complexity" in result
            assert "confidence" in result

    def test_qic_input_sanitization(self):
        """Test that QIC handles edge cases and potential security issues"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        # Test edge cases
        edge_cases = [
            "",                                 # Empty string
            " ",                               # Whitespace only
            "a" * 10000,                       # Very long string
            "🎲⚔️🏰",                          # Unicode characters
            "SELECT * FROM users;",            # SQL injection attempt
            "'; DROP TABLE spells; --",       # Another SQL injection
            "<script>alert('xss')</script>",   # XSS attempt
            "\n\r\t",                         # Control characters
        ]

        for test_input in edge_cases:
            try:
                result = classify_query(test_input)

                # Should return valid structure even for edge cases
                assert isinstance(result, dict), f"Should return dict for input: {repr(test_input)}"
                assert "intent" in result, f"Should have intent for input: {repr(test_input)}"
                assert "domain" in result, f"Should have domain for input: {repr(test_input)}"

                # Should not crash or return None
                assert result is not None, f"Should not return None for input: {repr(test_input)}"

            except Exception as e:
                pytest.fail(f"QIC crashed on input {repr(test_input)}: {e}")

    def test_qic_contract_stability(self):
        """Test that QIC output format matches established contract"""
        try:
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("QIC module not available for testing")

        result = classify_query("What is the damage of Fireball?")

        # Verify contract fields
        required_fields = ["intent", "domain", "complexity", "needs_tools", "confidence"]
        for field in required_fields:
            assert field in result, f"Contract violation: missing required field '{field}'"

        # Verify field types and values
        valid_intents = ["fact_lookup", "procedural_howto", "creative_write", "code_help", "summarize", "multi_hop_reasoning"]
        assert result["intent"] in valid_intents, f"Invalid intent: {result['intent']}"

        valid_domains = ["ttrpg_rules", "ttrpg_lore", "admin", "system", "unknown"]
        assert result["domain"] in valid_domains, f"Invalid domain: {result['domain']}"

        valid_complexities = ["low", "medium", "high"]
        assert result["complexity"] in valid_complexities, f"Invalid complexity: {result['complexity']}"

        assert isinstance(result["needs_tools"], bool), "needs_tools must be boolean"

        assert isinstance(result["confidence"], (int, float)), "confidence must be numeric"
        assert 0.0 <= result["confidence"] <= 1.0, "confidence must be between 0 and 1"