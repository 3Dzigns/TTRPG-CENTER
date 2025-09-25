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

try:
    from unstructured.partition.pdf import partition_pdf  # type: ignore
    UNSTRUCTURED_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    partition_pdf = None
    UNSTRUCTURED_AVAILABLE = False

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


class ExtractionRunner:
    """Handles Pass C extraction logic."""

    def __init__(self, job_id: str, env: str) -> None:
        self.job_id = job_id
        self.env = env
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

        for part in parts:
            part_chunks, part_used_unstructured, part_used_fallback = self._extract_part(part)
            chunks.extend(part_chunks)
            used_unstructured = used_unstructured or part_used_unstructured
            fallback_used = fallback_used or part_used_fallback

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

        return PassCResult(
            job_id=self.job_id,
            parts_processed=len(parts),
            chunks_extracted=len(chunks),
            chunks_written=len(chunks),
            used_unstructured=used_unstructured,
            fallback_used=fallback_used,
            processing_time_ms=processing_time_ms,
            artifacts=artifacts,
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
                raise RuntimeError("unstructured library not available")

            elements = partition_pdf(
                filename=str(part_path),
                strategy="hi_res",
                infer_table_structure=True,
                include_metadata=True,
                ocr_languages=self.ocr_languages,
            )
            chunks = self._convert_unstructured_elements(elements, lineage_prefix)
            logger.info(
                "pass_c_unstructured_ok",
                extra={"job_id": self.job_id, "part": part_path.name, "chunks": len(chunks)},
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


def process_pass_c(source_pdf: Path, job_dir: Path, job_id: str, env: str) -> PassCResult:
    runner = ExtractionRunner(job_id=job_id, env=env)
    return runner.process(source_pdf, job_dir)


def _sha256_text(text: str) -> str:
    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
