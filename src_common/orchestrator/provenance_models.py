"""
Answer Provenance Data Models

Defines data structures for tracking complete answer provenance including:
- Query processing provenance
- Retrieval and reranking provenance
- Answer generation provenance
- Source attribution and confidence metrics
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class ProvenanceStage(Enum):
    """Stages in the answer generation pipeline."""
    QUERY_PLANNING = "query_planning"
    RETRIEVAL = "retrieval"
    RERANKING = "reranking"
    ANSWER_GENERATION = "answer_generation"
    FINALIZATION = "finalization"


class ConfidenceLevel(Enum):
    """Confidence levels for various provenance components."""
    VERY_HIGH = "very_high"  # >0.9
    HIGH = "high"           # 0.7-0.9
    MEDIUM = "medium"       # 0.5-0.7
    LOW = "low"            # 0.3-0.5
    VERY_LOW = "very_low"  # <0.3


@dataclass
class SourceAttribution:
    """Attribution information for a source document."""

    # Source identification
    source_id: str
    source_path: str
    source_type: str  # phb, dmg, homebrew, etc.

    # Location within source
    page_number: Optional[int] = None
    section: Optional[str] = None
    paragraph: Optional[str] = None

    # Relevance and confidence
    relevance_score: float = 0.0
    confidence_score: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM

    # Content attribution
    excerpt: Optional[str] = None
    excerpt_length: int = 0

    # Usage tracking
    used_in_answer: bool = False
    contribution_weight: float = 0.0


@dataclass
class QueryProvenance:
    """Provenance for query processing stage."""

    # Query information
    original_query: str
    processed_query: str
    query_hash: str

    # Classification results
    intent: str
    domain: str
    complexity: str
    classification_confidence: float

    # Planning decisions
    strategy_selected: str
    strategy_reason: str
    alternative_strategies: List[str] = field(default_factory=list)

    # Performance metrics
    processing_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class RetrievalProvenance:
    """Provenance for retrieval stage."""

    # Retrieval configuration
    strategy: str
    top_k: int
    graph_expansion_enabled: bool

    # Search execution
    search_terms: List[str] = field(default_factory=list)
    expanded_terms: List[str] = field(default_factory=list)
    filters_applied: List[str] = field(default_factory=list)

    # Results
    total_candidates: int = 0
    results_returned: int = 0
    sources_found: List[SourceAttribution] = field(default_factory=list)

    # Graph augmentation
    graph_nodes_explored: int = 0
    relationships_found: int = 0
    cross_references: List[str] = field(default_factory=list)

    # Performance metrics
    retrieval_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class RerankingProvenance:
    """Provenance for reranking stage."""

    # Reranking configuration
    strategy: str
    signal_weights: Dict[str, float] = field(default_factory=dict)

    # Signal contributions
    vector_signals: Dict[str, float] = field(default_factory=dict)
    graph_signals: Dict[str, float] = field(default_factory=dict)
    content_signals: Dict[str, float] = field(default_factory=dict)
    domain_signals: Dict[str, float] = field(default_factory=dict)

    # Ranking changes
    original_ranking: List[str] = field(default_factory=list)
    final_ranking: List[str] = field(default_factory=list)
    ranking_changes: List[Dict[str, Any]] = field(default_factory=list)

    # Quality metrics
    ranking_confidence: float = 0.0
    signal_agreement: float = 0.0  # How well signals agree

    # Performance metrics
    reranking_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ReasoningStep:
    """Individual reasoning step in answer generation."""

    step_id: str
    step_type: str  # synthesis, inference, fact_lookup, etc.
    description: str

    # Inputs to this step
    input_sources: List[str] = field(default_factory=list)
    input_context: str = ""

    # Decision making
    reasoning: str = ""
    alternatives_considered: List[str] = field(default_factory=list)
    decision_rationale: str = ""

    # Outputs
    output: str = ""
    confidence: float = 0.0

    # Timing
    timestamp: float = field(default_factory=time.time)


@dataclass
class AnswerProvenance:
    """Provenance for answer generation stage."""

    # Generation configuration
    model_used: str
    generation_strategy: str
    temperature: float = 0.0
    max_tokens: int = 0

    # Reasoning process
    reasoning_steps: List[ReasoningStep] = field(default_factory=list)
    synthesis_approach: str = ""
    fact_checking_applied: bool = False

    # Source usage
    primary_sources: List[str] = field(default_factory=list)
    supporting_sources: List[str] = field(default_factory=list)
    contradictory_sources: List[str] = field(default_factory=list)

    # Quality assessment
    answer_confidence: float = 0.0
    completeness_score: float = 0.0
    accuracy_indicators: List[str] = field(default_factory=list)

    # Content analysis
    answer_length: int = 0
    citation_count: int = 0
    fact_density: float = 0.0

    # Performance metrics
    generation_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class QualityMetrics:
    """Overall quality metrics for the answer."""

    # Confidence scores
    overall_confidence: float = 0.0
    source_reliability: float = 0.0
    reasoning_soundness: float = 0.0
    completeness: float = 0.0

    # Trust indicators
    source_diversity: int = 0
    official_source_count: int = 0
    cross_validation_score: float = 0.0

    # Risk factors
    potential_inconsistencies: List[str] = field(default_factory=list)
    missing_information: List[str] = field(default_factory=list)
    confidence_warnings: List[str] = field(default_factory=list)

    # Metrics calculation
    calculated_at: float = field(default_factory=time.time)


@dataclass
class ProvenanceBundle:
    """Complete provenance bundle for an answer."""

    # Session identification
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Pipeline stages
    query_provenance: Optional[QueryProvenance] = None
    retrieval_provenance: Optional[RetrievalProvenance] = None
    reranking_provenance: Optional[RerankingProvenance] = None
    answer_provenance: Optional[AnswerProvenance] = None

    # Source attribution
    all_sources: List[SourceAttribution] = field(default_factory=list)
    primary_citations: List[SourceAttribution] = field(default_factory=list)

    # Quality assessment
    quality_metrics: Optional[QualityMetrics] = None

    # Timeline
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    total_time_ms: float = 0.0

    # Environment context
    environment: str = "dev"

    def mark_completed(self):
        """Mark the provenance bundle as completed."""
        self.completed_at = time.time()
        self.total_time_ms = (self.completed_at - self.started_at) * 1000

    def get_stage_status(self) -> Dict[str, bool]:
        """Get completion status of each pipeline stage."""
        return {
            "query_planning": self.query_provenance is not None,
            "retrieval": self.retrieval_provenance is not None,
            "reranking": self.reranking_provenance is not None,
            "answer_generation": self.answer_provenance is not None,
            "quality_metrics": self.quality_metrics is not None
        }

    def get_primary_sources(self) -> List[SourceAttribution]:
        """Get sources that were primarily used in the answer."""
        return [source for source in self.all_sources if source.used_in_answer]

    def get_confidence_summary(self) -> Dict[str, float]:
        """Get confidence scores summary."""
        summary = {}

        if self.query_provenance:
            summary["query_classification"] = self.query_provenance.classification_confidence

        if self.reranking_provenance:
            summary["ranking"] = self.reranking_provenance.ranking_confidence

        if self.answer_provenance:
            summary["answer_generation"] = self.answer_provenance.answer_confidence

        if self.quality_metrics:
            summary["overall"] = self.quality_metrics.overall_confidence

        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
            "stage_status": self.get_stage_status(),
            "confidence_summary": self.get_confidence_summary(),
            "primary_sources_count": len(self.get_primary_sources()),
            "total_sources_count": len(self.all_sources),
            "total_time_ms": self.total_time_ms,
            "environment": self.environment,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


@dataclass
class ProvenanceConfig:
    """Configuration for provenance tracking."""

    # Tracking settings
    enabled: bool = True
    track_query_processing: bool = True
    track_retrieval: bool = True
    track_reranking: bool = True
    track_answer_generation: bool = True

    # Detail levels
    include_reasoning_steps: bool = True
    include_signal_details: bool = True
    include_alternative_paths: bool = False
    max_source_excerpts: int = 5

    # Performance controls
    max_tracking_time_ms: int = 50
    enable_async_tracking: bool = True

    # Storage settings
    store_provenance: bool = True
    provenance_ttl_hours: int = 24
    compress_large_bundles: bool = True

    # Privacy settings
    anonymize_queries: bool = False
    redact_sensitive_content: bool = False


def create_confidence_level(score: float) -> ConfidenceLevel:
    """Convert numerical confidence score to confidence level."""
    if score >= 0.9:
        return ConfidenceLevel.VERY_HIGH
    elif score >= 0.7:
        return ConfidenceLevel.HIGH
    elif score >= 0.5:
        return ConfidenceLevel.MEDIUM
    elif score >= 0.3:
        return ConfidenceLevel.LOW
    else:
        return ConfidenceLevel.VERY_LOW


def calculate_source_diversity(sources: List[SourceAttribution]) -> float:
    """Calculate diversity score based on source types and origins."""
    if not sources:
        return 0.0

    source_types = set(source.source_type for source in sources)
    source_paths = set(source.source_path for source in sources)

    # Diversity based on variety of source types and individual sources
    type_diversity = len(source_types) / max(1, len(sources))
    path_diversity = len(source_paths) / max(1, len(sources))

    return (type_diversity + path_diversity) / 2.0


def aggregate_confidence_scores(scores: List[float]) -> float:
    """Aggregate multiple confidence scores into a single score."""
    if not scores:
        return 0.0

    # Use weighted harmonic mean to be conservative
    # Lower scores have more impact on the final result
    valid_scores = [max(0.01, score) for score in scores if score > 0]

    if not valid_scores:
        return 0.0

    harmonic_mean = len(valid_scores) / sum(1/score for score in valid_scores)
    return min(1.0, harmonic_mean)