#!/usr/bin/env python3
"""
gate_0_hash.py - Gate 0 File Validation (SHA-256 Hashing)
==========================================================

Computes SHA-256 hash of input file and creates validation marker
with document_id in Gate_0_Out directory for ingestion gating.

Usage:
  gate_0_hash.py <input_file> [options]
  gate_0_hash.py -v | --version
  gate_0_hash.py -? | --help

Arguments:
  input_file         Path to file for hash computation

Options:
  -o, --output DIR   Output directory (default: /Transfer_Station/Gate_0_Out)
  -q, --quiet        Suppress output, only print document_id
  --rebuild          Enable rebuild mode (default, clears document-specific DB entries)
  --no-rebuild       Disable rebuild (append-only mode)
  --rebuild-scope    Comma-separated list: mongodb,cassandra,neo4j (default: all)
  -v, --version      Show version
  -?, --help         Show this help

Examples:
  # Basic hash computation with rebuild (default)
  gate_0_hash.py /Transfer_Station/n8n_inbound/manual.pdf

  # Append-only mode (no cleanup)
  gate_0_hash.py /Transfer_Station/sources/doc.pdf --no-rebuild

  # Rebuild only Cassandra vectors
  gate_0_hash.py /Transfer_Station/sources/doc.pdf --rebuild-scope cassandra

Output:
  Creates file: <output_dir>/<document_id>.json

  JSON file containing:
    - document_id (sanitized filename + hash prefix)
    - original_filename
    - original_path
    - file_size_bytes
    - sha256_hash
    - computed_at (ISO 8601 timestamp)
    - rebuild_mode (boolean, v2.2.0)
    - rebuild_scope (dict, v2.2.0)

  document_id format: <sanitized_filename>_<sha_prefix>
  Example: pathfinder_core_rulebook_c6b1638fa012

Version: 2.2.0
Author: n8n TTRPG Center
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from path_utils import resolve_transfer_path


__version__ = "2.2.0"


class Gate0Error(Exception):
    """Base exception for Gate 0 errors."""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for use in document_id.

    Args:
        filename: Original filename (with or without extension)

    Returns:
        Sanitized filename (lowercase, alphanumeric + underscores)
    """
    # Remove extension
    name_without_ext = Path(filename).stem

    # Convert to lowercase
    sanitized = name_without_ext.lower()

    # Replace spaces and special characters with underscores
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')

    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Limit length to 100 characters
    if len(sanitized) > 100:
        sanitized = sanitized[:100].rstrip('_')

    return sanitized


def generate_document_id(file_path: Path, sha256_hash: str) -> str:
    """
    Generate deterministic document_id from filename and hash.

    Args:
        file_path: Path to input file
        sha256_hash: SHA-256 hash string for the file

    Returns:
        document_id in format: <sanitized_filename>_<sha[:12]>
        Example: pathfinder_core_rulebook_c6b1638fa012
    """
    sanitized_name = sanitize_filename(file_path.name)
    hash_prefix = sha256_hash[:12] if sha256_hash else 'unknown'
    return f"{sanitized_name}_{hash_prefix}"


def compute_sha256(file_path: Path, chunk_size: int = 8192) -> str:
    """
    Compute SHA-256 hash of file.

    Args:
        file_path: Path to input file
        chunk_size: Buffer size for reading file (default: 8KB)

    Returns:
        Hexadecimal SHA-256 hash string (64 characters, 0-9a-f)

    Raises:
        Gate0Error: If file cannot be read
    """
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, 'rb') as f:
            # Read file in chunks to handle large files efficiently
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    except IOError as e:
        raise Gate0Error(f"Failed to read file: {e}")


def create_gate_marker(
    file_path: Path,
    output_dir: Path,
    rebuild_mode: bool = True,
    rebuild_scope: Optional[list] = None,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Create Gate 0 validation marker file with document_id and rebuild flags.

    Args:
        file_path: Path to input file
        output_dir: Directory for gate marker files
        rebuild_mode: If True, enable document-specific DB cleanup (default: True)
        rebuild_scope: List of databases to rebuild (default: all)
        quiet: If True, suppress verbose output

    Returns:
        Dict with processing results

    Raises:
        Gate0Error: If processing fails
    """
    if not file_path.exists():
        raise Gate0Error(f"Input file not found: {file_path}")

    if not file_path.is_file():
        raise Gate0Error(f"Input path is not a file: {file_path}")

    if not quiet:
        print(f"Processing: {file_path.name}")
        print("Computing SHA-256 hash...")

    sha256_hash = compute_sha256(file_path)

    # Generate document_id using deterministic hash-based suffix
    document_id = generate_document_id(file_path, sha256_hash)

    if not quiet:
        print(f"Document ID: {document_id}")
        print(f"SHA-256: {sha256_hash}")

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create marker file named with document_id
    marker_filename = f"{document_id}.json"
    marker_path = output_dir / marker_filename

    # v2.2.0: Determine rebuild scope
    if rebuild_scope is None:
        rebuild_scope = ['mongodb', 'cassandra', 'neo4j']

    rebuild_scope_dict = {
        'mongodb': 'mongodb' in rebuild_scope,
        'cassandra': 'cassandra' in rebuild_scope,
        'neo4j': 'neo4j' in rebuild_scope
    }

    try:
        # Write metadata JSON to marker file with rebuild flags
        metadata = {
            "document_id": document_id,
            "original_filename": file_path.name,
            "original_path": str(file_path),
            "file_size_bytes": file_path.stat().st_size,
            "sha256_hash": sha256_hash,
            "computed_at": datetime.utcnow().isoformat() + 'Z',
            # v2.2.0: Rebuild flags
            "rebuild_mode": rebuild_mode,
            "rebuild_scope": rebuild_scope_dict
        }

        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        if not quiet:
            print(f"Created marker: {marker_filename}")
            if rebuild_mode:
                enabled_scopes = [k for k, v in rebuild_scope_dict.items() if v]
                print(f"Rebuild mode: enabled ({', '.join(enabled_scopes)})")
            else:
                print("Rebuild mode: disabled (append-only)")

    except IOError as e:
        raise Gate0Error(f"Failed to create marker file: {e}")

    return {
        "document_id": document_id,
        "input_file": str(file_path),
        "sha256_hash": sha256_hash,
        "marker_file": str(marker_path),
        "file_size": file_path.stat().st_size,
        "rebuild_mode": rebuild_mode,
        "rebuild_scope": rebuild_scope_dict
    }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Gate 0 file validation (SHA-256 hashing)',
        add_help=False
    )

    parser.add_argument(
        'input_file',
        nargs='?',
        type=Path,
        help='Path to input file'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=resolve_transfer_path('Gate_0_Out'),
        help=f'Output directory (default: {resolve_transfer_path("Gate_0_Out")})'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output, only print document_id'
    )

    # v2.2.0: Rebuild mode flags
    rebuild_group = parser.add_mutually_exclusive_group()
    rebuild_group.add_argument(
        '--rebuild',
        action='store_true',
        default=True,
        help='Enable rebuild mode (default, clears document-specific DB entries)'
    )
    rebuild_group.add_argument(
        '--no-rebuild',
        action='store_true',
        help='Disable rebuild (append-only mode)'
    )
    parser.add_argument(
        '--rebuild-scope',
        type=str,
        default='mongodb,cassandra,neo4j',
        help='Comma-separated list: mongodb,cassandra,neo4j (default: all)'
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'gate_0_hash v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    args = parser.parse_args()

    if not args.input_file:
        parser.print_help()
        sys.exit(1)

    return args


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        # v2.2.0: Parse rebuild parameters
        rebuild_mode = not args.no_rebuild  # If --no-rebuild is set, disable rebuild
        rebuild_scope = [s.strip() for s in args.rebuild_scope.split(',') if s.strip()]

        # Create gate marker with rebuild flags
        result = create_gate_marker(
            file_path=args.input_file,
            output_dir=args.output,
            rebuild_mode=rebuild_mode,
            rebuild_scope=rebuild_scope,
            quiet=args.quiet
        )

        # Quiet mode: only print document_id
        if args.quiet:
            print(result['document_id'])
        else:
            # Verbose success message
            print(
                f"\n✓ Gate 0 validation complete\n"
                f"  Document ID: {result['document_id']}\n"
                f"  Input: {Path(result['input_file']).name}\n"
                f"  Size: {result['file_size']:,} bytes\n"
                f"  SHA-256: {result['sha256_hash']}\n"
                f"  Marker: {Path(result['marker_file']).name}"
            )

        return 0

    except Gate0Error as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
