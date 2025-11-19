#!/usr/bin/env python3
"""
pass_a_toc_multipage_extractor.py - Multi-Page TOC Extraction (Fix for Issue #1)
==================================================================================

Extracts Table of Contents across multiple pages instead of assuming single page.
Fixes the root cause where TOC extraction only searches page 4, missing entries on pages 2-8.

This module addresses the issue identified in Pass F validation:
- 27 TOC entries not found on page 4
- Root cause: TOC spans multiple pages (typically pages 2-8)
- Current code only searches page 4

Fixes implemented:
1. Search TOC across page range (default: pages 2-8)
2. Configurable page range for different document layouts
3. Multi-page text aggregation before extraction
4. Improved entry location tracking across pages

Usage:
  Integrated into pass_a_metadata.py automatically

Version: 1.0.0
Author: n8n TTRPG Center
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class TOCMultiPageExtractor:
    """
    Extracts Table of Contents across multiple pages.
    """

    def __init__(
        self,
        toc_page_range: Tuple[int, int] = (2, 8),
        enable_logging: bool = True
    ):
        """
        Initialize multi-page TOC extractor.

        Args:
            toc_page_range: Tuple of (start_page, end_page) for TOC search (default: (2, 8))
            enable_logging: Enable detailed logging (default: True)
        """
        self.toc_page_range = toc_page_range
        self.enable_logging = enable_logging

        self.stats = {
            'pages_searched': 0,
            'entries_found': 0,
            'entries_with_page_numbers': 0,
            'entries_without_page_numbers': 0,
        }

    def extract_toc_from_multiple_pages(
        self,
        page_texts: Dict[int, str]
    ) -> List[Dict[str, any]]:
        """
        Extract TOC entries from multiple pages.

        Implements Fix #1: Multi-page TOC extraction

        Args:
            page_texts: Dictionary mapping page_number -> page_text

        Returns:
            List of TOC entries: [{"title": str, "page": Optional[int], "level": int}, ...]
        """
        # Aggregate text from TOC page range
        aggregated_text = ""
        pages_searched = []

        for page_num in range(self.toc_page_range[0], self.toc_page_range[1] + 1):
            if page_num in page_texts:
                page_text = page_texts[page_num]
                aggregated_text += f"\n--- PAGE {page_num} ---\n{page_text}"
                pages_searched.append(page_num)
                self.stats['pages_searched'] += 1

        if not aggregated_text.strip():
            logger.warning("No text found in TOC page range")
            return []

        if self.enable_logging:
            logger.info(f"Searching for TOC across pages: {pages_searched}")

        # Extract TOC entries from aggregated text
        toc_entries = self._parse_toc_entries(aggregated_text)

        # Update statistics
        self.stats['entries_found'] = len(toc_entries)
        self.stats['entries_with_page_numbers'] = sum(
            1 for entry in toc_entries if entry.get('page') is not None
        )
        self.stats['entries_without_page_numbers'] = (
            self.stats['entries_found'] - self.stats['entries_with_page_numbers']
        )

        if self.enable_logging:
            logger.info(f"  Found {len(toc_entries)} TOC entries across {len(pages_searched)} pages")

        return toc_entries

    def _parse_toc_entries(self, text: str) -> List[Dict[str, any]]:
        """
        Parse TOC entries from aggregated text.

        Recognizes common TOC patterns:
        - "Chapter 1: Introduction .......... 5"
        - "Introduction .......... 5"
        - "1. Introduction .......... 5"
        - "Introduction ...... 5"
        - "Chapter 1: Introduction 5"

        Args:
            text: Aggregated TOC text from multiple pages

        Returns:
            List of TOC entries
        """
        entries = []

        # Common TOC patterns (ordered by specificity)
        patterns = [
            # Pattern 1: "Chapter X: Title ...... Page"
            r'(?P<chapter>Chapter\s+\d+):\s*(?P<title>[^.]+?)\s*\.{2,}\s*(?P<page>\d+)',

            # Pattern 2: "Title ...... Page"
            r'(?P<title>[A-Z][^.]{2,}?)\s*\.{2,}\s*(?P<page>\d+)',

            # Pattern 3: "Number. Title ...... Page"
            r'(?P<number>\d+)\.\s*(?P<title>[^.]+?)\s*\.{2,}\s*(?P<page>\d+)',

            # Pattern 4: "Title Page" (no dots)
            r'(?P<title>[A-Z][A-Za-z\s&\-]{3,})\s+(?P<page>\d+)$',
        ]

        lines = text.split('\n')
        for line in lines:
            line = line.strip()

            if not line or line.startswith('---'):
                continue

            # Try each pattern
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    groups = match.groupdict()

                    # Extract title
                    title = groups.get('title', '').strip()
                    if groups.get('chapter'):
                        title = f"{groups['chapter']}: {title}"
                    elif groups.get('number'):
                        title = f"{groups['number']}. {title}"

                    # Extract page number
                    page_str = groups.get('page', '')
                    page = int(page_str) if page_str.isdigit() else None

                    # Determine indentation level (rough heuristic)
                    level = self._estimate_entry_level(line)

                    entries.append({
                        'title': title,
                        'page': page,
                        'level': level,
                        'raw_line': line
                    })

                    break  # Stop after first matching pattern

        return entries

    def _estimate_entry_level(self, line: str) -> int:
        """
        Estimate TOC entry level based on indentation/formatting.

        Args:
            line: TOC entry line

        Returns:
            Level (0 = top level, 1 = subsection, 2 = sub-subsection, etc.)
        """
        # Count leading spaces as indentation indicator
        leading_spaces = len(line) - len(line.lstrip(' '))

        if leading_spaces >= 8:
            return 2  # Sub-subsection
        elif leading_spaces >= 4:
            return 1  # Subsection
        else:
            return 0  # Top level

        # Alternative: Check for chapter vs section markers
        if line.startswith('Chapter'):
            return 0
        elif re.match(r'^\d+\.', line):  # Numbered section
            return 1
        else:
            return 1  # Default to subsection

    def validate_toc_entries(
        self,
        entries: List[Dict[str, any]],
        max_page: int
    ) -> List[Dict[str, any]]:
        """
        Validate TOC entries for consistency.

        Args:
            entries: List of TOC entries
            max_page: Maximum page number in document

        Returns:
            Validated entries (entries with invalid pages are flagged)
        """
        validated = []

        for entry in entries:
            page = entry.get('page')

            # Validate page number
            if page is not None:
                if page < 1 or page > max_page:
                    logger.warning(
                        f"  ⚠️  Invalid page number for TOC entry '{entry['title']}': "
                        f"{page} (max: {max_page})"
                    )
                    entry['page_valid'] = False
                else:
                    entry['page_valid'] = True
            else:
                entry['page_valid'] = False

            validated.append(entry)

        return validated

    def get_statistics(self) -> dict:
        """Get extraction statistics."""
        return dict(self.stats)

    def log_final_statistics(self):
        """Log final extraction statistics."""
        stats = self.get_statistics()

        logger.info("\n" + "="*60)
        logger.info("TOC MULTI-PAGE EXTRACTION STATISTICS")
        logger.info("="*60)
        logger.info(f"Pages Searched:           {stats['pages_searched']}")
        logger.info(f"TOC Entries Found:        {stats['entries_found']}")
        logger.info(f"  With Page Numbers:      {stats['entries_with_page_numbers']}")
        logger.info(f"  Without Page Numbers:   {stats['entries_without_page_numbers']}")
        logger.info("="*60 + "\n")


# Example usage for integration into pass_a_metadata.py:
"""
# In pass_a_metadata.py, replace single-page TOC extraction:

from pass_a_toc_multipage_extractor import TOCMultiPageExtractor

# Create extractor
toc_extractor = TOCMultiPageExtractor(
    toc_page_range=(2, 8),  # Search pages 2-8
    enable_logging=True
)

# Extract page texts (from pass_a_unstructured output)
page_texts = {}
for page_num in range(1, 11):  # First 10 pages
    page_text = extract_page_text(page_num)  # Your existing function
    if page_text:
        page_texts[page_num] = page_text

# Extract TOC entries across multiple pages
toc_entries = toc_extractor.extract_toc_from_multiple_pages(page_texts)

# Validate entries
validated_entries = toc_extractor.validate_toc_entries(toc_entries, max_page=578)

# Use validated entries
for entry in validated_entries:
    if entry.get('page_valid', False):
        insert_toc_entry_to_mongodb(entry)  # Your existing insertion

# Log statistics
toc_extractor.log_final_statistics()
"""


if __name__ == "__main__":
    # Example standalone usage
    import sys

    logging.basicConfig(level=logging.INFO)

    # Create extractor
    toc_extractor = TOCMultiPageExtractor(
        toc_page_range=(2, 8),
        enable_logging=True
    )

    # Mock page texts (simulating extracted TOC pages)
    mock_page_texts = {
        2: """
        Table of Contents
        Using This Book .......... 4
        Common Terms .......... 4
        """,
        3: """
        Chapter 1: Races .......... 10
        Chapter 2: Classes .......... 30
        """,
        4: """
        Chapter 3: Skills .......... 85
        Chapter 4: Feats .......... 112
        """,
        5: """
        Chapter 5: Equipment .......... 140
        Chapter 6: Magic .......... 208
        """,
    }

    print("\nTesting Multi-Page TOC Extraction\n" + "="*60)

    # Extract TOC
    toc_entries = toc_extractor.extract_toc_from_multiple_pages(mock_page_texts)

    # Validate entries
    validated = toc_extractor.validate_toc_entries(toc_entries, max_page=578)

    print(f"\nExtracted TOC Entries ({len(validated)}):")
    for entry in validated:
        status = "✅" if entry.get('page_valid') else "⚠️"
        print(f"  {status} '{entry['title']}' → Page {entry.get('page', 'N/A')}")

    # Log statistics
    toc_extractor.log_final_statistics()
