"""
Evaluation Gate for FR-028 Answer Quality Assessment

Main orchestrator for evaluating answer quality before delivery to users.
Provides comprehensive quality assessment with configurable evaluation strategies.
"""
from __future__ import annotations

import re
import time
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union
from statistics import mean

from ..ttrpg_logging import get_logger
from .eval_models import (
    QualityMetrics,
    EvaluationResult,
    EvalConfig,
    EvalContext,
    EvalStrategy,
    GateDecision,
    QualityLevel,
    aggregate_quality_scores,
    calculate_confidence_calibration,
    create_quality_level
)

logger = get_logger(__name__)


class EvalGate:
    """
    Main evaluation gate for answer quality assessment.

    Provides comprehensive quality evaluation using multiple assessment modules
    with configurable strategies and performance optimization.
    """

    def __init__(self, environment: str = "dev", config: Optional[EvalConfig] = None):
        """Initialize evaluation gate with configuration."""
        self.environment = environment
        self.config = config or EvalConfig()
        self.evaluation_cache: Dict[str, EvaluationResult] = {}

        logger.info(f"EvalGate initialized for environment: {environment}")

    def evaluate_answer(
        self,
        answer: str,
        query: str,
        context: Optional[EvalContext] = None,
        provenance_data: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> EvaluationResult:
        """
        Evaluate answer quality and determine gate decision.

        Args:
            answer: Generated answer text
            query: Original user query
            context: Evaluation context and requirements
            provenance_data: Provenance information from FR-027
            sources: Source documents and metadata

        Returns:
            EvaluationResult with comprehensive quality assessment
        """
        start_time = time.perf_counter()

        # Create evaluation context if not provided
        if context is None:
            context = EvalContext(environment=self.environment)

        # Adapt configuration based on context
        eval_config = context.get_adapted_config(self.config)

        # Create evaluation result
        result = EvaluationResult(
            query_hash=self._hash_query(query),
            answer_id=self._hash_answer(answer),
            strategy_used=eval_config.strategy,
            evaluation_context={
                "query": query[:100] + "..." if len(query) > 100 else query,
                "answer_length": len(answer),
                "environment": self.environment,
                "strategy": eval_config.strategy.value
            }
        )

        try:
            # Check cache if enabled
            cache_key = self._get_cache_key(query, answer, eval_config)
            if eval_config.enable_caching and cache_key in self.evaluation_cache:
                cached_result = self.evaluation_cache[cache_key]
                if time.time() - cached_result.started_at < eval_config.cache_ttl_seconds:
                    logger.debug(f"Using cached evaluation result for query hash: {result.query_hash[:8]}")
                    return cached_result

            # Perform quality evaluation
            quality_metrics = self._evaluate_quality(
                answer, query, eval_config, provenance_data, sources
            )
            result.quality_metrics = quality_metrics

            # Make gate decision
            gate_decision, decision_confidence = self._make_gate_decision(
                quality_metrics, eval_config, context
            )
            result.gate_decision = gate_decision
            result.decision_confidence = decision_confidence

            # Generate feedback and suggestions
            result.quality_issues = self._identify_quality_issues(quality_metrics, eval_config)
            result.improvement_suggestions = self._generate_improvement_suggestions(
                quality_metrics, eval_config, answer, query
            )
            result.critical_failures = self._identify_critical_failures(quality_metrics, eval_config)

            # Perform source and citation validation if enabled
            if eval_config.enable_source_validation and sources:
                result.source_validation_results = self._validate_sources(answer, sources)

            if eval_config.enable_citation_checking and sources:
                result.citation_validation_results = self._validate_citations(answer, sources)

            # Record threshold comparisons
            result.threshold_comparisons = self._get_threshold_comparisons(quality_metrics, eval_config)

            # Finalize timing
            result.completed_at = time.time()
            result.evaluation_time_ms = (time.perf_counter() - start_time) * 1000

            # Cache result if enabled
            if eval_config.enable_caching:
                self.evaluation_cache[cache_key] = result

            logger.debug(
                f"Answer evaluation completed: {gate_decision.value} "
                f"(score: {quality_metrics.overall_quality_score():.3f}, "
                f"time: {result.evaluation_time_ms:.2f}ms)"
            )

            return result

        except Exception as e:
            # Handle evaluation errors gracefully
            logger.warning(f"Error during evaluation: {e}")

            if eval_config.fallback_on_timeout:
                result.gate_decision = eval_config.fallback_decision
                result.decision_confidence = 0.5
                result.critical_failures = [f"Evaluation error: {str(e)}"]
                result.evaluation_time_ms = (time.perf_counter() - start_time) * 1000
                return result
            else:
                raise

    def _evaluate_quality(
        self,
        answer: str,
        query: str,
        config: EvalConfig,
        provenance_data: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> QualityMetrics:
        """Perform comprehensive quality evaluation."""
        metrics = QualityMetrics()

        # Basic answer characteristics
        metrics.answer_length = len(answer)
        metrics.source_count = len(sources) if sources else 0

        if config.strategy == EvalStrategy.FAST:
            # Fast evaluation - basic checks only
            metrics.accuracy_score = self._fast_accuracy_check(answer, query, sources)
            metrics.completeness_score = self._fast_completeness_check(answer, query)
            metrics.relevance_score = self._fast_relevance_check(answer, query)
            metrics.coherence_score = self._fast_coherence_check(answer)

        else:
            # Comprehensive evaluation
            metrics.accuracy_score = self._evaluate_accuracy(answer, query, sources, provenance_data)
            metrics.completeness_score = self._evaluate_completeness(answer, query, provenance_data)
            metrics.relevance_score = self._evaluate_relevance(answer, query)
            metrics.coherence_score = self._evaluate_coherence(answer)

            # TTRPG domain-specific evaluation
            if config.enable_domain_validation:
                metrics.rules_accuracy = self._evaluate_rules_accuracy(answer, sources)
                metrics.citation_quality = self._evaluate_citation_quality(answer, sources)
                metrics.domain_appropriateness = self._evaluate_domain_appropriateness(answer, query)

            # Confidence and uncertainty assessment
            if config.enable_confidence_calibration:
                metrics.confidence_score = self._assess_confidence(answer, provenance_data)
                metrics.uncertainty_level = self._assess_uncertainty(answer, provenance_data)
                metrics.source_reliability = self._assess_source_reliability(sources, provenance_data)

        # Calculate derived metrics
        if sources:
            metrics.citation_density = self._calculate_citation_density(answer)
            metrics.fact_density = self._calculate_fact_density(answer)

        return metrics

    def _evaluate_accuracy(
        self,
        answer: str,
        query: str,
        sources: Optional[List[Dict[str, Any]]],
        provenance_data: Optional[Dict[str, Any]]
    ) -> float:
        """Evaluate answer accuracy using source verification."""
        if not sources:
            return 0.7  # Default score when no sources available

        accuracy_scores = []

        # Source-based accuracy assessment
        for source in sources:
            source_content = source.get('content', '')
            source_score = source.get('score', 0.0)

            # Simple content overlap check
            answer_tokens = set(answer.lower().split())
            source_tokens = set(source_content.lower().split())
            overlap_ratio = len(answer_tokens & source_tokens) / max(len(answer_tokens), 1)

            # Weight by source confidence
            weighted_score = overlap_ratio * min(source_score, 1.0)
            accuracy_scores.append(weighted_score)

        # Use provenance data if available
        if provenance_data and 'retrieval_provenance' in provenance_data:
            retrieval_data = provenance_data['retrieval_provenance']
            if hasattr(retrieval_data, 'results_returned') and retrieval_data.results_returned > 0:
                # Boost score if good retrieval results
                base_score = mean(accuracy_scores) if accuracy_scores else 0.5
                return min(1.0, base_score * 1.2)

        return mean(accuracy_scores) if accuracy_scores else 0.6

    def _evaluate_completeness(
        self,
        answer: str,
        query: str,
        provenance_data: Optional[Dict[str, Any]]
    ) -> float:
        """Evaluate answer completeness against query requirements."""

        # Basic completeness heuristics
        query_keywords = set(re.findall(r'\w+', query.lower()))
        answer_keywords = set(re.findall(r'\w+', answer.lower()))

        keyword_coverage = len(query_keywords & answer_keywords) / max(len(query_keywords), 1)

        # Length-based completeness
        answer_length_score = min(1.0, len(answer) / 200)  # Assume 200 chars is adequate

        # Question-specific completeness
        if '?' in query:
            # Direct question - expect direct answer
            has_direct_answer = any(word in answer.lower() for word in ['yes', 'no', 'is', 'are', 'can', 'will'])
            direct_answer_score = 0.8 if has_direct_answer else 0.4
        else:
            direct_answer_score = 0.7  # Not a direct question

        return mean([keyword_coverage, answer_length_score, direct_answer_score])

    def _evaluate_relevance(self, answer: str, query: str) -> float:
        """Evaluate answer relevance to the query."""

        # Keyword overlap relevance
        query_terms = set(re.findall(r'\w+', query.lower()))
        answer_terms = set(re.findall(r'\w+', answer.lower()))

        if not query_terms:
            return 0.5

        overlap_ratio = len(query_terms & answer_terms) / len(query_terms)

        # TTRPG-specific relevance checks
        ttrpg_terms = {'spell', 'damage', 'class', 'level', 'roll', 'dice', 'attack', 'saving', 'throw'}
        query_has_ttrpg = bool(query_terms & ttrpg_terms)
        answer_has_ttrpg = bool(answer_terms & ttrpg_terms)

        ttrpg_relevance = 1.0 if (query_has_ttrpg == answer_has_ttrpg) else 0.6

        return mean([overlap_ratio, ttrpg_relevance])

    def _evaluate_coherence(self, answer: str) -> float:
        """Evaluate logical coherence and consistency of answer."""

        # Basic coherence heuristics
        sentences = re.split(r'[.!?]+', answer)
        if len(sentences) < 2:
            return 0.8  # Single sentence, assume coherent

        # Check for contradictory statements (simple)
        contradiction_indicators = ['but', 'however', 'although', 'not', "doesn't", "don't"]
        contradiction_count = sum(1 for sentence in sentences
                                  for indicator in contradiction_indicators
                                  if indicator in sentence.lower())

        contradiction_penalty = min(0.3, contradiction_count * 0.1)

        # Check for logical flow (basic)
        has_logical_connectors = any(connector in answer.lower()
                                     for connector in ['because', 'therefore', 'thus', 'so', 'since'])
        logic_bonus = 0.1 if has_logical_connectors else 0.0

        base_coherence = 0.8  # Assume reasonable coherence
        return max(0.0, min(1.0, base_coherence - contradiction_penalty + logic_bonus))

    def _evaluate_rules_accuracy(self, answer: str, sources: Optional[List[Dict[str, Any]]]) -> float:
        """Evaluate TTRPG rules accuracy."""
        if not sources:
            return 0.6

        # Look for game rules keywords
        rules_keywords = {'damage', 'spell', 'attack', 'saving throw', 'AC', 'HP', 'level', 'class'}
        answer_lower = answer.lower()

        # Check if answer contains rules-related content
        has_rules_content = any(keyword in answer_lower for keyword in rules_keywords)

        if not has_rules_content:
            return 0.7  # Not rules-specific, can't assess

        # Check against source content for rules accuracy
        rules_accuracy_scores = []
        for source in sources:
            source_content = source.get('content', '').lower()
            if any(keyword in source_content for keyword in rules_keywords):
                # Simple overlap check for rules content
                rules_terms = [term for term in answer.split() if term.lower() in rules_keywords]
                source_terms = [term for term in source_content.split() if term.lower() in rules_keywords]

                if rules_terms and source_terms:
                    overlap = len(set(rules_terms) & set(source_terms)) / max(len(set(rules_terms)), 1)
                    rules_accuracy_scores.append(overlap)

        return mean(rules_accuracy_scores) if rules_accuracy_scores else 0.7

    def _evaluate_citation_quality(self, answer: str, sources: Optional[List[Dict[str, Any]]]) -> float:
        """Evaluate quality of citations in answer."""
        if not sources:
            return 0.5

        # Count citations in answer
        citation_patterns = [r'\[(\d+)\]', r'\(([^)]+)\)', r'page \d+', r'p\. \d+']
        citation_count = sum(len(re.findall(pattern, answer)) for pattern in citation_patterns)

        # Citation density
        if len(answer) == 0:
            return 0.0

        citation_density = citation_count / max(len(answer.split()), 1)

        # Check if citations reference available sources
        source_references = 0
        for source in sources:
            source_id = source.get('id', '')
            source_path = source.get('source', '')
            if source_id in answer or any(part in answer for part in source_path.split('/')):
                source_references += 1

        source_reference_ratio = source_references / max(len(sources), 1)

        return mean([min(1.0, citation_density * 10), source_reference_ratio])

    def _evaluate_domain_appropriateness(self, answer: str, query: str) -> float:
        """Evaluate appropriateness for TTRPG domain."""

        # TTRPG context indicators
        ttrpg_terms = {
            'spell', 'damage', 'class', 'level', 'roll', 'dice', 'attack', 'saving', 'throw',
            'armor', 'weapon', 'magic', 'character', 'campaign', 'DM', 'GM', 'player',
            'pathfinder', 'dnd', 'd&d', '5e', 'pf2e'
        }

        query_lower = query.lower()
        answer_lower = answer.lower()

        query_ttrpg_score = len([term for term in ttrpg_terms if term in query_lower]) / max(len(query.split()), 1)
        answer_ttrpg_score = len([term for term in ttrpg_terms if term in answer_lower]) / max(len(answer.split()), 1)

        # Domain consistency
        if query_ttrpg_score > 0.1:  # Query is TTRPG-related
            return min(1.0, answer_ttrpg_score * 5)  # Answer should also be TTRPG-related
        else:
            return 0.8  # Non-TTRPG query, domain appropriateness less critical

    def _assess_confidence(self, answer: str, provenance_data: Optional[Dict[str, Any]]) -> float:
        """Assess confidence in answer quality."""
        confidence_indicators = []

        # Length-based confidence
        length_confidence = min(1.0, len(answer) / 150)
        confidence_indicators.append(length_confidence)

        # Definitiveness indicators
        definitive_words = ['is', 'are', 'will', 'must', 'always', 'never']
        tentative_words = ['might', 'could', 'possibly', 'perhaps', 'maybe']

        definitive_count = sum(1 for word in definitive_words if word in answer.lower())
        tentative_count = sum(1 for word in tentative_words if word in answer.lower())

        definitiveness_score = (definitive_count - tentative_count * 0.5) / max(len(answer.split()), 1)
        confidence_indicators.append(max(0.0, min(1.0, definitiveness_score * 5 + 0.5)))

        # Provenance-based confidence
        if provenance_data:
            if 'quality_metrics' in provenance_data:
                quality_metrics = provenance_data['quality_metrics']
                if hasattr(quality_metrics, 'confidence_score'):
                    confidence_indicators.append(quality_metrics.confidence_score)

        return mean(confidence_indicators) if confidence_indicators else 0.6

    def _assess_uncertainty(self, answer: str, provenance_data: Optional[Dict[str, Any]]) -> float:
        """Assess uncertainty level in answer."""

        # Uncertainty indicators
        uncertainty_words = ['uncertain', 'unclear', 'unknown', 'depends', 'varies', 'might', 'could']
        uncertainty_count = sum(1 for word in uncertainty_words if word in answer.lower())

        # Hedge words
        hedge_words = ['generally', 'usually', 'typically', 'often', 'sometimes']
        hedge_count = sum(1 for word in hedge_words if word in answer.lower())

        total_uncertainty = uncertainty_count + hedge_count * 0.5
        uncertainty_ratio = total_uncertainty / max(len(answer.split()), 1)

        return min(1.0, uncertainty_ratio * 10)

    def _assess_source_reliability(
        self,
        sources: Optional[List[Dict[str, Any]]],
        provenance_data: Optional[Dict[str, Any]]
    ) -> float:
        """Assess reliability of sources used."""
        if not sources:
            return 0.5

        reliability_scores = []

        for source in sources:
            # Source score from retrieval
            source_score = source.get('score', 0.5)
            reliability_scores.append(source_score)

            # Source type reliability
            source_type = source.get('metadata', {}).get('source_type', 'unknown')
            type_reliability = {
                'phb': 0.9,  # Player's Handbook
                'dmg': 0.9,  # Dungeon Master's Guide
                'official': 0.85,
                'supplement': 0.8,
                'unknown': 0.6
            }.get(source_type, 0.6)
            reliability_scores.append(type_reliability)

        return mean(reliability_scores) if reliability_scores else 0.6

    def _fast_accuracy_check(self, answer: str, query: str, sources: Optional[List[Dict[str, Any]]]) -> float:
        """Fast accuracy assessment for time-constrained evaluation."""
        if not sources:
            return 0.6

        # Simple keyword overlap
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        source_words = set()

        for source in sources[:3]:  # Limit to first 3 sources for speed
            source_words.update(source.get('content', '').lower().split())

        query_answer_overlap = len(query_words & answer_words) / max(len(query_words), 1)
        answer_source_overlap = len(answer_words & source_words) / max(len(answer_words), 1)

        return mean([query_answer_overlap, answer_source_overlap])

    def _fast_completeness_check(self, answer: str, query: str) -> float:
        """Fast completeness assessment."""
        # Basic length and keyword coverage
        min_length_met = len(answer) >= 50
        has_relevant_keywords = len(set(query.lower().split()) & set(answer.lower().split())) > 0

        return 0.8 if (min_length_met and has_relevant_keywords) else 0.4

    def _fast_relevance_check(self, answer: str, query: str) -> float:
        """Fast relevance assessment."""
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())

        overlap_ratio = len(query_words & answer_words) / max(len(query_words), 1)
        return min(1.0, overlap_ratio * 2)

    def _fast_coherence_check(self, answer: str) -> float:
        """Fast coherence assessment."""
        # Basic checks
        has_reasonable_length = 20 <= len(answer) <= 1000
        has_sentence_structure = '.' in answer or '!' in answer or '?' in answer

        return 0.7 if (has_reasonable_length and has_sentence_structure) else 0.4

    def _calculate_citation_density(self, answer: str) -> float:
        """Calculate citation density in answer."""
        if len(answer) == 0:
            return 0.0

        citation_patterns = [r'\[(\d+)\]', r'\(([^)]+)\)', r'page \d+']
        citation_count = sum(len(re.findall(pattern, answer)) for pattern in citation_patterns)

        return citation_count / len(answer.split())

    def _calculate_fact_density(self, answer: str) -> float:
        """Calculate fact density in answer."""
        if len(answer) == 0:
            return 0.0

        # Simple heuristic: sentences with numbers or specific terms
        fact_indicators = [r'\d+', 'level', 'damage', 'points', 'bonus', 'penalty']
        fact_count = sum(len(re.findall(pattern, answer, re.IGNORECASE)) for pattern in fact_indicators)

        return fact_count / max(len(answer.split()), 1)

    def _make_gate_decision(
        self,
        metrics: QualityMetrics,
        config: EvalConfig,
        context: EvalContext
    ) -> Tuple[GateDecision, float]:
        """Make gate decision based on quality metrics and thresholds."""

        overall_score = metrics.overall_quality_score(config.quality_weights)

        # Check critical thresholds
        critical_failures = []

        if metrics.accuracy_score < config.minimum_accuracy_score:
            critical_failures.append("accuracy")

        if overall_score < config.minimum_overall_score:
            critical_failures.append("overall_quality")

        if config.enable_domain_validation and metrics.rules_accuracy < config.minimum_rules_accuracy:
            critical_failures.append("rules_accuracy")

        # Decision logic
        if critical_failures:
            return GateDecision.FAIL, 0.9

        # Quality level based decisions
        quality_level = metrics.quality_level(config.quality_weights)

        if quality_level in [QualityLevel.EXCELLENT, QualityLevel.GOOD]:
            return GateDecision.PASS, 0.9

        elif quality_level == QualityLevel.ACCEPTABLE:
            if context.required_quality_level == QualityLevel.GOOD:
                return GateDecision.REVIEW, 0.7
            else:
                return GateDecision.PASS, 0.8

        elif quality_level == QualityLevel.POOR:
            return GateDecision.REVIEW, 0.6

        else:  # UNACCEPTABLE
            return GateDecision.FAIL, 0.9

    def _identify_quality_issues(self, metrics: QualityMetrics, config: EvalConfig) -> List[str]:
        """Identify specific quality issues."""
        issues = []

        if metrics.accuracy_score < config.minimum_accuracy_score:
            issues.append(f"Low accuracy score: {metrics.accuracy_score:.2f}")

        if metrics.completeness_score < config.minimum_completeness_score:
            issues.append(f"Incomplete answer: {metrics.completeness_score:.2f}")

        if metrics.relevance_score < config.minimum_relevance_score:
            issues.append(f"Low relevance: {metrics.relevance_score:.2f}")

        if metrics.coherence_score < 0.6:
            issues.append(f"Coherence issues: {metrics.coherence_score:.2f}")

        if config.enable_domain_validation:
            if metrics.rules_accuracy < config.minimum_rules_accuracy:
                issues.append(f"TTRPG rules accuracy issues: {metrics.rules_accuracy:.2f}")

            if metrics.citation_quality < config.minimum_citation_quality:
                issues.append(f"Poor citation quality: {metrics.citation_quality:.2f}")

        return issues

    def _generate_improvement_suggestions(
        self,
        metrics: QualityMetrics,
        config: EvalConfig,
        answer: str,
        query: str
    ) -> List[str]:
        """Generate specific improvement suggestions."""
        suggestions = []

        if metrics.accuracy_score < 0.7:
            suggestions.append("Verify facts against reliable sources")

        if metrics.completeness_score < 0.6:
            suggestions.append("Provide more comprehensive coverage of the query topic")

        if metrics.citation_quality < 0.5:
            suggestions.append("Add proper citations with page numbers")

        if metrics.coherence_score < 0.6:
            suggestions.append("Improve logical flow and consistency")

        if len(answer) < 50:
            suggestions.append("Provide more detailed explanation")

        if metrics.source_count == 0:
            suggestions.append("Include source references to support claims")

        return suggestions

    def _identify_critical_failures(self, metrics: QualityMetrics, config: EvalConfig) -> List[str]:
        """Identify critical quality failures."""
        failures = []

        if metrics.accuracy_score < 0.4:
            failures.append("Critical accuracy failure")

        if metrics.overall_quality_score() < 0.3:
            failures.append("Overall quality unacceptable")

        if config.enable_domain_validation and metrics.rules_accuracy < 0.5:
            failures.append("TTRPG rules accuracy critical failure")

        return failures

    def _validate_sources(self, answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate source usage in answer."""
        validation_results = []

        for source in sources:
            source_id = source.get('id', '')
            source_content = source.get('content', '')

            # Check if source is referenced in answer
            is_referenced = (
                source_id in answer or
                any(word in answer.lower() for word in source_content.lower().split()[:10])
            )

            validation_results.append({
                'source_id': source_id,
                'is_referenced': is_referenced,
                'relevance_score': source.get('score', 0.0)
            })

        return validation_results

    def _validate_citations(self, answer: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate citation accuracy and completeness."""
        citation_results = []

        # Find citation patterns
        citation_patterns = [r'\[(\d+)\]', r'\(([^)]+)\)']
        citations_found = []

        for pattern in citation_patterns:
            citations_found.extend(re.findall(pattern, answer))

        # Check citation-source mapping
        for i, citation in enumerate(citations_found):
            is_valid = i < len(sources)  # Simple validation
            citation_results.append({
                'citation': citation,
                'is_valid': is_valid,
                'position': i
            })

        return citation_results

    def _get_threshold_comparisons(self, metrics: QualityMetrics, config: EvalConfig) -> Dict[str, Dict[str, float]]:
        """Get threshold comparisons for debugging."""
        return {
            'accuracy': {
                'score': metrics.accuracy_score,
                'threshold': config.minimum_accuracy_score,
                'passes': metrics.accuracy_score >= config.minimum_accuracy_score
            },
            'completeness': {
                'score': metrics.completeness_score,
                'threshold': config.minimum_completeness_score,
                'passes': metrics.completeness_score >= config.minimum_completeness_score
            },
            'overall': {
                'score': metrics.overall_quality_score(config.quality_weights),
                'threshold': config.minimum_overall_score,
                'passes': metrics.overall_quality_score(config.quality_weights) >= config.minimum_overall_score
            }
        }

    def _hash_query(self, query: str) -> str:
        """Generate hash for query caching."""
        return hashlib.sha256(query.strip().encode('utf-8')).hexdigest()[:16]

    def _hash_answer(self, answer: str) -> str:
        """Generate hash for answer identification."""
        return hashlib.sha256(answer.strip().encode('utf-8')).hexdigest()[:16]

    def _get_cache_key(self, query: str, answer: str, config: EvalConfig) -> str:
        """Generate cache key for evaluation result."""
        key_components = [
            self._hash_query(query),
            self._hash_answer(answer),
            config.strategy.value,
            str(config.minimum_overall_score)
        ]
        return hashlib.sha256('|'.join(key_components).encode()).hexdigest()[:16]

    def get_evaluation_summary(self, result: EvaluationResult) -> Dict[str, Any]:
        """Get summary of evaluation result."""
        return {
            'gate_decision': result.gate_decision.value,
            'quality_level': result.quality_metrics.quality_level().value,
            'overall_score': result.quality_metrics.overall_quality_score(),
            'decision_confidence': result.decision_confidence,
            'evaluation_time_ms': result.evaluation_time_ms,
            'quality_issues_count': len(result.quality_issues),
            'critical_failures_count': len(result.critical_failures),
            'improvement_suggestions_count': len(result.improvement_suggestions)
        }

    def clear_cache(self):
        """Clear evaluation cache."""
        self.evaluation_cache.clear()
        logger.debug("Evaluation cache cleared")