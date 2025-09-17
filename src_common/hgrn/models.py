"""
HGRN Data Models

Defines dataclasses and types for HGRN validation reports and recommendations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class RecommendationType(Enum):
    """Types of HGRN recommendations."""
    DICTIONARY = "dictionary"
    GRAPH = "graph"
    CHUNK = "chunk"
    OCR = "ocr"


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HGRNRecommendation:
    """
    Single HGRN validation recommendation.

    Attributes:
        id: Unique recommendation identifier
        type: Type of recommendation (dictionary, graph, chunk, ocr)
        severity: Severity level of the issue
        confidence: Confidence score (0.0-1.0)
        title: Brief title of the recommendation
        description: Detailed description of the issue
        evidence: Raw evidence supporting the recommendation
        suggested_action: Recommended action to take
        page_refs: List of page references where issue was found
        chunk_ids: List of chunk IDs related to the issue
        created_at: Timestamp when recommendation was generated
        accepted: Whether recommendation has been accepted
        rejected: Whether recommendation has been rejected
        metadata: Additional metadata for the recommendation
    """
    id: str
    type: RecommendationType
    severity: ValidationSeverity
    confidence: float
    title: str
    description: str
    evidence: Dict[str, Any]
    suggested_action: str
    page_refs: List[int] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    accepted: bool = False
    rejected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate recommendation data after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

        if not self.id:
            raise ValueError("Recommendation ID cannot be empty")

        if not self.title:
            raise ValueError("Recommendation title cannot be empty")


@dataclass
class HGRNValidationStats:
    """
    Statistics from HGRN validation process.

    Attributes:
        total_chunks_analyzed: Total number of chunks processed
        dictionary_terms_validated: Number of dictionary terms checked
        graph_nodes_validated: Number of graph nodes checked
        ocr_fallback_triggered: Whether OCR fallback was used
        processing_time_seconds: Total processing time
        confidence_threshold_used: Confidence threshold applied
        package_version: HGRN package version used
    """
    total_chunks_analyzed: int
    dictionary_terms_validated: int
    graph_nodes_validated: int
    ocr_fallback_triggered: bool
    processing_time_seconds: float
    confidence_threshold_used: float
    package_version: str


@dataclass
class HGRNReport:
    """
    Complete HGRN validation report.

    Attributes:
        job_id: Ingestion job identifier
        environment: Environment where validation was run
        status: Overall validation status
        recommendations: List of validation recommendations
        stats: Validation statistics
        artifacts_analyzed: List of artifact files analyzed
        generated_at: Timestamp when report was generated
        hgrn_enabled: Whether HGRN was enabled for this job
        error_message: Error message if validation failed
    """
    job_id: str
    environment: str
    status: str  # "success", "partial", "failed"
    recommendations: List[HGRNRecommendation] = field(default_factory=list)
    stats: Optional[HGRNValidationStats] = None
    artifacts_analyzed: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    hgrn_enabled: bool = True
    error_message: Optional[str] = None

    def add_recommendation(self, recommendation: HGRNRecommendation) -> None:
        """Add a recommendation to the report."""
        self.recommendations.append(recommendation)

    def get_recommendations_by_type(self, rec_type: RecommendationType) -> List[HGRNRecommendation]:
        """Get all recommendations of a specific type."""
        return [rec for rec in self.recommendations if rec.type == rec_type]

    def get_high_priority_recommendations(self) -> List[HGRNRecommendation]:
        """Get recommendations with high or critical severity."""
        return [
            rec for rec in self.recommendations
            if rec.severity in [ValidationSeverity.HIGH, ValidationSeverity.CRITICAL]
        ]

    def get_unprocessed_recommendations(self) -> List[HGRNRecommendation]:
        """Get recommendations that haven't been accepted or rejected."""
        return [
            rec for rec in self.recommendations
            if not rec.accepted and not rec.rejected
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "job_id": self.job_id,
            "environment": self.environment,
            "status": self.status,
            "recommendations": [
                {
                    "id": rec.id,
                    "type": rec.type.value,
                    "severity": rec.severity.value,
                    "confidence": rec.confidence,
                    "title": rec.title,
                    "description": rec.description,
                    "evidence": rec.evidence,
                    "suggested_action": rec.suggested_action,
                    "page_refs": rec.page_refs,
                    "chunk_ids": rec.chunk_ids,
                    "created_at": rec.created_at.isoformat(),
                    "accepted": rec.accepted,
                    "rejected": rec.rejected,
                    "metadata": rec.metadata
                } for rec in self.recommendations
            ],
            "stats": {
                "total_chunks_analyzed": self.stats.total_chunks_analyzed,
                "dictionary_terms_validated": self.stats.dictionary_terms_validated,
                "graph_nodes_validated": self.stats.graph_nodes_validated,
                "ocr_fallback_triggered": self.stats.ocr_fallback_triggered,
                "processing_time_seconds": self.stats.processing_time_seconds,
                "confidence_threshold_used": self.stats.confidence_threshold_used,
                "package_version": self.stats.package_version
            } if self.stats else None,
            "artifacts_analyzed": self.artifacts_analyzed,
            "generated_at": self.generated_at.isoformat(),
            "hgrn_enabled": self.hgrn_enabled,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HGRNReport':
        """Create report from dictionary (JSON deserialization)."""
        recommendations = []
        for rec_data in data.get("recommendations", []):
            rec = HGRNRecommendation(
                id=rec_data["id"],
                type=RecommendationType(rec_data["type"]),
                severity=ValidationSeverity(rec_data["severity"]),
                confidence=rec_data["confidence"],
                title=rec_data["title"],
                description=rec_data["description"],
                evidence=rec_data["evidence"],
                suggested_action=rec_data["suggested_action"],
                page_refs=rec_data.get("page_refs", []),
                chunk_ids=rec_data.get("chunk_ids", []),
                created_at=datetime.fromisoformat(rec_data["created_at"]),
                accepted=rec_data.get("accepted", False),
                rejected=rec_data.get("rejected", False),
                metadata=rec_data.get("metadata", {})
            )
            recommendations.append(rec)

        stats = None
        if data.get("stats"):
            stats_data = data["stats"]
            stats = HGRNValidationStats(
                total_chunks_analyzed=stats_data["total_chunks_analyzed"],
                dictionary_terms_validated=stats_data["dictionary_terms_validated"],
                graph_nodes_validated=stats_data["graph_nodes_validated"],
                ocr_fallback_triggered=stats_data["ocr_fallback_triggered"],
                processing_time_seconds=stats_data["processing_time_seconds"],
                confidence_threshold_used=stats_data["confidence_threshold_used"],
                package_version=stats_data["package_version"]
            )

        return cls(
            job_id=data["job_id"],
            environment=data["environment"],
            status=data["status"],
            recommendations=recommendations,
            stats=stats,
            artifacts_analyzed=data.get("artifacts_analyzed", []),
            generated_at=datetime.fromisoformat(data["generated_at"]),
            hgrn_enabled=data.get("hgrn_enabled", True),
            error_message=data.get("error_message")
        )