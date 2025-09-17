"""
Data models for persona testing framework.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


class PersonaType(Enum):
    """Core persona types for TTRPG users."""
    # Experience-based personas
    NEW_USER = "new_user"
    INTERMEDIATE_USER = "intermediate_user"
    EXPERT_USER = "expert_user"
    RETURNING_USER = "returning_user"

    # Role-based personas
    DUNGEON_MASTER = "dungeon_master"
    PLAYER = "player"
    WORLD_BUILDER = "world_builder"
    RULES_LAWYER = "rules_lawyer"
    CASUAL_PLAYER = "casual_player"

    # Context-based personas
    MOBILE_USER = "mobile_user"
    DESKTOP_USER = "desktop_user"
    STREAMING_HOST = "streaming_host"
    LIVE_SESSION = "live_session"
    PREPARATION_MODE = "preparation_mode"

    # Language-based personas (aligned with existing Personas/ directory)
    ENGLISH_NATIVE = "english_native"
    MULTILINGUAL = "multilingual"
    ESL_USER = "esl_user"


class ExperienceLevel(Enum):
    """User experience levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class UserRole(Enum):
    """User roles in TTRPG context."""
    GAME_MASTER = "game_master"
    PLAYER = "player"
    BOTH = "both"
    OBSERVER = "observer"
    CONTENT_CREATOR = "content_creator"


class SessionContext(Enum):
    """Context of the user session."""
    PREPARATION = "preparation"
    ACTIVE_GAME = "active_game"
    RESEARCH = "research"
    LEARNING = "learning"
    CASUAL_BROWSING = "casual_browsing"


@dataclass
class PersonaProfile:
    """Complete persona profile for testing."""

    id: str
    name: str
    persona_type: PersonaType
    experience_level: ExperienceLevel
    user_role: UserRole

    # Demographics and preferences
    languages: List[str] = field(default_factory=lambda: ["English"])
    preferred_systems: List[str] = field(default_factory=list)
    technical_comfort: int = 5  # 1-10 scale

    # Response expectations
    preferred_detail_level: str = "moderate"  # brief, moderate, detailed, comprehensive
    expects_examples: bool = True
    expects_citations: bool = True
    expects_visual_aids: bool = False

    # Context preferences
    time_pressure: bool = False
    mobile_context: bool = False
    accessibility_needs: List[str] = field(default_factory=list)

    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "persona_type": self.persona_type.value,
            "experience_level": self.experience_level.value,
            "user_role": self.user_role.value,
            "languages": self.languages,
            "preferred_systems": self.preferred_systems,
            "technical_comfort": self.technical_comfort,
            "preferred_detail_level": self.preferred_detail_level,
            "expects_examples": self.expects_examples,
            "expects_citations": self.expects_citations,
            "expects_visual_aids": self.expects_visual_aids,
            "time_pressure": self.time_pressure,
            "mobile_context": self.mobile_context,
            "accessibility_needs": self.accessibility_needs,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PersonaProfile:
        """Create from dictionary."""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])

        return cls(
            id=data["id"],
            name=data["name"],
            persona_type=PersonaType(data["persona_type"]),
            experience_level=ExperienceLevel(data["experience_level"]),
            user_role=UserRole(data["user_role"]),
            languages=data.get("languages", ["English"]),
            preferred_systems=data.get("preferred_systems", []),
            technical_comfort=data.get("technical_comfort", 5),
            preferred_detail_level=data.get("preferred_detail_level", "moderate"),
            expects_examples=data.get("expects_examples", True),
            expects_citations=data.get("expects_citations", True),
            expects_visual_aids=data.get("expects_visual_aids", False),
            time_pressure=data.get("time_pressure", False),
            mobile_context=data.get("mobile_context", False),
            accessibility_needs=data.get("accessibility_needs", []),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            created_at=created_at
        )


@dataclass
class PersonaContext:
    """Runtime context for persona-aware processing."""

    persona_profile: PersonaProfile
    session_context: SessionContext

    # Query context
    query_complexity: float = 0.5  # 0-1 scale
    time_constraint: Optional[int] = None  # seconds
    device_type: str = "desktop"  # desktop, mobile, tablet

    # Session state
    previous_queries: List[str] = field(default_factory=list)
    session_duration: Optional[int] = None  # seconds
    error_count: int = 0

    # User behavior indicators
    scrolled_to_bottom: bool = False
    clicked_citations: bool = False
    requested_more_detail: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "persona_profile": self.persona_profile.to_dict(),
            "session_context": self.session_context.value,
            "query_complexity": self.query_complexity,
            "time_constraint": self.time_constraint,
            "device_type": self.device_type,
            "previous_queries": self.previous_queries,
            "session_duration": self.session_duration,
            "error_count": self.error_count,
            "scrolled_to_bottom": self.scrolled_to_bottom,
            "clicked_citations": self.clicked_citations,
            "requested_more_detail": self.requested_more_detail
        }


@dataclass
class PersonaMetrics:
    """Metrics for persona-specific performance tracking."""

    persona_id: str
    query_id: str

    # Response quality metrics
    appropriateness_score: float  # 0-1 scale
    detail_level_match: float  # 0-1 scale
    language_appropriateness: float  # 0-1 scale
    citation_quality: float  # 0-1 scale

    # Response characteristics
    response_length: int
    citation_count: int
    example_count: int
    technical_terms_count: int

    # User experience metrics
    response_time_ms: int
    complexity_match: float  # 0-1 scale
    user_satisfaction_predicted: float  # 0-1 scale

    # Validation flags
    has_hallucinations: bool = False
    has_inappropriate_content: bool = False
    has_accessibility_issues: bool = False

    # Metadata
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "persona_id": self.persona_id,
            "query_id": self.query_id,
            "appropriateness_score": self.appropriateness_score,
            "detail_level_match": self.detail_level_match,
            "language_appropriateness": self.language_appropriateness,
            "citation_quality": self.citation_quality,
            "response_length": self.response_length,
            "citation_count": self.citation_count,
            "example_count": self.example_count,
            "technical_terms_count": self.technical_terms_count,
            "response_time_ms": self.response_time_ms,
            "complexity_match": self.complexity_match,
            "user_satisfaction_predicted": self.user_satisfaction_predicted,
            "has_hallucinations": self.has_hallucinations,
            "has_inappropriate_content": self.has_inappropriate_content,
            "has_accessibility_issues": self.has_accessibility_issues,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class PersonaTestScenario:
    """Test scenario for persona validation."""

    id: str
    name: str
    persona_profile: PersonaProfile
    session_context: SessionContext

    # Test query and expected response characteristics
    query: str
    expected_appropriateness_score: float
    expected_detail_level: str
    expected_response_traits: List[str]  # e.g., ["has_examples", "cites_sources", "brief"]

    # Negative test cases
    inappropriate_responses: List[str] = field(default_factory=list)

    # Test metadata
    tags: List[str] = field(default_factory=list)
    priority: int = 1  # 1-5 scale
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "persona_profile": self.persona_profile.to_dict(),
            "session_context": self.session_context.value,
            "query": self.query,
            "expected_appropriateness_score": self.expected_appropriateness_score,
            "expected_detail_level": self.expected_detail_level,
            "expected_response_traits": self.expected_response_traits,
            "inappropriate_responses": self.inappropriate_responses,
            "tags": self.tags,
            "priority": self.priority,
            "description": self.description
        }