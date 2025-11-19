#!/usr/bin/env python3
"""
upsert_embeddings.py - Cassandra 5 Vector Embedding Upsert Module
==================================================================

Standalone module for upserting vector embeddings into Cassandra 5 with native
vector<float, 1536> type. Provides dimension validation and efficient batch operations.

Features:
- Vector dimension validation (1536 for text-embedding-3-small)
- Prepared statement pattern for performance
- Metadata filter support (system, source, section, tags)
- Type-safe upsert with automatic timestamp
- Batch operation support for Pass D integration

Usage:
  from upsert_embeddings import upsert_embedding, batch_upsert_embeddings

  # Single upsert
  upsert_embedding(session, {
      "document_id": "doc123",
      "element_id": "elem456",
      "chunk_index": 0,
      "text": "The wizard casts fireball...",
      "system": "D&D 5e",
      "source": "Player's Handbook",
      "section": "Chapter 11: Spells",
      "tags": ["spell", "evocation", "fire"],
      "vector": [0.123, -0.456, ...],  # 1536 floats
  })

  # Batch upsert
  batch_upsert_embeddings(session, rows, batch_size=100)

Version: 1.0.0
Author: n8n TTRPG Center
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from cassandra.cluster import Session
from cassandra.query import PreparedStatement


__version__ = "1.0.0"

# Expected embedding dimension for OpenAI text-embedding-3-small
EMBED_DIM = 1536


class EmbeddingUpsertError(Exception):
    """Exception raised for embedding upsert errors."""
    pass


def validate_vector_dimension(vector: List[float], expected_dim: int = EMBED_DIM) -> None:
    """
    Validate vector dimension matches expected embedding dimension.

    Args:
        vector: List of floats representing embedding vector
        expected_dim: Expected dimension (default: 1536)

    Raises:
        EmbeddingUpsertError: If dimension mismatch or invalid vector type
    """
    if not isinstance(vector, (list, tuple)):
        raise EmbeddingUpsertError(
            f"Vector must be list or tuple, got {type(vector).__name__}"
        )

    if len(vector) != expected_dim:
        raise EmbeddingUpsertError(
            f"Vector dimension mismatch: expected {expected_dim}, got {len(vector)}"
        )

    # Validate all elements are numeric
    try:
        _ = [float(v) for v in vector]
    except (TypeError, ValueError) as e:
        raise EmbeddingUpsertError(f"Vector contains non-numeric values: {e}")


def prepare_upsert_statement(session: Session, keyspace: str = "ttrpg_vectors") -> PreparedStatement:
    """
    Prepare INSERT statement for embedding upsert.

    Prepared statements provide:
    - Query plan caching for performance
    - Type safety and parameter validation
    - Protection against CQL injection

    Args:
        session: Active Cassandra session
        keyspace: Target keyspace (default: ttrpg_vectors)

    Returns:
        Prepared statement for embedding upsert

    Raises:
        EmbeddingUpsertError: If statement preparation fails
    """
    try:
        session.set_keyspace(keyspace)

        stmt = session.prepare('''
            INSERT INTO embeddings (
                document_id, element_id, chunk_index,
                text, system, source, section, tags,
                vector, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''')

        return stmt

    except Exception as e:
        raise EmbeddingUpsertError(f"Failed to prepare upsert statement: {e}")


def upsert_embedding(
    session: Session,
    row: Dict[str, Any],
    prepared_stmt: Optional[PreparedStatement] = None,
    keyspace: str = "ttrpg_vectors"
) -> None:
    """
    Upsert a single embedding row into Cassandra.

    Args:
        session: Active Cassandra session
        row: Dictionary containing embedding data with keys:
            - document_id (str): Document identifier
            - element_id (str): Element identifier
            - chunk_index (int): Chunk sequence number
            - text (str): Raw text content
            - system (str, optional): Game system
            - source (str, optional): Source book/module
            - section (str, optional): Document section
            - tags (list[str], optional): Metadata tags
            - vector (list[float]): Embedding vector (1536 dims)
        prepared_stmt: Pre-prepared statement (optional, created if None)
        keyspace: Target keyspace (default: ttrpg_vectors)

    Raises:
        EmbeddingUpsertError: If validation fails or upsert errors
    """
    # Validate required fields
    required_fields = ["document_id", "element_id", "chunk_index", "text", "vector"]
    missing = [f for f in required_fields if f not in row]
    if missing:
        raise EmbeddingUpsertError(f"Missing required fields: {missing}")

    # Validate vector dimension
    vector = row["vector"]
    validate_vector_dimension(vector)

    # Prepare statement if not provided
    if prepared_stmt is None:
        prepared_stmt = prepare_upsert_statement(session, keyspace)

    # Convert tags list to set (Cassandra set<text> type)
    tags = row.get("tags", [])
    if isinstance(tags, list):
        tags = set(tags)
    elif not isinstance(tags, set):
        tags = set()

    # Execute upsert with current timestamp
    try:
        session.execute(prepared_stmt, (
            row["document_id"],
            row["element_id"],
            row["chunk_index"],
            row["text"],
            row.get("system"),
            row.get("source"),
            row.get("section"),
            tags,
            vector,
            datetime.utcnow()
        ))

    except Exception as e:
        raise EmbeddingUpsertError(
            f"Failed to upsert embedding for {row['document_id']}/{row['element_id']}: {e}"
        )


def batch_upsert_embeddings(
    session: Session,
    rows: List[Dict[str, Any]],
    batch_size: int = 100,
    keyspace: str = "ttrpg_vectors"
) -> Dict[str, Any]:
    """
    Batch upsert multiple embeddings with progress tracking.

    Uses a single prepared statement for all upserts for optimal performance.
    Processes in batches to manage memory and provide progress feedback.

    Args:
        session: Active Cassandra session
        rows: List of embedding row dictionaries
        batch_size: Number of rows per batch (default: 100)
        keyspace: Target keyspace (default: ttrpg_vectors)

    Returns:
        Dictionary with statistics:
            - total_rows: Total rows processed
            - successful: Number of successful upserts
            - failed: Number of failed upserts
            - errors: List of error messages

    Raises:
        EmbeddingUpsertError: If preparation fails (individual upserts continue on error)
    """
    stats = {
        "total_rows": len(rows),
        "successful": 0,
        "failed": 0,
        "errors": []
    }

    if not rows:
        return stats

    # Prepare statement once for all upserts
    try:
        prepared_stmt = prepare_upsert_statement(session, keyspace)
    except EmbeddingUpsertError as e:
        stats["errors"].append(str(e))
        stats["failed"] = len(rows)
        return stats

    # Process in batches
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]

        for row in batch:
            try:
                upsert_embedding(session, row, prepared_stmt, keyspace)
                stats["successful"] += 1

            except EmbeddingUpsertError as e:
                stats["failed"] += 1
                error_msg = f"Row {stats['successful'] + stats['failed']}: {e}"
                stats["errors"].append(error_msg)

    return stats


def cleanup_document_embeddings(
    session: Session,
    document_id: str,
    keyspace: str = "ttrpg_vectors"
) -> int:
    """
    Delete all embeddings for a specific document.

    Useful for document-specific rebuild operations (Gate 0 rebuild mode).

    Args:
        session: Active Cassandra session
        document_id: Document identifier to delete
        keyspace: Target keyspace (default: ttrpg_vectors)

    Returns:
        Number of partitions deleted (1 if successful, 0 otherwise)

    Raises:
        EmbeddingUpsertError: If deletion fails
    """
    try:
        session.set_keyspace(keyspace)

        stmt = session.prepare('DELETE FROM embeddings WHERE document_id = ?')
        session.execute(stmt, (document_id,))

        return 1  # Cassandra doesn't return row count for DELETEs

    except Exception as e:
        raise EmbeddingUpsertError(
            f"Failed to cleanup embeddings for document {document_id}: {e}"
        )


# Example usage (for testing and documentation)
if __name__ == "__main__":
    import sys
    from cassandra.cluster import Cluster

    print("Cassandra 5 Vector Embedding Upsert Module")
    print(f"Version: {__version__}\n")

    # Example: Connect and test single upsert
    try:
        cluster = Cluster(['n8n_TTRPG_cassandra'], port=9042)
        session = cluster.connect()

        # Create test embedding
        test_row = {
            "document_id": "test_doc_001",
            "element_id": "elem_001",
            "chunk_index": 0,
            "text": "The wizard casts a powerful fireball spell.",
            "system": "D&D 5e",
            "source": "Player's Handbook",
            "section": "Chapter 11: Spells",
            "tags": ["spell", "evocation", "fire"],
            "vector": [0.0] * EMBED_DIM  # Dummy vector for testing
        }

        print("Testing single upsert...")
        upsert_embedding(session, test_row)
        print("✓ Single upsert successful\n")

        # Test batch upsert
        print("Testing batch upsert (3 rows)...")
        test_rows = [
            {**test_row, "element_id": f"elem_{i:03d}", "chunk_index": i}
            for i in range(3)
        ]
        stats = batch_upsert_embeddings(session, test_rows)
        print(f"✓ Batch upsert complete: {stats['successful']} successful, {stats['failed']} failed\n")

        # Test cleanup
        print("Testing cleanup...")
        cleanup_document_embeddings(session, "test_doc_001")
        print("✓ Cleanup successful\n")

        cluster.shutdown()
        sys.exit(0)

    except Exception as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)
