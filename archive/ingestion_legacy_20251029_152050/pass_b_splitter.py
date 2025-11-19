#!/usr/bin/env python3
"""
pass_b_splitter.py - Logical document splitter (Pass B)
=======================================================

Creates concise split plans for downstream Pass B processing. Uses TOC metadata
to group sections into 5–20 page page ranges while keeping logical boundaries.

Usage:
  pass_b_splitter.py <document> <metadata_json> [options]
  pass_b_splitter.py -v | --version
  pass_b_splitter.py -? | --help

Arguments:
  document              Path to source document (PDF/DOCX/TXT)
  metadata_json         Path to metadata JSON from Pass A

Options:
  -o, --output DIR      Output directory (default: /Transfer_Station/Pass_B_Out)
  --output-file FILE    Explicit manifest file path (overrides --output)
  --min-pages N         Minimum pages per logical part (default: 5)
  --max-pages N         Maximum pages per logical part (default: 20)
  --prefix NAME         Override output filename prefix
  -v, --version         Show version information
  -?, --help            Display help message

Output:
  JSON manifest with simplified chunks ready for doc_splitter, for example:
    {
      "document_id": "...",
      "parts": [
        {"part": 1, "start_page": 1, "end_page": 18},
        {"part": 2, "start_page": 19, "end_page": 35}
      ]
    }

Version: 1.2.0
Author: n8n TTRPG Center
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from path_utils import resolve_transfer_path

from doc_splitter import DocumentSplitterError, get_splitter


__version__ = "1.2.0"

DEFAULT_OUTPUT_DIR = resolve_transfer_path("Pass_B_Out")
DEFAULT_MIN_PAGES = 5
DEFAULT_MAX_PAGES = 20


class PassBSplitterError(Exception):
    """Raised when Pass B splitting fails."""


@dataclass
class TOCEntry:
    title: str
    level: int
    page_start: int
    page_end: int
    category: Optional[str] = None

    @property
    def page_count(self) -> int:
        return max(1, self.page_end - self.page_start + 1)


def load_metadata(metadata_path: Path) -> Dict[str, Any]:
    """Load metadata JSON from disk."""
    if not metadata_path.exists():
        raise PassBSplitterError(f"Metadata file not found: {metadata_path}")

    try:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise PassBSplitterError(f"Failed to read metadata JSON: {exc}") from exc


def normalize_toc_entries(metadata: Dict[str, Any]) -> List[TOCEntry]:
    """Extract and normalize TOC entries from metadata."""
    toc_data = metadata.get("toc_structure") or metadata.get("toc", [])

    if not toc_data or not isinstance(toc_data, Sequence):
        raise PassBSplitterError("Metadata missing toc_structure sequence.")

    entries: List[TOCEntry] = []

    for raw in toc_data:
        if not isinstance(raw, dict):
            continue

        page_start = int(raw.get("page_start") or raw.get("page", 0) or 0)
        page_end = raw.get("page_end")

        if page_end is None:
            # If metadata didn't capture an end page, assume single-page entry.
            page_end = page_start

        try:
            page_end = int(page_end)
        except (TypeError, ValueError):
            page_end = page_start

        if page_start <= 0:
            continue

        entry = TOCEntry(
            title=str(raw.get("title") or raw.get("name") or "Untitled"),
            level=int(raw.get("level") or 1),
            page_start=min(page_start, page_end),
            page_end=max(page_start, page_end),
            category=raw.get("category"),
        )
        entries.append(entry)

    if not entries:
        raise PassBSplitterError("No usable TOC entries found in metadata.")

    entries.sort(key=lambda entry: (entry.page_start, entry.level))
    return entries


def sanitize_basename(name: str) -> str:
    """Return filesystem-safe stem for naming outputs."""
    stem = Path(name).stem
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)
    return safe.strip("_") or "document"


def extract_anchor_pages(
    toc_entries: List[TOCEntry],
    total_pages: int,
    prefer_levels: Sequence[int],
) -> List[int]:
    """Collect candidate anchor pages from metadata within document bounds."""
    anchors: Set[int] = set()

    for entry in toc_entries:
        if entry.page_start <= 0 or entry.page_start > total_pages:
            continue
        if prefer_levels and entry.level not in prefer_levels:
            continue
        anchors.add(entry.page_start)
        if entry.page_end > 0:
            anchors.add(min(entry.page_end, total_pages))

    anchors.add(1)
    anchors.add(total_pages)

    return sorted(anchors)


def build_logical_parts(
    entries: List[TOCEntry],
    min_pages: int,
    max_pages: int,
    total_pages: int,
    prefer_levels: Sequence[int] = (1, 2),
) -> List[Dict[str, int]]:
    """Group pages into logical parts respecting page constraints."""
    if min_pages <= 0 or max_pages <= 0:
        raise PassBSplitterError("Page limits must be positive integers.")
    if min_pages > max_pages:
        raise PassBSplitterError("Minimum pages cannot exceed maximum pages.")
    if total_pages <= 0:
        raise PassBSplitterError("Unable to determine document page count.")

    anchors = extract_anchor_pages(entries, total_pages, prefer_levels)
    parts: List[Dict[str, int]] = []
    part_start = 1

    def append_part(end_page: int) -> None:
        nonlocal part_start
        end_page = min(end_page, total_pages)
        if end_page < part_start:
            end_page = part_start
        part_number = len(parts) + 1
        parts.append({"part": part_number, "start_page": part_start, "end_page": end_page})
        part_start = end_page + 1

    while part_start <= total_pages:
        desired_end = min(part_start + max_pages - 1, total_pages)
        candidate = max(
            (a for a in anchors if part_start + min_pages - 1 <= a <= desired_end),
            default=None,
        )
        if candidate is None:
            candidate = desired_end

        if candidate - part_start + 1 < min_pages and candidate < total_pages:
            candidate = min(part_start + min_pages - 1, total_pages)

        append_part(candidate)

    return parts


def determine_total_pages(source_file: Path) -> int:
    """Use doc_splitter helpers to count total pages."""
    try:
        splitter = get_splitter(source_file)
        total = splitter.get_total_pages()
        return int(total)
    except DocumentSplitterError as exc:
        raise PassBSplitterError(f"Unable to determine total pages: {exc}") from exc


def write_output(
    output_dir: Path,
    filename_prefix: str,
    document_id: str,
    parts: List[Dict[str, int]],
    total_pages: int,
    output_file: Optional[Path] = None,
) -> Path:
    """Write split manifest to JSON."""
    utc_now = datetime.now(timezone.utc)

    if output_file:
        output_path = output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = utc_now.strftime("%Y%m%d_%H%M%S")
        output_name = f"{filename_prefix}_pass_b_splits_{timestamp}.json"
        output_path = output_dir / output_name

    payload: Dict[str, Any] = {
        "document_id": document_id,
        "generated_at": utc_now.isoformat(),
        "total_pages": total_pages,
        "parts": parts,
    }

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    return output_path


def extract_document_id(metadata: Dict[str, Any], source: Path) -> str:
    """Derive document identifier from metadata or source filename."""
    if isinstance(metadata.get("document"), dict):
        doc_id = metadata["document"].get("document_id")
        if doc_id:
            return str(doc_id)

    if "document_id" in metadata:
        return str(metadata["document_id"])

    return sanitize_basename(source.stem)


def parse_args() -> argparse.Namespace:
    """Configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Create logical Pass B split manifest from metadata.",
        add_help=False,
    )

    parser.add_argument("document", type=Path, help="Source document path")
    parser.add_argument("metadata_json", type=Path, help="Metadata JSON path")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help="Optional explicit output manifest path",
    )
    parser.add_argument(
        "--min-pages",
        type=int,
        default=DEFAULT_MIN_PAGES,
        help=f"Minimum pages per part (default: {DEFAULT_MIN_PAGES})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Maximum pages per part (default: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        help="Optional override for output filename prefix",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pass_b_splitter v{__version__}",
    )
    parser.add_argument(
        "-?",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    return parser.parse_args()


def main() -> int:
    """Entry point."""
    try:
        args = parse_args()
        source_path = args.document
        metadata_path = args.metadata_json

        metadata = load_metadata(metadata_path)
        toc_entries = normalize_toc_entries(metadata)
        total_pages = determine_total_pages(source_path)

        parts = build_logical_parts(
            entries=toc_entries,
            min_pages=args.min_pages,
            max_pages=args.max_pages,
            total_pages=total_pages,
        )

        document_id = extract_document_id(metadata, source_path)
        prefix = args.prefix or sanitize_basename(document_id)
        output_file = args.output_file

        manifest_path = write_output(
            output_dir=args.output,
            filename_prefix=prefix,
            document_id=document_id,
            parts=parts,
            total_pages=total_pages,
            output_file=output_file,
        )

        print(
            f"Created Pass B split manifest ({len(parts)} parts): "
            f"{manifest_path.name}"
        )
        return 0

    except PassBSplitterError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
