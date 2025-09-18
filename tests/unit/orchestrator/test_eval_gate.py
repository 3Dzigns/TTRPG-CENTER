"""
Unit tests for FR-028 Evaluation Gate System

Tests cover:
- Evaluation models and quality metrics
- EvalGate core functionality
- Quality assessment algorithms
- Gate decision logic
- Performance and caching
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src_common.orchestrator.eval_gate import EvalGate
from src_common.orchestrator.eval_models import (
    QualityMetrics,
    EvaluationResult,
    EvalConfig,
    EvalContext,
    EvalStrategy,
    GateDecision,
    QualityLevel,
    create_quality_level,
    aggregate_quality_scores,
    calculate_confidence_calibration
)


@dataclass
class MockClassification:
    """Mock classification for testing."""
    intent: str = "fact_lookup"
    domain: str = "ttrpg_rules"
    complexity: str = "medium"
    confidence: float = 0.8


class TestEvalModels:
    """Test evaluation data models and utility functions."""

    def test_quality_metrics_creation(self):
        """Test QualityMetrics creation and scoring."""
        metrics = QualityMetrics(
            accuracy_score=0.8,
            completeness_score=0.7,
            relevance_score=0.9,
            coherence_score=0.8,
            rules_accuracy=0.85,
            citation_quality=0.6
        )

        assert metrics.accuracy_score == 0.8
        assert metrics.completeness_score == 0.7
        assert metrics.relevance_score == 0.9

        # Test overall quality score calculation
        overall_score = metrics.overall_quality_score()
        assert 0.0 <= overall_score <= 1.0
        assert overall_score > 0.7  # Should be reasonably high

    def test_quality_level_classification(self):
        """Test quality level classification."""
        assert create_quality_level(0.95) == QualityLevel.EXCELLENT
        assert create_quality_level(0.8) == QualityLevel.GOOD
        assert create_quality_level(0.65) == QualityLevel.ACCEPTABLE
        assert create_quality_level(0.5) == QualityLevel.POOR
        assert create_quality_level(0.3) == QualityLevel.UNACCEPTABLE

    def test_quality_score_aggregation(self):
        """Test quality score aggregation methods."""
        scores = [0.8, 0.7, 0.9]

        # Test harmonic mean (conservative)
        harmonic_result = aggregate_quality_scores(scores, "harmonic_mean")
        assert 0.0 <= harmonic_result <= 1.0
        assert harmonic_result < max(scores)

        # Test arithmetic mean
        arithmetic_result = aggregate_quality_scores(scores, "arithmetic_mean")
        assert arithmetic_result == sum(scores) / len(scores)

        # Test edge cases
        assert aggregate_quality_scores([]) == 0.0
        assert aggregate_quality_scores([0.8]) == 0.8

    def test_confidence_calibration(self):
        """Test confidence calibration calculation."""
        calibration = calculate_confidence_calibration(0.8, 0.75, 100)

        assert "calibration_error" in calibration
        assert "reliability_score" in calibration
        assert 0.0 <= calibration["calibration_error"] <= 1.0
        assert 0.0 <= calibration["reliability_score"] <= 1.0

    def test_eval_config_defaults(self):
        """Test EvalConfig default values and methods."""
        config = EvalConfig()

        assert config.strategy == EvalStrategy.COMPREHENSIVE
        assert config.enabled is True
        assert config.minimum_overall_score == 0.6
        assert config.minimum_accuracy_score == 0.7

        # Test threshold lookup
        assert config.get_threshold_for_metric("accuracy") == 0.7
        assert config.get_threshold_for_metric("overall") == 0.6

        # Test fast mode detection
        assert config.should_use_fast_mode(20.0) is True
        assert config.should_use_fast_mode(100.0) is False

    def test_eval_context_adaptation(self):
        """Test evaluation context configuration adaptation."""
        base_config = EvalConfig()
        context = EvalContext(
            environment="test",
            time_constraint_ms=25.0,
            required_quality_level=QualityLevel.EXCELLENT
        )

        adapted_config = context.get_adapted_config(base_config)

        # Should adapt to time constraints
        assert adapted_config.strategy == EvalStrategy.FAST
        assert adapted_config.max_evaluation_time_ms <= 25.0

        # Should raise quality thresholds for EXCELLENT requirement
        assert adapted_config.minimum_overall_score >= 0.9


class TestEvalGate:
    """Test EvalGate functionality."""

    @pytest.fixture
    def eval_gate(self):
        """Create EvalGate for testing."""
        return EvalGate(environment="test")

    @pytest.fixture
    def sample_sources(self):
        """Create sample sources for testing."""
        return [
            {
                'id': 'source_1',
                'content': 'Fireball deals 8d6 fire damage to creatures in a 20-foot radius.',
                'source': 'phb.pdf',
                'score': 0.9,
                'metadata': {'source_type': 'phb', 'page': 241}
            },
            {
                'id': 'source_2',
                'content': 'Each creature must make a Dexterity saving throw.',
                'source': 'phb.pdf',
                'score': 0.8,
                'metadata': {'source_type': 'phb', 'page': 241}
            }
        ]

    def test_eval_gate_initialization(self, eval_gate):
        """Test EvalGate initialization."""
        assert eval_gate.environment == "test"
        assert isinstance(eval_gate.config, EvalConfig)
        assert isinstance(eval_gate.evaluation_cache, dict)

    def test_basic_answer_evaluation(self, eval_gate, sample_sources):
        """Test basic answer evaluation functionality."""
        query = "How much damage does fireball deal?"
        answer = "Fireball deals 8d6 fire damage to all creatures in a 20-foot radius sphere."

        result = eval_gate.evaluate_answer(
            answer=answer,
            query=query,
            sources=sample_sources
        )

        assert isinstance(result, EvaluationResult)
        assert result.query_hash
        assert result.answer_id
        assert result.strategy_used in [EvalStrategy.COMPREHENSIVE, EvalStrategy.FAST]
        assert isinstance(result.quality_metrics, QualityMetrics)
        assert result.gate_decision in [GateDecision.PASS, GateDecision.REVIEW, GateDecision.FAIL]

    def test_fast_evaluation_strategy(self, eval_gate, sample_sources):
        """Test fast evaluation strategy."""
        config = EvalConfig(strategy=EvalStrategy.FAST)
        eval_gate.config = config

        query = "Fireball damage?"
        answer = "8d6 fire damage."

        result = eval_gate.evaluate_answer(
            answer=answer,
            query=query,
            sources=sample_sources
        )

        assert result.strategy_used == EvalStrategy.FAST
        assert result.evaluation_time_ms < 50  # Should be fast

    def test_accuracy_evaluation(self, eval_gate, sample_sources):
        """Test accuracy evaluation with sources."""
        query = "How much damage does fireball deal?"

        # High accuracy answer
        good_answer = "Fireball deals 8d6 fire damage to creatures in a 20-foot radius."
        result = eval_gate.evaluate_answer(good_answer, query, sources=sample_sources)
        assert result.quality_metrics.accuracy_score > 0.7

        # Low accuracy answer
        bad_answer = "Fireball deals 1d4 cold damage to one target."
        result = eval_gate.evaluate_answer(bad_answer, query, sources=sample_sources)
        assert result.quality_metrics.accuracy_score < 0.5

    def test_completeness_evaluation(self, eval_gate, sample_sources):
        """Test completeness evaluation."""
        query = "How does fireball work in combat?"

        # Complete answer
        complete_answer = """Fireball is a 3rd level spell that deals 8d6 fire damage
        to all creatures in a 20-foot radius. Each creature must make a Dexterity
        saving throw, taking full damage on failure or half on success."""

        result = eval_gate.evaluate_answer(complete_answer, query, sources=sample_sources)
        assert result.quality_metrics.completeness_score > 0.6

        # Incomplete answer
        incomplete_answer = "Fireball deals damage."
        result = eval_gate.evaluate_answer(incomplete_answer, query, sources=sample_sources)
        assert result.quality_metrics.completeness_score < 0.5

    def test_relevance_evaluation(self, eval_gate, sample_sources):
        """Test relevance evaluation."""
        query = "How much damage does fireball deal?"

        # Relevant answer
        relevant_answer = "Fireball deals 8d6 fire damage to creatures in the area."
        result = eval_gate.evaluate_answer(relevant_answer, query, sources=sample_sources)
        assert result.quality_metrics.relevance_score > 0.7

        # Irrelevant answer
        irrelevant_answer = "Magic missile always hits its target."
        result = eval_gate.evaluate_answer(irrelevant_answer, query, sources=sample_sources)
        assert result.quality_metrics.relevance_score < 0.4

    def test_domain_validation(self, eval_gate, sample_sources):
        """Test TTRPG domain-specific validation."""
        config = EvalConfig(enable_domain_validation=True)
        eval_gate.config = config

        query = "What is fireball's damage and save?"
        answer = "Fireball deals 8d6 fire damage, Dex save for half."

        result = eval_gate.evaluate_answer(answer, query, sources=sample_sources)

        assert result.quality_metrics.rules_accuracy > 0.6
        assert result.quality_metrics.domain_appropriateness > 0.6

    def test_citation_quality_evaluation(self, eval_gate, sample_sources):
        """Test citation quality assessment."""
        query = "How much damage does fireball deal?"

        # Good citations
        cited_answer = "Fireball deals 8d6 fire damage (PHB p. 241) to creatures in a 20-foot radius."
        result = eval_gate.evaluate_answer(cited_answer, query, sources=sample_sources)
        assert result.quality_metrics.citation_quality > 0.5

        # No citations
        uncited_answer = "Fireball deals 8d6 fire damage to creatures in a 20-foot radius."
        result = eval_gate.evaluate_answer(uncited_answer, query, sources=sample_sources)
        assert result.quality_metrics.citation_quality < 0.7

    def test_gate_decision_logic(self, eval_gate, sample_sources):
        """Test gate decision making logic."""
        config = EvalConfig(
            minimum_overall_score=0.7,
            minimum_accuracy_score=0.8
        )
        eval_gate.config = config

        query = "How much damage does fireball deal?"

        # High quality answer should pass
        high_quality_answer = """Fireball is a 3rd-level evocation spell that deals 8d6 fire damage
        to all creatures within a 20-foot radius sphere. Each creature in the area must make a
        Dexterity saving throw, taking the full damage on a failed save or half damage on success."""

        result = eval_gate.evaluate_answer(high_quality_answer, query, sources=sample_sources)
        assert result.gate_decision in [GateDecision.PASS, GateDecision.REVIEW]

        # Low quality answer should fail
        low_quality_answer = "Damage."
        result = eval_gate.evaluate_answer(low_quality_answer, query, sources=sample_sources)
        assert result.gate_decision in [GateDecision.FAIL, GateDecision.REVIEW]

    def test_source_validation(self, eval_gate):
        """Test source validation functionality."""
        answer = "According to the Player's Handbook, fireball deals 8d6 damage."
        sources = [
            {
                'id': 'phb_fireball',
                'content': 'Fireball spell description with damage details',
                'source': 'phb.pdf'
            }
        ]

        result = eval_gate.evaluate_answer(answer, "fireball damage", sources=sources)

        assert len(result.source_validation_results) > 0
        validation = result.source_validation_results[0]
        assert 'source_id' in validation
        assert 'is_referenced' in validation

    def test_citation_validation(self, eval_gate):
        """Test citation validation functionality."""
        answer = "Fireball deals 8d6 damage [1] and affects a 20-foot radius [2]."
        sources = [
            {'id': '1', 'content': 'damage info'},
            {'id': '2', 'content': 'radius info'}
        ]

        result = eval_gate.evaluate_answer(answer, "fireball info", sources=sources)

        assert len(result.citation_validation_results) > 0

    def test_evaluation_caching(self, eval_gate, sample_sources):
        """Test evaluation result caching."""
        config = EvalConfig(enable_caching=True)
        eval_gate.config = config

        query = "How much damage does fireball deal?"
        answer = "Fireball deals 8d6 fire damage."

        # First evaluation
        result1 = eval_gate.evaluate_answer(answer, query, sources=sample_sources)

        # Second evaluation should use cache
        result2 = eval_gate.evaluate_answer(answer, query, sources=sample_sources)

        # Results should be identical (cached)
        assert result1.evaluation_id == result2.evaluation_id

    def test_evaluation_timeout_handling(self, eval_gate):
        """Test evaluation timeout and fallback behavior."""
        config = EvalConfig(
            max_evaluation_time_ms=1.0,  # Very short timeout
            fallback_on_timeout=True,
            fallback_decision=GateDecision.REVIEW
        )
        eval_gate.config = config

        # Mock a slow evaluation
        with patch.object(eval_gate, '_evaluate_quality') as mock_eval:
            mock_eval.side_effect = Exception("Timeout simulation")

            result = eval_gate.evaluate_answer("test answer", "test query")

            assert result.gate_decision == GateDecision.REVIEW
            assert len(result.critical_failures) > 0

    def test_performance_requirements(self, eval_gate, sample_sources):
        """Test that evaluation meets performance requirements."""
        query = "How much damage does fireball deal?"
        answer = "Fireball deals 8d6 fire damage to creatures in a 20-foot radius."

        start_time = time.perf_counter()
        result = eval_gate.evaluate_answer(answer, query, sources=sample_sources)
        end_time = time.perf_counter()

        # Should complete within performance target
        actual_time_ms = (end_time - start_time) * 1000
        assert actual_time_ms < 100  # 100ms tolerance for test environment

        # Reported time should be reasonable
        assert result.evaluation_time_ms < 100

    def test_quality_issues_identification(self, eval_gate):
        """Test quality issue identification."""
        config = EvalConfig(
            minimum_accuracy_score=0.8,
            minimum_completeness_score=0.7
        )
        eval_gate.config = config

        # Answer with quality issues
        poor_answer = "Maybe some damage."
        result = eval_gate.evaluate_answer(poor_answer, "fireball damage")

        assert len(result.quality_issues) > 0
        issue_text = " ".join(result.quality_issues)
        assert any(keyword in issue_text.lower() for keyword in ["accuracy", "incomplete", "relevance"])

    def test_improvement_suggestions(self, eval_gate):
        """Test improvement suggestion generation."""
        short_answer = "8d6."
        result = eval_gate.evaluate_answer(short_answer, "fireball damage")

        assert len(result.improvement_suggestions) > 0
        suggestions_text = " ".join(result.improvement_suggestions)
        assert any(keyword in suggestions_text.lower() for keyword in ["detailed", "source", "citation"])

    def test_critical_failure_detection(self, eval_gate):
        """Test critical failure detection."""
        config = EvalConfig(minimum_accuracy_score=0.8)
        eval_gate.config = config

        # Completely wrong answer
        wrong_answer = "Fireball heals allies for maximum hit points."
        result = eval_gate.evaluate_answer(wrong_answer, "fireball damage")

        if result.quality_metrics.accuracy_score < 0.4:
            assert len(result.critical_failures) > 0

    def test_evaluation_summary(self, eval_gate, sample_sources):
        """Test evaluation summary generation."""
        query = "How much damage does fireball deal?"
        answer = "Fireball deals 8d6 fire damage."

        result = eval_gate.evaluate_answer(answer, query, sources=sample_sources)
        summary = eval_gate.get_evaluation_summary(result)

        assert 'gate_decision' in summary
        assert 'quality_level' in summary
        assert 'overall_score' in summary
        assert 'evaluation_time_ms' in summary

    def test_cache_management(self, eval_gate):
        """Test evaluation cache management."""
        # Add some cached results
        eval_gate.evaluation_cache['test_key'] = EvaluationResult()

        assert len(eval_gate.evaluation_cache) > 0

        # Clear cache
        eval_gate.clear_cache()
        assert len(eval_gate.evaluation_cache) == 0


class TestEvalGateIntegration:
    """Test evaluation gate integration scenarios."""

    def test_with_provenance_data(self):
        """Test evaluation with FR-027 provenance data."""
        eval_gate = EvalGate(environment="test")

        provenance_data = {
            'retrieval_provenance': {
                'results_returned': 5,
                'sources_found': ['source1', 'source2'],
                'confidence_score': 0.85
            },
            'quality_metrics': {
                'confidence_score': 0.8
            }
        }

        result = eval_gate.evaluate_answer(
            answer="Fireball deals 8d6 fire damage.",
            query="fireball damage",
            provenance_data=provenance_data
        )

        # Should incorporate provenance data into evaluation
        assert result.quality_metrics.confidence_score > 0.0

    def test_context_adaptation(self):
        """Test evaluation context adaptation."""
        eval_gate = EvalGate(environment="test")

        # High-performance context
        context = EvalContext(
            environment="prod",
            time_constraint_ms=20.0,
            required_quality_level=QualityLevel.GOOD
        )

        result = eval_gate.evaluate_answer(
            answer="Test answer",
            query="test query",
            context=context
        )

        assert result.evaluation_time_ms < 50  # Should respect time constraints

    def test_disabled_evaluation(self):
        """Test behavior when evaluation is disabled."""
        config = EvalConfig(enabled=False)
        eval_gate = EvalGate(environment="test", config=config)

        # Should still create result but with minimal processing
        result = eval_gate.evaluate_answer("test answer", "test query")
        assert isinstance(result, EvaluationResult)

    def test_error_recovery(self):
        """Test error recovery and graceful degradation."""
        eval_gate = EvalGate(environment="test")

        # Test with malformed input
        result = eval_gate.evaluate_answer("", "")  # Empty inputs
        assert isinstance(result, EvaluationResult)
        assert result.gate_decision in [GateDecision.FAIL, GateDecision.REVIEW]

        # Test with None inputs
        result = eval_gate.evaluate_answer(None, None)
        assert isinstance(result, EvaluationResult)