"""
Pass 0 — Preflight & De-dup

Compute file_sha, page count; short-circuit if identical to prior ingestion.
MVP v2 requirement: Pass 0→G pipeline with preflight checks.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .logging import get_logger
from .environment_isolation import get_environment_validator
from .job_logging import log_to_job, log_pass_start, log_pass_complete

logger = get_logger(__name__)


class PreflightResult:
    """Result of preflight checks."""

    def __init__(self, should_skip: bool, reason: str = "", file_sha: str = "",
                 page_count: int = 0, existing_job_id: str = "",
                 scanned_pages: list = None, has_text_layer: bool = True,
                 toc_pages: tuple = None, toc_confidence: float = 0.0):
        self.should_skip = should_skip
        self.reason = reason
        self.file_sha = file_sha
        self.page_count = page_count
        self.existing_job_id = existing_job_id
        self.scanned_pages = scanned_pages if scanned_pages is not None else []
        self.has_text_layer = has_text_layer
        self.toc_pages = toc_pages if toc_pages is not None else (0, 0)
        self.toc_confidence = toc_confidence


def compute_file_sha(file_path: Path) -> str:
    """
    Compute SHA-256 hash of file.

    Args:
        file_path: Path to file to hash

    Returns:
        Hex string of SHA-256 hash

    Raises:
        OSError: If file cannot be read
    """
    logger.info(f"Computing SHA-256 for {file_path}")

    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    file_sha = sha256_hash.hexdigest()
    logger.debug(f"File SHA-256: {file_sha}")

    return file_sha


def get_pdf_page_count(file_path: Path) -> int:
    """
    Get page count from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Number of pages in PDF

    Raises:
        ValueError: If file is not a valid PDF or cannot be read
    """
    try:
        # Try to use PyPDF2/PyPDF4 for page count
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                logger.debug(f"PDF page count (PyPDF2): {page_count}")
                return page_count
        except ImportError:
            logger.debug("PyPDF2 not available, trying alternative method")

        # Alternative: count pages using basic PDF parsing
        with open(file_path, "rb") as f:
            content = f.read()

        # Count occurrences of /Type /Page
        page_count = content.count(b"/Type /Page")
        if page_count == 0:
            # Fallback: count page objects
            page_count = content.count(b"obj") // 10  # Rough estimate

        logger.debug(f"PDF page count (fallback): {page_count}")
        return max(1, page_count)  # At least 1 page

    except Exception as e:
        logger.error(f"Failed to get page count for {file_path}: {str(e)}")
        raise ValueError(f"Cannot determine page count: {str(e)}")


def detect_scanned_pages(file_path: Path, page_count: int) -> tuple[list[int], bool]:
    """
    Detect which pages in a PDF are scanned (no text layer, image-heavy).

    Args:
        file_path: Path to PDF file
        page_count: Total number of pages

    Returns:
        Tuple of (scanned_page_numbers, has_text_layer)
        - scanned_page_numbers: List of page numbers (1-indexed) that appear to be scanned
        - has_text_layer: True if PDF has embedded text layer on at least one page

    Strategy:
        1. Check each page for extractable text
        2. If text length < 50 chars AND page has images → likely scanned
        3. has_text_layer = True if ANY page has significant text
    """
    scanned_pages = []
    has_any_text = False

    try:
        # Try using PyMuPDF (fitz) for more accurate detection
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)

            for page_num in range(min(page_count, len(doc))):
                page = doc[page_num]

                # Extract text from page
                text = page.get_text().strip()
                text_length = len(text)

                # Check for images on page
                image_list = page.get_images()
                has_images = len(image_list) > 0

                # Heuristic: scanned if very little text but has images
                if text_length < 50 and has_images:
                    scanned_pages.append(page_num + 1)  # 1-indexed
                    logger.debug(f"Page {page_num + 1}: Detected as scanned (text={text_length} chars, images={len(image_list)})")
                elif text_length >= 50:
                    has_any_text = True
                    logger.debug(f"Page {page_num + 1}: Has text layer ({text_length} chars)")

            doc.close()

        except ImportError:
            logger.warning("PyMuPDF (fitz) not available, using PyPDF2 for scanned page detection")

            # Fallback to PyPDF2
            import PyPDF2

            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)

                for page_num in range(min(page_count, len(reader.pages))):
                    page = reader.pages[page_num]

                    # Extract text
                    text = page.extract_text().strip()
                    text_length = len(text)

                    # PyPDF2 doesn't easily expose images, so use text-only heuristic
                    if text_length < 30:
                        scanned_pages.append(page_num + 1)  # 1-indexed
                        logger.debug(f"Page {page_num + 1}: Possibly scanned (text={text_length} chars)")
                    else:
                        has_any_text = True

        logger.info(f"Scanned page detection: {len(scanned_pages)} scanned pages out of {page_count}")

        return scanned_pages, has_any_text

    except Exception as e:
        logger.warning(f"Failed to detect scanned pages: {e}")
        # Conservative fallback: assume no scanned pages
        return [], True


def detect_toc_pages(file_path: Path, page_count: int, max_search_pages: int = 10) -> Tuple[Tuple[int, int], float]:
    """
    Detect Table of Contents page range in PDF.

    Args:
        file_path: Path to PDF file
        page_count: Total number of pages
        max_search_pages: Maximum pages to search for TOC (default: 10)

    Returns:
        Tuple of ((start_page, end_page), confidence)
        - start_page: 1-indexed first page of TOC (0 if not found)
        - end_page: 1-indexed last page of TOC (0 if not found)
        - confidence: 0.0-1.0 confidence score

    Strategy:
        1. Search first max_search_pages for TOC indicators
        2. Look for "Table of Contents" heading
        3. Detect page number patterns aligned right
        4. Identify dot leaders (.... or . . .)
        5. Return range with confidence score
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        search_pages = min(max_search_pages, page_count, len(doc))

        toc_indicators = []

        for page_num in range(search_pages):
            page = doc[page_num]
            text = page.get_text().lower()

            # Confidence factors
            confidence = 0.0
            indicators = []

            # 1. "Table of Contents" heading (strong indicator)
            if "table of contents" in text or "contents" in text[:500]:  # Check first 500 chars
                confidence += 0.4
                indicators.append("toc_heading")

            # 2. Multiple page number patterns (strong indicator)
            # Look for patterns like "... 23" or "........ 45" at end of lines
            import re
            page_number_patterns = re.findall(r'[\.\s]{3,}\d{1,4}$', text, re.MULTILINE)
            if len(page_number_patterns) >= 5:
                confidence += 0.3
                indicators.append(f"page_numbers_x{len(page_number_patterns)}")

            # 3. Dot leaders (moderate indicator)
            dot_leaders = re.findall(r'\.{3,}|(?:\.\s){3,}', text)
            if len(dot_leaders) >= 5:
                confidence += 0.2
                indicators.append(f"dot_leaders_x{len(dot_leaders)}")

            # 4. Numbered/lettered list structure (moderate indicator)
            # Look for patterns like "1.", "1.1", "I.", "A."
            structured_numbering = re.findall(r'^[\dIVXivx]+[\.\)]\s+|^[A-Z][\.\)]\s+', text, re.MULTILINE)
            if len(structured_numbering) >= 5:
                confidence += 0.15
                indicators.append(f"numbering_x{len(structured_numbering)}")

            # 5. Chapter/Section keywords (weak indicator)
            chapter_keywords = ["chapter", "section", "part", "appendix"]
            keyword_count = sum(text.count(kw) for kw in chapter_keywords)
            if keyword_count >= 3:
                confidence += 0.1
                indicators.append(f"keywords_x{keyword_count}")

            if confidence > 0.3:  # Threshold for TOC detection
                toc_indicators.append({
                    "page": page_num + 1,  # 1-indexed
                    "confidence": min(confidence, 1.0),
                    "indicators": indicators
                })
                logger.debug(f"Page {page_num + 1}: TOC indicators detected (confidence={confidence:.2f}): {indicators}")

        doc.close()

        # Determine TOC range from indicators
        if not toc_indicators:
            logger.info("No TOC pages detected")
            return ((0, 0), 0.0)

        # Find contiguous range of high-confidence pages
        toc_indicators.sort(key=lambda x: x["page"])

        # Start with highest confidence page
        best_page = max(toc_indicators, key=lambda x: x["confidence"])
        start_page = best_page["page"]
        end_page = start_page
        avg_confidence = best_page["confidence"]

        # Extend range to contiguous pages with confidence > 0.3
        for indicator in toc_indicators:
            if indicator["page"] == end_page + 1 and indicator["confidence"] > 0.3:
                end_page = indicator["page"]
                avg_confidence = (avg_confidence + indicator["confidence"]) / 2

        logger.info(f"TOC detected: pages {start_page}-{end_page} (confidence={avg_confidence:.2f})")

        return ((start_page, end_page), avg_confidence)

    except ImportError:
        logger.warning("PyMuPDF not available, cannot detect TOC pages")
        return ((0, 0), 0.0)

    except Exception as e:
        logger.warning(f"Failed to detect TOC pages: {e}")
        return ((0, 0), 0.0)


def check_existing_ingestion(file_sha: str, page_count: int, env_root: Path) -> Optional[Tuple[str, int]]:
    """
    Check if file has already been ingested by querying vector store.

    This is the proper way to check for duplicates - query the database where
    chunks are stored with source_hash metadata, rather than scanning log files.

    Args:
        file_sha: SHA-256 hash of file
        page_count: Number of pages in PDF
        env_root: Environment root directory

    Returns:
        Tuple of (source_hash, chunk_count) if found, None otherwise
    """
    logger.info(f"Checking vector store for existing ingestion: sha={file_sha[:12]}..., pages={page_count}")

    try:
        # Import vector store factory
        from .vector_store.factory import make_vector_store
        from .environment_isolation import get_environment_validator

        # Get environment name
        env_validator = get_environment_validator()
        env = env_validator.environment_name

        # Get vector store instance
        vector_store = make_vector_store(env)

        # Check if this source_hash already has chunks in the database
        chunk_count = vector_store.count_documents_for_source(file_sha, env)

        if chunk_count > 0:
            logger.info(f"Found existing ingestion: sha={file_sha[:12]}..., chunks={chunk_count}")
            return (file_sha, chunk_count)
        else:
            logger.info(f"No existing ingestion found for sha={file_sha[:12]}...")
            return None

    except Exception as e:
        logger.warning(f"Failed to check vector store for duplicates: {str(e)}")
        logger.info("Proceeding with ingestion due to dedup check failure")
        return None


def create_noop_job_record(file_path: Path, existing_job_id: str,
                          file_sha: str, page_count: int, env_root: Path) -> str:
    """
    Create a no-op job record for skipped ingestion.

    Args:
        file_path: Original file path
        existing_job_id: ID of existing job with same content
        file_sha: SHA-256 hash of file
        page_count: Page count
        env_root: Environment root directory

    Returns:
        New job_id for the no-op record
    """
    import uuid
    from datetime import datetime

    noop_job_id = f"noop-{uuid.uuid4().hex[:8]}"
    noop_job_dir = env_root / "artifacts" / noop_job_id
    noop_job_dir.mkdir(parents=True, exist_ok=True)

    noop_record = {
        "job_id": noop_job_id,
        "status": "skipped",
        "reason": "duplicate_content",
        "source_file": str(file_path),
        "source_file_sha": file_sha,
        "source_page_count": page_count,
        "existing_job_id": existing_job_id,
        "created_at": datetime.utcnow().isoformat(),
        "pass_0_preflight": {
            "duplicate_detected": True,
            "original_job": existing_job_id,
            "skip_reason": "Identical content already processed"
        }
    }

    # Write no-op manifest
    manifest_path = noop_job_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(noop_record, f, indent=2)

    logger.info(f"Created no-op job record: {noop_job_id}")
    return noop_job_id


def run_preflight_checks(file_path: Path, log_file_path: Optional[Path] = None) -> PreflightResult:
    """
    Run Pass 0 preflight checks for a file.

    Args:
        file_path: Path to file to check

    Returns:
        PreflightResult with skip decision and metadata

    Raises:
        OSError: If file cannot be accessed
        ValueError: If file is not valid
    """
    import time
    started_at = time.perf_counter()

    # Pass start logging
    file_size_mb = file_path.stat().st_size / 1024 / 1024
    log_pass_start("0", f"Preflight & Deduplication - {file_path.name} ({file_size_mb:.2f} MB)", log_file_path)

    logger.info(f"Pass 0: Starting preflight checks for {file_path.name}")
    logger.info(f"  File size: {file_size_mb:.2f} MB")

    # Validate file exists and is readable
    if not file_path.exists():
        raise OSError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise OSError(f"Path is not a file: {file_path}")

    # Validate OCR dependencies (tesseract, poppler, tessdata)
    logger.info(f"Pass 0: Validating OCR dependencies...")
    log_to_job("Validating OCR dependencies (tesseract, poppler, tessdata)...", log_file_path, "info", "0")
    try:
        from .ocr_validator import OCRValidator
        ocr_validator = OCRValidator()
        ocr_valid = ocr_validator.validate_all()

        if ocr_valid:
            log_to_job("✓ All OCR dependencies available", log_file_path, "info", "0")
        else:
            missing = [c.name for c in ocr_validator.checks if not c.available]
            log_to_job(f"⚠ OCR dependencies missing: {', '.join(missing)} - OCR fallback may fail", log_file_path, "warning", "0")
    except Exception as e:
        logger.warning(f"OCR validation failed: {e}")
        log_to_job(f"⚠ OCR validation failed: {e}", log_file_path, "warning", "0")

    # Get environment root for artifact checking
    env_validator = get_environment_validator()
    env_root = Path(env_validator.get_environment_root())

    try:
        # Compute file SHA
        logger.info(f"Pass 0: Computing SHA-256 checksum...")
        log_to_job("Computing SHA-256 checksum...", log_file_path, "info", "0")
        sha_start = time.perf_counter()
        file_sha = compute_file_sha(file_path)
        sha_duration = time.perf_counter() - sha_start
        logger.info(f"  Checksum: {file_sha[:16]}... (computed in {sha_duration:.2f}s)")
        log_to_job(f"Checksum: {file_sha[:16]}... (computed in {sha_duration:.2f}s)", log_file_path, "info", "0")

        # Get page count (assuming PDF for now)
        if file_path.suffix.lower() == '.pdf':
            logger.info(f"Pass 0: Extracting PDF page count...")
            page_count = get_pdf_page_count(file_path)
            logger.info(f"  Page count: {page_count} pages")

            # Detect scanned pages
            logger.info(f"Pass 0: Detecting scanned pages...")
            log_to_job("Detecting scanned pages (image-heavy, no text layer)...", log_file_path, "info", "0")
            scanned_pages, has_text_layer = detect_scanned_pages(file_path, page_count)

            if scanned_pages:
                logger.info(f"  Scanned pages detected: {len(scanned_pages)}/{page_count} pages")
                logger.info(f"  Scanned page numbers: {scanned_pages[:10]}{'...' if len(scanned_pages) > 10 else ''}")
                log_to_job(f"⚠ Found {len(scanned_pages)} scanned pages (will require OCR)", log_file_path, "warning", "0")
            else:
                logger.info(f"  No scanned pages detected - all pages have text layer")
                log_to_job("✓ All pages have text layer", log_file_path, "info", "0")

            logger.info(f"  Has text layer: {has_text_layer}")

            # Detect TOC pages (for Pass A TOC-only extraction)
            logger.info(f"Pass 0: Detecting Table of Contents pages...")
            log_to_job("Detecting Table of Contents pages...", log_file_path, "info", "0")
            toc_pages, toc_confidence = detect_toc_pages(file_path, page_count)

            if toc_pages[0] > 0:
                logger.info(f"  TOC detected: pages {toc_pages[0]}-{toc_pages[1]} (confidence={toc_confidence:.2f})")
                log_to_job(f"✓ TOC found: pages {toc_pages[0]}-{toc_pages[1]} (confidence={toc_confidence:.0%})", log_file_path, "info", "0")
            else:
                logger.info(f"  No TOC detected")
                log_to_job("⚠ No TOC detected - Pass A will use heading fallback", log_file_path, "warning", "0")

            # HARD FAIL: If scanned pages exist but OCR is not ready, fail the job
            if scanned_pages and not ocr_valid:
                missing_deps = [c.name for c in ocr_validator.checks if not c.available]
                error_msg = f"OCR_DEPENDENCY_MISSING: Found {len(scanned_pages)} scanned pages but OCR dependencies are missing: {', '.join(missing_deps)}"
                logger.error(f"Pass 0: {error_msg}")
                log_to_job(f"🚨 HARD FAIL: {error_msg}", log_file_path, "error", "0")
                log_to_job(f"  Scanned pages: {scanned_pages[:10]}{'...' if len(scanned_pages) > 10 else ''}", log_file_path, "error", "0")
                log_to_job(f"  Missing dependencies: {', '.join(missing_deps)}", log_file_path, "error", "0")

                # Raise error to fail the job (errors.jsonl will be emitted by caller with job_id)
                raise RuntimeError(error_msg)

        else:
            logger.warning(f"Non-PDF file: {file_path}, using page count = 1")
            page_count = 1
            scanned_pages = []
            has_text_layer = True
            toc_pages = (0, 0)
            toc_confidence = 0.0

        # Check for existing ingestion in vector store
        logger.info(f"Pass 0: Checking for duplicate content in vector store...")
        log_to_job("Checking for duplicate content in vector store...", log_file_path, "info", "0")
        existing_result = check_existing_ingestion(file_sha, page_count, env_root)

        # Calculate duration
        duration_seconds = time.perf_counter() - started_at

        if existing_result:
            existing_sha, chunk_count = existing_result
            logger.info(f"Pass 0: ✓ DUPLICATE DETECTED")
            logger.info(f"  Existing chunks in database: {chunk_count}")
            logger.info(f"  Matching SHA: {existing_sha[:16]}...")
            logger.info(f"  Decision: SKIP ingestion (content already processed)")

            # Log completion
            stats = {
                "decision": "SKIP",
                "reason": "duplicate_content",
                "existing_chunks": chunk_count,
                "file_sha": file_sha[:12],
                "page_count": page_count,
                "scanned_pages": len(scanned_pages)
            }
            log_pass_complete("0", duration_seconds, stats, log_file_path)

            # Create no-op record and skip
            noop_job_id = create_noop_job_record(
                file_path, f"sha:{existing_sha[:12]}", file_sha, page_count, env_root
            )

            return PreflightResult(
                should_skip=True,
                reason=f"Duplicate content ({chunk_count} chunks already in database)",
                file_sha=file_sha,
                page_count=page_count,
                existing_job_id=f"sha:{existing_sha[:12]}",
                scanned_pages=scanned_pages,
                has_text_layer=has_text_layer,
                toc_pages=toc_pages,
                toc_confidence=toc_confidence
            )

        else:
            # New content, proceed with ingestion
            logger.info(f"Pass 0: ✓ NEW CONTENT DETECTED")
            logger.info(f"  No matching content in database")
            logger.info(f"  Decision: PROCEED with ingestion")

            # Log completion
            stats = {
                "decision": "PROCEED",
                "reason": "new_content",
                "file_sha": file_sha[:12],
                "page_count": page_count,
                "scanned_pages": len(scanned_pages),
                "has_text_layer": has_text_layer
            }
            log_pass_complete("0", duration_seconds, stats, log_file_path)

            return PreflightResult(
                should_skip=False,
                reason="New content",
                file_sha=file_sha,
                page_count=page_count,
                scanned_pages=scanned_pages,
                has_text_layer=has_text_layer,
                toc_pages=toc_pages,
                toc_confidence=toc_confidence
            )

    except Exception as e:
        logger.error(f"Preflight checks failed for {file_path}: {str(e)}")
        raise


def create_gate0_report(job_id: str, file_path: Path, preflight_result: PreflightResult,
                       job_dir: Path, ocr_validator=None) -> Dict[str, Any]:
    """
    Create gate0.report.json per AI prompt spec.

    Args:
        job_id: Job identifier (doc_id in spec)
        file_path: Source file path
        preflight_result: Results from preflight checks
        job_dir: Job artifact directory
        ocr_validator: OCRValidator instance (optional)

    Returns:
        gate0 report dictionary
    """
    from .ocr_validator import OCRValidator

    # Get OCR readiness
    if ocr_validator is None:
        ocr_validator = OCRValidator()
        ocr_validator.validate_all()

    # Extract tessdata languages from checks
    tessdata_langs = []
    for check in ocr_validator.checks:
        if check.name.endswith('.traineddata') and check.available:
            # Extract language code (e.g., 'eng' from 'eng.traineddata')
            lang = check.name.replace('.traineddata', '')
            tessdata_langs.append(lang)

    # Determine if OCR stack is ready
    tesseract_available = any(c.name == 'tesseract' and c.available for c in ocr_validator.checks)
    poppler_available = any(c.name == 'pdftotext' and c.available for c in ocr_validator.checks)
    ocr_ready = tesseract_available and poppler_available and len(tessdata_langs) > 0

    # Check for prior ingestion match
    prior_match = {
        "matched": preflight_result.should_skip,
        "existing_job_id": preflight_result.existing_job_id if preflight_result.should_skip else None
    }

    # Create gate0 report
    report = {
        "doc_id": job_id,
        "filename": file_path.name,
        "file_sha256": preflight_result.file_sha,
        "filesize_bytes": file_path.stat().st_size,
        "page_count": preflight_result.page_count,
        "scanned_pages": preflight_result.scanned_pages,
        "has_text_layer": preflight_result.has_text_layer,
        "toc_pages": {
            "start": preflight_result.toc_pages[0],
            "end": preflight_result.toc_pages[1],
            "confidence": preflight_result.toc_confidence
        },
        "ocr_readiness": {
            "tesseract": tesseract_available,
            "poppler": poppler_available,
            "tessdata_langs": tessdata_langs,
            "ready": ocr_ready
        },
        "prior_ingest_match": prior_match
    }

    # Write gate0.report.json
    pass_0_dir = job_dir / "pass_0"
    pass_0_dir.mkdir(parents=True, exist_ok=True)

    report_path = pass_0_dir / "gate0.report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Pass 0: Created gate0.report.json at {report_path}")

    return report


def create_preflight_manifest(job_id: str, file_path: Path,
                             preflight_result: PreflightResult, env_root: Path) -> Dict[str, Any]:
    """
    Create initial manifest with preflight results.

    Args:
        job_id: Job identifier
        file_path: Source file path
        preflight_result: Results from preflight checks
        env_root: Environment root directory

    Returns:
        Initial manifest dictionary
    """
    manifest = {
        "job_id": job_id,
        "source_file": str(file_path),
        "source_file_sha": preflight_result.file_sha,
        "source_page_count": preflight_result.page_count,
        "created_at": datetime.utcnow().isoformat(),
        "status": "preflight_complete",
        "pass_0_preflight": {
            "file_sha": preflight_result.file_sha,
            "page_count": preflight_result.page_count,
            "scanned_pages": preflight_result.scanned_pages,
            "has_text_layer": preflight_result.has_text_layer,
            "toc_pages": {
                "start": preflight_result.toc_pages[0],
                "end": preflight_result.toc_pages[1],
                "confidence": preflight_result.toc_confidence
            },
            "duplicate_check": "passed" if not preflight_result.should_skip else "duplicate",
            "reason": preflight_result.reason,
            "completed_at": datetime.utcnow().isoformat()
        }
    }

    return manifest


if __name__ == "__main__":
    # Test with a sample file
    import sys
    if len(sys.argv) > 1:
        test_file = Path(sys.argv[1])
        result = run_preflight_checks(test_file)
        print(f"Preflight result: skip={result.should_skip}, reason={result.reason}")
        print(f"SHA: {result.file_sha}")
        print(f"Pages: {result.page_count}")