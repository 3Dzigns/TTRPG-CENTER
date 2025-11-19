#!/usr/bin/env python3
"""
pass_d_hayhooks.py - Vector Embedding Generation and Storage (Pass D)
======================================================================

Generates OpenAI embeddings for document chunks and stores vectors in Cassandra.
Takes Pass B manifest as input and auto-discovers Pass C element files.
Supports document-specific cleanup via Gate 0 rebuild flags (v3.0.0).

Usage:
  pass_d_hayhooks.py <pass_b_manifest> [options]
  pass_d_hayhooks.py -v | --version
  pass_d_hayhooks.py -? | --help

Arguments:
  pass_b_manifest    Path to Pass B manifest JSON

Options:
  -o, --output DIR       Output directory (default: /Transfer_Station/Pass_D_Out)
  --pass-c-dir DIR       Pass C output directory (default: /Transfer_Station/Pass_C_Out)
  --host HOST            Cassandra host (default: n8n_TTRPG_cassandra)
  --port PORT            Cassandra port (default: 9042)
  --keyspace NAME        Cassandra keyspace (default: ttrpg_vectors)
  --batch-size N         Embedding batch size (default: 100)
  --gate-marker FILE     Gate 0 marker file (v3.0.0, enables rebuild mode)
  --create-schema        Create Cassandra schema if not exists
  --dry-run              Validate input without processing
  -v, --version          Show version
  -?, --help             Show this help

Examples:
  # With Gate 0 marker (rebuild mode enabled)
  pass_d_hayhooks.py /Transfer_Station/Pass_B_Out/document_manifest.json \
    --gate-marker /Transfer_Station/Gate_0_Out/document_20251009_120000.json

  # Create schema first
  pass_d_hayhooks.py /Transfer_Station/Pass_B_Out/manifest.json --create-schema

  # Custom Pass C directory
  pass_d_hayhooks.py /Transfer_Station/Pass_B_Out/manifest.json --pass-c-dir /custom/path

  # Dry run validation
  pass_d_hayhooks.py /Transfer_Station/Pass_B_Out/manifest.json --dry-run

Version: 3.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from path_utils import resolve_transfer_path
from cassandra_manifest import (
    compute_chunk_metrics,
    ensure_manifest_table,
    upsert_manifest,
    ManifestRecord,
)
from secrets_utils import read_secret

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed, using system environment only", file=sys.stderr)

# OpenAI client
try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)

# Cassandra driver
try:
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.query import SimpleStatement
    from cassandra import ConsistencyLevel
except ImportError:
    print("Error: cassandra-driver not installed. Run: pip install cassandra-driver", file=sys.stderr)
    sys.exit(1)


__version__ = "3.0.0"

# Configuration
DEFAULT_OUTPUT_DIR = str(resolve_transfer_path("Pass_D_Out"))
DEFAULT_PASS_C_DIR = str(resolve_transfer_path("Pass_C_Out"))
DEFAULT_CASSANDRA_HOST = "ttrpg_cassandra"
DEFAULT_CASSANDRA_PORT = 9042
DEFAULT_KEYSPACE = "ttrpg_vectors"
DEFAULT_BATCH_SIZE = 100
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
# Character-based chunking for fine-grained semantic search
MIN_CHUNK_CHARS = 500
MAX_CHUNK_CHARS = 600
CHUNK_OVERLAP = 50


class PassDHayhooksError(Exception):
    """Base exception for Pass D Hayhooks errors."""
    pass


def validate_openai_key() -> str:
    """
    Retrieve and validate OpenAI API key from Docker secrets or environment.

    Returns:
        API key string

    Raises:
        PassDHayhooksError: If key is missing or invalid format
    """
    api_key = read_secret("openai_api_key", "OPENAI_API_KEY")

    if not api_key:
        raise PassDHayhooksError(
            "OPENAI_API_KEY not found in Docker secrets or environment.\n"
            "Create Docker secret: echo 'sk-...' | docker secret create openai_api_key -\n"
            "Or set .env file with: OPENAI_API_KEY=sk-..."
        )

    if not api_key.startswith("sk-"):
        raise PassDHayhooksError(
            f"Invalid OPENAI_API_KEY format: {api_key[:10]}...\n"
            "Expected format: sk-..."
        )

    return api_key


def load_pass_b_manifest(manifest_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Load Pass B manifest and extract document_id and parts.

    Args:
        manifest_path: Path to Pass B manifest JSON

    Returns:
        Tuple of (document_id, parts list)

    Raises:
        PassDHayhooksError: If manifest cannot be loaded or is invalid
    """
    if not manifest_path.exists():
        raise PassDHayhooksError(f"Pass B manifest not found: {manifest_path}")

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        raise PassDHayhooksError(f"Invalid JSON in Pass B manifest: {e}")
    except IOError as e:
        raise PassDHayhooksError(f"Failed to read Pass B manifest: {e}")

    # Extract document_id and parts
    document_id = manifest.get('document_id')
    if not document_id:
        raise PassDHayhooksError("Pass B manifest missing 'document_id' field")

    parts = manifest.get('parts')
    if not parts or not isinstance(parts, list):
        raise PassDHayhooksError("Pass B manifest missing or invalid 'parts' array")

    return document_id, parts


def discover_pass_c_files(
    document_id: str,
    parts: List[Dict[str, Any]],
    pass_c_dir: Path
) -> List[Dict[str, Any]]:
    """
    Discover Pass C element and metadata files from Pass B parts.

    Args:
        document_id: Document identifier
        parts: List of part dictionaries from Pass B manifest
        pass_c_dir: Directory containing Pass C output files

    Returns:
        List of discovered file info dicts

    Raises:
        PassDHayhooksError: If no element files are found
    """
    discovered_files = []

    for part in parts:
        part_num = part.get('part')
        if part_num is None:
            print(f"Warning: Part missing 'part' number: {part}")
            continue

        # Look for element file (required)
        element_filename = f"{document_id}_part{part_num:02d}_elements.json"
        element_path = pass_c_dir / element_filename

        if not element_path.exists():
            print(f"Warning: Element file not found: {element_filename}")
            continue

        # Look for metadata file (optional)
        metadata_filename = f"{document_id}_part{part_num:02d}_metadata.json"
        metadata_path = pass_c_dir / metadata_filename

        file_info = {
            'part': part_num,
            'element_file': element_path,
            'element_filename': element_filename,
            'metadata_file': metadata_path if metadata_path.exists() else None,
            'metadata_filename': metadata_filename if metadata_path.exists() else None,
            'has_metadata': metadata_path.exists()
        }

        if not metadata_path.exists():
            print(f"Info: Metadata file not found (optional): {metadata_filename}")

        discovered_files.append(file_info)

    if not discovered_files:
        raise PassDHayhooksError(
            f"No Pass C element files found in {pass_c_dir}\n"
            f"Expected pattern: {document_id}_part##_elements.json"
        )

    print(f"✓ Discovered {len(discovered_files)} element files from {len(parts)} parts")
    return discovered_files


def load_elements_from_files(
    discovered_files: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load all elements from discovered Pass C files.

    Args:
        discovered_files: List of file info dicts from discover_pass_c_files

    Returns:
        Tuple of (combined elements list, parts detail dict)

    Raises:
        PassDHayhooksError: If element files cannot be loaded
    """
    all_elements = []
    parts_detail = []

    for file_info in discovered_files:
        try:
            # Load element file
            with open(file_info['element_file'], 'r', encoding='utf-8') as f:
                elements = json.load(f)

            if not isinstance(elements, list):
                raise PassDHayhooksError(
                    f"Invalid elements format in {file_info['element_filename']}: "
                    f"expected list, got {type(elements)}"
                )

            # Optionally load metadata
            metadata = None
            if file_info['metadata_file']:
                try:
                    with open(file_info['metadata_file'], 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except Exception as e:
                    print(f"Warning: Could not load metadata file: {e}")

            # Add part number to each element for tracking
            for elem in elements:
                elem['source_part'] = file_info['part']

            all_elements.extend(elements)

            parts_detail.append({
                'part': file_info['part'],
                'element_file': file_info['element_filename'],
                'element_count': len(elements),
                'metadata_found': file_info['has_metadata']
            })

            print(f"  Part {file_info['part']:02d}: {len(elements)} elements loaded")

        except IOError as e:
            raise PassDHayhooksError(
                f"Failed to read element file {file_info['element_filename']}: {e}"
            )
        except json.JSONDecodeError as e:
            raise PassDHayhooksError(
                f"Invalid JSON in {file_info['element_filename']}: {e}"
            )

    return all_elements, {'parts_detail': parts_detail}


def load_pass_c_metadata(document_id: str, pass_c_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Load Pass C metadata file for document.

    Args:
        document_id: Document identifier
        pass_c_dir: Directory containing Pass C metadata

    Returns:
        Metadata dictionary or None if not found

    Raises:
        PassDHayhooksError: If metadata file exists but cannot be loaded
    """
    metadata_filename = f"{document_id}_pass_c_metadata.json"
    metadata_path = pass_c_dir / metadata_filename

    if not metadata_path.exists():
        print(f"Warning: Pass C metadata not found: {metadata_filename}")
        return None

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise PassDHayhooksError(f"Invalid JSON in metadata file: {e}")
    except IOError as e:
        raise PassDHayhooksError(f"Failed to read metadata file: {e}")


def split_text_with_overlap(
    text: str,
    min_chars: int = MIN_CHUNK_CHARS,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """
    Split text into chunks with overlap for context continuity.

    Uses character-based chunking for fine-grained semantic search.
    Overlap ensures that concepts spanning chunk boundaries are preserved.

    Args:
        text: Text to split
        min_chars: Minimum characters per chunk
        max_chars: Maximum characters per chunk
        overlap: Characters to overlap between chunks

    Returns:
        List of text chunks with overlap
    """
    # If text fits in one chunk, return as-is
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        # Calculate end position
        end = start + max_chars

        # If this would be the last chunk and it's too small, extend previous chunk
        if end >= len(text):
            chunk = text[start:]
            if len(chunk) >= min_chars or not chunks:
                chunks.append(chunk)
            else:
                # Merge with previous chunk if this one is too small
                if chunks:
                    chunks[-1] = chunks[-1] + chunk
                else:
                    chunks.append(chunk)
            break

        # Extract chunk
        chunk = text[start:end]
        chunks.append(chunk)

        # Move start position (with overlap)
        start = end - overlap

    return chunks


def extract_text_chunks(
    elements: List[Dict[str, Any]],
    min_chars: int = MIN_CHUNK_CHARS,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap: int = CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    """
    Extract text chunks from elements for embedding.
    Splits large texts using character-based chunking with overlap.

    Args:
        elements: List of element dictionaries
        min_chars: Minimum characters per chunk
        max_chars: Maximum characters per chunk
        overlap: Character overlap between chunks

    Returns:
        List of chunk dictionaries with metadata
    """
    chunks = []
    global_chunk_index = 0
    split_count = 0

    for elem_idx, element in enumerate(elements):
        text = element.get('text', '').strip()

        if not text or len(text) < 10:  # Skip very short texts
            continue

        # Split text with overlap for fine-grained semantic chunks
        text_parts = split_text_with_overlap(text, min_chars, max_chars, overlap)

        if len(text_parts) > 1:
            split_count += 1

        for part_idx, text_part in enumerate(text_parts):
            chunk = {
                'chunk_index': global_chunk_index,
                'element_id': element.get('element_id', f'elem_{elem_idx}'),
                'sub_chunk': part_idx if len(text_parts) > 1 else None,
                'text': text_part,
                'element_type': element.get('type', 'Unknown'),
                'source_part': element.get('source_part', 0),
                'metadata': {
                    'page_number': str(element.get('metadata', {}).get('page_number', '')),
                    'type': element.get('type', ''),
                    'filename': element.get('metadata', {}).get('filename', ''),
                }
            }
            chunks.append(chunk)
            global_chunk_index += 1

    if split_count > 0:
        print(f"Note: Split {split_count} large elements into sub-chunks")

    return chunks


def generate_embeddings_batch(
    client: OpenAI,
    chunks: List[Dict[str, Any]],
    batch_size: int = DEFAULT_BATCH_SIZE
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Generate embeddings for chunks using OpenAI API with batching.

    Args:
        client: OpenAI client instance
        chunks: List of chunk dictionaries
        batch_size: Number of chunks per API call

    Returns:
        Tuple of (chunks with embeddings, total tokens used)

    Raises:
        PassDHayhooksError: If embedding generation fails
    """
    total_tokens = 0
    embedded_chunks = []

    print(f"Generating embeddings for {len(chunks)} chunks (batch size: {batch_size})...")

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [chunk['text'] for chunk in batch]

        try:
            # Call OpenAI API
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
                encoding_format="float"
            )

            # Extract embeddings and attach to chunks
            for chunk, embedding_obj in zip(batch, response.data):
                chunk['embedding'] = embedding_obj.embedding
                chunk['embedding_model'] = EMBEDDING_MODEL
                embedded_chunks.append(chunk)

            # Track token usage
            total_tokens += response.usage.total_tokens

            print(f"  Batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size}: "
                  f"{len(batch)} chunks, {response.usage.total_tokens} tokens")

            # Rate limiting courtesy delay
            time.sleep(0.1)

        except Exception as e:
            raise PassDHayhooksError(f"OpenAI API error at batch {i}-{i+batch_size}: {e}")

    return embedded_chunks, total_tokens


def create_cassandra_schema(session, keyspace: str) -> None:
    """
    Create Cassandra 5 keyspace and table with native vector<float, 1536> type.

    Uses Cassandra 5 features:
    - Native vector<float, 1536> type (replaces list<float>)
    - Storage-Attached Indexing (SAI) for metadata filters
    - SAI ANN index for vector similarity search

    Args:
        session: Cassandra session
        keyspace: Keyspace name

    Raises:
        PassDHayhooksError: If schema creation fails
    """
    try:
        # Create keyspace
        session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {keyspace}
            WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
        """)

        # Use keyspace
        session.set_keyspace(keyspace)

        # Create table with native vector<float, 1536> type (Cassandra 5)
        session.execute(f"""
            CREATE TABLE IF NOT EXISTS embeddings (
                document_id text,
                element_id text,
                chunk_index int,
                text text,
                system text,
                source text,
                section text,
                tags set<text>,
                vector vector<float, 1536>,
                updated_at timestamp,
                PRIMARY KEY ((document_id), element_id, chunk_index)
            ) WITH CLUSTERING ORDER BY (element_id ASC, chunk_index ASC)
        """)

        # Create SAI indexes for metadata filters
        session.execute(f"""
            CREATE CUSTOM INDEX IF NOT EXISTS embeddings_system_idx
            ON {keyspace}.embeddings (system)
            USING 'StorageAttachedIndex'
        """)

        session.execute(f"""
            CREATE CUSTOM INDEX IF NOT EXISTS embeddings_source_idx
            ON {keyspace}.embeddings (source)
            USING 'StorageAttachedIndex'
        """)

        session.execute(f"""
            CREATE CUSTOM INDEX IF NOT EXISTS embeddings_section_idx
            ON {keyspace}.embeddings (section)
            USING 'StorageAttachedIndex'
        """)

        session.execute(f"""
            CREATE CUSTOM INDEX IF NOT EXISTS embeddings_tags_idx
            ON {keyspace}.embeddings (values(tags))
            USING 'StorageAttachedIndex'
        """)

        # Create SAI ANN index for vector similarity
        session.execute(f"""
            CREATE CUSTOM INDEX IF NOT EXISTS embeddings_vector_ann
            ON {keyspace}.embeddings (vector)
            USING 'StorageAttachedIndex'
            WITH OPTIONS = {{'similarity_function': 'cosine'}}
        """)

        ensure_manifest_table(session, keyspace)
        print(f"[ok] Cassandra 5 schema verified (keyspace: {keyspace}, vector<float, 1536> + SAI indexes)")

    except Exception as e:
        raise PassDHayhooksError(f"Failed to create Cassandra schema: {e}")


def ensure_embeddings_columns(session, keyspace: str) -> None:
    """
    Ensure embeddings table exists with Cassandra 5 vector schema.

    Note: This function is deprecated in favor of create_cassandra_schema()
    with native vector<float, 1536> type. Kept for backward compatibility.
    """
    # Cassandra 5 schema uses native vector type - no column migration needed
    # Schema is created via create_cassandra_schema() with all required columns
    pass


def store_embeddings_cassandra(
    session,
    keyspace: str,
    document_id: str,
    chunks: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Store embeddings in Cassandra 5 using native vector<float, 1536> type.

    Maps chunk data to new simplified schema with metadata filters:
    - system: Game system (from metadata extraction)
    - source: Source filename (from chunk metadata)
    - section: Element type (from chunk data)
    - tags: Derived from element_type and category

    Args:
        session: Cassandra session
        keyspace: Keyspace name
        document_id: Document identifier
        chunks: List of chunks with embeddings
        metadata: Pass C metadata (optional)

    Returns:
        Number of rows inserted

    Raises:
        PassDHayhooksError: If storage fails
    """
    ensure_embeddings_columns(session, keyspace)

    # Extract metadata fields for system filter
    game_system = None
    publisher = None
    if metadata:
        extraction_info = metadata.get('extraction', {})
        game_system = extraction_info.get('system')
        publisher = extraction_info.get('publisher')

    # Delete existing embeddings for this document (idempotent behavior)
    try:
        delete_query = SimpleStatement(
            f'DELETE FROM {keyspace}.embeddings WHERE document_id = %s',
            consistency_level=ConsistencyLevel.ONE
        )
        session.execute(delete_query, (document_id,), timeout=120)
        print(f"Cleared existing embeddings for document_id: {document_id}")
    except Exception as e:
        print(f"Warning: Failed to clear existing embeddings: {e}")

    # Prepare insert for new schema (vector<float, 1536>)
    insert_query = f"""
        INSERT INTO {keyspace}.embeddings (
            document_id, element_id, chunk_index,
            text, system, source, section, tags,
            vector, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    prepared = session.prepare(insert_query)
    rows_inserted = 0

    print(f"Storing {len(chunks)} embeddings in Cassandra 5 (vector<float, 1536>)...")
    if game_system or publisher:
        print(f"  Metadata: system={game_system}, publisher={publisher}")

    try:
        for chunk in chunks:
            # Map fields to new schema
            element_type = chunk.get('element_type', 'unknown')
            category = chunk.get('category', '')
            filename = chunk['metadata'].get('filename', '')

            # Build tags from element_type and category
            tags = set()
            if element_type:
                tags.add(element_type.lower())
            if category:
                tags.add(category.lower())
            if publisher:
                tags.add(f"publisher:{publisher.lower()}")

            session.execute(prepared, (
                document_id,
                chunk['element_id'],
                chunk['chunk_index'],
                chunk['text'],              # text (renamed from text_content)
                game_system,                # system (for metadata filtering)
                filename,                   # source (from chunk metadata)
                element_type,               # section (maps to element_type)
                tags,                       # tags (set<text>)
                chunk['embedding'],         # vector<float, 1536> (renamed from embedding)
                datetime.utcnow()           # updated_at (renamed from created_at)
            ))
            rows_inserted += 1

        print(f"✓ Stored {rows_inserted} embeddings with native vector type")
        return rows_inserted

    except Exception as e:
        raise PassDHayhooksError(f"Failed to store embeddings: {e}")


def clear_document_embeddings(
    session,
    keyspace: str,
    document_id: str,
    dry_run: bool = False
) -> int:
    """
    Clear all embeddings for a specific document_id from Cassandra.
    Enables document-specific rebuilds without affecting other documents.

    Args:
        session: Cassandra session
        keyspace: Keyspace name
        document_id: Document identifier to clear
        dry_run: If True, report count without deleting

    Returns:
        Number of rows that would be/were deleted

    Raises:
        PassDHayhooksError: If deletion fails
    """
    try:
        # Count existing rows
        count_query = f"""
            SELECT COUNT(*) as count
            FROM {keyspace}.embeddings
            WHERE document_id = %s
            ALLOW FILTERING
        """
        result = session.execute(count_query, [document_id])
        count = result.one().count if result else 0

        # Delete if not dry run and count > 0
        if not dry_run and count > 0:
            delete_query = f"""
                DELETE FROM {keyspace}.embeddings
                WHERE document_id = %s
            """
            # Note: Cassandra requires partition key for DELETE
            # We need to fetch all rows first and delete by primary key
            select_query = f"""
                SELECT document_id, element_id, chunk_index
                FROM {keyspace}.embeddings
                WHERE document_id = %s
                ALLOW FILTERING
            """
            rows = session.execute(select_query, [document_id])

            # Delete each row by primary key
            delete_stmt = session.prepare(f"""
                DELETE FROM {keyspace}.embeddings
                WHERE document_id = ? AND element_id = ? AND chunk_index = ?
            """)

            for row in rows:
                session.execute(delete_stmt, (row.document_id, row.element_id, row.chunk_index))

        return count

    except Exception as e:
        raise PassDHayhooksError(f"Failed to clear Cassandra embeddings: {e}")


def connect_cassandra(host: str, port: int) -> Tuple[Any, Any]:
    """
    Connect to Cassandra cluster.

    Args:
        host: Cassandra host
        port: Cassandra port

    Returns:
        Tuple of (cluster, session)

    Raises:
        PassDHayhooksError: If connection fails
    """
    try:
        cluster = Cluster([host], port=port)
        session = cluster.connect()
        return cluster, session
    except NoHostAvailable as e:
        raise PassDHayhooksError(
            f"Cannot connect to Cassandra at {host}:{port}\n"
            f"Ensure n8n_TTRPG_cassandra container is running\n"
            f"Error: {e}"
        )
    except Exception as e:
        raise PassDHayhooksError(f"Cassandra connection error: {e}")


def estimate_cost(total_tokens: int) -> float:
    """
    Estimate OpenAI API cost in USD.

    Args:
        total_tokens: Total tokens processed

    Returns:
        Estimated cost in USD
    """
    # text-embedding-3-small pricing: $0.020 per 1M tokens
    cost_per_million = 0.020
    return (total_tokens / 1_000_000) * cost_per_million


def create_manifest(
    output_dir: Path,
    document_id: str,
    input_manifest: Path,
    total_chunks: int,
    embedded_chunks: int,
    total_tokens: int,
    cassandra_config: Dict[str, Any],
    rows_inserted: int,
    parts_detail: List[Dict[str, Any]],
    parts_discovered: int,
    parts_processed: int,
    metadata: Optional[Dict[str, Any]] = None,
    manifest_metrics: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Create processing manifest JSON.

    Args:
        output_dir: Output directory
        document_id: Document identifier
        input_manifest: Input Pass B manifest path
        total_chunks: Total chunks extracted
        embedded_chunks: Chunks successfully embedded
        total_tokens: Total OpenAI tokens used
        cassandra_config: Cassandra configuration dict
        rows_inserted: Rows inserted to Cassandra
        parts_detail: List of per-part processing details
        parts_discovered: Number of parts discovered
        parts_processed: Number of parts successfully processed
        metadata: Pass C metadata (optional)

    Returns:
        Path to created manifest file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_filename = f"{document_id}_pass_d_manifest.json"
    manifest_path = output_dir / manifest_filename

    manifest = {
        "document_id": document_id,
        "input_manifest": str(input_manifest),
        "output_manifest": str(manifest_path),
        "processing": {
            "parts_discovered": parts_discovered,
            "parts_processed": parts_processed,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "failed_chunks": total_chunks - embedded_chunks,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimate_cost(total_tokens), 4),
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimensions": EMBEDDING_DIMENSIONS
        },
        "cassandra": {
            "host": cassandra_config['host'],
            "port": cassandra_config['port'],
            "keyspace": cassandra_config['keyspace'],
            "table": "embeddings",
            "rows_inserted": rows_inserted
        },
        "parts_detail": parts_detail,
        "timestamp": datetime.utcnow().isoformat() + 'Z'
    }

    if manifest_metrics:
        manifest["cassandra"]["vector_checksum"] = manifest_metrics.get("vector_checksum")
        manifest["cassandra"]["chunk_index_min"] = manifest_metrics.get("chunk_index_min")
        manifest["cassandra"]["chunk_index_max"] = manifest_metrics.get("chunk_index_max")
        manifest["cassandra"]["chunk_count"] = manifest_metrics.get("chunk_count")

    # Add metadata if available
    if metadata:
        extraction_info = metadata.get('extraction', {})
        manifest['metadata'] = {
            'game_system': extraction_info.get('system'),
            'publisher': extraction_info.get('publisher'),
            'extraction_date': extraction_info.get('extraction_date'),
            'statistics': metadata.get('statistics', {})
        }

    try:
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise PassDHayhooksError(f"Failed to write manifest: {e}")

    return manifest_path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Generate embeddings from Pass B manifest (Pass D)',
        add_help=False
    )

    parser.add_argument(
        'pass_b_manifest',
        nargs='?',
        type=Path,
        help='Path to Pass B manifest JSON'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path(DEFAULT_OUTPUT_DIR),
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--pass-c-dir',
        type=Path,
        default=Path(DEFAULT_PASS_C_DIR),
        help=f'Pass C output directory (default: {DEFAULT_PASS_C_DIR})'
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
        default=DEFAULT_KEYSPACE,
        help=f'Cassandra keyspace (default: {DEFAULT_KEYSPACE})'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f'Embedding batch size (default: {DEFAULT_BATCH_SIZE})'
    )
    parser.add_argument(
        '--min-chunk-chars',
        type=int,
        default=MIN_CHUNK_CHARS,
        help=f'Minimum characters per chunk (default: {MIN_CHUNK_CHARS})'
    )
    parser.add_argument(
        '--max-chunk-chars',
        type=int,
        default=MAX_CHUNK_CHARS,
        help=f'Maximum characters per chunk (default: {MAX_CHUNK_CHARS})'
    )
    parser.add_argument(
        '--chunk-overlap',
        type=int,
        default=CHUNK_OVERLAP,
        help=f'Character overlap between chunks (default: {CHUNK_OVERLAP})'
    )
    parser.add_argument(
        '--gate-marker',
        type=Path,
        help='Gate 0 marker file (v3.0.0, enables rebuild mode)'
    )
    parser.add_argument(
        '--create-schema',
        action='store_true',
        help='Create Cassandra schema if not exists'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate input without processing'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'pass_d_hayhooks v{__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    args = parser.parse_args()

    if not args.pass_b_manifest:
        parser.print_help()
        sys.exit(1)

    return args


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        # Validate OpenAI API key
        api_key = validate_openai_key()
        openai_client = OpenAI(api_key=api_key)

        # Load Pass B manifest
        print(f"Loading Pass B manifest from {args.pass_b_manifest.name}...")
        document_id, parts = load_pass_b_manifest(args.pass_b_manifest)
        print(f"✓ Loaded manifest for document: {document_id} ({len(parts)} parts)")

        # Discover Pass C files
        print(f"\nDiscovering Pass C element files in {args.pass_c_dir}...")
        discovered_files = discover_pass_c_files(document_id, parts, args.pass_c_dir)

        # Load all elements
        print(f"\nLoading elements from {len(discovered_files)} files...")
        all_elements, processing_info = load_elements_from_files(discovered_files)
        print(f"✓ Loaded {len(all_elements)} total elements")

        # Load Pass C metadata
        print(f"\nLoading Pass C metadata...")
        pass_c_metadata = load_pass_c_metadata(document_id, args.pass_c_dir)
        if pass_c_metadata:
            system = pass_c_metadata.get('extraction', {}).get('system', 'Unknown')
            publisher = pass_c_metadata.get('extraction', {}).get('publisher', 'Unknown')
            print(f"✓ Loaded metadata: system={system}, publisher={publisher}")
        else:
            print("  No metadata found (will store embeddings without system/publisher)")

        # Extract text chunks with configured chunk sizes
        chunks = extract_text_chunks(
            all_elements,
            args.min_chunk_chars,
            args.max_chunk_chars,
            args.chunk_overlap
        )
        print(f"✓ Extracted {len(chunks)} text chunks (min={args.min_chunk_chars}, max={args.max_chunk_chars}, overlap={args.chunk_overlap})")

        if args.dry_run:
            print("\n--dry-run mode: Validation complete, no processing performed")
            print(f"  Parts discovered: {len(discovered_files)}")
            print(f"  Total chunks: {len(chunks)}")
            return 0

        # Connect to Cassandra
        print(f"\nConnecting to Cassandra at {args.host}:{args.port}...")
        cluster, session = connect_cassandra(args.host, args.port)

        # Create schema if requested
        if args.create_schema:
            create_cassandra_schema(session, args.keyspace)

        # Ensure manifest table exists even if schema already provisioned
        try:
            ensure_manifest_table(session, args.keyspace)
        except Exception as exc:
            raise PassDHayhooksError(f"Failed to verify embedding manifest table: {exc}")

        # v3.0.0: Load Gate 0 marker for rebuild control
        rebuild_mode = False
        rebuild_scope = {}
        deletion_count = 0
        if args.gate_marker and args.gate_marker.exists():
            try:
                with open(args.gate_marker, 'r', encoding='utf-8') as f:
                    gate_marker = json.load(f)
                    rebuild_mode = gate_marker.get('rebuild_mode', False)
                    rebuild_scope = gate_marker.get('rebuild_scope', {})
            except (IOError, json.JSONDecodeError) as e:
                raise PassDHayhooksError(f"Failed to load Gate 0 marker: {e}")

            # Document-specific cleanup if rebuild enabled for Cassandra
            if rebuild_mode and rebuild_scope.get('cassandra', False):
                print(f"\n⚠️  Rebuild mode enabled for Cassandra")
                deletion_count = clear_document_embeddings(session, args.keyspace, document_id, dry_run=False)
                if deletion_count > 0:
                    print(f"✓ Cleared {deletion_count} existing embeddings for document_id: {document_id}\n")

        # Generate embeddings
        print(f"\nGenerating embeddings using {EMBEDDING_MODEL}...")
        embedded_chunks, total_tokens = generate_embeddings_batch(
            openai_client,
            chunks,
            args.batch_size
        )
        print(f"✓ Generated {len(embedded_chunks)} embeddings ({total_tokens:,} tokens)")

        manifest_metrics = compute_chunk_metrics(embedded_chunks)

        # Store in Cassandra with metadata
        print(f"\nStoring embeddings in {args.keyspace}.embeddings...")
        rows_inserted = store_embeddings_cassandra(
            session,
            args.keyspace,
            document_id,
            embedded_chunks,
            pass_c_metadata
        )

        if manifest_metrics["chunk_count"] != rows_inserted:
            print(
                f"  Warning: manifest chunk count ({manifest_metrics['chunk_count']}) "
                f"differs from rows inserted ({rows_inserted})"
            )

        upsert_manifest(
            session,
            args.keyspace,
            ManifestRecord(
                document_id=document_id,
                chunk_count=manifest_metrics["chunk_count"],
                vector_checksum=manifest_metrics["vector_checksum"],
                chunk_index_min=manifest_metrics["chunk_index_min"],
                chunk_index_max=manifest_metrics["chunk_index_max"],
                embedding_model=EMBEDDING_MODEL,
                vector_dim=EMBEDDING_DIMENSIONS,
                updated_at=datetime.utcnow(),
                updated_by="pass_d",
            ),
        )

        # Create manifest with metadata
        print("\nCreating manifest...")
        manifest_path = create_manifest(
            args.output,
            document_id,
            args.pass_b_manifest,
            len(chunks),
            len(embedded_chunks),
            total_tokens,
            {
                'host': args.host,
                'port': args.port,
                'keyspace': args.keyspace
            },
            rows_inserted,
            processing_info['parts_detail'],
            len(parts),
            len(discovered_files),
            pass_c_metadata,
            manifest_metrics
        )

        # Cleanup
        cluster.shutdown()

        # Success summary
        print(
            f"\n✓ Pass D processing complete\n"
            f"  Document: {document_id}\n"
            f"  Parts: {len(discovered_files)}/{len(parts)}\n"
            f"  Chunks: {len(embedded_chunks)}\n"
            f"  Tokens: {total_tokens:,}\n"
            f"  Cost: ${estimate_cost(total_tokens):.4f}\n"
            f"  Manifest: {manifest_path.name}"
        )

        return 0

    except PassDHayhooksError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
