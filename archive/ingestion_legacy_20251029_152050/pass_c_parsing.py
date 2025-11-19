#!/usr/bin/env python3
"""
pass_c_parsing.py - Pass C Unstructured Parsing
================================================

Runs pass_a_unstructured.py over each Pass B chunk listed in a manifest,
producing structured JSON outputs in /Transfer_Station/Pass_C_Out (by default).

Usage:
  pass_c_parsing.py <manifest_json> [options]
  pass_c_parsing.py -v | --version
  pass_c_parsing.py -? | --help

Options mirror pass_a_unstructured defaults to keep behavior aligned with the
wrapper pipeline.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from path_utils import resolve_transfer_path


__version__ = "1.0.0"

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_CHUNKS_DIR = resolve_transfer_path("Pass_B_Out")
DEFAULT_OUTPUT_DIR = resolve_transfer_path("Pass_C_Out")
DEFAULT_LANGUAGE = "eng"
DEFAULT_STRATEGY = "hi_res"


class PassCParsingError(Exception):
    """Raised when Pass C parsing fails."""


def load_manifest(manifest_path: Path) -> Dict:
    if not manifest_path.exists():
        raise PassCParsingError(f"Manifest not found: {manifest_path}")
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PassCParsingError(f"Failed to read manifest: {exc}") from exc

    if "document_id" not in manifest:
        raise PassCParsingError("Manifest missing document_id.")
    if "parts" not in manifest or not isinstance(manifest["parts"], list):
        raise PassCParsingError("Manifest missing parts array.")
    return manifest


def discover_chunk_path(
    chunks_dir: Path,
    document_id: str,
    part_number: int
) -> Optional[Path]:
    expected_prefix = f"{document_id}_part{part_number:02d}"
    candidates = list(chunks_dir.glob(f"{expected_prefix}*"))
    if candidates:
        return candidates[0]

    # fallback: scan entire directory for prefix if numbering differs
    for file in chunks_dir.iterdir():
        if file.is_file() and file.name.startswith(expected_prefix):
            return file
    return None


def run_pass_a_unstructured(
    chunk_path: Path,
    output_dir: Path,
    strategy: str,
    language: str,
    toc_only: bool,
    max_pages: int,
) -> subprocess.CompletedProcess:
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        str(sys.executable),
        str(SCRIPTS_DIR / "pass_a_unstructured.py"),
        str(chunk_path),
        "-o", str(output_dir),
        "-l", language,
        "-s", strategy,
    ]

    if toc_only:
        command.append("--toc-only")
        if max_pages:
            command.extend(["-m", str(max_pages)])

    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pass_a_unstructured on Pass B chunks (Pass C parsing).",
        add_help=False,
    )

    parser.add_argument("manifest", type=Path, help="Pass B manifest JSON path")
    parser.add_argument(
        "-b",
        "--chunks-dir",
        type=Path,
        default=DEFAULT_CHUNKS_DIR,
        help=f"Directory containing Pass B chunks (default: {DEFAULT_CHUNKS_DIR})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for Pass C JSON (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default=DEFAULT_STRATEGY,
        help=f"Unstructured strategy (default: {DEFAULT_STRATEGY})",
    )
    parser.add_argument(
        "--language",
        type=str,
        default=DEFAULT_LANGUAGE,
        help=f"OCR language (default: {DEFAULT_LANGUAGE})",
    )
    parser.add_argument(
        "--toc-only",
        action="store_true",
        help="Reuse TOC-only extraction mode",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=8,
        help="Maximum pages when using --toc-only (default: 8)",
    )
    parser.add_argument(
        "--parts",
        type=int,
        nargs="+",
        help="Optional specific part numbers to process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned operations without executing pass_a_unstructured",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pass_c_parsing v{__version__}",
    )
    parser.add_argument(
        "-?",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        manifest = load_manifest(args.manifest)
        document_id = manifest["document_id"]
        parts: List[Dict] = manifest["parts"]

        if args.parts:
            filtered_parts = [
                part for part in parts
                if int(part.get("part") or part.get("part_number") or 0) in args.parts
            ]
        else:
            filtered_parts = parts

        if not filtered_parts:
            raise PassCParsingError("No matching parts to process.")

        print(f"Pass C parsing for document {document_id}: {len(filtered_parts)} parts")

        for part in filtered_parts:
            part_number = int(part.get("part") or part.get("part_number") or 0)
            chunk_path = discover_chunk_path(args.chunks_dir, document_id, part_number)

            if not chunk_path:
                raise PassCParsingError(
                    f"Chunk file missing for part {part_number} in {args.chunks_dir}"
                )

            if args.dry_run:
                print(f"[DRY RUN] Would process: {chunk_path.name}")
                continue

            result = run_pass_a_unstructured(
                chunk_path=chunk_path,
                output_dir=args.output,
                strategy=args.strategy,
                language=args.language,
                toc_only=args.toc_only,
                max_pages=args.max_pages,
            )

            if result.returncode != 0:
                raise PassCParsingError(
                    f"pass_a_unstructured failed for {chunk_path.name}: {result.stderr.strip()}"
                )

            print(f"Processed chunk: {chunk_path.name}")

        if args.dry_run:
            print("Dry run complete. No files processed.")
        else:
            print("Pass C parsing completed successfully.")

        return 0

    except PassCParsingError as exc:
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
