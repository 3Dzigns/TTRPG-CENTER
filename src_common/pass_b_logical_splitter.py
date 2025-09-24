# src_common/pass_b_logical_splitter.py
"""
Pass B: Fast Split (≤10 MB parts) - MVP v2

Split large PDFs (>10 MB) by logical sections (chapters/parts) guided by
Pass A's ToC analysis. Skip splitting for smaller files.
MVP v2 requirement: 10MB split threshold for Pass 0→G pipeline.

Responsibilities:
- Check file size threshold (10 MB)
- Split large PDFs by logical sections using ToC guidance
- Generate split index mapping sections to parts
- Update job manifest with split information
- No chunk upserts, only manifest updates

Artifacts:
- *_parts/*.pdf: Split PDF parts by logical sections
- split_index.json: Maps sections to parts with content hashes
- manifest.json: Updated with split information
"""

import json
import time
import hashlib
import shutil
import gc
import psutil
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import pypdf

from .ttrpg_logging import get_logger
from .artifact_validator import write_json_atomically, load_json_with_retry

logger = get_logger(__name__)

# 10 MB threshold for splitting (MVP v2 requirement)
SPLIT_THRESHOLD_BYTES = 10 * 1024 * 1024


@dataclass
class SplitPart:
    """Information about a split PDF part"""
    part_name: str
    page_start: int
    page_end: int
    section_titles: List[str]
    file_path: str
    file_size: int
    content_hash: str


@dataclass
class PassBResult:
    """Result of Pass B logical splitting"""
    source_file: str
    job_id: str
    split_performed: bool
    parts_created: int
    total_pages: int
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    error_message: Optional[str] = None


class PassBLogicalSplitter:
    """Pass B: Logical Split for large PDFs"""

    def __init__(self, job_id: str, env: str = "dev", job_log_file: Optional[Path] = None):
        self.job_id = job_id
        self.env = env
        self.job_log_file = job_log_file

    def _log_status(self, message: str, level: str = "INFO") -> None:
        """Log to both container logs and job log file for observability"""
        # Always log to container logs
        if level == "INFO":
            logger.info(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "DEBUG":
            logger.debug(message)

        # Also write to job log file if available
        if self.job_log_file:
            try:
                from datetime import datetime
                timestamp = datetime.now().isoformat()
                job_log_entry = f"[{timestamp}] {message}"
                with open(self.job_log_file, 'a', encoding='utf-8') as f:
                    f.write(job_log_entry + "\n")
                    f.flush()  # Ensure immediate write for observability
            except Exception as e:
                logger.warning(f"Failed to write to job log file: {e}")

    def process_pdf(self, pdf_path: Path, output_dir: Path, pass_a_manifest: Optional[Path] = None) -> PassBResult:
        """
        Process PDF for Pass B: Logical splitting if needed
        
        Args:
            pdf_path: Path to source PDF
            output_dir: Directory for output artifacts  
            pass_a_manifest: Path to Pass A manifest for ToC guidance
            
        Returns:
            PassBResult with processing statistics
        """
        start_time = time.time()
        self._log_status(f"Pass B starting: Logical split check for {pdf_path.name}")
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check file size
            file_size = pdf_path.stat().st_size
            self._log_status(f"PDF size: {file_size / (1024*1024):.1f} MB (threshold: {SPLIT_THRESHOLD_BYTES / (1024*1024):.1f} MB)")

            if file_size <= SPLIT_THRESHOLD_BYTES:
                self._log_status("PDF below split threshold, skipping logical split")
                return self._create_no_split_result(pdf_path, output_dir, start_time)
            
            # Load Pass A manifest for ToC guidance
            toc_sections = []
            if pass_a_manifest and pass_a_manifest.exists():
                try:
                    pass_a_data = load_json_with_retry(pass_a_manifest)
                    # Extract section information from Pass A dictionary entries
                    if "pass_a_results" in pass_a_data:
                        pass_a_dict_path = output_dir / f"{self.job_id}_pass_a_dict.json"
                        if pass_a_dict_path.exists():
                            dict_data = load_json_with_retry(pass_a_dict_path)
                            toc_sections = self._extract_toc_sections(dict_data)
                    self._log_status(f"Loaded {len(toc_sections)} ToC sections from Pass A")
                except Exception as e:
                    self._log_status(f"Failed to load Pass A guidance: {e}", "WARNING")
            
            # Perform logical split
            split_parts = self._perform_logical_split(pdf_path, output_dir, toc_sections)
            
            if not split_parts:
                # For large PDFs, treat split failure as a hard failure so downstream passes are skipped
                raise RuntimeError("Logical split produced no parts for large PDF")
            
            # Generate split index with status updates
            self._log_status(f"Pass B: Generating split index for {len(split_parts)} parts...")
            index_start_time = time.time()
            split_index_path = self._generate_split_index(output_dir, split_parts)
            index_duration = time.time() - index_start_time
            self._log_status(f"Pass B: Split index generated in {index_duration:.1f}s")

            # Update manifest with status updates
            self._log_status(f"Pass B: Updating manifest with split information...")
            manifest_start_time = time.time()
            manifest_path = self._update_manifest(output_dir, pdf_path, split_parts, split_index_path)
            manifest_duration = time.time() - manifest_start_time
            self._log_status(f"Pass B: Manifest updated in {manifest_duration:.1f}s")
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            total_processing_time = end_time - start_time

            artifacts = [str(split_index_path)] + [part.file_path for part in split_parts]
            total_output_size = sum(Path(part.file_path).stat().st_size for part in split_parts)

            self._log_status(f"Pass B ✓ COMPLETED: Split {pdf_path.name} into {len(split_parts)} parts")
            self._log_status(f"Pass B Summary: {total_pages} pages → {len(split_parts)} parts, "
                           f"{total_output_size / (1024*1024):.1f} MB output, {total_processing_time:.1f}s total")
            self._log_status(f"Pass B Artifacts: {len(artifacts)} files created in {output_dir}")
            
            return PassBResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                split_performed=True,
                parts_created=len(split_parts),
                total_pages=sum(part.page_end - part.page_start + 1 for part in split_parts),
                processing_time_ms=processing_time_ms,
                artifacts=artifacts,
                manifest_path=str(manifest_path),
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass B failed for {pdf_path.name}: {e}")
            
            return PassBResult(
                source_file=pdf_path.name,
                job_id=self.job_id,
                split_performed=False,
                parts_created=0,
                total_pages=0,
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )
    
    def _create_no_split_result(self, pdf_path: Path, output_dir: Path, start_time: float) -> PassBResult:
        """Create result for PDFs that don't need splitting"""
        
        # Update manifest to indicate no split was needed
        manifest_path = self._update_manifest(output_dir, pdf_path, [], None)
        
        end_time = time.time()
        processing_time_ms = int((end_time - start_time) * 1000)
        
        # Get total pages for reporting
        total_pages = 0
        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                total_pages = len(reader.pages)
        except Exception as e:
            logger.warning(f"Failed to get page count: {e}")
        
        return PassBResult(
            source_file=pdf_path.name,
            job_id=self.job_id,
            split_performed=False,
            parts_created=0,
            total_pages=total_pages,
            processing_time_ms=processing_time_ms,
            artifacts=[],
            manifest_path=str(manifest_path),
            success=True
        )
    
    def _extract_toc_sections(self, dict_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract ToC sections from Pass A dictionary data"""
        sections = []
        
        for entry in dict_data.get("dictionary_entries", []):
            if entry.get("sources"):
                source = entry["sources"][0]
                sections.append({
                    "title": entry.get("term", ""),
                    "page": source.get("page", 1),
                    "level": source.get("level", 1),
                    "section_id": source.get("section_id", "")
                })
        
        # Sort by page number
        sections.sort(key=lambda x: x["page"])
        return sections
    
    def _perform_logical_split(
        self,
        pdf_path: Path,
        output_dir: Path,
        toc_sections: List[Dict[str, Any]]
    ) -> List[SplitPart]:
        """Perform logical splitting based on ToC sections with memory optimization"""

        parts = []
        parts_dir = output_dir / f"{self.job_id}_parts"
        parts_dir.mkdir(exist_ok=True)

        # Monitor memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        max_memory_threshold = initial_memory + 750  # 750MB increase limit
        self._log_status(f"Pass B: Starting logical split, initial memory: {initial_memory:.1f} MB, threshold: {max_memory_threshold:.1f} MB")

        # Setup timeout for very large files (30 minutes max)
        start_time = time.time()
        timeout_seconds = 30 * 60  # 30 minutes

        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                total_pages = len(reader.pages)
                self._log_status(f"Pass B: PDF loaded, total pages: {total_pages}")

                # Check memory after loading PDF
                memory_after_load = process.memory_info().rss / 1024 / 1024
                self._log_status(f"Pass B: Memory after PDF load: {memory_after_load:.1f} MB (+{memory_after_load - initial_memory:.1f} MB)")

                # Determine split points based on ToC with status updates
                self._log_status(f"Pass B: Analyzing ToC structure for {len(toc_sections)} sections...")
                split_points = self._calculate_split_points(toc_sections, total_pages)
                self._log_status(f"Pass B: Calculated {len(split_points)} logical split points")

                # Log split point details for transparency
                for i, (start_page, end_page, section_titles) in enumerate(split_points, 1):
                    page_count = end_page - start_page + 1
                    self._log_status(f"Pass B: Part {i}: pages {start_page}-{end_page} ({page_count} pages) - {len(section_titles)} sections")
                    if section_titles:
                        self._log_status(f"Pass B: Part {i} sections: {', '.join(section_titles[:3])}{'...' if len(section_titles) > 3 else ''}", "DEBUG")

                for i, (start_page, end_page, section_titles) in enumerate(split_points, 1):
                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        raise TimeoutError(f"Pass B splitting timed out after {timeout_seconds} seconds")

                    part_start_time = time.time()
                    part_name = f"part_{i:03d}"
                    part_filename = f"{self.job_id}_{part_name}.pdf"
                    part_path = parts_dir / part_filename

                    self._log_status(f"Pass B: Creating part {i}/{len(split_points)}: {part_name} (pages {start_page}-{end_page})")

                    # Create PDF writer for this part
                    writer = pypdf.PdfWriter()

                    # Add pages to this part with progress tracking and memory management
                    page_count = min(end_page, total_pages) - (start_page - 1)
                    pages_processed = 0

                    for idx, page_num in enumerate(range(start_page - 1, min(end_page, total_pages))):
                        # Timeout check for individual part
                        if time.time() - part_start_time > 300:  # 5 minute timeout per part
                            raise TimeoutError(f"Part {part_name} timed out after 5 minutes")

                        # Progress logging every 10 pages for better observability
                        if idx % 10 == 0:
                            elapsed = time.time() - part_start_time
                            total_elapsed = time.time() - start_time
                            progress_pct = (idx + 1) / page_count * 100
                            est_part_time = elapsed / (idx + 1) * page_count if idx > 0 else 0

                            self._log_status(f"Pass B: Part {i}/{len(split_points)} - processing page {page_num + 1} "
                                        f"({idx + 1}/{page_count}, {progress_pct:.1f}%) "
                                        f"[{elapsed:.1f}s elapsed, est. {est_part_time:.1f}s total, overall {total_elapsed:.1f}s]")

                        try:
                            # Clone page to avoid sharing resources
                            page = reader.pages[page_num]
                            writer.add_page(page)
                            pages_processed += 1

                        except Exception as page_error:
                            logger.warning(f"Pass B: Failed to process page {page_num + 1}: {page_error}")
                            continue

                        # Memory management every 25 pages with status updates
                        if idx % 25 == 0 and idx > 0:
                            current_memory = process.memory_info().rss / 1024 / 1024
                            logger.debug(f"Pass B: Memory check at page {page_num + 1}: {current_memory:.1f} MB")

                            if current_memory > max_memory_threshold:
                                logger.warning(f"Pass B: High memory usage: {current_memory:.1f} MB, forcing cleanup")
                                gc.collect()

                                # Check memory again after cleanup
                                post_gc_memory = process.memory_info().rss / 1024 / 1024
                                logger.info(f"Pass B: Memory after cleanup: {post_gc_memory:.1f} MB (freed {current_memory - post_gc_memory:.1f} MB)")

                                # If still too high, consider this a memory limit breach
                                if post_gc_memory > max_memory_threshold + 100:
                                    raise MemoryError(f"Memory usage too high: {post_gc_memory:.1f} MB")

                    # Ensure we processed some pages
                    if pages_processed == 0:
                        logger.warning(f"Pass B: No pages processed for part {part_name}, skipping")
                        continue

                    # Write part PDF with retry logic and status updates
                    self._log_status(f"Pass B: Writing part {part_name} with {pages_processed} pages to disk...")
                    write_start_time = time.time()
                    part_written = False

                    for attempt in range(3):
                        try:
                            with open(part_path, "wb") as part_file:
                                writer.write(part_file)
                            part_written = True
                            write_duration = time.time() - write_start_time
                            self._log_status(f"Pass B: Successfully wrote {part_name} in {write_duration:.1f}s")
                            break
                        except Exception as write_error:
                            logger.warning(f"Pass B: Write attempt {attempt + 1} failed for {part_name}: {write_error}")
                            if attempt < 2:  # Not the last attempt
                                time.sleep(1)  # Brief delay before retry
                                gc.collect()

                    if not part_written:
                        logger.error(f"Pass B: Failed to write part {part_name} after 3 attempts")
                        continue

                    # Calculate file info with status updates
                    file_size = part_path.stat().st_size
                    self._log_status(f"Pass B: Computing hash for {part_name} ({file_size / (1024*1024):.1f} MB)...")
                    hash_start_time = time.time()
                    content_hash = self._compute_file_hash(part_path)
                    hash_duration = time.time() - hash_start_time
                    self._log_status(f"Pass B: Hash computed for {part_name} in {hash_duration:.1f}s", "DEBUG")

                    part = SplitPart(
                        part_name=part_name,
                        page_start=start_page,
                        page_end=min(end_page, total_pages),
                        section_titles=section_titles,
                        file_path=str(part_path),
                        file_size=file_size,
                        content_hash=content_hash
                    )
                    parts.append(part)

                    part_duration = time.time() - part_start_time
                    total_elapsed = time.time() - start_time
                    remaining_parts = len(split_points) - i
                    avg_part_time = total_elapsed / i
                    est_remaining_time = avg_part_time * remaining_parts

                    self._log_status(f"Pass B: ✓ Completed part {part_name}: pages {start_page}-{min(end_page, total_pages)} "
                                   f"({pages_processed} pages, {file_size / (1024*1024):.1f} MB, {part_duration:.1f}s)")
                    self._log_status(f"Pass B: Progress: {i}/{len(split_points)} parts complete "
                                   f"({i/len(split_points)*100:.1f}%), est. {est_remaining_time:.1f}s remaining")

                    # Force cleanup between parts for large files
                    logger.debug(f"Pass B: Cleaning up resources before next part...")
                    del writer
                    gc.collect()

        except (TimeoutError, MemoryError) as e:
            logger.error(f"Pass B: Resource limit exceeded: {e}")
            # Clean up any partial files
            if parts_dir.exists():
                shutil.rmtree(parts_dir, ignore_errors=True)
            return []
        except Exception as e:
            logger.error(f"Pass B: Failed to split PDF: {e}")
            # Clean up any partial files
            if parts_dir.exists():
                shutil.rmtree(parts_dir, ignore_errors=True)
            return []
        finally:
            # Final memory report
            final_memory = process.memory_info().rss / 1024 / 1024
            total_time = time.time() - start_time
            logger.info(f"Pass B: Splitting completed, final memory: {final_memory:.1f} MB, total time: {total_time:.1f}s")

        return parts
    
    def _calculate_split_points(
        self, 
        toc_sections: List[Dict[str, Any]], 
        total_pages: int
    ) -> List[Tuple[int, int, List[str]]]:
        """Calculate logical split points based on ToC structure"""
        
        if not toc_sections:
            # Fallback: split into equal chunks
            chunk_size = max(50, total_pages // 4)  # At least 50 pages per chunk
            split_points = []
            for i in range(0, total_pages, chunk_size):
                start = i + 1
                end = min(i + chunk_size, total_pages)
                split_points.append((start, end, [f"Pages {start}-{end}"]))
            return split_points
        
        # Use ToC structure for logical splits
        split_points = []
        major_sections = [s for s in toc_sections if s.get("level", 1) <= 2]  # Top-level sections
        
        if not major_sections:
            major_sections = toc_sections[:10]  # Use first 10 sections
        
        # Group sections into logical parts
        current_start = 1
        current_titles = []
        
        for i, section in enumerate(major_sections):
            section_page = section.get("page", 1)
            section_title = section.get("title", "")
            
            # Start new part if we have enough pages or this is a major boundary
            if (section_page - current_start >= 30) and current_titles:
                split_points.append((current_start, section_page - 1, current_titles[:]))
                current_start = section_page
                current_titles = [section_title]
            else:
                current_titles.append(section_title)
        
        # Add final part
        if current_titles:
            split_points.append((current_start, total_pages, current_titles))
        
        # Ensure we don't have tiny parts
        filtered_points = []
        for start, end, titles in split_points:
            if end - start + 1 >= 10:  # At least 10 pages
                filtered_points.append((start, end, titles))
            elif filtered_points:
                # Merge small part with previous
                prev_start, prev_end, prev_titles = filtered_points[-1]
                filtered_points[-1] = (prev_start, end, prev_titles + titles)
        
        return filtered_points or [(1, total_pages, ["Complete Document"])]
    
    def _generate_split_index(self, output_dir: Path, split_parts: List[SplitPart]) -> Path:
        """Generate split_index.json mapping sections to parts"""
        
        split_index = {
            "job_id": self.job_id,
            "created_at": time.time(),
            "parts_count": len(split_parts),
            "total_pages": sum(part.page_end - part.page_start + 1 for part in split_parts),
            "chunks": [],  # BUG-016: Always include chunks key for schema validation
            "parts": [
                {
                    "part_name": part.part_name,
                    "file_name": Path(part.file_path).name,
                    "file_path": part.file_path,
                    "page_start": part.page_start,
                    "page_end": part.page_end,
                    "page_count": part.page_end - part.page_start + 1,
                    "section_titles": part.section_titles,
                    "file_size": part.file_size,
                    "content_hash": part.content_hash
                }
                for part in split_parts
            ]
        }
        
        split_index_path = output_dir / "split_index.json"
        write_json_atomically(split_index, split_index_path)
        
        return split_index_path
    
    def _update_manifest(
        self, 
        output_dir: Path, 
        pdf_path: Path, 
        split_parts: List[SplitPart],
        split_index_path: Optional[Path]
    ) -> Path:
        """Update manifest.json with Pass B results"""
        
        manifest_path = output_dir / "manifest.json"
        
        # Load existing manifest from Pass A if available
        manifest_data = {}
        if manifest_path.exists():
            try:
                manifest_data = load_json_with_retry(manifest_path)
            except Exception as e:
                logger.warning(f"Failed to load existing manifest: {e}")
        
        # Get actual PDF page count for reporting
        actual_total_pages = 0
        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                actual_total_pages = len(reader.pages)
        except Exception as e:
            logger.warning(f"Failed to get page count for manifest: {e}")

        # Update with Pass B information
        manifest_data.update({
            "completed_passes": list(set(manifest_data.get("completed_passes", []) + ["B"])),
            "chunks": manifest_data.get("chunks", []),  # BUG-016: Ensure chunks key exists
            "pass_b_results": {
                "split_performed": len(split_parts) > 0,
                "parts_created": len(split_parts),
                "split_threshold_mb": SPLIT_THRESHOLD_BYTES / (1024*1024),
                "source_size_mb": (pdf_path.stat().st_size / (1024*1024)) if pdf_path.exists() else 0,
                "total_pages": actual_total_pages
            }
        })
        
        # Add split artifacts
        if split_index_path:
            split_artifacts = [{
                "file": "split_index.json",
                "path": str(split_index_path),
                "size": split_index_path.stat().st_size,
                "mtime": split_index_path.stat().st_mtime,
                "checksum": self._compute_file_hash(split_index_path)
            }]
            
            # Add part files
            for part in split_parts:
                part_path = Path(part.file_path)
                split_artifacts.append({
                    "file": part_path.name,
                    "path": part.file_path,
                    "size": part.file_size,
                    "mtime": part_path.stat().st_mtime if part_path.exists() else 0,
                    "checksum": part.content_hash
                })
            
            manifest_data["artifacts"] = manifest_data.get("artifacts", []) + split_artifacts
        
        # Write updated manifest
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


def process_pass_b(
    pdf_path: Path,
    output_dir: Path,
    job_id: str,
    env: str = "dev",
    pass_a_manifest: Optional[Path] = None,
    job_log_file: Optional[Path] = None
) -> PassBResult:
    """
    Convenience function for Pass B processing
    
    Args:
        pdf_path: Path to source PDF
        output_dir: Directory for output artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        pass_a_manifest: Path to Pass A manifest for ToC guidance
        
    Returns:
        PassBResult with processing statistics
    """
    splitter = PassBLogicalSplitter(job_id, env, job_log_file)
    return splitter.process_pdf(pdf_path, output_dir, pass_a_manifest)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass B: Logical Split for large PDFs")
    parser.add_argument("pdf_path", help="Path to source PDF")
    parser.add_argument("output_dir", help="Output directory for artifacts")
    parser.add_argument("--job-id", help="Job ID (default: auto-generated)")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    parser.add_argument("--pass-a-manifest", help="Path to Pass A manifest for ToC guidance")
    
    args = parser.parse_args()
    
    pdf_path = Path(args.pdf_path)
    output_dir = Path(args.output_dir)
    job_id = args.job_id or f"job_{int(time.time())}"
    pass_a_manifest = Path(args.pass_a_manifest) if args.pass_a_manifest else None
    
    result = process_pass_b(pdf_path, output_dir, job_id, args.env, pass_a_manifest)
    
    print(f"Pass B Result:")
    print(f"  Success: {result.success}")
    print(f"  Split performed: {result.split_performed}")
    print(f"  Parts created: {result.parts_created}")
    print(f"  Total pages: {result.total_pages}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)
