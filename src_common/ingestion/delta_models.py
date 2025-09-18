"""
Delta Refresh Models for FR-029 Incremental Processing

Defines data structures for content change detection, delta metadata,
and incremental processing state management.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime


class ChangeType(Enum):
    """Types of content changes detected."""
    ADDED = "added"           # New content/sections
    MODIFIED = "modified"     # Changed existing content
    DELETED = "deleted"       # Removed content/sections
    MOVED = "moved"          # Content relocated within document
    RENAMED = "renamed"       # Section/heading renamed


class DeltaStatus(Enum):
    """Status of delta refresh operations."""
    PENDING = "pending"       # Queued for processing
    PROCESSING = "processing" # Currently being processed
    COMPLETED = "completed"   # Successfully processed
    FAILED = "failed"         # Processing failed
    ROLLED_BACK = "rolled_back"  # Changes rolled back


class ProcessingMode(Enum):
    """Delta processing modes."""
    INCREMENTAL = "incremental"  # Process only changes
    FULL = "full"               # Full reprocessing
    VALIDATION = "validation"    # Validate against full processing


@dataclass
class ContentFingerprint:
    """SHA-256 based content fingerprint for change detection."""

    content_hash: str           # SHA-256 hash of content
    metadata_hash: str          # SHA-256 hash of metadata
    page_number: Optional[int] = None
    section_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    # Content characteristics
    content_length: int = 0
    word_count: int = 0
    line_count: int = 0

    # Structural information
    heading_level: Optional[int] = None
    parent_section: Optional[str] = None
    child_sections: List[str] = field(default_factory=list)

    @classmethod
    def from_content(
        cls,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        page_number: Optional[int] = None,
        section_id: Optional[str] = None
    ) -> ContentFingerprint:
        """Create fingerprint from content and metadata."""
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        metadata_str = ""
        if metadata:
            # Sort keys for consistent hashing
            metadata_str = str(sorted(metadata.items()))
        metadata_hash = hashlib.sha256(metadata_str.encode('utf-8')).hexdigest()

        return cls(
            content_hash=content_hash,
            metadata_hash=metadata_hash,
            page_number=page_number,
            section_id=section_id,
            content_length=len(content),
            word_count=len(content.split()),
            line_count=len(content.splitlines())
        )

    def matches(self, other: ContentFingerprint) -> bool:
        """Check if fingerprints match (content and metadata)."""
        return (
            self.content_hash == other.content_hash and
            self.metadata_hash == other.metadata_hash
        )

    def content_matches(self, other: ContentFingerprint) -> bool:
        """Check if only content matches (ignoring metadata)."""
        return self.content_hash == other.content_hash


@dataclass
class ContentChange:
    """Represents a detected change in document content."""

    change_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    change_type: ChangeType = ChangeType.MODIFIED

    # Location information
    document_path: str = ""
    page_number: Optional[int] = None
    section_id: Optional[str] = None

    # Change details
    old_fingerprint: Optional[ContentFingerprint] = None
    new_fingerprint: Optional[ContentFingerprint] = None

    # Content snippets for debugging
    old_content_preview: str = ""
    new_content_preview: str = ""

    # Change metrics
    similarity_score: float = 0.0    # Content similarity (0-1)
    change_magnitude: float = 0.0    # Magnitude of change (0-1)

    # Processing information
    detected_at: float = field(default_factory=time.time)
    affects_chunks: List[str] = field(default_factory=list)
    affects_vectors: List[str] = field(default_factory=list)
    affects_graph_nodes: List[str] = field(default_factory=list)

    # Dependencies
    dependent_changes: List[str] = field(default_factory=list)
    blocking_changes: List[str] = field(default_factory=list)

    def get_change_summary(self) -> Dict[str, Any]:
        """Get summary of change for logging/debugging."""
        return {
            'change_id': self.change_id,
            'type': self.change_type.value,
            'location': f"{self.document_path}:{self.page_number}:{self.section_id}",
            'magnitude': self.change_magnitude,
            'similarity': self.similarity_score,
            'affects': {
                'chunks': len(self.affects_chunks),
                'vectors': len(self.affects_vectors),
                'graph_nodes': len(self.affects_graph_nodes)
            }
        }


@dataclass
class DeltaSession:
    """Represents a delta refresh processing session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_path: str = ""
    processing_mode: ProcessingMode = ProcessingMode.INCREMENTAL

    # Session metadata
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: DeltaStatus = DeltaStatus.PENDING

    # Change information
    total_changes: int = 0
    processed_changes: int = 0
    failed_changes: int = 0

    # Processing metrics
    processing_time_ms: float = 0.0
    time_saved_ms: float = 0.0      # vs full processing
    efficiency_ratio: float = 0.0    # time_saved / original_time

    # Change tracking
    detected_changes: List[ContentChange] = field(default_factory=list)
    processing_log: List[Dict[str, Any]] = field(default_factory=list)
    error_log: List[Dict[str, Any]] = field(default_factory=list)

    # Rollback information
    rollback_data: Optional[Dict[str, Any]] = None
    can_rollback: bool = True

    def add_change(self, change: ContentChange):
        """Add a detected change to the session."""
        self.detected_changes.append(change)
        self.total_changes = len(self.detected_changes)

    def log_processing_step(self, step: str, details: Dict[str, Any]):
        """Log a processing step with timestamp."""
        self.processing_log.append({
            'timestamp': time.time(),
            'step': step,
            'details': details
        })

    def log_error(self, error: str, details: Optional[Dict[str, Any]] = None):
        """Log an error with timestamp."""
        self.error_log.append({
            'timestamp': time.time(),
            'error': error,
            'details': details or {}
        })

    def mark_completed(self, success: bool = True):
        """Mark session as completed."""
        self.completed_at = time.time()
        self.processing_time_ms = (self.completed_at - self.started_at) * 1000
        self.status = DeltaStatus.COMPLETED if success else DeltaStatus.FAILED

    def calculate_efficiency(self, baseline_time_ms: float):
        """Calculate efficiency compared to full processing."""
        if baseline_time_ms > 0:
            self.time_saved_ms = baseline_time_ms - self.processing_time_ms
            self.efficiency_ratio = self.time_saved_ms / baseline_time_ms

    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary for reporting."""
        return {
            'session_id': self.session_id,
            'document': self.document_path,
            'status': self.status.value,
            'mode': self.processing_mode.value,
            'changes': {
                'total': self.total_changes,
                'processed': self.processed_changes,
                'failed': self.failed_changes
            },
            'performance': {
                'processing_time_ms': self.processing_time_ms,
                'time_saved_ms': self.time_saved_ms,
                'efficiency_ratio': self.efficiency_ratio
            },
            'timestamps': {
                'started_at': self.started_at,
                'completed_at': self.completed_at
            }
        }


@dataclass
class DocumentState:
    """Represents the current state of a document for delta tracking."""

    document_path: str
    last_modified: float
    file_size: int
    document_hash: str          # Hash of entire document

    # Page-level fingerprints
    page_fingerprints: Dict[int, ContentFingerprint] = field(default_factory=dict)

    # Section-level fingerprints
    section_fingerprints: Dict[str, ContentFingerprint] = field(default_factory=dict)

    # Processing state
    last_processed: float = 0.0
    processing_version: str = "1.0"

    # Chunk mapping
    chunk_mappings: Dict[str, List[str]] = field(default_factory=dict)  # page/section -> chunk_ids
    vector_mappings: Dict[str, List[str]] = field(default_factory=dict)  # page/section -> vector_ids
    graph_mappings: Dict[str, List[str]] = field(default_factory=dict)   # page/section -> node_ids

    # Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> DocumentState:
        """Create document state from file."""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        stat = path.stat()

        # Calculate file hash
        with open(path, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        return cls(
            document_path=str(path),
            last_modified=stat.st_mtime,
            file_size=stat.st_size,
            document_hash=file_hash
        )

    def add_page_fingerprint(self, page_num: int, fingerprint: ContentFingerprint):
        """Add fingerprint for a page."""
        self.page_fingerprints[page_num] = fingerprint
        self.updated_at = time.time()

    def add_section_fingerprint(self, section_id: str, fingerprint: ContentFingerprint):
        """Add fingerprint for a section."""
        self.section_fingerprints[section_id] = fingerprint
        self.updated_at = time.time()

    def get_changed_pages(self, other: DocumentState) -> List[int]:
        """Get list of pages that have changed."""
        changed_pages = []

        # Check for added/modified pages
        for page_num, fingerprint in self.page_fingerprints.items():
            if page_num not in other.page_fingerprints:
                changed_pages.append(page_num)
            elif not fingerprint.matches(other.page_fingerprints[page_num]):
                changed_pages.append(page_num)

        # Check for deleted pages
        for page_num in other.page_fingerprints:
            if page_num not in self.page_fingerprints:
                changed_pages.append(page_num)

        return sorted(set(changed_pages))

    def get_changed_sections(self, other: DocumentState) -> List[str]:
        """Get list of sections that have changed."""
        changed_sections = []

        # Check for added/modified sections
        for section_id, fingerprint in self.section_fingerprints.items():
            if section_id not in other.section_fingerprints:
                changed_sections.append(section_id)
            elif not fingerprint.matches(other.section_fingerprints[section_id]):
                changed_sections.append(section_id)

        # Check for deleted sections
        for section_id in other.section_fingerprints:
            if section_id not in self.section_fingerprints:
                changed_sections.append(section_id)

        return changed_sections

    def has_changes(self, other: DocumentState) -> bool:
        """Check if document has any changes."""
        return (
            self.document_hash != other.document_hash or
            self.last_modified != other.last_modified or
            len(self.get_changed_pages(other)) > 0 or
            len(self.get_changed_sections(other)) > 0
        )


@dataclass
class DeltaConfig:
    """Configuration for delta refresh operations."""

    # Detection settings
    enable_page_level_detection: bool = True
    enable_section_level_detection: bool = True
    enable_content_similarity_analysis: bool = True

    # Similarity thresholds
    min_similarity_for_update: float = 0.1   # Below this, treat as new content
    max_similarity_for_skip: float = 0.95    # Above this, skip processing

    # Performance settings
    max_parallel_changes: int = 5
    change_batch_size: int = 10
    processing_timeout_ms: float = 300000    # 5 minutes

    # Safety settings
    enable_rollback: bool = True
    backup_before_processing: bool = True
    validate_consistency: bool = True

    # Fallback behavior
    fallback_to_full_processing: bool = True
    max_change_percentage: float = 0.5       # Above this, use full processing

    # Optimization settings
    enable_caching: bool = True
    cache_fingerprints: bool = True
    cache_ttl_seconds: int = 3600

    # Integration settings
    preserve_vector_relationships: bool = True
    update_graph_incrementally: bool = True
    maintain_cross_references: bool = True

    def should_use_full_processing(self, change_ratio: float) -> bool:
        """Determine if full processing should be used instead of delta."""
        return (
            not self.fallback_to_full_processing or
            change_ratio > self.max_change_percentage
        )

    def get_processing_batch_size(self, total_changes: int) -> int:
        """Get appropriate batch size for processing."""
        if total_changes <= self.change_batch_size:
            return total_changes
        return min(self.change_batch_size, max(1, total_changes // self.max_parallel_changes))


def calculate_content_similarity(content1: str, content2: str) -> float:
    """Calculate similarity between two content strings."""
    if not content1 and not content2:
        return 1.0

    if not content1 or not content2:
        return 0.0

    # Simple token-based similarity
    tokens1 = set(content1.lower().split())
    tokens2 = set(content2.lower().split())

    if not tokens1 and not tokens2:
        return 1.0

    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def estimate_change_magnitude(old_content: str, new_content: str) -> float:
    """Estimate the magnitude of change between content versions."""
    if not old_content and not new_content:
        return 0.0

    if not old_content:
        return 1.0  # Complete addition

    if not new_content:
        return 1.0  # Complete deletion

    # Calculate various change metrics
    length_ratio = abs(len(new_content) - len(old_content)) / max(len(old_content), len(new_content))
    word_count_ratio = abs(len(new_content.split()) - len(old_content.split())) / max(len(old_content.split()), len(new_content.split()))
    similarity = calculate_content_similarity(old_content, new_content)

    # Combine metrics for overall magnitude
    change_magnitude = (length_ratio + word_count_ratio + (1.0 - similarity)) / 3.0

    return min(1.0, max(0.0, change_magnitude))


def create_section_id(page_num: int, heading: str, level: int = 1) -> str:
    """Create a consistent section ID from page number, heading, and level."""
    # Clean heading for use as ID
    clean_heading = "".join(c.lower() if c.isalnum() else "_" for c in heading)
    clean_heading = "_".join(part for part in clean_heading.split("_") if part)

    return f"page_{page_num}_h{level}_{clean_heading}"


def generate_change_id(document_path: str, page_num: Optional[int], section_id: Optional[str]) -> str:
    """Generate a unique change ID for tracking."""
    components = [document_path]

    if page_num is not None:
        components.append(f"page_{page_num}")

    if section_id:
        components.append(section_id)

    # Add timestamp for uniqueness
    components.append(str(int(time.time() * 1000)))

    change_string = "|".join(components)
    return hashlib.sha256(change_string.encode('utf-8')).hexdigest()[:16]