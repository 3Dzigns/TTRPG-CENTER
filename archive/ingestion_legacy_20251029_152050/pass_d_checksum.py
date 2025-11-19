#!/usr/bin/env python3
"""
pass_d_checksum.py - Pass D Cassandra Upsert Checksum Writer
============================================================

Reads the Pass D manifest produced by pass_d_hayhooks.py, discovers the
corresponding Gate 0 marker, and writes a checksum record containing the
number of chunks upserted. The checksum file is stored as JSON named after
the document SHA-256 hash in the Gate 0 check folder.

Arguments:
  pass_d_manifest       Path to Pass D manifest JSON file.

Options:
  --output-dir DIR      Output directory (default: /Transfer_Station/Gate_0_Check).
  -v, --version         Show script version.
  -?, --help            Show this help message and exit.

Example:
  pass_d_checksum.py /Transfer_Station/Pass_D_Out/doc_pass_d_manifest.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List

from path_utils import resolve_transfer_path


__version__ = "1.1.0"

DEFAULT_OUTPUT_DIR = resolve_transfer_path("Gate_0_Check")
GATE_0_OUT_DIR = resolve_transfer_path("Gate_0_Out")


class PassDChecksumError(Exception):
    """Base exception for checksum processing errors."""


def load_json(path: Path, description: str) -> Dict[str, Any]:
    """Load JSON file with helpful error message."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise PassDChecksumError(f"{description} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PassDChecksumError(f"{description} is invalid JSON: {path}") from exc
    except OSError as exc:
        raise PassDChecksumError(f"Failed to read {description}: {path}") from exc


def extract_manifest_metadata(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Extract chunk count and checksum metadata from Pass D manifest."""
    cassandra_info = manifest.get("cassandra", {})
    processing_info = manifest.get("processing", {})

    chunk_value: Optional[Any] = cassandra_info.get("rows_inserted")
    if chunk_value is None:
        chunk_value = cassandra_info.get("chunk_count")
    if chunk_value is None:
        chunk_value = processing_info.get("embedded_chunks")

    if chunk_value is None:
        raise PassDChecksumError("Pass D manifest missing chunk count (rows_inserted/embedded_chunks).")

    try:
        chunk_count = int(chunk_value)
    except (TypeError, ValueError) as exc:
        raise PassDChecksumError(f"Invalid chunk count value: {chunk_value}") from exc

    return {
        "chunk_count": chunk_count,
        "vector_checksum": cassandra_info.get("vector_checksum"),
        "chunk_index_min": cassandra_info.get("chunk_index_min"),
        "chunk_index_max": cassandra_info.get("chunk_index_max"),
    }


def write_checksum(
    output_dir: Path,
    sha256: str,
    document_id: str,
    manifest_data: Dict[str, Any],
    manifest_path: Path
) -> Path:
    """Write checksum JSON file and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    checksum_path = output_dir / f"{sha256}.json"

    payload = {
        "document_id": document_id,
        "sha256": sha256,
        "chunks_upserted": manifest_data["chunk_count"],
        "vector_checksum": manifest_data.get("vector_checksum"),
        "chunk_index_min": manifest_data.get("chunk_index_min"),
        "chunk_index_max": manifest_data.get("chunk_index_max"),
        "pass_d_manifest": str(manifest_path)
    }

    try:
        with checksum_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except OSError as exc:
        raise PassDChecksumError(f"Failed to write checksum file: {checksum_path}") from exc

    return checksum_path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Create Gate 0 checksum file from Pass D manifest.",
        add_help=False
    )

    parser.add_argument(
        "pass_d_manifest",
        type=Path,
        help="Path to Pass D manifest JSON."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"pass_d_checksum v{__version__}"
    )
    parser.add_argument(
        "-?", "--help",
        action="help",
        help="Show this help message and exit."
    )

    args = parser.parse_args(argv)

    if not args.pass_d_manifest.exists():
        parser.error(f"Pass D manifest not found: {args.pass_d_manifest}")

    return args


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    try:
        args = parse_args(argv)
        manifest = load_json(args.pass_d_manifest, "Pass D manifest")
        document_id = manifest.get("document_id")
        if not document_id:
            raise PassDChecksumError("Pass D manifest missing document_id.")

        marker_path = GATE_0_OUT_DIR / f"{document_id}.json"
        marker = load_json(marker_path, "Gate 0 marker")

        sha256_hash = marker.get("sha256_hash")
        if not sha256_hash:
            raise PassDChecksumError(f"Gate 0 marker missing sha256_hash: {marker_path}")

        manifest_data = extract_manifest_metadata(manifest)
        checksum_path = write_checksum(
            args.output_dir,
            str(sha256_hash),
            str(document_id),
            manifest_data,
            args.pass_d_manifest.resolve()
        )

        print(
            f"Checksum written: {checksum_path} ({manifest_data['chunk_count']} chunks, "
            f"checksum={manifest_data.get('vector_checksum')})"
        )
        return 0

    except PassDChecksumError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
