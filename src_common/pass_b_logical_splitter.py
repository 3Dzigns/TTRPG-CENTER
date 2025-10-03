"""Pass B logical splitter for MVP v2 ingestion pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

from pypdf import PdfReader, PdfWriter

from src_common.config import ConfigManager
from src_common.logging import get_logger

try:
    from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete, log_heartbeat
except ImportError:  # pragma: no cover - legacy runtime fallback
    from datetime import datetime

    def _fallback_write(message: str, log_file_path=None) -> None:
        if not log_file_path:
            return
        try:
            path_obj = Path(log_file_path)
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            with path_obj.open('a', encoding='utf-8') as handle:
                handle.write(message + "\n")
        except Exception:
            return

    def log_to_job(message: str, log_file_path=None, level: str = 'info', pass_name: str | None = None) -> None:
        timestamp = datetime.now().isoformat()
        prefix = f"[{timestamp}] "
        if pass_name:
            prefix += f"Pass {pass_name}: "
        _fallback_write(prefix + message, log_file_path)

    def log_pass_start(pass_name: str, description: str, log_file_path=None) -> None:
        banner = '=' * 60
        log_to_job(f"{banner}\n{description}\n{banner}", log_file_path, 'info', pass_name)

    def log_pass_complete(pass_name: str, duration_seconds: float, stats: dict, log_file_path=None) -> None:
        stats_str = ', '.join(f"{k}={v}" for k, v in stats.items())
        log_to_job(f"Completed in {duration_seconds:.2f}s - {stats_str}", log_file_path, 'info', pass_name)
        log_to_job('=' * 60, log_file_path, 'info', pass_name)

    def log_heartbeat(
        current: int,
        total: int,
        item_name: str,
        log_file_path=None,
        pass_name: str | None = None,
        last_logged: float = 0.0,
        heartbeat_interval: float = 8.0
    ) -> float:
        import time

        now = time.time()
        if now - last_logged >= heartbeat_interval:
            progress_pct = (current / total * 100) if total else 0
            log_to_job(
                f"Processing {current}/{total} ({progress_pct:.1f}%): {item_name}",
                log_file_path,
                'info',
                pass_name
            )
            return now
        return last_logged


logger = get_logger(__name__)

# Retain legacy constant for compatibility with existing tests
SPLIT_THRESHOLD_BYTES = 10 * 1024 * 1024


@dataclass
class SplitPart:
    """Metadata for a generated PDF part."""

    doc_id: str
    part_id: str
    section_id: Optional[str]
    page_start: int
    page_end: int
    relative_path: str
    checksum_sha256: str
    size_bytes: int
    section_title: Optional[str] = None


@dataclass
class PassBResult:
    """Structured result returned by Pass B."""

    job_id: str
    split_performed: bool
    total_pages: int
    threshold_mb: int
    parts: List[SplitPart]
    processing_time_ms: int
    artifacts: List[str]
    success: bool = True
    error_message: Optional[str] = None
    mode: str = "standard"
    lightweight: bool = False
    min_pages_per_part: int = 20
    max_pages_per_part: int = 30
    target_pages_per_part: int = 25
    split_plan_path: Optional[str] = None
    section_catalog: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self) -> None:
        if self.section_catalog is None:
            self.section_catalog = []

    @property
    def artifacts_paths(self) -> List[str]:
        return self.artifacts

    @property
    def parts_created(self) -> int:
        return len(self.parts)


class LogicalSplitter:
    """Split large PDFs into logical parts based on size threshold."""

    def __init__(
        self,
        job_id: str,
        env: str,
        pass_a_manifest: Optional[Path] = None,
        job_log_file: Optional[Path] = None,
    ) -> None:
        self.job_id = job_id
        self.env = env
        self.config = ConfigManager()
        self.processing_config = self.config.get_processing_config()
        self.threshold_mb = self.processing_config.get("pass_b_split_threshold_mb", 10)
        self.max_pages_per_part = max(1, int(self.processing_config.get("pass_b_max_pages_per_part", 30)))
        configured_min_pages = int(self.processing_config.get("pass_b_min_pages_per_part", 20))
        self.min_pages_per_part = max(1, min(self.max_pages_per_part, configured_min_pages))
        configured_target_pages = int(self.processing_config.get("pass_b_target_pages_per_part", 25))
        self.target_pages_per_part = min(self.max_pages_per_part, max(self.min_pages_per_part, configured_target_pages))
        self.max_toc_sections = int(self.processing_config.get("pass_b_max_toc_sections", 200))
        self.pass_a_manifest = pass_a_manifest
        self.job_log_file = job_log_file
        self.section_catalog: List[Dict[str, Any]] = []
        self.section_titles: List[str] = []
        self.source_pdf_name: Optional[str] = None
        self.source_doc_id: Optional[str] = None

    def _log_job(self, message: str) -> None:
        """Legacy wrapper around standardized job logging"""
        if self.source_pdf_name:
            message = f"source={self.source_pdf_name} :: {message}"
        log_to_job(message, self.job_log_file, "info", "B")

    def _load_toc_entries(self, job_dir: Path, total_pages: int) -> List[Dict[str, Any]]:
        """Load ToC metadata emitted by Pass A if available.

        Prioritizes new passA.toc.json format, falls back to legacy formats.
        """
        candidates = []

        # Priority 1: New passA.toc.json format (from Pass A TOC-only extraction)
        candidates.append(job_dir / "pass_a" / f"{self.job_id}_passA.toc.json")

        # Priority 2: Explicit pass_a_manifest if provided
        if self.pass_a_manifest:
            candidates.append(Path(self.pass_a_manifest))

        # Priority 3: Legacy formats (backward compatibility)
        candidates.append(job_dir / f"{self.job_id}_pass_a_manifest.json")
        candidates.append(job_dir / f"{self.job_id}_pass_a_dict.json")

        for candidate in candidates:
            if not candidate:
                continue
            candidate_path = Path(candidate)
            if not candidate_path.exists():
                continue
            try:
                with candidate_path.open('r', encoding='utf-8') as handle:
                    data = json.load(handle)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pass_b_toc_manifest_load_failed",
                    extra={"job_id": self.job_id, "manifest": str(candidate_path), "error": str(exc)},
                )
                continue

            # Extract document ID from Pass A data
            if 'document_id' in data and not self.source_doc_id:
                self.source_doc_id = data['document_id']
                logger.info(
                    "pass_b_doc_id_loaded",
                    extra={"job_id": self.job_id, "doc_id": self.source_doc_id}
                )

            # NEW FORMAT: passA.toc.json with sections array
            if 'sections' in data and isinstance(data.get('sections'), list):
                sections = data['sections']
                if sections:
                    logger.info(
                        "pass_b_toc_loaded_new_format",
                        extra={
                            "job_id": self.job_id,
                            "manifest": str(candidate_path),
                            "sections": len(sections),
                            "extraction_method": data.get('extraction_method', 'unknown')
                        },
                    )
                    catalog = self._build_section_catalog_from_new_format(sections, total_pages)
                    if catalog:
                        return catalog

            # LEGACY FORMAT: toc_sections or toc arrays
            sections = data.get('toc_sections') or data.get('toc') or []
            if not sections:
                continue

            catalog = self._build_section_catalog(sections, total_pages)
            if catalog:
                logger.info(
                    "pass_b_toc_loaded_legacy_format",
                    extra={"job_id": self.job_id, "manifest": str(candidate_path), "sections": len(catalog)},
                )
                return catalog

        return []

    def _build_section_catalog_from_new_format(self, sections: List[Dict[str, Any]], total_pages: int) -> List[Dict[str, Any]]:
        """Build section catalog from new passA.toc.json format.

        New format sections have:
        - section_id: SHA1 hash
        - title: Section title
        - start_page: 1-indexed start page
        - end_page: 1-indexed end page
        - level: Hierarchy level (1, 2, 3, ...)
        - parent_id: Parent section ID or null
        """
        catalog: List[Dict[str, Any]] = []
        if not sections:
            return catalog

        for section in sections:
            # Validate required fields
            if not all(key in section for key in ['section_id', 'title', 'start_page', 'end_page', 'level']):
                logger.warning(
                    "pass_b_invalid_toc_section",
                    extra={"job_id": self.job_id, "section": section}
                )
                continue

            # Extract and validate page ranges
            start_page = int(section['start_page'])
            end_page = int(section['end_page'])

            # Clamp to valid page range
            start_page = max(1, min(start_page, total_pages))
            end_page = max(start_page, min(end_page, total_pages))

            catalog.append({
                "section_id": section['section_id'],
                "title": section['title'],
                "page_start": start_page,
                "page_end": end_page,
                "level": section['level'],
                "parent_id": section.get('parent_id'),
            })

        logger.info(
            "pass_b_catalog_built_from_new_format",
            extra={"job_id": self.job_id, "sections": len(catalog)}
        )

        return catalog

    def _build_section_catalog(self, sections: List[Dict[str, Any]], total_pages: int) -> List[Dict[str, Any]]:
        """Normalize ToC entries and compute page ranges."""
        catalog: List[Dict[str, Any]] = []
        if not sections:
            return catalog

        sorted_sections = sorted(sections, key=lambda entry: int(entry.get('page', 0) or 0))
        for index, section in enumerate(sorted_sections):
            start_page = int(section.get('page') or 1)
            if start_page < 1:
                start_page = 1

            if index + 1 < len(sorted_sections):
                next_start = int(sorted_sections[index + 1].get('page') or total_pages + 1)
            else:
                next_start = total_pages + 1

            end_page = max(start_page, min(total_pages, next_start - 1))

            catalog.append(
                {
                    "title": section.get('title') or f"section-{index + 1:02d}",
                    "page_start": start_page,
                    "page_end": end_page,
                    "level": section.get('level', 1),
                    "section_id": section.get('section_id') or f"section_{index:03d}",
                }
            )

        return catalog

    def _align_end_page(self, start_page: int, proposed_end: int, total_pages: int) -> int:
        """Align chunk boundaries to avoid splitting ToC sections."""
        if not self.section_catalog:
            return min(proposed_end, total_pages)

        for section in self.section_catalog:
            boundary = section.get('page_start')
            if boundary is None:
                continue
            if start_page < boundary <= proposed_end:
                aligned = boundary - 1
                if aligned >= start_page:
                    return min(aligned, total_pages)

        return min(proposed_end, total_pages)

    def _section_for_page(self, page: int) -> Optional[Dict[str, Any]]:
        """Return catalog entry that contains the given page."""
        if not self.section_catalog:
            return None
        for section in self.section_catalog:
            if section['page_start'] <= page <= section['page_end']:
                return section
        return None

    def _determine_part_count(self, total_pages: int) -> int:
        """Compute the number of parts needed to satisfy page constraints."""
        if total_pages <= 0:
            return 0
        min_parts = max(1, math.ceil(total_pages / self.max_pages_per_part))
        max_parts_candidate = total_pages // self.min_pages_per_part if self.min_pages_per_part else total_pages
        if max_parts_candidate < 1:
            max_parts_candidate = 1
        max_parts = max(min_parts, max_parts_candidate)
        candidates = range(min_parts, max_parts + 1)
        target = self.target_pages_per_part
        return min(candidates, key=lambda count: (abs((total_pages / count) - target), count))

    def _candidate_section_boundaries(self, start_page: int, max_end: int) -> List[int]:
        """Return ToC section boundaries that fall within the allowed range."""
        if not self.section_catalog:
            return []
        boundaries = set()
        for entry in self.section_catalog:
            page_end = entry.get('page_end')
            if page_end is None:
                continue
            try:
                boundary = int(page_end)
            except (TypeError, ValueError):  # noqa: PLW0703
                continue
            if start_page <= boundary <= max_end:
                boundaries.add(boundary)
        return sorted(boundaries)

    def _select_split_boundary(
        self,
        start_page: int,
        min_end: int,
        target_end: int,
        max_end: int,
        total_pages: int,
        is_last_part: bool,
    ) -> Dict[str, Any]:
        """Choose the page boundary for the current part using ToC guidance when available."""
        boundaries = self._candidate_section_boundaries(start_page, max_end)
        if is_last_part:
            final_end = max(start_page, min(total_pages, max_end))
            selection = {
                "page_end": final_end,
                "selection_reason": "final_remainder",
                "toc_candidates": boundaries,
            }
            return selection

        if boundaries:
            eligible = [end for end in boundaries if end >= min_end]
            if eligible:
                best = min(
                    eligible,
                    key=lambda candidate: (abs(candidate - target_end), candidate),
                )
                selection = {
                    "page_end": best,
                    "selection_reason": "toc_aligned",
                    "toc_candidates": boundaries,
                }
                return selection

        selection = {
            "page_end": max_end,
            "selection_reason": "limit_enforced",
            "toc_candidates": boundaries,
        }
        return selection

    def _estimate_tokens(self, page_count: int) -> int:
        """Estimate token count from page count using simple heuristic.

        Assumes average 500 words per page, 1.3 tokens per word.
        This is a rough estimate for splitting decisions.
        """
        return int(page_count * 500 * 1.3)

    def _generate_toc_based_splits(self, total_pages: int) -> List[Dict[str, Any]]:
        """Generate splits based on TOC structure (structure-first approach).

        Strategy per AI spec:
        1. Split on TOC section boundaries (level 1)
        2. Use sub-headings (level 2/3) if section too large (>8k tokens)
        3. Target 3-8k tokens per part
        4. Cap at 30 pages only at safe boundaries
        """
        if not self.section_catalog:
            # No TOC available, fall back to page-based splitting
            logger.info("pass_b_no_toc_fallback", extra={"job_id": self.job_id})
            return self._generate_page_ranges(total_pages)

        ranges: List[Dict[str, Any]] = []
        current_page = 1

        # Group sections by level 1 (top-level chapters/parts)
        level_1_sections = [s for s in self.section_catalog if s['level'] == 1]

        if level_1_sections and len(level_1_sections) > self.max_toc_sections:
            logger.info("pass_b_toc_overflow", extra={
                "job_id": self.job_id,
                "sections": len(level_1_sections),
                "threshold": self.max_toc_sections,
            })
            self._log_job(
                f"Pass B: TOC has {len(level_1_sections)} level-1 sections; falling back to page-based splitting"
            )
            return self._generate_page_ranges(total_pages)

        if not level_1_sections:
            # No level 1 sections, use all sections as boundaries
            level_1_sections = self.section_catalog

        for section_idx, section in enumerate(level_1_sections):
            section_start = section['page_start']
            section_end = section['page_end']
            section_pages = section_end - section_start + 1
            section_tokens = self._estimate_tokens(section_pages)

            # If section fits target (3-8k tokens / ~5-13 pages), use as-is
            if 3000 <= section_tokens <= 8000:
                ranges.append({
                    "page_start": section_start,
                    "page_end": section_end,
                    "selection_reason": "toc_section_optimal",
                    "section_id": section['section_id'],
                    "section_title": section['title'],
                    "section_level": section['level'],
                    "estimated_tokens": section_tokens,
                })
                current_page = section_end + 1

            # If section is too large (>8k tokens), try to split using sub-headings
            elif section_tokens > 8000:
                # Find sub-sections (level 2+) within this section
                subsections = [
                    s for s in self.section_catalog
                    if s['page_start'] >= section_start
                    and s['page_end'] <= section_end
                    and s['level'] > section['level']
                ]

                if subsections:
                    # Split using sub-headings
                    for subsection in subsections:
                        subsection_pages = subsection['page_end'] - subsection['page_start'] + 1
                        subsection_tokens = self._estimate_tokens(subsection_pages)

                        # Cap at 30 pages per AI spec
                        if subsection_pages <= 30:
                            ranges.append({
                                "page_start": subsection['page_start'],
                                "page_end": subsection['page_end'],
                                "selection_reason": "toc_subsection_split",
                                "section_id": subsection['section_id'],
                                "section_title": subsection['title'],
                                "section_level": subsection['level'],
                                "estimated_tokens": subsection_tokens,
                            })
                        else:
                            # Subsection itself is too large, split into chunks
                            chunk_start = subsection['page_start']
                            while chunk_start <= subsection['page_end']:
                                chunk_end = min(chunk_start + 29, subsection['page_end'])
                                chunk_tokens = self._estimate_tokens(chunk_end - chunk_start + 1)

                                ranges.append({
                                    "page_start": chunk_start,
                                    "page_end": chunk_end,
                                    "selection_reason": "large_subsection_chunked",
                                    "section_id": subsection['section_id'],
                                    "section_title": subsection['title'],
                                    "section_level": subsection['level'],
                                    "estimated_tokens": chunk_tokens,
                                })
                                chunk_start = chunk_end + 1

                    current_page = section_end + 1
                else:
                    # No subsections, split into page chunks (cap at 30 pages)
                    chunk_start = section_start
                    while chunk_start <= section_end:
                        chunk_end = min(chunk_start + 29, section_end)
                        chunk_tokens = self._estimate_tokens(chunk_end - chunk_start + 1)

                        ranges.append({
                            "page_start": chunk_start,
                            "page_end": chunk_end,
                            "selection_reason": "large_section_chunked",
                            "section_id": section['section_id'],
                            "section_title": section['title'],
                            "section_level": section['level'],
                            "estimated_tokens": chunk_tokens,
                        })
                        chunk_start = chunk_end + 1

                    current_page = section_end + 1

            # If section is too small (<3k tokens), combine with next section if possible
            else:
                # For now, include small sections as-is (could be combined in future)
                ranges.append({
                    "page_start": section_start,
                    "page_end": section_end,
                    "selection_reason": "toc_section_small",
                    "section_id": section['section_id'],
                    "section_title": section['title'],
                    "section_level": section['level'],
                    "estimated_tokens": section_tokens,
                })
                current_page = section_end + 1

        logger.info(
            "pass_b_toc_based_splits_generated",
            extra={"job_id": self.job_id, "parts": len(ranges), "total_pages": total_pages}
        )

        return ranges

    def _generate_page_ranges(self, total_pages: int) -> List[Dict[str, Any]]:
        """Plan the page ranges for each split using page constraints and ToC hints."""
        if total_pages <= 0:
            return []

        part_count = self._determine_part_count(total_pages)
        if part_count <= 0:
            return []

        ranges: List[Dict[str, Any]] = []
        current_page = 1

        for index in range(part_count):
            parts_remaining = part_count - index - 1
            remaining_pages = total_pages - current_page + 1

            if parts_remaining <= 0:
                min_size = max(1, min(self.min_pages_per_part, remaining_pages))
                max_size = remaining_pages
            else:
                min_size = max(
                    self.min_pages_per_part,
                    remaining_pages - (parts_remaining * self.max_pages_per_part),
                )
                max_size = min(
                    self.max_pages_per_part,
                    remaining_pages - (parts_remaining * self.min_pages_per_part),
                )
                min_size = max(1, min_size)
                if max_size < min_size:
                    max_size = min_size

            preferred_size = min(
                max_size,
                max(min_size, self.target_pages_per_part),
            )

            min_end = min(total_pages, current_page + min_size - 1)
            max_end = min(total_pages, current_page + max_size - 1)
            target_end = min(total_pages, current_page + preferred_size - 1)

            selection = self._select_split_boundary(
                start_page=current_page,
                min_end=min_end,
                target_end=target_end,
                max_end=max_end,
                total_pages=total_pages,
                is_last_part=parts_remaining == 0,
            )

            page_end = selection["page_end"]
            if page_end < current_page:
                page_end = max_end
                selection["selection_reason"] = "limit_enforced"

            ranges.append(
                {
                    "page_start": current_page,
                    "page_end": page_end,
                    "selection_reason": selection.get("selection_reason", "limit_enforced"),
                    "toc_candidates": selection.get("toc_candidates", []),
                }
            )

            current_page = page_end + 1

        if ranges and ranges[-1]["page_end"] < total_pages:
            ranges[-1]["page_end"] = total_pages
            ranges[-1]["selection_reason"] = "final_remainder"

        return ranges

    def _sanitize_page_ranges(self, page_ranges: List[Dict[str, Any]], total_pages: int) -> List[Dict[str, Any]]:
        """Clamp and validate planned page ranges before PDF slicing."""
        if total_pages <= 0 or not page_ranges:
            return []

        sanitized: List[Dict[str, Any]] = []
        adjustments: List[Dict[str, Any]] = []

        for index, raw_range in enumerate(page_ranges, start=1):
            raw_start = raw_range.get('page_start', 1)
            raw_end = raw_range.get('page_end', raw_start)

            try:
                start_page = int(raw_start)
            except Exception:
                start_page = 1
            try:
                end_page = int(raw_end)
            except Exception:
                end_page = start_page

            original_start, original_end = start_page, end_page

            if start_page < 1:
                start_page = 1
            if total_pages > 0 and start_page > total_pages:
                start_page = total_pages

            if end_page < start_page:
                end_page = start_page
            if total_pages > 0 and end_page > total_pages:
                end_page = total_pages

            if total_pages > 0 and start_page > total_pages:
                continue

            if original_start != start_page or original_end != end_page:
                adjustments.append({
                    'index': index,
                    'original_start': original_start,
                    'original_end': original_end,
                    'adjusted_start': start_page,
                    'adjusted_end': end_page,
                })

            normalized = dict(raw_range)
            normalized['page_start'] = start_page
            normalized['page_end'] = end_page
            sanitized.append(normalized)

        if adjustments:
            logger.warning(
                'pass_b_page_ranges_normalized',
                extra={
                    'job_id': self.job_id,
                    'total_pages': total_pages,
                    'adjusted_ranges': len(adjustments),
                },
            )
            for detail in adjustments[:5]:
                self._log_job(
                    f"Pass B normalized range #{detail['index']}: {detail['original_start']}-{detail['original_end']} -> {detail['adjusted_start']}-{detail['adjusted_end']}"
                )

        return sanitized

    def process(self, source_pdf: Path, job_dir: Path, lightweight: bool = False) -> PassBResult:
        """Process PDF and determine if logical splitting is needed."""
        min_pages_per_part: int = 20
        max_pages_per_part: int = 30
        target_pages_per_part: int = 25
        started_at = time.perf_counter()
        mode = "lightweight" if lightweight else "standard"

        # Pass start logging
        log_pass_start("B", f"Logical Splitting ({mode} mode) - {source_pdf.name}", self.job_log_file)

        logger.info(
            "pass_b_split_start",
            extra={
                "job_id": self.job_id,
                "env": self.env,
                "source_pdf": str(source_pdf),
                "threshold_mb": self.threshold_mb,
                "mode": mode,
            },
        )

        if not source_pdf.exists():
            raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

        self.source_pdf_name = Path(source_pdf).name

        pass_dir = job_dir / "pass_b"
        parts_dir = pass_dir / "parts"
        pass_dir.mkdir(parents=True, exist_ok=True)
        parts_dir.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(source_pdf))
        total_pages = len(reader.pages)
        file_size = source_pdf.stat().st_size
        threshold_bytes = self.threshold_mb * 1024 * 1024
        split_performed = file_size > threshold_bytes and total_pages > 0

        logger.info(
            "pass_b_pdf_loaded",
            extra={
                "job_id": self.job_id,
                "env": self.env,
                "source_pdf": str(source_pdf),
                "total_pages": total_pages,
                "file_size_bytes": file_size,
                "threshold_bytes": threshold_bytes,
                "threshold_mb": self.threshold_mb,
                "split_required": split_performed,
                "mode": mode,
                "lightweight": lightweight,
            },
        )

        self._log_job(
            "Pass B source: pages="
            f"{total_pages}, file_size_bytes={file_size}, "
            f"threshold_mb={self.threshold_mb}, split_required={split_performed}, mode={mode}, "
            f"lightweight={lightweight}"
        )

        self.section_catalog = self._load_toc_entries(job_dir, total_pages)
        self.section_titles = [entry["title"] for entry in self.section_catalog]

        parts: List[SplitPart] = []
        artifacts: List[str] = []
        split_plan: List[Dict[str, Any]] = []
        plan_path: Optional[Path] = None
        parts_jsonl: List[Dict[str, Any]] = []  # For passB.parts.jsonl

        # NEW STRATEGY: TOC-first splitting
        # If TOC is available, use structure-based splitting regardless of file size
        # Otherwise, fall back to size-based splitting
        use_toc_splitting = len(self.section_catalog) > 0

        if use_toc_splitting:
            # TOC-BASED SPLITTING (Structure-first approach per AI spec)
            logger.info(
                "pass_b_using_toc_splitting",
                extra={
                    "job_id": self.job_id,
                    "total_pages": total_pages,
                    "toc_sections": len(self.section_catalog),
                    "mode": mode,
                },
            )
            self._log_job(
                f"Pass B strategy: TOC-based splitting with {len(self.section_catalog)} sections"
            )

            # Generate TOC-based split plan
            page_ranges = self._generate_toc_based_splits(total_pages)
            page_ranges = self._sanitize_page_ranges(page_ranges, total_pages)
            if not page_ranges:
                logger.warning(
                    "pass_b_toc_plan_empty",
                    extra={"job_id": self.job_id, "total_pages": total_pages, "mode": mode},
                )
                self._log_job("Pass B: TOC plan invalid, falling back to page-based ranges")
                page_ranges = self._sanitize_page_ranges(self._generate_page_ranges(total_pages), total_pages)

            split_performed = len(page_ranges) > 1

            logger.info(
                "pass_b_toc_plan_established",
                extra={
                    "job_id": self.job_id,
                    "parts": len(page_ranges),
                    "total_pages": total_pages,
                    "mode": mode,
                },
            )

            # Process each TOC-based range
            part_index = 0
            for page_range in page_ranges:
                part_number = part_index + 1
                part_start_page = page_range["page_start"]
                aligned_end = page_range["page_end"]

                if lightweight and not split_performed:
                    # Lightweight mode with no splitting - skip PDF generation
                    # Just record the plan
                    split_plan.append({
                        "part_id": None,
                        "page_start": part_start_page,
                        "page_end": aligned_end,
                        "section_id": page_range.get("section_id"),
                        "section_title": page_range.get("section_title"),
                    })
                    part_index += 1
                    continue

                # Generate actual PDF part
                part_started_at = time.perf_counter()
                writer = PdfWriter()

                # Add pages with progress logging (heartbeat every 8s)
                total_pages_in_part = aligned_end - part_start_page + 1
                pages_processed = 0
                last_log_time = 0.0

                logger.info(f"Pass B: Building part {part_number} - adding {total_pages_in_part} pages...")
                log_to_job(f"Building part {part_number} - {total_pages_in_part} pages", self.job_log_file, "info", "B")

                for page_number in range(part_start_page - 1, aligned_end):
                    writer.add_page(reader.pages[page_number])
                    pages_processed += 1

                    # Standardized heartbeat logging (prevents >10s silence)
                    last_log_time = log_heartbeat(
                        pages_processed,
                        total_pages_in_part,
                        f"Part {part_number} page {page_number + 1}",
                        self.job_log_file,
                        "B",
                        last_log_time,
                        heartbeat_interval=8.0
                    )

                part_filename = f"{self.job_id}_part_{part_number:02d}.pdf"
                part_path = parts_dir / part_filename

                logger.info(f"Pass B: Writing part {part_number} to disk: {part_filename}")
                write_started = time.perf_counter()

                with part_path.open("wb") as handle:
                    writer.write(handle)

                write_duration = time.perf_counter() - write_started
                logger.info(f"  File write completed in {write_duration:.2f}s ({part_path.stat().st_size / 1024 / 1024:.2f} MB)")

                checksum = _sha256(part_path)
                part_relative = part_path.relative_to(job_dir).as_posix()

                # Use section ID from TOC if available
                section_id = page_range.get("section_id", f"pages-{part_start_page}-{aligned_end}")
                section_title = page_range.get("section_title")

                # Use source document ID if available, otherwise fall back to job_id
                doc_id_for_part = self.source_doc_id if self.source_doc_id else self.job_id

                part_meta = SplitPart(
                    doc_id=doc_id_for_part,
                    part_id=f"{self.job_id}-part-{part_number:02d}",
                    section_id=section_id,
                    page_start=part_start_page,
                    page_end=aligned_end,
                    relative_path=part_relative,
                    checksum_sha256=checksum,
                    size_bytes=part_path.stat().st_size,
                    section_title=section_title,
                )
                parts.append(part_meta)
                artifacts.append(part_relative)

                # Build split plan entry
                split_plan.append({
                    "part_id": part_meta.part_id,
                    "page_start": part_meta.page_start,
                    "page_end": part_meta.page_end,
                    "section_id": section_id,
                    "section_title": section_title,
                    "selection_reason": page_range.get("selection_reason", "toc_based"),
                    "estimated_tokens": page_range.get("estimated_tokens"),
                })

                # Build JSONL entry for passB.parts.jsonl (per AI spec)
                parts_jsonl.append({
                    "part_id": part_meta.part_id,
                    "doc_id": doc_id_for_part,
                    "page_start": part_meta.page_start,
                    "page_end": part_meta.page_end,
                    "page_count": aligned_end - part_start_page + 1,
                    "section_id": section_id,
                    "section_title": section_title,
                    "section_level": page_range.get("section_level"),
                    "relative_path": part_relative,
                    "size_bytes": part_meta.size_bytes,
                    "checksum_sha256": checksum,
                    "reason": page_range.get("selection_reason", "toc_based"),
                    "estimated_tokens": page_range.get("estimated_tokens"),
                })

                part_duration_ms = int((time.perf_counter() - part_started_at) * 1000)
                page_count = aligned_end - part_start_page + 1

                # Comprehensive logging
                logger.info(
                    f"Pass B: Created part {part_number}: {self.source_pdf_name} "
                    f"(pages {part_start_page}-{aligned_end}, {page_count} pages) → {part_filename}"
                )
                logger.info(f"  Source: {self.source_pdf_name}")
                logger.info(f"  Document ID: {doc_id_for_part}")
                logger.info(f"  Section: {section_title or section_id}")
                logger.info(f"  Output: {part_relative}")
                logger.info(f"  Pages: {part_start_page}-{aligned_end} ({page_count} pages)")
                logger.info(f"  Size: {part_meta.size_bytes:,} bytes")
                logger.info(f"  Checksum: {checksum[:16]}...")
                logger.info(f"  Duration: {part_duration_ms}ms")

                # Structured log for automation
                logger.info(
                    "pass_b_part_emitted",
                    extra={
                        "job_id": self.job_id,
                        "doc_id": doc_id_for_part,
                        "source_file": self.source_pdf_name,
                        "part_index": part_number,
                        "page_start": part_meta.page_start,
                        "page_end": part_meta.page_end,
                        "page_count": page_count,
                        "size_bytes": part_meta.size_bytes,
                        "duration_ms": part_duration_ms,
                        "output_file": part_filename,
                        "relative_path": part_relative,
                        "checksum": checksum,
                    },
                )
                self._log_job(
                    f"Pass B part {part_number}: {self.source_pdf_name} "
                    f"→ {part_filename} (pages {part_meta.page_start}-{part_meta.page_end}, "
                    f"section={section_title or section_id}, doc_id={doc_id_for_part})"
                )

                part_index += 1

        elif split_performed:
            # FALLBACK: SIZE-BASED SPLITTING (when no TOC available)
            logger.info(
                "pass_b_using_size_splitting",
                extra={
                    "job_id": self.job_id,
                    "total_pages": total_pages,
                    "file_size_bytes": file_size,
                    "mode": mode,
                },
            )
            self._log_job("Pass B strategy: Size-based splitting (no TOC available)")

            safe_threshold = max(threshold_bytes, 1)
            estimated_parts = max(2, math.ceil(file_size / safe_threshold))
            pages_per_part = max(1, math.ceil(total_pages / estimated_parts))

            logger.info(
                "pass_b_split_plan_established",
                extra={
                    "job_id": self.job_id,
                    "estimated_parts": estimated_parts,
                    "pages_per_part": pages_per_part,
                    "total_pages": total_pages,
                    "file_size_bytes": file_size,
                    "mode": mode,
                    "lightweight": lightweight,
                },
            )

            self._log_job(
                "Pass B plan: estimated_parts="
                f"{estimated_parts}, pages_per_part={pages_per_part}, "
                f"total_pages={total_pages}, threshold_mb={self.threshold_mb}, "
                f"mode={mode}, lightweight={lightweight}, toc_sections=0"
            )

            current_page = 1
            part_index = 0

            while current_page <= total_pages:
                part_number = part_index + 1
                part_start_page = current_page
                proposed_end = min(total_pages, part_start_page + pages_per_part - 1)
                aligned_end = min(proposed_end, total_pages)

                part_started_at = time.perf_counter()
                writer = PdfWriter()

                # Add pages with progress logging (heartbeat every 8s)
                total_pages_in_part = aligned_end - part_start_page + 1
                pages_processed = 0
                last_log_time = 0.0  # Initialize for heartbeat

                logger.info(f"Pass B: Building part {part_number}/{estimated_parts} - adding {total_pages_in_part} pages...")
                log_to_job(f"Building part {part_number}/{estimated_parts} - {total_pages_in_part} pages", self.job_log_file, "info", "B")

                for page_number in range(part_start_page - 1, aligned_end):
                    writer.add_page(reader.pages[page_number])
                    pages_processed += 1

                    # Standardized heartbeat logging (prevents >10s silence)
                    last_log_time = log_heartbeat(
                        pages_processed,
                        total_pages_in_part,
                        f"Part {part_number} page {page_number + 1}",
                        self.job_log_file,
                        "B",
                        last_log_time,
                        heartbeat_interval=8.0
                    )

                part_filename = f"{self.job_id}_part_{part_number:02d}.pdf"
                part_path = parts_dir / part_filename

                logger.info(f"Pass B: Writing part {part_number} to disk: {part_filename}")
                write_started = time.perf_counter()

                with part_path.open("wb") as handle:
                    writer.write(handle)

                write_duration = time.perf_counter() - write_started
                logger.info(f"  File write completed in {write_duration:.2f}s ({part_path.stat().st_size / 1024 / 1024:.2f} MB)")

                checksum = _sha256(part_path)
                part_relative = part_path.relative_to(job_dir).as_posix()
                pages_label = f"pages-{part_start_page}-{aligned_end}"

                # Use source document ID if available, otherwise fall back to job_id
                doc_id_for_part = self.source_doc_id if self.source_doc_id else self.job_id

                part_meta = SplitPart(
                    doc_id=doc_id_for_part,
                    part_id=f"{self.job_id}-part-{part_number:02d}",
                    section_id=pages_label,
                    page_start=part_start_page,
                    page_end=aligned_end,
                    relative_path=part_relative,
                    checksum_sha256=checksum,
                    size_bytes=part_path.stat().st_size,
                )
                parts.append(part_meta)
                artifacts.append(part_relative)

                split_plan.append(
                    {
                        "part_id": part_meta.part_id,
                        "page_start": part_meta.page_start,
                        "page_end": part_meta.page_end,
                        "section_id": part_meta.section_id,
                        "section_title": None,
                    }
                )

                part_duration_ms = int((time.perf_counter() - part_started_at) * 1000)
                page_count = aligned_end - part_start_page + 1

                # Comprehensive logging with all traceability info
                logger.info(
                    f"Pass B: Created chunk {part_number}/{estimated_parts}: {self.source_pdf_name} "
                    f"(pages {part_start_page}-{aligned_end}, {page_count} pages) → {part_filename}"
                )
                logger.info(
                    f"  Source: {self.source_pdf_name}"
                )
                logger.info(
                    f"  Document ID: {doc_id_for_part}"
                )
                logger.info(
                    f"  Output: {part_relative}"
                )
                logger.info(
                    f"  Pages: {part_start_page}-{aligned_end} ({page_count} pages)"
                )
                logger.info(
                    f"  Size: {part_meta.size_bytes:,} bytes"
                )
                logger.info(
                    f"  Checksum: {checksum[:16]}..."
                )
                logger.info(
                    f"  Duration: {part_duration_ms}ms"
                )

                # Structured log for automation
                logger.info(
                    "pass_b_part_emitted",
                    extra={
                        "job_id": self.job_id,
                        "doc_id": doc_id_for_part,
                        "source_file": self.source_pdf_name,
                        "part_index": part_number,
                        "page_start": part_meta.page_start,
                        "page_end": part_meta.page_end,
                        "page_count": page_count,
                        "size_bytes": part_meta.size_bytes,
                        "duration_ms": part_duration_ms,
                        "output_file": part_filename,
                        "relative_path": part_relative,
                        "checksum": checksum,
                    },
                )
                self._log_job(
                    f"Pass B chunk {part_number}/{estimated_parts}: {self.source_pdf_name} "
                    f"→ {part_filename} (pages {part_meta.page_start}-{part_meta.page_end}, "
                    f"doc_id={doc_id_for_part})"
                )

                part_index += 1
                current_page = aligned_end + 1

        else:
            logger.info(
                "pass_b_skip_split",
                extra={
                    "job_id": self.job_id,
                    "reason": "below_threshold" if file_size <= threshold_bytes else "no_pages",
                    "total_pages": total_pages,
                    "file_size_bytes": file_size,
                    "threshold_bytes": threshold_bytes,
                    "mode": mode,
                    "lightweight": lightweight,
                },
            )
            self._log_job(
                "Pass B skip: reason="
                f"{'below_threshold' if file_size <= threshold_bytes else 'no_pages'}, "
                f"total_pages={total_pages}, file_size_bytes={file_size}, threshold_mb={self.threshold_mb}, "
                f"mode={mode}, lightweight={lightweight}"
            )

        if not split_plan and self.section_catalog:
            for section in self.section_catalog:
                split_plan.append(
                    {
                        "part_id": None,
                        "page_start": section["page_start"],
                        "page_end": section["page_end"],
                        "section_id": f"pages-{section['page_start']}-{section['page_end']}",
                        "section_title": None,
                    }
                )

            logger.info(
                "pass_b_section_catalog_applied",
                extra={
                    "job_id": self.job_id,
                    "sections": len(self.section_catalog),
                    "mode": mode,
                },
            )
            self._log_job(
                "Pass B section catalog reused: sections="
                f"{len(self.section_catalog)}, mode={mode}"
            )

        split_index_path = pass_dir / "split_index.json"
        with split_index_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "split_performed": split_performed,
                    "total_pages": total_pages,
                    "threshold_mb": self.threshold_mb,
                    "mode": mode,
                    "lightweight": lightweight,
                    "parts": [asdict(part) for part in parts],
                },
                handle,
                indent=2,
            )
        artifacts.append(split_index_path.relative_to(job_dir).as_posix())

        summary_path = pass_dir / "split_summary.json"
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "split_performed": split_performed,
                    "total_pages": total_pages,
                    "file_size_bytes": file_size,
                    "threshold_mb": self.threshold_mb,
                    "parts_created": len(parts),
                    "mode": mode,
                    "lightweight": lightweight,
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )
        artifacts.append(summary_path.relative_to(job_dir).as_posix())

        if split_plan:
            plan_path = pass_dir / "split_plan.json"
            with plan_path.open("w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "job_id": self.job_id,
                        "mode": mode,
                        "lightweight": lightweight,
                        "parts": split_plan,
                        "section_catalog": self.section_catalog,
                    },
                    handle,
                    indent=2,
                )
            artifacts.append(plan_path.relative_to(job_dir).as_posix())

        # Generate passB.parts.jsonl (JSONL format per AI spec)
        if parts_jsonl:
            parts_jsonl_path = pass_dir / f"{self.job_id}_passB.parts.jsonl"
            with parts_jsonl_path.open("w", encoding="utf-8") as handle:
                for part_entry in parts_jsonl:
                    handle.write(json.dumps(part_entry, ensure_ascii=False) + "\n")

            artifacts.append(parts_jsonl_path.relative_to(job_dir).as_posix())
            logger.info(
                "pass_b_parts_jsonl_generated",
                extra={
                    "job_id": self.job_id,
                    "path": str(parts_jsonl_path),
                    "entries": len(parts_jsonl)
                }
            )
            self._log_job(f"Pass B: Generated passB.parts.jsonl with {len(parts_jsonl)} entries")

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        duration_seconds = duration_ms / 1000

        logger.info(
            "pass_b_split_complete",
            extra={
                "job_id": self.job_id,
                "split_performed": split_performed,
                "parts": len(parts),
                "duration_ms": duration_ms,
                "mode": mode,
            },
        )

        # Pass complete logging
        stats = {
            "split_performed": split_performed,
            "parts": len(parts),
            "total_pages": total_pages,
            "sections": len(self.section_catalog)
        }
        log_pass_complete("B", duration_seconds, stats, self.job_log_file)

        return PassBResult(
            job_id=self.job_id,
            split_performed=split_performed,
            total_pages=total_pages,
            threshold_mb=self.threshold_mb,
            parts=parts,
            processing_time_ms=duration_ms,
            artifacts=artifacts,
            mode=mode,
            lightweight=lightweight,
            split_plan_path=str(plan_path.relative_to(job_dir)) if plan_path else None,
            section_catalog=self.section_catalog,
        )





class PassBLogicalSplitter(LogicalSplitter):
    """Legacy wrapper for backwards compatibility."""

    def process_pdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        pass_a_manifest: Optional[Path] = None,
        lightweight: bool = False
    ) -> PassBResult:
        if pass_a_manifest is not None:
            self.pass_a_manifest = Path(pass_a_manifest)
        return self.process(pdf_path, output_dir, lightweight=lightweight)


def process_pass_b(
    source_pdf: Path,
    job_dir: Path,
    job_id: str,
    env: str,
    pass_a_manifest: Optional[Path] = None,
    job_log_file: Optional[Path] = None,
    lightweight: bool = False,
    min_pages_per_part: int = 20,
    max_pages_per_part: int = 30,
    target_pages_per_part: int = 25
) -> PassBResult:
    """Entry point used by the ingestion pipeline."""

    splitter = LogicalSplitter(
        job_id=job_id,
        env=env,
        pass_a_manifest=pass_a_manifest,
        job_log_file=job_log_file,
    )
    return splitter.process(source_pdf, job_dir, lightweight=lightweight)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()

