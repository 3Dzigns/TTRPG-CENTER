#!/usr/bin/env python3
"""
pass_b_chunker.py - Create Pass B document chunks
=================================================

Splits a source document into smaller files using page ranges produced by
pass_b_splitter. Writes chunk files into /Transfer_Station/Pass_B_Out by default,
preserving the original document format (PDF, DOCX, or TXT).

Usage:
  pass_b_chunker.py <source_document> <parts_manifest> [options]
  pass_b_chunker.py -v | --version
  pass_b_chunker.py -? | --help

Options:
  -o, --output DIR     Output directory (default: /Transfer_Station/Pass_B_Out)
  --prefix NAME        Filename prefix override (default based on document_id)
  --min-pages N        Optional override for minimum part length (validate manifest)
  --max-pages N        Optional override for maximum part length (validate manifest)
  --dry-run            Validate manifest and show planned operations only
  -v, --version        Show version
  -?, --help           Show help
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from path_utils import resolve_transfer_path

from doc_splitter import DocumentSplitterError, get_splitter


__version__ = "1.1.0"

DEFAULT_OUTPUT_DIR = resolve_transfer_path("Pass_B_Out")


class PassBChunkerError(Exception):
    """Raised when Pass B chunking fails."""


def load_manifest(manifest_path: Path) -> Dict:
    """Load and validate the pass_b_splitter manifest."""
    if not manifest_path.exists():
        raise PassBChunkerError(f"Manifest not found: {manifest_path}")

    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise PassBChunkerError(f"Failed to read manifest: {exc}") from exc

    if "parts" not in manifest or not isinstance(manifest["parts"], list):
        raise PassBChunkerError("Manifest missing 'parts' array.")

    return manifest


def validate_parts(
    parts: List[Dict],
    min_pages: Optional[int],
    max_pages: Optional[int],
    total_pages: int,
) -> None:
    """Ensure parts are within configured limits and document length."""
    if not parts:
        raise PassBChunkerError("Manifest contains no parts.")

    last_end = 0
    for part in parts:
        start = int(part.get("start_page", 0))
        end = int(part.get("end_page", 0))
        if start <= 0 or end <= 0 or end < start:
            raise PassBChunkerError(f"Invalid page range in part: {part}")
        if end > total_pages:
            raise PassBChunkerError(
                f"Part end page {end} exceeds document length ({total_pages})."
            )
        if start <= last_end:
            raise PassBChunkerError("Parts overlap or are not strictly ordered.")

        length = end - start + 1
        if min_pages and length < min_pages:
            raise PassBChunkerError(
                f"Part length {length} below min-pages threshold ({min_pages})."
            )
        if max_pages and length > max_pages:
            raise PassBChunkerError(
                f"Part length {length} above max-pages threshold ({max_pages})."
            )

        last_end = end


def split_document(
    splitter,
    source_path: Path,
    output_dir: Path,
    prefix: str,
    part: Dict,
) -> Path:
    """Use doc_splitter abstractions to extract a page range."""
    start = int(part["start_page"])
    end = int(part["end_page"])
    part_id = part.get("part") or part.get("part_number")
    suffix = f"{prefix}_part{part_id:02d}" if part_id is not None else f"{prefix}_{start}_{end}"
    destination = output_dir / f"{suffix}{source_path.suffix}"

    splitter.split(start, end, destination)
    return destination


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Split documents into Pass B chunks.",
        add_help=False,
    )

    parser.add_argument("document", type=Path, help="Source document path")
    parser.add_argument("manifest", type=Path, help="Pass B manifest JSON")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        help="Override filename prefix (default uses manifest document_id)",
    )
    parser.add_argument(
        "--min-pages",
        type=int,
        help="Optional validation override for minimum pages",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Optional validation override for maximum pages",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate and print planned operations",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pass_b_chunker v{__version__}",
    )
    parser.add_argument(
        "-?",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()
        source_path = args.document
        manifest_path = args.manifest

        manifest = load_manifest(manifest_path)
        document_id = manifest.get("document_id") or source_path.stem
        parts: List[Dict] = manifest["parts"]

        splitter = get_splitter(source_path)
        total_pages = splitter.get_total_pages()

        validate_parts(
            parts=parts,
            min_pages=args.min_pages,
            max_pages=args.max_pages,
            total_pages=total_pages,
        )

        prefix = args.prefix or document_id
        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)

        if args.dry_run:
            print("Dry run: planned Pass B chunks")
            for part in parts:
                print(
                    f"  Part {part.get('part')}: pages {part['start_page']}-{part['end_page']}"
                )
            return 0

        created_files: List[Path] = []
        for part in parts:
            destination = split_document(
                splitter=splitter,
                source_path=source_path,
                output_dir=output_dir,
                prefix=prefix,
                part=part,
            )
            created_files.append(destination)
            print(f"Created chunk: {destination.name} ({part['start_page']}-{part['end_page']})")

        print(f"\nCompleted Pass B chunking: {len(created_files)} files.")
        return 0

    except DocumentSplitterError as exc:
        print(f"Splitter error: {exc}", file=sys.stderr)
        return 1
    except PassBChunkerError as exc:
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
