#!/usr/bin/env python3
"""
gate_0_validate.py - Gate 0 Chunk Count Validation
==================================================

Validates that the expected chunk count (from Gate_0_Check) matches the
actual count in Cassandra. Returns the difference between actual and expected.

Usage:
  gate_0_validate.py <sha256_hash> [options]
  gate_0_validate.py -v | --version
  gate_0_validate.py -? | --help

Arguments:
  sha256_hash          64-character SHA-256 hash

Options:
  --check-dir DIR      Gate_0_Check directory (default: /Transfer_Station/Gate_0_Check)
  --quiet              Suppress output, only print difference value
  --json               Output as JSON
  -v, --version        Show version
  -?, --help           Show help

Examples:
  # Basic validation
  gate_0_validate.py 4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0

  # Quiet mode (just the difference number)
  gate_0_validate.py 4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0 --quiet

  # JSON output
  gate_0_validate.py 4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0 --json

Exit Codes:
  0 - Validation passed (counts match, difference = 0)
  1 - Mismatch detected (difference != 0 and != -1)
  2 - Unprocessed (both counts are 0, difference = -1)
  3 - Error (connection failure, invalid input, etc.)

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from path_utils import resolve_transfer_path


__version__ = "1.0.0"

DEFAULT_CHECK_DIR = resolve_transfer_path("Gate_0_Check")
DB_MANAGER_PATH = Path(__file__).resolve().parent / "db_manager.py"


class Gate0ValidationError(Exception):
    """Base exception for validation errors."""
    pass


class ChecksumFileError(Gate0ValidationError):
    """Error loading/parsing checksum file."""
    pass


class CassandraQueryError(Gate0ValidationError):
    """Error querying Cassandra."""
    pass


def validate_sha256_format(sha256: str) -> bool:
    """
    Validate SHA-256 hash format.

    Args:
        sha256: SHA-256 hash string

    Returns:
        True if valid format (64 hex characters)
    """
    return bool(re.match(r'^[0-9a-f]{64}$', sha256.lower()))


def load_checksum_file(sha256: str, check_dir: Path) -> Dict[str, Any]:
    """
    Load checksum file from Gate_0_Check directory.

    Args:
        sha256: SHA-256 hash
        check_dir: Gate_0_Check directory path

    Returns:
        Dict with 'document_id' and 'chunks_upserted' (defaults to 0 if missing)

    Raises:
        ChecksumFileError: If file exists but cannot be parsed
    """
    checksum_path = check_dir / f"{sha256}.json"

    # If file doesn't exist, return default values
    if not checksum_path.exists():
        return {
            "document_id": None,
            "chunks_upserted": 0,
            "file_found": False
        }

    # Try to load and parse the file
    try:
        with checksum_path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        return {
            "document_id": data.get("document_id"),
            "chunks_upserted": int(data.get("chunks_upserted", 0)),
            "file_found": True,
            "sha256_from_file": data.get("sha256"),
            "pass_d_manifest": data.get("pass_d_manifest")
        }

    except json.JSONDecodeError as e:
        raise ChecksumFileError(f"Invalid JSON in checksum file: {e}")
    except (ValueError, TypeError) as e:
        raise ChecksumFileError(f"Invalid chunks_upserted value: {e}")
    except Exception as e:
        raise ChecksumFileError(f"Failed to load checksum file: {e}")


def get_cassandra_state(document_id: Optional[str]) -> Dict[str, Any]:
    """
    Query Cassandra via db_manager for manifest-backed chunk info.

    Args:
        document_id: Document ID to query (None if no checksum file)

    Returns:
        Dictionary with chunk_count, checksum, and metadata.
    """
    state = {
        "chunk_count": 0,
        "vector_checksum": None,
        "manifest_found": False,
        "chunk_index_min": None,
        "chunk_index_max": None,
        "method": None,
    }

    if not document_id:
        return state

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(DB_MANAGER_PATH),
                "--count-document",
                document_id,
                "--cassandra-keyspace",
                "ttrpg_vectors",
                "--cassandra-table",
                "embeddings",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise CassandraQueryError(f"db_manager failed: {result.stderr}")

        in_manifest_section = False
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("Manifest:"):
                in_manifest_section = "not found" not in line.lower()
                state["manifest_found"] = in_manifest_section
                continue

            if in_manifest_section:
                if line.startswith("Chunk Count:"):
                    count_str = line.split(":", 1)[1].strip().split(" ")[0].replace(",", "")
                    try:
                        state["chunk_count"] = int(count_str)
                    except ValueError:
                        pass
                elif line.startswith("Vector Checksum:"):
                    checksum = line.split(":", 1)[1].strip()
                    state["vector_checksum"] = checksum or None
                elif line.startswith("Chunk Index Range:"):
                    _, range_str = line.split(":", 1)
                    bounds = [value.strip() for value in range_str.split("-")]
                    if len(bounds) == 2:
                        try:
                            state["chunk_index_min"] = int(bounds[0])
                            state["chunk_index_max"] = int(bounds[1])
                        except ValueError:
                            pass
                continue

            if line.startswith("Chunk Count (query):"):
                count_str = line.split(":", 1)[1].strip().replace(",", "")
                try:
                    state["chunk_count"] = int(count_str)
                except ValueError:
                    pass
            elif line.startswith("Method:"):
                state["method"] = line.split(":", 1)[1].strip()

        return state

    except subprocess.TimeoutExpired:
        raise CassandraQueryError("Cassandra query timeout (>120s)")
    except CassandraQueryError:
        raise
    except Exception as e:
        raise CassandraQueryError(f"Failed to query Cassandra: {e}")


def calculate_difference(expected: int, actual: int) -> int:
    """
    Calculate difference with special case handling.

    Args:
        expected: Expected chunk count from Gate_0_Check
        actual: Actual chunk count from Cassandra

    Returns:
        Difference (actual - expected), or -1 if both are 0
    """
    # Special case: both zero → return -1
    if expected == 0 and actual == 0:
        return -1

    return actual - expected


def validate_chunks(sha256: str, check_dir: Path) -> Dict[str, Any]:
    """
    Main validation function.

    Args:
        sha256: SHA-256 hash
        check_dir: Gate_0_Check directory path

    Returns:
        Validation result dictionary with status and counts

    Raises:
        Gate0ValidationError: On validation errors
    """
    checksum_data = load_checksum_file(sha256, check_dir)
    expected = checksum_data["chunks_upserted"]
    expected_checksum = checksum_data.get("vector_checksum")
    document_id = checksum_data["document_id"]

    cassandra_state = get_cassandra_state(document_id)
    actual = cassandra_state.get("chunk_count", 0) or 0
    actual_checksum = cassandra_state.get("vector_checksum")

    difference = calculate_difference(expected, actual)
    checksum_match = (
        expected_checksum is None
        or actual_checksum is None
        or expected_checksum == actual_checksum
    )

    if difference == -1:
        status = "unprocessed"
        validation_passed = False
    elif difference == 0 and checksum_match:
        status = "valid"
        validation_passed = True
    else:
        status = "mismatch"
        validation_passed = False

    return {
        "sha256": sha256,
        "document_id": document_id,
        "expected_chunks": expected,
        "actual_chunks": actual,
        "expected_checksum": expected_checksum,
        "actual_checksum": actual_checksum,
        "checksum_match": checksum_match,
        "manifest_found": cassandra_state.get("manifest_found", False),
        "chunk_index_min": cassandra_state.get("chunk_index_min"),
        "chunk_index_max": cassandra_state.get("chunk_index_max"),
        "validation_method": cassandra_state.get("method"),
        "difference": difference,
        "status": status,
        "validation_passed": validation_passed,
        "checksum_file_found": checksum_data["file_found"],
    }


def format_output(result: Dict[str, Any], quiet: bool, json_output: bool) -> str:
    """
    Format validation result for display.

    Args:
        result: Validation result dictionary
        quiet: Quiet mode (only print difference)
        json_output: JSON mode (print as JSON)

    Returns:
        Formatted output string
    """
    if quiet:
        # Quiet mode: just the difference number
        return str(result["difference"])

    if json_output:
        # JSON mode: full result as JSON
        return json.dumps(result, indent=2)

    # Normal mode: human-readable output
    lines = []
    lines.append("=" * 60)
    lines.append("Gate 0 Validation")
    lines.append("=" * 60)
    lines.append(f"SHA-256: {result['sha256']}")

    if result['document_id']:
        lines.append(f"Document ID: {result['document_id']}")
    else:
        lines.append("Document ID: Unknown (checksum file not found)")

    lines.append("")
    lines.append(f"Expected (Gate 0): {result['expected_chunks']:,} chunks")
    lines.append(f"Actual (Cassandra): {result['actual_chunks']:,} chunks")
    lines.append(f"Expected checksum: {result.get('expected_checksum') or 'N/A'}")
    lines.append(f"Actual checksum: {result.get('actual_checksum') or 'N/A'}")
    lines.append(f"Manifest Found: {'Yes' if result['manifest_found'] else 'No'}")
    if result['manifest_found']:
        lines.append(f"Chunk Index Range: {result.get('chunk_index_min')} - {result.get('chunk_index_max')}")
    if result.get('validation_method'):
        lines.append(f"Validation Method: {result['validation_method']}")

    # Format difference
    diff = result['difference']
    if diff == -1:
        lines.append("Difference: -1 (special case: both zero)")
    elif diff > 0:
        lines.append(f"Difference: +{diff:,}")
    elif diff < 0:
        lines.append(f"Difference: {diff:,}")
    else:
        lines.append("Difference: 0")

    lines.append("")

    # Status message
    if result['status'] == 'valid':
        lines.append("✓ Validation PASSED: Counts match")
    elif result['status'] == 'mismatch':
        lines.append("✗ Validation FAILED: Mismatch detected")
        if not result.get('checksum_match', True):
            lines.append("  Checksum mismatch detected between Gate 0 metadata and Cassandra manifest")
        lines.append("  Possible causes:")
        lines.append("    - Pass D run multiple times")
        lines.append("    - Manual Cassandra edits")
        lines.append("    - Checksum file out of date")
    elif result['status'] == 'unprocessed':
        lines.append("⚠ Validation SKIPPED: Document has not been processed through Pass D")

    if not result['checksum_file_found']:
        lines.append("")
        lines.append("Note: Checksum file not found (assumed expected = 0)")

    return '\n'.join(lines)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='gate_0_validate.py',
        description='Gate 0 chunk count validation',
        add_help=False
    )

    parser.add_argument(
        'sha256_hash',
        type=str,
        help='64-character SHA-256 hash'
    )
    parser.add_argument(
        '--check-dir',
        type=Path,
        default=DEFAULT_CHECK_DIR,
        help=f'Gate_0_Check directory (default: {DEFAULT_CHECK_DIR})'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output, only print difference value'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'gate_0_validate v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        # Validate SHA-256 format
        if not validate_sha256_format(args.sha256_hash):
            print(f"Error: Invalid SHA-256 format: {args.sha256_hash}", file=sys.stderr)
            print("Expected: 64 hexadecimal characters (0-9, a-f)", file=sys.stderr)
            return 3

        # Validate check directory exists
        if not args.check_dir.exists():
            print(f"Error: Check directory not found: {args.check_dir}", file=sys.stderr)
            return 3

        # Perform validation
        result = validate_chunks(args.sha256_hash, args.check_dir)

        # Format and print output
        output = format_output(result, args.quiet, args.json)
        print(output)

        # Determine exit code
        if result['status'] == 'valid':
            return 0  # Match
        elif result['status'] == 'unprocessed':
            return 2  # Both zero
        else:
            return 1  # Mismatch

    except ChecksumFileError as e:
        print(f"Error loading checksum file: {e}", file=sys.stderr)
        return 3
    except CassandraQueryError as e:
        print(f"Error querying Cassandra: {e}", file=sys.stderr)
        return 3
    except Gate0ValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
