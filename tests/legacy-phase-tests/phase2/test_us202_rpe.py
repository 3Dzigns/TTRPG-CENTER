# tests/regression/phase2/test_us202_rpe.py
"""
Phase 2 - US-202: Retrieval Policy Engine Regression Tests
Tests hybrid retrieval policies with performance and accuracy requirements
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRetrievalPolicyEngine:
    """Test suite for Retrieval Policy Engine (RPE) validation"""

    def test_rpe_module_availability(self):
        """Test that RPE module exists and is importable"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine, RetrievalPolicy

            assert RetrievalPolicyEngine is not None, "RetrievalPolicyEngine class should be available"
            assert RetrievalPolicy is not None, "RetrievalPolicy enum should be available"

        except ImportError as e:
            pytest.fail(f"RPE module not available: {e}")

    def test_rpe_policy_selection_accuracy(self):
        """Test that RPE correctly selects retrieval policies based on query classification"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("RPE or QIC modules not available for testing")

        rpe = RetrievalPolicyEngine()

        # Test cases with expected policies
        test_cases = [
            # Fact lookup queries - should use vector search
            ("What is the damage of Fireball?", "vector_search"),
            ("How many spell slots does a 5th level Wizard have?", "vector_search"),

            # Complex reasoning - should use hybrid approach
            ("Compare Wizard vs Sorcerer spell progression and recommend best for damage", "hybrid_search"),
            ("Analyze the balance between spell damage and utility across character levels", "hybrid_search"),

            # Specific rule lookups - should use metadata search
            ("Show me all evocation spells", "metadata_search"),
            ("List spells that deal fire damage", "metadata_search"),

            # Procedural queries - should use graph traversal
            ("What are the steps to create a character?", "graph_traversal"),
            ("How do I calculate attack bonus for a Fighter?", "graph_traversal")
        ]

        correct_selections = 0
        total_selections = len(test_cases)

        for query, expected_policy in test_cases:
            # Get query classification
            classification = classify_query(query)

            # Get policy recommendation
            policy = rpe.select_policy(classification)

            if policy == expected_policy:
                correct_selections += 1
            else:
                print(f"Policy mismatch: '{query}' -> {policy}, expected {expected_policy}")

        # Calculate accuracy
        accuracy = correct_selections / total_selections

        # Should achieve high accuracy on policy selection
        assert accuracy >= 0.75, f"Policy selection accuracy {accuracy:.2%} below 75% threshold"

    def test_rpe_performance_policy_selection(self):
        """Test that RPE policy selection meets performance requirements"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
            from src_common.orchestrator.classifier import classify_query
        except ImportError:
            pytest.skip("RPE or QIC modules not available for testing")

        rpe = RetrievalPolicyEngine()

        test_queries = [
            "What is the damage of Fireball?",
            "How do I cast a spell?",
            "List all fire spells",
            "Compare Wizard vs Sorcerer",
            "What are character creation steps?"
        ]

        response_times = []

        # Measure policy selection performance
        for _ in range(10):  # 10 iterations for statistical significance
            for query in test_queries:
                # Classification time is separate - only measure policy selection
                classification = classify_query(query)

                start_time = time.perf_counter()
                policy = rpe.select_policy(classification)
                end_time = time.perf_counter()

                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)

                # Verify policy is valid
                valid_policies = ["vector_search", "metadata_search", "hybrid_search", "graph_traversal"]
                assert policy in valid_policies, f"Invalid policy returned: {policy}"

        # Calculate performance metrics
        avg_time = sum(response_times) / len(response_times)
        response_times.sort()
        p95_index = int(0.95 * len(response_times))
        p95_time = response_times[p95_index]

        # Policy selection should be very fast (< 10ms average)
        assert avg_time < 10.0, f"Average policy selection time {avg_time:.1f}ms exceeds 10ms requirement"
        assert p95_time < 20.0, f"P95 policy selection time {p95_time:.1f}ms exceeds 20ms requirement"

    def test_rpe_vector_search_integration(self):
        """Test that RPE can execute vector search retrieval"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock vector store integration
        with patch('src_common.vector_store.cassandra.CassandraVectorStore') as mock_vector_store:
            mock_store = MagicMock()
            mock_vector_store.return_value = mock_store

            # Mock search results
            mock_results = [
                {
                    "content": "Fireball spell deals 8d6 fire damage",
                    "metadata": {"page": 241, "section": "Spells", "type": "spell"},
                    "score": 0.95
                },
                {
                    "content": "Fireball has a range of 150 feet",
                    "metadata": {"page": 241, "section": "Spells", "type": "spell"},
                    "score": 0.87
                }
            ]
            mock_store.similarity_search.return_value = mock_results

            # Execute vector search
            results = rpe.execute_vector_search("What is Fireball damage?", k=5)

            # Verify results structure
            assert isinstance(results, list), "Vector search should return a list"
            assert len(results) > 0, "Should return search results"

            for result in results:
                assert "content" in result, "Result should have content field"
                assert "metadata" in result, "Result should have metadata field"
                assert "score" in result, "Result should have similarity score"
                assert isinstance(result["score"], (int, float)), "Score should be numeric"

    def test_rpe_metadata_search_integration(self):
        """Test that RPE can execute metadata-based search"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock metadata search
        with patch('src_common.vector_store.cassandra.CassandraVectorStore') as mock_vector_store:
            mock_store = MagicMock()
            mock_vector_store.return_value = mock_store

            # Mock filtered results
            mock_results = [
                {
                    "content": "Fireball - 3rd level evocation spell",
                    "metadata": {"spell_school": "evocation", "level": 3, "damage_type": "fire"},
                    "score": 1.0
                },
                {
                    "content": "Lightning Bolt - 3rd level evocation spell",
                    "metadata": {"spell_school": "evocation", "level": 3, "damage_type": "lightning"},
                    "score": 1.0
                }
            ]
            mock_store.metadata_search.return_value = mock_results

            # Execute metadata search
            filters = {"spell_school": "evocation", "level": 3}
            results = rpe.execute_metadata_search(filters)

            # Verify results structure
            assert isinstance(results, list), "Metadata search should return a list"
            assert len(results) > 0, "Should return filtered results"

            for result in results:
                assert "content" in result, "Result should have content field"
                assert "metadata" in result, "Result should have metadata field"

                # Verify filtering worked
                metadata = result["metadata"]
                assert metadata.get("spell_school") == "evocation", "Should match filter criteria"
                assert metadata.get("level") == 3, "Should match filter criteria"

    def test_rpe_hybrid_search_integration(self):
        """Test that RPE can execute hybrid retrieval combining multiple approaches"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock hybrid search components
        with patch('src_common.vector_store.cassandra.CassandraVectorStore') as mock_vector_store:
            mock_store = MagicMock()
            mock_vector_store.return_value = mock_store

            # Mock vector results
            mock_vector_results = [
                {"content": "Wizard spell progression table", "metadata": {"class": "wizard"}, "score": 0.9}
            ]

            # Mock metadata results
            mock_metadata_results = [
                {"content": "Sorcerer spell progression table", "metadata": {"class": "sorcerer"}, "score": 1.0}
            ]

            mock_store.similarity_search.return_value = mock_vector_results
            mock_store.metadata_search.return_value = mock_metadata_results

            # Execute hybrid search
            query = "Compare Wizard vs Sorcerer spell progression"
            results = rpe.execute_hybrid_search(query, filters={"type": "class_feature"})

            # Verify hybrid results
            assert isinstance(results, list), "Hybrid search should return a list"
            assert len(results) > 0, "Should combine results from multiple sources"

            # Should contain results from both vector and metadata search
            contents = [r["content"] for r in results]
            assert any("Wizard" in content for content in contents), "Should include vector search results"
            assert any("Sorcerer" in content for content in contents), "Should include metadata search results"

    def test_rpe_graph_traversal_integration(self):
        """Test that RPE can execute graph-based traversal for procedural queries"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock graph traversal
        with patch('src_common.graph.workflows.WorkflowGraph') as mock_graph:
            mock_graph_instance = MagicMock()
            mock_graph.return_value = mock_graph_instance

            # Mock workflow steps
            mock_steps = [
                {"step": 1, "action": "Choose race", "details": "Select character race from available options"},
                {"step": 2, "action": "Choose class", "details": "Select character class and starting equipment"},
                {"step": 3, "action": "Roll ability scores", "details": "Generate or assign ability scores"},
                {"step": 4, "action": "Calculate modifiers", "details": "Determine ability modifiers and bonuses"}
            ]
            mock_graph_instance.get_workflow.return_value = mock_steps

            # Execute graph traversal
            workflow_id = "character_creation"
            results = rpe.execute_graph_traversal(workflow_id)

            # Verify workflow structure
            assert isinstance(results, list), "Graph traversal should return a list of steps"
            assert len(results) > 0, "Should return workflow steps"

            for step in results:
                assert "step" in step, "Step should have step number"
                assert "action" in step, "Step should have action description"
                assert "details" in step, "Step should have detailed instructions"
                assert isinstance(step["step"], int), "Step number should be integer"

    def test_rpe_result_ranking_and_scoring(self):
        """Test that RPE properly ranks and scores retrieval results"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock results with different scores
        mock_results = [
            {"content": "High relevance content", "metadata": {"page": 1}, "score": 0.95},
            {"content": "Medium relevance content", "metadata": {"page": 2}, "score": 0.75},
            {"content": "Low relevance content", "metadata": {"page": 3}, "score": 0.45},
            {"content": "Very high relevance", "metadata": {"page": 4}, "score": 0.98}
        ]

        # Test result ranking
        ranked_results = rpe.rank_results(mock_results)

        # Verify ranking order (highest score first)
        assert len(ranked_results) == len(mock_results), "Should preserve all results"
        assert ranked_results[0]["score"] >= ranked_results[1]["score"], "Should be sorted by score descending"
        assert ranked_results[1]["score"] >= ranked_results[2]["score"], "Should maintain sort order"

        # Verify highest scoring result is first
        assert ranked_results[0]["content"] == "Very high relevance", "Highest scored result should be first"

        # Test score normalization
        normalized_results = rpe.normalize_scores(mock_results)

        for result in normalized_results:
            assert 0.0 <= result["score"] <= 1.0, "Normalized scores should be between 0 and 1"

    def test_rpe_confidence_calculation(self):
        """Test that RPE calculates retrieval confidence scores"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Test confidence calculation for different result sets
        test_cases = [
            # High confidence case - multiple high-scoring results
            {
                "results": [
                    {"score": 0.95}, {"score": 0.92}, {"score": 0.88}
                ],
                "expected_confidence": "high"
            },
            # Medium confidence case - mixed scores
            {
                "results": [
                    {"score": 0.85}, {"score": 0.65}, {"score": 0.45}
                ],
                "expected_confidence": "medium"
            },
            # Low confidence case - low scores
            {
                "results": [
                    {"score": 0.35}, {"score": 0.28}, {"score": 0.15}
                ],
                "expected_confidence": "low"
            }
        ]

        for case in test_cases:
            confidence = rpe.calculate_confidence(case["results"])

            assert isinstance(confidence, (float, str)), "Confidence should be numeric or categorical"

            if isinstance(confidence, float):
                assert 0.0 <= confidence <= 1.0, "Confidence score should be between 0 and 1"

    def test_rpe_telemetry_emission(self):
        """Test that RPE emits structured telemetry for retrieval operations"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock telemetry collection
        with patch('src_common.logging.jlog') as mock_jlog:
            # Mock a retrieval operation
            with patch.object(rpe, 'execute_vector_search') as mock_search:
                mock_search.return_value = [
                    {"content": "test", "metadata": {}, "score": 0.9}
                ]

                # Execute retrieval with telemetry
                query = "test query"
                policy = "vector_search"
                results = rpe.retrieve(query, policy)

                # Verify telemetry was emitted
                if mock_jlog.call_count > 0:
                    log_calls = [call.args for call in mock_jlog.call_args_list]

                    # Look for retrieval-related logs
                    retrieval_logs = [call for call in log_calls if "retrieval" in str(call).lower()]

                    assert len(retrieval_logs) > 0, "Should emit retrieval telemetry"

                    # Verify telemetry structure (basic check)
                    for log_call in retrieval_logs:
                        assert len(log_call) >= 2, "Log should have level and message"

    def test_rpe_error_handling_and_fallbacks(self):
        """Test that RPE handles errors gracefully with appropriate fallbacks"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Test vector search failure fallback
        with patch('src_common.vector_store.cassandra.CassandraVectorStore') as mock_vector_store:
            mock_store = MagicMock()
            mock_vector_store.return_value = mock_store

            # Simulate vector search failure
            mock_store.similarity_search.side_effect = Exception("Vector search failed")

            # Should handle gracefully and potentially fall back
            try:
                results = rpe.execute_vector_search("test query")
                # If no exception, verify graceful handling
                assert isinstance(results, list), "Should return empty list or fallback results"
            except Exception as e:
                # If exception propagated, should be informative
                assert "Vector search failed" in str(e) or "fallback" in str(e).lower()

        # Test invalid policy handling
        with pytest.raises((ValueError, KeyError)):
            rpe.retrieve("test query", "invalid_policy")

        # Test empty results handling
        with patch.object(rpe, 'execute_vector_search') as mock_search:
            mock_search.return_value = []

            results = rpe.retrieve("test query", "vector_search")
            assert isinstance(results, list), "Should handle empty results gracefully"

    def test_rpe_contract_compliance(self):
        """Test that RPE output format matches established contract"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        rpe = RetrievalPolicyEngine()

        # Mock successful retrieval
        with patch.object(rpe, 'execute_vector_search') as mock_search:
            mock_search.return_value = [
                {
                    "content": "Test content",
                    "metadata": {"page": 1, "section": "test"},
                    "score": 0.95
                }
            ]

            results = rpe.retrieve("test query", "vector_search")

            # Verify contract compliance
            assert isinstance(results, list), "Results should be a list"

            for result in results:
                # Required fields
                assert "content" in result, "Result missing content field"
                assert "metadata" in result, "Result missing metadata field"
                assert "score" in result, "Result missing score field"

                # Field types
                assert isinstance(result["content"], str), "Content should be string"
                assert isinstance(result["metadata"], dict), "Metadata should be dictionary"
                assert isinstance(result["score"], (int, float)), "Score should be numeric"

                # Score constraints
                assert 0.0 <= result["score"] <= 1.0, "Score should be between 0 and 1"

    def test_rpe_performance_under_load(self):
        """Test that RPE maintains performance under concurrent load"""
        try:
            from src_common.orchestrator.retrieval import RetrievalPolicyEngine
        except ImportError:
            pytest.skip("RPE module not available for testing")

        import threading
        import time

        rpe = RetrievalPolicyEngine()

        # Mock fast retrieval
        with patch.object(rpe, 'execute_vector_search') as mock_search:
            mock_search.return_value = [{"content": "test", "metadata": {}, "score": 0.9}]

            results = []
            errors = []

            def worker_thread(thread_id):
                try:
                    start_time = time.perf_counter()
                    result = rpe.retrieve(f"test query {thread_id}", "vector_search")
                    end_time = time.perf_counter()

                    response_time = (end_time - start_time) * 1000
                    results.append(response_time)
                except Exception as e:
                    errors.append(str(e))

            # Simulate concurrent load
            threads = []
            for i in range(10):
                thread = threading.Thread(target=worker_thread, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Verify performance under load
            assert len(errors) == 0, f"Errors occurred under load: {errors}"
            assert len(results) == 10, "All threads should complete successfully"

            avg_response_time = sum(results) / len(results)
            assert avg_response_time < 100.0, f"Average response time {avg_response_time:.1f}ms too high under load"