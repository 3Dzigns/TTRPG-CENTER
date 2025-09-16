# src_common/models/unified_dictionary.py
"""
Unified Dictionary Data Models - FR-015

Provides unified data models that can bridge AdminDictionaryService and MongoDictionaryService,
enabling seamless transition between file-based and MongoDB storage while maintaining
backward compatibility and performance requirements.
"""

import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union
from enum import Enum

# Import existing models for conversion
from ..admin.dictionary_models import DictionaryTerm, DictionaryStats
from ..mongo_dictionary_service import DictEntry


class SourceType(Enum):
    """Source type enumeration for dictionary entries"""
    MANUAL = "manual"
    IMPORTED = "imported"
    EXTRACTED = "extracted"
    VALIDATED = "validated"


class ConfidenceLevel(Enum):
    """Confidence level enumeration for source reliability"""
    LOW = 0.3
    MEDIUM = 0.6
    HIGH = 0.8
    VERIFIED = 1.0


@dataclass
class UnifiedSource:
    """Unified source information structure"""
    system: str  # Source system name (e.g., "Player Handbook", "Monster Manual")
    page_reference: Optional[str] = None  # Page reference (e.g., "p.241")
    confidence: float = 0.8  # Confidence level (0.0-1.0)
    extraction_method: str = "manual"  # How the data was obtained
    source_type: SourceType = SourceType.MANUAL  # Type of source
    verified: bool = False  # Whether the source has been verified
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        # Clamp confidence to valid range
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class UnifiedDictionaryTerm:
    """
    Unified dictionary term that can bridge AdminDictionaryService and MongoDictionaryService

    This model provides:
    - Bidirectional conversion between DictionaryTerm and DictEntry
    - Enhanced source tracking with confidence and verification
    - Performance optimization metadata
    - Backward compatibility with existing APIs
    """

    # Core fields (common to both systems)
    term: str
    definition: str
    category: str
    environment: str

    # Enhanced source information
    sources: List[UnifiedSource]

    # Metadata and tracking
    created_at: float
    updated_at: float
    version: int = 1
    tags: List[str] = None

    # Performance and caching hints
    search_priority: float = 1.0  # Search ranking hint (0.0-1.0)
    cache_ttl: Optional[int] = None  # Custom cache TTL in seconds

    # Legacy compatibility
    source: Optional[str] = None  # Primary source (backward compatibility)
    page_reference: Optional[str] = None  # Primary page ref (backward compatibility)

    def __post_init__(self):
        # Initialize defaults
        if self.tags is None:
            self.tags = []
        if not self.sources:
            # Create default source from legacy fields
            if self.source:
                default_source = UnifiedSource(
                    system=self.source,
                    page_reference=self.page_reference,
                    confidence=0.8,
                    extraction_method="legacy_import"
                )
                self.sources = [default_source]
            else:
                self.sources = []

        # Ensure legacy compatibility fields are set
        if self.sources and not self.source:
            primary_source = self.get_primary_source()
            self.source = primary_source.system
            self.page_reference = primary_source.page_reference

    def get_primary_source(self) -> Optional[UnifiedSource]:
        """Get the primary (highest confidence) source"""
        if not self.sources:
            return None
        return max(self.sources, key=lambda s: s.confidence)

    def get_confidence_score(self) -> float:
        """Calculate overall confidence score for this term"""
        if not self.sources:
            return 0.5  # Default medium confidence

        # Weighted average based on confidence and verification
        total_weight = 0.0
        weighted_confidence = 0.0

        for source in self.sources:
            weight = 1.0
            if source.verified:
                weight *= 1.5  # Boost verified sources
            if source.source_type == SourceType.VERIFIED:
                weight *= 1.3  # Boost verified source types

            total_weight += weight
            weighted_confidence += source.confidence * weight

        return min(1.0, weighted_confidence / total_weight) if total_weight > 0 else 0.5

    def update_timestamp(self):
        """Update the modification timestamp"""
        self.updated_at = time.time()
        self.version += 1

    def add_source(self, source: UnifiedSource):
        """Add a new source to this term"""
        self.sources.append(source)
        self.update_timestamp()

        # Update legacy compatibility fields if this is now the primary source
        primary = self.get_primary_source()
        if primary and primary == source:
            self.source = source.system
            self.page_reference = source.page_reference

    def to_dictionary_term(self) -> DictionaryTerm:
        """Convert to AdminDictionaryService DictionaryTerm format"""
        return DictionaryTerm(
            term=self.term,
            definition=self.definition,
            category=self.category,
            environment=self.environment,
            source=self.source or (self.get_primary_source().system if self.sources else "unknown"),
            page_reference=self.page_reference or (self.get_primary_source().page_reference if self.sources else None),
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
            tags=self.tags.copy() if self.tags else []
        )

    def to_dict_entry(self) -> DictEntry:
        """Convert to MongoDictionaryService DictEntry format"""
        # Convert UnifiedSource to dict format expected by DictEntry
        sources_dict = []
        for source in self.sources:
            source_dict = {
                "system": source.system,
                "page_reference": source.page_reference,
                "confidence": source.confidence,
                "extraction_method": source.extraction_method,
                "source_type": source.source_type.value,
                "verified": source.verified
            }
            if source.metadata:
                source_dict.update(source.metadata)
            sources_dict.append(source_dict)

        return DictEntry(
            term=self.term,
            definition=self.definition,
            category=self.category,
            sources=sources_dict
        )

    def to_mongo_doc(self) -> Dict[str, Any]:
        """Convert to MongoDB document format with enhanced metadata"""
        doc = {
            "_id": self.term.lower(),
            "term": self.term,
            "term_normalized": self.term.lower(),
            "definition": self.definition,
            "category": self.category,
            "environment": self.environment,
            "sources": [asdict(source) for source in self.sources],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "tags": self.tags,
            "search_priority": self.search_priority,
            "confidence_score": self.get_confidence_score(),
            "cache_ttl": self.cache_ttl
        }

        # Add legacy compatibility fields
        if self.source:
            doc["legacy_source"] = self.source
        if self.page_reference:
            doc["legacy_page_reference"] = self.page_reference

        return doc

    @classmethod
    def from_dictionary_term(cls, term: DictionaryTerm) -> 'UnifiedDictionaryTerm':
        """Create UnifiedDictionaryTerm from AdminDictionaryService DictionaryTerm"""
        # Create UnifiedSource from legacy source info
        sources = []
        if term.source:
            source = UnifiedSource(
                system=term.source,
                page_reference=term.page_reference,
                confidence=0.8,  # Default confidence for imported data
                extraction_method="admin_import",
                source_type=SourceType.IMPORTED
            )
            sources.append(source)

        return cls(
            term=term.term,
            definition=term.definition,
            category=term.category,
            environment=term.environment,
            sources=sources,
            created_at=term.created_at or time.time(),
            updated_at=term.updated_at or time.time(),
            version=term.version or 1,
            tags=term.tags.copy() if term.tags else [],
            source=term.source,
            page_reference=term.page_reference
        )

    @classmethod
    def from_dict_entry(cls, entry: DictEntry, environment: str) -> 'UnifiedDictionaryTerm':
        """Create UnifiedDictionaryTerm from MongoDictionaryService DictEntry"""
        # Convert source dicts to UnifiedSource objects
        sources = []
        for source_dict in entry.sources:
            try:
                source = UnifiedSource(
                    system=source_dict.get("system", "unknown"),
                    page_reference=source_dict.get("page_reference"),
                    confidence=source_dict.get("confidence", 0.8),
                    extraction_method=source_dict.get("extraction_method", "unknown"),
                    source_type=SourceType(source_dict.get("source_type", "manual")),
                    verified=source_dict.get("verified", False),
                    metadata={k: v for k, v in source_dict.items()
                             if k not in ["system", "page_reference", "confidence",
                                         "extraction_method", "source_type", "verified"]}
                )
                sources.append(source)
            except (ValueError, KeyError) as e:
                # Handle malformed source data gracefully
                fallback_source = UnifiedSource(
                    system=source_dict.get("system", "unknown"),
                    confidence=0.5,
                    extraction_method="recovered_data"
                )
                sources.append(fallback_source)

        return cls(
            term=entry.term,
            definition=entry.definition,
            category=entry.category,
            environment=environment,
            sources=sources,
            created_at=time.time(),  # DictEntry doesn't track creation time
            updated_at=time.time(),  # DictEntry doesn't track update time
            version=1,  # DictEntry doesn't have versioning
            tags=[]  # DictEntry doesn't have tags
        )

    @classmethod
    def from_mongo_doc(cls, doc: Dict[str, Any]) -> 'UnifiedDictionaryTerm':
        """Create UnifiedDictionaryTerm from MongoDB document"""
        # Handle both new unified format and legacy format
        sources = []

        if "sources" in doc and isinstance(doc["sources"], list):
            for source_data in doc["sources"]:
                if isinstance(source_data, dict):
                    try:
                        source = UnifiedSource(**source_data)
                        sources.append(source)
                    except TypeError:
                        # Handle legacy format or malformed data
                        source = UnifiedSource(
                            system=source_data.get("system", "unknown"),
                            page_reference=source_data.get("page_reference"),
                            confidence=source_data.get("confidence", 0.8),
                            extraction_method=source_data.get("extraction_method", "unknown")
                        )
                        sources.append(source)

        return cls(
            term=doc.get("term", ""),
            definition=doc.get("definition", ""),
            category=doc.get("category", ""),
            environment=doc.get("environment", "dev"),
            sources=sources,
            created_at=doc.get("created_at", time.time()),
            updated_at=doc.get("updated_at", time.time()),
            version=doc.get("version", 1),
            tags=doc.get("tags", []),
            search_priority=doc.get("search_priority", 1.0),
            cache_ttl=doc.get("cache_ttl"),
            source=doc.get("legacy_source"),
            page_reference=doc.get("legacy_page_reference")
        )


@dataclass
class UnifiedDictionaryStats:
    """
    Unified dictionary statistics that can aggregate data from multiple backends
    """
    total_terms: int
    categories: Dict[str, int]
    sources: Dict[str, int]
    recent_updates: int
    environment: str

    # Enhanced metrics
    confidence_distribution: Dict[str, int] = None  # Distribution by confidence level
    source_types: Dict[str, int] = None  # Distribution by source type
    verified_count: int = 0  # Number of verified entries
    avg_confidence: float = 0.0  # Average confidence score
    last_updated: float = None  # Timestamp of last update

    # Backend information
    backend_type: str = "unified"  # "file", "mongodb", or "unified"
    backend_health: str = "unknown"  # Backend health status

    def __post_init__(self):
        if self.confidence_distribution is None:
            self.confidence_distribution = {}
        if self.source_types is None:
            self.source_types = {}
        if self.last_updated is None:
            self.last_updated = time.time()

    def to_dictionary_stats(self) -> DictionaryStats:
        """Convert to AdminDictionaryService DictionaryStats format"""
        return DictionaryStats(
            total_terms=self.total_terms,
            categories=self.categories.copy(),
            sources=self.sources.copy(),
            recent_updates=self.recent_updates,
            environment=self.environment
        )

    def add_backend_stats(self, backend_stats: Union[DictionaryStats, Dict[str, Any]], backend_type: str):
        """Merge statistics from a backend into unified stats"""
        if isinstance(backend_stats, DictionaryStats):
            # Merge AdminDictionaryService stats
            self.total_terms += backend_stats.total_terms
            self.recent_updates += backend_stats.recent_updates

            # Merge categories and sources
            for cat, count in backend_stats.categories.items():
                self.categories[cat] = self.categories.get(cat, 0) + count
            for source, count in backend_stats.sources.items():
                self.sources[source] = self.sources.get(source, 0) + count

        elif isinstance(backend_stats, dict):
            # Merge MongoDB stats
            self.total_terms += backend_stats.get("total_entries", 0)

            # Merge category distribution
            for cat, count in backend_stats.get("category_distribution", {}).items():
                self.categories[cat] = self.categories.get(cat, 0) + count

        self.backend_type = f"{self.backend_type}+{backend_type}"
        self.last_updated = time.time()

    def calculate_health_score(self) -> float:
        """Calculate overall health score based on statistics"""
        score = 0.0

        # Data availability (40% of score)
        if self.total_terms > 0:
            score += 0.4

        # Data quality (30% of score)
        if self.avg_confidence > 0.7:
            score += 0.3
        elif self.avg_confidence > 0.5:
            score += 0.15

        # Data freshness (20% of score)
        if self.recent_updates > 0:
            score += 0.2

        # Verification coverage (10% of score)
        if self.total_terms > 0:
            verification_ratio = self.verified_count / self.total_terms
            score += 0.1 * verification_ratio

        return min(1.0, score)