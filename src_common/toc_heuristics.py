"""
TOC-Specific Heuristics Parser

Per AI Prompt Spec (Pass A):
- Pattern matching: "title … page_number"
- Hierarchical structure detection (indentation, numbering: 1, 1.1, I, A, etc.)
- Section ID generation: sha1(title+start_page)
- End page inference (next section's start_page - 1)
"""

import hashlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .logging import get_logger
from .pass_a_toc_extraction import TocSection

logger = get_logger(__name__)


@dataclass
class TocLine:
    """Raw TOC line with extracted components."""
    raw_text: str
    title: str
    page_number: int
    numbering: Optional[str] = None  # e.g., "1.2.3", "I", "A"
    indentation_level: int = 0


class TocHeuristicParser:
    """Parse TOC using heuristics and pattern matching."""

    # Numbering patterns
    DECIMAL_PATTERN = re.compile(r'^(\d+(?:\.\d+)*)\.?\s+(.+?)[\s\.]*(\d+)\s*$')  # "1.2.3 Title ... 45" or "1. Title ... 45"
    ROMAN_PATTERN = re.compile(r'^([IVXivx]+)\.\s+(.+?)[\s\.]*(\d+)\s*$')  # "I. Title ... 45"
    ALPHA_PATTERN = re.compile(r'^([A-Z])\.\s+(.+?)[\s\.]*(\d+)\s*$')  # "A. Title ... 45"
    SIMPLE_PATTERN = re.compile(r'^(.+?)[\s\.]{2,}(\d+)\s*$')  # "Title .... 45"

    def __init__(self):
        self.sections: List[TocSection] = []

    def normalize_title(self, title: str) -> str:
        """
        Normalize TOC title by removing OCR artifacts and noise.

        Handles:
        - Excessive dot leaders (". . . . . ." → "")
        - Spaced-out text ("S o l o" → "Solo")
        - Trailing page numbers ("Title...1" → "Title")
        - Extra whitespace

        Args:
            title: Raw TOC title from OCR

        Returns:
            Normalized title string
        """
        if not title:
            return title

        # 1. Remove dot leaders (2+ consecutive dots, possibly with spaces)
        title = re.sub(r'[\s\.]{2,}', ' ', title)

        # 2. Collapse spaced-out characters (preserve intentional spacing)
        # Pattern: Single characters with spaces between them (S o l o → Solo)
        # Only collapse sequences of 3+ spaced single characters (likely OCR artifacts)

        # First, identify if we have spaced-out OCR text (3+ single-letter-space sequences)
        spaced_count = len(re.findall(r'\b[A-Za-z]\s+(?=[A-Za-z](\s|$))', title))

        if spaced_count >= 3:
            # This looks like OCR-spaced text - remove ALL single-letter spaces
            # Strategy: repeatedly remove spaces after single letters until none remain
            max_iterations = 20  # Safety limit
            iteration = 0
            prev_title = None

            while prev_title != title and iteration < max_iterations:
                prev_title = title
                # Remove space after any single letter followed by another letter
                title = re.sub(r'\b([A-Za-z])\s+(?=[A-Za-z])', r'\1', title)
                iteration += 1

        # 3. Remove trailing isolated numbers ONLY if preceded by dots/spaces (page numbers)
        # Don't remove numbers that are part of the title (e.g., "Chapter 2")
        title = re.sub(r'[\s\.]+\d+\s*$', '', title)

        # 4. Normalize whitespace
        title = re.sub(r'\s+', ' ', title).strip()

        return title

    def parse_toc_lines(self, text_lines: List[str]) -> List[TocSection]:
        """
        Parse TOC text lines into structured sections.

        Args:
            text_lines: List of text lines from TOC pages

        Returns:
            List of TocSection objects with hierarchy
        """
        # Step 1: Extract TOC lines with components
        toc_lines = []
        for line in text_lines:
            toc_line = self._parse_line(line)
            if toc_line:
                toc_lines.append(toc_line)

        logger.info(f"Parsed {len(toc_lines)} TOC lines from {len(text_lines)} input lines")

        # Step 2: Determine hierarchy levels
        toc_lines = self._determine_hierarchy(toc_lines)

        # Step 3: Infer end pages
        toc_lines = self._infer_end_pages(toc_lines)

        # Step 4: Generate stable section IDs and create TocSection objects
        sections = self._create_sections(toc_lines)

        # Step 5: Establish parent-child relationships
        sections = self._establish_hierarchy(sections)

        logger.info(f"Created {len(sections)} structured TOC sections")

        return sections

    def _parse_line(self, line: str) -> Optional[TocLine]:
        """
        Parse a single TOC line to extract components.

        Patterns (in order of priority):
        1. Decimal numbering: "1.2.3 Title ... 45"
        2. Roman numerals: "I. Title ... 45"
        3. Alphabetic: "A. Title ... 45"
        4. Simple: "Title .... 45"
        """
        line = line.strip()

        if not line or len(line) < 3:
            return None

        # Try decimal numbering pattern
        match = self.DECIMAL_PATTERN.match(line)
        if match:
            numbering, title, page = match.groups()
            title = self.normalize_title(title.strip('. '))
            return TocLine(
                raw_text=line,
                title=title,
                page_number=int(page),
                numbering=numbering
            )

        # Try Roman numeral pattern
        match = self.ROMAN_PATTERN.match(line)
        if match:
            numbering, title, page = match.groups()
            title = self.normalize_title(title.strip('. '))
            return TocLine(
                raw_text=line,
                title=title,
                page_number=int(page),
                numbering=numbering
            )

        # Try alphabetic pattern
        match = self.ALPHA_PATTERN.match(line)
        if match:
            numbering, title, page = match.groups()
            title = self.normalize_title(title.strip('. '))
            return TocLine(
                raw_text=line,
                title=title,
                page_number=int(page),
                numbering=numbering
            )

        # Try simple pattern (title with dot leaders and page)
        match = self.SIMPLE_PATTERN.match(line)
        if match:
            title, page = match.groups()
            # Clean up title (remove excessive dots, spaces)
            title = re.sub(r'\.{2,}', '', title).strip()
            title = self.normalize_title(title)

            if title and len(title) >= 3:
                return TocLine(
                    raw_text=line,
                    title=title,
                    page_number=int(page),
                    numbering=None
                )

        return None

    def _determine_hierarchy(self, toc_lines: List[TocLine]) -> List[TocLine]:
        """
        Determine hierarchy levels based on numbering and patterns.

        Level determination:
        - "1" → level 1
        - "1.1" → level 2
        - "1.1.1" → level 3
        - "I" → level 1
        - "A" → level 1 (or 2 if after numbered sections)
        - No numbering → infer from context
        """
        for i, toc_line in enumerate(toc_lines):
            if toc_line.numbering:
                # Decimal numbering: count dots to determine level
                if '.' in toc_line.numbering:
                    toc_line.indentation_level = toc_line.numbering.count('.') + 1
                # Roman numerals and letters at top level
                elif re.match(r'^[IVXivx]+$', toc_line.numbering):
                    toc_line.indentation_level = 1
                elif re.match(r'^[A-Z]$', toc_line.numbering):
                    # Check if we're in a numbered context
                    if i > 0 and toc_lines[i-1].numbering and '.' in toc_lines[i-1].numbering:
                        toc_line.indentation_level = 2
                    else:
                        toc_line.indentation_level = 1
                else:
                    toc_line.indentation_level = 1
            else:
                # No explicit numbering - infer from context
                # Default to level 1, unless previous line suggests otherwise
                if i > 0:
                    prev_level = toc_lines[i-1].indentation_level
                    # If title is significantly shorter, might be higher level
                    if len(toc_line.title) < len(toc_lines[i-1].title) * 0.7:
                        toc_line.indentation_level = max(1, prev_level - 1)
                    else:
                        toc_line.indentation_level = prev_level
                else:
                    toc_line.indentation_level = 1

        return toc_lines

    def _infer_end_pages(self, toc_lines: List[TocLine]) -> List[TocLine]:
        """
        Infer end pages for each section.

        Logic: end_page = next_section_start_page - 1
        Last section: end_page = start_page (will be updated later with actual page count)
        """
        for i, toc_line in enumerate(toc_lines):
            if i < len(toc_lines) - 1:
                # End page is one before the next section starts
                next_start = toc_lines[i + 1].page_number
                toc_line.end_page = next_start - 1
            else:
                # Last section - set to same as start for now
                toc_line.end_page = toc_line.page_number

        return toc_lines

    def _create_sections(self, toc_lines: List[TocLine]) -> List[TocSection]:
        """
        Create TocSection objects with stable IDs.

        Section ID: sha1(title + start_page)[:12]
        """
        sections = []

        for toc_line in toc_lines:
            # Generate stable section ID
            id_input = f"{toc_line.title}{toc_line.page_number}"
            section_id = hashlib.sha1(id_input.encode()).hexdigest()[:12]

            section = TocSection(
                section_id=section_id,
                title=toc_line.title,
                start_page=toc_line.page_number,
                end_page=getattr(toc_line, 'end_page', toc_line.page_number),
                level=toc_line.indentation_level,
                parent_id=None  # Will be set in next step
            )

            sections.append(section)

        return sections

    def _establish_hierarchy(self, sections: List[TocSection]) -> List[TocSection]:
        """
        Establish parent-child relationships based on levels.

        Logic:
        - A section's parent is the nearest preceding section with lower level
        - Level 1 sections have no parent
        """
        for i, section in enumerate(sections):
            if section.level == 1:
                # Top-level section, no parent
                continue

            # Find parent: nearest preceding section with lower level
            for j in range(i - 1, -1, -1):
                if sections[j].level < section.level:
                    section.parent_id = sections[j].section_id
                    break

        return sections


def parse_toc_with_heuristics(text_lines: List[str]) -> List[TocSection]:
    """
    Convenience function to parse TOC lines with heuristics.

    Args:
        text_lines: List of text lines from TOC pages

    Returns:
        List of TocSection objects with hierarchy
    """
    parser = TocHeuristicParser()
    return parser.parse_toc_lines(text_lines)
