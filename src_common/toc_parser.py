# src_common/toc_parser.py
"""
FR1-E1: Table of Contents and Heading Parser for section-aware chunking
Intelligently detects document structure from ToC and heading patterns
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pypdf
from .ttrpg_logging import get_logger

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
    
    def _find_and_parse_toc(self, pdf_reader: pypdf.PdfReader) -> Tuple[List[TocEntry], List[int], bool]:
        """Find and parse Table of Contents pages"""
        toc_pages = []
        toc_entries = []
        
        # Search first 10 pages for ToC
        search_pages = min(10, len(pdf_reader.pages))
        
        for page_num in range(search_pages):
            try:
                page = pdf_reader.pages[page_num]
                text = page.extract_text().lower()
                
                # Check if this page contains ToC indicators
                if any(re.search(pattern, text, re.IGNORECASE) for pattern in self.toc_indicators):
                    logger.info(f"Found ToC on page {page_num + 1}")
                    toc_pages.append(page_num + 1)
                    
                    # Parse ToC entries from this page
                    page_entries = self._parse_toc_page(pdf_reader.pages[page_num], page_num + 1)
                    toc_entries.extend(page_entries)
            
            except Exception as e:
                logger.warning(f"Error processing page {page_num + 1} for ToC: {e}")
        
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
        
        has_toc = len(toc_entries) > 0
        logger.info(f"ToC parsing complete: {len(toc_entries)} entries found on pages {toc_pages}")
        
        return toc_entries, toc_pages, has_toc
    
    def _parse_toc_page(self, page: pypdf.PageObject, page_num: int) -> List[TocEntry]:
        """Parse ToC entries from a single page"""
        entries = []
        text = page.extract_text()
        lines = text.split('\n')
        
        entry_count = 0
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Try to match ToC entry patterns
            entry = self._parse_toc_line(line, entry_count)
            if entry:
                entries.append(entry)
                entry_count += 1
        
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
    
    def _extract_headings_from_content(self, pdf_reader: pypdf.PdfReader) -> List[TocEntry]:
        """Extract headings directly from document content when ToC is unavailable"""
        headings = []
        heading_count = 0
        
        # Skip ToC pages and first few pages, focus on main content
        start_page = min(5, len(pdf_reader.pages) // 10)  # Start at 5 or 10% through document
        
        for page_num in range(start_page, len(pdf_reader.pages)):
            try:
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                # Extract headings from this page
                page_headings = self._extract_page_headings(text, page_num + 1, heading_count)
                headings.extend(page_headings)
                heading_count += len(page_headings)
                
            except Exception as e:
                logger.warning(f"Error extracting headings from page {page_num + 1}: {e}")
        
        logger.info(f"Extracted {len(headings)} headings from document content")
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
