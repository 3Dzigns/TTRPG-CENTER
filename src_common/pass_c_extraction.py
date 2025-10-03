"""Pass C extraction using Unstructured with deterministic fallbacks."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from pypdf import PdfReader

from src_common.config import ConfigManager
from src_common.logging import get_logger
from src_common.ocr_validator import validate_ocr_dependencies, OCRValidator
from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete, log_heartbeat

try:
    from unstructured.partition.pdf import partition_pdf  # type: ignore
    UNSTRUCTURED_AVAILABLE = True
    UNSTRUCTURED_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - import guard
    partition_pdf = None
    UNSTRUCTURED_AVAILABLE = False
    UNSTRUCTURED_IMPORT_ERROR = str(e)

logger = get_logger(__name__)


@dataclass
class ExtractionChunk:
    """Chunk of content produced by Pass C."""

    doc_id: str
    part_id: str
    section_id: str
    chunk_id: str
    text: str
    page_number: int
    lineage: Dict[str, str]
    checksum_sha256: str


@dataclass
class PassCResult:
    """Structured Pass C result for manifest recording."""

    job_id: str
    parts_processed: int
    chunks_extracted: int
    chunks_written: int
    used_unstructured: bool
    fallback_used: bool
    processing_time_ms: int
    artifacts: List[str]
    success: bool = True
    error_message: Optional[str] = None
    chunks_loaded: int = 0


class ExtractionRunner:
    """Handles Pass C extraction logic."""

    def __init__(self, job_id: str, env: str, job_log_file: Optional[Path] = None) -> None:
        self.job_id = job_id
        self.env = env
        self.job_log_file = job_log_file
        self.config = ConfigManager()
        self.allow_fallback = self._read_bool("ALLOW_UNSTRUCTURED_FALLBACK", default=False)
        self.ocr_languages = self.config.get_config("UNSTRUCTURED_OCR_LANGUAGES", "eng")

    def _read_bool(self, key: str, default: bool = False) -> bool:
        value = self.config.get_config(key)
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def process(self, source_pdf: Path, job_dir: Path) -> PassCResult:
        started_at = time.perf_counter()

        # Pass start logging
        log_pass_start("C", f"Content Extraction - {source_pdf.name}", self.job_log_file)

        logger.info(
            "pass_c_start",
            extra={
                "job_id": self.job_id,
                "env": self.env,
                "source_pdf": str(source_pdf),
                "unstructured_available": UNSTRUCTURED_AVAILABLE,
                "fallback_allowed": self.allow_fallback,
            },
        )

        pass_dir = job_dir / "pass_c"
        pass_dir.mkdir(parents=True, exist_ok=True)

        parts = self._discover_parts(job_dir, source_pdf)
        chunks: List[ExtractionChunk] = []
        used_unstructured = False
        fallback_used = False

        total_parts = len(parts)
        last_log_time = 0.0  # Initialize for heartbeat

        for part_idx, part in enumerate(parts, 1):
            logger.info(f"Pass C: Processing part {part_idx}/{total_parts}: {part.name}")

            # Heartbeat before processing (prevents >10s silence for slow parts)
            last_log_time = log_heartbeat(
                part_idx,
                total_parts,
                f"Extracting {part.name}",
                self.job_log_file,
                "C",
                last_log_time,
                heartbeat_interval=8.0
            )

            part_started = time.perf_counter()

            part_chunks, part_used_unstructured, part_used_fallback = self._extract_part(part)
            chunks.extend(part_chunks)
            used_unstructured = used_unstructured or part_used_unstructured
            fallback_used = fallback_used or part_used_fallback

            part_duration = time.perf_counter() - part_started
            logger.info(f"  Part {part_idx} completed: {len(part_chunks)} chunks extracted in {part_duration:.1f}s")
            log_to_job(f"Part {part_idx}/{total_parts} completed: {len(part_chunks)} chunks in {part_duration:.1f}s", self.job_log_file, "info", "C")

        chunks_file = pass_dir / f"{self.job_id}_pass_c_chunks.jsonl"
        with chunks_file.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(asdict(chunk), ensure_ascii=True))
                handle.write("\n")

        summary_path = pass_dir / "extraction_summary.json"
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "parts_processed": len(parts),
                    "chunks_extracted": len(chunks),
                    "used_unstructured": used_unstructured,
                    "fallback_used": fallback_used,
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )

        artifacts = [
            chunks_file.relative_to(job_dir).as_posix(),
            summary_path.relative_to(job_dir).as_posix(),
        ]

        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        duration_seconds = processing_time_ms / 1000

        logger.info(
            "pass_c_complete",
            extra={
                "job_id": self.job_id,
                "parts_processed": len(parts),
                "chunks": len(chunks),
                "duration_ms": processing_time_ms,
                "used_unstructured": used_unstructured,
                "fallback_used": fallback_used,
            },
        )

        # Pass complete logging
        stats = {
            "parts_processed": len(parts),
            "chunks_extracted": len(chunks),
            "used_unstructured": used_unstructured,
            "fallback_used": fallback_used
        }
        log_pass_complete("C", duration_seconds, stats, self.job_log_file)

        return PassCResult(
            job_id=self.job_id,
            parts_processed=len(parts),
            chunks_extracted=len(chunks),
            chunks_written=len(chunks),
            used_unstructured=used_unstructured,
            fallback_used=fallback_used,
            processing_time_ms=processing_time_ms,
            artifacts=artifacts,
            chunks_loaded=len(chunks),
        )

    def _discover_parts(self, job_dir: Path, source_pdf: Path) -> List[Path]:
        split_index = job_dir / "pass_b" / "split_index.json"
        if split_index.exists():
            with split_index.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if data.get("split_performed"):
                parts = []
                for part in data.get("parts", []):
                    relative_path = part.get("relative_path")
                    if not relative_path:
                        continue
                    part_path = job_dir / Path(relative_path)
                    if part_path.exists():
                        parts.append(part_path)
                if parts:
                    return parts
        return [source_pdf]

    def _extract_part(self, part_path: Path) -> tuple[List[ExtractionChunk], bool, bool]:
        lineage_prefix = part_path.stem
        try:
            if not UNSTRUCTURED_AVAILABLE:
                # Run OCR dependency validation to provide detailed error message
                validator = OCRValidator()
                validator.validate_all()
                error_msg = f"unstructured library not available: {UNSTRUCTURED_IMPORT_ERROR}\n{validator.get_summary()}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Log start of extraction (can take 30s+ for large PDFs)
            extraction_started = time.perf_counter()
            logger.info(f"Pass C: Starting unstructured.io extraction for {part_path.name} (this may take 30-60s for large PDFs)")

            elements = partition_pdf(
                filename=str(part_path),
                strategy="hi_res",
                infer_table_structure=True,
                include_metadata=True,
                ocr_languages=self.ocr_languages,
            )

            extraction_duration = time.perf_counter() - extraction_started
            logger.info(f"Pass C: Unstructured extraction completed in {extraction_duration:.1f}s, converting to chunks...")

            chunks = self._convert_unstructured_elements(elements, lineage_prefix)
            logger.info(
                "pass_c_unstructured_ok",
                extra={"job_id": self.job_id, "part": part_path.name, "chunks": len(chunks), "extraction_seconds": extraction_duration},
            )
            return chunks, True, False
        except Exception as exc:  # noqa: BLE001
            if not self.allow_fallback:
                logger.error(
                    "pass_c_unstructured_failed",
                    extra={"job_id": self.job_id, "part": part_path.name, "error": str(exc)},
                )
                raise
            logger.warning(
                "pass_c_fallback",
                extra={"job_id": self.job_id, "part": part_path.name, "reason": str(exc)},
            )
            chunks = self._fallback_chunks(part_path, lineage_prefix)
            return chunks, False, True

    def _convert_unstructured_elements(self, elements: Iterable[object], lineage_prefix: str) -> List[ExtractionChunk]:
        chunks: List[ExtractionChunk] = []
        for idx, element in enumerate(elements, start=1):
            text = getattr(element, "text", "") or ""
            if not text.strip():
                continue
            metadata = getattr(element, "metadata", None)
            lineage: Dict[str, str] = {}
            if metadata is not None:
                lineage.update(
                    {
                        key: str(getattr(metadata, key))
                        for key in ["category", "filename", "page_number", "text_as_html"]
                        if getattr(metadata, key, None)
                    }
                )
            page_number = int(lineage.get("page_number", 0)) or idx
            chunk_id = f"{lineage_prefix}-chunk-{idx:04d}"
            chunks.append(
                ExtractionChunk(
                    doc_id=self.job_id,
                    part_id=lineage_prefix,
                    section_id=lineage.get("category", "section"),
                    chunk_id=chunk_id,
                    text=text.strip(),
                    page_number=page_number,
                    lineage=lineage,
                    checksum_sha256=_sha256_text(text),
                )
            )
        return chunks

    def _fallback_chunks(self, part_path: Path, lineage_prefix: str) -> List[ExtractionChunk]:
        reader = PdfReader(str(part_path))
        chunks: List[ExtractionChunk] = []
        for index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:  # pragma: no cover - extractor guard
                text = ""
            if not text.strip():
                continue
            chunk_id = f"{lineage_prefix}-fallback-{index:04d}"
            chunks.append(
                ExtractionChunk(
                    doc_id=self.job_id,
                    part_id=lineage_prefix,
                    section_id=f"page-{index:04d}",
                    chunk_id=chunk_id,
                    text=text.strip(),
                    page_number=index,
                    lineage={"source": part_path.name, "generator": "pypdf"},
                    checksum_sha256=_sha256_text(text),
                )
            )
        return chunks


def process_pass_c(source_pdf: Path, job_dir: Path, job_id: str, env: str, job_log_file: Optional[Path] = None) -> PassCResult:
    runner = ExtractionRunner(job_id=job_id, env=env, job_log_file=job_log_file)
    return runner.process(source_pdf, job_dir)


def _sha256_text(text: str) -> str:
    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
