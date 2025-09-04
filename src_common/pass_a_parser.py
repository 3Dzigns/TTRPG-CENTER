# src_common/pass_a_parser.py
"""
Pass A - PDF parsing and chunking using pypdf as fallback
Implements the first pass of the Phase 1 ingestion pipeline.
"""

import json
import os
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

# Fallback imports when unstructured has issues
try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.chunking.title import chunk_by_title
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    
import pypdf

from ttrpg_logging import get_logger
from fr1_config import get_fr1_config
from toc_parser import TocParser, DocumentOutline

logger = get_logger(__name__)


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk - FR1-E1 Enhanced"""
    page: int
    section: str
    chunk_type: str
    element_id: str
    coordinates: Optional[Dict[str, float]] = None
    confidence: Optional[float] = None
    # FR1-E1: Section-aware metadata
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    section_level: Optional[int] = None
    parent_section_id: Optional[str] = None


@dataclass 
class DocumentChunk:
    """Structured representation of a document chunk"""
    id: str
    content: str
    metadata: ChunkMetadata


@dataclass
class PassAOutput:
    """Contract-compliant output for Pass A"""
    job_id: str
    phase: str
    tool: str
    input_file: str
    chunks: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    processing_metadata: Dict[str, Any]


class PassAParser:
    """PDF parser using unstructured.io or pypdf fallback for Pass A of the ingestion pipeline
    FR1-E1 Enhanced: Section-aware chunking with ToC/heading parser"""
    
    def __init__(self, job_id: str, env: str = None):
        self.job_id = job_id
        self.tool_name = "unstructured.io" if UNSTRUCTURED_AVAILABLE else "pypdf"
        
        # FR1-E1: Initialize configuration and ToC parser
        self.fr1_config = get_fr1_config(env)
        self.toc_parser = TocParser()
        self.document_outline = None  # Will be populated during parsing
        
    def parse_pdf(self, pdf_path: Path, output_dir: Path) -> PassAOutput:
        """
        Parse PDF document and extract structured chunks.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to write output files
            
        Returns:
            PassAOutput with parsed chunks and metadata
        """
        logger.info(f"Starting Pass A parsing for {pdf_path}", extra={
            'job_id': self.job_id,
            'phase': 'pass_a',
            'input_file': str(pdf_path),
            'component': 'pass_a_parser'
        })
        
        start_time = time.time()
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # FR1-E1: Parse document structure first for section-aware chunking
            if self.fr1_config.get("preprocessor", "semantic_split_preferred", True):
                logger.info("FR1-E1: Parsing document structure for section-aware chunking")
                self.document_outline = self.toc_parser.parse_document_structure(pdf_path)
                logger.info(f"Found {len(self.document_outline.entries)} sections in document")
            else:
                self.document_outline = None
            
            # Check if PDF is large and needs chapter-based processing
            file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
            if file_size_mb > 50:  # Large PDFs (>50MB) use chapter-based processing
                logger.info(f"Large PDF detected ({file_size_mb:.1f}MB), using chapter-based processing")
                chunks = self._parse_with_chapters(pdf_path)
            elif UNSTRUCTURED_AVAILABLE:
                chunks = self._parse_with_unstructured(pdf_path)
            else:
                chunks = self._parse_with_pypdf(pdf_path)
            
            logger.info(f"Created {len(chunks)} chunks from PDF")
            
            # Calculate processing statistics
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            statistics = {
                "total_chunks": len(chunks),
                "total_elements": len(chunks),  # For pypdf fallback, elements == chunks
                "processing_time_ms": processing_time_ms,
                "average_chunk_length": sum(len(chunk['content']) for chunk in chunks) // len(chunks) if chunks else 0,
                "file_size_bytes": pdf_path.stat().st_size
            }
            
            processing_metadata = {
                "tool": self.tool_name,
                "version": self._get_tool_version(),
                "strategy": "auto" if UNSTRUCTURED_AVAILABLE else "simple_chunking",
                "max_characters": 1500,
                "language": "eng",
                "infer_tables": UNSTRUCTURED_AVAILABLE,
                "timestamp": time.time()
            }
            
            # Create output object
            output = PassAOutput(
                job_id=self.job_id,
                phase="pass_a",
                tool=self.tool_name,
                input_file=str(pdf_path),
                chunks=chunks,
                statistics=statistics,
                processing_metadata=processing_metadata
            )
            
            # Write output to file
            output_file = output_dir / f"{self.job_id}_pass_a_chunks.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(output), f, indent=2, ensure_ascii=False)
            
            logger.info(f"Pass A completed successfully", extra={
                'job_id': self.job_id,
                'phase': 'pass_a',
                'chunks_created': len(chunks),
                'processing_time_ms': processing_time_ms,
                'output_file': str(output_file),
                'component': 'pass_a_parser'
            })
            
            return output
            
        except Exception as e:
            logger.error(f"Pass A parsing failed: {str(e)}", extra={
                'job_id': self.job_id,
                'phase': 'pass_a',
                'error': str(e),
                'input_file': str(pdf_path),
                'component': 'pass_a_parser'
            })
            raise
    
    def _parse_with_unstructured(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Parse PDF using unstructured.io"""
        logger.debug(f"Partitioning PDF with unstructured.io: {pdf_path}")
        elements = partition_pdf(
            filename=str(pdf_path),
            strategy="auto",
            infer_table_structure=True,
            extract_images_in_pdf=False,
            include_page_breaks=True,
            languages=["eng"],
        )
        
        logger.info(f"Extracted {len(elements)} elements from PDF")
        
        # Chunk elements by title for better semantic grouping
        logger.debug("Chunking elements by title")
        chunked_elements = chunk_by_title(
            elements,
            max_characters=1500,
            new_after_n_chars=1200,
            combine_text_under_n_chars=200,
        )
        
        logger.info(f"Created {len(chunked_elements)} chunks from elements")
        
        # Convert to our structured format
        chunks = []
        for i, element in enumerate(chunked_elements):
            chunk_id = f"{self.job_id}_chunk_{i:03d}"
            
            # Extract metadata from unstructured element
            metadata = ChunkMetadata(
                page=getattr(element.metadata, 'page_number', 1),
                section=self._extract_section_name_unstructured(element),
                chunk_type=str(element.category) if hasattr(element, 'category') else 'text',
                element_id=getattr(element.metadata, 'element_id', f'element_{i}'),
                coordinates=self._extract_coordinates(element),
                confidence=getattr(element.metadata, 'detection_confidence', None)
            )
            
            chunk = DocumentChunk(
                id=chunk_id,
                content=str(element).strip(),
                metadata=metadata
            )
            
            chunks.append(asdict(chunk))
        
        return chunks
    
    def _parse_with_pypdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Parse PDF using pypdf as fallback"""
        logger.debug(f"Parsing PDF with pypdf: {pdf_path}")
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            
            full_text = ""
            page_texts = []
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                page_texts.append((page_num, page_text))
                full_text += f"\n--- PAGE {page_num} ---\n" + page_text
        
        logger.info(f"Extracted text from {len(pdf_reader.pages)} pages")
        
        # Simple chunking based on content structure
        chunks = self._chunk_text_simple(full_text, page_texts)
        
        return chunks
    
    def _chunk_text_simple(self, full_text: str, page_texts: List[tuple]) -> List[Dict[str, Any]]:
        """Simple text chunking for pypdf fallback"""
        chunks = []
        
        # Split text into paragraphs and sections
        sections = self._split_into_sections(full_text)
        
        for i, section_text in enumerate(sections):
            if len(section_text.strip()) < 50:  # Skip very short sections
                continue
                
            chunk_id = f"{self.job_id}_chunk_{i:03d}"
            
            # Determine page number from content
            page_num = self._find_page_for_text(section_text, page_texts)
            
            metadata = ChunkMetadata(
                page=page_num,
                section=self._extract_section_name_text(section_text),
                chunk_type='text',
                element_id=f'element_{i}',
                coordinates=None,
                confidence=None
            )
            
            chunk = DocumentChunk(
                id=chunk_id,
                content=section_text.strip(),
                metadata=metadata
            )
            
            chunks.append(asdict(chunk))
        
        return chunks
    
    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into logical sections"""
        # Split on chapter headings, major breaks, or double newlines
        sections = []
        
        # First try to split on chapter/section headings
        chapter_pattern = r'(Chapter \d+[^\n]*|[A-Z][A-Z\s]{2,}[A-Z][^\n]*)'
        parts = re.split(chapter_pattern, text)
        
        current_section = ""
        for part in parts:
            if re.match(chapter_pattern, part):
                if current_section.strip():
                    sections.append(current_section)
                current_section = part + "\n"
            else:
                current_section += part
        
        if current_section.strip():
            sections.append(current_section)
        
        # If no chapters found, split on double newlines with some intelligence
        if len(sections) <= 1:
            paragraphs = text.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) > 1500:  # Max chunk size
                    if current_chunk.strip():
                        sections.append(current_chunk)
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para if current_chunk else para
            
            if current_chunk.strip():
                sections.append(current_chunk)
        
        return [s for s in sections if len(s.strip()) > 50]
    
    def _find_page_for_text(self, text: str, page_texts: List[tuple]) -> int:
        """Find which page a text section belongs to"""
        text_sample = text[:100].strip()
        
        for page_num, page_text in page_texts:
            if text_sample in page_text:
                return page_num
        
        return 1  # Default to first page
    
    def _extract_section_name_text(self, text: str) -> str:
        """Extract section name from raw text"""
        lines = text.strip().split('\n')
        first_line = lines[0] if lines else text[:50]
        
        # Look for chapter/section headers
        if re.match(r'Chapter \d+', first_line):
            return first_line[:50]
        
        # Look for all-caps headers
        if first_line.isupper() and len(first_line) > 3:
            return first_line[:50]
        
        # Infer from content
        content_lower = text.lower()
        if any(word in content_lower for word in ['spell', 'magic', 'cast']):
            return 'Spells'
        elif any(word in content_lower for word in ['combat', 'attack', 'damage', 'hit points']):
            return 'Combat'
        elif any(word in content_lower for word in ['character', 'race', 'class', 'ability score']):
            return 'Character Creation'
        else:
            return 'General'
    
    def _extract_section_name_unstructured(self, element) -> str:
        """Extract section name from element metadata or content"""
        if hasattr(element, 'category') and element.category == 'Title':
            return str(element)[:50]  # Use title text as section name
        
        if hasattr(element.metadata, 'section'):
            return element.metadata.section
            
        # Try to infer from content patterns
        content = str(element)
        if content.startswith('Chapter '):
            return content.split('\n')[0][:50]
        elif any(word in content.lower() for word in ['spell', 'magic']):
            return 'Spells'
        elif any(word in content.lower() for word in ['combat', 'attack', 'damage']):
            return 'Combat'
        elif any(word in content.lower() for word in ['character', 'race', 'class']):
            return 'Character Creation'
        else:
            return 'General'
    
    def _extract_coordinates(self, element) -> Optional[Dict[str, float]]:
        """Extract coordinate information if available"""
        if hasattr(element.metadata, 'coordinates'):
            coords = element.metadata.coordinates
            if coords and hasattr(coords, 'points'):
                # Convert to simple bounding box format
                points = coords.points
                if points:
                    x_coords = [p[0] for p in points]
                    y_coords = [p[1] for p in points]
                    return {
                        'x_min': min(x_coords),
                        'x_max': max(x_coords),
                        'y_min': min(y_coords),
                        'y_max': max(y_coords)
                    }
        return None
    
    def _get_tool_version(self) -> str:
        """Get version of the parsing tool being used"""
        if UNSTRUCTURED_AVAILABLE:
            try:
                import unstructured
                return getattr(unstructured, '__version__', 'unknown')
            except:
                return 'unknown'
        else:
            try:
                import pypdf
                return getattr(pypdf, '__version__', 'unknown')
            except:
                return 'unknown'

    def _parse_with_chapters(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Parse large PDF using chapter-based splitting to avoid unstructured.io hangs"""
        logger.info(f"Parsing large PDF with chapter-based approach: {pdf_path}")
        
        all_chunks = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                # Create 50-page chapters for better efficiency
                max_pages_per_chapter = 50
                num_chapters = (total_pages + max_pages_per_chapter - 1) // max_pages_per_chapter
                
                logger.info(f"Splitting {total_pages} pages into {num_chapters} chapters of ~{max_pages_per_chapter} pages each")
                try:
                    print(f"Starting Core Rulebook processing: {total_pages} pages → {num_chapters} chapters")
                except UnicodeEncodeError:
                    print(f"Starting Core Rulebook processing: {total_pages} pages -> {num_chapters} chapters")
                
                for chapter_idx in range(num_chapters):
                    start_page = (chapter_idx * max_pages_per_chapter) + 1
                    end_page = min((chapter_idx + 1) * max_pages_per_chapter, total_pages)
                    
                    try:
                        print(f"Processing chapter {chapter_idx + 1}/{num_chapters} (pages {start_page}-{end_page})")
                    except UnicodeEncodeError:
                        print(f"Processing chapter {chapter_idx + 1}/{num_chapters} (pages {start_page}-{end_page})", encoding='utf-8', errors='replace')
                    logger.info(f"Processing chapter {chapter_idx + 1}/{num_chapters} (pages {start_page}-{end_page})")
                    
                    # Extract text from chapter pages using pypdf
                    chapter_chunks = []
                    chunk_id_base = len(all_chunks)
                    
                    for page_num in range(start_page - 1, end_page):  # pypdf uses 0-based indexing
                        if (page_num - (start_page - 1)) % 10 == 0:
                            try:
                                print(f"  Page {page_num + 1}/{end_page} ({len(all_chunks)} chunks total)")
                            except UnicodeEncodeError:
                                print(f"  Page {page_num + 1}/{end_page} ({len(all_chunks)} chunks total)", encoding='utf-8', errors='replace')
                        
                        try:
                            page = pdf_reader.pages[page_num]
                            text = page.extract_text()
                            
                            if text.strip():
                                # Split large pages into smaller chunks
                                page_chunks = self._split_page_text(text, page_num + 1, chunk_id_base + len(chapter_chunks))
                                chapter_chunks.extend(page_chunks)
                        except Exception as e:
                            logger.warning(f"Error processing page {page_num + 1}: {e}")
                    
                    logger.info(f"Chapter {chapter_idx + 1} produced {len(chapter_chunks)} chunks")
                    all_chunks.extend(chapter_chunks)
                
                logger.info(f"Chapter-based parsing complete: {len(all_chunks)} total chunks from {num_chapters} chapters")
                return all_chunks
                
        except Exception as e:
            logger.error(f"Chapter-based parsing failed: {e}")
            # Fallback to pypdf without chapters
            return self._parse_with_pypdf(pdf_path)
    
    def _get_section_info_for_page(self, page_num: int) -> Dict[str, Any]:
        """FR1-E1: Get section information for a given page"""
        section_info = {
            'section': 'main',
            'section_id': None,
            'section_title': None,
            'section_level': None,
            'parent_section_id': None
        }
        
        if self.document_outline:
            section_entry = self.toc_parser.get_section_for_page(self.document_outline, page_num)
            if section_entry:
                section_info.update({
                    'section': section_entry.title,
                    'section_id': section_entry.section_id,
                    'section_title': section_entry.title,
                    'section_level': section_entry.level,
                    'parent_section_id': section_entry.parent_id
                })
        
        return section_info
    
    def _split_page_text(self, text: str, page_num: int, base_chunk_id: int) -> List[Dict[str, Any]]:
        """Split page text into manageable chunks - FR1-E1 Enhanced with section-aware chunking"""
        chunks = []
        max_chunk_size = 2000
        
        # FR1-E1: Get section information for this page
        section_info = self._get_section_info_for_page(page_num)
        
        if len(text) <= max_chunk_size:
            # Small page, single chunk
            metadata = {
                'page': page_num,
                'section': section_info['section'],
                'chunk_type': 'text',
                'element_id': f'element_{base_chunk_id:03d}',
                # FR1-E1: Section-aware metadata
                'section_id': section_info['section_id'],
                'section_title': section_info['section_title'],
                'section_level': section_info['section_level'],
                'parent_section_id': section_info['parent_section_id']
            }
            
            chunks.append({
                'id': f'{self.job_id}_chunk_{base_chunk_id:03d}',
                'content': text,
                'metadata': metadata
            })
        else:
            # Large page, split by paragraphs
            paragraphs = text.split('\n\n')
            current_chunk = ''
            chunk_count = 0
            
            for para in paragraphs:
                if len(current_chunk + para) > max_chunk_size and current_chunk:
                    # Save current chunk with section-aware metadata
                    metadata = {
                        'page': page_num,
                        'section': section_info['section'],
                        'chunk_type': 'text',
                        'element_id': f'element_{base_chunk_id + chunk_count:03d}',
                        # FR1-E1: Section-aware metadata
                        'section_id': section_info['section_id'],
                        'section_title': section_info['section_title'],
                        'section_level': section_info['section_level'],
                        'parent_section_id': section_info['parent_section_id']
                    }
                    
                    chunks.append({
                        'id': f'{self.job_id}_chunk_{base_chunk_id + chunk_count:03d}',
                        'content': current_chunk.strip(),
                        'metadata': metadata
                    })
                    chunk_count += 1
                    current_chunk = para
                else:
                    current_chunk += '\n\n' + para if current_chunk else para
            
            # Add final chunk if exists
            if current_chunk.strip():
                metadata = {
                    'page': page_num,
                    'section': section_info['section'],
                    'chunk_type': 'text',
                    'element_id': f'element_{base_chunk_id + chunk_count:03d}',
                    # FR1-E1: Section-aware metadata
                    'section_id': section_info['section_id'],
                    'section_title': section_info['section_title'],
                    'section_level': section_info['section_level'],
                    'parent_section_id': section_info['parent_section_id']
                }
                
                chunks.append({
                    'id': f'{self.job_id}_chunk_{base_chunk_id + chunk_count:03d}',
                    'content': current_chunk.strip(),
                    'metadata': metadata
                })
        
        return chunks


async def run_pass_a(job_id: str, pdf_path: Path, output_dir: Path, env: str = None) -> PassAOutput:
    """
    Async wrapper for Pass A parsing.
    FR1-E1 Enhanced: Section-aware chunking with ToC/heading parser
    
    Args:
        job_id: Unique job identifier
        pdf_path: Path to input PDF file
        output_dir: Directory for output files
        env: Environment name for FR1 configuration
        
    Returns:
        PassAOutput with parsing results
    """
    parser = PassAParser(job_id, env)
    return parser.parse_pdf(pdf_path, output_dir)


def run_pass_a_sync(job_id: str, pdf_path: Path, output_dir: Path, env: str = None) -> PassAOutput:
    """
    Synchronous version for testing and simple use cases.
    FR1-E1 Enhanced: Section-aware chunking with ToC/heading parser
    
    Args:
        job_id: Unique job identifier  
        pdf_path: Path to input PDF file
        output_dir: Directory for output files
        env: Environment name for FR1 configuration
        
    Returns:
        PassAOutput with parsing results
    """
    parser = PassAParser(job_id, env)
    return parser.parse_pdf(pdf_path, output_dir)


if __name__ == "__main__":
    # Test with our fixture PDFs
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        pdf_file = Path(sys.argv[1])
    else:
        pdf_file = Path("test_fixtures/test_fixtures/dnd_character_creation.pdf")
    
    if not pdf_file.exists():
        print(f"PDF file not found: {pdf_file}")
        sys.exit(1)
    
    output_dir = Path("artifacts/test")
    
    try:
        result = run_pass_a_sync("test_job", pdf_file, output_dir)
        print(f"Pass A completed successfully!")
        print(f"Chunks created: {result.statistics['total_chunks']}")
        print(f"Processing time: {result.statistics['processing_time_ms']}ms")
        print(f"Output written to: {output_dir}")
        
    except Exception as e:
        print(f"Pass A failed: {e}")
        sys.exit(1)