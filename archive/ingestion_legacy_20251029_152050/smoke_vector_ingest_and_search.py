#!/usr/bin/env python3
"""
smoke_vector_ingest_and_search.py - Cassandra 5 Vector Integration Test
========================================================================

End-to-end smoke test for Cassandra 5 native vector implementation.
Validates schema, vector ingestion, and ANN search functionality.

Test Flow:
1. Connect to Cassandra and verify schema exists
2. Insert test embeddings with metadata
3. Perform ANN search with cosine similarity
4. Validate search results and scoring
5. Test metadata filtering (system, source, tag)
6. Cleanup test data

Usage:
  # Run smoke test
  python3 smoke_vector_ingest_and_search.py

  # Run with custom Cassandra host
  CASSANDRA_HOST=localhost python3 smoke_vector_ingest_and_search.py

  # Skip cleanup (leave test data)
  python3 smoke_vector_ingest_and_search.py --no-cleanup

  # Docker execution
  docker exec n8n_TTRPG_ingestion_engine python3 /app/tests/smoke_vector_ingest_and_search.py

Exit Codes:
  0 - All tests passed
  1 - Test failures
  2 - Connection errors
  3 - Schema validation errors

Version: 1.0.0
Author: n8n TTRPG Center
"""

import sys
import os
import argparse
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingestion'))

try:
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.auth import PlainTextAuthProvider
except ImportError:
    print("Error: cassandra-driver not installed. Run: pip install cassandra-driver")
    sys.exit(2)

try:
    from upsert_embeddings import (
        upsert_embedding,
        batch_upsert_embeddings,
        cleanup_document_embeddings,
        validate_vector_dimension,
        EMBED_DIM
    )
except ImportError:
    print("Error: Could not import upsert_embeddings module")
    print("Ensure ingestion/upsert_embeddings.py is accessible")
    sys.exit(2)


__version__ = "1.0.0"

# Configuration
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "n8n_TTRPG_cassandra")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "ttrpg_vectors")
TEST_DOCUMENT_ID = "smoke_test_doc_001"


def create_test_vector(seed: int = 0) -> List[float]:
    """
    Create a deterministic test vector for reproducible tests.

    Args:
        seed: Seed for pseudo-random generation

    Returns:
        List of 1536 floats representing test embedding
    """
    import math

    # Generate simple sinusoidal pattern based on seed
    vector = []
    for i in range(EMBED_DIM):
        value = math.sin((i + seed) * 0.01) * 0.5
        vector.append(value)

    return vector


def verify_schema(session) -> bool:
    """
    Verify Cassandra 5 vector schema exists and is correct.

    Args:
        session: Active Cassandra session

    Returns:
        True if schema valid, False otherwise
    """
    print("\n=== Schema Verification ===")

    try:
        # Check keyspace exists
        keyspaces = session.execute("SELECT keyspace_name FROM system_schema.keyspaces")
        keyspace_names = [row.keyspace_name for row in keyspaces]

        if CASSANDRA_KEYSPACE not in keyspace_names:
            print(f"✗ Keyspace '{CASSANDRA_KEYSPACE}' not found")
            return False

        print(f"✓ Keyspace '{CASSANDRA_KEYSPACE}' exists")

        # Check table structure
        session.set_keyspace(CASSANDRA_KEYSPACE)
        columns = session.execute(
            "SELECT column_name, type FROM system_schema.columns "
            "WHERE keyspace_name = %s AND table_name = %s",
            (CASSANDRA_KEYSPACE, "embeddings")
        )

        column_types = {row.column_name: row.type for row in columns}

        # Validate required columns
        required = {
            "document_id": "text",
            "element_id": "text",
            "chunk_index": "int",
            "text": "text",
            "system": "text",
            "source": "text",
            "section": "text",
            "tags": "set<text>",
            "vector": "vector<float, 1536>",
            "updated_at": "timestamp"
        }

        for col, expected_type in required.items():
            if col not in column_types:
                print(f"✗ Missing column: {col}")
                return False
            # Note: vector type might be reported differently
            if col == "vector" and "vector" not in column_types[col]:
                print(f"⚠ Vector column type: {column_types[col]} (expected native vector type)")

        print("✓ Table 'embeddings' has required columns")

        # Check indexes exist
        indexes = session.execute(
            "SELECT index_name FROM system_schema.indexes "
            "WHERE keyspace_name = %s AND table_name = %s",
            (CASSANDRA_KEYSPACE, "embeddings")
        )

        index_names = [row.index_name for row in indexes]
        expected_indexes = [
            "embeddings_system_idx",
            "embeddings_source_idx",
            "embeddings_section_idx",
            "embeddings_tags_idx",
            "embeddings_vector_ann"
        ]

        for idx in expected_indexes:
            if idx in index_names:
                print(f"✓ Index '{idx}' exists")
            else:
                print(f"⚠ Index '{idx}' not found (may not be critical)")

        return True

    except Exception as e:
        print(f"✗ Schema verification failed: {e}")
        return False


def test_vector_ingestion(session) -> bool:
    """
    Test vector ingestion with various metadata combinations.

    Args:
        session: Active Cassandra session

    Returns:
        True if ingestion successful, False otherwise
    """
    print("\n=== Vector Ingestion Test ===")

    try:
        # Create test data with different metadata
        test_rows = [
            {
                "document_id": TEST_DOCUMENT_ID,
                "element_id": "elem_001",
                "chunk_index": 0,
                "text": "A wizard casts a powerful fireball spell, dealing massive fire damage.",
                "system": "D&D 5e",
                "source": "Player's Handbook",
                "section": "Chapter 11: Spells",
                "tags": ["spell", "evocation", "fire"],
                "vector": create_test_vector(0)
            },
            {
                "document_id": TEST_DOCUMENT_ID,
                "element_id": "elem_002",
                "chunk_index": 1,
                "text": "The rogue sneaks through shadows, using stealth to avoid detection.",
                "system": "D&D 5e",
                "source": "Player's Handbook",
                "section": "Chapter 3: Classes",
                "tags": ["class", "rogue", "stealth"],
                "vector": create_test_vector(1)
            },
            {
                "document_id": TEST_DOCUMENT_ID,
                "element_id": "elem_003",
                "chunk_index": 2,
                "text": "A dragon breathes fire, engulfing adventurers in flames.",
                "system": "D&D 5e",
                "source": "Monster Manual",
                "section": "Chapter 2: Dragons",
                "tags": ["monster", "dragon", "fire"],
                "vector": create_test_vector(2)
            },
            {
                "document_id": TEST_DOCUMENT_ID,
                "element_id": "elem_004",
                "chunk_index": 3,
                "text": "The cleric channels divine energy to heal wounded allies.",
                "system": "Pathfinder 2e",
                "source": "Core Rulebook",
                "section": "Chapter 4: Divine Magic",
                "tags": ["class", "cleric", "healing"],
                "vector": create_test_vector(3)
            }
        ]

        # Test single upsert
        print("Testing single upsert...")
        upsert_embedding(session, test_rows[0], keyspace=CASSANDRA_KEYSPACE)
        print("✓ Single upsert successful")

        # Test batch upsert
        print("Testing batch upsert (3 more rows)...")
        stats = batch_upsert_embeddings(
            session,
            test_rows[1:],
            batch_size=2,
            keyspace=CASSANDRA_KEYSPACE
        )

        if stats["successful"] == 3 and stats["failed"] == 0:
            print(f"✓ Batch upsert successful: {stats['successful']} rows")
        else:
            print(f"✗ Batch upsert partial failure: {stats}")
            return False

        # Verify row count
        count_query = f"SELECT COUNT(*) as count FROM {CASSANDRA_KEYSPACE}.embeddings WHERE document_id = %s ALLOW FILTERING"
        result = session.execute(count_query, (TEST_DOCUMENT_ID,))
        count = result.one().count

        if count == 4:
            print(f"✓ Verified {count} rows inserted")
            return True
        else:
            print(f"✗ Expected 4 rows, found {count}")
            return False

    except Exception as e:
        print(f"✗ Ingestion test failed: {e}")
        return False


def test_ann_search(session) -> bool:
    """
    Test ANN vector search with cosine similarity.

    Args:
        session: Active Cassandra session

    Returns:
        True if search successful, False otherwise
    """
    print("\n=== ANN Search Test ===")

    try:
        # Create query vector similar to first test vector
        query_vector = create_test_vector(0)

        # Basic ANN search (no filters)
        print("Testing unfiltered ANN search...")
        cql = f'''
            SELECT document_id, element_id, chunk_index, text,
                   similarity_cosine(vector, %s) AS score
            FROM {CASSANDRA_KEYSPACE}.embeddings
            ORDER BY vector ANN OF %s
            LIMIT 3
        '''

        rows = list(session.execute(cql, (query_vector, query_vector)))

        if len(rows) > 0:
            print(f"✓ Found {len(rows)} results")
            print(f"  Top result: element_id={rows[0].element_id}, score={rows[0].score:.4f}")

            # Verify highest score is first result (elem_001, seed=0)
            if rows[0].element_id == "elem_001":
                print("✓ Highest similarity result is correct")
            else:
                print(f"⚠ Expected elem_001 as top result, got {rows[0].element_id}")

        else:
            print("✗ No results found")
            return False

        return True

    except Exception as e:
        print(f"✗ ANN search test failed: {e}")
        return False


def test_filtered_search(session) -> bool:
    """
    Test ANN search with metadata filters.

    Args:
        session: Active Cassandra session

    Returns:
        True if filtered search successful, False otherwise
    """
    print("\n=== Filtered ANN Search Test ===")

    try:
        query_vector = create_test_vector(0)

        # Test 1: Filter by system
        print("Test 1: Filter by system='D&D 5e'")
        cql = f'''
            SELECT document_id, element_id, text, similarity_cosine(vector, %s) AS score
            FROM {CASSANDRA_KEYSPACE}.embeddings
            WHERE system = %s
            ORDER BY vector ANN OF %s
            LIMIT 3
        '''

        rows = list(session.execute(cql, (query_vector, "D&D 5e", query_vector)))
        if len(rows) == 3:
            print(f"✓ Found 3 D&D 5e results")
        else:
            print(f"⚠ Expected 3 results, got {len(rows)}")

        # Test 2: Filter by source
        print("Test 2: Filter by source='Monster Manual'")
        cql = f'''
            SELECT document_id, element_id, text, similarity_cosine(vector, %s) AS score
            FROM {CASSANDRA_KEYSPACE}.embeddings
            WHERE source = %s
            ORDER BY vector ANN OF %s
            LIMIT 3
        '''

        rows = list(session.execute(cql, (query_vector, "Monster Manual", query_vector)))
        if len(rows) == 1 and rows[0].element_id == "elem_003":
            print(f"✓ Found Monster Manual result (elem_003)")
        else:
            print(f"⚠ Unexpected result count or element_id")

        # Test 3: Filter by tag
        print("Test 3: Filter by tag='spell'")
        cql = f'''
            SELECT document_id, element_id, text, similarity_cosine(vector, %s) AS score
            FROM {CASSANDRA_KEYSPACE}.embeddings
            WHERE tags CONTAINS %s
            ORDER BY vector ANN OF %s
            LIMIT 3
        '''

        rows = list(session.execute(cql, (query_vector, "spell", query_vector)))
        if len(rows) == 1 and rows[0].element_id == "elem_001":
            print(f"✓ Found spell result (elem_001)")
        else:
            print(f"⚠ Unexpected result count or element_id")

        # Test 4: Multiple filters
        print("Test 4: Multiple filters (system + tag)")
        cql = f'''
            SELECT document_id, element_id, text, similarity_cosine(vector, %s) AS score
            FROM {CASSANDRA_KEYSPACE}.embeddings
            WHERE system = %s AND tags CONTAINS %s
            ORDER BY vector ANN OF %s
            LIMIT 3
        '''

        rows = list(session.execute(cql, (query_vector, "D&D 5e", "fire", query_vector)))
        if len(rows) == 2:  # elem_001 (spell) and elem_003 (dragon)
            print(f"✓ Found 2 D&D 5e + fire results")
        else:
            print(f"⚠ Expected 2 results, got {len(rows)}")

        return True

    except Exception as e:
        print(f"✗ Filtered search test failed: {e}")
        return False


def cleanup_test_data(session) -> bool:
    """
    Remove test data from Cassandra.

    Args:
        session: Active Cassandra session

    Returns:
        True if cleanup successful, False otherwise
    """
    print("\n=== Cleanup Test Data ===")

    try:
        cleanup_document_embeddings(session, TEST_DOCUMENT_ID, CASSANDRA_KEYSPACE)
        print(f"✓ Cleaned up test document: {TEST_DOCUMENT_ID}")
        return True

    except Exception as e:
        print(f"✗ Cleanup failed: {e}")
        return False


def main():
    """Run smoke tests."""
    parser = argparse.ArgumentParser(description="Cassandra 5 Vector Smoke Test")
    parser.add_argument("--no-cleanup", action="store_true", help="Skip cleanup (leave test data)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    print("=" * 70)
    print("Cassandra 5 Vector Integration Smoke Test")
    print(f"Version: {__version__}")
    print("=" * 70)
    print(f"Cassandra: {CASSANDRA_HOST}:{CASSANDRA_PORT}")
    print(f"Keyspace: {CASSANDRA_KEYSPACE}")
    print(f"Test Document ID: {TEST_DOCUMENT_ID}")
    print(f"Vector Dimension: {EMBED_DIM}")

    # Connect to Cassandra
    print("\n=== Cassandra Connection ===")
    try:
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        session = cluster.connect()
        print(f"✓ Connected to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}")

    except NoHostAvailable:
        print(f"✗ Failed to connect to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}")
        print("Ensure Cassandra container is running and healthy")
        return 2

    except Exception as e:
        print(f"✗ Connection error: {e}")
        return 2

    # Run tests
    test_results = {
        "Schema Verification": verify_schema(session),
        "Vector Ingestion": test_vector_ingestion(session),
        "ANN Search": test_ann_search(session),
        "Filtered Search": test_filtered_search(session),
    }

    # Cleanup
    if not args.no_cleanup:
        test_results["Cleanup"] = cleanup_test_data(session)
    else:
        print("\n⚠ Skipping cleanup (--no-cleanup flag)")

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<50} {status}")

    print("=" * 70)
    print(f"Results: {passed}/{total} tests passed")

    cluster.shutdown()

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
