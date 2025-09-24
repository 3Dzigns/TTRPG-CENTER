# src_common/pass_a_toc_parser.py
"""
Pass A: Initial ToC Parse (Prime Dictionary)

Parse Table of Contents and high-confidence headings to build a seed dictionary 
of section names, page ranges, and canonical spell/feat/class names.

Responsibilities:
- Parse ToC and extract section structure
- Identify high-confidence game terms (spells, feats, classes)
- Build seed dictionary entries
- Write dictionary terms only (no chunk upserts)
- Generate manifest with checksums/mtime

Artifacts:
- *_pass_a_dict.json: Dictionary entries extracted from ToC
- manifest.json: Checksums, metadata, validation info
"""

import json
import re
import time
import hashlib
from pathlib import Path
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .ttrpg_logging import get_logger
from .toc_parser import TocParser
from .dictionary_loader import DictionaryLoader, DictEntry
from .artifact_validator import write_json_atomically
from .ttrpg_secrets import _load_env_file

# Import for PDF metadata extraction
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

logger = get_logger(__name__)


@dataclass
class TermUpsertResult:
    """Individual term upsert result"""
    term: str
    category: str
    status: str  # "inserted", "updated", "unchanged", "failed"
    error_message: Optional[str] = None

@dataclass
class PassAResult:
    """Result of Pass A ToC parsing and dictionary seeding"""
    source_file: str
    job_id: str
    dictionary_entries_extracted: int  # Total terms extracted from ToC
    dictionary_entries_upserted: int   # Terms successfully upserted to database
    sections_parsed: int
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    term_results: List[TermUpsertResult] = None  # Individual term upsert results
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.term_results is None:
            self.term_results = []

    @property
    def dictionary_entries(self) -> int:
        """Backward compatibility: return upserted count"""
        return self.dictionary_entries_upserted


class PassATocParser:
    """Pass A: Initial ToC Parse and Dictionary Seeding"""

    def __init__(self, job_id: str, env: str = "dev"):
        self.job_id = job_id
        self.env = env
        self.toc_parser = TocParser()
        self.dict_loader = DictionaryLoader(env)
        self._document_metadata = None  # Cache for document metadata

    def _extract_pdf_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract document metadata from PDF"""
        if self._document_metadata is not None:
            return self._document_metadata

        metadata = {
            'title': None,
            'author': None,
            'subject': None,
            'creator': None,
            'filename': pdf_path.stem,
            'full_filename': pdf_path.name,
            'file_size': pdf_path.stat().st_size if pdf_path.exists() else 0
        }

        if HAS_PYMUPDF and pdf_path.exists():
            try:
                doc = fitz.open(str(pdf_path))
                pdf_metadata = doc.metadata

                # Extract standard metadata fields
                metadata['title'] = pdf_metadata.get('title', '').strip() or None
                metadata['author'] = pdf_metadata.get('author', '').strip() or None
                metadata['subject'] = pdf_metadata.get('subject', '').strip() or None
                metadata['creator'] = pdf_metadata.get('creator', '').strip() or None

                # Try to extract title from first page if metadata title is empty
                if not metadata['title'] and doc.page_count > 0:
                    first_page = doc[0]
                    page_text = first_page.get_text()
                    lines = [line.strip() for line in page_text.split('\n') if line.strip()]

                    # Look for title-like text in first few lines
                    for line in lines[:10]:
                        if len(line) > 5 and len(line) < 100 and not line.isdigit():
                            # Skip common non-title patterns
                            if not any(pattern in line.lower() for pattern in ['page', 'table of contents', 'copyright', '©']):
                                metadata['title'] = line.strip()
                                break

                doc.close()
                logger.debug(f"PDF metadata extracted: title='{metadata['title']}', author='{metadata['author']}'")

            except Exception as e:
                logger.warning(f"Failed to extract PDF metadata from {pdf_path}: {e}")

        self._document_metadata = metadata
        return metadata

    def _generate_document_id(self, pdf_path: Path) -> str:
        """Generate a stable document ID for tracking across passes"""
        # Use file content hash + filename for stable ID
        try:
            with open(pdf_path, 'rb') as f:
                # Read first 64KB for hash (faster than full file)
                content_sample = f.read(65536)
                content_hash = hashlib.md5(content_sample).hexdigest()[:12]

            # Combine with normalized filename
            filename_normalized = re.sub(r'[^a-z0-9]+', '_', pdf_path.stem.lower()).strip('_')
            document_id = f"doc_{filename_normalized}_{content_hash}"

            logger.debug(f"Generated document ID: {document_id}")
            return document_id

        except Exception as e:
            logger.warning(f"Failed to generate content-based document ID: {e}")
            # Fallback to filename-based ID
            filename_normalized = re.sub(r'[^a-z0-9]+', '_', pdf_path.stem.lower()).strip('_')
            return f"doc_{filename_normalized}_{int(time.time())}"

    def _get_document_title(self, pdf_path: Path) -> str:
        """Get document title with fallback hierarchy"""
        metadata = self._extract_pdf_metadata(pdf_path)

        # Fallback hierarchy: PDF title → filename (cleaned) → full filename
        if metadata['title']:
            return metadata['title']

        # Clean up filename for display
        filename_clean = pdf_path.stem.replace('_', ' ').replace('-', ' ')
        filename_clean = re.sub(r'\s+', ' ', filename_clean).strip()

        return filename_clean or pdf_path.name

    def process_pdf(self, pdf_path: Path, output_dir: Path, force_dict_init: bool = False) -> PassAResult:
        """
        Process PDF for Pass A: ToC parsing and dictionary seeding
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output artifacts
            force_dict_init: Force dictionary initialization even if exists
            
        Returns:
            PassAResult with processing statistics
        """
        start_time = time.time()
        logger.info(f"Pass A starting: ToC parse for {pdf_path.name}")
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Parse document structure and ToC
            logger.info("Parsing document structure and ToC...")
            outline = self.toc_parser.parse_document_structure(pdf_path)
            sections_count = len(outline.entries)

            # Log detailed ToC processing results
            logger.info(f"Pass A: Document analysis complete - {outline.total_pages} total pages")
            if outline.has_toc:
                logger.info(f"Pass A: ToC found on pages: {outline.toc_pages}")
                logger.info(f"Pass A: ToC structure contains {sections_count} entries")
            else:
                logger.info(f"Pass A: No ToC detected - fallback to heading extraction")
                logger.info(f"Pass A: Extracted {sections_count} heading-based sections")

            # Extract dictionary entries from ToC structure (if any)
            dict_entries: List[DictEntry] = []
            upserted_count = 0
            if sections_count == 0:
                logger.info(f"No ToC entries found in {pdf_path.name}; proceeding without dictionary seeding")
            else:
                dict_entries = self._extract_dictionary_from_toc(outline, pdf_path)
                logger.info(f"Pass A: Extracted {len(dict_entries)} dictionary entries from {sections_count} ToC sections")

                # Debug logging: show sample of extracted terms
                if dict_entries:
                    sample_terms = [entry.term for entry in dict_entries[:5]]
                    categories = list(set(entry.category for entry in dict_entries))
                    logger.debug(f"Pass A: Sample dictionary terms extracted: {sample_terms}")
                    logger.debug(f"Pass A: Categories found: {categories}")

                # Try to upsert dictionary entries to database; do not fail Pass A if this step fails
                term_results = []
                if dict_entries:
                    try:
                        logger.debug(f"Pass A: Attempting to upsert {len(dict_entries)} dictionary entries to {self.dict_loader.backend} backend")
                        upserted_count, term_results = self.dict_loader.upsert_entries(dict_entries)
                        logger.info(f"Pass A: Successfully upserted {upserted_count}/{len(dict_entries)} dictionary entries to {self.dict_loader.backend} database")
                        if upserted_count != len(dict_entries):
                            logger.warning(f"Pass A: Only {upserted_count} of {len(dict_entries)} entries were upserted - possible duplicates or errors")
                    except Exception as e:
                        logger.error(f"Pass A: Dictionary upsert failed (non-fatal for Pass A): {e}")
                        logger.debug(f"Pass A: Backend configuration - {self.dict_loader.backend}, connection status: {hasattr(self.dict_loader, 'mongo_client') and self.dict_loader.mongo_client is not None}")

                # Convert term results to TermUpsertResult objects
                term_upsert_results = []
                for result in term_results:
                    term_upsert_results.append(TermUpsertResult(
                        term=result["term"],
                        category=result["category"],
                        status=result["status"],
                        error_message=result["error_message"]
                    ))
            
            # Write Pass A artifact
            dict_artifact_path = output_dir / f"{self.job_id}_pass_a_dict.json"
            dict_data = {
                "source": pdf_path.name,
                "job_id": self.job_id,
                "pass": "A",
                "stage": "toc_dictionary_seed",
                "entries_count": len(dict_entries),
                "upserted_count": upserted_count,
                "sections_parsed": sections_count,
                "dictionary_entries": [
                    {
                        "term": entry.term,
                        "definition": entry.definition,
                        "category": entry.category,
                        "sources": entry.sources
                    }
                    for entry in dict_entries
                ],
                "created_at": time.time()
            }
            
            write_json_atomically(dict_data, dict_artifact_path)
            logger.info(f"Wrote Pass A dictionary artifact: {dict_artifact_path}")
            
            # Generate manifest
            manifest_path = self._generate_manifest(
                output_dir, 
                pdf_path, 
                [dict_artifact_path],
                dict_entries,
                sections_count
            )
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            logger.info(f"Pass A completed for {pdf_path.name} in {processing_time_ms}ms: {len(dict_entries)} extracted, {upserted_count} upserted")
            
            return PassAResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                dictionary_entries_extracted=len(dict_entries),
                dictionary_entries_upserted=upserted_count,
                sections_parsed=sections_count,
                processing_time_ms=processing_time_ms,
                artifacts=[str(dict_artifact_path)],
                manifest_path=str(manifest_path),
                success=True,
                term_results=term_upsert_results
            )

        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass A failed for {pdf_path.name}: {e}")
            
            return PassAResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                dictionary_entries_extracted=0,
                dictionary_entries_upserted=0,
                sections_parsed=0,
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )
    
    def _sanitize_title(self, title: str) -> str:
        """Normalize noisy ToC titles into clean dictionary terms.

        Fixes common issues:
        - Dotted leaders with or without spaces
        - Letter-spaced headings (e.g., "S h a m a n")
        - Stray trailing page numbers left in title
        - Excess punctuation/whitespace
        """
        s = title.strip()
        # Remove dotted/dashed leaders, including spaced variants (". . .", "---")
        s = re.sub(r"(?:\.|\s)*\.{1}(?:\s*\.){2,}", " ", s)  # collapse runs of spaced dots
        s = re.sub(r"[\.]{3,}", " ", s)  # collapse contiguous dots
        s = re.sub(r"-{3,}", " ", s)
        # If the line looks like letter-spaced text (many single-letter tokens), collapse them
        if re.search(r"(?:[A-Za-z]\s+){3,}[A-Za-z]", s):
            letters_only = re.sub(r"[^A-Za-z\s]", "", s)
            s = re.sub(r"\s+", "", letters_only)
        # Remove lingering page number at end when likely ToC artifacts were present
        if re.search(r"(?:\.|\s){2,}", title) or re.search(r"(?:[A-Za-z]\s+){3,}[A-Za-z]", title):
            s = re.sub(r"[\s\._-]*\d{1,4}$", "", s)
        # Normalize inner whitespace and trim punctuation
        s = re.sub(r"\s+", " ", s).strip(" .-_:\t")
        return s

    def _extract_dictionary_from_toc(self, outline, pdf_path: Path) -> List[DictEntry]:
        """Extract dictionary entries from ToC structure"""
        entries = []

        # Get document metadata for improved source information
        document_title = self._get_document_title(pdf_path)
        document_id = self._generate_document_id(pdf_path)

        logger.info(f"Pass A: Starting dictionary extraction from {len(outline.entries)} ToC entries")
        logger.info(f"Pass A: Document title: '{document_title}', Document ID: {document_id}")

        # Game term patterns for high-confidence identification
        spell_patterns = ["spell", "magic", "incantation", "enchantment"]
        feat_patterns = ["feat", "ability", "talent", "skill"]
        class_patterns = ["class", "archetype", "prestige", "profession"]
        equipment_patterns = ["weapon", "armor", "item", "equipment", "gear"]
        rule_patterns = ["rule", "mechanic", "system", "combat", "action"]

        processed_count = 0
        extracted_count = 0

        for entry in outline.entries:
            processed_count += 1
            raw_title = entry.title.strip()
            title = self._sanitize_title(raw_title)

            logger.debug(f"Pass A: ToC[{processed_count}] raw='{raw_title}' → sanitized='{title}' page={entry.page} level={entry.level}")

            if not title or len(title) < 3:
                logger.debug(f"Pass A: ToC[{processed_count}] SKIPPED - too short or empty")
                continue

            # Guardrails: require at least one run of 3+ letters and reasonable signal
            letters = re.findall(r"[A-Za-z]", title)
            nonspace = re.findall(r"\S", title)
            if len(letters) < 3 or (len(nonspace) > 0 and (len(letters) / max(1, len(nonspace))) < 0.5):
                logger.debug(f"Pass A: ToC[{processed_count}] SKIPPED - insufficient letter content: {len(letters)} letters of {len(nonspace)} chars")
                continue

            title_lower = title.lower()
            category = "general"
            definition = f"Section from {document_title} table of contents"

            # Categorize based on title content
            if any(pattern in title_lower for pattern in spell_patterns):
                category = "spells"
                definition = f"Spell or magical ability described in {document_title} (ToC reference)"
            elif any(pattern in title_lower for pattern in feat_patterns):
                category = "feats"
                definition = f"Character feat or ability from {document_title} (ToC reference)"
            elif any(pattern in title_lower for pattern in class_patterns):
                category = "classes"
                definition = f"Character class or archetype from {document_title} (ToC reference)"
            elif any(pattern in title_lower for pattern in equipment_patterns):
                category = "equipment"
                definition = f"Equipment or gear from {document_title} (ToC reference)"
            elif any(pattern in title_lower for pattern in rule_patterns):
                category = "mechanics"
                definition = f"Game rule or mechanic from {document_title} (ToC reference)"
            elif entry.level <= 2:  # High-level sections
                category = "general"
                definition = f"Major section from {document_title} table of contents"
            else:
                # Skip very low-level entries to avoid noise
                logger.debug(f"Pass A: ToC[{processed_count}] SKIPPED - low-level entry (level {entry.level})")
                continue

            # Create dictionary entry with improved metadata
            dict_entry = DictEntry(
                term=title,
                definition=definition[:400],  # Limit definition length
                category=category,
                sources=[{
                    "system": document_title,      # Document title instead of filename
                    "document_id": document_id,    # Stable document identifier
                    "method": "toc_parse",
                    "page_reference": "TOC",       # All Pass A entries are from ToC
                    "original_page": entry.page,   # Keep original page for reference
                    "section_id": entry.section_id,
                    "level": entry.level,
                    "pass": "A"                    # Track which pass created this
                }]
            )
            entries.append(dict_entry)
            extracted_count += 1

            logger.info(f"Pass A: EXTRACTED #{extracted_count}: '{title}' → {category} (page {entry.page}, level {entry.level})")

        logger.info(f"Pass A: Extraction complete - processed {processed_count} ToC entries, extracted {extracted_count} terms")
        return entries
    
    def _generate_manifest(
        self, 
        output_dir: Path, 
        pdf_path: Path, 
        artifacts: List[Path],
        dict_entries: List[DictEntry],
        sections_count: int
    ) -> Path:
        """Generate manifest.json with checksums and metadata"""
        
        manifest_data = {
            "job_id": self.job_id,
            "source_file": pdf_path.name,
            "source_path": str(pdf_path),
            "pass": "A",
            "stage": "toc_dictionary_seed",
            "completed_passes": ["A"],
            "environment": self.env,
            "created_at": time.time(),
            "chunks": [],  # BUG-016: Always include chunks key for schema validation
            "source_info": {
                "file_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
                "file_mtime": pdf_path.stat().st_mtime if pdf_path.exists() else 0,
                "source_hash": self._compute_file_hash(pdf_path) if pdf_path.exists() else ""
            },
            "pass_a_results": {
                "dictionary_entries_extracted": len(dict_entries),
                "sections_parsed": sections_count,
                "categories": list(set(entry.category for entry in dict_entries))
            },
            "artifacts": []
        }
        
        # Add artifact checksums
        for artifact_path in artifacts:
            if artifact_path.exists():
                manifest_data["artifacts"].append({
                    "file": artifact_path.name,
                    "path": str(artifact_path),
                    "size": artifact_path.stat().st_size,
                    "mtime": artifact_path.stat().st_mtime,
                    "checksum": self._compute_file_hash(artifact_path)
                })
        
        # Write manifest
        manifest_path = output_dir / "manifest.json"
        write_json_atomically(manifest_data, manifest_path)
        
        return manifest_path
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def process_pass_a(pdf_path: Path, output_dir: Path, job_id: str, env: str = "dev", force_dict_init: bool = False) -> PassAResult:
    """
    Convenience function for Pass A processing
    
    Args:
        pdf_path: Path to source PDF
        output_dir: Directory for output artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        force_dict_init: Force dictionary initialization even if exists
        
    Returns:
        PassAResult with processing statistics
    """
    parser = PassATocParser(job_id, env)
    return parser.process_pdf(pdf_path, output_dir, force_dict_init=force_dict_init)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass A: ToC Parse and Dictionary Seeding")
    parser.add_argument("pdf_path", help="Path to source PDF")
    parser.add_argument("output_dir", help="Output directory for artifacts")
    parser.add_argument("--job-id", help="Job ID (default: auto-generated)")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir)
    job_id = args.job_id or f"job_{int(time.time())}"
    
    result = process_pass_a(pdf_path, output_dir, job_id, args.env)
    
    print(f"Pass A Result:")
    print(f"  Success: {result.success}")
    print(f"  Dictionary entries extracted: {result.dictionary_entries_extracted}")
    print(f"  Dictionary entries upserted: {result.dictionary_entries_upserted}")
    print(f"  Sections parsed: {result.sections_parsed}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)
