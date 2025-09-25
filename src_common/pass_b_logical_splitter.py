"""Pass B logical splitter for MVP v2 ingestion pipeline."""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

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
    section_id: str
    page_start: int
    page_end: int
    relative_path: str
    checksum_sha256: str
    size_bytes: int


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

    @property
    def artifacts_paths(self) -> List[str]:
        return self.artifacts


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
        self.section_titles = self._load_toc_entries(pass_a_manifest)
        self.job_log_file = job_log_file

    def process(self, source_pdf: Path, job_dir: Path) -> PassBResult:
        started_at = time.perf_counter()
        logger.info(
            "pass_b_split_start",
            extra={
                "job_id": self.job_id,
                "env": self.env,
                "source_pdf": str(source_pdf),
                "threshold_mb": self.threshold_mb,
            },
        )

        if not source_pdf.exists():
            raise FileNotFoundError(f"Source PDF not found: {source_pdf}")

        pass_dir = job_dir / "pass_b"
        parts_dir = pass_dir / "parts"
        pass_dir.mkdir(parents=True, exist_ok=True)
        parts_dir.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(source_pdf))
        total_pages = len(reader.pages)
        file_size = source_pdf.stat().st_size
        threshold_bytes = self.threshold_mb * 1024 * 1024

        split_performed = file_size > threshold_bytes and total_pages > 0
        parts: List[SplitPart] = []
        artifacts: List[str] = []

        if split_performed:
            parts_count = max(2, math.ceil(file_size / max(threshold_bytes, 1)))
            pages_per_part = max(1, math.ceil(total_pages / parts_count))
            logger.info(
                "pass_b_split_plan",
                extra={
                    "job_id": self.job_id,
                    "total_pages": total_pages,
                    "parts_count": parts_count,
                    "pages_per_part": pages_per_part,
                },
            )

            for index in range(parts_count):
                start_page = index * pages_per_part
                end_page = min(total_pages, start_page + pages_per_part)
                if start_page >= end_page:
                    break

                writer = PdfWriter()
                for page_number in range(start_page, end_page):
                    writer.add_page(reader.pages[page_number])

                part_filename = f"{self.job_id}_part_{index + 1:02d}.pdf"
                part_path = parts_dir / part_filename
                with part_path.open("wb") as handle:
                    writer.write(handle)

                checksum = _sha256(part_path)
                part_relative = part_path.relative_to(job_dir).as_posix()
                section_title = (
                    self.section_titles[index]
                    if index < len(self.section_titles)
                    else f"section-{index + 1:02d}"
                )
                part_meta = SplitPart(
                    doc_id=self.job_id,
                    part_id=f"{self.job_id}-part-{index + 1:02d}",
                    section_id=section_title,
                    page_start=start_page + 1,
                    page_end=end_page,
                    relative_path=part_relative,
                    checksum_sha256=checksum,
                    size_bytes=part_path.stat().st_size,
                )
                parts.append(part_meta)
                artifacts.append(part_relative)
        else:
            logger.info(
                "pass_b_threshold_not_met",
                extra={
                    "job_id": self.job_id,
                    "file_size_bytes": file_size,
                    "threshold_bytes": threshold_bytes,
                },
            )

        split_index_path = pass_dir / "split_index.json"
        with split_index_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "split_performed": split_performed,
                    "total_pages": total_pages,
                    "threshold_mb": self.threshold_mb,
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
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )
        artifacts.append(summary_path.relative_to(job_dir).as_posix())

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "pass_b_split_complete",
            extra={
                "job_id": self.job_id,
                "split_performed": split_performed,
                "parts": len(parts),
                "duration_ms": duration_ms,
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
        )

    def _load_toc_entries(self, manifest_path: Optional[Path]) -> List[str]:
        if manifest_path is None or not manifest_path.exists():
            return []
        try:
            with manifest_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            toc_entries = []
            for entry in data.get("toc", []):
                title = entry.get("title")
                if title:
                    toc_entries.append(title)
            return toc_entries
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "pass_b_toc_load_failed",
                extra={"job_id": self.job_id, "reason": str(exc)},
            )
            return []


class PassBLogicalSplitter(LogicalSplitter):
    """Legacy wrapper for backwards compatibility."""

    def process_pdf(
        self,
        pdf_path: Path,
        output_dir: Path,
        pass_a_manifest: Optional[Path] = None,
    ) -> PassBResult:
        if pass_a_manifest is not None:
            self.section_titles = self._load_toc_entries(pass_a_manifest)
        return self.process(pdf_path, output_dir)


def process_pass_b(
    source_pdf: Path,
    job_dir: Path,
    job_id: str,
    env: str,
    pass_a_manifest: Optional[Path] = None,
    job_log_file: Optional[Path] = None,
) -> PassBResult:
    """Entry point used by the ingestion pipeline."""

    splitter = LogicalSplitter(
        job_id=job_id,
        env=env,
        pass_a_manifest=pass_a_manifest,
        job_log_file=job_log_file,
    )
    return splitter.process(source_pdf, job_dir)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
