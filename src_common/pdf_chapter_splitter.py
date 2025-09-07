# src_common/pdf_chapter_splitter.py
"""
PDF Chapter Splitter - Pre-processor for large PDFs
Intelligently splits PDFs by chapters before sending to unstructured.io
FR1-E6: Enhanced with configurable size-based auto-splitting
"""

import re
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import pypdf
from .logging import get_logger
from .fr1_config import get_fr1_config

logger = get_logger(__name__)

@dataclass
class Chapter:
    """Represents a detected chapter in the PDF"""
    title: str
    start_page: int
    end_page: int
    page_count: int
    estimated_size: int  # Character count estimate

@dataclass
class SplitManifest:
    """FR1-E6: Manifest details for split operations"""
    original_file: str
    original_size_bytes: int
    original_size_mb: float
    threshold_mb: float
    split_strategy: str  # "semantic_chapters", "page_windows", "no_split"
    split_triggered: bool
    num_parts: int
    part_checksums: List[str] = field(default_factory=list)
    processing_time_ms: int = 0
    
@dataclass
class ChapterSplit:
    """Result of chapter splitting operation"""
    chapters: List[Chapter]
    total_pages: int
    split_successful: bool
    fallback_used: bool
    processing_time_ms: int
    manifest: Optional[SplitManifest] = None  # FR1-E6: Added manifest tracking

class PDFChapterSplitter:
    """Intelligent chapter detection and splitting for large PDFs"""
    
    def __init__(self, max_chapter_pages: int = 50, min_chapter_pages: int = 5, env: str = None):
        """
        Initialize the chapter splitter.
        
        Args:
            max_chapter_pages: Maximum pages per chapter for unstructured.io processing
            min_chapter_pages: Minimum pages to constitute a chapter
            env: Environment name for FR1 configuration (dev/test/prod)
        """
        self.max_chapter_pages = max_chapter_pages
        self.min_chapter_pages = min_chapter_pages
        
        # FR1-E6: Load configuration for size-based splitting
        self.config = get_fr1_config(env)
        self.preprocessor_config = self.config.get_preprocessor_config()
        # Apply page ceiling from config if present
        try:
            cfg_max = int(self.preprocessor_config.get("max_pages_per_part", self.max_chapter_pages))
            if cfg_max > 0:
                self.max_chapter_pages = cfg_max
        except Exception:
            pass
        
        # TTRPG-specific chapter patterns
        self.chapter_patterns = [
            r'^Chapter\s+(\d+|[IVX]+):?\s*(.+)$',           # Chapter 1: Title
            r'^CHAPTER\s+(\d+|[IVX]+):?\s*(.+)$',           # CHAPTER 1: TITLE
            r'^\d+\.\s*([A-Z][A-Za-z\s]{5,})$',             # 1. Chapter Title
            r'^([A-Z][A-Z\s]{10,})$',                       # ALL CAPS CHAPTER TITLE
            r'^Part\s+(\d+|[IVX]+):?\s*(.+)$',              # Part I: Title
            r'^Section\s+(\d+|[IVX]+):?\s*(.+)$',           # Section 1: Title
            r'^APPENDIX\s+([A-Z]):?\s*(.+)$',               # APPENDIX A: Title
            r'^INDEX$|^GLOSSARY$|^BIBLIOGRAPHY$',            # Back matter
            r'^TABLE\s+OF\s+CONTENTS$',                     # Front matter
        ]
    
    def should_auto_split(self, pdf_path: Path) -> Tuple[bool, SplitManifest]:
        """
        FR1-E6: Determine if PDF should be auto-split based on size threshold.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (should_split, manifest)
        """
        file_size_bytes = pdf_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)
        threshold_mb = self.preprocessor_config.get("size_threshold_mb", 40.0)
        
        should_split = self.config.should_split_by_size(file_size_mb)
        
        # Create manifest even if not splitting (for tracking)
        manifest = SplitManifest(
            original_file=str(pdf_path),
            original_size_bytes=file_size_bytes,
            original_size_mb=file_size_mb,
            threshold_mb=threshold_mb,
            split_strategy="no_split" if not should_split else "pending",
            split_triggered=should_split,
            num_parts=1 if not should_split else 0  # Will be updated during splitting
        )
        
        return should_split, manifest
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum for file integrity tracking"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.warning(f"Could not calculate checksum for {file_path}: {e}")
            return "unknown"
        
    def detect_chapters(self, pdf_path: Path) -> ChapterSplit:
        """
        Detect chapters in a PDF using text analysis.
        FR1-E6: Enhanced with size-based auto-splitting decision.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ChapterSplit with detected chapters and manifest
        """
        logger.info(f"Detecting chapters in {pdf_path}")
        start_time = time.time()
        
        # FR1-E6: Check if auto-splitting should be applied
        should_split, manifest = self.should_auto_split(pdf_path)
        manifest.processing_time_ms = 0  # Will be updated at the end
        
        try:
            # Optional: load primer to enhance splitting cues
            try:
                from .ingestion_primer import load_or_create_primer
            except Exception:
                load_or_create_primer = None  # type: ignore

            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                chapters = []
                current_chapter = None
                page_texts = []
                
                # Extract text from first 20 pages to find chapter patterns (optimized)
                max_scan_pages = min(20, total_pages)
                logger.info(f"Scanning first {max_scan_pages} pages for chapter markers")

                for page_num in range(max_scan_pages):
                    try:
                        page = pdf_reader.pages[page_num]
                        text = page.extract_text()
                        page_texts.append((page_num + 1, text))
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                        page_texts.append((page_num + 1, ""))

                # Primer pass: infer additional cues from title/ToC/sample text
                try:
                    if load_or_create_primer:
                        title = pdf_path.stem
                        toc_text = "\n".join(t or "" for _, t in page_texts[:4])
                        primer = load_or_create_primer(self.config._config.get('environment', 'dev'), title, toc_text, [])  # type: ignore
                        cues = []
                        if isinstance(primer, dict):
                            cues = primer.get('procedures', {}).get('cues', []) if primer.get('procedures') else []
                        # Convert cues to regex-ish patterns (simple upper-case headings)
                        for cue in (cues or []):
                            pat = rf'^({re.escape(cue)})[:\s]'
                            if pat not in self.chapter_patterns:
                                self.chapter_patterns.append(pat)
                        logger.info(f"Primer cues applied: {len(cues) if cues else 0}")
                except Exception as e:
                    logger.debug(f"Primer step skipped/failed: {e}")
                
                # Find chapter boundaries
                chapter_pages = []
                for page_num, text in page_texts:
                    if self._is_chapter_start(text):
                        chapter_title = self._extract_chapter_title(text)
                        chapter_pages.append((page_num, chapter_title))
                        logger.debug(f"Found chapter at page {page_num}: {chapter_title}")
                
                # Create chapter objects
                if chapter_pages:
                    for i, (start_page, title) in enumerate(chapter_pages):
                        if i < len(chapter_pages) - 1:
                            end_page = chapter_pages[i + 1][0] - 1
                        else:
                            end_page = total_pages
                        
                        page_count = end_page - start_page + 1
                        
                        # Split large chapters
                        if page_count > self.max_chapter_pages:
                            sub_chapters = self._split_large_chapter(
                                title, start_page, end_page, pdf_reader
                            )
                            chapters.extend(sub_chapters)
                        else:
                            chapters.append(Chapter(
                                title=title,
                                start_page=start_page,
                                end_page=end_page,
                                page_count=page_count,
                                estimated_size=page_count * 2000  # Rough estimate
                            ))
                else:
                    # No chapters detected - use page-based splitting
                    logger.info("No chapter markers found, using page-based splitting")
                    chapters = self._create_page_based_chapters(total_pages)
                
                end_time = time.time()
                processing_time_ms = int((end_time - start_time) * 1000)
                
                # FR1-E6: Update manifest with final details
                manifest.processing_time_ms = processing_time_ms
                if should_split:
                    manifest.split_strategy = "semantic_chapters" if len(chapter_pages) > 0 else "page_windows"
                    manifest.num_parts = len(chapters)
                    # Calculate checksums for chapter parts (placeholder for future implementation)
                    manifest.part_checksums = [f"checksum_{i}" for i in range(len(chapters))]
                
                logger.info(f"Detected {len(chapters)} chapters in {processing_time_ms}ms")
                
                return ChapterSplit(
                    chapters=chapters,
                    total_pages=total_pages,
                    split_successful=len(chapter_pages) > 0,
                    fallback_used=len(chapter_pages) == 0,
                    processing_time_ms=processing_time_ms,
                    manifest=manifest
                )
                
        except Exception as e:
            logger.error(f"Error detecting chapters: {e}")
            # Fallback to simple page-based splitting
            return self._fallback_split(pdf_path)
    
    def _is_chapter_start(self, text: str) -> bool:
        """Check if text indicates the start of a chapter"""
        lines = text.strip().split('\n')
        
        # Check first few lines for chapter patterns
        for line in lines[:5]:
            line = line.strip()
            if not line:
                continue
                
            for pattern in self.chapter_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    return True
        
        return False
    
    def _extract_chapter_title(self, text: str) -> str:
        """Extract chapter title from page text"""
        lines = text.strip().split('\n')
        
        for line in lines[:5]:
            line = line.strip()
            if not line:
                continue
                
            for pattern in self.chapter_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    if len(match.groups()) >= 2:
                        return f"{match.group(1)}: {match.group(2)}"
                    else:
                        return line
        
        # Fallback - use first non-empty line
        for line in lines[:3]:
            line = line.strip()
            if line and len(line) > 5:
                return line[:100]  # Truncate long titles
        
        return "Untitled Chapter"
    
    def _split_large_chapter(self, title: str, start_page: int, end_page: int, pdf_reader: pypdf.PdfReader) -> List[Chapter]:
        """Split a large chapter into smaller sub-chapters"""
        chapters = []
        page_count = end_page - start_page + 1
        
        # Calculate number of sub-chapters needed
        num_sub_chapters = (page_count + self.max_chapter_pages - 1) // self.max_chapter_pages
        pages_per_sub = page_count // num_sub_chapters
        
        for i in range(num_sub_chapters):
            sub_start = start_page + (i * pages_per_sub)
            if i == num_sub_chapters - 1:
                sub_end = end_page  # Last sub-chapter gets remaining pages
            else:
                sub_end = start_page + ((i + 1) * pages_per_sub) - 1
            
            sub_title = f"{title} (Part {i + 1}/{num_sub_chapters})"
            sub_page_count = sub_end - sub_start + 1
            
            chapters.append(Chapter(
                title=sub_title,
                start_page=sub_start,
                end_page=sub_end,
                page_count=sub_page_count,
                estimated_size=sub_page_count * 2000
            ))
        
        return chapters
    
    def _create_page_based_chapters(self, total_pages: int) -> List[Chapter]:
        """Create chapters based on page ranges when no chapter markers are found"""
        chapters = []
        num_chapters = (total_pages + self.max_chapter_pages - 1) // self.max_chapter_pages
        pages_per_chapter = total_pages // num_chapters
        
        for i in range(num_chapters):
            start_page = (i * pages_per_chapter) + 1
            if i == num_chapters - 1:
                end_page = total_pages  # Last chapter gets remaining pages
            else:
                end_page = (i + 1) * pages_per_chapter
            
            page_count = end_page - start_page + 1
            
            chapters.append(Chapter(
                title=f"Section {i + 1}",
                start_page=start_page,
                end_page=end_page,
                page_count=page_count,
                estimated_size=page_count * 2000
            ))
        
        return chapters
    
    def _fallback_split(self, pdf_path: Path) -> ChapterSplit:
        """Fallback splitting when chapter detection fails"""
        try:
            # FR1-E6: Create manifest for fallback case
            should_split, manifest = self.should_auto_split(pdf_path)
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                chapters = self._create_page_based_chapters(total_pages)
                
                # Update manifest for fallback
                manifest.processing_time_ms = 100
                manifest.split_strategy = "page_windows"
                manifest.num_parts = len(chapters)
                manifest.part_checksums = [f"fallback_checksum_{i}" for i in range(len(chapters))]
                
                return ChapterSplit(
                    chapters=chapters,
                    total_pages=total_pages,
                    split_successful=False,
                    fallback_used=True,
                    processing_time_ms=100,  # Quick fallback
                    manifest=manifest
                )
        except Exception as e:
            logger.error(f"Fallback split failed: {e}")
            # Preserve measured size info from should_auto_split, but mark error
            try:
                manifest.split_strategy = "error"  # type: ignore[name-defined]
                manifest.processing_time_ms = 100  # type: ignore[name-defined]
                manifest.num_parts = 0  # type: ignore[name-defined]
            except Exception:
                manifest = SplitManifest(
                    original_file=str(pdf_path),
                    original_size_bytes=0,
                    original_size_mb=0.0,
                    threshold_mb=40.0,
                    split_strategy="error",
                    split_triggered=False,
                    num_parts=0,
                    processing_time_ms=100,
                )
            return ChapterSplit(
                chapters=[],
                total_pages=0,
                split_successful=False,
                fallback_used=True,
                processing_time_ms=100,
                manifest=manifest
            )
    
    def extract_chapter_pages(self, pdf_path: Path, chapter: Chapter, output_path: Path) -> bool:
        """
        Extract specific chapter pages to a new PDF file.
        
        Args:
            pdf_path: Source PDF path
            chapter: Chapter to extract
            output_path: Output path for chapter PDF
            
        Returns:
            True if extraction successful
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                pdf_writer = pypdf.PdfWriter()
                
                # Extract pages (pypdf uses 0-based indexing)
                for page_num in range(chapter.start_page - 1, chapter.end_page):
                    if page_num < len(pdf_reader.pages):
                        pdf_writer.add_page(pdf_reader.pages[page_num])
                
                # Write chapter PDF
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)
                
                logger.info(f"Extracted chapter '{chapter.title}' to {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error extracting chapter '{chapter.title}': {e}")
            return False


def split_pdf_by_chapters(pdf_path: Path, output_dir: Path, max_chapter_pages: int = 50, env: str = None) -> ChapterSplit:
    """
    Convenience function to split a PDF by chapters.
    FR1-E6: Enhanced with configurable size-based auto-splitting
    
    Args:
        pdf_path: Path to input PDF
        output_dir: Directory to store chapter PDFs
        max_chapter_pages: Maximum pages per chapter
        env: Environment name for FR1 configuration (dev/test/prod)
        
    Returns:
        ChapterSplit with results including manifest
    """
    splitter = PDFChapterSplitter(max_chapter_pages=max_chapter_pages, env=env)
    return splitter.detect_chapters(pdf_path)


if __name__ == "__main__":
    # Test the chapter splitter
    pdf_path = Path("E:/Downloads/A_TTRPG_Tool/Source_Books/Paizo/Pathfinder/Core/Pathfinder RPG - Core Rulebook (6th Printing).pdf")
    
    if pdf_path.exists():
        result = split_pdf_by_chapters(pdf_path, Path("temp_chapters"))
        
        print(f"Chapter detection results:")
        print(f"Total pages: {result.total_pages}")
        print(f"Chapters found: {len(result.chapters)}")
        print(f"Split successful: {result.split_successful}")
        print(f"Fallback used: {result.fallback_used}")
        print(f"Processing time: {result.processing_time_ms}ms")
        
        for i, chapter in enumerate(result.chapters):
            print(f"  {i+1}. {chapter.title} (Pages {chapter.start_page}-{chapter.end_page}, {chapter.page_count} pages)")
    else:
        print("Test PDF not found")
