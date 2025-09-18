"""
Functional tests for FR-028 Evaluation Gate Pipeline Integration

Tests cover:
- End-to-end answer pipeline with evaluation gate
- Query planner evaluation configuration generation
- Pipeline performance and quality requirements
- Integration with existing FR-024, FR-025, FR-026, FR-027 systems
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src_common.orchestrator.answer_pipeline import AnswerPipeline, evaluate_answer_quality
from src_common.orchestrator.eval_gate import EvalGate
from src_common.orchestrator.eval_models import (
    EvaluationResult,
    EvalConfig,
    EvalContext,
    EvalStrategy,
    GateDecision,
    QualityLevel
)
from src_common.orchestrator.plan_models import QueryPlan, PlanGenerationContext
from src_common.orchestrator.query_planner import QueryPlanner


@dataclass
class MockClassification:
    """Mock classification for testing."""
    intent: str = "fact_lookup"
    domain: str = "ttrpg_rules"
    complexity: str = "medium"
    confidence: float = 0.8


@pytest.fixture
def mock_environment_setup():
    """Setup mock environment for testing."""
    return None


class TestQueryPlannerEvalConfig:
    """Test query planner evaluation configuration generation."""

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_query_planner_generates_eval_config(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test that QueryPlanner generates appropriate evaluation configuration."""

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

        # Create QueryPlanner with evaluation enabled
        context = PlanGenerationContext(
            environment="test",
            enable_evaluation_gate=True,
            evaluation_strategy="comprehensive",
            minimum_overall_quality=0.7,
            minimum_accuracy_score=0.8
        )
        planner = QueryPlanner(environment="test", context=context)

        # Generate plan
        plan = planner.get_plan("What damage does fireball deal?")

        # Verify evaluation configuration was generated
        assert hasattr(plan, 'eval_config')
        assert plan.eval_config is not None
        assert plan.eval_config['enabled'] is True
        assert plan.eval_config['strategy'] in ['comprehensive', 'accuracy_first']
        assert plan.eval_config['minimum_accuracy_score'] >= 0.8

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_eval_config_adaptation_by_query_type(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test evaluation configuration adaptation based on query type."""

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        context = PlanGenerationContext(environment="test", enable_evaluation_gate=True)
        planner = QueryPlanner(environment="test", context=context)

        # Test fact lookup query
        mock_classify.return_value = MockClassification(intent="fact_lookup")
        plan = planner.get_plan("What is fireball's damage?")
        assert plan.eval_config['strategy'] == 'accuracy_first'
        assert plan.eval_config['minimum_accuracy_score'] >= 0.8

        # Test creative writing query
        mock_classify.return_value = MockClassification(intent="creative_write")
        plan = planner.get_plan("Write a story about a wizard")
        assert plan.eval_config['strategy'] == 'fast'
        assert plan.eval_config['minimum_accuracy_score'] <= 0.6

        # Test complex reasoning query
        mock_classify.return_value = MockClassification(intent="multi_hop_reasoning")
        plan = planner.get_plan("How do spell slots interact with multiclassing?")
        assert plan.eval_config['strategy'] == 'comprehensive'

    @patch('src_common.orchestrator.query_planner.classify_query')
    @patch('src_common.orchestrator.query_planner.get_cache')
    def test_eval_config_environment_adaptation(
        self,
        mock_cache,
        mock_classify,
        mock_environment_setup
    ):
        """Test evaluation configuration adaptation for different environments."""

        mock_cache_instance = Mock()
        mock_cache_instance.get.return_value = None
        mock_cache.return_value = mock_cache_instance

        mock_classify.return_value = MockClassification()

        # Production environment - should prioritize speed
        prod_context = PlanGenerationContext(
            environment="prod",
            enable_evaluation_gate=True
        )
        prod_planner = QueryPlanner(environment="prod", context=prod_context)
        prod_plan = prod_planner.get_plan("Test query")

        assert prod_plan.eval_config['max_evaluation_time_ms'] <= 30
        assert prod_plan.eval_config['fallback_on_timeout'] is True

        # Development environment - should allow more time
        dev_context = PlanGenerationContext(
            environment="dev",
            enable_evaluation_gate=True
        )
        dev_planner = QueryPlanner(environment="dev", context=dev_context)
        dev_plan = dev_planner.get_plan("Test query")

        assert dev_plan.eval_config['max_evaluation_time_ms'] >= 100

    def test_eval_config_disabled(self, mock_environment_setup):
        """Test behavior when evaluation gate is disabled."""
        context = PlanGenerationContext(
            environment="test",
            enable_evaluation_gate=False
        )

        with patch('src_common.orchestrator.query_planner.classify_query') as mock_classify:
            with patch('src_common.orchestrator.query_planner.get_cache') as mock_cache:
                mock_cache_instance = Mock()
                mock_cache_instance.get.return_value = None
                mock_cache.return_value = mock_cache_instance
                mock_classify.return_value = MockClassification()

                planner = QueryPlanner(environment="test", context=context)
                plan = planner.get_plan("Test query")

                assert plan.eval_config is None


class TestAnswerPipelineIntegration:
    """Test answer pipeline with evaluation gate integration."""

    @pytest.fixture
    def mock_retrieval_results(self):
        """Create mock retrieval results."""
        from src_common.orchestrator.retriever import DocChunk
        return [
            DocChunk(
                id="fireball_1",
                text="Fireball deals 8d6 fire damage to creatures in a 20-foot radius sphere.",
                source="phb.pdf",
                score=0.9,
                metadata={"source_type": "phb", "page": 241}
            ),
            DocChunk(
                id="fireball_2",
                text="Each creature in the area must make a Dexterity saving throw.",
                source="phb.pdf",
                score=0.8,
                metadata={"source_type": "phb", "page": 241}
            )
        ]

    @pytest.fixture
    def sample_query_plan(self):
        """Create sample query plan with evaluation configuration."""
        classification = MockClassification()
        return QueryPlan.create_from_query(
            query="What damage does fireball deal?",
            classification=classification,
            retrieval_strategy={"strategy": "hybrid", "vector_top_k": 5},
            model_config={"model": "gpt-4", "temperature": 0.0},
            eval_config={
                "enabled": True,
                "strategy": "comprehensive",
                "minimum_overall_score": 0.6,
                "minimum_accuracy_score": 0.7,
                "max_evaluation_time_ms": 50.0
            }
        )

    def test_answer_pipeline_with_evaluation(
        self,
        mock_retrieval_results,
        sample_query_plan,
        mock_environment_setup
    ):
        """Test answer pipeline with evaluation gate enabled."""
        pipeline = AnswerPipeline(environment="test")

        # Mock retrieval
        with patch.object(pipeline, '_perform_retrieval') as mock_retrieval:
            mock_retrieval.return_value = mock_retrieval_results

            result = pipeline.generate_answer(
                query="What damage does fireball deal?",
                plan=sample_query_plan
            )

            # Verify pipeline execution
            assert 'answer' in result
            assert 'evaluation' in result
            assert 'quality_passed' in result
            assert 'metadata' in result

            # Verify evaluation was performed
            assert result['metadata']['evaluation_enabled'] is True
            if result['evaluation']:
                assert isinstance(result['evaluation'], EvaluationResult)

    def test_answer_pipeline_quality_pass(
        self,
        mock_retrieval_results,
        sample_query_plan,
        mock_environment_setup
    ):
        """Test answer pipeline with high-quality answer that passes evaluation."""
        pipeline = AnswerPipeline(environment="test")

        # Mock retrieval and evaluation to return high quality
        with patch.object(pipeline, '_perform_retrieval') as mock_retrieval:
            with patch.object(pipeline.eval_gate, 'evaluate_answer') as mock_evaluate:
                mock_retrieval.return_value = mock_retrieval_results

                # Create mock evaluation result that passes
                mock_eval_result = EvaluationResult()
                mock_eval_result.gate_decision = GateDecision.PASS
                mock_eval_result.quality_metrics.accuracy_score = 0.9
                mock_eval_result.evaluation_time_ms = 25.0
                mock_evaluate.return_value = mock_eval_result

                result = pipeline.generate_answer(
                    query="What damage does fireball deal?",
                    plan=sample_query_plan
                )

                assert result['quality_passed'] is True
                assert result['evaluation'].gate_decision == GateDecision.PASS

    def test_answer_pipeline_quality_fail_with_retry(
        self,
        mock_retrieval_results,
        sample_query_plan,
        mock_environment_setup
    ):
        """Test answer pipeline with quality failure and retry logic."""
        pipeline = AnswerPipeline(environment="test")

        with patch.object(pipeline, '_perform_retrieval') as mock_retrieval:
            with patch.object(pipeline.eval_gate, 'evaluate_answer') as mock_evaluate:
                mock_retrieval.return_value = mock_retrieval_results

                # Mock evaluation results: fail, then retry, then pass
                fail_result = EvaluationResult()
                fail_result.gate_decision = GateDecision.RETRY
                fail_result.quality_metrics.accuracy_score = 0.5

                pass_result = EvaluationResult()
                pass_result.gate_decision = GateDecision.PASS
                pass_result.quality_metrics.accuracy_score = 0.8

                mock_evaluate.side_effect = [fail_result, pass_result]

                result = pipeline.generate_answer(
                    query="What damage does fireball deal?",
                    plan=sample_query_plan,
                    max_retries=2
                )

                assert result['quality_passed'] is True
                assert result['metadata']['retry_count'] == 1
                assert len(result['attempts']) == 2

    def test_answer_pipeline_evaluation_disabled(
        self,
        mock_retrieval_results,
        mock_environment_setup
    ):
        """Test answer pipeline with evaluation disabled."""
        # Create plan without evaluation config
        classification = MockClassification()
        plan = QueryPlan.create_from_query(
            query="Test query",
            classification=classification,
            retrieval_strategy={"strategy": "hybrid"},
            model_config={"model": "gpt-4"}
            # No eval_config
        )

        pipeline = AnswerPipeline(environment="test")

        with patch.object(pipeline, '_perform_retrieval') as mock_retrieval:
            mock_retrieval.return_value = mock_retrieval_results

            result = pipeline.generate_answer(query="Test query", plan=plan)

            assert result['metadata']['evaluation_enabled'] is False
            assert result['evaluation'] is None
            assert result['quality_passed'] is None

    def test_answer_pipeline_performance_requirements(
        self,
        mock_retrieval_results,
        sample_query_plan,
        mock_environment_setup
    ):
        """Test that answer pipeline meets performance requirements."""
        pipeline = AnswerPipeline(environment="test")

        with patch.object(pipeline, '_perform_retrieval') as mock_retrieval:
            mock_retrieval.return_value = mock_retrieval_results

            import time
            start_time = time.perf_counter()

            result = pipeline.generate_answer(
                query="What damage does fireball deal?",
                plan=sample_query_plan
            )

            end_time = time.perf_counter()
            total_time_ms = (end_time - start_time) * 1000

            # Should complete within reasonable time
            assert total_time_ms < 500  # 500ms tolerance for test environment

            # Evaluation should be fast
            if result['evaluation']:
                assert result['evaluation'].evaluation_time_ms < 100

    def test_answer_generation_quality(
        self,
        mock_retrieval_results,
        mock_environment_setup
    ):
        """Test answer generation quality without full pipeline."""
        pipeline = AnswerPipeline(environment="test")

        # Test answer generation method directly
        classification = MockClassification()
        plan = QueryPlan.create_from_query(
            query="What damage does fireball deal?",
            classification=classification,
            retrieval_strategy={"strategy": "hybrid"},
            model_config={"model": "gpt-4"}
        )

        answer = pipeline._generate_answer_content(
            query="What damage does fireball deal?",
            retrieval_results=mock_retrieval_results,
            plan=plan
        )

        # Answer should be reasonable
        assert len(answer) > 50
        assert "fireball" in answer.lower()
        assert "damage" in answer.lower()
        assert "sources" in answer.lower()  # Should include source references

    def test_pipeline_error_handling(
        self,
        sample_query_plan,
        mock_environment_setup
    ):
        """Test pipeline error handling and recovery."""
        pipeline = AnswerPipeline(environment="test")

        # Mock retrieval failure
        with patch.object(pipeline, '_perform_retrieval') as mock_retrieval:
            mock_retrieval.side_effect = Exception("Retrieval failed")

            result = pipeline.generate_answer(
                query="Test query",
                plan=sample_query_plan
            )

            assert 'error' in result
            assert result['quality_passed'] is False


class TestStandaloneEvaluation:
    """Test standalone evaluation function."""

    def test_standalone_answer_evaluation(self, mock_environment_setup):
        """Test standalone answer evaluation function."""
        answer = "Fireball deals 8d6 fire damage to creatures in a 20-foot radius."
        query = "How much damage does fireball deal?"
        sources = [
            {
                'id': 'phb_fireball',
                'content': 'Fireball spell deals 8d6 fire damage',
                'source': 'phb.pdf',
                'score': 0.9
            }
        ]

        result = evaluate_answer_quality(
            answer=answer,
            query=query,
            sources=sources,
            environment="test"
        )

        assert isinstance(result, EvaluationResult)
        assert result.quality_metrics.accuracy_score > 0.0
        assert result.gate_decision in [GateDecision.PASS, GateDecision.REVIEW, GateDecision.FAIL]

    def test_standalone_evaluation_without_sources(self, mock_environment_setup):
        """Test standalone evaluation without sources."""
        result = evaluate_answer_quality(
            answer="Test answer",
            query="Test query",
            environment="test"
        )

        assert isinstance(result, EvaluationResult)
        assert result.quality_metrics.source_count == 0


class TestEndToEndEvaluation:
    """Test end-to-end evaluation scenarios."""

    def test_complete_eval_pipeline_flow(self, mock_environment_setup):
        """Test complete evaluation pipeline from query to evaluated answer."""
        # This would be a more complex test that integrates multiple components
        # For now, we'll test the key integration points

        eval_gate = EvalGate(environment="test")

        # Simulate a complete flow
        query = "What is the damage and range of fireball?"
        answer = """Fireball is a 3rd-level evocation spell that deals 8d6 fire damage
        to all creatures within a 20-foot radius sphere. Each creature in the area must
        make a Dexterity saving throw, taking full damage on failure or half on success.
        The spell has a range of 150 feet."""

        sources = [
            {
                'id': 'phb_fireball_damage',
                'content': 'A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one.',
                'source': 'phb.pdf',
                'score': 0.95,
                'metadata': {'page': 241, 'source_type': 'phb'}
            }
        ]

        result = eval_gate.evaluate_answer(
            answer=answer,
            query=query,
            sources=sources
        )

        # Comprehensive answer should score well
        assert result.quality_metrics.overall_quality_score() > 0.7
        assert result.quality_metrics.accuracy_score > 0.7
        assert result.quality_metrics.completeness_score > 0.7
        assert result.gate_decision in [GateDecision.PASS, GateDecision.REVIEW]

    def test_performance_benchmark(self, mock_environment_setup):
        """Test performance benchmark for evaluation system."""
        eval_gate = EvalGate(environment="test")

        # Test evaluation performance with various answer lengths
        test_cases = [
            ("Short answer", "8d6 damage"),
            ("Medium answer", "Fireball deals 8d6 fire damage to creatures in a 20-foot radius."),
            ("Long answer", "Fireball is a 3rd-level evocation spell that creates an explosion of flame..." + " " * 500)
        ]

        for test_name, answer in test_cases:
            start_time = time.perf_counter()

            result = eval_gate.evaluate_answer(
                answer=answer,
                query="fireball damage",
                sources=[{'id': 'test', 'content': 'test content', 'source': 'test.pdf'}]
            )

            end_time = time.perf_counter()
            actual_time_ms = (end_time - start_time) * 1000

            # Should meet performance targets
            assert actual_time_ms < 100, f"{test_name} took {actual_time_ms:.2f}ms"
            assert result.evaluation_time_ms < 100, f"{test_name} reported {result.evaluation_time_ms:.2f}ms"

    def test_quality_threshold_enforcement(self, mock_environment_setup):
        """Test that quality thresholds are properly enforced."""
        config = EvalConfig(
            minimum_overall_score=0.8,
            minimum_accuracy_score=0.9,
            minimum_completeness_score=0.7
        )

        eval_gate = EvalGate(environment="test", config=config)

        # High quality answer should pass
        high_quality_answer = """Fireball is a 3rd-level evocation spell (PHB p. 241) that deals 8d6 fire damage
        to all creatures within a 20-foot radius sphere. Each creature must make a Dexterity saving throw,
        taking full damage on failure or half damage on success. The spell has a range of 150 feet."""

        sources = [
            {
                'id': 'phb_fireball',
                'content': 'Fireball spell details with 8d6 damage and 20-foot radius',
                'source': 'phb.pdf',
                'score': 0.95
            }
        ]

        result = eval_gate.evaluate_answer(
            answer=high_quality_answer,
            query="What is fireball's damage and area?",
            sources=sources
        )

        # Should pass with high quality thresholds
        assert result.gate_decision in [GateDecision.PASS, GateDecision.REVIEW]

        # Low quality answer should fail
        low_quality_answer = "Some damage maybe?"

        result = eval_gate.evaluate_answer(
            answer=low_quality_answer,
            query="What is fireball's damage and area?",
            sources=sources
        )

        # Should fail with high quality thresholds
        assert result.gate_decision in [GateDecision.FAIL, GateDecision.REVIEW]