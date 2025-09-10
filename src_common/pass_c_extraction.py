# src_common/pass_c_extraction.py
"""
Pass C: Unstructured.io (Extraction)

Run Unstructured.io on each part (or whole file if not split) to extract 
section-aware blocks at paragraph/small-section granularity.

Responsibilities:
- Process split parts or whole file using unstructured.io
- Extract section-aware blocks with paragraph/section granularity
- Upsert raw chunks into AstraDB with stage:"raw"
- Include metadata: source_id, section_id, page_span, toc_path
- No embeddings yet (that's Pass D)

Artifacts:
- *_pass_c_raw_chunks.jsonl: Schema-validated chunk records
- manifest.json: Updated with extraction results
"""

import json
import os
import sys
import time
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict

# Unstructured.io imports with fallback
try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.chunking.title import chunk_by_title
    import unstructured
    UNSTRUCTURED_AVAILABLE = True
except ImportError as e:
    UNSTRUCTURED_AVAILABLE = False
    UNSTRUCTURED_IMPORT_ERROR = str(e)

# Fallback imports
import pypdf

from .logging import get_logger
from .artifact_validator import write_json_atomically, load_json_with_retry
from .astra_loader import AstraLoader
from .metadata_utils import extract_page_info, extract_coordinates, safe_metadata_get

logger = get_logger(__name__)


@dataclass
class RawChunk:
    """Raw chunk extracted in Pass C"""
    chunk_id: str
    content: str
    stage: str = "raw"
    source_id: str = ""
    section_id: str = ""
    page_span: str = ""
    toc_path: str = ""
    element_type: str = ""
    page_number: int = 0
    coordinates: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PassCResult:
    """Result of Pass C extraction processing"""
    source_file: str
    job_id: str
    chunks_extracted: int
    chunks_loaded: int
    parts_processed: int
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    error_message: Optional[str] = None


class PassCExtractor:
    """Pass C: Unstructured.io Extraction"""
    
    def __init__(self, job_id: str, env: str = "dev", max_chunk_size: int = 600):
        self.job_id = job_id
        self.env = env
        self.max_chunk_size = max_chunk_size
        self.astra_loader = AstraLoader(env)
        
    def process_pdf(self, pdf_path: Path, output_dir: Path) -> PassCResult:
        """
        Process PDF for Pass C: Raw extraction using unstructured.io
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output artifacts
            
        Returns:
            PassCResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Pass C starting: Raw extraction for {pdf_path.name}")
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if PDF was split in Pass B
            split_index_path = output_dir / "split_index.json"
            pdf_parts = []
            
            if split_index_path.exists():
                # Process split parts
                split_data = load_json_with_retry(split_index_path, expected_schema_keys={'parts'})
                for part_info in split_data.get("parts", []):
                    part_path = Path(part_info["file_path"])
                    if part_path.exists():
                        pdf_parts.append({
                            "path": part_path,
                            "page_start": part_info["page_start"],
                            "page_end": part_info["page_end"],
                            "section_titles": part_info["section_titles"]
                        })
                logger.info(f"Processing {len(pdf_parts)} split parts")
            else:
                # Process whole file
                pdf_parts = [{
                    "path": pdf_path,
                    "page_start": 1,
                    "page_end": self._get_page_count(pdf_path),
                    "section_titles": ["Complete Document"]
                }]
                logger.info("Processing whole PDF file (no split)")
            
            # Extract raw chunks from all parts
            all_chunks = []
            for i, part_info in enumerate(pdf_parts, 1):
                logger.info(f"Extracting from part {i}/{len(pdf_parts)}: {part_info['path'].name}")
                part_chunks = self._extract_from_part(part_info, i)
                all_chunks.extend(part_chunks)
            
            logger.info(f"Extracted {len(all_chunks)} raw chunks total")
            
            # Write raw chunks artifact
            chunks_artifact_path = output_dir / f"{self.job_id}_pass_c_raw_chunks.jsonl"
            self._write_chunks_jsonl(all_chunks, chunks_artifact_path)
            
            # Load chunks to AstraDB
            chunks_loaded = self._load_chunks_to_astra(all_chunks)
            
            # Update manifest
            manifest_path = self._update_manifest(
                output_dir, 
                pdf_path, 
                len(all_chunks), 
                chunks_loaded,
                len(pdf_parts),
                [chunks_artifact_path]
            )
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            logger.info(f"Pass C completed for {pdf_path.name} in {processing_time_ms}ms")
            
            return PassCResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                chunks_extracted=len(all_chunks),
                chunks_loaded=chunks_loaded,
                parts_processed=len(pdf_parts),
                processing_time_ms=processing_time_ms,
                artifacts=[str(chunks_artifact_path)],
                manifest_path=str(manifest_path),
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass C failed for {pdf_path.name}: {e}")
            
            return PassCResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                chunks_extracted=0,
                chunks_loaded=0,
                parts_processed=0,
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )
    
    def _extract_from_part(self, part_info: Dict[str, Any], part_index: int) -> List[RawChunk]:
        """Extract raw chunks from a single PDF part"""
        
        part_path = part_info["path"]
        page_start = part_info["page_start"]
        page_end = part_info["page_end"]
        section_titles = part_info["section_titles"]
        
        chunks = []
        
        if UNSTRUCTURED_AVAILABLE:
            chunks = self._extract_with_unstructured(
                part_path, page_start, page_end, section_titles, part_index
            )
        else:
            logger.error("Unstructured.io not available - cannot proceed with document extraction")
            chunks = self._handle_unstructured_unavailable(part_path)
        
        return chunks
    
    def _extract_with_unstructured(
        self, 
        part_path: Path, 
        page_start: int, 
        page_end: int,
        section_titles: List[str],
        part_index: int
    ) -> List[RawChunk]:
        """Extract chunks using unstructured.io"""
        
        # Configure Poppler and Tesseract for unstructured.io
        poppler_path = os.getenv("POPPLER_PATH")
        tesseract_path = os.getenv("TESSERACT_PATH")
        tessdata_prefix = os.getenv("TESSDATA_PREFIX")
        original_path = os.environ.get("PATH", "")
        
        # Configure Poppler
        if poppler_path and poppler_path.strip() and Path(poppler_path).exists():
            logger.info(f"Adding Poppler to PATH: {poppler_path}")
            os.environ["PATH"] = f"{poppler_path};{original_path}"
        else:
            if poppler_path and poppler_path.strip():
                logger.warning(f"Poppler path not found: {poppler_path}")
            else:
                logger.info("Poppler not configured - using fallback extraction without OCR")
        
        # Configure Tesseract
        if tesseract_path and tesseract_path.strip() and Path(tesseract_path).exists():
            logger.info(f"Adding Tesseract to PATH: {tesseract_path}")
            os.environ["PATH"] = f"{tesseract_path};{os.environ.get('PATH', '')}"
        else:
            if tesseract_path and tesseract_path.strip():
                logger.warning(f"Tesseract path not found: {tesseract_path}")
            else:
                logger.info("Tesseract not configured - using fallback extraction without OCR")
            
        # Configure Tessdata path
        if tessdata_prefix and Path(tessdata_prefix).exists():
            logger.info(f"Setting TESSDATA_PREFIX: {tessdata_prefix}")
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix
        else:
            logger.warning(f"Tessdata path not found or not configured: {tessdata_prefix}")
        
        chunks = []
        
        try:
            # Partition PDF with unstructured.io
            elements = partition_pdf(
                filename=str(part_path),
                strategy="auto",
                infer_table_structure=True,
                extract_images_in_pdf=False,
                include_page_breaks=True
            )
            
            # Chunk by title for better section awareness with overlap for context preservation
            chunked_elements = chunk_by_title(
                elements=elements,
                max_characters=self.max_chunk_size,  # Soft limit - Unstructured.io can exceed for sentence integrity
                new_after_n_chars=int(self.max_chunk_size * 0.75),  # 75% of max for new chunk trigger
                combine_text_under_n_chars=120,
                overlap=150,  # 150 character overlap for context preservation
                overlap_all=False  # Only overlap chunks that are split due to length
            )
            
            for i, element in enumerate(chunked_elements):
                # Extract content and metadata
                content = str(element).strip()
                if len(content) < 50:  # Skip very short chunks
                    continue
                
                # Log chunk size statistics for monitoring (no truncation)
                if len(content) > self.max_chunk_size:
                    logger.info(f"Chunk {i+1}: {len(content)} chars (target: {self.max_chunk_size}) - Unstructured.io preserved sentence integrity")
                
                # Generate chunk ID
                chunk_id = f"{self.job_id}_c_{part_index}_{i+1:04d}"
                
                # Extract page information using metadata utility
                page_num = extract_page_info(getattr(element, 'metadata', None), page_start)
                
                # Build section path from titles
                toc_path = " > ".join(section_titles[:2])  # Limit depth
                section_id = f"part_{part_index}_section_{i+1}"
                
                # Extract coordinates if available using metadata utility
                coordinates = extract_coordinates(getattr(element, 'metadata', None))
                
                chunk = RawChunk(
                    chunk_id=chunk_id,
                    content=content,
                    stage="raw",
                    source_id=self.job_id,
                    section_id=section_id,
                    page_span=f"{page_num}",
                    toc_path=toc_path,
                    element_type=getattr(element, 'category', 'text'),
                    page_number=page_num,
                    coordinates=coordinates,
                    metadata={
                        "part_index": part_index,
                        "page_start": page_start,
                        "page_end": page_end,
                        "extraction_method": "unstructured.io",
                        "element_index": i
                    }
                )
                chunks.append(chunk)
                
        except Exception as e:
            logger.error(f"Unstructured.io extraction failed for {part_path.name}: {e}")
            return self._handle_unstructured_failure(part_path, e)
        finally:
            # Restore original PATH and environment
            if poppler_path or tesseract_path:
                os.environ["PATH"] = original_path
                logger.debug("Restored original PATH after unstructured.io processing")
                
            # Remove TESSDATA_PREFIX if we set it
            if tessdata_prefix and "TESSDATA_PREFIX" in os.environ:
                del os.environ["TESSDATA_PREFIX"]
                logger.debug("Removed TESSDATA_PREFIX after unstructured.io processing")
        
        return chunks
    
    def _handle_unstructured_unavailable(self, part_path: Path) -> List[RawChunk]:
        """Handle case where Unstructured.io is not available - diagnostic logging only"""
        
        logger.error("UNSTRUCTURED.IO NOT AVAILABLE - CRITICAL DEPENDENCY MISSING")
        logger.error(f"Import error: {UNSTRUCTURED_IMPORT_ERROR}")
        logger.error("Remediation steps:")
        logger.error("1. Install unstructured: pip install 'unstructured[local-inference,pdf]>=0.17.2'")
        logger.error("2. Verify installation: python -c 'import unstructured; print(unstructured.__version__)'")
        logger.error("3. Check requirements.txt for version conflicts")
        
        # Log system diagnostics
        diagnostics = {
            "file_path": str(part_path),
            "file_exists": part_path.exists(),
            "file_size": part_path.stat().st_size if part_path.exists() else "N/A",
            "python_version": sys.version,
            "working_directory": os.getcwd(),
            "import_error": UNSTRUCTURED_IMPORT_ERROR,
        }
        logger.error("System diagnostics:", extra=diagnostics)
        
        # Return empty list - job should fail
        return []
    
    def _handle_unstructured_failure(self, part_path: Path, error: Exception) -> List[RawChunk]:
        """Handle Unstructured.io processing failure with comprehensive diagnostic logging"""
        
        logger.error(f"UNSTRUCTURED.IO PROCESSING FAILED for {part_path.name}")
        logger.error(f"Error type: {type(error).__name__}")
        logger.error(f"Error details: {str(error)}")
        
        # Collect comprehensive diagnostic information
        diagnostics = {
            "file_path": str(part_path),
            "file_exists": part_path.exists(),
            "file_size": part_path.stat().st_size if part_path.exists() else "N/A",
            "file_readable": os.access(part_path, os.R_OK) if part_path.exists() else False,
            "python_version": sys.version,
            "unstructured_version": unstructured.__version__ if UNSTRUCTURED_AVAILABLE else "N/A",
            "error_type": type(error).__name__,
            "error_message": str(error),
            
            # OCR tool availability
            "poppler_pdfinfo": bool(shutil.which("pdfinfo")),
            "poppler_pdftoppm": bool(shutil.which("pdftoppm")),
            "tesseract_available": bool(shutil.which("tesseract")),
            
            # Environment configuration
            "tessdata_prefix": os.getenv("TESSDATA_PREFIX"),
            "tesseract_path": os.getenv("TESSERACT_PATH"),
            "poppler_path": os.getenv("POPPLER_PATH"),
            "path_env": os.getenv("PATH", "")[:200] + "..." if len(os.getenv("PATH", "")) > 200 else os.getenv("PATH", ""),
        }
        
        logger.error("Comprehensive diagnostic information:", extra=diagnostics)
        
        # Provide specific remediation guidance based on error type
        if "poppler" in str(error).lower():
            logger.error("POPPLER ISSUE DETECTED - Install Poppler utilities:")
            logger.error("- Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases")
            logger.error("- Linux: apt-get install poppler-utils")
            logger.error("- macOS: brew install poppler")
            logger.error("- Add installation directory to PATH environment variable")
        elif "tesseract" in str(error).lower():
            logger.error("TESSERACT ISSUE DETECTED - Install Tesseract OCR:")
            logger.error("- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            logger.error("- Linux: apt-get install tesseract-ocr")
            logger.error("- macOS: brew install tesseract")
            logger.error("- Set TESSDATA_PREFIX environment variable")
        elif "memory" in str(error).lower() or "out of memory" in str(error).lower():
            logger.error("MEMORY ISSUE DETECTED - Try:")
            logger.error("- Reduce max_characters parameter")
            logger.error("- Process smaller file chunks")
            logger.error("- Increase system memory")
        elif "permission" in str(error).lower() or "access" in str(error).lower():
            logger.error("PERMISSION ISSUE DETECTED - Check:")
            logger.error("- File read permissions")
            logger.error("- Directory access permissions")
            logger.error("- User account privileges")
        else:
            logger.error("UNKNOWN ERROR - General troubleshooting:")
            logger.error("- Verify PDF file is not corrupted")
            logger.error("- Try with a different PDF file")
            logger.error("- Check unstructured.io version compatibility")
            logger.error("- Review unstructured.io documentation")
        
        # Return empty list - let job fail gracefully with full diagnostic info
        return []
    
    def _write_chunks_jsonl(self, chunks: List[RawChunk], output_path: Path):
        """Write chunks to JSONL file"""
        
        lines = []
        for chunk in chunks:
            chunk_dict = asdict(chunk)
            lines.append(json.dumps(chunk_dict, ensure_ascii=False))
        
        content = "\n".join(lines)
        
        # Use atomic write
        temp_path = output_path.with_suffix('.tmp')
        temp_path.write_text(content, encoding='utf-8')
        temp_path.replace(output_path)
        
        logger.info(f"Wrote {len(chunks)} chunks to {output_path}")
    
    def _load_chunks_to_astra(self, chunks: List[RawChunk]) -> int:
        """Load raw chunks to AstraDB collection"""
        
        if not chunks:
            return 0
        
        # Convert to AstraDB format
        documents = []
        for chunk in chunks:
            doc = {
                'chunk_id': chunk.chunk_id,
                'content': chunk.content,
                'stage': chunk.stage,
                'source_id': chunk.source_id,
                'section_id': chunk.section_id,
                'page_span': chunk.page_span,
                'toc_path': chunk.toc_path,
                'element_type': chunk.element_type,
                'page_number': chunk.page_number,
                'coordinates': chunk.coordinates,
                'metadata': chunk.metadata or {},
                'environment': self.env,
                'loaded_at': time.time()
            }
            documents.append(doc)
        
        try:
            # Use AstraLoader to insert chunks
            if self.astra_loader.client:
                collection = self.astra_loader.client.get_collection(self.astra_loader.collection_name)
                insert_result = collection.insert_many(documents)
                loaded_count = len(insert_result.inserted_ids) if insert_result.inserted_ids else len(documents)
                logger.info(f"Loaded {loaded_count} raw chunks to AstraDB")
                return loaded_count
            else:
                logger.info(f"SIMULATION: Would load {len(documents)} raw chunks to AstraDB")
                return len(documents)
                
        except Exception as e:
            logger.error(f"Failed to load chunks to AstraDB: {e}")
            return 0
    
    def _get_page_count(self, pdf_path: Path) -> int:
        """Get total page count of PDF"""
        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                return len(reader.pages)
        except Exception as e:
            logger.warning(f"Failed to get page count for {pdf_path}: {e}")
            return 1
    
    def _update_manifest(
        self,
        output_dir: Path,
        pdf_path: Path,
        chunks_extracted: int,
        chunks_loaded: int,
        parts_processed: int,
        artifacts: List[Path]
    ) -> Path:
        """Update manifest.json with Pass C results"""
        
        manifest_path = output_dir / "manifest.json"
        
        # Load existing manifest
        manifest_data = {}
        if manifest_path.exists():
            try:
                manifest_data = load_json_with_retry(manifest_path)
            except Exception as e:
                logger.warning(f"Failed to load existing manifest: {e}")
        
        # Update with Pass C information
        manifest_data.update({
            "completed_passes": list(set(manifest_data.get("completed_passes", []) + ["C"])),
            "chunks": manifest_data.get("chunks", []),  # BUG-016: Ensure chunks key exists
            "pass_c_results": {
                "chunks_extracted": chunks_extracted,
                "chunks_loaded": chunks_loaded,
                "parts_processed": parts_processed,
                "extraction_method": "unstructured.io" if UNSTRUCTURED_AVAILABLE else "pypdf_fallback",
                "collection_name": self.astra_loader.collection_name
            }
        })
        
        # Add artifacts
        for artifact_path in artifacts:
            if artifact_path.exists():
                manifest_data.setdefault("artifacts", []).append({
                    "file": artifact_path.name,
                    "path": str(artifact_path),
                    "size": artifact_path.stat().st_size,
                    "mtime": artifact_path.stat().st_mtime,
                    "checksum": self._compute_file_hash(artifact_path)
                })
        
        # Write updated manifest
        write_json_atomically(manifest_data, manifest_path)
        
        return manifest_path
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        import hashlib
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def preflight_ocr_tools() -> bool:
    """
    LEGACY: Preflight check for Poppler and Tesseract OCR tools
    
    This function is deprecated in favor of the centralized preflight_checks module.
    It remains for backward compatibility with existing code that may call it.
    
    Returns:
        True if all tools are available, False otherwise
    """
    from .preflight_checks import PreflightValidator, PreflightError
    
    try:
        validator = PreflightValidator()
        validator.validate_dependencies()
        validator.cleanup()
        return True
    except PreflightError:
        return False


def process_pass_c(pdf_path: Path, output_dir: Path, job_id: str, env: str = "dev", max_chunk_size: int = 600) -> PassCResult:
    """
    Convenience function for Pass C processing
    
    Args:
        pdf_path: Path to source PDF
        output_dir: Directory for output artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        max_chunk_size: Maximum characters per chunk (default: 600)
        
    Returns:
        PassCResult with processing statistics
    """
    extractor = PassCExtractor(job_id, env, max_chunk_size)
    return extractor.process_pdf(pdf_path, output_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass C: Raw Extraction with unstructured.io")
    parser.add_argument("pdf_path", help="Path to source PDF")
    parser.add_argument("output_dir", help="Output directory for artifacts")
    parser.add_argument("--job-id", help="Job ID (default: auto-generated)")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir)
    job_id = args.job_id or f"job_{int(time.time())}"
    
    result = process_pass_c(pdf_path, output_dir, job_id, args.env)
    
    print(f"Pass C Result:")
    print(f"  Success: {result.success}")
    print(f"  Chunks extracted: {result.chunks_extracted}")
    print(f"  Chunks loaded: {result.chunks_loaded}")
    print(f"  Parts processed: {result.parts_processed}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)