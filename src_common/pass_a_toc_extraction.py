"""
Pass A TOC-Only Extraction using Unstructured.io

Per AI Prompt Spec:
- Extract ONLY TOC pages (as identified by Pass 0)
- Use Unstructured.io partition_pdf() with page range
- Parse TOC-specific patterns and structure
- Generate passA.toc.json with section hierarchy
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from .logging import get_logger

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
    UNSTRUCTURED_IMPORT_ERROR = None
except Exception as e:
    partition_pdf = None
    UNSTRUCTURED_AVAILABLE = False
    UNSTRUCTURED_IMPORT_ERROR = str(e)

logger = get_logger(__name__)


@dataclass
class TocSection:
    """Represents a TOC section with hierarchical information."""
    section_id: str
    title: str
    start_page: int
    end_page: int
    level: int
    parent_id: Optional[str] = None


@dataclass
class TocExtractionResult:
    """Result of TOC extraction."""
    doc_id: str
    sections: List[TocSection]
    toc_pages_used: Tuple[int, int]
    extraction_method: str  # "unstructured" or "fallback"
    success: bool
    error_message: Optional[str] = None


class TocExtractor:
    """Extract TOC using Unstructured.io from specified pages only."""

    def __init__(self, job_id: str, log_file_path: Optional[Path] = None):
        self.job_id = job_id
        self.log_file_path = log_file_path

    def extract_toc(self, pdf_path: Path, toc_pages: Tuple[int, int]) -> TocExtractionResult:
        """
        Extract TOC from specified page range using Unstructured.io.

        Args:
            pdf_path: Path to PDF file
            toc_pages: Tuple of (start_page, end_page) 1-indexed

        Returns:
            TocExtractionResult with extracted sections
        """
        start_page, end_page = toc_pages

        # Validate TOC pages
        if start_page == 0 or end_page == 0:
            logger.warning(f"No TOC pages detected, cannot extract TOC")
            return TocExtractionResult(
                doc_id=self.job_id,
                sections=[],
                toc_pages_used=(0, 0),
                extraction_method="none",
                success=False,
                error_message="No TOC pages detected"
            )

        logger.info(f"Pass A: Extracting TOC from pages {start_page}-{end_page} using Unstructured.io")

        # Check if Unstructured.io is available
        if not UNSTRUCTURED_AVAILABLE:
            logger.error(f"Unstructured.io not available: {UNSTRUCTURED_IMPORT_ERROR}")
            return TocExtractionResult(
                doc_id=self.job_id,
                sections=[],
                toc_pages_used=toc_pages,
                extraction_method="failed",
                success=False,
                error_message=f"Unstructured.io not available: {UNSTRUCTURED_IMPORT_ERROR}"
            )

        try:
            # Extract TOC pages using Unstructured.io
            # Note: Unstructured.io uses 1-indexed page numbers
            elements = partition_pdf(
                filename=str(pdf_path),
                strategy="fast",  # Use fast strategy for TOC extraction
                languages=["eng"],
                include_page_breaks=True,
                starting_page_number=start_page,
                # Note: Unstructured doesn't have ending_page_number, we'll filter after
            )

            logger.info(f"Pass A: Extracted {len(elements)} elements from Unstructured.io")

            # Filter to only TOC pages
            toc_elements = []
            for elem in elements:
                # Check if element has page_number metadata
                if hasattr(elem, 'metadata') and hasattr(elem.metadata, 'page_number'):
                    page_num = elem.metadata.page_number
                    if start_page <= page_num <= end_page:
                        toc_elements.append(elem)

            logger.info(f"Pass A: Filtered to {len(toc_elements)} elements from TOC pages {start_page}-{end_page}")

            # Parse TOC structure from elements
            sections = self._parse_toc_structure(toc_elements)

            logger.info(f"Pass A: Parsed {len(sections)} sections from TOC")

            return TocExtractionResult(
                doc_id=self.job_id,
                sections=sections,
                toc_pages_used=toc_pages,
                extraction_method="unstructured",
                success=True
            )

        except Exception as e:
            logger.error(f"Pass A: TOC extraction failed: {e}")
            return TocExtractionResult(
                doc_id=self.job_id,
                sections=[],
                toc_pages_used=toc_pages,
                extraction_method="failed",
                success=False,
                error_message=str(e)
            )

    def _parse_toc_structure(self, elements: List) -> List[TocSection]:
        """
        Parse TOC elements into hierarchical section structure using heuristics.

        Uses the TOC-specific heuristics parser from Phase 3.
        """
        # Extract text lines from elements
        text_lines = []
        for elem in elements:
            text = str(elem).strip()
            if text and len(text) >= 3:
                text_lines.append(text)

        # Use heuristics parser to parse TOC structure
        from .toc_heuristics import parse_toc_with_heuristics
        sections = parse_toc_with_heuristics(text_lines)

        return sections


def extract_toc_from_pages(pdf_path: Path, toc_pages: Tuple[int, int], job_id: str,
                           log_file_path: Optional[Path] = None) -> TocExtractionResult:
    """
    Convenience function to extract TOC from specified pages.

    Args:
        pdf_path: Path to PDF file
        toc_pages: Tuple of (start_page, end_page) from Pass 0
        job_id: Job identifier
        log_file_path: Optional path to job log file

    Returns:
        TocExtractionResult with extracted sections
    """
    extractor = TocExtractor(job_id, log_file_path)
    return extractor.extract_toc(pdf_path, toc_pages)


def generate_pass_a_toc_json(result: TocExtractionResult, output_path: Path) -> None:
    """
    Generate passA.toc.json output file per AI prompt spec.

    Format:
    {
        "doc_id": "job_id",
        "extraction_method": "unstructured|fallback",
        "toc_pages_used": {"start": int, "end": int},
        "sections": [
            {
                "section_id": "sha1_hash",
                "title": "Chapter Title",
                "start_page": int,
                "end_page": int,
                "level": int,
                "parent_id": "sha1_hash|null"
            }
        ],
        "total_sections": int,
        "success": bool,
        "error_message": "string|null"
    }
    """
    import json

    # Build JSON structure
    toc_json = {
        "doc_id": result.doc_id,
        "extraction_method": result.extraction_method,
        "toc_pages_used": {
            "start": result.toc_pages_used[0],
            "end": result.toc_pages_used[1]
        },
        "sections": [
            {
                "section_id": section.section_id,
                "title": section.title,
                "start_page": section.start_page,
                "end_page": section.end_page,
                "level": section.level,
                "parent_id": section.parent_id
            }
            for section in result.sections
        ],
        "total_sections": len(result.sections),
        "success": result.success,
        "error_message": result.error_message
    }

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(toc_json, f, indent=2, ensure_ascii=False)

    logger.info(f"Pass A: Generated passA.toc.json at {output_path}")
