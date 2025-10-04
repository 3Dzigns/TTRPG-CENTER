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
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from .ttrpg_logging import get_logger
from .toc_parser import TocParser
from .dictionary_loader import DictionaryLoader, DictEntry
from .artifact_validator import write_json_atomically
from .ttrpg_secrets import _load_env_file
from .job_logging import log_to_job, log_pass_start, log_pass_complete, log_upsert_result

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
    mode: str = "standard"
    lightweight: bool = False
    term_results: List[TermUpsertResult] = None  # Individual term upsert results
    toc_sections: List[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.term_results is None:
            self.term_results = []
        if self.toc_sections is None:
            self.toc_sections = []

    @property
    def dictionary_entries(self) -> int:
        """Backward compatibility: return upserted count"""
        return self.dictionary_entries_upserted


class PassATocParser:
    """Pass A: Initial ToC Parse and Dictionary Seeding"""

    def __init__(self, job_id: str, env: str = "dev", lightweight: bool = False, log_file_path: Optional[Path] = None):
        self.job_id = job_id
        self.env = env
        self.lightweight = lightweight
        self.log_file_path = log_file_path
        self.toc_parser = TocParser()
        self.dict_loader = DictionaryLoader(env)
        self._document_metadata = None  # Cache for document metadata
        self._category_map: Dict[str, Dict[str, Any]] = {}
        self._category_assignments = {"organic": 0, "pattern": 0, "general": 0}

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

                    # OCR fallback if text extraction returns minimal content
                    if len(page_text.strip()) < 10:
                        log_to_job("Standard text extraction returned minimal content, attempting OCR fallback", self.job_log_file, "info", "A")
                        page_text = self._ocr_fallback_page(pdf_path, page_num=0) or page_text

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

    def process_pdf(self, pdf_path: Path, output_dir: Path, force_dict_init: bool = False, lightweight: Optional[bool] = None) -> PassAResult:
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
        lightweight = self.lightweight if lightweight is None else lightweight
        self.lightweight = lightweight
        mode = "lightweight" if lightweight else "standard"
        source_hash = self._compute_file_hash(pdf_path) if pdf_path.exists() else None

        # Log to both container and job logs
        log_pass_start("A", f"ToC Parse & Dictionary Seeding ({mode} mode) - {pdf_path.name}", self.log_file_path)
        logger.info(f"Pass A starting ({mode} mode): ToC parse for {pdf_path.name}")
        term_upsert_results: List[TermUpsertResult] = []
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Check for Pass 0 TOC detection results
            import json
            gate0_report_path = output_dir.parent / "pass_0" / "gate0.report.json"
            use_new_toc_extraction = False
            toc_pages = (0, 0)

            if gate0_report_path.exists():
                try:
                    with open(gate0_report_path, 'r', encoding='utf-8') as f:
                        gate0_data = json.load(f)

                    toc_pages = (
                        gate0_data.get("toc_pages", {}).get("start", 0),
                        gate0_data.get("toc_pages", {}).get("end", 0)
                    )

                    if toc_pages[0] > 0:
                        use_new_toc_extraction = True
                        logger.info(f"Pass A: Pass 0 detected TOC on pages {toc_pages[0]}-{toc_pages[1]}, using new TOC-only extraction")
                    else:
                        logger.info(f"Pass A: Pass 0 did not detect TOC, using legacy PyMuPDF extraction")
                except Exception as e:
                    logger.warning(f"Pass A: Failed to read Pass 0 gate0.report.json: {e}, falling back to legacy extraction")
            else:
                logger.info(f"Pass A: No Pass 0 results found at {gate0_report_path}, using legacy PyMuPDF extraction")

            # Parse document structure and ToC with BUG-035 timeout protection
            logger.info(f"BUG-035 Fix: Starting Pass A with timeout protection for {pdf_path.name}")
            start_parse_time = time.time()

            # Initialize variables
            dict_entries: List[DictEntry] = []
            sections_count = 0
            extraction_method = "none"

            if use_new_toc_extraction:
                # NEW APPROACH: Use Unstructured.io TOC-only extraction
                try:
                    from .pass_a_toc_extraction import extract_toc_from_pages, generate_pass_a_toc_json

                    logger.info(f"Pass A: Extracting TOC from pages {toc_pages[0]}-{toc_pages[1]} using Unstructured.io")
                    toc_result = extract_toc_from_pages(pdf_path, toc_pages, self.job_id, self.log_file_path)

                    if toc_result.success:
                        sections_count = len(toc_result.sections)
                        extraction_method = toc_result.extraction_method

                        # Generate passA.toc.json
                        toc_json_path = output_dir / f"{self.job_id}_passA.toc.json"
                        generate_pass_a_toc_json(toc_result, toc_json_path)
                        logger.info(f"Pass A: Generated passA.toc.json with {sections_count} sections")

                        # Extract dictionary entries from passA.toc.json
                        dict_entries = self._extract_dictionary_from_toc_json(
                            toc_json_path,
                            pdf_path,
                            source_hash=source_hash,
                            job_id=self.job_id,
                            environment=self.env,
                        )
                        logger.info(f"Pass A: Extracted {len(dict_entries)} dictionary entries from passA.toc.json")
                    else:
                        logger.warning(f"Pass A: TOC extraction failed: {toc_result.error_message}, falling back to legacy")
                        use_new_toc_extraction = False  # Fall back to legacy

                except Exception as e:
                    logger.error(f"Pass A: New TOC extraction failed: {e}, falling back to legacy")
                    use_new_toc_extraction = False  # Fall back to legacy

            if not use_new_toc_extraction:
                # LEGACY APPROACH: Use PyMuPDF full-document parsing
                outline = self.toc_parser.parse_document_structure(pdf_path)
                sections_count = len(outline.entries)
                extraction_method = "pymupdf"

                parse_duration = time.time() - start_parse_time
                if parse_duration > 30:  # Log if parsing took longer than 30 seconds
                    logger.warning(f"BUG-035: Document structure parsing took {parse_duration:.1f}s - may indicate slow PDF")
                else:
                    logger.info(f"BUG-035: Document structure parsed in {parse_duration:.1f}s")

                # Log detailed ToC processing results
                logger.info(f"Pass A: Document analysis complete - {outline.total_pages} total pages")
                if outline.has_toc:
                    logger.info(f"Pass A: ToC found on pages: {outline.toc_pages}")
                    logger.info(f"Pass A: ToC structure contains {sections_count} entries")
                else:
                    logger.info(f"Pass A: No ToC detected - fallback to heading extraction")
                    logger.info(f"Pass A: Extracted {sections_count} heading-based sections")

                # Extract dictionary entries from legacy ToC structure
                if sections_count > 0:
                    dict_entries = self._extract_dictionary_from_toc(
                            outline,
                            pdf_path,
                            source_hash=source_hash,
                            job_id=self.job_id,
                            environment=self.env,
                        )

            # Common processing for both approaches
            upserted_count = 0
            term_results: List[Dict[str, Any]] = []

            if sections_count == 0:
                logger.info(f"No ToC entries found in {pdf_path.name}; proceeding without dictionary seeding")
            elif not dict_entries:
                logger.info(f"Pass A: No dictionary entries extracted from {sections_count} ToC sections")
            else:
                logger.info(f"Pass A: Extracted {len(dict_entries)} dictionary entries from {sections_count} ToC sections")

            if dict_entries:
                sample_terms = [entry.term for entry in dict_entries[:5]]
                categories = list(set(entry.category for entry in dict_entries))
                logger.debug(f"Pass A: Sample dictionary terms extracted: {sample_terms}")
                logger.debug(f"Pass A: Categories found: {categories}")

                try:
                    logger.debug(f"Pass A: Attempting to upsert {len(dict_entries)} dictionary entries to {self.dict_loader.backend} backend")
                    print(f"DEBUG: About to call upsert_entries with {len(dict_entries)} entries", flush=True)
                    upserted_count, term_results = self.dict_loader.upsert_entries(
                        dict_entries,
                        job_id=self.job_id,
                        source_hash=source_hash,
                        source_file=pdf_path.name,
                        environment=self.env,
                    )
                    print(f"DEBUG: upsert_entries returned upserted_count={upserted_count}, term_results type={type(term_results)}, len={len(term_results) if term_results else 'None'}", flush=True)
                    verification_count = getattr(self.dict_loader, "last_verification_count", None)
                    if verification_count is not None:
                        log_to_job(
                            f"Pass A dictionary: wrote {upserted_count} entries (verified {verification_count})",
                            self.log_file_path,
                            "info",
                            "A",
                        )
                        logger.info(
                            "pass_a.mongo.verify_ok",
                            extra={
                                "job_id": self.job_id,
                                "source_hash": source_hash,
                                "environment": self.env,
                                "rows_written": upserted_count,
                                "verified_count": verification_count,
                            },
                        )
                    else:
                        log_to_job(
                            f"Pass A dictionary: wrote {upserted_count} entries",
                            self.log_file_path,
                            "info",
                            "A",
                        )
                    logger.info(f"Pass A: Successfully upserted {upserted_count}/{len(dict_entries)} dictionary entries to {self.dict_loader.backend} database")
                    logger.info(f"Pass A: Received {len(term_results)} term results for detailed logging")

                    # Log detailed results for each term/category to both container and job logs
                    status_counts = {"inserted": 0, "updated": 0, "unchanged": 0, "failed": 0}
                    for result in term_results:
                        term = result.get('term', 'unknown')
                        category = result.get('category', 'uncategorized')
                        status = result.get('status', 'unknown')
                        error = result.get('error_message')

                        # Count by status
                        if status in status_counts:
                            status_counts[status] += 1

                        # Log individual term result using standardized format
                        operation_map = {
                            "inserted": "NEW",
                            "updated": "CHANGED",
                            "unchanged": "UNCHANGED",
                            "failed": "FAILED"
                        }
                        operation = operation_map.get(status, "UNKNOWN")
                        details = f"category={category}"
                        if error:
                            details += f", error={error}"

                        log_upsert_result(operation, term, "term", self.log_file_path, "A", details)

                        # Also log to container logger for backward compatibility
                        if status == "inserted":
                            logger.info(f"  📝 NEW: '{term}' → {category}")
                        elif status == "updated":
                            logger.info(f"  ✏️  CHANGED: '{term}' → {category}")
                        elif status == "unchanged":
                            logger.debug(f"  ✓ UNCHANGED: '{term}' → {category}")
                        elif status == "failed":
                            logger.error(f"  ✗ FAILED: '{term}' → {category}: {error}")

                    # Summary by status (to both logs)
                    summary = f"Dictionary Summary: {status_counts['inserted']} new, {status_counts['updated']} updated, {status_counts['unchanged']} unchanged, {status_counts['failed']} failed"
                    log_to_job(summary, self.log_file_path, "info", "A")
                    logger.info(f"Pass A {summary}")

                    if upserted_count != len(dict_entries):
                        logger.warning(f"Pass A: Only {upserted_count} of {len(dict_entries)} entries were upserted - possible duplicates or errors")
                except Exception as e:
                    logger.error(f"Pass A: Dictionary upsert failed (non-fatal for Pass A): {e}")
                    logger.debug(f"Pass A: Backend configuration - {self.dict_loader.backend}, connection status: {hasattr(self.dict_loader, 'mongo_client') and self.dict_loader.mongo_client is not None}")

            # Convert term results to TermUpsertResult objects
            term_upsert_results = []
            for result in term_results:
                term_upsert_results.append(TermUpsertResult(
                    term=result.get('term', ''),
                    category=result.get('category'),
                    status=result.get('status', 'unknown'),
                    error_message=result.get('error_message')
                ))

            # Write Pass A artifact
            dict_artifact_path = output_dir / f"{self.job_id}_pass_a_dict.json"
            dict_data = {
                "source": pdf_path.name,
                "job_id": self.job_id,
                "pass": "A",
                "stage": "toc_dictionary_seed",
                "mode": mode,
                "lightweight": lightweight,
                "entries_count": len(dict_entries),
                "upserted_count": upserted_count,
                "sections_parsed": sections_count,
                "toc_sections": [
                    {
                        "title": entry.title,
                        "page": entry.page,
                        "level": entry.level,
                    }
                    for entry in outline.entries
                ],
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

            # Write category taxonomy artifact
            category_artifact_path = output_dir / f"{self.job_id}_pass_a_categories.json"
            category_data = {
                "job_id": self.job_id,
                "document_title": self._get_document_title(pdf_path),
                "document_id": self._generate_document_id(pdf_path),
                "categories": self._category_map,
                "assignments": self._category_assignments,
                "total_categories": len(self._category_map),
                "created_at": time.time()
            }

            write_json_atomically(category_data, category_artifact_path)
            logger.info(f"Wrote Pass A category taxonomy artifact: {category_artifact_path}")
            logger.info(f"  Categories discovered: {len(self._category_map)}")
            logger.info(f"  Organic assignments: {self._category_assignments.get('organic', 0)}")
            logger.info(f"  Pattern-based assignments: {self._category_assignments.get('pattern', 0)}")

            # Generate manifest
            manifest_path = self._generate_manifest(
                output_dir,
                pdf_path,
                [dict_artifact_path, category_artifact_path],
                dict_entries,
                sections_count,
                outline
            )
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            duration_seconds = end_time - start_time

            # Log completion to both container and job logs
            stats = {
                "extracted": len(dict_entries),
                "upserted": upserted_count,
                "sections": sections_count,
                "categories": len(self._category_map) if hasattr(self, '_category_map') else 0
            }
            log_pass_complete("A", duration_seconds, stats, self.log_file_path)
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
                mode=mode,
                lightweight=lightweight,
                term_results=term_upsert_results,
                toc_sections=[
                    {
                        "title": entry.title,
                        "page": entry.page,
                        "level": entry.level,
                        "section_id": entry.section_id,
                        "parent_id": entry.parent_id,
                    }
                    for entry in outline.entries
                ]
            )

        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)

            # Enhanced error logging for BUG-035 diagnostics
            error_type = type(e).__name__
            if "timeout" in str(e).lower() or "TimeoutError" in error_type:
                logger.error(f"BUG-035: Pass A timeout failure for {pdf_path.name} after {processing_time_ms}ms: {e}")
                error_message = f"PDF processing timeout: {str(e)[:200]}"
            else:
                logger.error(f"BUG-035: Pass A general failure for {pdf_path.name} after {processing_time_ms}ms: {e}")
                error_message = f"PDF processing error ({error_type}): {str(e)[:200]}"

            # Log circuit breaker stats if available
            try:
                if hasattr(self.toc_parser, 'pdf_circuit'):
                    circuit_stats = self.toc_parser.pdf_circuit.get_stats()
                    logger.warning(f"BUG-035: Circuit breaker stats - calls: {circuit_stats['total_calls']}, "
                                 f"failures: {circuit_stats['total_failures']}, "
                                 f"timeouts: {circuit_stats['total_timeouts']}, "
                                 f"state: {circuit_stats['state']}")
            except Exception as circuit_error:
                logger.debug(f"BUG-035: Could not retrieve circuit breaker stats: {circuit_error}")

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
                mode=mode,
                lightweight=lightweight,
                term_results=[],
                toc_sections=[],
                error_message=error_message
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

    def _discover_categories_from_toc(self, toc_entries: List) -> Dict[str, Dict[str, Any]]:
        """
        Discover organic categories from ToC structure.

        Level 1-3 entries become category names. Child entries inherit parent category.
        Expanded to level 3 to capture comprehensive taxonomy (e.g., spell schools, class archetypes).
        Returns mapping: {category_name: {source_title, level, section_id, entry_count}}
        """
        category_map = {}

        for entry in toc_entries:
            # Level 1-3 entries become categories (expanded from 1-2 for richer taxonomy)
            # Also detect "Chapter" entries regardless of level (common in RPG books)
            is_chapter = "chapter" in entry.title.lower() and entry.level <= 4

            if entry.level <= 3 or is_chapter:
                # Normalize category name: lowercase, remove special chars, replace spaces with underscores
                raw_category = entry.title.strip()
                category_name = self._normalize_category_name(raw_category)

                if category_name and category_name not in category_map:
                    category_map[category_name] = {
                        "source_title": raw_category,
                        "level": entry.level,
                        "section_id": entry.section_id,
                        "parent_id": entry.parent_id,
                        "entry_count": 0,  # Will be incremented as entries are assigned
                        "is_chapter": is_chapter  # Flag for chapter-based categories
                    }

        return category_map

    def _normalize_category_name(self, raw_title: str) -> str:
        """
        Normalize a ToC title into a category name.

        Examples:
            "Chapter 2: Races" → "races"
            "Equipment & Gear" → "equipment_gear"
            "Spell Lists" → "spell_lists"
        """
        # Remove common prefixes
        title = raw_title.lower()
        title = re.sub(r'^(chapter|section|part|appendix)\s+[\dIVXivx]+\s*[:\-–—]?\s*', '', title)

        # Clean up punctuation and special chars
        title = re.sub(r'[&/]', '_and_', title)  # & or / becomes _and_
        title = re.sub(r'[^\w\s\-]', '', title)  # Remove non-alphanumeric except spaces and hyphens
        title = re.sub(r'[\s\-]+', '_', title)   # Replace spaces/hyphens with underscores
        title = re.sub(r'_+', '_', title)        # Collapse multiple underscores
        title = title.strip('_')                 # Trim leading/trailing underscores

        return title

    def _discover_categories_from_json_sections(self, sections: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """
        Discover organic categories from passA.toc.json sections.

        Level 1-3 sections become category names. Child sections inherit parent category.
        """
        category_map = {}

        for section in sections:
            # Level 1-3 sections become categories
            is_chapter = "chapter" in section["title"].lower() and section["level"] <= 4

            if section["level"] <= 3 or is_chapter:
                raw_category = section["title"].strip()
                category_name = self._normalize_category_name(raw_category)

                if category_name and category_name not in category_map:
                    category_map[category_name] = {
                        "source_title": raw_category,
                        "level": section["level"],
                        "section_id": section["section_id"],
                        "parent_id": section.get("parent_id"),
                        "entry_count": 0,
                        "is_chapter": is_chapter
                    }

        return category_map

    def _assign_category_from_json_section(self, section: Dict, category_map: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
        """
        Assign category to section based on passA.toc.json hierarchy.

        Returns: (category_name, source) where source is "organic" or "default"
        """
        # If section itself is a category (level 1-3), assign to that category
        normalized_title = self._normalize_category_name(section["title"])
        if normalized_title in category_map:
            category_map[normalized_title]["entry_count"] += 1
            return (normalized_title, "organic")

        # If section has parent_id, find the parent category
        parent_id = section.get("parent_id")
        if parent_id:
            for cat_name, cat_info in category_map.items():
                if cat_info["section_id"] == parent_id:
                    cat_info["entry_count"] += 1
                    return (cat_name, "organic")

        # No hierarchy-based category found
        return ("general", "default")

    def _assign_category_from_hierarchy(self, entry, category_map: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
        """
        Assign category to entry based on ToC hierarchy.

        Returns: (category_name, source) where source is "toc_hierarchy" or "default"
        """
        # Check if this is a chapter entry (common in RPG books)
        is_chapter = "chapter" in entry.title.lower() and entry.level <= 4

        # If this entry is a category itself (level 1-3 or chapter), use its own normalized name
        if entry.level <= 3 or is_chapter:
            category_name = self._normalize_category_name(entry.title)
            if category_name in category_map:
                category_map[category_name]["entry_count"] += 1
                return (category_name, "toc_hierarchy")

        # Otherwise, find parent category by walking up the hierarchy
        if entry.parent_id:
            # Look for parent in category map by section_id
            for cat_name, cat_info in category_map.items():
                if cat_info["section_id"] == entry.parent_id:
                    cat_info["entry_count"] += 1
                    return (cat_name, "toc_hierarchy")

        # No ToC-based category found
        return ("general", "default")

    def _extract_dictionary_from_toc_json(
        self,
        toc_json_path: Path,
        pdf_path: Path,
        *,
        source_hash: Optional[str],
        job_id: str,
        environment: str,
    ) -> List[DictEntry]:
        """Extract dictionary entries from passA.toc.json structure."""
        import json

        resolved_hash = source_hash or (self._compute_file_hash(pdf_path) if pdf_path.exists() else None)

        with open(toc_json_path, "r", encoding="utf-8") as handle:
            toc_data = json.load(handle)

        entries: List[DictEntry] = []
        document_title = self._get_document_title(pdf_path)
        document_id = self._generate_document_id(pdf_path)

        sections = toc_data.get("sections", [])
        logger.info("Pass A: Starting dictionary extraction from %s TOC sections (passA.toc.json)", len(sections))
        logger.info("Pass A: Document title: '%s', Document ID: %s", document_title, document_id)

        category_map = self._discover_categories_from_json_sections(sections)
        logger.info("Pass A: Discovered %s organic categories from TOC structure", len(category_map))
        for cat_name, cat_info in category_map.items():
            logger.info(
                "  Category: '%s' from '%s' (level %s, %s entries)",
                cat_name,
                cat_info['source_title'],
                cat_info['level'],
                cat_info['entry_count'],
            )

        spell_patterns = ["spell", "magic", "incantation", "enchantment"]
        feat_patterns = ["feat", "ability", "talent", "skill"]
        class_patterns = ["class", "archetype", "prestige", "profession"]
        equipment_patterns = ["weapon", "armor", "item", "equipment", "gear"]
        rule_patterns = ["rule", "mechanic", "system", "combat", "action"]

        processed_count = 0
        extracted_count = 0
        category_assignments = {"organic": 0, "pattern": 0, "general": 0}

        for section in sections:
            processed_count += 1
            raw_title = section["title"].strip()
            title = self._sanitize_title(raw_title)

            logger.debug(
                "Pass A: Section[%s] raw='%s' -> sanitized='%s' page=%s level=%s",
                processed_count,
                raw_title,
                title,
                section.get("start_page"),
                section.get("level"),
            )

            if not title or len(title) < 3:
                logger.debug("Pass A: Section[%s] SKIPPED - too short or empty", processed_count)
                continue

            letters = re.findall(r"[A-Za-z]", title)
            nonspace = re.findall(r"\S", title)
            if len(letters) < 3 or (len(nonspace) > 0 and (len(letters) / max(1, len(nonspace))) < 0.5):
                logger.debug("Pass A: Section[%s] SKIPPED - insufficient letter content", processed_count)
                continue

            title_lower = title.lower()
            category = "general"
            category_source = "default"
            definition = f"Section from {document_title} table of contents"

            category, category_source = self._assign_category_from_json_section(section, category_map)

            if category == "general" and category_source == "default":
                if any(pattern in title_lower for pattern in spell_patterns):
                    category = "spells"
                    category_source = "pattern"
                    definition = f"Spell or magical ability described in {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in feat_patterns):
                    category = "feats"
                    category_source = "pattern"
                    definition = f"Character feat or ability from {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in class_patterns):
                    category = "classes"
                    category_source = "pattern"
                    definition = f"Character class or archetype from {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in equipment_patterns):
                    category = "equipment"
                    category_source = "pattern"
                    definition = f"Equipment or gear from {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in rule_patterns):
                    category = "mechanics"
                    category_source = "pattern"
                    definition = f"Game rule or mechanic from {document_title} (ToC reference)"

            if category_source == "organic":
                category_assignments["organic"] += 1
            elif category_source == "pattern":
                category_assignments["pattern"] += 1
            else:
                category_assignments["general"] += 1

            source_metadata = {
                "system": document_title,
                "document_id": document_id,
                "method": "toc_parse",
                "page_reference": "TOC",
                "original_page": section.get("start_page"),
                "level": section.get("level"),
                "category_source": category_source,
                "pass": "A",
                "source_hash": resolved_hash,
                "environment": environment,
                "job_id": job_id,
            }

            dict_entry = DictEntry(
                term=title,
                category=category,
                definition=definition,
                sources=[source_metadata],
                job_id=job_id,
                source_hash=resolved_hash,
                environment=environment,
                source_file=pdf_path.name,
                source_page=section.get("start_page"),
                document_id=document_id,
                confidence=0.8 if category_source in ["organic", "pattern"] else 0.5,
            )

            entries.append(dict_entry)
            extracted_count += 1
            logger.debug(
                "Pass A: Section[%s] EXTRACTED - category='%s' (%s)",
                processed_count,
                category,
                category_source,
            )

        logger.info(
            "Pass A: Dictionary extraction complete - processed %s sections, extracted %s entries",
            processed_count,
            extracted_count,
        )
        logger.info(
            "Pass A: Category assignments - organic: %s, pattern: %s, general: %s",
            category_assignments['organic'],
            category_assignments['pattern'],
            category_assignments['general'],
        )

        return entries

    def _extract_dictionary_from_toc(self, outline, pdf_path: Path) -> List[DictEntry]:
        """
        Extract dictionary entries from ToC structure with organic category discovery.

        LEGACY METHOD - Used when passA.toc.json is not available.
        Prefer _extract_dictionary_from_toc_json() when possible.
        """
        entries = []

        # Get document metadata for improved source information
        document_title = self._get_document_title(pdf_path)
        document_id = self._generate_document_id(pdf_path)

        logger.info(f"Pass A: Starting dictionary extraction from {len(outline.entries)} ToC entries (LEGACY PyMuPDF)")
        logger.info(f"Pass A: Document title: '{document_title}', Document ID: {document_id}")

        # Phase 1: Discover categories from ToC hierarchy (level 1-2 entries become categories)
        logger.info(f"Pass A: Phase 1 - Discovering categories from ToC structure...")
        category_map = self._discover_categories_from_toc(outline.entries)
        logger.info(f"Pass A: Discovered {len(category_map)} organic categories from ToC structure")

        for cat_name, cat_info in category_map.items():
            logger.info(f"  Category: '{cat_name}' from '{cat_info['source_title']}' (level {cat_info['level']}, {cat_info['entry_count']} entries)")

        # Fallback pattern matching for entries without ToC context
        spell_patterns = ["spell", "magic", "incantation", "enchantment"]
        feat_patterns = ["feat", "ability", "talent", "skill"]
        class_patterns = ["class", "archetype", "prestige", "profession"]
        equipment_patterns = ["weapon", "armor", "item", "equipment", "gear"]
        rule_patterns = ["rule", "mechanic", "system", "combat", "action"]

        # Phase 2: Extract dictionary entries with category assignment
        logger.info(f"Pass A: Phase 2 - Extracting dictionary entries with category mapping...")
        processed_count = 0
        extracted_count = 0
        category_assignments = {"organic": 0, "pattern": 0, "general": 0}

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
            category_source = "default"
            definition = f"Section from {document_title} table of contents"

            # Try organic category assignment from ToC hierarchy first
            category, category_source = self._assign_category_from_hierarchy(entry, category_map)

            # Fallback to pattern matching if no ToC-derived category found
            if category == "general" and category_source == "default":
                if any(pattern in title_lower for pattern in spell_patterns):
                    category = "spells"
                    category_source = "pattern"
                    definition = f"Spell or magical ability described in {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in feat_patterns):
                    category = "feats"
                    category_source = "pattern"
                    definition = f"Character feat or ability from {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in class_patterns):
                    category = "classes"
                    category_source = "pattern"
                    definition = f"Character class or archetype from {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in equipment_patterns):
                    category = "equipment"
                    category_source = "pattern"
                    definition = f"Equipment or gear from {document_title} (ToC reference)"
                elif any(pattern in title_lower for pattern in rule_patterns):
                    category = "mechanics"
                    category_source = "pattern"
                    definition = f"Game rule or mechanic from {document_title} (ToC reference)"
                elif entry.level <= 2:
                    category = "general"
                    category_source = "general"
                    definition = f"Major section from {document_title} table of contents"

            # Skip very low-level entries without category assignment to avoid noise
            if category == "general" and category_source == "default" and entry.level > 3:
                logger.debug(f"Pass A: ToC[{processed_count}] SKIPPED - low-level entry without category (level {entry.level})")
                continue

            # Track category assignment method
            if category_source == "toc_hierarchy":
                category_assignments["organic"] += 1
            elif category_source == "pattern":
                category_assignments["pattern"] += 1
            else:
                category_assignments["general"] += 1

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
                    "category_source": category_source,  # Track how category was assigned
                    "pass": "A"                    # Track which pass created this
                }]
            )
            entries.append(dict_entry)
            extracted_count += 1

            logger.info(f"Pass A: EXTRACTED #{extracted_count}: '{title}' → {category} ({category_source}) (page {entry.page}, level {entry.level})")

        logger.info(f"Pass A: Extraction complete - processed {processed_count} ToC entries, extracted {extracted_count} terms")
        logger.info(f"Pass A: Category assignments - organic: {category_assignments['organic']}, pattern: {category_assignments['pattern']}, general: {category_assignments['general']}")

        # Store category taxonomy for reference
        self._category_map = category_map
        self._category_assignments = category_assignments

        return entries
    
    def _generate_manifest(
        self,
        output_dir: Path,
        pdf_path: Path,
        artifacts: List[Path],
        dict_entries: List[DictEntry],
        sections_count: int,
        outline
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
            "mode": "lightweight" if self.lightweight else "standard",
            "lightweight": self.lightweight,
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
            "has_toc": bool(getattr(outline, "entries", [])),
            "toc": [
                {
                    "title": entry.title,
                    "page": entry.page,
                    "level": entry.level,
                    "section_id": entry.section_id,
                    "parent_id": entry.parent_id,
                }
                for entry in getattr(outline, "entries", [])
            ],
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
        manifest_path = output_dir / f"{self.job_id}_pass_a_manifest.json"
        write_json_atomically(manifest_data, manifest_path)
        
        return manifest_path
    
    def _ocr_fallback_page(self, pdf_path: Path, page_num: int) -> Optional[str]:
        """
        OCR fallback for image-based PDFs when standard text extraction fails.

        Uses pdftotext and tesseract to extract text from image-based pages.
        """
        try:
            import subprocess
            import tempfile

            # First attempt: Use pdftotext (faster, part of poppler-utils)
            try:
                result = subprocess.run(
                    ["pdftotext", "-f", str(page_num + 1), "-l", str(page_num + 1), str(pdf_path), "-"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0 and len(result.stdout.strip()) > 10:
                    log_to_job(f"OCR: pdftotext extracted {len(result.stdout)} chars from page {page_num}", self.job_log_file, "info", "A")
                    return result.stdout
            except Exception as e:
                logger.debug(f"pdftotext fallback failed: {e}")

            # Second attempt: Use tesseract OCR (slower but works on pure images)
            try:
                # Convert PDF page to image using pdftoppm
                with tempfile.TemporaryDirectory() as tmpdir:
                    img_prefix = f"{tmpdir}/page"

                    # Extract single page as PNG
                    subprocess.run(
                        ["pdftoppm", "-f", str(page_num + 1), "-l", str(page_num + 1),
                         "-png", str(pdf_path), img_prefix],
                        capture_output=True,
                        timeout=15
                    )

                    # Find generated image
                    import glob
                    img_files = glob.glob(f"{tmpdir}/*.png")
                    if not img_files:
                        return None

                    # Run tesseract OCR
                    result = subprocess.run(
                        ["tesseract", img_files[0], "stdout"],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    if result.returncode == 0 and len(result.stdout.strip()) > 10:
                        log_to_job(f"OCR: tesseract extracted {len(result.stdout)} chars from page {page_num}", self.job_log_file, "info", "A")
                        return result.stdout

            except Exception as e:
                logger.debug(f"tesseract fallback failed: {e}")

            return None

        except Exception as e:
            logger.warning(f"OCR fallback failed for page {page_num}: {e}")
            return None

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


def process_pass_a(
    pdf_path: Path,
    output_dir: Path,
    job_id: str,
    env: str = "dev",
    force_dict_init: bool = False,
    lightweight: bool = False,
    log_file_path: Optional[Path] = None,
) -> PassAResult:
    """
    Convenience function for Pass A processing

    Args:
        pdf_path: Path to source PDF
        output_dir: Directory for output artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        force_dict_init: Force dictionary initialization even if exists
        lightweight: Lightweight mode for testing
        log_file_path: Path to job-specific log file for observability

    Returns:
        PassAResult with processing statistics
    """
    parser = PassATocParser(job_id, env, lightweight=lightweight, log_file_path=log_file_path)
    return parser.process_pdf(
        pdf_path,
        output_dir,
        force_dict_init=force_dict_init,
        lightweight=lightweight,
    )


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
