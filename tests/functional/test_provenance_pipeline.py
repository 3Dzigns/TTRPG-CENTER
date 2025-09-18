"""
Functional tests for Answer Provenance Pipeline Integration

Tests cover:
- End-to-end provenance tracking with QueryPlanner
- Integration with retrieval and reranking systems
- Complete answer lineage tracking
- Performance benchmarks
- Real-world answer provenance scenarios
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from src_common.orchestrator.query_planner import QueryPlanner
from src_common.orchestrator.plan_models import QueryPlan, PlanGenerationContext
from src_common.orchestrator.classifier import Classification
from src_common.orchestrator.provenance_tracker import ProvenanceTracker
from src_common.orchestrator.provenance_models import ProvenanceBundle, ProvenanceConfig
from src_common.orchestrator.retriever import retrieve, _apply_provenance_tracking, DocChunk


class MockClassification:
    """Mock classification for testing."""

    def __init__(self, intent="fact_lookup", domain="ttrpg_rules", complexity="medium", confidence=0.8):
        self.intent = intent
        self.domain = domain
        self.complexity = complexity
        self.confidence = confidence


@pytest.fixture
def mock_environment_setup():
    """Set up mock environment for testing."""
    with patch.dict('os.environ', {'APP_ENV': 'test'}):
        yield


@pytest.fixture
def sample_query_plan_with_provenance():
    """Sample QueryPlan with provenance configuration."""
    classification = MockClassification(intent="fact_lookup", domain="ttrpg_rules")

    return QueryPlan(
        query_hash="test_hash",
        original_query="What damage does fireball deal?",
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
            "weights": {"vector": 0.3, "graph": 0.2, "domain": 0.4, "content": 0.1}
        },
        provenance_config={
            "enabled": True,
            "track_query_processing": True,
            "track_retrieval": True,
            "track_reranking": True,
            "track_answer_generation": True,
            "detail_level": "full",
            "include_reasoning_steps": True
        },
        cache_ttl=3600,
        created_at=time.time(),
        hit_count=0
    )


@pytest.fixture
def sample_doc_chunks_with_metadata():
    """Sample DocChunk results with rich metadata."""
    return [
        DocChunk(
            id="fireball_main",
            text="Fireball: A 3rd-level evocation spell. You point your finger and determine a point within range where a ball of fire blooms. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.",
            source="phb.pdf",
            score=0.95,
            metadata={
                "source": "phb",
                "page": 241,
                "spell_level": 3,
                "school": "evocation",
                "damage_type": "fire",
                "save_type": "dexterity"
            }
        ),
        DocChunk(
            id="evocation_school",
            text="Evocation: Evocation spells manipulate magical energy to produce a desired effect. Some call up blasts of fire or lightning. Others channel positive energy to heal wounds.",
            source="phb.pdf",
            score=0.72,
            metadata={
                "source": "phb",
                "page": 117,
                "category": "magic_schools",
                "school": "evocation"
            }
        ),
        DocChunk(
            id="damage_rules",
            text="Damage Rolls: Each spell specifies the damage it deals. You roll the damage dice and add any relevant modifiers. Unless a spell has a perceptible effect, a creature might not know it was targeted by a spell at all.",
            source="phb.pdf",
            score=0.68,
            metadata={
                "source": "phb",
                "page": 196,
                "category": "spellcasting_rules",
                "topic": "damage"
            }
        )
    ]


class TestQueryPlannerProvenance:
    """Test QueryPlanner integration with provenance tracking."""

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_query_planner_generates_provenance_config(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test that QueryPlanner generates appropriate provenance configuration."""

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
        plan = planner.get_plan("What damage does fireball deal?")

        # Verify provenance config was generated
        assert plan.provenance_config is not None
        assert plan.provenance_config["enabled"] is True
        assert plan.provenance_config["track_query_processing"] is True
        assert plan.provenance_config["track_retrieval"] is True
        assert plan.provenance_config["detail_level"] in ["minimal", "standard", "full"]

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_provenance_config_adaptation_by_query_type(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test provenance config adaptation for different query types."""

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        planner = QueryPlanner(environment="test")

        # Test high complexity reasoning query
        mock_classify.return_value = MockClassification(
            intent="multi_hop_reasoning",
            complexity="high"
        )
        plan_complex = planner.get_plan("How do spell slots interact with multiclassing?")
        assert plan_complex.provenance_config["detail_level"] == "full"
        assert plan_complex.provenance_config["include_reasoning_steps"] is True

        # Test simple fact lookup
        mock_classify.return_value = MockClassification(
            intent="fact_lookup",
            complexity="low"
        )
        plan_simple = planner.get_plan("What is AC?")
        assert plan_simple.provenance_config["detail_level"] == "standard"
        assert plan_simple.provenance_config["include_reasoning_steps"] is False

        # Test TTRPG rules domain
        mock_classify.return_value = MockClassification(
            domain="ttrpg_rules"
        )
        plan_rules = planner.get_plan("How does advantage work?")
        assert plan_rules.provenance_config["include_signal_details"] is True
        assert plan_rules.provenance_config["track_source_authority"] is True

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_provenance_query_specific_adaptations(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test query-specific provenance adaptations."""

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        planner = QueryPlanner(environment="test")
        mock_classify.return_value = MockClassification()

        # Test reasoning-focused queries
        plan_why = planner.get_plan("Why does fireball require a Dexterity save?")
        assert plan_why.provenance_config["include_reasoning_steps"] is True
        assert plan_why.provenance_config["track_decision_points"] is True

        # Test source-focused queries
        plan_source = planner.get_plan("What sources mention fireball spell?")
        assert plan_source.provenance_config["enhanced_source_tracking"] is True
        assert plan_source.provenance_config["include_source_excerpts"] is True


class TestRetrieverProvenance:
    """Test retriever integration with provenance tracking."""

    @patch('src_common.orchestrator.retriever._retrieve_from_store')
    @patch('src_common.orchestrator.retriever._iter_candidate_chunks')
    def test_retriever_applies_provenance_tracking(
        self,
        mock_iter_chunks,
        mock_store_retrieve,
        sample_query_plan_with_provenance,
        sample_doc_chunks_with_metadata
    ):
        """Test that retriever applies provenance tracking when enabled."""

        # Mock no AstraDB results, use local chunks
        mock_store_retrieve.return_value = []
        mock_iter_chunks.return_value = sample_doc_chunks_with_metadata

        with patch('src_common.orchestrator.retriever._apply_provenance_tracking') as mock_provenance:
            mock_provenance.return_value = sample_doc_chunks_with_metadata

            results = retrieve(
                plan=sample_query_plan_with_provenance,
                query="What damage does fireball deal?",
                env="test",
                limit=3
            )

            # Verify provenance tracking was called
            mock_provenance.assert_called_once()
            call_args = mock_provenance.call_args

            assert call_args[0][1] == sample_query_plan_with_provenance  # plan argument
            assert call_args[0][2] == "What damage does fireball deal?"  # query argument
            assert call_args[0][3] == "test"  # env argument

    @patch('src_common.orchestrator.retriever.ProvenanceTracker')
    def test_apply_provenance_tracking_function(
        self,
        mock_tracker_class,
        sample_query_plan_with_provenance,
        sample_doc_chunks_with_metadata
    ):
        """Test _apply_provenance_tracking function with QueryPlan."""

        # Mock tracker
        mock_tracker = Mock()
        mock_bundle = Mock()
        mock_bundle.correlation_id = "test_correlation_id"
        mock_bundle.session_id = "test_session_id"
        mock_tracker.start_tracking.return_value = mock_bundle
        mock_tracker_class.return_value = mock_tracker

        # Apply provenance tracking
        tracked_chunks = _apply_provenance_tracking(
            results=sample_doc_chunks_with_metadata,
            plan=sample_query_plan_with_provenance,
            query="fireball damage",
            env="test"
        )

        # Verify tracker was created and called
        mock_tracker_class.assert_called_once_with(environment="test")
        mock_tracker.start_tracking.assert_called_once_with("fireball damage")
        mock_tracker.track_retrieval.assert_called_once()

        # Verify provenance metadata was added to results
        assert len(tracked_chunks) == len(sample_doc_chunks_with_metadata)
        for chunk in tracked_chunks:
            assert 'provenance_bundle_id' in chunk.metadata
            assert 'provenance_session_id' in chunk.metadata
            assert chunk.metadata['provenance_bundle_id'] == "test_correlation_id"

    def test_apply_provenance_tracking_with_legacy_plan(self, sample_doc_chunks_with_metadata):
        """Test _apply_provenance_tracking with legacy dict plan (should skip tracking)."""

        legacy_plan = {"vector_top_k": 10, "graph_depth": 1}

        tracked_chunks = _apply_provenance_tracking(
            results=sample_doc_chunks_with_metadata,
            plan=legacy_plan,
            query="test query",
            env="test"
        )

        # Should return original results unchanged
        assert tracked_chunks == sample_doc_chunks_with_metadata

    def test_apply_provenance_tracking_disabled(self, sample_doc_chunks_with_metadata):
        """Test _apply_provenance_tracking when provenance is disabled."""

        classification = MockClassification()
        plan_no_provenance = QueryPlan(
            query_hash="test",
            original_query="test",
            classification=classification,
            retrieval_strategy={},
            model_config={},
            performance_hints={},
            provenance_config=None,  # No provenance config
            cache_ttl=3600,
            created_at=time.time()
        )

        tracked_chunks = _apply_provenance_tracking(
            results=sample_doc_chunks_with_metadata,
            plan=plan_no_provenance,
            query="test query",
            env="test"
        )

        # Should return original results unchanged
        assert tracked_chunks == sample_doc_chunks_with_metadata


class TestEndToEndProvenance:
    """Test complete end-to-end provenance scenarios."""

    def create_complete_answer_scenario(self):
        """Create a complete answer scenario with full provenance."""
        return {
            "query": "What damage does fireball deal and how does it work?",
            "classification": MockClassification(
                intent="multi_hop_reasoning",
                domain="ttrpg_rules",
                complexity="medium"
            ),
            "retrieval_results": [
                {
                    "id": "fireball_damage",
                    "content": "Fireball deals 8d6 fire damage to creatures in a 20-foot radius sphere.",
                    "score": 0.95,
                    "source": "phb.pdf",
                    "metadata": {"page": 241, "spell_level": 3}
                },
                {
                    "id": "fireball_mechanics",
                    "content": "Each creature in the area must make a Dexterity saving throw. On a failed save, a creature takes full damage, or half damage on a successful save.",
                    "score": 0.88,
                    "source": "phb.pdf",
                    "metadata": {"page": 241, "spell_level": 3}
                },
                {
                    "id": "spell_targeting",
                    "content": "You point your finger and determine a point within range where the fireball blooms.",
                    "score": 0.75,
                    "source": "phb.pdf",
                    "metadata": {"page": 241, "spell_level": 3}
                }
            ],
            "reasoning_steps": [
                {
                    "type": "fact_lookup",
                    "description": "Find fireball damage information",
                    "input_sources": ["fireball_damage"],
                    "reasoning": "Located primary damage information in PHB",
                    "output": "8d6 fire damage",
                    "confidence": 0.95
                },
                {
                    "type": "fact_lookup",
                    "description": "Find saving throw mechanics",
                    "input_sources": ["fireball_mechanics"],
                    "reasoning": "Found Dexterity saving throw requirement",
                    "output": "Dexterity save for half damage",
                    "confidence": 0.9
                },
                {
                    "type": "synthesis",
                    "description": "Combine damage and mechanics",
                    "input_sources": ["fireball_damage", "fireball_mechanics", "spell_targeting"],
                    "reasoning": "Synthesized complete answer about fireball operation",
                    "output": "Complete fireball mechanics explanation",
                    "confidence": 0.85
                }
            ],
            "expected_answer": "Fireball deals 8d6 fire damage in a 20-foot radius. Creatures make a Dexterity saving throw, taking full damage on failure or half on success."
        }

    def test_complete_provenance_tracking_flow(self):
        """Test complete provenance tracking through entire answer pipeline."""

        scenario = self.create_complete_answer_scenario()
        tracker = ProvenanceTracker(environment="test")

        # Start tracking
        bundle = tracker.start_tracking(scenario["query"])

        # Track query processing
        strategy_info = {
            "selected": "hybrid_reasoning",
            "reason": "Multi-hop question requires graph and vector search",
            "alternatives": ["vector_only", "graph_enhanced"]
        }

        tracker.track_query_processing(
            bundle=bundle,
            original_query=scenario["query"],
            processed_query=scenario["query"].lower(),
            classification=scenario["classification"],
            strategy_info=strategy_info,
            processing_time_ms=25.0
        )

        # Track retrieval
        search_params = {
            "top_k": 10,
            "graph_expansion": True,
            "search_terms": ["fireball", "damage", "mechanics"],
            "strategy": "hybrid_vector_graph"
        }

        tracker.track_retrieval(
            bundle=bundle,
            strategy="hybrid_vector_graph",
            search_params=search_params,
            results=scenario["retrieval_results"],
            graph_data={"nodes_explored": 8, "relationships_found": 5},
            retrieval_time_ms=45.0
        )

        # Track reranking
        reranking_data = {
            "strategy": "domain_aware",
            "weights": {"vector": 0.3, "graph": 0.2, "domain": 0.4, "content": 0.1},
            "confidence": 0.88,
            "signal_agreement": 0.82
        }

        original_ranking = ["spell_targeting", "fireball_damage", "fireball_mechanics"]
        final_ranking = ["fireball_damage", "fireball_mechanics", "spell_targeting"]

        tracker.track_reranking(
            bundle=bundle,
            reranking_data=reranking_data,
            original_results=original_ranking,
            reranked_results=final_ranking,
            reranking_time_ms=18.0
        )

        # Track answer generation
        generation_config = {
            "model": "gpt-4",
            "strategy": "multi_step_reasoning",
            "temperature": 0.7,
            "max_tokens": 300
        }

        source_usage = {
            "primary": ["fireball_damage", "fireball_mechanics"],
            "supporting": ["spell_targeting"],
            "contradictory": []
        }

        answer_metrics = {
            "confidence": 0.87,
            "completeness": 0.92,
            "length": len(scenario["expected_answer"]),
            "citations": 2,
            "fact_density": 0.8
        }

        tracker.track_answer_generation(
            bundle=bundle,
            generation_config=generation_config,
            reasoning_steps=scenario["reasoning_steps"],
            source_usage=source_usage,
            answer_metrics=answer_metrics,
            generation_time_ms=150.0
        )

        # Calculate quality metrics and finalize
        metrics = tracker.calculate_quality_metrics(bundle)
        finalized_bundle = tracker.finalize_bundle(bundle)

        # Verify complete provenance chain
        assert finalized_bundle.query_provenance is not None
        assert finalized_bundle.retrieval_provenance is not None
        assert finalized_bundle.reranking_provenance is not None
        assert finalized_bundle.answer_provenance is not None
        assert finalized_bundle.quality_metrics is not None

        # Verify query provenance
        query_prov = finalized_bundle.query_provenance
        assert query_prov.intent == "multi_hop_reasoning"
        assert query_prov.strategy_selected == "hybrid_reasoning"
        assert len(query_prov.alternative_strategies) == 2

        # Verify retrieval provenance
        retrieval_prov = finalized_bundle.retrieval_provenance
        assert retrieval_prov.strategy == "hybrid_vector_graph"
        assert retrieval_prov.results_returned == 3
        assert len(retrieval_prov.sources_found) == 3
        assert retrieval_prov.graph_nodes_explored == 8

        # Verify reranking provenance
        reranking_prov = finalized_bundle.reranking_provenance
        assert reranking_prov.strategy == "domain_aware"
        assert reranking_prov.ranking_confidence == 0.88
        assert len(reranking_prov.ranking_changes) > 0

        # Verify answer provenance
        answer_prov = finalized_bundle.answer_provenance
        assert answer_prov.model_used == "gpt-4"
        assert len(answer_prov.reasoning_steps) == 3
        assert len(answer_prov.primary_sources) == 2
        assert answer_prov.answer_confidence == 0.87

        # Verify quality metrics
        assert 0.8 <= metrics.overall_confidence <= 1.0
        assert metrics.source_diversity >= 1
        assert metrics.official_source_count >= 0

        # Verify timeline
        assert finalized_bundle.total_time_ms > 0
        assert finalized_bundle.completed_at is not None

        # Verify stage completion
        stage_status = finalized_bundle.get_stage_status()
        assert all(stage_status.values())  # All stages should be complete

    def test_provenance_performance_benchmark(self):
        """Test that provenance tracking meets performance targets."""

        tracker = ProvenanceTracker(environment="test")
        classification = MockClassification()

        # Create realistic data volume
        large_results = [
            {
                "id": f"result_{i}",
                "content": f"Test content {i} with detailed information about spells and mechanics.",
                "score": 0.8 - (i * 0.05),
                "source": "phb.pdf",
                "metadata": {"page": 100 + i, "category": "spells"}
            }
            for i in range(20)  # 20 results
        ]

        large_reasoning_steps = [
            {
                "type": "fact_lookup",
                "description": f"Step {i} analysis",
                "input_sources": [f"result_{i}"],
                "reasoning": f"Detailed reasoning for step {i}",
                "output": f"Output {i}",
                "confidence": 0.8
            }
            for i in range(10)  # 10 reasoning steps
        ]

        # Measure complete tracking performance
        start_time = time.perf_counter()

        bundle = tracker.start_tracking("performance test query")

        tracker.track_query_processing(
            bundle, "test query", "test query", classification,
            {"selected": "hybrid"}, 10.0
        )

        tracker.track_retrieval(
            bundle, "hybrid", {"top_k": 20}, large_results,
            {"nodes_explored": 15}, 30.0
        )

        tracker.track_reranking(
            bundle, {"strategy": "hybrid", "weights": {"vector": 0.5}},
            [f"result_{i}" for i in range(20)],
            [f"result_{i}" for i in range(20)], 20.0
        )

        tracker.track_answer_generation(
            bundle, {"model": "gpt-4"}, large_reasoning_steps,
            {"primary": ["result_0"]}, {"confidence": 0.8}, 100.0
        )

        tracker.calculate_quality_metrics(bundle)
        tracker.finalize_bundle(bundle)

        end_time = time.perf_counter()
        total_tracking_time_ms = (end_time - start_time) * 1000

        # Should meet <50ms performance target
        assert total_tracking_time_ms < 50.0

        # Verify all data was tracked
        assert bundle.query_provenance is not None
        assert bundle.retrieval_provenance is not None
        assert bundle.reranking_provenance is not None
        assert bundle.answer_provenance is not None
        assert len(bundle.answer_provenance.reasoning_steps) == 10
        assert len(bundle.all_sources) == 20

    def test_provenance_source_attribution_accuracy(self):
        """Test accuracy of source attribution in provenance tracking."""

        scenario = self.create_complete_answer_scenario()
        tracker = ProvenanceTracker(environment="test")

        bundle = tracker.start_tracking(scenario["query"])

        # Track retrieval with detailed source information
        tracker.track_retrieval(
            bundle=bundle,
            strategy="vector_search",
            search_params={"top_k": 3},
            results=scenario["retrieval_results"],
            retrieval_time_ms=30.0
        )

        # Track answer generation with source usage
        source_usage = {
            "primary": ["fireball_damage", "fireball_mechanics"],
            "supporting": ["spell_targeting"],
            "contradictory": []
        }

        tracker.track_answer_generation(
            bundle=bundle,
            generation_config={"model": "gpt-4"},
            reasoning_steps=scenario["reasoning_steps"],
            source_usage=source_usage,
            answer_metrics={"confidence": 0.9},
            generation_time_ms=100.0
        )

        tracker.finalize_bundle(bundle)

        # Verify source attribution accuracy
        primary_sources = bundle.get_primary_sources()
        assert len(primary_sources) == 2  # Should match primary sources

        # Check specific source details
        fireball_damage_source = next(
            (s for s in bundle.all_sources if s.source_id == "fireball_damage"), None
        )
        assert fireball_damage_source is not None
        assert fireball_damage_source.used_in_answer is True
        assert fireball_damage_source.source_type == "phb"
        assert fireball_damage_source.page_number == 241

        # Verify confidence scores are preserved
        for source in bundle.all_sources:
            assert 0.0 <= source.confidence_score <= 1.0
            assert 0.0 <= source.relevance_score <= 1.0

    def test_provenance_reasoning_chain_tracking(self):
        """Test detailed reasoning chain tracking."""

        scenario = self.create_complete_answer_scenario()
        tracker = ProvenanceTracker(environment="test")

        bundle = tracker.start_tracking(scenario["query"])

        # Track with detailed reasoning steps
        tracker.track_answer_generation(
            bundle=bundle,
            generation_config={"model": "gpt-4", "strategy": "step_by_step"},
            reasoning_steps=scenario["reasoning_steps"],
            source_usage={"primary": ["fireball_damage", "fireball_mechanics"]},
            answer_metrics={"confidence": 0.88},
            generation_time_ms=120.0
        )

        tracker.finalize_bundle(bundle)

        # Verify reasoning chain completeness
        reasoning_steps = bundle.answer_provenance.reasoning_steps
        assert len(reasoning_steps) == 3

        # Check step progression
        fact_steps = [s for s in reasoning_steps if s.step_type == "fact_lookup"]
        synthesis_steps = [s for s in reasoning_steps if s.step_type == "synthesis"]

        assert len(fact_steps) == 2
        assert len(synthesis_steps) == 1

        # Verify confidence progression
        confidences = [step.confidence for step in reasoning_steps]
        assert all(0.8 <= conf <= 1.0 for conf in confidences)

        # Verify source linkage
        step1 = reasoning_steps[0]
        assert "fireball_damage" in step1.input_sources
        assert step1.confidence == 0.95

        synthesis_step = synthesis_steps[0]
        assert len(synthesis_step.input_sources) == 3
        assert synthesis_step.confidence == 0.85