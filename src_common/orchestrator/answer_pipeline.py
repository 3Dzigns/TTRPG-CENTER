"""
Answer Pipeline with Evaluation Gate Integration for FR-028

Provides answer generation pipeline with integrated quality evaluation gate
for ensuring high-quality responses before delivery to users.
"""
from __future__ import annotations

import time
from typing import Dict, List, Any, Optional, Union, Tuple

from ..ttrpg_logging import get_logger
from .eval_gate import EvalGate
from .eval_models import EvaluationResult, EvalConfig, EvalContext, EvalStrategy, GateDecision
from .retriever import retrieve, DocChunk
from .plan_models import QueryPlan
from .classifier import Classification

logger = get_logger(__name__)


class AnswerPipeline:
    """
    Enhanced answer generation pipeline with integrated evaluation gate.

    Combines retrieval, answer generation, and quality assessment for
    high-quality TTRPG query responses.
    """

    def __init__(self, environment: str = "dev"):
        """Initialize answer pipeline with evaluation gate."""
        self.environment = environment
        self.eval_gate = EvalGate(environment=environment)

        logger.info(f"AnswerPipeline initialized for environment: {environment}")

    def generate_answer(
        self,
        query: str,
        plan: QueryPlan,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Generate answer with integrated evaluation gate.

        Args:
            query: User query
            plan: Query execution plan with eval configuration
            max_retries: Maximum retry attempts for failed evaluations

        Returns:
            Dictionary containing answer, evaluation result, and metadata
        """
        start_time = time.perf_counter()

        # Extract evaluation configuration from plan
        eval_config_dict = getattr(plan, 'eval_config', None)
        eval_enabled = eval_config_dict and eval_config_dict.get('enabled', False)

        # Track all attempts for debugging
        attempts = []

        for attempt in range(max_retries + 1):
            try:
                # Perform retrieval
                retrieval_results = self._perform_retrieval(query, plan)

                # Generate answer
                answer = self._generate_answer_content(query, retrieval_results, plan)

                # Evaluate answer quality if enabled
                if eval_enabled:
                    evaluation_result = self._evaluate_answer(
                        answer, query, plan, retrieval_results
                    )

                    attempts.append({
                        'attempt': attempt,
                        'answer_length': len(answer),
                        'evaluation': evaluation_result.get_quality_summary(),
                        'gate_decision': evaluation_result.gate_decision.value
                    })

                    # Check if answer passes evaluation
                    if evaluation_result.gate_decision == GateDecision.PASS:
                        # Answer passed evaluation
                        total_time = (time.perf_counter() - start_time) * 1000

                        return {
                            'answer': answer,
                            'evaluation': evaluation_result,
                            'retrieval_results': retrieval_results,
                            'quality_passed': True,
                            'attempts': attempts,
                            'total_time_ms': total_time,
                            'metadata': {
                                'plan_hash': plan.query_hash,
                                'evaluation_enabled': True,
                                'retry_count': attempt
                            }
                        }

                    elif evaluation_result.gate_decision == GateDecision.RETRY and attempt < max_retries:
                        # Retry with modifications based on feedback
                        logger.info(f"Answer evaluation suggested retry (attempt {attempt + 1})")
                        continue

                    elif evaluation_result.gate_decision == GateDecision.REVIEW:
                        # Answer needs review but can be delivered with warning
                        total_time = (time.perf_counter() - start_time) * 1000

                        return {
                            'answer': answer,
                            'evaluation': evaluation_result,
                            'retrieval_results': retrieval_results,
                            'quality_passed': False,
                            'quality_warning': True,
                            'attempts': attempts,
                            'total_time_ms': total_time,
                            'metadata': {
                                'plan_hash': plan.query_hash,
                                'evaluation_enabled': True,
                                'retry_count': attempt,
                                'needs_review': True
                            }
                        }

                    else:  # GateDecision.FAIL
                        if attempt < max_retries:
                            logger.warning(f"Answer evaluation failed (attempt {attempt + 1})")
                            continue
                        else:
                            # All retries exhausted, return with failure
                            total_time = (time.perf_counter() - start_time) * 1000

                            return {
                                'answer': answer,
                                'evaluation': evaluation_result,
                                'retrieval_results': retrieval_results,
                                'quality_passed': False,
                                'quality_failed': True,
                                'attempts': attempts,
                                'total_time_ms': total_time,
                                'error': 'Answer quality evaluation failed after retries',
                                'metadata': {
                                    'plan_hash': plan.query_hash,
                                    'evaluation_enabled': True,
                                    'retry_count': attempt,
                                    'evaluation_failed': True
                                }
                            }

                else:
                    # Evaluation disabled, return answer directly
                    total_time = (time.perf_counter() - start_time) * 1000

                    return {
                        'answer': answer,
                        'evaluation': None,
                        'retrieval_results': retrieval_results,
                        'quality_passed': None,
                        'attempts': [{'attempt': 0, 'answer_length': len(answer)}],
                        'total_time_ms': total_time,
                        'metadata': {
                            'plan_hash': plan.query_hash,
                            'evaluation_enabled': False,
                            'retry_count': 0
                        }
                    }

            except Exception as e:
                logger.error(f"Error in answer generation attempt {attempt}: {e}")
                if attempt >= max_retries:
                    total_time = (time.perf_counter() - start_time) * 1000
                    return {
                        'answer': None,
                        'evaluation': None,
                        'retrieval_results': [],
                        'quality_passed': False,
                        'error': f"Answer generation failed: {str(e)}",
                        'attempts': attempts,
                        'total_time_ms': total_time,
                        'metadata': {
                            'plan_hash': getattr(plan, 'query_hash', 'unknown'),
                            'evaluation_enabled': eval_enabled,
                            'retry_count': attempt,
                            'generation_failed': True
                        }
                    }

    def _perform_retrieval(self, query: str, plan: QueryPlan) -> List[DocChunk]:
        """Perform document retrieval using the plan configuration."""
        try:
            # Use the retriever from the existing pipeline
            results = retrieve(plan, query, self.environment)
            logger.debug(f"Retrieved {len(results)} documents for query")
            return results
        except Exception as e:
            logger.warning(f"Retrieval failed: {e}")
            return []

    def _generate_answer_content(
        self,
        query: str,
        retrieval_results: List[DocChunk],
        plan: QueryPlan
    ) -> str:
        """Generate answer content from retrieval results."""

        # Simple answer generation for demonstration
        # In a real implementation, this would use LLM or template-based generation

        if not retrieval_results:
            return f"I couldn't find specific information about '{query}'. Please provide more context or try a different query."

        # Extract text from top results
        top_results = retrieval_results[:3]  # Use top 3 results
        content_pieces = []

        for i, result in enumerate(top_results):
            content_pieces.append(f"According to {result.source}, {result.text[:200]}...")

        # Combine into coherent answer
        answer = f"Based on the available sources:\n\n" + "\n\n".join(content_pieces)

        # Add source references
        sources = [f"[{i+1}] {result.source}" for i, result in enumerate(top_results)]
        answer += f"\n\nSources:\n" + "\n".join(sources)

        return answer

    def _evaluate_answer(
        self,
        answer: str,
        query: str,
        plan: QueryPlan,
        retrieval_results: List[DocChunk]
    ) -> EvaluationResult:
        """Evaluate answer quality using the evaluation gate."""

        # Create evaluation context from plan
        eval_context = self._create_eval_context(plan)

        # Convert retrieval results to sources format
        sources = self._convert_retrieval_to_sources(retrieval_results)

        # Get provenance data if available
        provenance_data = self._extract_provenance_data(plan)

        # Perform evaluation
        return self.eval_gate.evaluate_answer(
            answer=answer,
            query=query,
            context=eval_context,
            provenance_data=provenance_data,
            sources=sources
        )

    def _create_eval_context(self, plan: QueryPlan) -> EvalContext:
        """Create evaluation context from query plan."""
        eval_config_dict = getattr(plan, 'eval_config', {})
        classification = getattr(plan, 'classification', None)

        return EvalContext(
            environment=self.environment,
            query_complexity=getattr(classification, 'complexity', 'medium'),
            time_constraint_ms=eval_config_dict.get('max_evaluation_time_ms', 50.0),
            classification=classification,
            retrieval_strategy=getattr(plan, 'retrieval_strategy', {}).get('strategy', 'default')
        )

    def _convert_retrieval_to_sources(self, retrieval_results: List[DocChunk]) -> List[Dict[str, Any]]:
        """Convert DocChunk results to sources format for evaluation."""
        sources = []

        for result in retrieval_results:
            source = {
                'id': result.id,
                'content': result.text,
                'source': result.source,
                'score': result.score,
                'metadata': result.metadata
            }
            sources.append(source)

        return sources

    def _extract_provenance_data(self, plan: QueryPlan) -> Optional[Dict[str, Any]]:
        """Extract provenance data from plan if available."""
        # In a real implementation, this would extract provenance data
        # from the FR-027 provenance tracking system
        return None

    def get_evaluation_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Get summary of pipeline execution and evaluation."""
        evaluation = result.get('evaluation')

        summary = {
            'quality_passed': result.get('quality_passed'),
            'total_time_ms': result.get('total_time_ms', 0),
            'retry_count': result.get('metadata', {}).get('retry_count', 0),
            'evaluation_enabled': result.get('metadata', {}).get('evaluation_enabled', False)
        }

        if evaluation:
            summary.update({
                'gate_decision': evaluation.gate_decision.value,
                'quality_score': evaluation.quality_metrics.overall_quality_score(),
                'quality_issues': len(evaluation.quality_issues),
                'critical_failures': len(evaluation.critical_failures)
            })

        return summary


def create_answer_pipeline(environment: str = "dev") -> AnswerPipeline:
    """Create answer pipeline instance for the specified environment."""
    return AnswerPipeline(environment=environment)


def evaluate_answer_quality(
    answer: str,
    query: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    environment: str = "dev"
) -> EvaluationResult:
    """
    Standalone function for evaluating answer quality.

    Args:
        answer: Generated answer text
        query: Original user query
        sources: Source documents used
        environment: Evaluation environment

    Returns:
        EvaluationResult with quality assessment
    """
    eval_gate = EvalGate(environment=environment)
    context = EvalContext(environment=environment)

    return eval_gate.evaluate_answer(
        answer=answer,
        query=query,
        context=context,
        sources=sources or []
    )