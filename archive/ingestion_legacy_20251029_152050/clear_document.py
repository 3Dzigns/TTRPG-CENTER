#!/usr/bin/env python3
"""
clear_document.py - Document-Specific Database Cleanup
======================================================

Deletes all database entries for a specific document_id across all databases
(MongoDB, Cassandra, Neo4j). Only affects the specified document_id.

Usage:
  clear_document.py <document_id> [options]
  clear_document.py -v | --version
  clear_document.py -? | --help

Arguments:
  document_id          Document ID to delete (required)

Options:
  --force              Skip confirmation prompts
  --dry-run            Preview deletions without executing
  --targets TARGET [TARGET ...]
                       Limit cleanup to one or more stores (mongodb, cassandra, neo4j)
  -v, --version        Show version
  -?, --help           Show help

Examples:
  # Delete with confirmation prompt
  clear_document.py cyberpunk_v3_cp4110_core_rulebook_4f81185e7057

  # Delete without confirmation
  clear_document.py cyberpunk_v3_cp4110_core_rulebook_4f81185e7057 --force

  # Preview deletions without executing
  clear_document.py cyberpunk_v3_cp4110_core_rulebook_4f81185e7057 --dry-run

Exit Codes:
  0 - Deletion successful or dry-run completed
  1 - User cancelled operation
  2 - Connection error
  3 - Invalid input

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import sys
from typing import Dict, Any, Optional
from pymongo import MongoClient, errors as mongo_errors
from cassandra.cluster import Cluster, NoHostAvailable
from cassandra.auth import PlainTextAuthProvider
from neo4j import GraphDatabase, exceptions as neo4j_errors


__version__ = "1.0.0"

# Default connection settings
MONGO_HOST = "n8n_TTRPG_mongodb"
MONGO_PORT = 27017
MONGO_DB = "ttrpg_ingestion"

CASSANDRA_HOST = "n8n_TTRPG_cassandra"
CASSANDRA_PORT = 9042
CASSANDRA_KEYSPACE = "ttrpg_vectors"
CASSANDRA_TABLE = "embeddings"

NEO4J_URI = "bolt://n8n_TTRPG_neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "vRaG3iV3A-KHb5jdvBi&P702APe29V%"


class ClearDocumentError(Exception):
    """Base exception for clear_document errors."""
    pass


class ConnectionManager:
    """Manages connections to all databases."""

    def __init__(self):
        self.mongo_client: Optional[MongoClient] = None
        self.cassandra_session = None
        self.cassandra_cluster = None
        self.neo4j_driver = None

    def connect_mongodb(self) -> bool:
        """Connect to MongoDB."""
        try:
            self.mongo_client = MongoClient(
                host=MONGO_HOST,
                port=MONGO_PORT,
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            self.mongo_client.admin.command('ping')
            return True
        except mongo_errors.ConnectionFailure as e:
            print(f"MongoDB connection failed: {e}", file=sys.stderr)
            return False

    def connect_cassandra(self) -> bool:
        """Connect to Cassandra."""
        try:
            self.cassandra_cluster = Cluster(
                contact_points=[CASSANDRA_HOST],
                port=CASSANDRA_PORT,
                connect_timeout=10
            )
            self.cassandra_session = self.cassandra_cluster.connect()
            self.cassandra_session.set_keyspace(CASSANDRA_KEYSPACE)
            return True
        except NoHostAvailable as e:
            print(f"Cassandra connection failed: {e}", file=sys.stderr)
            return False

    def connect_neo4j(self) -> bool:
        """Connect to Neo4j."""
        try:
            self.neo4j_driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            # Test connection
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            return True
        except neo4j_errors.ServiceUnavailable as e:
            print(f"Neo4j connection failed: {e}", file=sys.stderr)
            return False

    def close_all(self):
        """Close all database connections."""
        if self.mongo_client:
            self.mongo_client.close()
        if self.cassandra_cluster:
            self.cassandra_cluster.shutdown()
        if self.neo4j_driver:
            self.neo4j_driver.close()


def count_mongodb_documents(client: MongoClient, document_id: str) -> Dict[str, int]:
    """Count documents in MongoDB collections for document_id."""
    db = client[MONGO_DB]

    counts = {
        "elements": 0,
        "categories": 0,
        "terms": 0,
        "documents": 0
    }

    try:
        counts["elements"] = db.elements.count_documents({"document_id": document_id})
        counts["categories"] = db.categories.count_documents({"document_id": document_id})
        counts["terms"] = db.terms.count_documents({"document_id": document_id})
        counts["documents"] = db.documents.count_documents({"document_id": document_id})
    except mongo_errors.PyMongoError as e:
        raise ClearDocumentError(f"MongoDB count failed: {e}")

    return counts


def count_cassandra_chunks(session, document_id: str) -> int:
    """Count chunks in Cassandra for document_id with retry logic."""
    from cassandra.query import SimpleStatement
    from cassandra import ConsistencyLevel, ReadFailure
    import time

    # Strategy 1: Try COUNT(*) with retries
    max_retries = 2
    for attempt in range(max_retries):
        try:
            count_query = SimpleStatement(
                f'SELECT COUNT(*) FROM "{CASSANDRA_KEYSPACE}"."{CASSANDRA_TABLE}" WHERE document_id = %s',
                fetch_size=None,
                consistency_level=ConsistencyLevel.ONE
            )
            result = session.execute(count_query, (document_id,), timeout=60)
            row = result.one()
            return int(row[0]) if row else 0
        except (ReadFailure, Exception) as e:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            # If all retries failed, fall through to client-side scan
            break

    # Strategy 2: Client-side scan fallback
    try:
        scan_query = SimpleStatement(
            f'SELECT element_id FROM "{CASSANDRA_KEYSPACE}"."{CASSANDRA_TABLE}" WHERE document_id = %s',
            fetch_size=5000,
            consistency_level=ConsistencyLevel.ONE
        )
        chunk_count = 0
        for _ in session.execute(scan_query, (document_id,), timeout=120):
            chunk_count += 1
        return chunk_count
    except Exception as e:
        raise ClearDocumentError(f"Cassandra count failed: {e}")


def count_neo4j_nodes(driver, document_id: str) -> Dict[str, int]:
    """Count nodes and relationships in Neo4j for document_id."""
    counts = {
        "nodes": 0,
        "relationships": 0
    }

    try:
        with driver.session() as session:
            # Count nodes
            result = session.run(
                "MATCH (n {document_id: $document_id}) RETURN count(n) as count",
                document_id=document_id
            )
            record = result.single()
            counts["nodes"] = record["count"] if record else 0

            # Count relationships
            result = session.run(
                "MATCH (n {document_id: $document_id})-[r]-() RETURN count(r) as count",
                document_id=document_id
            )
            record = result.single()
            counts["relationships"] = record["count"] if record else 0
    except neo4j_errors.Neo4jError as e:
        raise ClearDocumentError(f"Neo4j count failed: {e}")

    return counts


def delete_mongodb_documents(client: MongoClient, document_id: str, dry_run: bool = False) -> Dict[str, int]:
    """Delete documents from MongoDB collections."""
    db = client[MONGO_DB]

    deleted = {
        "elements": 0,
        "categories": 0,
        "terms": 0,
        "documents": 0
    }

    if dry_run:
        return deleted

    try:
        deleted["elements"] = db.elements.delete_many({"document_id": document_id}).deleted_count
        deleted["categories"] = db.categories.delete_many({"document_id": document_id}).deleted_count
        deleted["terms"] = db.terms.delete_many({"document_id": document_id}).deleted_count
        deleted["documents"] = db.documents.delete_many({"document_id": document_id}).deleted_count
    except mongo_errors.PyMongoError as e:
        raise ClearDocumentError(f"MongoDB deletion failed: {e}")

    return deleted


def delete_cassandra_chunks(session, document_id: str, dry_run: bool = False) -> int:
    """Delete chunks from Cassandra."""
    if dry_run:
        return 0

    try:
        query = f'DELETE FROM "{CASSANDRA_KEYSPACE}"."{CASSANDRA_TABLE}" WHERE document_id = %s'
        session.execute(query, (document_id,), timeout=120)
        # Cassandra DELETE doesn't return count, so we return 0 as placeholder
        return 0
    except Exception as e:
        raise ClearDocumentError(f"Cassandra deletion failed: {e}")


def delete_neo4j_nodes(driver, document_id: str, dry_run: bool = False) -> Dict[str, int]:
    """Delete nodes and relationships from Neo4j."""
    deleted = {
        "nodes": 0,
        "relationships": 0
    }

    if dry_run:
        return deleted

    try:
        with driver.session() as session:
            # Count relationships before deletion
            count_result = session.run(
                "MATCH (n {document_id: $document_id})-[r]-() RETURN count(r) as rels",
                document_id=document_id
            )
            count_record = count_result.single()
            deleted["relationships"] = count_record["rels"] if count_record else 0

            # DETACH DELETE removes nodes and their relationships
            delete_result = session.run(
                "MATCH (n {document_id: $document_id}) DETACH DELETE n RETURN count(n) as nodes",
                document_id=document_id
            )
            delete_record = delete_result.single()
            deleted["nodes"] = delete_record["nodes"] if delete_record else 0
    except neo4j_errors.Neo4jError as e:
        raise ClearDocumentError(f"Neo4j deletion failed: {e}")

    return deleted


def print_summary(document_id: str, mongo_counts: Dict[str, int],
                 cassandra_count: int, neo4j_counts: Dict[str, int],
                 dry_run: bool = False):
    """Print deletion summary."""
    print("=" * 60)
    if dry_run:
        print("Document Cleanup - DRY RUN")
    else:
        print("Document Cleanup - COMPLETED")
    print("=" * 60)
    print(f"Document ID: {document_id}")
    print()

    print("MongoDB:")
    print(f"  Elements:    {mongo_counts['elements']:,}")
    print(f"  Categories:  {mongo_counts['categories']:,}")
    print(f"  Terms:       {mongo_counts['terms']:,}")
    print(f"  Documents:   {mongo_counts['documents']:,}")
    mongo_total = sum(mongo_counts.values())
    print(f"  Total:       {mongo_total:,}")
    print()

    print("Cassandra:")
    print(f"  Embeddings:  {cassandra_count:,}")
    print()

    print("Neo4j:")
    print(f"  Nodes:         {neo4j_counts['nodes']:,}")
    print(f"  Relationships: {neo4j_counts['relationships']:,}")
    print()

    grand_total = mongo_total + cassandra_count + neo4j_counts['nodes']
    print(f"Grand Total: {grand_total:,} entries")
    print("=" * 60)


def confirm_deletion(document_id: str, mongo_counts: Dict[str, int],
                    cassandra_count: int, neo4j_counts: Dict[str, int]) -> bool:
    """Prompt user for deletion confirmation."""
    mongo_total = sum(mongo_counts.values())
    grand_total = mongo_total + cassandra_count + neo4j_counts['nodes']

    print()
    print("⚠️  WARNING: You are about to DELETE all entries for this document!")
    print(f"   Document ID: {document_id}")
    print(f"   Total entries: {grand_total:,}")
    print()
    print("   This operation CANNOT be undone.")
    print()

    response = input("Type 'yes' to confirm deletion: ").strip().lower()
    return response == 'yes'


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog='clear_document.py',
        description='Delete all database entries for a specific document_id',
        add_help=False
    )

    parser.add_argument(
        'document_id',
        type=str,
        help='Document ID to delete'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview deletions without executing'
    )
    parser.add_argument(
        '--targets',
        nargs='+',
        choices=['mongodb', 'cassandra', 'neo4j'],
        default=['mongodb', 'cassandra', 'neo4j'],
        help='Limit cleanup to the specified stores (default: all)'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'clear_document v{__version__}'
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
        document_id = args.document_id

        if not document_id or not document_id.strip():
            print("Error: document_id cannot be empty", file=sys.stderr)
            return 3

        targets = set(args.targets or [])
        conn_mgr = ConnectionManager()

        print("Connecting to databases...")
        mongo_ok = cassandra_ok = neo4j_ok = True

        if "mongodb" in targets:
            mongo_ok = conn_mgr.connect_mongodb()
            if not mongo_ok and not args.dry_run:
                print("\nError: Failed to connect to MongoDB", file=sys.stderr)
                conn_mgr.close_all()
                return 2
        else:
            print("  Skipping MongoDB (not in targets)")

        if "cassandra" in targets:
            cassandra_ok = conn_mgr.connect_cassandra()
            if not cassandra_ok and not args.dry_run:
                print("\nError: Failed to connect to Cassandra", file=sys.stderr)
                conn_mgr.close_all()
                return 2
        else:
            print("  Skipping Cassandra (not in targets)")

        if "neo4j" in targets:
            neo4j_ok = conn_mgr.connect_neo4j()
            if not neo4j_ok and not args.dry_run:
                print("\nError: Failed to connect to Neo4j", file=sys.stderr)
                conn_mgr.close_all()
                return 2
        else:
            print("  Skipping Neo4j (not in targets)")

        print()

        print(f"Counting entries for document_id: {document_id}")
        mongo_counts = {
            "elements": 0,
            "categories": 0,
            "terms": 0,
            "documents": 0
        }
        cassandra_count = 0
        neo4j_counts = {
            "nodes": 0,
            "relationships": 0
        }

        if "mongodb" in targets and mongo_ok:
            mongo_counts = count_mongodb_documents(conn_mgr.mongo_client, document_id)
        if "cassandra" in targets and cassandra_ok:
            cassandra_count = count_cassandra_chunks(conn_mgr.cassandra_session, document_id)
        if "neo4j" in targets and neo4j_ok:
            neo4j_counts = count_neo4j_nodes(conn_mgr.neo4j_driver, document_id)

        mongo_total = sum(mongo_counts.values()) if "mongodb" in targets else 0
        grand_total = (
            mongo_total
            + (cassandra_count if "cassandra" in targets else 0)
            + (neo4j_counts["nodes"] if "neo4j" in targets else 0)
        )

        if grand_total == 0 and targets:
            print(f"\nNo entries found for document_id: {document_id}")
            conn_mgr.close_all()
            return 0

        print_summary(document_id, mongo_counts, cassandra_count, neo4j_counts, dry_run=True)

        if args.dry_run:
            print("\n✓ Dry run completed (no deletions performed)")
            conn_mgr.close_all()
            return 0

        if not args.force:
            if not confirm_deletion(document_id, mongo_counts, cassandra_count, neo4j_counts):
                print("\nOperation cancelled by user")
                conn_mgr.close_all()
                return 1

        print("\nDeleting entries...")
        mongo_deleted = {
            "elements": 0,
            "categories": 0,
            "terms": 0,
            "documents": 0
        }
        cassandra_deleted = 0
        neo4j_deleted = {
            "nodes": 0,
            "relationships": 0
        }

        if "mongodb" in targets and mongo_ok:
            mongo_deleted = delete_mongodb_documents(conn_mgr.mongo_client, document_id)
        if "cassandra" in targets and cassandra_ok:
            cassandra_deleted = delete_cassandra_chunks(conn_mgr.cassandra_session, document_id)
        if "neo4j" in targets and neo4j_ok:
            neo4j_deleted = delete_neo4j_nodes(conn_mgr.neo4j_driver, document_id)

        print()
        print_summary(document_id, mongo_deleted, cassandra_deleted, neo4j_deleted, dry_run=False)

        print("\n✓ Deletion completed successfully")

        conn_mgr.close_all()
        return 0

    except ClearDocumentError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 3


if __name__ == '__main__':
    sys.exit(main())
