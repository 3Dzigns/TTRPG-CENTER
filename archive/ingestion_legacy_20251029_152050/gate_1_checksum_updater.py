#!/usr/bin/env python3
"""
gate_1_checksum_updater.py - Gate 1 Checksum Regeneration
==========================================================

Regenerates Pass D checksums after database modifications to ensure chunk counts
match the current state of Cassandra embeddings. Updates pass_d_checksum.json
with accurate embedded chunk counts.

Usage:
  gate_1_checksum_updater.py <document_id> [options]
  gate_1_checksum_updater.py -v | --version
  gate_1_checksum_updater.py -? | --help

Arguments:
  document_id               Document ID to regenerate checksums for

Options:
  --pass-d-dir DIR          Pass D output directory (default: /Transfer_Station/Pass_D_Out)
  --host HOST               Cassandra host (default: n8n_TTRPG_cassandra)
  --port PORT               Cassandra port (default: 9042)
  --keyspace NAME           Cassandra keyspace (default: ttrpg_vectors)
  --dry-run                 Count chunks without updating checksum file
  -v, --version             Show version
  -?, --help                Show this help

Examples:
  gate_1_checksum_updater.py pathfinder_core_20251009_120000
  gate_1_checksum_updater.py doc_id --pass-d-dir /custom/path --dry-run

Output:
  Updates pass_d_checksum.json with current embedded chunk count from Cassandra

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from path_utils import resolve_transfer_path

try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
except ImportError:
    print("Error: cassandra-driver not installed. Run: pip install cassandra-driver", file=sys.stderr)
    sys.exit(1)


__version__ = "1.0.0"

DEFAULT_PASS_D_DIR = str(resolve_transfer_path("Pass_D_Out"))
DEFAULT_CASSANDRA_HOST = "n8n_TTRPG_cassandra"
DEFAULT_CASSANDRA_PORT = 9042
DEFAULT_CASSANDRA_KEYSPACE = "ttrpg_vectors"


class Gate1ChecksumUpdaterError(Exception):
    """Base exception for Gate 1 checksum updater errors."""
    pass


def count_cassandra_chunks(
    session,
    keyspace: str,
    document_id: str
) -> int:
    """
    Count embedded chunks for document_id in Cassandra.

    Args:
        session: Cassandra session
        keyspace: Keyspace name
        document_id: Document ID to count chunks for

    Returns:
        Number of embedded chunks

    Raises:
        Gate1ChecksumUpdaterError: If query fails
    """
    try:
        query = f"""
            SELECT COUNT(*) as count
            FROM {keyspace}.embeddings
            WHERE document_id = %s
            ALLOW FILTERING
        """

        result = session.execute(query, [document_id])
        row = result.one()

        if row:
            return row.count
        else:
            return 0

    except Exception as e:
        raise Gate1ChecksumUpdaterError(f"Failed to count Cassandra chunks: {e}")


def get_cassandra_metadata(
    session,
    keyspace: str,
    document_id: str
) -> Dict[str, Any]:
    """
    Get metadata about embedded chunks from Cassandra.

    Args:
        session: Cassandra session
        keyspace: Keyspace name
        document_id: Document ID

    Returns:
        Metadata dictionary with counts by part, element type, etc.

    Raises:
        Gate1ChecksumUpdaterError: If query fails
    """
    try:
        metadata = {
            "total_chunks": 0,
            "parts": {},
            "element_types": {}
        }

        # Count by part
        query_parts = f"""
            SELECT source_part, COUNT(*) as count
            FROM {keyspace}.embeddings
            WHERE document_id = %s
            ALLOW FILTERING
        """

        result = session.execute(query_parts, [document_id])
        for row in result:
            part_num = row.source_part if hasattr(row, 'source_part') else None
            count = row.count
            if part_num is not None:
                metadata["parts"][part_num] = count
            metadata["total_chunks"] += count

        # Count by element type
        query_types = f"""
            SELECT element_type, COUNT(*) as count
            FROM {keyspace}.embeddings
            WHERE document_id = %s
            ALLOW FILTERING
        """

        result = session.execute(query_types, [document_id])
        for row in result:
            element_type = row.element_type if hasattr(row, 'element_type') else "unknown"
            count = row.count
            metadata["element_types"][element_type] = count

        return metadata

    except Exception as e:
        raise Gate1ChecksumUpdaterError(f"Failed to get Cassandra metadata: {e}")


def find_pass_d_checksum_file(
    pass_d_dir: Path,
    document_id: str
) -> Optional[Path]:
    """
    Find existing pass_d_checksum.json file for document_id.

    Args:
        pass_d_dir: Pass D output directory
        document_id: Document ID

    Returns:
        Path to checksum file if found, None otherwise
    """
    # Try exact match
    checksum_file = pass_d_dir / f"{document_id}_pass_d_checksum.json"
    if checksum_file.exists():
        return checksum_file

    # Try finding by document_id prefix (in case filename differs)
    for file in pass_d_dir.glob("*_pass_d_checksum.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("document_id") == document_id:
                    return file
        except (IOError, json.JSONDecodeError):
            continue

    return None


def update_checksum_file(
    checksum_file: Path,
    document_id: str,
    chunk_count: int,
    metadata: Dict[str, Any],
    dry_run: bool = False
) -> None:
    """
    Update or create pass_d_checksum.json with new chunk count.

    Args:
        checksum_file: Path to checksum file
        document_id: Document ID
        chunk_count: Current embedded chunk count
        metadata: Additional metadata from Cassandra
        dry_run: If True, don't write file

    Raises:
        Gate1ChecksumUpdaterError: If file write fails
    """
    try:
        # Load existing checksum if present
        if checksum_file.exists():
            with open(checksum_file, 'r', encoding='utf-8') as f:
                checksum_data = json.load(f)
        else:
            checksum_data = {
                "document_id": document_id,
                "created_at": datetime.utcnow().isoformat() + 'Z'
            }

        # Update with new values
        old_count = checksum_data.get("embedded_chunks", 0)
        checksum_data["embedded_chunks"] = chunk_count
        checksum_data["updated_at"] = datetime.utcnow().isoformat() + 'Z'
        checksum_data["metadata"] = metadata

        # Track history
        if "history" not in checksum_data:
            checksum_data["history"] = []

        checksum_data["history"].append({
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "old_count": old_count,
            "new_count": chunk_count,
            "change": chunk_count - old_count,
            "reason": "gate_1_checksum_updater"
        })

        if dry_run:
            print(f"Dry run: Would update {checksum_file}")
            print(f"  Old count: {old_count}")
            print(f"  New count: {chunk_count}")
            print(f"  Change: {chunk_count - old_count:+d}")
            return

        # Write checksum file
        with open(checksum_file, 'w', encoding='utf-8') as f:
            json.dump(checksum_data, f, indent=2)

        print(f"✓ Updated checksum file: {checksum_file.name}")
        print(f"  Old count: {old_count}")
        print(f"  New count: {chunk_count}")
        print(f"  Change: {chunk_count - old_count:+d}")

    except IOError as e:
        raise Gate1ChecksumUpdaterError(f"Failed to write checksum file: {e}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Regenerate Pass D checksums after DB modifications',
        add_help=False
    )

    parser.add_argument(
        'document_id',
        nargs='?',
        type=str,
        help='Document ID to regenerate checksums for'
    )
    parser.add_argument(
        '--pass-d-dir',
        type=Path,
        default=Path(DEFAULT_PASS_D_DIR),
        help=f'Pass D output directory (default: {DEFAULT_PASS_D_DIR})'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=DEFAULT_CASSANDRA_HOST,
        help=f'Cassandra host (default: {DEFAULT_CASSANDRA_HOST})'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_CASSANDRA_PORT,
        help=f'Cassandra port (default: {DEFAULT_CASSANDRA_PORT})'
    )
    parser.add_argument(
        '--keyspace',
        type=str,
        default=DEFAULT_CASSANDRA_KEYSPACE,
        help=f'Cassandra keyspace (default: {DEFAULT_CASSANDRA_KEYSPACE})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Count chunks without updating checksum file'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'gate_1_checksum_updater v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    args = parser.parse_args()

    if not args.document_id:
        parser.print_help()
        sys.exit(1)

    return args


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        print(f"Gate 1 Checksum Updater v{__version__}")
        print(f"Document ID: {args.document_id}")
        print(f"Pass D directory: {args.pass_d_dir}")
        print(f"Cassandra: {args.host}:{args.port}/{args.keyspace}")
        print(f"Dry run: {args.dry_run}")
        print()

        # Verify Pass D directory exists
        if not args.pass_d_dir.exists():
            raise Gate1ChecksumUpdaterError(f"Pass D directory not found: {args.pass_d_dir}")

        # Connect to Cassandra
        print("Connecting to Cassandra...")
        cluster = Cluster([args.host], port=args.port)
        session = cluster.connect(args.keyspace)
        print("✓ Connected to Cassandra")

        # Count chunks in Cassandra
        print(f"\nCounting embedded chunks for {args.document_id}...")
        chunk_count = count_cassandra_chunks(session, args.keyspace, args.document_id)
        print(f"✓ Found {chunk_count:,} embedded chunks")

        # Get metadata
        print("\nGathering chunk metadata...")
        metadata = get_cassandra_metadata(session, args.keyspace, args.document_id)
        print(f"✓ Metadata gathered")
        print(f"  Parts: {len(metadata['parts'])}")
        print(f"  Element types: {len(metadata['element_types'])}")

        # Close Cassandra connection
        cluster.shutdown()

        # Find or create checksum file
        checksum_file = find_pass_d_checksum_file(args.pass_d_dir, args.document_id)
        if not checksum_file:
            checksum_file = args.pass_d_dir / f"{args.document_id}_pass_d_checksum.json"
            print(f"\nCreating new checksum file: {checksum_file.name}")
        else:
            print(f"\nUpdating existing checksum file: {checksum_file.name}")

        # Update checksum file
        update_checksum_file(checksum_file, args.document_id, chunk_count, metadata, args.dry_run)

        # Display metadata details
        if metadata["parts"]:
            print("\nChunks by part:")
            for part_num in sorted(metadata["parts"].keys()):
                count = metadata["parts"][part_num]
                print(f"  Part {part_num}: {count:,} chunks")

        if metadata["element_types"]:
            print("\nChunks by element type:")
            for element_type in sorted(metadata["element_types"].keys()):
                count = metadata["element_types"][element_type]
                print(f"  {element_type}: {count:,} chunks")

        print(f"\n✓ Checksum regeneration completed")

        return 0

    except Gate1ChecksumUpdaterError as e:
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
