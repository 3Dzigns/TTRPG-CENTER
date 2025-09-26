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
        self.pass_a_manifest = pass_a_manifest
        self.job_log_file = job_log_file
        self.section_catalog: List[Dict[str, Any]] = []
        self.section_titles: List[str] = []
        self.source_pdf_name: Optional[str] = None

    def _log_job(self, message: str) -> None:
        if not self.job_log_file:
            return
        try:
            log_path = Path(self.job_log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            prefix = f"Pass B job={self.job_id}"
            if self.source_pdf_name:
                prefix += f", source={self.source_pdf_name}"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{iso_timestamp()}] {prefix} :: {message}\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pass_b_job_log_write_failed",
                extra={"job_id": self.job_id, "error": str(exc)},
            )

    def _load_toc_entries(self, job_dir: Path, total_pages: int) -> List[Dict[str, Any]]:
        """Load ToC metadata emitted by Pass A if available."""
        candidates = []
        if self.pass_a_manifest:
            candidates.append(Path(self.pass_a_manifest))
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

            sections = data.get('toc_sections') or data.get('toc') or []
            if not sections:
                continue

            catalog = self._build_section_catalog(sections, total_pages)
            if catalog:
                logger.info(
                    "pass_b_toc_loaded",
                    extra={"job_id": self.job_id, "manifest": str(candidate_path), "sections": len(catalog)},
                )
                return catalog

        return []

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
            return {
                "page_end": final_end,
                "selection_reason": "final_remainder",
                "toc_candidates": boundaries,
            }

        if boundaries:
            eligible = [end for end in boundaries if end >= min_end]
            if eligible:
                best = min(
                    eligible,
                    key=lambda candidate: (abs(candidate - target_end), candidate),
                )
                return {
                    "page_end": best,
                    "selection_reason": "toc_aligned",
                    "toc_candidates": boundaries,
                }

        return {
            "page_end": max_end,
            "selection_reason": "limit_enforced",
            "toc_candidates": boundaries,
        }

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
    def process(self, source_pdf: Path, job_dir: Path, lightweight: bool = False) -> PassBResult:
    min_pages_per_part: int = 20
    max_pages_per_part: int = 30
    target_pages_per_part: int = 25
        started_at = time.perf_counter()
        mode = "lightweight" if lightweight else "standard"
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

        if split_performed:
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

            sections_detected = len(self.section_catalog)
            self._log_job(
                "Pass B plan: estimated_parts="
                f"{estimated_parts}, pages_per_part={pages_per_part}, "
                f"total_pages={total_pages}, threshold_mb={self.threshold_mb}, "
                f"mode={mode}, lightweight={lightweight}, toc_sections={sections_detected}"
            )

            current_page = 1
            part_index = 0

            while current_page <= total_pages:
                part_number = part_index + 1
                part_start_page = current_page
                proposed_end = min(total_pages, part_start_page + pages_per_part - 1)
                aligned_end = proposed_end

                if lightweight and self.section_catalog:
                    candidate = self._align_end_page(part_start_page, proposed_end, total_pages)
                    if candidate >= part_start_page:
                        aligned_end = candidate

                if aligned_end < part_start_page:
                    aligned_end = proposed_end
                if aligned_end < part_start_page:
                    aligned_end = part_start_page

                if aligned_end != proposed_end:
                    logger.info(
                        "pass_b_boundary_adjusted",
                        extra={
                            "job_id": self.job_id,
                            "part_index": part_number,
                            "requested_end": proposed_end,
                            "aligned_end": aligned_end,
                            "mode": mode,
                            "lightweight": lightweight,
                        },
                    )
                    self._log_job(
                        "Pass B boundary adjust: part="
                        f"{part_number}, requested_end={proposed_end}, aligned_end={aligned_end}, "
                        f"mode={mode}, lightweight={lightweight}"
                    )

                part_started_at = time.perf_counter()
                writer = PdfWriter()
                for page_number in range(part_start_page - 1, aligned_end):
                    writer.add_page(reader.pages[page_number])

                part_filename = f"{self.job_id}_part_{part_number:02d}.pdf"
                part_path = parts_dir / part_filename
                with part_path.open("wb") as handle:
                    writer.write(handle)

                checksum = _sha256(part_path)
                part_relative = part_path.relative_to(job_dir).as_posix()
                pages_label = f"pages-{part_start_page}-{aligned_end}"

                part_meta = SplitPart(
                    doc_id=self.job_id,
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
                logger.info(
                    "pass_b_part_emitted",
                    extra={
                        "job_id": self.job_id,
                        "part_index": part_number,
                        "page_start": part_meta.page_start,
                        "page_end": part_meta.page_end,
                        "size_bytes": part_meta.size_bytes,
                        "duration_ms": part_duration_ms,
                        "pages_label": part_meta.section_id,
                    },
                )
                self._log_job(
                    "Pass B part="
                    f"{part_number}, pages={part_meta.page_start}-{part_meta.page_end}, "
                    f"size_bytes={part_meta.size_bytes}, path={part_relative}"
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

        duration_ms = int((time.perf_counter() - started_at) * 1000)
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
        lightweight: bool = False,
    min_pages_per_part: int = 20
    max_pages_per_part: int = 30
    target_pages_per_part: int = 25
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
    min_pages_per_part: int = 20
    max_pages_per_part: int = 30
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

