import PyPDF2
import re
import logging
from typing import List, Dict, Any, Tuple
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFParser:
    """PDF parsing for TTRPG source materials"""
    
    def __init__(self):
        self.chunk_size_target = 300  # Target words per chunk
        self.chunk_overlap = 50       # Overlap words between chunks
    
    def parse_pdf(self, file_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse PDF and extract structured content
        Returns manifest with parsing results
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"PDF file not found: {file_path}")
            
            logger.info(f"Starting PDF parse: {path.name}")
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Basic info
                num_pages = len(pdf_reader.pages)
                
                # Extract page text
                pages = []
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text.strip():  # Only include pages with text
                        pages.append({
                            "page_num": page_num + 1,  # 1-indexed
                            "text": self._clean_text(text)
                        })
                
                # Create chunks
                chunks = self._create_chunks(pages, metadata)
                
                # Generate manifest
                manifest = {
                    "source_id": self._generate_source_id(metadata),
                    "file_path": str(path),
                    "pages_detected": num_pages,
                    "pages_with_text": len(pages),
                    "chunks": len(chunks),
                    "metadata": metadata,
                    "chunks_data": chunks
                }
                
                logger.info(f"Parsed {num_pages} pages, created {len(chunks)} chunks")
                return manifest
                
        except Exception as e:
            logger.error(f"PDF parsing failed: {e}")
            return {
                "error": str(e),
                "source_id": self._generate_source_id(metadata),
                "file_path": file_path,
                "chunks_data": []
            }
    
    def _generate_source_id(self, metadata: Dict[str, Any]) -> str:
        """Generate consistent source ID from metadata"""
        title = metadata.get("title", "unknown")
        system = metadata.get("system", "generic")
        year = metadata.get("copyright_date", "unknown")
        
        # Create readable ID
        clean_title = re.sub(r'[^a-zA-Z0-9]', '_', title.lower())
        clean_system = re.sub(r'[^a-zA-Z0-9]', '_', system.lower())
        
        return f"{clean_system}_{clean_title}_{year}"
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted PDF text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common PDF artifacts
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # Page numbers
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()
    
    def _create_chunks(self, pages: List[Dict], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create single-concept chunks from pages"""
        chunks = []
        source_id = self._generate_source_id(metadata)
        
        for page_data in pages:
            page_num = page_data["page_num"]
            text = page_data["text"]
            
            # Split by paragraphs first
            paragraphs = text.split('\n\n')
            
            current_chunk = ""
            current_word_count = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                para_words = len(para.split())
                
                # If paragraph alone exceeds target, create chunk and split it
                if para_words > self.chunk_size_target * 1.5:
                    # Save current chunk if exists
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk, page_num, source_id, len(chunks)
                        ))
                        current_chunk = ""
                        current_word_count = 0
                    
                    # Split large paragraph
                    sub_chunks = self._split_large_paragraph(para, page_num)
                    for sub_chunk in sub_chunks:
                        chunks.append(self._create_chunk(
                            sub_chunk, page_num, source_id, len(chunks)
                        ))
                
                # If adding paragraph would exceed target, save current chunk
                elif current_word_count + para_words > self.chunk_size_target:
                    if current_chunk:
                        chunks.append(self._create_chunk(
                            current_chunk, page_num, source_id, len(chunks)
                        ))
                        current_chunk = para
                        current_word_count = para_words
                
                # Otherwise add to current chunk
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para
                    current_word_count += para_words
            
            # Save final chunk for this page
            if current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk, page_num, source_id, len(chunks)
                ))
        
        return chunks
    
    def _split_large_paragraph(self, text: str, page_num: int) -> List[str]:
        """Split large paragraphs at sentence boundaries"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        sub_chunks = []
        current = ""
        
        for sentence in sentences:
            if len((current + " " + sentence).split()) > self.chunk_size_target:
                if current:
                    sub_chunks.append(current.strip())
                    current = sentence
                else:
                    # Very long sentence, force split
                    sub_chunks.append(sentence[:1000] + "...")
            else:
                if current:
                    current += " " + sentence
                else:
                    current = sentence
        
        if current:
            sub_chunks.append(current.strip())
        
        return sub_chunks
    
    def _create_chunk(self, text: str, page_num: int, source_id: str, chunk_index: int) -> Dict[str, Any]:
        """Create a standardized chunk object"""
        chunk_id = f"{source_id}_chunk_{chunk_index:04d}"
        
        # Extract section hints from text
        section, subsection = self._extract_section_hints(text)
        
        return {
            "id": chunk_id,
            "text": text,
            "page": page_num,
            "source_id": source_id,
            "section": section,
            "subsection": subsection,
            "word_count": len(text.split()),
            "metadata": {
                "chunk_index": chunk_index,
                "extraction_method": "paragraph_boundary"
            }
        }
    
    def _extract_section_hints(self, text: str) -> Tuple[str, str]:
        """Extract section/subsection hints from chunk text"""
        lines = text.split('\n')
        section = ""
        subsection = ""
        
        # Look for headings in first few lines
        for i, line in enumerate(lines[:3]):
            line = line.strip()
            
            # Chapter/section patterns
            if re.match(r'^(CHAPTER|Chapter|Section|SECTION)\s+\d+', line):
                section = line
                break
            
            # Bold/caps pattern (common in RPG books)
            if len(line) < 100 and (line.isupper() or line.count(' ') <= 4):
                if not section:
                    section = line
                else:
                    subsection = line
                    break
        
        return section, subsection