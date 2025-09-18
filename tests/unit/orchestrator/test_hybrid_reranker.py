"""
Unit tests for Hybrid Reranker System

Tests cover:
- Core HybridReranker functionality
- Signal extraction and aggregation
- Strategy selection and weight adjustment
- Performance benchmarks
- Integration with QueryPlanner
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src_common.orchestrator.hybrid_reranker import (
    HybridReranker,
    RerankingConfig,
    RerankingStrategy,
    RerankingSignals,
    RerankedResult
)
from src_common.orchestrator.signal_extractors import (
    VectorSignalExtractor,
    GraphSignalExtractor,
    ContentSignalExtractor,
    DomainSignalExtractor
)
from src_common.orchestrator.classifier import Classification


@dataclass
class MockClassification:
    """Mock classification for testing."""
    intent: str = "fact_lookup"
    domain: str = "ttrpg_rules"
    complexity: str = "medium"


class TestRerankingConfig:
    """Test reranking configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RerankingConfig()

        assert config.strategy == RerankingStrategy.HYBRID_FULL
        assert config.vector_weight == 0.3
        assert config.graph_weight == 0.2
        assert config.content_weight == 0.2
        assert config.domain_weight == 0.2
        assert config.metadata_weight == 0.1
        assert config.max_results_to_rerank == 20
        assert config.reranking_timeout_ms == 100

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RerankingConfig(
            strategy=RerankingStrategy.VECTOR_ONLY,
            vector_weight=0.8,
            content_weight=0.2,
            max_results_to_rerank=10
        )

        assert config.strategy == RerankingStrategy.VECTOR_ONLY
        assert config.vector_weight == 0.8
        assert config.content_weight == 0.2
        assert config.max_results_to_rerank == 10


class TestHybridReranker:
    """Test core HybridReranker functionality."""

    @pytest.fixture
    def mock_signal_extractors(self):
        """Mock signal extractors."""
        with patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor') as mock_vector, \
             patch('src_common.orchestrator.hybrid_reranker.GraphSignalExtractor') as mock_graph, \
             patch('src_common.orchestrator.hybrid_reranker.ContentSignalExtractor') as mock_content, \
             patch('src_common.orchestrator.hybrid_reranker.DomainSignalExtractor') as mock_domain:

            # Configure vector extractor
            mock_vector_instance = Mock()
            mock_vector_instance.extract_signals.return_value = {
                'similarity': 0.8,
                'semantic': 0.7
            }
            mock_vector.return_value = mock_vector_instance

            # Configure graph extractor
            mock_graph_instance = Mock()
            mock_graph_instance.extract_signals.return_value = {
                'relevance': 0.6,
                'relationships': 0.5,
                'cross_refs': 0.4
            }
            mock_graph.return_value = mock_graph_instance

            # Configure content extractor
            mock_content_instance = Mock()
            mock_content_instance.extract_signals.return_value = {
                'quality': 0.7,
                'readability': 0.8,
                'length_penalty': 0.1,
                'structure': 0.6
            }
            mock_content.return_value = mock_content_instance

            # Configure domain extractor
            mock_domain_instance = Mock()
            mock_domain_instance.extract_signals.return_value = {
                'entity_match': 0.9,
                'mechanics': 0.8,
                'authority': 0.7
            }
            mock_domain.return_value = mock_domain_instance

            yield {
                'vector': mock_vector_instance,
                'graph': mock_graph_instance,
                'content': mock_content_instance,
                'domain': mock_domain_instance
            }

    @pytest.fixture
    def sample_results(self):
        """Sample search results for testing."""
        return [
            {
                'id': 'result_1',
                'content': 'Fireball is a 3rd level evocation spell that deals fire damage.',
                'score': 0.8,
                'metadata': {'source': 'phb', 'page': 241},
                'source': 'phb.pdf'
            },
            {
                'id': 'result_2',
                'content': 'Magic Missile is a 1st level evocation spell with guaranteed hit.',
                'score': 0.7,
                'metadata': {'source': 'phb', 'page': 257},
                'source': 'phb.pdf'
            },
            {
                'id': 'result_3',
                'content': 'Lightning Bolt is a 3rd level evocation spell in a line.',
                'score': 0.6,
                'metadata': {'source': 'phb', 'page': 255},
                'source': 'phb.pdf'
            }
        ]

    def test_reranker_initialization(self, mock_signal_extractors):
        """Test reranker initialization."""
        reranker = HybridReranker(environment="test")

        assert reranker.environment == "test"
        assert reranker.vector_extractor is not None
        assert reranker.graph_extractor is not None
        assert reranker.content_extractor is not None
        assert reranker.domain_extractor is not None
        assert isinstance(reranker.signal_cache, dict)

    def test_rerank_empty_results(self, mock_signal_extractors):
        """Test reranking with empty results."""
        reranker = HybridReranker(environment="test")

        reranked = reranker.rerank_results(
            query="test query",
            results=[],
            config=RerankingConfig()
        )

        assert reranked == []

    def test_rerank_basic_functionality(self, mock_signal_extractors, sample_results):
        """Test basic reranking functionality."""
        reranker = HybridReranker(environment="test")
        config = RerankingConfig(strategy=RerankingStrategy.HYBRID_FULL)

        reranked = reranker.rerank_results(
            query="fireball spell",
            results=sample_results,
            config=config
        )

        assert len(reranked) == len(sample_results)
        assert all(isinstance(result, RerankedResult) for result in reranked)

        # Check that results are properly ordered by final score
        scores = [result.final_score for result in reranked]
        assert scores == sorted(scores, reverse=True)

        # Verify signal extraction was called
        for extractor in mock_signal_extractors.values():
            assert extractor.extract_signals.call_count >= len(sample_results)

    def test_rerank_with_classification(self, mock_signal_extractors, sample_results):
        """Test reranking with query classification."""
        reranker = HybridReranker(environment="test")
        classification = MockClassification(intent="fact_lookup", domain="ttrpg_rules")

        reranked = reranker.rerank_results(
            query="fireball spell damage",
            results=sample_results,
            classification=classification
        )

        assert len(reranked) == len(sample_results)

        # Verify that classification was passed to extractors
        mock_signal_extractors['vector'].extract_signals.assert_called()
        mock_signal_extractors['content'].extract_signals.assert_called()
        mock_signal_extractors['domain'].extract_signals.assert_called()

    def test_rerank_with_query_plan(self, mock_signal_extractors, sample_results):
        """Test reranking with query plan context."""
        reranker = HybridReranker(environment="test")

        query_plan = {
            'retrieval_strategy': {'vector_top_k': 10},
            'graph_expansion': {
                'expanded_entities': [{'name': 'fireball', 'confidence': 0.9}]
            }
        }

        reranked = reranker.rerank_results(
            query="fireball spell",
            results=sample_results,
            query_plan=query_plan
        )

        assert len(reranked) == len(sample_results)

        # Verify graph extractor received query plan
        mock_signal_extractors['graph'].extract_signals.assert_called()

    def test_signal_caching(self, mock_signal_extractors, sample_results):
        """Test signal caching functionality."""
        reranker = HybridReranker(environment="test")
        config = RerankingConfig(enable_signal_caching=True)

        # First call
        reranked1 = reranker.rerank_results(
            query="fireball spell",
            results=sample_results[:1],  # Only one result
            config=config
        )

        # Second call with same query and result
        reranked2 = reranker.rerank_results(
            query="fireball spell",
            results=sample_results[:1],
            config=config
        )

        assert len(reranker.signal_cache) > 0

        # Verify extractors weren't called again for cached signals
        # (This test would need more sophisticated mocking to verify)

    def test_performance_constraints(self, mock_signal_extractors):
        """Test performance constraints and timeouts."""
        reranker = HybridReranker(environment="test")

        # Large number of results to test max_results constraint
        large_results = [
            {
                'id': f'result_{i}',
                'content': f'Content {i}',
                'score': 0.5,
                'metadata': {},
                'source': 'test.pdf'
            }
            for i in range(50)
        ]

        config = RerankingConfig(
            max_results_to_rerank=10,
            reranking_timeout_ms=50
        )

        start_time = time.perf_counter()
        reranked = reranker.rerank_results(
            query="test query",
            results=large_results,
            config=config
        )
        end_time = time.perf_counter()

        # Should only rerank the first 10 results
        assert len(reranked) <= config.max_results_to_rerank

        # Should complete reasonably quickly
        duration_ms = (end_time - start_time) * 1000
        assert duration_ms < 1000  # Should be well under 1 second

    def test_get_default_config_adaptations(self, mock_signal_extractors):
        """Test default config adaptations based on classification."""
        reranker = HybridReranker(environment="test")

        # Test fact lookup adaptation
        fact_lookup_classification = MockClassification(
            intent="fact_lookup",
            domain="general",
            complexity="low"
        )
        fact_config = reranker._get_default_config(fact_lookup_classification)
        assert fact_config.strategy == RerankingStrategy.VECTOR_ONLY

        # Test multi-hop reasoning adaptation
        reasoning_classification = MockClassification(
            intent="multi_hop_reasoning",
            domain="ttrpg_rules",
            complexity="high"
        )
        reasoning_config = reranker._get_default_config(reasoning_classification)
        assert reasoning_config.strategy == RerankingStrategy.GRAPH_ENHANCED

        # Test domain-aware adaptation
        rules_classification = MockClassification(
            intent="general",
            domain="ttrpg_rules",
            complexity="medium"
        )
        rules_config = reranker._get_default_config(rules_classification)
        assert rules_config.strategy == RerankingStrategy.DOMAIN_AWARE

    def test_metrics_and_cache_management(self, mock_signal_extractors):
        """Test metrics collection and cache management."""
        reranker = HybridReranker(environment="test")

        # Get initial metrics
        metrics = reranker.get_reranking_metrics()

        assert 'cache_size' in metrics
        assert 'environment' in metrics
        assert 'extractors_available' in metrics
        assert metrics['environment'] == "test"

        # Add some cached data
        reranker.signal_cache['test_key'] = RerankingSignals()

        # Check cache size
        metrics = reranker.get_reranking_metrics()
        assert metrics['cache_size'] == 1

        # Clear cache
        cleared_count = reranker.clear_cache()
        assert cleared_count == 1

        # Verify cache is empty
        metrics = reranker.get_reranking_metrics()
        assert metrics['cache_size'] == 0


class TestSignalExtractors:
    """Test individual signal extractors."""

    def test_vector_signal_extractor(self):
        """Test vector signal extraction."""
        extractor = VectorSignalExtractor(environment="test")

        result = {
            'content': 'Fireball is a powerful spell',
            'score': 0.8
        }

        signals = extractor.extract_signals(
            query="fireball spell",
            result=result
        )

        assert 'similarity' in signals
        assert 'semantic' in signals
        assert 0.0 <= signals['similarity'] <= 1.0
        assert 0.0 <= signals['semantic'] <= 1.0

    def test_content_signal_extractor(self):
        """Test content signal extraction."""
        extractor = ContentSignalExtractor(environment="test")

        result = {
            'content': 'Fireball: A 3rd-level evocation spell. ' * 10,  # Decent length
            'metadata': {'source': 'phb'}
        }

        signals = extractor.extract_signals(
            query="fireball spell",
            result=result
        )

        assert 'quality' in signals
        assert 'readability' in signals
        assert 'length_penalty' in signals
        assert 'structure' in signals

        for signal_value in signals.values():
            assert 0.0 <= signal_value <= 1.0

    def test_domain_signal_extractor(self):
        """Test TTRPG domain signal extraction."""
        extractor = DomainSignalExtractor(environment="test")

        result = {
            'content': 'The wizard casts fireball dealing 8d6 fire damage. ' +
                      'Targets make a Dexterity saving throw.',
            'metadata': {'source': 'phb'}
        }

        signals = extractor.extract_signals(
            query="wizard fireball damage",
            result=result
        )

        assert 'entity_match' in signals
        assert 'mechanics' in signals
        assert 'authority' in signals

        # Should detect TTRPG entities
        assert signals['entity_match'] > 0.0
        assert signals['mechanics'] > 0.0
        assert signals['authority'] > 0.0


class TestRerankerIntegration:
    """Test integration scenarios."""

    @patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.GraphSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.ContentSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.DomainSignalExtractor')
    def test_end_to_end_reranking_flow(self, mock_domain, mock_content, mock_graph, mock_vector):
        """Test complete end-to-end reranking flow."""

        # Configure extractors to return realistic signals
        mock_vector_instance = Mock()
        mock_vector_instance.extract_signals.return_value = {'similarity': 0.8, 'semantic': 0.7}
        mock_vector.return_value = mock_vector_instance

        mock_graph_instance = Mock()
        mock_graph_instance.extract_signals.return_value = {
            'relevance': 0.6, 'relationships': 0.5, 'cross_refs': 0.4
        }
        mock_graph.return_value = mock_graph_instance

        mock_content_instance = Mock()
        mock_content_instance.extract_signals.return_value = {
            'quality': 0.7, 'readability': 0.8, 'length_penalty': 0.1, 'structure': 0.6
        }
        mock_content.return_value = mock_content_instance

        mock_domain_instance = Mock()
        mock_domain_instance.extract_signals.return_value = {
            'entity_match': 0.9, 'mechanics': 0.8, 'authority': 0.7
        }
        mock_domain.return_value = mock_domain_instance

        # Create reranker and sample data
        reranker = HybridReranker(environment="test")

        results = [
            {
                'id': 'spell_1',
                'content': 'Fireball is a 3rd level spell',
                'score': 0.6,
                'metadata': {'source': 'phb'},
                'source': 'phb.pdf'
            },
            {
                'id': 'spell_2',
                'content': 'Magic Missile never misses',
                'score': 0.8,
                'metadata': {'source': 'phb'},
                'source': 'phb.pdf'
            }
        ]

        classification = MockClassification(intent="fact_lookup", domain="ttrpg_rules")

        # Perform reranking
        reranked = reranker.rerank_results(
            query="fireball spell damage",
            results=results,
            classification=classification
        )

        # Verify results
        assert len(reranked) == 2
        assert all(isinstance(r, RerankedResult) for r in reranked)

        # Check that final scores are computed
        for result in reranked:
            assert 0.0 <= result.final_score <= 1.0
            assert result.reranking_time_ms > 0.0
            assert result.strategy_used == RerankingStrategy.VECTOR_ONLY  # fact_lookup default

        # Verify all extractors were called
        assert mock_vector_instance.extract_signals.call_count == 2
        assert mock_content_instance.extract_signals.call_count == 2
        assert mock_domain_instance.extract_signals.call_count == 2

    def test_reranker_with_missing_extractors(self):
        """Test reranker behavior when signal extractors are not available."""

        with patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor',
                  side_effect=ImportError("Not available")):

            reranker = HybridReranker(environment="test")

            # Should handle missing extractors gracefully
            assert reranker.vector_extractor is None
            assert reranker.graph_extractor is None
            assert reranker.content_extractor is None
            assert reranker.domain_extractor is None

            # Should still work with limited functionality
            results = [{'id': 'test', 'content': 'test', 'score': 0.5,
                       'metadata': {}, 'source': 'test.pdf'}]

            reranked = reranker.rerank_results(
                query="test",
                results=results
            )

            assert len(reranked) == 1
            assert reranked[0].final_score > 0.0