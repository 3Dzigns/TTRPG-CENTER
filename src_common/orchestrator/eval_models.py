"""
Evaluation Models and Quality Metrics for FR-028 Eval Gate

Defines data structures for answer quality assessment, evaluation results,
and configuration models for the evaluation gate system.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from statistics import mean, harmonic_mean


class QualityLevel(Enum):
    """Quality level classifications for evaluation results."""
    EXCELLENT = "excellent"      # 0.9+
    GOOD = "good"               # 0.75-0.89
    ACCEPTABLE = "acceptable"   # 0.6-0.74
    POOR = "poor"              # 0.4-0.59
    UNACCEPTABLE = "unacceptable"  # <0.4


class EvalStrategy(Enum):
    """Evaluation strategies for different query types."""
    COMPREHENSIVE = "comprehensive"    # Full evaluation suite
    FAST = "fast"                     # Basic quality checks only
    DOMAIN_FOCUSED = "domain_focused"  # TTRPG-specific validation
    ACCURACY_FIRST = "accuracy_first"  # Prioritize accuracy over speed


class GateDecision(Enum):
    """Gate decisions for answer delivery."""
    PASS = "pass"           # Answer meets quality standards
    FAIL = "fail"           # Answer does not meet standards
    REVIEW = "review"       # Borderline quality, needs review
    RETRY = "retry"         # Suggest retry with different strategy


@dataclass
class QualityMetrics:
    """Comprehensive quality metrics for answer evaluation."""

    # Core quality dimensions
    accuracy_score: float = 0.0          # Source verification accuracy (0-1)
    completeness_score: float = 0.0      # Query requirement coverage (0-1)
    relevance_score: float = 0.0         # Answer relevance to query (0-1)
    coherence_score: float = 0.0         # Logical consistency (0-1)

    # TTRPG domain-specific metrics
    rules_accuracy: float = 0.0          # Game rules correctness (0-1)
    citation_quality: float = 0.0        # Source citation quality (0-1)
    domain_appropriateness: float = 0.0  # Domain context correctness (0-1)

    # Confidence and uncertainty
    confidence_score: float = 0.0        # Overall confidence (0-1)
    uncertainty_level: float = 0.0       # Uncertainty quantification (0-1)
    source_reliability: float = 0.0      # Source trustworthiness (0-1)

    # Answer characteristics
    answer_length: int = 0               # Character count
    source_count: int = 0                # Number of sources cited
    fact_density: float = 0.0            # Facts per unit length
    citation_density: float = 0.0        # Citations per unit length

    # Timestamps and processing
    evaluation_time_ms: float = 0.0      # Evaluation processing time
    timestamp: float = field(default_factory=time.time)

    def overall_quality_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate weighted overall quality score."""
        if weights is None:
            weights = {
                "accuracy": 0.3,
                "completeness": 0.25,
                "relevance": 0.2,
                "coherence": 0.15,
                "domain": 0.1
            }

        domain_score = mean([self.rules_accuracy, self.citation_quality, self.domain_appropriateness])

        weighted_score = (
            self.accuracy_score * weights.get("accuracy", 0.3) +
            self.completeness_score * weights.get("completeness", 0.25) +
            self.relevance_score * weights.get("relevance", 0.2) +
            self.coherence_score * weights.get("coherence", 0.15) +
            domain_score * weights.get("domain", 0.1)
        )

        return min(1.0, max(0.0, weighted_score))

    def quality_level(self, weights: Optional[Dict[str, float]] = None) -> QualityLevel:
        """Determine quality level based on overall score."""
        score = self.overall_quality_score(weights)

        if score >= 0.9:
            return QualityLevel.EXCELLENT
        elif score >= 0.75:
            return QualityLevel.GOOD
        elif score >= 0.6:
            return QualityLevel.ACCEPTABLE
        elif score >= 0.4:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNACCEPTABLE


@dataclass
class EvaluationResult:
    """Result of answer evaluation with detailed quality assessment."""

    # Evaluation metadata
    evaluation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_hash: str = ""
    answer_id: str = ""
    strategy_used: EvalStrategy = EvalStrategy.COMPREHENSIVE

    # Quality assessment
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)
    gate_decision: GateDecision = GateDecision.REVIEW
    decision_confidence: float = 0.0

    # Detailed feedback
    quality_issues: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    critical_failures: List[str] = field(default_factory=list)

    # Source validation
    source_validation_results: List[Dict[str, Any]] = field(default_factory=list)
    citation_validation_results: List[Dict[str, Any]] = field(default_factory=list)

    # Performance metrics
    evaluation_time_ms: float = 0.0
    threshold_comparisons: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Context and debugging
    evaluation_context: Dict[str, Any] = field(default_factory=dict)
    debug_info: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def is_passing(self) -> bool:
        """Check if evaluation result indicates passing quality."""
        return self.gate_decision == GateDecision.PASS

    def has_critical_issues(self) -> bool:
        """Check if evaluation found critical quality issues."""
        return len(self.critical_failures) > 0

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get summary of quality assessment."""
        return {
            "overall_score": self.quality_metrics.overall_quality_score(),
            "quality_level": self.quality_metrics.quality_level().value,
            "gate_decision": self.gate_decision.value,
            "decision_confidence": self.decision_confidence,
            "critical_issues": len(self.critical_failures),
            "improvement_suggestions": len(self.improvement_suggestions),
            "evaluation_time_ms": self.evaluation_time_ms
        }


@dataclass
class EvalConfig:
    """Configuration for evaluation gate behavior."""

    # Evaluation strategy
    strategy: EvalStrategy = EvalStrategy.COMPREHENSIVE
    enabled: bool = True

    # Quality thresholds
    minimum_overall_score: float = 0.6
    minimum_accuracy_score: float = 0.7
    minimum_completeness_score: float = 0.6
    minimum_relevance_score: float = 0.7

    # TTRPG domain thresholds
    minimum_rules_accuracy: float = 0.8
    minimum_citation_quality: float = 0.6

    # Performance settings
    max_evaluation_time_ms: float = 50.0
    enable_caching: bool = True
    cache_ttl_seconds: int = 300

    # Quality weights
    quality_weights: Dict[str, float] = field(default_factory=lambda: {
        "accuracy": 0.3,
        "completeness": 0.25,
        "relevance": 0.2,
        "coherence": 0.15,
        "domain": 0.1
    })

    # Evaluation modules
    enable_source_validation: bool = True
    enable_citation_checking: bool = True
    enable_domain_validation: bool = True
    enable_confidence_calibration: bool = True

    # Fallback behavior
    fallback_on_timeout: bool = True
    fallback_decision: GateDecision = GateDecision.REVIEW
    enable_fast_mode_fallback: bool = True

    def get_threshold_for_metric(self, metric_name: str) -> float:
        """Get quality threshold for specific metric."""
        thresholds = {
            "accuracy": self.minimum_accuracy_score,
            "completeness": self.minimum_completeness_score,
            "relevance": self.minimum_relevance_score,
            "rules_accuracy": self.minimum_rules_accuracy,
            "citation_quality": self.minimum_citation_quality,
            "overall": self.minimum_overall_score
        }
        return thresholds.get(metric_name, 0.6)

    def should_use_fast_mode(self, time_constraint_ms: float) -> bool:
        """Determine if fast mode should be used based on time constraints."""
        return (
            time_constraint_ms < self.max_evaluation_time_ms and
            self.enable_fast_mode_fallback
        )


@dataclass
class EvalContext:
    """Context information for evaluation processing."""

    environment: str = "dev"
    query_complexity: str = "medium"
    domain_requirements: Dict[str, Any] = field(default_factory=dict)
    time_constraint_ms: float = 50.0

    # Integration context
    provenance_bundle_id: Optional[str] = None
    classification: Optional[Any] = None
    retrieval_strategy: Optional[str] = None

    # Quality requirements
    required_quality_level: QualityLevel = QualityLevel.ACCEPTABLE
    critical_accuracy_domains: List[str] = field(default_factory=list)

    # Performance context
    max_processing_time_ms: float = 100.0
    enable_detailed_feedback: bool = True

    def get_adapted_config(self, base_config: EvalConfig) -> EvalConfig:
        """Adapt evaluation config based on context."""
        adapted = EvalConfig(
            strategy=base_config.strategy,
            enabled=base_config.enabled,
            minimum_overall_score=base_config.minimum_overall_score,
            minimum_accuracy_score=base_config.minimum_accuracy_score,
            minimum_completeness_score=base_config.minimum_completeness_score,
            minimum_relevance_score=base_config.minimum_relevance_score,
            minimum_rules_accuracy=base_config.minimum_rules_accuracy,
            minimum_citation_quality=base_config.minimum_citation_quality,
            max_evaluation_time_ms=min(base_config.max_evaluation_time_ms, self.time_constraint_ms),
            enable_caching=base_config.enable_caching,
            cache_ttl_seconds=base_config.cache_ttl_seconds,
            quality_weights=base_config.quality_weights.copy(),
            enable_source_validation=base_config.enable_source_validation,
            enable_citation_checking=base_config.enable_citation_checking,
            enable_domain_validation=base_config.enable_domain_validation,
            enable_confidence_calibration=base_config.enable_confidence_calibration,
            fallback_on_timeout=base_config.fallback_on_timeout,
            fallback_decision=base_config.fallback_decision,
            enable_fast_mode_fallback=base_config.enable_fast_mode_fallback
        )

        # Adapt thresholds based on required quality level
        if self.required_quality_level == QualityLevel.EXCELLENT:
            adapted.minimum_overall_score = max(0.9, adapted.minimum_overall_score)
            adapted.minimum_accuracy_score = max(0.9, adapted.minimum_accuracy_score)
        elif self.required_quality_level == QualityLevel.GOOD:
            adapted.minimum_overall_score = max(0.75, adapted.minimum_overall_score)

        # Use fast mode if time constrained
        if self.time_constraint_ms < 25.0:
            adapted.strategy = EvalStrategy.FAST
            adapted.enable_source_validation = False
            adapted.enable_citation_checking = False

        return adapted


def create_quality_level(score: float) -> QualityLevel:
    """Create quality level from numeric score."""
    if score >= 0.9:
        return QualityLevel.EXCELLENT
    elif score >= 0.75:
        return QualityLevel.GOOD
    elif score >= 0.6:
        return QualityLevel.ACCEPTABLE
    elif score >= 0.4:
        return QualityLevel.POOR
    else:
        return QualityLevel.UNACCEPTABLE


def aggregate_quality_scores(scores: List[float], method: str = "harmonic_mean") -> float:
    """Aggregate multiple quality scores using specified method."""
    if not scores:
        return 0.0

    if len(scores) == 1:
        return scores[0]

    # Filter out zero scores for harmonic mean
    non_zero_scores = [s for s in scores if s > 0]

    if method == "harmonic_mean" and non_zero_scores:
        return harmonic_mean(non_zero_scores)
    elif method == "arithmetic_mean":
        return mean(scores)
    elif method == "min":
        return min(scores)
    elif method == "weighted_mean":
        # Default equal weights if not specified
        return mean(scores)
    else:
        return mean(scores)


def calculate_confidence_calibration(
    predicted_confidence: float,
    actual_accuracy: float,
    sample_size: int = 100
) -> Dict[str, float]:
    """Calculate confidence calibration metrics."""

    # Simple calibration error approximation
    calibration_error = abs(predicted_confidence - actual_accuracy)

    # Reliability score based on calibration
    reliability_score = max(0.0, 1.0 - (calibration_error * 2))

    # Confidence interval estimation
    margin_of_error = 1.96 * (0.5 / (sample_size ** 0.5))  # Conservative estimate

    return {
        "calibration_error": calibration_error,
        "reliability_score": reliability_score,
        "margin_of_error": margin_of_error,
        "is_well_calibrated": calibration_error < 0.1
    }