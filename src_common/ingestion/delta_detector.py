"""
Delta Detection Engine for FR-029 Incremental Processing

Provides SHA-based content change detection with granular tracking
for efficient incremental document processing.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

from ..ttrpg_logging import get_logger
from .delta_models import (
    ContentFingerprint,
    ContentChange,
    DocumentState,
    DeltaConfig,
    ChangeType,
    calculate_content_similarity,
    estimate_change_magnitude,
    create_section_id,
    generate_change_id
)

logger = get_logger(__name__)


class DeltaDetector:
    """
    Engine for detecting content changes using SHA-based fingerprinting.

    Provides granular change detection at page and section levels with
    intelligent similarity analysis and change classification.
    """

    def __init__(self, config: Optional[DeltaConfig] = None):
        """Initialize delta detector with configuration."""
        self.config = config or DeltaConfig()
        self.fingerprint_cache: Dict[str, ContentFingerprint] = {}

        logger.info("DeltaDetector initialized")

    def detect_document_changes(
        self,
        current_state: DocumentState,
        previous_state: DocumentState
    ) -> List[ContentChange]:
        """
        Detect all changes between document states.

        Args:
            current_state: Current document state
            previous_state: Previous document state

        Returns:
            List of detected content changes
        """
        start_time = time.perf_counter()
        changes = []

        try:
            # Quick check: if document hashes match, no changes
            if current_state.document_hash == previous_state.document_hash:
                logger.debug(f"No changes detected: document hashes match")
                return []

            # Detect page-level changes
            if self.config.enable_page_level_detection:
                page_changes = self._detect_page_changes(current_state, previous_state)
                changes.extend(page_changes)

            # Detect section-level changes
            if self.config.enable_section_level_detection:
                section_changes = self._detect_section_changes(current_state, previous_state)
                changes.extend(section_changes)

            # Enhance changes with similarity analysis
            if self.config.enable_content_similarity_analysis:
                changes = self._enhance_changes_with_similarity(changes)

            # Filter changes based on thresholds
            changes = self._filter_changes_by_thresholds(changes)

            detection_time = (time.perf_counter() - start_time) * 1000
            logger.info(f"Detected {len(changes)} changes in {detection_time:.2f}ms")

            return changes

        except Exception as e:
            logger.error(f"Error detecting document changes: {e}")
            return []

    def detect_file_changes(
        self,
        file_path: Union[str, Path],
        previous_state: Optional[DocumentState] = None
    ) -> Tuple[DocumentState, List[ContentChange]]:
        """
        Detect changes in a file compared to previous state.

        Args:
            file_path: Path to the document file
            previous_state: Previous document state for comparison

        Returns:
            Tuple of (current_state, detected_changes)
        """
        try:
            # Create current document state
            current_state = self._create_document_state(file_path)

            if previous_state is None:
                # No previous state - treat everything as new
                return current_state, []

            # Detect changes
            changes = self.detect_document_changes(current_state, previous_state)

            return current_state, changes

        except Exception as e:
            logger.error(f"Error detecting file changes for {file_path}: {e}")
            # Return empty state and no changes on error
            return DocumentState(document_path=str(file_path), last_modified=0, file_size=0, document_hash=""), []

    def _detect_page_changes(
        self,
        current_state: DocumentState,
        previous_state: DocumentState
    ) -> List[ContentChange]:
        """Detect changes at the page level."""
        changes = []

        # Get changed pages
        changed_pages = current_state.get_changed_pages(previous_state)

        for page_num in changed_pages:
            change_type = self._determine_page_change_type(
                page_num, current_state, previous_state
            )

            change = ContentChange(
                change_id=generate_change_id(current_state.document_path, page_num, None),
                change_type=change_type,
                document_path=current_state.document_path,
                page_number=page_num,
                old_fingerprint=previous_state.page_fingerprints.get(page_num),
                new_fingerprint=current_state.page_fingerprints.get(page_num)
            )

            changes.append(change)

        return changes

    def _detect_section_changes(
        self,
        current_state: DocumentState,
        previous_state: DocumentState
    ) -> List[ContentChange]:
        """Detect changes at the section level."""
        changes = []

        # Get changed sections
        changed_sections = current_state.get_changed_sections(previous_state)

        for section_id in changed_sections:
            change_type = self._determine_section_change_type(
                section_id, current_state, previous_state
            )

            # Extract page number from section ID if possible
            page_num = self._extract_page_from_section_id(section_id)

            change = ContentChange(
                change_id=generate_change_id(current_state.document_path, page_num, section_id),
                change_type=change_type,
                document_path=current_state.document_path,
                page_number=page_num,
                section_id=section_id,
                old_fingerprint=previous_state.section_fingerprints.get(section_id),
                new_fingerprint=current_state.section_fingerprints.get(section_id)
            )

            changes.append(change)

        return changes

    def _determine_page_change_type(
        self,
        page_num: int,
        current_state: DocumentState,
        previous_state: DocumentState
    ) -> ChangeType:
        """Determine the type of change for a page."""
        current_fingerprint = current_state.page_fingerprints.get(page_num)
        previous_fingerprint = previous_state.page_fingerprints.get(page_num)

        if previous_fingerprint is None:
            return ChangeType.ADDED
        elif current_fingerprint is None:
            return ChangeType.DELETED
        else:
            return ChangeType.MODIFIED

    def _determine_section_change_type(
        self,
        section_id: str,
        current_state: DocumentState,
        previous_state: DocumentState
    ) -> ChangeType:
        """Determine the type of change for a section."""
        current_fingerprint = current_state.section_fingerprints.get(section_id)
        previous_fingerprint = previous_state.section_fingerprints.get(section_id)

        if previous_fingerprint is None:
            return ChangeType.ADDED
        elif current_fingerprint is None:
            return ChangeType.DELETED
        else:
            return ChangeType.MODIFIED

    def _enhance_changes_with_similarity(self, changes: List[ContentChange]) -> List[ContentChange]:
        """Enhance changes with content similarity analysis."""
        enhanced_changes = []

        for change in changes:
            if change.old_fingerprint and change.new_fingerprint:
                # For this implementation, we'll use a simplified similarity calculation
                # In a full implementation, you'd extract actual content for comparison

                # Estimate similarity based on content characteristics
                old_fp = change.old_fingerprint
                new_fp = change.new_fingerprint

                # Basic similarity heuristics
                length_similarity = 1.0 - abs(old_fp.content_length - new_fp.content_length) / max(old_fp.content_length, new_fp.content_length, 1)
                word_similarity = 1.0 - abs(old_fp.word_count - new_fp.word_count) / max(old_fp.word_count, new_fp.word_count, 1)

                change.similarity_score = (length_similarity + word_similarity) / 2.0
                change.change_magnitude = 1.0 - change.similarity_score

                # Add content previews for debugging
                change.old_content_preview = f"Length: {old_fp.content_length}, Words: {old_fp.word_count}"
                change.new_content_preview = f"Length: {new_fp.content_length}, Words: {new_fp.word_count}"

            elif change.old_fingerprint and not change.new_fingerprint:
                # Deletion
                change.similarity_score = 0.0
                change.change_magnitude = 1.0
                change.old_content_preview = f"Length: {change.old_fingerprint.content_length}"
                change.new_content_preview = "DELETED"

            elif not change.old_fingerprint and change.new_fingerprint:
                # Addition
                change.similarity_score = 0.0
                change.change_magnitude = 1.0
                change.old_content_preview = "NEW"
                change.new_content_preview = f"Length: {change.new_fingerprint.content_length}"

            enhanced_changes.append(change)

        return enhanced_changes

    def _filter_changes_by_thresholds(self, changes: List[ContentChange]) -> List[ContentChange]:
        """Filter changes based on similarity thresholds."""
        filtered_changes = []

        for change in changes:
            # Skip changes that are too similar (likely minor formatting changes)
            if change.similarity_score > self.config.max_similarity_for_skip:
                logger.debug(f"Skipping change {change.change_id}: similarity too high ({change.similarity_score:.3f})")
                continue

            # Include changes that meet minimum similarity threshold
            if change.similarity_score >= self.config.min_similarity_for_update:
                filtered_changes.append(change)
            else:
                logger.debug(f"Including significant change {change.change_id}: similarity ({change.similarity_score:.3f})")
                filtered_changes.append(change)

        return filtered_changes

    def _create_document_state(self, file_path: Union[str, Path]) -> DocumentState:
        """Create document state from file."""
        try:
            # Create basic document state
            doc_state = DocumentState.from_file(file_path)

            # For this implementation, we'll create simplified fingerprints
            # In a full implementation, you'd parse the document and create
            # detailed page and section fingerprints

            # Create a single fingerprint for the entire document as a page
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Create page fingerprint for page 1 (simplified)
            page_fingerprint = ContentFingerprint.from_content(
                content=content,
                metadata={'file_size': doc_state.file_size},
                page_number=1
            )

            doc_state.add_page_fingerprint(1, page_fingerprint)

            # Create section fingerprints based on simple heuristics
            sections = self._extract_simple_sections(content)
            for section_id, section_content in sections.items():
                section_fingerprint = ContentFingerprint.from_content(
                    content=section_content,
                    metadata={'section_type': 'auto_detected'},
                    section_id=section_id
                )
                doc_state.add_section_fingerprint(section_id, section_fingerprint)

            return doc_state

        except Exception as e:
            logger.error(f"Error creating document state for {file_path}: {e}")
            # Return minimal state on error
            return DocumentState(
                document_path=str(file_path),
                last_modified=0,
                file_size=0,
                document_hash=""
            )

    def _extract_simple_sections(self, content: str) -> Dict[str, str]:
        """Extract simple sections from content based on headings."""
        sections = {}

        # Split content by lines
        lines = content.split('\n')
        current_section = "intro"
        current_content = []

        for line in lines:
            stripped_line = line.strip()

            # Simple heading detection (lines that are short and contain certain keywords)
            if len(stripped_line) > 0 and len(stripped_line) < 100:
                # Check for heading-like patterns
                if any(keyword in stripped_line.lower() for keyword in ['chapter', 'section', 'overview', 'introduction']):
                    # Save previous section
                    if current_content:
                        sections[current_section] = '\n'.join(current_content)

                    # Start new section
                    current_section = create_section_id(1, stripped_line, 1)
                    current_content = []
                    continue

            current_content.append(line)

        # Save final section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def _extract_page_from_section_id(self, section_id: str) -> Optional[int]:
        """Extract page number from section ID."""
        try:
            if section_id.startswith('page_'):
                parts = section_id.split('_')
                if len(parts) >= 2:
                    return int(parts[1])
        except (ValueError, IndexError):
            pass
        return None

    def calculate_change_dependencies(self, changes: List[ContentChange]) -> List[ContentChange]:
        """Calculate dependencies between changes."""
        # Simple dependency calculation based on page/section proximity
        for i, change in enumerate(changes):
            for j, other_change in enumerate(changes):
                if i != j and self._are_changes_related(change, other_change):
                    change.dependent_changes.append(other_change.change_id)

        return changes

    def _are_changes_related(self, change1: ContentChange, change2: ContentChange) -> bool:
        """Determine if two changes are related."""
        # Same page changes are related
        if change1.page_number == change2.page_number:
            return True

        # Adjacent pages might be related
        if (change1.page_number and change2.page_number and
            abs(change1.page_number - change2.page_number) == 1):
            return True

        # Section hierarchy relationships
        if change1.section_id and change2.section_id:
            # Check if one section is a parent/child of another
            if (change1.section_id in change2.section_id or
                change2.section_id in change1.section_id):
                return True

        return False

    def get_cache_key(self, document_path: str, content_hash: str) -> str:
        """Generate cache key for fingerprint caching."""
        return hashlib.sha256(f"{document_path}|{content_hash}".encode()).hexdigest()

    def cache_fingerprint(self, cache_key: str, fingerprint: ContentFingerprint):
        """Cache a content fingerprint."""
        if self.config.enable_caching and self.config.cache_fingerprints:
            self.fingerprint_cache[cache_key] = fingerprint

    def get_cached_fingerprint(self, cache_key: str) -> Optional[ContentFingerprint]:
        """Get cached fingerprint if available."""
        if self.config.enable_caching and self.config.cache_fingerprints:
            return self.fingerprint_cache.get(cache_key)
        return None

    def clear_cache(self):
        """Clear fingerprint cache."""
        self.fingerprint_cache.clear()
        logger.debug("Fingerprint cache cleared")

    def get_detection_summary(self, changes: List[ContentChange]) -> Dict[str, Any]:
        """Get summary of detection results."""
        change_types = {}
        total_magnitude = 0.0

        for change in changes:
            change_type = change.change_type.value
            change_types[change_type] = change_types.get(change_type, 0) + 1
            total_magnitude += change.change_magnitude

        avg_magnitude = total_magnitude / len(changes) if changes else 0.0

        return {
            'total_changes': len(changes),
            'change_types': change_types,
            'average_magnitude': avg_magnitude,
            'significant_changes': len([c for c in changes if c.change_magnitude > 0.5]),
            'minor_changes': len([c for c in changes if c.change_magnitude <= 0.5])
        }