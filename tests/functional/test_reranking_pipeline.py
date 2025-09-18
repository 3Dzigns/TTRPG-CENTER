"""
Functional tests for Hybrid Reranking Pipeline Integration

Tests cover:
- End-to-end reranking pipeline with QueryPlanner
- Integration with retriever.py reranking
- Performance benchmarks
- Real-world query scenarios
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from src_common.orchestrator.query_planner import QueryPlanner
from src_common.orchestrator.plan_models import QueryPlan, PlanGenerationContext
from src_common.orchestrator.classifier import Classification
from src_common.orchestrator.hybrid_reranker import HybridReranker, RerankingConfig, RerankingStrategy
from src_common.orchestrator.retriever import retrieve, _apply_reranking, DocChunk


class MockClassification:
    """Mock classification for testing."""

    def __init__(self, intent="fact_lookup", domain="ttrpg_rules", complexity="medium"):
        self.intent = intent
        self.domain = domain
        self.complexity = complexity


@pytest.fixture
def mock_environment_setup():
    """Set up mock environment for testing."""
    with patch.dict('os.environ', {'APP_ENV': 'test'}):
        yield


@pytest.fixture
def sample_query_plan():
    """Sample QueryPlan for testing."""
    classification = MockClassification(intent="fact_lookup", domain="ttrpg_rules")

    return QueryPlan(
        query_hash="test_hash",
        original_query="What is fireball spell damage?",
        classification=classification,
        retrieval_strategy={"vector_top_k": 10, "graph_depth": 1},
        model_config={"provider": "openai", "model": "gpt-4"},
        performance_hints={"complexity": "medium"},
        graph_expansion={
            "enabled": True,
            "expanded_entities": [{"name": "fireball", "confidence": 0.9}]
        },
        reranking_config={
            "strategy": "domain_aware",
            "max_results": 10,
            "timeout_ms": 100,
            "weights": {
                "vector": 0.25,
                "graph": 0.25,
                "content": 0.25,
                "domain": 0.4,
                "metadata": 0.05
            }
        },
        cache_ttl=3600,
        created_at=time.time(),
        hit_count=0
    )


@pytest.fixture
def sample_doc_chunks():
    """Sample DocChunk results for testing."""
    return [
        DocChunk(
            id="chunk_1",
            text="Fireball: A 3rd-level evocation spell. You point your finger and determine a point within range where a ball of fire blooms. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.",
            source="phb.pdf",
            score=0.85,
            metadata={"source": "phb", "page": 241, "spell_level": 3}
        ),
        DocChunk(
            id="chunk_2",
            text="Magic Missile: A 1st-level evocation spell. You create three glowing darts of magical force. Each dart hits a creature of your choice that you can see within range. A dart deals 1d4 + 1 force damage to its target.",
            source="phb.pdf",
            score=0.65,
            metadata={"source": "phb", "page": 257, "spell_level": 1}
        ),
        DocChunk(
            id="chunk_3",
            text="Lightning Bolt: A 3rd-level evocation spell. A stroke of lightning forming a line 100 feet long and 5 feet wide blasts out from you in a direction you choose. Each creature in the line must make a Dexterity saving throw. A creature takes 8d6 lightning damage on a failed save, or half as much damage on a successful one.",
            source="phb.pdf",
            score=0.70,
            metadata={"source": "phb", "page": 255, "spell_level": 3}
        ),
        DocChunk(
            id="chunk_4",
            text="Spell Attack Rolls: Some spells require you to make an attack roll to determine whether the spell effect hits the intended target. Your attack bonus with a spell attack equals your spellcasting ability modifier plus your proficiency bonus.",
            source="phb.pdf",
            score=0.40,
            metadata={"source": "phb", "page": 205, "category": "general_rules"}
        )
    ]


class TestQueryPlannerReranking:
    """Test QueryPlanner integration with reranking."""

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_query_planner_generates_reranking_config(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test that QueryPlanner generates appropriate reranking configuration."""

        # Mock cache
        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        # Mock classification
        mock_classify.return_value = MockClassification(
            intent="fact_lookup",
            domain="ttrpg_rules",
            complexity="medium"
        )

        # Create QueryPlanner
        planner = QueryPlanner(environment="test")

        # Generate plan
        plan = planner.get_plan("What damage does fireball do?")

        # Verify reranking config was generated
        assert plan.reranking_config is not None
        assert "strategy" in plan.reranking_config
        assert "weights" in plan.reranking_config
        assert "max_results" in plan.reranking_config

        # Should be domain-aware for ttrpg_rules
        assert plan.reranking_config["strategy"] == "domain_aware"

        # Weights should emphasize domain signals
        weights = plan.reranking_config["weights"]
        assert weights["domain"] >= 0.3  # Should be high for domain queries

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_reranking_config_adaptation_by_query_type(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test reranking config adaptation for different query types."""

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        planner = QueryPlanner(environment="test")

        # Test fact lookup query
        mock_classify.return_value = MockClassification(intent="fact_lookup")
        plan_fact = planner.get_plan("What is AC?")
        assert plan_fact.reranking_config["strategy"] == "vector_only"

        # Test multi-hop reasoning query
        mock_classify.return_value = MockClassification(intent="multi_hop_reasoning")
        plan_reasoning = planner.get_plan("How do spells interact with armor?")
        assert plan_reasoning.reranking_config["strategy"] == "graph_enhanced"

        # Test high complexity query
        mock_classify.return_value = MockClassification(complexity="high")
        plan_complex = planner.get_plan("Explain the interaction between multiclassing spellcasting rules")
        assert plan_complex.reranking_config["strategy"] == "hybrid_full"


class TestRetrieverReranking:
    """Test retriever integration with reranking."""

    @patch('src_common.orchestrator.retriever._retrieve_from_store')
    @patch('src_common.orchestrator.retriever._iter_candidate_chunks')
    def test_retriever_applies_reranking_to_query_plan(
        self,
        mock_iter_chunks,
        mock_store_retrieve,
        sample_query_plan,
        sample_doc_chunks
    ):
        """Test that retriever applies reranking when QueryPlan has reranking config."""

        # Mock no AstraDB results, use local chunks
        mock_store_retrieve.return_value = []
        mock_iter_chunks.return_value = sample_doc_chunks

        with patch('src_common.orchestrator.retriever._apply_reranking') as mock_reranking:
            mock_reranking.return_value = sample_doc_chunks[:2]  # Return top 2

            results = retrieve(
                plan=sample_query_plan,
                query="What damage does fireball do?",
                env="test",
                limit=3
            )

            # Verify reranking was called
            mock_reranking.assert_called_once()
            call_args = mock_reranking.call_args

            assert call_args[0][1] == sample_query_plan  # plan argument
            assert call_args[0][2] == "What damage does fireball do?"  # query argument
            assert call_args[0][3] == "test"  # env argument

    @patch('src_common.orchestrator.retriever.HybridReranker')
    def test_apply_reranking_function(self, mock_reranker_class, sample_query_plan, sample_doc_chunks):
        """Test _apply_reranking function with QueryPlan."""

        # Mock reranker
        mock_reranker = Mock()
        mock_reranked_results = [
            Mock(
                original_result={
                    'id': chunk.id,
                    'content': chunk.text,
                    'score': chunk.score,
                    'metadata': chunk.metadata,
                    'source': chunk.source
                },
                final_score=chunk.score * 1.2  # Boost scores
            )
            for chunk in sample_doc_chunks[:2]  # Return top 2
        ]
        mock_reranker.rerank_results.return_value = mock_reranked_results
        mock_reranker_class.return_value = mock_reranker

        # Apply reranking
        reranked_chunks = _apply_reranking(
            results=sample_doc_chunks,
            plan=sample_query_plan,
            query="fireball damage",
            env="test"
        )

        # Verify reranker was created and called
        mock_reranker_class.assert_called_once_with(environment="test")
        mock_reranker.rerank_results.assert_called_once()

        # Verify results were converted back to DocChunk format
        assert len(reranked_chunks) == 2
        assert all(isinstance(chunk, DocChunk) for chunk in reranked_chunks)

        # Verify scores were updated
        for i, chunk in enumerate(reranked_chunks):
            expected_score = sample_doc_chunks[i].score * 1.2
            assert chunk.score == expected_score

    def test_apply_reranking_with_legacy_plan(self, sample_doc_chunks):
        """Test _apply_reranking with legacy dict plan (should skip reranking)."""

        legacy_plan = {"vector_top_k": 10, "graph_depth": 1}

        reranked_chunks = _apply_reranking(
            results=sample_doc_chunks,
            plan=legacy_plan,
            query="test query",
            env="test"
        )

        # Should return original results unchanged
        assert reranked_chunks == sample_doc_chunks

    def test_apply_reranking_disabled_config(self, sample_doc_chunks):
        """Test _apply_reranking when reranking is disabled."""

        classification = MockClassification()
        plan_no_reranking = QueryPlan(
            query_hash="test",
            original_query="test",
            classification=classification,
            retrieval_strategy={},
            model_config={},
            performance_hints={},
            reranking_config=None,  # No reranking config
            cache_ttl=3600,
            created_at=time.time()
        )

        reranked_chunks = _apply_reranking(
            results=sample_doc_chunks,
            plan=plan_no_reranking,
            query="test query",
            env="test"
        )

        # Should return original results unchanged
        assert reranked_chunks == sample_doc_chunks


class TestPerformanceBenchmarks:
    """Test reranking performance benchmarks."""

    @patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.GraphSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.ContentSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.DomainSignalExtractor')
    def test_reranking_performance_target(
        self,
        mock_domain,
        mock_content,
        mock_graph,
        mock_vector
    ):
        """Test that reranking meets performance targets (<50ms for 10-20 results)."""

        # Mock extractors to return quickly
        for mock_extractor in [mock_vector, mock_graph, mock_content, mock_domain]:
            mock_instance = Mock()
            mock_instance.extract_signals.return_value = {
                'test_signal': 0.5
            }
            mock_extractor.return_value = mock_instance

        reranker = HybridReranker(environment="test")

        # Create test results
        test_results = [
            {
                'id': f'result_{i}',
                'content': f'Test content {i} with some TTRPG terms like fireball and wizard.',
                'score': 0.5 + (i * 0.1),
                'metadata': {'source': 'phb'},
                'source': 'test.pdf'
            }
            for i in range(15)  # 15 results
        ]

        config = RerankingConfig(
            strategy=RerankingStrategy.HYBRID_FULL,
            max_results_to_rerank=15
        )

        # Measure reranking time
        start_time = time.perf_counter()
        reranked = reranker.rerank_results(
            query="fireball wizard spell",
            results=test_results,
            config=config
        )
        end_time = time.perf_counter()

        duration_ms = (end_time - start_time) * 1000

        # Performance target: <50ms for typical result sets
        assert duration_ms < 50.0, f"Reranking took {duration_ms:.2f}ms, expected <50ms"

        # Verify all results were processed
        assert len(reranked) == 15

        # Verify reranking time is recorded
        for result in reranked:
            assert result.reranking_time_ms > 0.0

    def test_reranking_scales_with_result_count(self):
        """Test that reranking performance scales reasonably with result count."""

        with patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor'), \
             patch('src_common.orchestrator.hybrid_reranker.GraphSignalExtractor'), \
             patch('src_common.orchestrator.hybrid_reranker.ContentSignalExtractor'), \
             patch('src_common.orchestrator.hybrid_reranker.DomainSignalExtractor'):

            reranker = HybridReranker(environment="test")

            # Test with different result counts
            for result_count in [5, 10, 20]:
                results = [
                    {
                        'id': f'result_{i}',
                        'content': f'Content {i}',
                        'score': 0.5,
                        'metadata': {},
                        'source': 'test.pdf'
                    }
                    for i in range(result_count)
                ]

                start_time = time.perf_counter()
                reranked = reranker.rerank_results(
                    query="test",
                    results=results
                )
                end_time = time.perf_counter()

                duration_ms = (end_time - start_time) * 1000

                # Should scale linearly or better
                assert duration_ms < result_count * 5.0  # <5ms per result


class TestRealWorldScenarios:
    """Test real-world query scenarios."""

    def create_spell_results(self):
        """Create realistic spell-related search results."""
        return [
            {
                'id': 'phb_fireball',
                'content': 'Fireball: 3rd-level evocation. Range: 150 feet. A bright streak flashes from your pointing finger to a point within range, then blossoms with a low roar into an explosion of flame. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.',
                'score': 0.9,
                'metadata': {'source': 'phb', 'page': 241, 'spell_level': 3, 'school': 'evocation'},
                'source': 'phb.pdf'
            },
            {
                'id': 'phb_spell_damage',
                'content': 'Damage Rolls: Each spell specifies the damage it deals. You roll the damage dice and add any relevant modifiers. Unless a spell has a perceptible effect, a creature might not know it was targeted by a spell at all.',
                'score': 0.7,
                'metadata': {'source': 'phb', 'page': 196, 'category': 'spellcasting_rules'},
                'source': 'phb.pdf'
            },
            {
                'id': 'phb_evocation_school',
                'content': 'Evocation: Evocation spells manipulate magical energy to produce a desired effect. Some call up blasts of fire or lightning. Others channel positive energy to heal wounds.',
                'score': 0.6,
                'metadata': {'source': 'phb', 'page': 117, 'category': 'magic_schools'},
                'source': 'phb.pdf'
            }
        ]

    @patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.GraphSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.ContentSignalExtractor')
    @patch('src_common.orchestrator.hybrid_reranker.DomainSignalExtractor')
    def test_spell_damage_query_scenario(
        self,
        mock_domain,
        mock_content,
        mock_graph,
        mock_vector
    ):
        """Test reranking for spell damage query scenario."""

        # Configure extractors for spell scenario
        mock_vector_instance = Mock()
        mock_vector_instance.extract_signals.side_effect = [
            {'similarity': 0.95, 'semantic': 0.9},  # Fireball - high relevance
            {'similarity': 0.8, 'semantic': 0.7},   # Damage rules - medium relevance
            {'similarity': 0.6, 'semantic': 0.5}    # Evocation - lower relevance
        ]
        mock_vector.return_value = mock_vector_instance

        mock_domain_instance = Mock()
        mock_domain_instance.extract_signals.side_effect = [
            {'entity_match': 0.9, 'mechanics': 0.8, 'authority': 1.0},  # Fireball
            {'entity_match': 0.6, 'mechanics': 0.9, 'authority': 1.0},  # Damage rules
            {'entity_match': 0.4, 'mechanics': 0.3, 'authority': 1.0}   # Evocation
        ]
        mock_domain.return_value = mock_domain_instance

        mock_content_instance = Mock()
        mock_content_instance.extract_signals.return_value = {
            'quality': 0.8, 'readability': 0.7, 'length_penalty': 0.1, 'structure': 0.6
        }
        mock_content.return_value = mock_content_instance

        mock_graph_instance = Mock()
        mock_graph_instance.extract_signals.return_value = {
            'relevance': 0.5, 'relationships': 0.4, 'cross_refs': 0.3
        }
        mock_graph.return_value = mock_graph_instance

        reranker = HybridReranker(environment="test")
        spell_results = self.create_spell_results()

        # Use domain-aware strategy for TTRPG rules
        config = RerankingConfig(
            strategy=RerankingStrategy.DOMAIN_AWARE,
            vector_weight=0.25,
            graph_weight=0.25,
            content_weight=0.25,
            domain_weight=0.4,
            metadata_weight=0.05
        )

        classification = MockClassification(
            intent="fact_lookup",
            domain="ttrpg_rules",
            complexity="medium"
        )

        reranked = reranker.rerank_results(
            query="fireball spell damage",
            results=spell_results,
            config=config,
            classification=classification
        )

        # Verify fireball result is ranked highest (most specific match)
        assert reranked[0].original_result['id'] == 'phb_fireball'

        # Verify all results have reasonable scores
        for result in reranked:
            assert 0.0 <= result.final_score <= 1.0
            assert result.reranking_time_ms > 0.0

    def test_comparison_query_scenario(self):
        """Test reranking for comparison queries (should favor graph signals)."""

        comparison_results = [
            {
                'id': 'fireball_vs_lightning',
                'content': 'Both fireball and lightning bolt are 3rd-level spells that deal 8d6 damage, but fireball affects a sphere while lightning bolt affects a line.',
                'score': 0.8,
                'metadata': {'source': 'comparison_guide', 'category': 'spell_comparison'},
                'source': 'guide.pdf'
            },
            {
                'id': 'fireball_solo',
                'content': 'Fireball deals 8d6 fire damage in a 20-foot radius.',
                'score': 0.9,
                'metadata': {'source': 'phb', 'page': 241},
                'source': 'phb.pdf'
            }
        ]

        with patch('src_common.orchestrator.hybrid_reranker.VectorSignalExtractor'), \
             patch('src_common.orchestrator.hybrid_reranker.GraphSignalExtractor') as mock_graph, \
             patch('src_common.orchestrator.hybrid_reranker.ContentSignalExtractor'), \
             patch('src_common.orchestrator.hybrid_reranker.DomainSignalExtractor'):

            # Graph extractor should boost comparison content
            mock_graph_instance = Mock()
            mock_graph_instance.extract_signals.side_effect = [
                {'relevance': 0.9, 'relationships': 0.8, 'cross_refs': 0.7},  # Comparison
                {'relevance': 0.4, 'relationships': 0.2, 'cross_refs': 0.1}   # Single spell
            ]
            mock_graph.return_value = mock_graph_instance

            reranker = HybridReranker(environment="test")

            # Use graph-enhanced strategy for comparison queries
            config = RerankingConfig(
                strategy=RerankingStrategy.GRAPH_ENHANCED,
                vector_weight=0.3,
                graph_weight=0.4,  # Emphasize graph signals
                content_weight=0.2,
                domain_weight=0.1
            )

            reranked = reranker.rerank_results(
                query="compare fireball vs lightning bolt",
                results=comparison_results,
                config=config
            )

            # Comparison result should be ranked higher despite lower initial score
            assert reranked[0].original_result['id'] == 'fireball_vs_lightning'