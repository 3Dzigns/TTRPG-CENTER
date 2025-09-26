# src_common/toc_parser.py
"""
FR1-E1: Table of Contents and Heading Parser for section-aware chunking
Intelligently detects document structure from ToC and heading patterns
"""

import re
import io
import concurrent.futures
import threading
try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import fitz  # type: ignore
    HAS_PYMUPDF = True
except ImportError:
    fitz = None  # type: ignore
    HAS_PYMUPDF = False

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pypdf
from .ttrpg_logging import get_logger
from .patterns.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig

logger = get_logger(__name__)

@dataclass
class TocEntry:
    """Table of Contents entry with hierarchical structure"""
    title: str
    page: int
    level: int
    section_id: str
    parent_id: Optional[str] = None
    children: List[str] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

@dataclass
class DocumentOutline:
    """Document structure outline from ToC parsing"""
    entries: List[TocEntry]
    has_toc: bool
    toc_pages: List[int]
    total_pages: int
    
class TocParser:
    """
    FR1-E1: Parses Table of Contents and document headings for section-aware chunking
    """
    
    def __init__(self):
        # TTRPG-specific ToC patterns
        self.toc_indicators = [
            r'table\s+of\s+contents',
            r'contents',
            r'index',
            r'chapter\s+list',
            r'section\s+overview'
        ]

        # Configure circuit breaker for PDF text extraction
        pdf_circuit_config = CircuitBreakerConfig(
            failure_threshold=3,      # Open after 3 failures
            recovery_timeout=60,      # Try recovery after 60 seconds
            timeout=10.0,            # 10 second operation timeout
            max_retry_attempts=2      # 2 retry attempts in half-open
        )
        self.pdf_circuit = get_circuit_breaker("pdf_text_extraction", pdf_circuit_config)
        
        # Heading patterns for different levels
        self.heading_patterns = [
            # Level 1 - Chapters and major sections
            (1, r'^(Chapter \d+|CHAPTER \d+|Part \d+|PART \d+):?\s*(.+)$'),
            (1, r'^([A-Z][A-Z\s]{10,})$'),  # All caps headings
            (1, r'^(Appendix [A-Z]):?\s*(.+)$'),
            
            # Level 2 - Subsections
            (2, r'^(\d+\.\d+)\s+(.+)$'),  # 1.1 Subsection
            (2, r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$'),  # Title Case headings
            
            # Level 3 - Sub-subsections
            (3, r'^(\d+\.\d+\.\d+)\s+(.+)$'),  # 1.1.1 Sub-subsection
            (3, r'^([A-Z][a-z]+\s+[A-Z][a-z]+):\s*(.+)$'),  # Category: Description
        ]
        
        # Page number patterns in ToC
        self.page_patterns = [
            r'\.+\s*(\d+)$',  # Dotted leaders: "Chapter 1 .... 15"
            r'\s+(\d+)$',     # Simple space: "Chapter 1 15"
            r'\t+(\d+)$',     # Tab separated: "Chapter 1\t15"
            r'-+\s*(\d+)$',   # Dashed leaders: "Chapter 1 --- 15"
        ]
        # Allow scanning additional pages when ToC is offset by long front-matter
        self.max_toc_search_pages = 20

        self._current_pdf_path: Optional[Path] = None
        self._fitz_doc = None
        self._ocr_enabled = HAS_TESSERACT and HAS_PYMUPDF


    def _extract_text_safely(self, page: pypdf.PageObject, page_index: int, timeout_seconds: float = 10.0) -> str:
        """
        Extract text from PDF page with timeout protection and circuit breaker.

        Args:
            page: PDF page object to extract text from
            timeout_seconds: Maximum time to wait for extraction

        Returns:
            Extracted text or empty string on timeout/failure
        """
        def _extract_text():
            """Internal text extraction function for timeout wrapper"""
            return page.extract_text()

        try:
            # Use circuit breaker to protect against repeated failures
            text = self.pdf_circuit.call(_extract_text_with_timeout, _extract_text, timeout_seconds)
        except Exception as e:
            logger.warning(f"Text extraction failed with circuit breaker: {e}")
            text = ""

        if text:
            return text

        if self._ocr_enabled:
            ocr_text = self._extract_text_via_ocr(page_index)
            if ocr_text:
                logger.debug(f"TocParser: OCR fallback used for page {page_index + 1}")
            return ocr_text

        return ""

    def _open_pdf_for_ocr(self, pdf_path: Path) -> None:
        """Open PDF with PyMuPDF for OCR fallback when available."""
        if not self._ocr_enabled:
            return

        if self._current_pdf_path == pdf_path and self._fitz_doc is not None:
            return

        self._close_ocr_resources()

        try:
            self._fitz_doc = fitz.open(pdf_path)  # type: ignore[arg-type]
            self._current_pdf_path = pdf_path
            logger.debug("TocParser: Initialized OCR fallback session")
        except Exception as exc:
            logger.debug(f"TocParser: Unable to open PDF for OCR fallback: {exc}")
            self._fitz_doc = None
            self._current_pdf_path = None

    def _close_ocr_resources(self) -> None:
        """Release OCR resources if they were opened."""
        if self._fitz_doc is not None:
            try:
                self._fitz_doc.close()
            except Exception:
                pass
        self._fitz_doc = None
        self._current_pdf_path = None

    def _extract_text_via_ocr(self, page_index: int) -> str:
        """Extract text from a page using OCR fallback."""
        if not self._ocr_enabled or self._fitz_doc is None:
            return ""

        try:
            page = self._fitz_doc.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) if HAS_PYMUPDF else None
            if pix is None:
                return ""

            image = Image.open(io.BytesIO(pix.tobytes("png")))
            try:
                text = pytesseract.image_to_string(image)
            finally:
                image.close()

            return text
        except Exception as exc:
            logger.warning(f"TocParser: OCR fallback failed for page {page_index + 1}: {exc}")
            return ""

    def _extract_text_with_timeout(extract_func, timeout_seconds: float) -> str:
        """
        Execute text extraction with timeout protection using ThreadPoolExecutor.

        Args:
            extract_func: Function to execute text extraction
            timeout_seconds: Maximum execution time

        Returns:
            Extracted text or empty string on timeout

        Raises:
            concurrent.futures.TimeoutError: If extraction exceeds timeout
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdf_extract") as executor:
            future = executor.submit(extract_func)
            try:
                result = future.result(timeout=timeout_seconds)
                logger.debug(f"Text extraction completed within {timeout_seconds}s")
                return result

            except concurrent.futures.TimeoutError:
                logger.warning(f"Text extraction timed out after {timeout_seconds}s - returning empty text")
                # Cancel the future to clean up resources
                future.cancel()
                raise

            except Exception as e:
                logger.error(f"Text extraction failed: {e}")
                raise
    
    def parse_document_structure(self, pdf_path: Path) -> DocumentOutline:
        """
        Parse document structure from ToC and headings

        Args:
            pdf_path: Path to PDF file

        Returns:
            DocumentOutline with hierarchical structure
        """
        logger.info(f"Parsing document structure from {pdf_path}")

        try:
            self._open_pdf_for_ocr(pdf_path)
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)

                # First, try to find and parse Table of Contents
                toc_entries, toc_pages, has_toc = self._find_and_parse_toc(pdf_reader)

                # If no ToC found or incomplete, extract headings from content
                if not has_toc or len(toc_entries) < 3:
                    logger.info("No comprehensive ToC found, extracting headings from content")
                    content_headings = self._extract_headings_from_content(pdf_reader)

                    # Merge or replace ToC entries with content headings
                    if len(content_headings) > len(toc_entries):
                        toc_entries = content_headings

                # Build hierarchical structure
                hierarchical_entries = self._build_hierarchy(toc_entries)

                logger.info(f"Document structure parsed: {len(hierarchical_entries)} sections, ToC pages: {toc_pages}")

                return DocumentOutline(
                    entries=hierarchical_entries,
                    has_toc=has_toc,
                    toc_pages=toc_pages,
                    total_pages=total_pages
                )

        except Exception as e:
            logger.error(f"Error parsing document structure: {e}")
            # Return minimal structure
            return DocumentOutline(
                entries=[TocEntry("Document", 1, 1, "doc_1", None, [])],
                has_toc=False,
                toc_pages=[],
                total_pages=1
            )
        finally:
            self._close_ocr_resources()


    def _find_and_parse_toc(self, pdf_reader: pypdf.PdfReader) -> Tuple[List[TocEntry], List[int], bool]:
        """Find and parse Table of Contents pages with enhanced error recovery"""
        toc_pages = []
        toc_entries = []
        successful_pages = 0
        failed_pages = []

        # Search first pages for ToC
        search_pages = min(self.max_toc_search_pages, len(pdf_reader.pages))
        logger.info(f"BUG-035 Fix: Searching {search_pages} pages for ToC with timeout protection")

        for page_num in range(search_pages):
            try:
                page = pdf_reader.pages[page_num]
                raw_text = self._extract_text_safely(page, page_num)
                text = raw_text.lower()

                # Skip pages where text extraction failed (timeout or error)
                if not text:
                    failed_pages.append(page_num + 1)
                    logger.warning(f"BUG-035: Skipping page {page_num + 1} due to text extraction failure")
                    continue

                successful_pages += 1

                # Check if this page contains ToC indicators
                if any(re.search(pattern, text, re.IGNORECASE) for pattern in self.toc_indicators):
                    logger.info(f"Found ToC on page {page_num + 1}")
                    toc_pages.append(page_num + 1)

                    # Parse ToC entries from this page
                    page_entries = self._parse_toc_page(pdf_reader.pages[page_num], page_num + 1)
                    toc_entries.extend(page_entries)

            except Exception as e:
                failed_pages.append(page_num + 1)
                logger.warning(f"BUG-035: Error processing page {page_num + 1} for ToC: {e}")
                continue  # Skip problematic pages, continue with others
        
        # If we found multiple ToC pages, continue parsing subsequent pages
        if toc_pages and len(toc_pages) == 1:
            # Check if ToC continues on next pages
            toc_start = toc_pages[0]
            for page_num in range(toc_start, min(toc_start + 5, len(pdf_reader.pages))):
                try:
                    page_entries = self._parse_toc_page(pdf_reader.pages[page_num], page_num + 1)
                    if page_entries:  # If we found entries, this page is part of ToC
                        if page_num + 1 not in toc_pages:
                            toc_pages.append(page_num + 1)
                        toc_entries.extend(page_entries)
                    elif page_num > toc_start:  # No entries and not first page = end of ToC
                        break
                except Exception as e:
                    logger.warning(f"Error parsing ToC continuation page {page_num + 1}: {e}")
        
        if not toc_entries:
            outline_entries = self._parse_pdf_outline(pdf_reader)
            if outline_entries:
                logger.info(
                    "ToC text scan produced no entries; using PDF outline fallback (found %d sections)",
                    len(outline_entries),
                )
                toc_entries = outline_entries
                toc_pages = sorted({entry.page for entry in outline_entries})

        has_toc = len(toc_entries) > 0

        # Enhanced logging for BUG-035 diagnostics
        if failed_pages:
            logger.warning(f"BUG-035: ToC parsing completed with {len(failed_pages)} failed pages: {failed_pages}")

        logger.info(f"BUG-035 Fix: ToC parsing complete - {len(toc_entries)} entries found on pages {toc_pages}")
        logger.info(f"BUG-035 Stats: {successful_pages}/{search_pages} pages processed successfully")

        return toc_entries, toc_pages, has_toc
    
    def _parse_toc_page(self, page: pypdf.PageObject, page_num: int) -> List[TocEntry]:
        """Parse ToC entries from a single page with enhanced error recovery"""
        entries = []
        text = self._extract_text_safely(page, page_num - 1)

        # Handle cases where text extraction failed (timeout or error)
        if not text:
            logger.warning(f"BUG-035: No text extracted from ToC page {page_num} - skipping ToC parsing")
            return entries

        lines = text.split('\n')
        entry_count = 0
        parse_errors = 0

        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue

            try:
                # Try to match ToC entry patterns
                entry = self._parse_toc_line(line, entry_count)
                if entry:
                    entries.append(entry)
                    entry_count += 1
            except Exception as e:
                parse_errors += 1
                logger.debug(f"BUG-035: Failed to parse ToC line '{line[:50]}...': {e}")
                continue  # Skip problematic lines, continue with others

        # Log summary statistics for debugging
        if parse_errors > 0:
            logger.warning(f"BUG-035: ToC page {page_num} had {parse_errors} parsing errors, extracted {len(entries)} entries")
        else:
            logger.debug(f"BUG-035: ToC page {page_num} successfully parsed {len(entries)} entries")

        return entries
    
    def _parse_toc_line(self, line: str, entry_count: int) -> Optional[TocEntry]:
        """Parse a single ToC line"""
        # Remove common ToC formatting
        clean_line = re.sub(r'[\.]{3,}', ' ', line)  # Remove dotted leaders
        clean_line = re.sub(r'[-]{3,}', ' ', clean_line)  # Remove dashed leaders
        
        # Try to extract page number
        page_num = None
        title = clean_line
        
        for pattern in self.page_patterns:
            match = re.search(pattern, clean_line)
            if match:
                page_num = int(match.group(1))
                title = re.sub(pattern, '', clean_line).strip()
                break
        
        # If no page number found, skip
        if page_num is None:
            return None
        
        # Determine heading level based on indentation and content
        level = self._determine_heading_level(line, title)
        
        # Generate section ID
        section_id = f"section_{entry_count:03d}"
        
        return TocEntry(
            title=title,
            page=page_num,
            level=level,
            section_id=section_id
        )
    
    def _determine_heading_level(self, original_line: str, title: str) -> int:
        """Determine the hierarchical level of a heading"""
        # Count leading whitespace for indentation
        leading_spaces = len(original_line) - len(original_line.lstrip())
        
        # Check for explicit level indicators
        if re.match(r'^(Chapter|CHAPTER|Part|PART)\s+\d+', title, re.IGNORECASE):
            return 1
        elif re.match(r'^(Appendix|APPENDIX)\s+[A-Z]', title, re.IGNORECASE):
            return 1
        elif re.match(r'^\d+\.\s+', title):  # "1. Section"
            return 2
        elif re.match(r'^\d+\.\d+\s+', title):  # "1.1 Subsection"
            return 3
        elif leading_spaces > 10:  # Heavy indentation
            return 3
        elif leading_spaces > 5:   # Medium indentation
            return 2
        else:
            return 1
    
    def _parse_pdf_outline(self, pdf_reader: pypdf.PdfReader) -> List[TocEntry]:
        """Build TocEntry list from embedded PDF outline/bookmarks."""
        entries: List[TocEntry] = []
        outline = getattr(pdf_reader, "outline", None)
        if not outline:
            outline = getattr(pdf_reader, "outlines", None)
        if not outline:
            return entries

        def walk(nodes, level: int, parent_id: Optional[str]) -> None:
            for node in nodes:
                if isinstance(node, list):
                    walk(node, level, parent_id)
                    continue

                title = getattr(node, "title", str(node)) or ""
                title = title.strip()
                try:
                    page_index = pdf_reader.get_destination_page_number(node)
                except Exception:
                    destination = getattr(node, "destination", None)
                    if destination is None:
                        continue
                    try:
                        page_index = pdf_reader.get_destination_page_number(destination)
                    except Exception:
                        continue

                section_id = f"outline_{len(entries):03d}"
                entry = TocEntry(
                    title=title[:100] or f"Section {len(entries) + 1}",
                    page=page_index + 1,
                    level=level,
                    section_id=section_id,
                    parent_id=parent_id,
                )
                entries.append(entry)
                if parent_id:
                    for existing in entries:
                        if existing.section_id == parent_id:
                            existing.children.append(section_id)
                            break

                child_nodes = getattr(node, "children", None)
                if isinstance(child_nodes, list) and child_nodes:
                    walk(child_nodes, level + 1, section_id)

        initial_outline = outline if isinstance(outline, list) else [outline]
        walk(initial_outline, 1, None)
        return entries

    def _extract_headings_from_content(self, pdf_reader: pypdf.PdfReader) -> List[TocEntry]:
        """Extract headings directly from document content when ToC is unavailable"""
        headings = []
        heading_count = 0
        successful_pages = 0
        failed_pages = []

        # Skip ToC pages and first few pages, focus on main content
        start_page = min(5, len(pdf_reader.pages) // 10)  # Start at 5 or 10% through document
        total_pages = len(pdf_reader.pages) - start_page

        logger.info(f"BUG-035 Fix: Extracting headings from {total_pages} content pages with timeout protection")

        for page_num in range(start_page, len(pdf_reader.pages)):
            try:
                page = pdf_reader.pages[page_num]
                text = self._extract_text_safely(page)

                # Skip pages where text extraction failed (timeout or error)
                if not text:
                    failed_pages.append(page_num + 1)
                    logger.debug(f"BUG-035: Skipping page {page_num + 1} due to text extraction failure")
                    continue

                successful_pages += 1

                # Extract headings from this page
                page_headings = self._extract_page_headings(text, page_num + 1, heading_count)
                headings.extend(page_headings)
                heading_count += len(page_headings)

            except Exception as e:
                failed_pages.append(page_num + 1)
                logger.warning(f"BUG-035: Error extracting headings from page {page_num + 1}: {e}")
                continue  # Skip problematic pages, continue with others

        # Enhanced logging for BUG-035 diagnostics
        if failed_pages:
            logger.warning(f"BUG-035: Heading extraction completed with {len(failed_pages)} failed pages: {failed_pages[:10]}")

        logger.info(f"BUG-035 Fix: Extracted {len(headings)} headings from document content")
        logger.info(f"BUG-035 Stats: {successful_pages}/{total_pages} content pages processed successfully")

        return headings
    
    def _extract_page_headings(self, text: str, page_num: int, base_count: int) -> List[TocEntry]:
        """Extract headings from a single page of text"""
        headings = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Try each heading pattern
            for level, pattern in self.heading_patterns:
                match = re.match(pattern, line)
                if match:
                    # Extract title from pattern groups
                    if len(match.groups()) >= 2:
                        title = f"{match.group(1)}: {match.group(2)}"
                    else:
                        title = match.group(1) if match.groups() else line
                    
                    section_id = f"section_{base_count + len(headings):03d}"
                    
                    heading = TocEntry(
                        title=title[:100],  # Limit title length
                        page=page_num,
                        level=level,
                        section_id=section_id
                    )
                    
                    headings.append(heading)
                    break  # Only match first pattern per line
        
        return headings
    
    def _build_hierarchy(self, entries: List[TocEntry]) -> List[TocEntry]:
        """Build hierarchical structure from flat list of entries"""
        if not entries:
            return entries
        
        # Sort by page number to ensure proper order
        entries.sort(key=lambda x: x.page)
        
        # Build parent-child relationships
        stack = []  # Stack to track parent entries at each level
        
        for entry in entries:
            # Find appropriate parent based on level
            while stack and stack[-1].level >= entry.level:
                stack.pop()
            
            if stack:
                # Set parent relationship
                parent = stack[-1]
                entry.parent_id = parent.section_id
                parent.children.append(entry.section_id)
            
            stack.append(entry)
        
        return entries
    
    def get_section_for_page(self, outline: DocumentOutline, page_num: int) -> Optional[TocEntry]:
        """Get the section that contains a given page number"""
        if not outline.entries:
            return None
        
        # Find the section that contains this page
        current_section = None
        
        for i, entry in enumerate(outline.entries):
            if entry.page <= page_num:
                current_section = entry
                
                # Check if next entry starts after this page
                if i + 1 < len(outline.entries):
                    next_entry = outline.entries[i + 1]
                    if next_entry.page > page_num:
                        break
            else:
                break
        
        return current_section
    
    def get_section_boundaries(self, outline: DocumentOutline) -> Dict[str, Tuple[int, int]]:
        """Get page boundaries for each section"""
        boundaries = {}
        
        for i, entry in enumerate(outline.entries):
            start_page = entry.page
            
            # Find end page (start of next section - 1, or last page)
            if i + 1 < len(outline.entries):
                end_page = outline.entries[i + 1].page - 1
            else:
                end_page = outline.total_pages
            
            boundaries[entry.section_id] = (start_page, end_page)
        
        return boundaries


def parse_document_toc(pdf_path: Path) -> DocumentOutline:
    """
    Convenience function to parse document structure
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        DocumentOutline with hierarchical structure
    """
    parser = TocParser()
    return parser.parse_document_structure(pdf_path)


if __name__ == "__main__":
    # Test ToC parser
    pdf_path = Path("E:/Downloads/A_TTRPG_Tool/Source_Books/Paizo/Pathfinder/Core/Pathfinder RPG - Core Rulebook (6th Printing).pdf")
    
    if pdf_path.exists():
        outline = parse_document_toc(pdf_path)
        
        print(f"Document Structure Analysis:")
        print(f"Has ToC: {outline.has_toc}")
        print(f"ToC Pages: {outline.toc_pages}")
        print(f"Total Sections: {len(outline.entries)}")
        print()
        
        print("Section Hierarchy:")
        for entry in outline.entries[:15]:  # Show first 15 sections
            indent = "  " * (entry.level - 1)
            print(f"{indent}{entry.title} (Page {entry.page}, Level {entry.level})")
    else:
        print("Test PDF not found")
