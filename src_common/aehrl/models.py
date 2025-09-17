"""
AEHRL Data Models

Defines dataclasses and types for automated evaluation, hallucination detection,
and correction recommendations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import uuid


class HallucinationSeverity(Enum):
    """Severity levels for hallucination flags."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CorrectionType(Enum):
    """Types of corrections that can be recommended."""
    DICTIONARY_UPDATE = "dictionary_update"
    GRAPH_EDGE_FIX = "graph_edge_fix"
    GRAPH_NODE_FIX = "graph_node_fix"
    METADATA_CORRECTION = "metadata_correction"
    CHUNK_REVISION = "chunk_revision"


class SupportLevel(Enum):
    """Level of support for a claim or statement."""
    FULLY_SUPPORTED = "fully_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


@dataclass
class FactClaim:
    """
    Represents an extracted fact claim from model output.

    Attributes:
        text: The actual claim text
        confidence: Confidence in fact extraction (0.0-1.0)
        context: Surrounding context for the claim
        source_span: Character span in original text
        claim_type: Type of claim (entity, relationship, attribute, etc.)
        metadata: Additional metadata about the claim
    """
    text: str
    confidence: float
    context: str = ""
    source_span: tuple[int, int] = (0, 0)
    claim_type: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate claim data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class SupportEvidence:
    """
    Evidence supporting or contradicting a fact claim.

    Attributes:
        source: Source of the evidence (chunk_id, graph_node, dictionary_entry)
        text: Relevant text from the source
        support_level: How well this evidence supports the claim
        confidence: Confidence in this evidence (0.0-1.0)
        citation_info: Information for proper citation
        metadata: Additional evidence metadata
    """
    source: str
    text: str
    support_level: SupportLevel
    confidence: float
    citation_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate evidence data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class HallucinationFlag:
    """
    Represents a detected hallucination or unsupported claim.

    Attributes:
        id: Unique flag identifier
        claim: The fact claim being flagged
        severity: Severity level of the hallucination
        reason: Human-readable reason for flagging
        evidence: Supporting/contradicting evidence
        recommended_action: Suggested action to take
        flagged_at: Timestamp when flagged
        query_id: Associated query identifier
        user_warned: Whether user has been warned
        admin_reviewed: Whether admin has reviewed
        metadata: Additional flag metadata
    """
    id: str
    claim: FactClaim
    severity: HallucinationSeverity
    reason: str
    evidence: List[SupportEvidence] = field(default_factory=list)
    recommended_action: str = ""
    flagged_at: datetime = field(default_factory=datetime.now)
    query_id: Optional[str] = None
    user_warned: bool = False
    admin_reviewed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate ID if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "claim": {
                "text": self.claim.text,
                "confidence": self.claim.confidence,
                "context": self.claim.context,
                "source_span": self.claim.source_span,
                "claim_type": self.claim.claim_type,
                "metadata": self.claim.metadata
            },
            "severity": self.severity.value,
            "reason": self.reason,
            "evidence": [
                {
                    "source": ev.source,
                    "text": ev.text,
                    "support_level": ev.support_level.value,
                    "confidence": ev.confidence,
                    "citation_info": ev.citation_info,
                    "metadata": ev.metadata
                }
                for ev in self.evidence
            ],
            "recommended_action": self.recommended_action,
            "flagged_at": self.flagged_at.isoformat(),
            "query_id": self.query_id,
            "user_warned": self.user_warned,
            "admin_reviewed": self.admin_reviewed,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HallucinationFlag':
        """Create from dictionary."""
        claim = FactClaim(
            text=data["claim"]["text"],
            confidence=data["claim"]["confidence"],
            context=data["claim"]["context"],
            source_span=tuple(data["claim"]["source_span"]),
            claim_type=data["claim"]["claim_type"],
            metadata=data["claim"]["metadata"]
        )

        evidence = [
            SupportEvidence(
                source=ev["source"],
                text=ev["text"],
                support_level=SupportLevel(ev["support_level"]),
                confidence=ev["confidence"],
                citation_info=ev["citation_info"],
                metadata=ev["metadata"]
            )
            for ev in data["evidence"]
        ]

        return cls(
            id=data["id"],
            claim=claim,
            severity=HallucinationSeverity(data["severity"]),
            reason=data["reason"],
            evidence=evidence,
            recommended_action=data["recommended_action"],
            flagged_at=datetime.fromisoformat(data["flagged_at"]),
            query_id=data["query_id"],
            user_warned=data["user_warned"],
            admin_reviewed=data["admin_reviewed"],
            metadata=data["metadata"]
        )


@dataclass
class CorrectionRecommendation:
    """
    Represents a recommended correction for ingestion artifacts.

    Attributes:
        id: Unique recommendation identifier
        type: Type of correction recommended
        target: Target entity to be corrected (chunk_id, node_id, etc.)
        description: Human-readable description of the issue
        current_value: Current problematic value
        suggested_value: Suggested corrected value
        confidence: Confidence in the recommendation (0.0-1.0)
        impact_assessment: Assessment of correction impact
        created_at: Timestamp when recommendation was created
        job_id: Associated ingestion job ID
        environment: Environment where issue was detected
        accepted: Whether recommendation has been accepted
        rejected: Whether recommendation has been rejected
        applied_at: Timestamp when correction was applied
        metadata: Additional recommendation metadata
    """
    id: str
    type: CorrectionType
    target: str
    description: str
    current_value: Any
    suggested_value: Any
    confidence: float
    impact_assessment: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    job_id: Optional[str] = None
    environment: str = "dev"
    accepted: bool = False
    rejected: bool = False
    applied_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and generate ID if needed."""
        if not self.id:
            self.id = str(uuid.uuid4())

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "target": self.target,
            "description": self.description,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "confidence": self.confidence,
            "impact_assessment": self.impact_assessment,
            "created_at": self.created_at.isoformat(),
            "job_id": self.job_id,
            "environment": self.environment,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CorrectionRecommendation':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=CorrectionType(data["type"]),
            target=data["target"],
            description=data["description"],
            current_value=data["current_value"],
            suggested_value=data["suggested_value"],
            confidence=data["confidence"],
            impact_assessment=data["impact_assessment"],
            created_at=datetime.fromisoformat(data["created_at"]),
            job_id=data["job_id"],
            environment=data["environment"],
            accepted=data["accepted"],
            rejected=data["rejected"],
            applied_at=datetime.fromisoformat(data["applied_at"]) if data["applied_at"] else None,
            metadata=data["metadata"]
        )


@dataclass
class AEHRLMetrics:
    """
    Metrics for AEHRL evaluation performance.

    Attributes:
        query_id: Associated query identifier
        support_rate: Percentage of claims with supporting evidence
        hallucination_rate: Percentage of unsupported/contradicted claims
        citation_accuracy: Accuracy of citation information
        total_claims: Total number of fact claims extracted
        flagged_claims: Number of claims flagged as potentially hallucinated
        processing_time_ms: Time taken for evaluation in milliseconds
        confidence_threshold: Confidence threshold used for flagging
        timestamp: When metrics were recorded
        metadata: Additional metrics metadata
    """
    query_id: str
    support_rate: float
    hallucination_rate: float
    citation_accuracy: float
    total_claims: int
    flagged_claims: int
    processing_time_ms: float
    confidence_threshold: float = 0.7
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate metrics data."""
        for rate in [self.support_rate, self.hallucination_rate, self.citation_accuracy]:
            if not 0.0 <= rate <= 1.0:
                raise ValueError(f"Rate values must be between 0.0 and 1.0, got {rate}")


@dataclass
class AEHRLReport:
    """
    Complete AEHRL evaluation report.

    Attributes:
        query_id: Associated query identifier
        job_id: Associated ingestion job ID (for ingestion-time evaluation)
        environment: Environment where evaluation was performed
        evaluation_type: Type of evaluation (query_time, ingestion_time)
        status: Overall evaluation status
        hallucination_flags: List of detected hallucination flags
        correction_recommendations: List of correction recommendations
        metrics: Evaluation metrics
        processing_time_ms: Total processing time in milliseconds
        created_at: Timestamp when report was created
        error_message: Error message if evaluation failed
        metadata: Additional report metadata
    """
    query_id: Optional[str] = None
    job_id: Optional[str] = None
    environment: str = "dev"
    evaluation_type: str = "query_time"
    status: str = "completed"
    hallucination_flags: List[HallucinationFlag] = field(default_factory=list)
    correction_recommendations: List[CorrectionRecommendation] = field(default_factory=list)
    metrics: Optional[AEHRLMetrics] = None
    processing_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_high_priority_flags(self) -> List[HallucinationFlag]:
        """Get hallucination flags with high or critical severity."""
        return [
            flag for flag in self.hallucination_flags
            if flag.severity in [HallucinationSeverity.HIGH, HallucinationSeverity.CRITICAL]
        ]

    def get_pending_corrections(self) -> List[CorrectionRecommendation]:
        """Get correction recommendations that haven't been accepted or rejected."""
        return [
            rec for rec in self.correction_recommendations
            if not rec.accepted and not rec.rejected
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query_id": self.query_id,
            "job_id": self.job_id,
            "environment": self.environment,
            "evaluation_type": self.evaluation_type,
            "status": self.status,
            "hallucination_flags": [flag.to_dict() for flag in self.hallucination_flags],
            "correction_recommendations": [rec.to_dict() for rec in self.correction_recommendations],
            "metrics": {
                "query_id": self.metrics.query_id,
                "support_rate": self.metrics.support_rate,
                "hallucination_rate": self.metrics.hallucination_rate,
                "citation_accuracy": self.metrics.citation_accuracy,
                "total_claims": self.metrics.total_claims,
                "flagged_claims": self.metrics.flagged_claims,
                "processing_time_ms": self.metrics.processing_time_ms,
                "confidence_threshold": self.metrics.confidence_threshold,
                "timestamp": self.metrics.timestamp.isoformat(),
                "metadata": self.metrics.metadata
            } if self.metrics else None,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat(),
            "error_message": self.error_message,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AEHRLReport':
        """Create from dictionary."""
        flags = [HallucinationFlag.from_dict(flag) for flag in data["hallucination_flags"]]
        corrections = [CorrectionRecommendation.from_dict(rec) for rec in data["correction_recommendations"]]

        metrics = None
        if data["metrics"]:
            metrics_data = data["metrics"]
            metrics = AEHRLMetrics(
                query_id=metrics_data["query_id"],
                support_rate=metrics_data["support_rate"],
                hallucination_rate=metrics_data["hallucination_rate"],
                citation_accuracy=metrics_data["citation_accuracy"],
                total_claims=metrics_data["total_claims"],
                flagged_claims=metrics_data["flagged_claims"],
                processing_time_ms=metrics_data["processing_time_ms"],
                confidence_threshold=metrics_data["confidence_threshold"],
                timestamp=datetime.fromisoformat(metrics_data["timestamp"]),
                metadata=metrics_data["metadata"]
            )

        return cls(
            query_id=data["query_id"],
            job_id=data["job_id"],
            environment=data["environment"],
            evaluation_type=data["evaluation_type"],
            status=data["status"],
            hallucination_flags=flags,
            correction_recommendations=corrections,
            metrics=metrics,
            processing_time_ms=data["processing_time_ms"],
            created_at=datetime.fromisoformat(data["created_at"]),
            error_message=data["error_message"],
            metadata=data["metadata"]
        )