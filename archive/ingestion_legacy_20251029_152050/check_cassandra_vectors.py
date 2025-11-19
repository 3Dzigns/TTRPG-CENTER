#!/usr/bin/env python3
"""
check_cassandra_vectors.py - Validate Cassandra Vector Embeddings and Checksums
"""

import sys
import hashlib
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement

def compute_vector_checksum(embeddings_list):
    """Compute checksum from list of embedding vectors."""
    hasher = hashlib.sha256()
    for emb in embeddings_list:
        # Convert each float to bytes and hash
        for val in emb:
            hasher.update(str(val).encode('utf-8'))
    return hasher.hexdigest()[:16]

def main():
    print("=== Cassandra Vector Validation ===\n")

    # Connect to Cassandra
    print("Connecting to Cassandra...")
    try:
        cluster = Cluster(['n8n_TTRPG_cassandra'], port=9042)
        session = cluster.connect('ttrpg_vectors')
        print("✓ Connected to ttrpg_vectors keyspace\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return 1

    # Get token ranges to partition the query
    print("Fetching token ranges...")
    try:
        token_query = "SELECT DISTINCT token(document_id) as token FROM embeddings LIMIT 1000;"
        rows = session.execute(token_query, timeout=30)
        tokens = [row.token for row in rows]
        print(f"✓ Found {len(tokens)} token samples\n")
    except Exception as e:
        print(f"Token query failed: {e}")
        print("Trying alternative approach...\n")
        tokens = []

    # Try to get a sample of embeddings by limiting results
    print("Fetching embedding samples (limited query)...")
    try:
        # Use ALLOW FILTERING with small limit for sampling
        sample_query = """
            SELECT document_id, element_id, chunk_index,
                   embedding, element_type, game_system, publisher
            FROM embeddings
            LIMIT 10
            ALLOW FILTERING;
        """

        rows = list(session.execute(SimpleStatement(sample_query, fetch_size=10), timeout=30))

        if not rows:
            print("⚠️  No embeddings found in table")
            return 0

        print(f"✓ Retrieved {len(rows)} embedding samples\n")

        # Analyze samples
        print("=== Sample Analysis ===")
        for i, row in enumerate(rows[:3], 1):
            print(f"\nSample {i}:")
            print(f"  Document ID: {row.document_id}")
            print(f"  Element ID: {row.element_id}")
            print(f"  Chunk Index: {row.chunk_index}")
            print(f"  Element Type: {row.element_type}")
            print(f"  Game System: {row.game_system}")
            print(f"  Publisher: {row.publisher}")
            if row.embedding:
                print(f"  Embedding Dimensions: {len(row.embedding)}")
                print(f"  Embedding Sample (first 5): {row.embedding[:5]}")
                print(f"  Embedding Range: [{min(row.embedding):.4f}, {max(row.embedding):.4f}]")
            else:
                print("  ⚠️  Embedding is NULL!")

        # Compute checksum for samples
        print("\n=== Checksum Validation ===")
        embeddings_list = [row.embedding for row in rows if row.embedding]
        if embeddings_list:
            checksum = compute_vector_checksum(embeddings_list)
            print(f"Sample Checksum (10 vectors): {checksum}")
            print(f"Total vectors in sample: {len(embeddings_list)}")

            # Validate dimensions
            dims = [len(emb) for emb in embeddings_list]
            if len(set(dims)) == 1:
                print(f"✓ All embeddings have consistent dimensions: {dims[0]}")
            else:
                print(f"⚠️  Inconsistent dimensions found: {set(dims)}")

        # Try to count documents
        print("\n=== Document Statistics ===")
        try:
            doc_query = "SELECT DISTINCT document_id FROM embeddings LIMIT 100 ALLOW FILTERING;"
            doc_rows = list(session.execute(SimpleStatement(doc_query, fetch_size=100), timeout=30))
            doc_ids = [row.document_id for row in doc_rows if row.document_id]
            print(f"Documents found (sample): {len(doc_ids)}")
            if doc_ids:
                print(f"Sample document IDs:")
                for doc_id in doc_ids[:5]:
                    print(f"  - {doc_id}")
        except Exception as e:
            print(f"Could not retrieve document list: {e}")

        print("\n✓ Vector validation complete")

    except Exception as e:
        print(f"✗ Sample query failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        cluster.shutdown()

    return 0

if __name__ == '__main__':
    sys.exit(main())
