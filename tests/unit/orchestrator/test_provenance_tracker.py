"""
Unit tests for Answer Provenance Tracker

Tests cover:
- Provenance data models and structures
- ProvenanceTracker core functionality
- Pipeline stage tracking
- Quality metrics calculation
- Integration with QueryPlanner
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src_common.orchestrator.provenance_tracker import ProvenanceTracker
from src_common.orchestrator.provenance_models import (
    ProvenanceBundle,
    ProvenanceConfig,
    QueryProvenance,
    RetrievalProvenance,
    RerankingProvenance,
    AnswerProvenance,
    QualityMetrics,
    SourceAttribution,
    ReasoningStep,
    ConfidenceLevel,
    create_confidence_level,
    calculate_source_diversity,
    aggregate_confidence_scores
)


@dataclass
class MockClassification:
    """Mock classification for testing."""
    intent: str = "fact_lookup"
    domain: str = "ttrpg_rules"
    complexity: str = "medium"
    confidence: float = 0.8


class TestProvenanceModels:
    """Test provenance data models."""

    def test_source_attribution_creation(self):
        """Test SourceAttribution creation and properties."""
        source = SourceAttribution(
            source_id="test_source",
            source_path="phb.pdf",
            source_type="phb",
            page_number=42,
            relevance_score=0.8,
            confidence_score=0.9
        )

        assert source.source_id == "test_source"
        assert source.source_path == "phb.pdf"
        assert source.source_type == "phb"
        assert source.page_number == 42
        assert source.relevance_score == 0.8
        assert source.confidence_score == 0.9
        assert source.used_in_answer is False
        assert source.contribution_weight == 0.0

    def test_confidence_level_creation(self):
        """Test confidence level classification."""
        assert create_confidence_level(0.95) == ConfidenceLevel.VERY_HIGH
        assert create_confidence_level(0.8) == ConfidenceLevel.HIGH
        assert create_confidence_level(0.6) == ConfidenceLevel.MEDIUM
        assert create_confidence_level(0.4) == ConfidenceLevel.LOW
        assert create_confidence_level(0.2) == ConfidenceLevel.VERY_LOW

    def test_source_diversity_calculation(self):
        """Test source diversity calculation."""
        sources = [
            SourceAttribution(source_id="1", source_path="phb.pdf", source_type="phb"),
            SourceAttribution(source_id="2", source_path="dmg.pdf", source_type="dmg"),
            SourceAttribution(source_id="3", source_path="custom.pdf", source_type="homebrew")
        ]

        diversity = calculate_source_diversity(sources)
        assert 0.0 <= diversity <= 1.0
        assert diversity > 0.5  # Should be high due to variety

        # Test with empty sources
        assert calculate_source_diversity([]) == 0.0

    def test_confidence_aggregation(self):
        """Test confidence score aggregation."""
        scores = [0.8, 0.7, 0.9]
        aggregated = aggregate_confidence_scores(scores)
        assert 0.0 <= aggregated <= 1.0
        assert aggregated < min(scores)  # Harmonic mean is conservative

        # Test with empty scores
        assert aggregate_confidence_scores([]) == 0.0

        # Test with single score
        assert aggregate_confidence_scores([0.8]) == 0.8

    def test_provenance_bundle_creation(self):
        """Test ProvenanceBundle creation and methods."""
        bundle = ProvenanceBundle(environment="test")

        assert bundle.environment == "test"
        assert bundle.session_id is not None
        assert bundle.correlation_id is not None
        assert bundle.completed_at is None

        # Test stage status
        status = bundle.get_stage_status()
        assert all(not completed for completed in status.values())

        # Test marking completed
        bundle.mark_completed()
        assert bundle.completed_at is not None
        assert bundle.total_time_ms > 0

    def test_provenance_config_defaults(self):
        """Test ProvenanceConfig default values."""
        config = ProvenanceConfig()

        assert config.enabled is True
        assert config.track_query_processing is True
        assert config.track_retrieval is True
        assert config.track_reranking is True
        assert config.track_answer_generation is True
        assert config.max_tracking_time_ms == 50
        assert config.provenance_ttl_hours == 24


class TestProvenanceTracker:
    """Test ProvenanceTracker functionality."""

    @pytest.fixture
    def tracker(self):
        """Create ProvenanceTracker for testing."""
        return ProvenanceTracker(environment="test")

    @pytest.fixture
    def sample_bundle(self, tracker):
        """Create sample ProvenanceBundle."""
        return tracker.start_tracking("test query")

    def test_tracker_initialization(self, tracker):
        """Test ProvenanceTracker initialization."""
        assert tracker.environment == "test"
        assert isinstance(tracker.config, ProvenanceConfig)
        assert isinstance(tracker.active_bundles, dict)

    def test_start_tracking(self, tracker):
        """Test starting provenance tracking."""
        query = "What is the damage of fireball?"
        bundle = tracker.start_tracking(query)

        assert isinstance(bundle, ProvenanceBundle)
        assert bundle.environment == "test"
        assert bundle.correlation_id in tracker.active_bundles
        assert tracker.active_bundles[bundle.correlation_id] == bundle

    def test_start_tracking_disabled(self):
        """Test tracking when disabled."""
        config = ProvenanceConfig(enabled=False)
        tracker = ProvenanceTracker(environment="test", config=config)

        bundle = tracker.start_tracking("test query")
        assert isinstance(bundle, ProvenanceBundle)
        assert len(tracker.active_bundles) == 0  # Should not track when disabled

    def test_track_query_processing(self, tracker, sample_bundle):
        """Test query processing tracking."""
        classification = MockClassification()
        strategy_info = {
            "selected": "hybrid",
            "reason": "optimal for complexity",
            "alternatives": ["vector_only", "graph_enhanced"]
        }

        tracker.track_query_processing(
            bundle=sample_bundle,
            original_query="What is fireball damage?",
            processed_query="fireball spell damage",
            classification=classification,
            strategy_info=strategy_info,
            processing_time_ms=25.0
        )

        assert sample_bundle.query_provenance is not None
        provenance = sample_bundle.query_provenance

        assert provenance.original_query == "What is fireball damage?"
        assert provenance.processed_query == "fireball spell damage"
        assert provenance.intent == "fact_lookup"
        assert provenance.domain == "ttrpg_rules"
        assert provenance.complexity == "medium"
        assert provenance.strategy_selected == "hybrid"
        assert provenance.processing_time_ms == 25.0

    def test_track_retrieval(self, tracker, sample_bundle):
        """Test retrieval tracking."""
        strategy = "hybrid_vector_graph"
        search_params = {
            "top_k": 5,
            "graph_expansion": True,
            "search_terms": ["fireball", "damage"],
            "filters": ["official_sources"]
        }

        results = [
            {
                "id": "result_1",
                "content": "Fireball deals 8d6 fire damage.",
                "score": 0.9,
                "source": "phb.pdf",
                "metadata": {"page": 241, "source": "phb"}
            },
            {
                "id": "result_2",
                "content": "Evocation spells deal damage.",
                "score": 0.7,
                "source": "phb.pdf",
                "metadata": {"page": 117, "source": "phb"}
            }
        ]

        graph_data = {
            "nodes_explored": 5,
            "relationships_found": 3,
            "cross_references": ["magic_missile", "lightning_bolt"]
        }

        tracker.track_retrieval(
            bundle=sample_bundle,
            strategy=strategy,
            search_params=search_params,
            results=results,
            graph_data=graph_data,
            retrieval_time_ms=45.0
        )

        assert sample_bundle.retrieval_provenance is not None
        provenance = sample_bundle.retrieval_provenance

        assert provenance.strategy == strategy
        assert provenance.top_k == 5
        assert provenance.graph_expansion_enabled is True
        assert provenance.results_returned == 2
        assert len(provenance.sources_found) == 2
        assert provenance.graph_nodes_explored == 5
        assert provenance.retrieval_time_ms == 45.0

        # Check source attribution
        source1 = provenance.sources_found[0]
        assert source1.source_id == "result_1"
        assert source1.source_type == "phb"
        assert source1.page_number == 241
        assert source1.relevance_score == 0.9

    def test_track_reranking(self, tracker, sample_bundle):
        """Test reranking tracking."""
        reranking_data = {
            "strategy": "domain_aware",
            "weights": {"vector": 0.3, "domain": 0.4, "content": 0.3},
            "confidence": 0.85,
            "signal_agreement": 0.75,
            "vector_signals": {"similarity": 0.8},
            "domain_signals": {"entity_match": 0.9}
        }

        original_results = ["result_2", "result_1", "result_3"]
        reranked_results = ["result_1", "result_2", "result_3"]

        tracker.track_reranking(
            bundle=sample_bundle,
            reranking_data=reranking_data,
            original_results=original_results,
            reranked_results=reranked_results,
            reranking_time_ms=15.0
        )

        assert sample_bundle.reranking_provenance is not None
        provenance = sample_bundle.reranking_provenance

        assert provenance.strategy == "domain_aware"
        assert provenance.signal_weights["domain"] == 0.4
        assert provenance.ranking_confidence == 0.85
        assert provenance.original_ranking == original_results
        assert provenance.final_ranking == reranked_results
        assert len(provenance.ranking_changes) > 0
        assert provenance.reranking_time_ms == 15.0

    def test_track_answer_generation(self, tracker, sample_bundle):
        """Test answer generation tracking."""
        generation_config = {
            "model": "gpt-4",
            "strategy": "synthesis",
            "temperature": 0.7,
            "max_tokens": 500
        }

        reasoning_steps = [
            {
                "type": "fact_lookup",
                "description": "Find fireball damage information",
                "input_sources": ["result_1"],
                "reasoning": "Located spell damage in PHB",
                "output": "8d6 fire damage",
                "confidence": 0.9
            },
            {
                "type": "synthesis",
                "description": "Synthesize answer",
                "input_sources": ["result_1", "result_2"],
                "reasoning": "Combined spell and school information",
                "output": "Complete answer about fireball",
                "confidence": 0.8
            }
        ]

        source_usage = {
            "primary": ["result_1"],
            "supporting": ["result_2"],
            "contradictory": []
        }

        answer_metrics = {
            "confidence": 0.85,
            "completeness": 0.9,
            "length": 150,
            "citations": 2,
            "fact_density": 0.7
        }

        tracker.track_answer_generation(
            bundle=sample_bundle,
            generation_config=generation_config,
            reasoning_steps=reasoning_steps,
            source_usage=source_usage,
            answer_metrics=answer_metrics,
            generation_time_ms=200.0
        )

        assert sample_bundle.answer_provenance is not None
        provenance = sample_bundle.answer_provenance

        assert provenance.model_used == "gpt-4"
        assert provenance.generation_strategy == "synthesis"
        assert len(provenance.reasoning_steps) == 2
        assert provenance.primary_sources == ["result_1"]
        assert provenance.answer_confidence == 0.85
        assert provenance.generation_time_ms == 200.0

        # Check reasoning steps
        step1 = provenance.reasoning_steps[0]
        assert step1.step_type == "fact_lookup"
        assert step1.confidence == 0.9

    def test_calculate_quality_metrics(self, tracker, sample_bundle):
        """Test quality metrics calculation."""
        # Add some provenance data
        sample_bundle.query_provenance = QueryProvenance(
            original_query="test",
            processed_query="test",
            query_hash="hash",
            intent="fact_lookup",
            domain="ttrpg_rules",
            complexity="medium",
            classification_confidence=0.8,
            strategy_selected="hybrid",
            strategy_reason="test"
        )

        sample_bundle.answer_provenance = AnswerProvenance(
            model_used="test",
            generation_strategy="test",
            answer_confidence=0.85,
            completeness_score=0.9
        )

        # Add sources
        sample_bundle.all_sources = [
            SourceAttribution(
                source_id="1",
                source_path="phb.pdf",
                source_type="phb",
                used_in_answer=True,
                contribution_weight=0.8
            ),
            SourceAttribution(
                source_id="2",
                source_path="dmg.pdf",
                source_type="dmg",
                used_in_answer=True,
                contribution_weight=0.6
            )
        ]

        metrics = tracker.calculate_quality_metrics(sample_bundle)

        assert isinstance(metrics, QualityMetrics)
        assert 0.0 <= metrics.overall_confidence <= 1.0
        assert 0.0 <= metrics.source_reliability <= 1.0
        assert metrics.source_diversity == 2
        assert metrics.official_source_count == 2

    def test_finalize_bundle(self, tracker, sample_bundle):
        """Test bundle finalization."""
        # Add minimal provenance data
        sample_bundle.query_provenance = QueryProvenance(
            original_query="test",
            processed_query="test",
            query_hash="hash",
            intent="fact_lookup",
            domain="ttrpg_rules",
            complexity="medium",
            classification_confidence=0.8,
            strategy_selected="hybrid",
            strategy_reason="test"
        )

        correlation_id = sample_bundle.correlation_id
        assert correlation_id in tracker.active_bundles

        finalized = tracker.finalize_bundle(sample_bundle)

        assert finalized.completed_at is not None
        assert finalized.quality_metrics is not None
        assert correlation_id not in tracker.active_bundles

    def test_context_manager(self, tracker, sample_bundle):
        """Test stage tracking context manager."""
        with tracker.track_stage(sample_bundle, "test_stage"):
            time.sleep(0.01)  # Small delay to measure

        # Context manager should complete without errors

    def test_bundle_management(self, tracker):
        """Test bundle management methods."""
        # Create multiple bundles
        bundle1 = tracker.start_tracking("query 1")
        bundle2 = tracker.start_tracking("query 2")

        # Test getting active bundles
        active = tracker.get_active_bundles()
        assert len(active) == 2
        assert bundle1.correlation_id in active
        assert bundle2.correlation_id in active

        # Test getting by session
        found = tracker.get_bundle_by_session(bundle1.session_id)
        assert found == bundle1

        # Test clearing expired bundles
        expired = tracker.clear_expired_bundles(max_age_hours=0)
        assert expired == 2
        assert len(tracker.active_bundles) == 0


class TestProvenanceIntegration:
    """Test provenance integration scenarios."""

    def test_disabled_tracking(self):
        """Test behavior when tracking is disabled."""
        config = ProvenanceConfig(enabled=False)
        tracker = ProvenanceTracker(environment="test", config=config)

        bundle = tracker.start_tracking("test query")
        classification = MockClassification()

        # All tracking methods should handle disabled state gracefully
        tracker.track_query_processing(
            bundle, "test", "test", classification, {}, 0.0
        )
        tracker.track_retrieval(
            bundle, "test", {}, [], None, 0.0
        )
        tracker.track_reranking(
            bundle, {}, [], [], 0.0
        )
        tracker.track_answer_generation(
            bundle, {}, [], {}, {}, 0.0
        )

        # Should not have detailed provenance data
        assert bundle.query_provenance is None
        assert bundle.retrieval_provenance is None
        assert bundle.reranking_provenance is None
        assert bundle.answer_provenance is None

    def test_partial_tracking_config(self):
        """Test with partial tracking configuration."""
        config = ProvenanceConfig(
            track_query_processing=False,
            track_retrieval=True,
            track_reranking=False,
            track_answer_generation=True
        )
        tracker = ProvenanceTracker(environment="test", config=config)

        bundle = tracker.start_tracking("test query")
        classification = MockClassification()

        # Track all stages
        tracker.track_query_processing(
            bundle, "test", "test", classification, {}, 0.0
        )
        tracker.track_retrieval(
            bundle, "test", {"top_k": 5}, [{"id": "1", "score": 0.8}], None, 0.0
        )
        tracker.track_reranking(
            bundle, {"strategy": "test"}, [], [], 0.0
        )
        tracker.track_answer_generation(
            bundle, {"model": "test"}, [], {}, {"confidence": 0.8}, 0.0
        )

        # Should only have data for enabled stages
        assert bundle.query_provenance is None  # Disabled
        assert bundle.retrieval_provenance is not None  # Enabled
        assert bundle.reranking_provenance is None  # Disabled
        assert bundle.answer_provenance is not None  # Enabled

    def test_error_handling(self, tracker):
        """Test error handling in tracking methods."""
        bundle = tracker.start_tracking("test query")

        # Test with malformed data - should not crash
        tracker.track_query_processing(
            bundle, "test", "test", None, {}, 0.0  # None classification
        )

        tracker.track_retrieval(
            bundle, "test", {}, None, None, 0.0  # None results
        )

        # Should handle errors gracefully
        assert bundle.query_provenance is None or bundle.query_provenance.intent == "unknown"

    def test_performance_tracking(self, tracker):
        """Test that tracking overhead is minimal."""
        bundle = tracker.start_tracking("performance test")
        classification = MockClassification()

        start_time = time.perf_counter()

        # Perform typical tracking operations
        tracker.track_query_processing(
            bundle, "test query", "test query", classification,
            {"selected": "hybrid"}, 10.0
        )

        tracker.track_retrieval(
            bundle, "hybrid", {"top_k": 10},
            [{"id": f"result_{i}", "score": 0.8, "content": "test"} for i in range(10)],
            {"nodes_explored": 5}, 20.0
        )

        tracker.track_reranking(
            bundle, {"strategy": "domain_aware", "weights": {"vector": 0.5}},
            [f"result_{i}" for i in range(10)],
            [f"result_{i}" for i in range(10)], 15.0
        )

        tracker.calculate_quality_metrics(bundle)

        end_time = time.perf_counter()
        tracking_time_ms = (end_time - start_time) * 1000

        # Should be well under the 50ms target
        assert tracking_time_ms < 50.0

    def test_bundle_serialization(self, tracker):
        """Test bundle serialization to dict."""
        bundle = tracker.start_tracking("serialization test")

        # Add some data
        bundle.query_provenance = QueryProvenance(
            original_query="test",
            processed_query="test",
            query_hash="hash",
            intent="fact_lookup",
            domain="ttrpg_rules",
            complexity="medium",
            classification_confidence=0.8,
            strategy_selected="hybrid",
            strategy_reason="test"
        )

        bundle.mark_completed()

        bundle_dict = bundle.to_dict()

        assert isinstance(bundle_dict, dict)
        assert "session_id" in bundle_dict
        assert "correlation_id" in bundle_dict
        assert "stage_status" in bundle_dict
        assert "confidence_summary" in bundle_dict
        assert "total_time_ms" in bundle_dict