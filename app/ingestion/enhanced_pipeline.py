#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTRPG Center - Enhanced Three-Pass Ingestion Pipeline
====================================================

Enhanced ingestion pipeline that combines the existing TTRPG Center infrastructure
with advanced three-pass processing inspired by the suggested data_ingestion module.

Pass 1: Parse & Normalize
  - Loads PDF/Markdown/Text using existing PDFParser
  - Extracts page text with improved section detection
  - Normalizes whitespace and basic cleaning

Pass 2: Chunk & Annotate  
  - Produces optimized chunks with rich metadata
  - Merges tiny paragraphs and splits oversized content
  - Builds comprehensive section paths and tags

Pass 3: Enrich, Embed & Persist
  - Optional LLM enrichment via existing services
  - Embeds chunks via existing embedding service
  - Persists to AstraDB via existing vector store
"""
import logging
import time
import json
import os
import re
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# Import existing TTRPG Center infrastructure
from .pdf_parser import PDFParser
from .dictionary import get_dictionary
from app.common.embeddings import get_embedding_service
from app.common.astra_client import get_vector_store
from app.common.config import load_config

logger = logging.getLogger(__name__)

# Configuration constants
TARGET_TOKENS = 320       # Target paragraph-sized chunks for RAG
MIN_TOKENS = 120          # Minimum chunk size
MAX_TOKENS = 480          # Maximum chunk size  
TOKEN_APPROX_RATIO = 4.0  # Approximate tokens = len(text)/4
ENRICH_MAX_WORKERS = 6    # Concurrent enrichment workers

@contextmanager
def enhanced_ingestion_lock(env: str = "dev"):
    """Enhanced ingestion lock with better error handling"""
    lock_dir = Path("./locks")
    lock_dir.mkdir(exist_ok=True) 
    lock_file = lock_dir / f"enhanced_ingestion_{env}.lock"
    
    try:
        with open(lock_file, 'w') as f:
            if os.name == 'nt':  # Windows
                import msvcrt
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    logger.info(f"Acquired enhanced ingestion lock for environment: {env}")
                    yield
                finally:
                    try:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                        logger.info(f"Released enhanced ingestion lock for environment: {env}")
                    except:
                        pass
            else:  # Unix-like systems
                import fcntl
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    logger.info(f"Acquired enhanced ingestion lock for environment: {env}")
                    yield
                finally:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        logger.info(f"Released enhanced ingestion lock for environment: {env}")
                    except:
                        pass
    except (IOError, OSError) as e:
        logger.error(f"Could not acquire enhanced ingestion lock for {env}: {e}")
        raise RuntimeError(f"Another enhanced ingestion process is running for environment {env}")
    finally:
        try:
            if lock_file.exists():
                lock_file.unlink()
        except:
            pass

# Enhanced data models
@dataclass
class PageBlock:
    """Represents a page of content with metadata"""
    page_number: int
    text: str
    metadata: Optional[Dict[str, Any]] = None

@dataclass  
class Section:
    """Represents a document section with hierarchical path"""
    title: str
    page_number: int
    level: int  # 1 = top-level, 2 = subsection, etc.
    path: List[str]  # Full hierarchical path
    content_start: Optional[int] = None
    content_end: Optional[int] = None

@dataclass
class EnhancedChunk:
    """Enhanced chunk model with comprehensive metadata"""
    chunk_id: str
    book_title: str
    system: Optional[str]
    edition: Optional[str] 
    source_path: str
    content: str
    page_start: int
    page_end: int
    section_path: List[str]
    section_title: str
    created_at: str
    content_hash: str
    char_count: int
    token_estimate: int
    chunk_index: int
    chunk_count: int
    tags: List[str]
    language: str = "en"
    enrichment: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None
    
    def to_vector_doc(self) -> Dict[str, Any]:
        """Convert to AstraDB document format"""
        return {
            "_id": self.chunk_id,
            "text": self.content,  # Map to existing schema
            "page": self.page_start,  # Map to existing schema
            "source_id": self.content_hash,  # Map to existing schema
            "section": self.section_title,
            "subsection": "/".join(self.section_path),
            "book_title": self.book_title,
            "system": self.system,
            "edition": self.edition,
            "source_path": self.source_path,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_path": self.section_path,
            "created_at": self.created_at,
            "content_hash": self.content_hash,
            "char_count": self.char_count,
            "token_estimate": self.token_estimate,
            "chunk_index": self.chunk_index,
            "chunk_count": self.chunk_count,
            "tags": self.tags,
            "language": self.language,
            "enrichment": self.enrichment or {},
            "$vector": self.embedding,
            "metadata": {
                "ingestion_version": "enhanced_v1",
                "processing_timestamp": self.created_at
            }
        }

class EnhancedDocumentLoader:
    """Enhanced document loader with better text extraction"""
    
    def __init__(self, pdf_parser: PDFParser):
        self.pdf_parser = pdf_parser
        
    def load(self, file_path: str) -> List[PageBlock]:
        """Load document into page blocks"""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == '.pdf':
            return self._load_pdf(path)
        elif suffix in ['.md', '.markdown']:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return self._text_to_pages(text, "markdown")
        elif suffix == '.txt':
            text = path.read_text(encoding="utf-8", errors="ignore") 
            return self._text_to_pages(text, "text")
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
    
    def _load_pdf(self, path: Path) -> List[PageBlock]:
        """Load PDF using existing PDFParser"""
        result = self.pdf_parser.extract_text(str(path))
        if not result.get("success", False):
            raise ValueError(f"PDF parsing failed: {result.get('error', 'Unknown error')}")
        
        pages = []
        page_texts = result.get("pages", [])
        for i, page_text in enumerate(page_texts, start=1):
            normalized = self._normalize_whitespace(page_text)
            pages.append(PageBlock(
                page_number=i,
                text=normalized,
                metadata={"extraction_method": "pypdf2"}
            ))
        return pages
    
    def _text_to_pages(self, text: str, format_type: str) -> List[PageBlock]:
        """Convert text to page blocks"""
        normalized = self._normalize_whitespace(text)
        return [PageBlock(
            page_number=1,
            text=normalized,
            metadata={"format": format_type, "extraction_method": "direct"}
        )]
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace and fix common PDF artifacts"""
        # Basic cleanup
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        # Fix hyphenated line breaks common in PDFs
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        
        # Collapse space before punctuation
        text = re.sub(r"\s+([,;:.!?])", r"\1", text)
        
        return text.strip()

class EnhancedSectionDetector:
    """Enhanced section detection with better heuristics"""
    
    def detect(self, pages: List[PageBlock]) -> List[Tuple[PageBlock, List[Section]]]:
        """Detect sections across all pages"""
        result = []
        current_path: List[str] = []
        
        for page in pages:
            sections_on_page = []
            lines = page.text.split("\n")
            
            for line_num, line in enumerate(lines):
                if self._is_probable_heading(line):
                    level = self._infer_level(line)
                    title = self._clean_heading(line)
                    
                    # Update hierarchical path
                    current_path = current_path[:level-1]
                    current_path.append(title)
                    
                    section = Section(
                        title=title,
                        page_number=page.page_number,
                        level=level,
                        path=current_path.copy(),
                        content_start=line_num
                    )
                    sections_on_page.append(section)
            
            result.append((page, sections_on_page))
        
        return result
    
    def _is_probable_heading(self, line: str) -> bool:
        """Improved heading detection for TTRPG content"""
        s = line.strip()
        if not s:
            return False
            
        # Markdown headings
        if s.startswith("#"):
            return True
            
        # ALL CAPS sections (common in RPG books)
        if len(s) < 80 and s.isupper() and re.search(r"[A-Z]", s):
            return True
            
        # Title Case without trailing punctuation
        if (len(s) < 80 and 
            re.match(r"^[A-Z][A-Za-z0-9 ,''():/-]+$", s) and 
            not s.endswith(".") and
            not re.search(r"\d+\s*$", s)):  # Exclude page numbers
            return True
            
        return False
    
    def _infer_level(self, line: str) -> int:
        """Infer heading level from line formatting"""
        if line.strip().startswith("#"):
            return max(1, min(6, line.count("#")))
        
        s = line.strip()
        # Heuristics for level based on length and formatting
        if len(s) < 25:
            return 2
        return 1
    
    def _clean_heading(self, line: str) -> str:
        """Clean heading text"""
        return re.sub(r"^#+\s*", "", line).strip()

class EnhancedChunker:
    """Enhanced chunking with optimal sizing and metadata"""
    
    def __init__(self, book_title: str, system: Optional[str], edition: Optional[str]):
        self.book_title = book_title
        self.system = system 
        self.edition = edition
    
    def chunk(self, file_path: str, pages_with_sections: List[Tuple[PageBlock, List[Section]]]) -> List[EnhancedChunk]:
        """Create optimized chunks with rich metadata"""
        # Extract raw chunks with section context
        raw_chunks = self._extract_raw_chunks(pages_with_sections)
        
        # Merge small chunks and split large ones
        optimized_chunks = self._optimize_chunk_sizes(raw_chunks)
        
        # Convert to EnhancedChunk objects
        return self._create_chunk_objects(file_path, optimized_chunks)
    
    def _extract_raw_chunks(self, pages_with_sections: List[Tuple[PageBlock, List[Section]]]) -> List[Tuple[str, int, int, List[str], str]]:
        """Extract raw text chunks with section context"""
        current_section_path = []
        raw_chunks = []
        
        for page, sections_on_page in pages_with_sections:
            # Update current section based on page
            for section in sections_on_page:
                current_section_path = section.path
            
            section_title = current_section_path[-1] if current_section_path else ""
            
            # Split into paragraphs
            paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
            
            for para in paragraphs:
                raw_chunks.append((
                    para, 
                    page.page_number, 
                    page.page_number,
                    current_section_path.copy(),
                    section_title
                ))
        
        return raw_chunks
    
    def _optimize_chunk_sizes(self, raw_chunks: List[Tuple[str, int, int, List[str], str]]) -> List[Tuple[str, int, int, List[str], str]]:
        """Optimize chunk sizes by merging small and splitting large chunks"""
        # First pass: merge small chunks within same section
        merged = []
        buffer = {"text": "", "start": None, "end": None, "path": [], "title": ""}
        
        def flush_buffer():
            if buffer["text"].strip():
                merged.append((
                    buffer["text"].strip(),
                    buffer["start"] or 0,
                    buffer["end"] or 0,
                    buffer["path"],
                    buffer["title"]
                ))
            buffer.update({"text": "", "start": None, "end": None, "path": [], "title": ""})
        
        for text, pstart, pend, spath, stitle in raw_chunks:
            if not buffer["text"]:
                # Start new buffer
                buffer.update({
                    "text": text,
                    "start": pstart, 
                    "end": pend,
                    "path": spath,
                    "title": stitle
                })
            else:
                # Check if we should merge or flush
                if (self._approx_tokens(buffer["text"]) < MIN_TOKENS and 
                    spath == buffer["path"]):
                    # Merge with buffer
                    buffer["text"] += "\n\n" + text
                    buffer["end"] = pend
                else:
                    # Flush buffer and start new one
                    flush_buffer()
                    buffer.update({
                        "text": text,
                        "start": pstart,
                        "end": pend, 
                        "path": spath,
                        "title": stitle
                    })
        
        flush_buffer()
        
        # Second pass: split oversized chunks
        final_chunks = []
        for content, pstart, pend, spath, stitle in merged:
            if self._approx_tokens(content) <= MAX_TOKENS:
                final_chunks.append((content, pstart, pend, spath, stitle))
            else:
                # Split by sentences
                sentences = re.split(r"(?<=[.!?])\s+", content)
                current = ""
                current_start = pstart
                
                for sentence in sentences:
                    candidate = (current + " " + sentence).strip() if current else sentence
                    if self._approx_tokens(candidate) > TARGET_TOKENS and current:
                        final_chunks.append((current, current_start, pend, spath, stitle))
                        current = sentence
                        current_start = pstart
                    else:
                        current = candidate
                
                if current:
                    final_chunks.append((current, pstart, pend, spath, stitle))
        
        return final_chunks
    
    def _create_chunk_objects(self, file_path: str, chunks: List[Tuple[str, int, int, List[str], str]]) -> List[EnhancedChunk]:
        """Convert raw chunks to EnhancedChunk objects"""
        created_at = datetime.now(timezone.utc).isoformat()
        file_hash = self._file_sha256(Path(file_path))
        chunk_objects = []
        total = len(chunks)
        
        for idx, (content, pstart, pend, spath, stitle) in enumerate(chunks):
            chunk_id = f"{file_hash}::{idx:06d}"
            content_hash = self._text_sha256(content)
            
            chunk_obj = EnhancedChunk(
                chunk_id=chunk_id,
                book_title=self.book_title,
                system=self.system,
                edition=self.edition,
                source_path=file_path,
                content=content,
                page_start=pstart,
                page_end=pend,
                section_path=spath,
                section_title=stitle,
                created_at=created_at,
                content_hash=content_hash,
                char_count=len(content),
                token_estimate=self._approx_tokens(content),
                chunk_index=idx,
                chunk_count=total,
                tags=self._infer_tags(spath, stitle, content)
            )
            chunk_objects.append(chunk_obj)
        
        return chunk_objects
    
    def _approx_tokens(self, text: str) -> int:
        """Approximate token count"""
        return max(1, int(len(text) / TOKEN_APPROX_RATIO))
    
    def _file_sha256(self, path: Path) -> str:
        """Calculate file SHA256"""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    
    def _text_sha256(self, text: str) -> str:
        """Calculate text SHA256"""
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    
    def _infer_tags(self, section_path: List[str], section_title: str, content: str) -> List[str]:
        """Infer TTRPG-specific tags from content"""
        tags = []
        blob = (section_title + " " + " ".join(section_path) + " " + content[:500]).lower()
        
        # TTRPG content tags
        ttrpg_patterns = {
            "feat": r"\bfeat(s)?\b",
            "spell": r"\bspell(s)?\b", 
            "class": r"\bclass(es)?\b",
            "ancestry": r"\bancestr(y|ies)\b",
            "monster": r"\bmonster(s)?\b|\bcreature(s)?\b|\bstatblock\b",
            "item": r"\bitem(s)?\b|\bequipment\b",
            "lore": r"\blore\b|\bsetting\b|\bworld\b",
            "rules": r"\brule(s)?\b|\bmechanic(s)?\b|\bDC\b|\battack\b|\bproficiency\b"
        }
        
        for tag, pattern in ttrpg_patterns.items():
            if re.search(pattern, blob):
                tags.append(tag)
        
        return sorted(set(tags))

class EnhancedIngestionPipeline:
    """Enhanced three-pass ingestion pipeline"""
    
    def __init__(self):
        # Use existing infrastructure
        self.pdf_parser = PDFParser()
        self.dictionary = get_dictionary()
        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store()
        self.config = load_config()
        
        # Enhanced components
        self.loader = EnhancedDocumentLoader(self.pdf_parser)
        self.section_detector = EnhancedSectionDetector()
    
    def ingest_file(self, 
                   file_path: str,
                   metadata: Dict[str, Any],
                   progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Enhanced three-pass file ingestion"""
        ingestion_id = f"enh_{str(uuid.uuid4())[:8]}"
        start_time = time.time()
        
        logger.info(f"Starting enhanced ingestion {ingestion_id} for {Path(file_path).name}")
        
        def update_progress(phase: str, step: str, progress: float = 0.0, details: Dict[str, Any] = None):
            if progress_callback:
                progress_callback({
                    "ingestion_id": ingestion_id,
                    "phase": phase,
                    "step": step,
                    "progress": progress,
                    "timestamp": time.time(),
                    "details": details or {}
                })
        
        try:
            # Extract metadata parameters
            book_title = metadata.get("book_title", Path(file_path).stem)
            system = metadata.get("system")
            edition = metadata.get("edition")
            
            chunker = EnhancedChunker(book_title, system, edition)
            
            # PASS 1: Parse & Normalize
            update_progress("Pass 1", "Loading document", 5.0)
            pages = self.loader.load(file_path)
            
            update_progress("Pass 1", "Detecting sections", 15.0)
            pages_with_sections = self.section_detector.detect(pages)
            
            update_progress("Pass 1", "Parse complete", 25.0, {
                "pages": len(pages),
                "sections": sum(len(secs) for _, secs in pages_with_sections)
            })
            
            # PASS 2: Chunk & Annotate
            update_progress("Pass 2", "Creating optimized chunks", 35.0)
            chunks = chunker.chunk(file_path, pages_with_sections)
            
            update_progress("Pass 2", "Chunk creation complete", 50.0, {
                "chunks": len(chunks),
                "avg_tokens": sum(c.token_estimate for c in chunks) // len(chunks) if chunks else 0
            })
            
            # PASS 3: Enrich, Embed & Persist
            update_progress("Pass 3", "Generating embeddings", 60.0)
            self._add_embeddings(chunks, update_progress)
            
            update_progress("Pass 3", "Persisting to vector store", 85.0)
            self._persist_chunks(chunks)
            
            # Update dictionary with extracted terms
            update_progress("Pass 3", "Updating dictionary", 95.0)
            self._update_dictionary(chunks)
            
            duration = time.time() - start_time
            update_progress("Complete", "Ingestion successful", 100.0)
            
            # Create manifest
            manifest = {
                "ingestion_id": ingestion_id,
                "status": "completed",
                "file_path": file_path,
                "book_title": book_title,
                "system": system,
                "edition": edition,
                "pages_processed": len(pages),
                "chunks_created": len(chunks),
                "duration_seconds": duration,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pipeline_version": "enhanced_v1"
            }
            
            logger.info(f"Enhanced ingestion {ingestion_id} completed in {duration:.2f}s - {len(chunks)} chunks")
            return manifest
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Enhanced ingestion {ingestion_id} failed: {e}")
            update_progress("Error", f"Ingestion failed: {str(e)}", 0.0)
            
            return {
                "ingestion_id": ingestion_id,
                "status": "failed",
                "error": str(e),
                "duration_seconds": duration,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
    
    def _add_embeddings(self, chunks: List[EnhancedChunk], update_progress: callable):
        """Add embeddings to chunks using existing service"""
        batch_size = 32  # Optimize for API limits
        total = len(chunks)
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk.content for chunk in batch]
            
            try:
                # Use existing embedding service
                embeddings = self.embedding_service.get_embeddings(texts)
                
                # Assign embeddings to chunks
                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = embedding
                    
                progress = 60.0 + (25.0 * (i + len(batch)) / total)
                update_progress("Pass 3", f"Embedded {i + len(batch)}/{total} chunks", progress)
                
            except Exception as e:
                logger.warning(f"Embedding batch {i//batch_size + 1} failed: {e}")
                # Continue without embeddings for this batch
    
    def _persist_chunks(self, chunks: List[EnhancedChunk]):
        """Persist chunks to vector store using existing infrastructure"""
        # Convert to format expected by existing vector store
        docs = [chunk.to_vector_doc() for chunk in chunks]
        
        # Use existing vector store's insert method
        result = self.vector_store.insert_chunks(docs)
        
        if result.get("errors"):
            logger.warning(f"Some chunks failed to persist: {result['errors']}")
        
        logger.info(f"Persisted {result.get('inserted', 0)} chunks to vector store")
    
    def _update_dictionary(self, chunks: List[EnhancedChunk]):
        """Update dictionary with terms from chunks"""
        try:
            # Extract terms from chunk content and tags
            terms = []
            for chunk in chunks:
                # Add section titles as terms
                if chunk.section_title:
                    terms.append(chunk.section_title)
                
                # Add tags as terms
                terms.extend(chunk.tags)
            
            # Update dictionary via existing service
            if hasattr(self.dictionary, 'add_terms'):
                self.dictionary.add_terms(terms)
                
        except Exception as e:
            logger.warning(f"Dictionary update failed: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Enhanced health check"""
        checks = {
            "pdf_parser": "healthy" if self.pdf_parser else "unavailable",
            "dictionary": "healthy" if self.dictionary else "unavailable", 
            "embedding_service": "healthy" if self.embedding_service else "unavailable",
            "vector_store": "healthy" if self.vector_store else "unavailable"
        }
        
        # Test vector store connection
        if self.vector_store:
            try:
                vs_health = self.vector_store.health_check()
                checks["vector_store"] = vs_health.get("status", "unknown")
            except Exception as e:
                checks["vector_store"] = f"error: {str(e)}"
        
        overall_status = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
        
        return {
            "status": overall_status,
            "components": checks,
            "pipeline_version": "enhanced_v1",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Global instance
_enhanced_pipeline = None

def get_enhanced_pipeline() -> EnhancedIngestionPipeline:
    """Get global enhanced pipeline instance"""
    global _enhanced_pipeline
    if _enhanced_pipeline is None:
        _enhanced_pipeline = EnhancedIngestionPipeline()
    return _enhanced_pipeline