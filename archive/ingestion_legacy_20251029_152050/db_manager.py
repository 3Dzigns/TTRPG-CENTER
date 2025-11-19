#!/usr/bin/env python3
"""
db_manager.py - Unified Database Management Tool
=================================================

Manage MongoDB, Cassandra, Neo4j, and PostgreSQL databases.
Provides summarize, clear, and document chunk count operations.

Usage:
  db_manager.py --summarize [options]
  db_manager.py --clear [options]
  db_manager.py --count-document DOCUMENT_ID [--cassandra-keyspace KS] [--cassandra-table T]
  db_manager.py --list-partitions [--partition-limit N] [--cassandra-keyspace KS] [--cassandra-table T]
  db_manager.py -v | --version
  db_manager.py -? | --help

Operations:
  --summarize            Show database statistics (collections, counts, etc.)
  --clear                Clear all data from databases (with confirmation)
  --count-document ID    Count chunks for specific document_id in Cassandra
  --list-partitions      List partition (document) counts for Cassandra table

Options:
  --db TYPE              Target database: mongo|cassandra|neo4j|postgres|all (default: all)
  --force                Skip confirmation prompts for --clear
  --dry-run              Preview clear operations without executing
  --cassandra-keyspace KS  Cassandra keyspace for partition operations (default: ttrpg_vectors)
  --cassandra-table T      Cassandra table for partition operations (default: embeddings)
  --partition-limit N      Max partitions to count with --list-partitions (0 for all, default: 50)
  -v, --version          Show version
  -?, --help             Show this help

Examples:
  # Summarize all databases
  db_manager.py --summarize

  # Summarize only MongoDB
  db_manager.py --summarize --db mongo

  # Clear all databases (with confirmation)
  db_manager.py --clear

  # Clear only Neo4j (skip confirmation)
  db_manager.py --clear --db neo4j --force

  # Preview clear operation
  db_manager.py --clear --dry-run

  # Count chunks for specific document (Pass D validation)
  db_manager.py --count-document cyberpunk_v3_cp4110_core_rulebook_4f81185e7057

  # List the first 10 Cassandra partitions with chunk counts
  db_manager.py --list-partitions --partition-limit 10

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import sys
import time
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set
from datetime import datetime

# Database drivers - imported with error handling
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure as MongoConnectionError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoConnectionError = Exception

try:
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.query import SimpleStatement, ConsistencyLevel
    from cassandra import ReadFailure, OperationTimedOut
    CASSANDRA_AVAILABLE = True
except ImportError:
    CASSANDRA_AVAILABLE = False
    NoHostAvailable = Exception
    ReadFailure = Exception
    OperationTimedOut = Exception

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable as Neo4jConnectionError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    Neo4jConnectionError = Exception

try:
    import psycopg2
    from psycopg2 import OperationalError as PostgresConnectionError
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    PostgresConnectionError = Exception


__version__ = "1.0.0"


class DatabaseManagerError(Exception):
    """Base exception for database manager errors."""
    pass


class BaseDatabaseManager(ABC):
    """Abstract base class for database managers."""

    def __init__(self, name: str):
        self.name = name
        self.connection = None
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the database. Returns True if successful."""
        pass

    @abstractmethod
    def summarize(self) -> Dict[str, Any]:
        """Return database statistics."""
        pass

    @abstractmethod
    def clear(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear all data. Returns operation statistics."""
        pass

    @abstractmethod
    def close(self):
        """Close database connection."""
        pass

    def is_available(self) -> bool:
        """Check if database driver is installed."""
        return True


class MongoDBManager(BaseDatabaseManager):
    """MongoDB database manager."""

    def __init__(self, host: str = "mongodb", port: int = 27017, db_name: str = "ttrpg_ingestion"):
        super().__init__("MongoDB")
        self.host = host
        self.port = port
        self.db_name = db_name
        self.client = None
        self.db = None

    def is_available(self) -> bool:
        return PYMONGO_AVAILABLE

    def connect(self) -> bool:
        """Connect to MongoDB."""
        if not self.is_available():
            return False

        try:
            self.client = MongoClient(
                host=self.host,
                port=self.port,
                serverSelectionTimeoutMS=5000
            )
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            self.connected = True
            return True
        except (MongoConnectionError, Exception) as e:
            self.connected = False
            return False

    def summarize(self) -> Dict[str, Any]:
        """Get MongoDB statistics."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            collections = self.db.list_collection_names()
            stats = {
                "database": self.db_name,
                "collections": {},
                "total_documents": 0
            }

            for collection_name in collections:
                count = self.db[collection_name].count_documents({})
                stats["collections"][collection_name] = count
                stats["total_documents"] += count

            return stats
        except Exception as e:
            return {"error": str(e)}

    def clear(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear all MongoDB collections."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            collections = self.db.list_collection_names()
            stats = {
                "collections_dropped": 0,
                "documents_deleted": 0,
                "collections": []
            }

            for collection_name in collections:
                count = self.db[collection_name].count_documents({})
                stats["collections"].append({
                    "name": collection_name,
                    "documents": count
                })

                if not dry_run:
                    self.db[collection_name].drop()
                    stats["collections_dropped"] += 1
                    stats["documents_deleted"] += count

            return stats
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.connected = False


class CassandraManager(BaseDatabaseManager):
    """Cassandra database manager."""

    def __init__(self, host: str = "cassandra", port: int = 9042):
        super().__init__("Cassandra")
        self.host = host
        self.port = port
        self.cluster = None
        self.session = None

    def is_available(self) -> bool:
        return CASSANDRA_AVAILABLE

    def connect(self) -> bool:
        """Connect to Cassandra."""
        if not self.is_available():
            return False

        try:
            self.cluster = Cluster(
                [self.host],
                port=self.port,
                connect_timeout=5
            )
            self.session = self.cluster.connect()
            self.connected = True
            return True
        except (NoHostAvailable, Exception) as e:
            self.connected = False
            return False

    def _get_partition_keys(self, keyspace: str, table: str) -> List[str]:
        """Return the partition key column names for a table using metadata API."""
        try:
            # Use cluster metadata API instead of querying system_schema
            # This avoids ALLOW FILTERING requirements
            metadata = self.cluster.metadata
            keyspace_meta = metadata.keyspaces.get(keyspace)
            if not keyspace_meta:
                print(f"  ERROR: Keyspace '{keyspace}' not found in metadata")
                return []

            table_meta = keyspace_meta.tables.get(table)
            if not table_meta:
                print(f"  ERROR: Table '{table}' not found in keyspace '{keyspace}'")
                return []

            # Extract partition key column names
            partition_keys = [col.name for col in table_meta.partition_key]

            if not partition_keys:
                print(f"  WARNING: No partition keys found for {keyspace}.{table}")

            return partition_keys
        except Exception as e:
            print(f"  ERROR getting partition keys for {keyspace}.{table}: {e}")
            return []

    def _estimate_row_count(self, keyspace: str, table: str) -> Optional[int]:
        """
        Return an approximate row count using system.size_estimates.

        Cassandra does not track exact counts, but partitions_count offers a
        reasonable estimate without a full table scan.
        """
        try:
            estimate_query = SimpleStatement(
                """
                SELECT partitions_count
                FROM system.size_estimates
                WHERE keyspace_name = %s AND table_name = %s
                """,
                fetch_size=None,
            )
            rows = self.session.execute(estimate_query, (keyspace, table))
            total = 0
            for row in rows:
                partitions = getattr(row, "partitions_count", 0) or 0
                total += int(partitions)
            return total if total > 0 else None
        except Exception:
            return None

    def _fetch_manifest_row(self, keyspace: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Return manifest metadata for a document if available."""
        try:
            self.session.set_keyspace(keyspace)
            stmt = SimpleStatement(
                f"""
                SELECT document_id, chunk_count, vector_checksum,
                       chunk_index_min, chunk_index_max,
                       embedding_model, vector_dim, updated_at, updated_by
                FROM embedding_manifests
                WHERE document_id = %s
                """,
                consistency_level=ConsistencyLevel.ONE,
            )
            row = self.session.execute(stmt, (document_id,), timeout=10).one()
            if not row:
                return None

            return {
                "document_id": row.document_id,
                "chunk_count": row.chunk_count,
                "vector_checksum": row.vector_checksum,
                "chunk_index_min": row.chunk_index_min,
                "chunk_index_max": row.chunk_index_max,
                "embedding_model": row.embedding_model,
                "vector_dim": row.vector_dim,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "updated_by": row.updated_by,
            }
        except Exception:
            return None

    def _count_by_partitions(self, keyspace: str, table: str) -> Optional[int]:
        """
        Count rows by iterating through partition keys for accuracy without full scan.

        Only enabled when the table has a single partition key column.
        """
        partition_keys = self._get_partition_keys(keyspace, table)
        if len(partition_keys) != 1:
            return None

        partition_col = partition_keys[0]

        try:
            distinct_query = SimpleStatement(
                f'SELECT DISTINCT "{partition_col}" FROM "{keyspace}"."{table}"',
                fetch_size=1000,  # Increased for better pagination performance
                consistency_level=ConsistencyLevel.ONE,
            )
            partition_values = [
                getattr(row, partition_col)
                for row in self.session.execute(distinct_query, timeout=20)  # Reduced timeout for faster fallback
                if getattr(row, partition_col) is not None
            ]
        except Exception:
            # Skip scan fallback - return None to allow COUNT(*) attempt instead
            return None

        total = 0
        count_query = SimpleStatement(
            f'SELECT COUNT(*) FROM "{keyspace}"."{table}" WHERE "{partition_col}" = %s',
            fetch_size=None,
            consistency_level=ConsistencyLevel.ONE,
        )

        for value in partition_values:
            try:
                row = self.session.execute(count_query, (value,), timeout=20).one()  # Reduced timeout
                if row is not None:
                    total += int(row[0])
            except Exception:
                # Skip scan fallback - return None to allow COUNT(*) attempt
                return None

        return total

    def _count_by_token_ranges(self, keyspace: str, table: str, partition_col: str, num_ranges: int = 256) -> Optional[int]:
        """
        Count rows using token range pagination for 100% accuracy without timeouts.

        Splits the Cassandra token space into ranges and counts each separately.
        This avoids loading all partition keys and prevents timeout issues.

        Args:
            keyspace: Keyspace name
            table: Table name
            partition_col: Partition key column name
            num_ranges: Number of token ranges to split into (default: 256)

        Returns:
            Total row count (exact), or None if method fails
        """
        from cassandra.query import SimpleStatement
        from cassandra import ConsistencyLevel, ReadFailure

        # Cassandra token range: -2^63 to 2^63-1
        MIN_TOKEN = -9223372036854775808
        MAX_TOKEN = 9223372036854775807

        range_size = (MAX_TOKEN - MIN_TOKEN) // num_ranges
        total = 0
        failed_ranges = []

        for i in range(num_ranges):
            start_token = MIN_TOKEN + (i * range_size)
            end_token = start_token + range_size if i < num_ranges - 1 else MAX_TOKEN

            count_query = SimpleStatement(
                f'SELECT COUNT(*) FROM "{keyspace}"."{table}" '
                f'WHERE token("{partition_col}") >= {start_token} '
                f'AND token("{partition_col}") < {end_token}',
                fetch_size=None,
                consistency_level=ConsistencyLevel.ONE,
            )

            # Retry logic for ReadFailure exceptions
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    result = self.session.execute(count_query, timeout=60)  # Increased timeout
                    row = result.one()
                    if row:
                        total += int(row[0])
                    # Progress indicator every 10 ranges
                    if i % 10 == 0:
                        print(".", end='', flush=True)
                    break  # Success - exit retry loop
                except ReadFailure as e:
                    if attempt < max_retries - 1:
                        # Retry with backoff
                        time.sleep(1 * (attempt + 1))
                        continue
                    else:
                        # Final retry failed
                        failed_ranges.append(i)
                        print(f"\n  ERROR range {i}/{num_ranges}: ReadFailure (retried {max_retries}x)", flush=True)
                        break
                except Exception as e:
                    failed_ranges.append(i)
                    print(f"\n  ERROR range {i}/{num_ranges}: {e.__class__.__name__}", flush=True)
                    break

        print()  # Newline after progress dots

        # If ranges failed, try scanning them individually
        if failed_ranges:
            print(f"  WARNING: {len(failed_ranges)}/{num_ranges} ranges failed: {failed_ranges[:10]}{'...' if len(failed_ranges) > 10 else ''}")
            print(f"  Attempting client-side scan of failed ranges...")

            # Scan each failed range
            scanned_total = 0
            scan_failures = []

            for range_idx in failed_ranges:
                start_token = MIN_TOKEN + (range_idx * range_size)
                end_token = start_token + range_size if range_idx < num_ranges - 1 else MAX_TOKEN

                try:
                    # Scan partition keys in this token range
                    scan_query = SimpleStatement(
                        f'SELECT "{partition_col}" FROM "{keyspace}"."{table}" '
                        f'WHERE token("{partition_col}") >= {start_token} '
                        f'AND token("{partition_col}") < {end_token}',
                        fetch_size=5000,
                        consistency_level=ConsistencyLevel.ONE,
                    )

                    range_count = 0
                    for _ in self.session.execute(scan_query, timeout=120):
                        range_count += 1

                    scanned_total += range_count
                    print(f"  ✓ Scanned range {range_idx}: {range_count:,} rows")

                except Exception as e:
                    scan_failures.append(range_idx)
                    print(f"  ✗ Scan failed for range {range_idx}: {e.__class__.__name__}")

            # If any scans failed, abort
            if scan_failures:
                print(f"  ERROR: {len(scan_failures)} ranges failed scan: {scan_failures}")
                return None

            # Add scanned results to total
            total += scanned_total
            print(f"  ✓ Client-side scan recovered {scanned_total:,} rows from {len(failed_ranges)} failed ranges")

        return total

    def _scan_row_count(self, keyspace: str, table: str, partition_col: str) -> Optional[int]:
        """
        Fallback that scans rows by selecting the partition column only.

        Limits to a reasonable number of rows to avoid runaway scans on very
        large tables.
        """
        max_scan_rows = 1_000_000
        try:
            scan_query = SimpleStatement(
                f'SELECT "{partition_col}" FROM "{keyspace}"."{table}"',
                fetch_size=2000,
                consistency_level=ConsistencyLevel.ONE,
            )
            total = 0
            for _ in self.session.execute(scan_query, timeout=60):
                total += 1
                if total > max_scan_rows:
                    return None
            return total
        except Exception:
            return None

    def list_partition_counts(
        self,
        keyspace: str = "ttrpg_vectors",
        table: str = "embeddings",
        limit: Optional[int] = 50,
        fetch_size: int = 200,
    ) -> Dict[str, Any]:
        """
        Iterate through distinct partition values and count each individually.

        Args:
            keyspace: Cassandra keyspace name.
            table: Table name.
            limit: Maximum number of partitions to evaluate (None or 0 for all).
            fetch_size: Paging size for DISTINCT iteration.

        Returns:
            Dictionary containing per-partition counts and summary metadata.
        """
        if not self.connected:
            return {"error": "Not connected"}

        partition_keys = self._get_partition_keys(keyspace, table)
        if not partition_keys:
            return {"error": f"No partition keys found for {keyspace}.{table}"}
        if len(partition_keys) > 1:
            return {
                "error": (
                    f"{keyspace}.{table} has composite partition keys {partition_keys}; "
                    "listing counts requires a single partition column"
                )
            }

        partition_col = partition_keys[0]

        partitions: List[Dict[str, Any]] = []
        total_chunks = 0
        evaluated = 0
        truncated = False

        try:
            distinct_stmt = SimpleStatement(
                f'SELECT DISTINCT "{partition_col}" FROM "{keyspace}"."{table}"',
                fetch_size=fetch_size,
                consistency_level=ConsistencyLevel.ONE,
            )
            rows = self.session.execute(distinct_stmt, timeout=60)

            for row in rows:
                document_id = getattr(row, partition_col, None)
                if document_id is None:
                    continue

                count_info = self.count_document_chunks(
                    document_id,
                    keyspace=keyspace,
                    table=table,
                    partition_col=partition_col,
                )
                partitions.append(count_info)

                chunk_count = count_info.get("chunk_count")
                if isinstance(chunk_count, int):
                    total_chunks += chunk_count

                evaluated += 1
                if limit and limit > 0 and evaluated >= limit:
                    truncated = True
                    break

            return {
                "keyspace": keyspace,
                "table": table,
                "partition_key": partition_col,
                "documents_evaluated": evaluated,
                "total_chunk_count": total_chunks,
                "partitions": partitions,
                "truncated": truncated,
                "note": (
                    "Set --partition-limit 0 to evaluate all partitions; "
                    "this may be expensive on large datasets."
                )
                if truncated
                else None,
            }
        except Exception as exc:
            return {"error": str(exc)}

    def count_document_chunks(
        self,
        document_id: str,
        keyspace: str = "ttrpg_vectors",
        table: str = "embeddings",
        partition_col: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Count chunks for a specific document_id in Cassandra embeddings table.

        This method uses the partition key (document_id) for fast, accurate counting.
        Ideal for validation against Pass D manifest rows_inserted values.

        For large partitions that fail COUNT(*), falls back to client-side scanning.

        Args:
            document_id: Document ID to count chunks for
            keyspace: Cassandra keyspace (default: ttrpg_vectors)
            table: Table name (default: embeddings)

        Returns:
            Dictionary with document_id, chunk_count, and metadata:
            {
                "document_id": str,
                "chunk_count": int,
                "keyspace": str,
                "table": str,
                "found": bool
            }
            Or on error:
            {
                "document_id": str,
                "error": str
            }
        """
        import time

        if not self.connected:
            return {"error": "Not connected"}

        manifest = self._fetch_manifest_row(keyspace, document_id)

        result_payload: Dict[str, Any] = {
            "document_id": document_id,
            "keyspace": keyspace,
            "table": table,
            "manifest_found": bool(manifest),
        }

        if manifest and manifest.get("chunk_count") is not None:
            chunk_count = int(manifest.get("chunk_count") or 0)
            result_payload.update(
                {
                    "chunk_count": chunk_count,
                    "vector_checksum": manifest.get("vector_checksum"),
                    "chunk_index_min": manifest.get("chunk_index_min"),
                    "chunk_index_max": manifest.get("chunk_index_max"),
                    "embedding_model": manifest.get("embedding_model"),
                    "vector_dim": manifest.get("vector_dim"),
                    "updated_at": manifest.get("updated_at"),
                    "updated_by": manifest.get("updated_by"),
                    "found": chunk_count > 0,
                    "method": "manifest",
                }
            )
            return result_payload

        # Determine partition column
        if partition_col is None:
            partition_keys = self._get_partition_keys(keyspace, table)
            if not partition_keys:
                return {
                    "document_id": document_id,
                    "error": f"No partition keys found for {keyspace}.{table}"
                }
            if len(partition_keys) > 1:
                return {
                    "document_id": document_id,
                    "error": (
                        f"Multiple partition keys ({partition_keys}) detected; "
                        "count_document_chunks requires a single partition column"
                    )
                }
            partition_col = partition_keys[0]

        # Strategy 1: Try COUNT(*) with retries
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Count rows for specific document_id using partition key
                count_query = SimpleStatement(
                    f'SELECT COUNT(*) FROM "{keyspace}"."{table}" WHERE "{partition_col}" = %s',
                    fetch_size=None,
                    consistency_level=ConsistencyLevel.ONE
                )

                result = self.session.execute(count_query, (document_id,), timeout=60)
                row = result.one()

                if row is None:
                    return {
                        "document_id": document_id,
                        "chunk_count": 0,
                        "keyspace": keyspace,
                        "table": table,
                        "found": False
                    }

                chunk_count = int(row[0])

                result_payload.update(
                    {
                        "chunk_count": chunk_count,
                        "found": chunk_count > 0,
                        "method": "count",
                    }
                )
                return result_payload

            except ReadFailure as e:
                if attempt < max_retries - 1:
                    # Retry with backoff
                    time.sleep(1 * (attempt + 1))
                    continue
                else:
                    # Final retry failed - try client-side scan
                    break
            except Exception as e:
                # Non-ReadFailure errors return immediately
                return {
                    "document_id": document_id,
                    "error": str(e)
                }

        # Strategy 2: Client-side scan fallback
        try:
            scan_query = SimpleStatement(
                f'SELECT element_id FROM "{keyspace}"."{table}" WHERE "{partition_col}" = %s',
                fetch_size=5000,
                consistency_level=ConsistencyLevel.ONE
            )

            chunk_count = 0
            for _ in self.session.execute(scan_query, (document_id,), timeout=120):
                chunk_count += 1

            result_payload.update(
                {
                    "chunk_count": chunk_count,
                    "found": chunk_count > 0,
                    "method": "scan",
                }
            )
            return result_payload

        except Exception as e:
            result_payload["error"] = str(e)
            return result_payload

    def summarize(self) -> Dict[str, Any]:
        """Get Cassandra statistics."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            # Get all keyspaces (excluding system keyspaces)
            keyspaces_query = "SELECT keyspace_name FROM system_schema.keyspaces"
            rows = self.session.execute(keyspaces_query)
            # Filter out system keyspaces in Python
            system_keyspaces = {
                'system',
                'system_schema',
                'system_auth',
                'system_distributed',
                'system_traces',
                'system_virtual_schema',
                'data_endpoint_auth',  # Managed by Stargate auth component
            }
            keyspaces = [row.keyspace_name for row in rows if row.keyspace_name not in system_keyspaces]

            stats = {
                "keyspaces": {},
                "total_tables": 0
            }

            for keyspace in keyspaces:
                # Get tables in keyspace
                tables_query = f"SELECT table_name FROM system_schema.tables WHERE keyspace_name = '{keyspace}'"
                table_rows = self.session.execute(tables_query)
                tables = [row.table_name for row in table_rows]

                keyspace_stats = {"tables": {}}
                for table in tables:
                    partition_keys = self._get_partition_keys(keyspace, table)
                    table_info: Dict[str, Any] = {
                        "partition_keys": partition_keys or []
                    }

                    estimate = self._estimate_row_count(keyspace, table)
                    if estimate is not None:
                        table_info["approx_partitions"] = estimate

                    if len(partition_keys) == 1:
                        table_info["count_hint"] = (
                            "Use --list-partitions for per-partition counts"
                        )
                    else:
                        table_info["count_hint"] = (
                            "Composite partition key; per-partition counts not supported"
                        )

                    keyspace_stats["tables"][table] = table_info

                stats["keyspaces"][keyspace] = keyspace_stats
                stats["total_tables"] += len(tables)

            return stats
        except Exception as e:
            return {"error": str(e)}

    def clear(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear all Cassandra user tables."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            # Get all user keyspaces
            keyspaces_query = "SELECT keyspace_name FROM system_schema.keyspaces"
            rows = self.session.execute(keyspaces_query)
            # Filter out system keyspaces in Python
            system_keyspaces = {'system', 'system_schema', 'system_auth', 'system_distributed', 'system_traces', 'system_virtual_schema'}
            keyspaces = [row.keyspace_name for row in rows if row.keyspace_name not in system_keyspaces]

            stats = {
                "keyspaces_dropped": 0,
                "tables_truncated": 0,
                "keyspaces": []
            }

            for keyspace in keyspaces:
                # Get tables in keyspace
                tables_query = f"SELECT table_name FROM system_schema.tables WHERE keyspace_name = '{keyspace}'"
                table_rows = self.session.execute(tables_query)
                tables = [row.table_name for row in table_rows]

                keyspace_info = {
                    "name": keyspace,
                    "tables": tables
                }
                stats["keyspaces"].append(keyspace_info)

                if not dry_run:
                    # Truncate all tables in keyspace
                    for table in tables:
                        self.session.execute(f"TRUNCATE {keyspace}.{table}")
                        stats["tables_truncated"] += 1

            return stats
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        """Close Cassandra connection."""
        if self.cluster:
            self.cluster.shutdown()
            self.connected = False


class Neo4jManager(BaseDatabaseManager):
    """Neo4j graph database manager."""

    def __init__(self, uri: str = "bolt://neo4j:7687",
                 user: str = None,
                 password: str = None):
        # Use environment variables if not explicitly provided
        if user is None:
            user = os.getenv("NEO4J_USER", "neo4j")
        if password is None:
            password = os.getenv("NEO4J_PASSWORD", "password")
        super().__init__("Neo4j")
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None

    def is_available(self) -> bool:
        return NEO4J_AVAILABLE

    def connect(self) -> bool:
        """Connect to Neo4j."""
        if not self.is_available():
            return False

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=5
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            self.connected = True
            return True
        except (Neo4jConnectionError, Exception) as e:
            self.connected = False
            return False

    def summarize(self) -> Dict[str, Any]:
        """Get Neo4j statistics."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            with self.driver.session() as session:
                # Count nodes
                node_result = session.run("MATCH (n) RETURN count(n) as count")
                node_count = node_result.single()["count"]

                # Count relationships
                rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                rel_count = rel_result.single()["count"]

                # Get labels
                labels_result = session.run("CALL db.labels()")
                labels = [record["label"] for record in labels_result]

                # Count by label
                label_counts = {}
                for label in labels:
                    count_result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                    label_counts[label] = count_result.single()["count"]

                # Get relationship types
                rel_types_result = session.run("CALL db.relationshipTypes()")
                rel_types = [record["relationshipType"] for record in rel_types_result]

                return {
                    "total_nodes": node_count,
                    "total_relationships": rel_count,
                    "labels": label_counts,
                    "relationship_types": rel_types
                }
        except Exception as e:
            return {"error": str(e)}

    def clear(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear all Neo4j nodes and relationships."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            with self.driver.session() as session:
                # Get counts before clearing
                node_result = session.run("MATCH (n) RETURN count(n) as count")
                node_count = node_result.single()["count"]

                rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
                rel_count = rel_result.single()["count"]

                stats = {
                    "nodes_deleted": node_count,
                    "relationships_deleted": rel_count
                }

                if not dry_run:
                    # Delete all nodes and relationships
                    # Use batching for large graphs to avoid memory issues
                    batch_size = 10000
                    while True:
                        result = session.run(f"MATCH (n) WITH n LIMIT {batch_size} DETACH DELETE n RETURN count(n) as deleted")
                        deleted = result.single()["deleted"]
                        if deleted == 0:
                            break

                return stats
        except Exception as e:
            return {"error": str(e)}

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.connected = False


class PostgreSQLManager(BaseDatabaseManager):
    """PostgreSQL database manager."""

    def __init__(self, host: str = "postgres", port: int = 5432,
                 user: str = None,
                 password: str = None,
                 db_name: str = None):
        # Use environment variables if not explicitly provided
        if user is None:
            user = os.getenv("POSTGRES_USER", "postgres")
        if password is None:
            password = os.getenv("POSTGRES_PASSWORD", "postgres")
        if db_name is None:
            db_name = os.getenv("POSTGRES_DB", "ttrpg_ingestion")
        super().__init__("PostgreSQL")
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.db_name = db_name
        self.conn = None
        self.cursor = None

    def is_available(self) -> bool:
        return PSYCOPG2_AVAILABLE

    def connect(self) -> bool:
        """Connect to PostgreSQL."""
        if not self.is_available():
            return False

        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.db_name,
                connect_timeout=5
            )
            self.cursor = self.conn.cursor()
            self.connected = True
            return True
        except (PostgresConnectionError, Exception) as e:
            self.connected = False
            return False

    def summarize(self) -> Dict[str, Any]:
        """Get PostgreSQL statistics."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            # Get all tables in public schema
            self.cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in self.cursor.fetchall()]

            stats = {
                "database": self.db_name,
                "tables": {},
                "total_rows": 0
            }

            for table in tables:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                stats["tables"][table] = count
                stats["total_rows"] += count

            return stats
        except Exception as e:
            return {"error": str(e)}

    def clear(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear all PostgreSQL tables."""
        if not self.connected:
            return {"error": "Not connected"}

        try:
            # Get all tables in public schema
            self.cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in self.cursor.fetchall()]

            stats = {
                "tables_truncated": 0,
                "rows_deleted": 0,
                "tables": []
            }

            for table in tables:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                stats["tables"].append({
                    "name": table,
                    "rows": count
                })

                if not dry_run:
                    self.cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
                    stats["tables_truncated"] += 1
                    stats["rows_deleted"] += count

            if not dry_run:
                self.conn.commit()

            return stats
        except Exception as e:
            if not dry_run:
                self.conn.rollback()
            return {"error": str(e)}

    def close(self):
        """Close PostgreSQL connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        self.connected = False


def create_managers(db_filter: str = "all") -> List[BaseDatabaseManager]:
    """Create database managers based on filter."""
    managers = []

    if db_filter in ("all", "mongo"):
        managers.append(MongoDBManager())

    if db_filter in ("all", "cassandra"):
        managers.append(CassandraManager())

    if db_filter in ("all", "neo4j"):
        managers.append(Neo4jManager())

    if db_filter in ("all", "postgres"):
        managers.append(PostgreSQLManager())

    return managers


def print_separator(char: str = "=", length: int = 60):
    """Print a separator line."""
    print(char * length)


def format_summary_output(manager_name: str, stats: Dict[str, Any]):
    """Format and print summary statistics."""
    print_separator()
    print(f"{manager_name} Summary")
    print_separator()

    if "error" in stats:
        print(f"  Error: {stats['error']}")
        return

    if manager_name == "MongoDB":
        print(f"  Database: {stats['database']}")
        print(f"  Total Documents: {stats['total_documents']}")
        print("\n  Collections:")
        for coll, count in stats['collections'].items():
            print(f"    - {coll}: {count:,} documents")

    elif manager_name == "Cassandra":
        print(f"  Total Tables: {stats['total_tables']}")
        print("\n  Keyspaces:")
        for keyspace, data in stats['keyspaces'].items():
            print(f"    {keyspace}:")
            for table, info in data['tables'].items():
                if isinstance(info, dict):
                    partition_keys = info.get("partition_keys", [])
                    approx = info.get("approx_partitions")
                    hint = info.get("count_hint")
                    print(f"      - {table}:")
                    print(f"          Partition Keys: {partition_keys or 'N/A'}")
                    if approx is not None:
                        print(f"          Approx. Partitions: {approx:,}")
                    if hint:
                        print(f"          Hint: {hint}")
                else:
                    # Backwards compatibility for older summary formats
                    if isinstance(info, int):
                        formatted = f"{info:,} rows"
                    else:
                        formatted = str(info)
                    print(f"      - {table}: {formatted}")

    elif manager_name == "Neo4j":
        print(f"  Total Nodes: {stats['total_nodes']:,}")
        print(f"  Total Relationships: {stats['total_relationships']:,}")
        print("\n  Node Labels:")
        for label, count in stats['labels'].items():
            print(f"    - {label}: {count:,} nodes")
        print("\n  Relationship Types:")
        for rel_type in stats['relationship_types']:
            print(f"    - {rel_type}")

    elif manager_name == "PostgreSQL":
        print(f"  Database: {stats['database']}")
        print(f"  Total Rows: {stats['total_rows']:,}")
        print("\n  Tables:")
        for table, count in stats['tables'].items():
            print(f"    - {table}: {count:,} rows")


def format_clear_output(manager_name: str, stats: Dict[str, Any], dry_run: bool):
    """Format and print clear operation results."""
    print_separator()
    print(f"{manager_name} Clear {'(DRY RUN)' if dry_run else ''}")
    print_separator()

    if "error" in stats:
        print(f"  Error: {stats['error']}")
        return

    if manager_name == "MongoDB":
        print(f"  Collections: {len(stats['collections'])}")
        print(f"  Documents to delete: {stats.get('documents_deleted', 'N/A'):,}")
        if not dry_run:
            print(f"  Collections dropped: {stats['collections_dropped']}")

    elif manager_name == "Cassandra":
        print(f"  Keyspaces affected: {len(stats['keyspaces'])}")
        print(f"  Tables to truncate: {sum(len(ks['tables']) for ks in stats['keyspaces'])}")
        if not dry_run:
            print(f"  Tables truncated: {stats['tables_truncated']}")

    elif manager_name == "Neo4j":
        print(f"  Nodes to delete: {stats['nodes_deleted']:,}")
        print(f"  Relationships to delete: {stats['relationships_deleted']:,}")

    elif manager_name == "PostgreSQL":
        print(f"  Tables to truncate: {len(stats['tables'])}")
        print(f"  Rows to delete: {stats.get('rows_deleted', 'N/A'):,}")
        if not dry_run:
            print(f"  Tables truncated: {stats['tables_truncated']}")


def confirm_clear() -> bool:
    """Prompt user for confirmation before clearing data."""
    print("\n⚠️  WARNING: This will DELETE ALL DATA from the selected database(s)!")
    print("This operation CANNOT be undone.\n")
    response = input("Type 'yes' to confirm: ")
    return response.lower() == 'yes'


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Unified database management tool',
        add_help=False
    )

    # Operations (mutually exclusive)
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument(
        '--summarize',
        action='store_true',
        help='Show database statistics'
    )
    operations.add_argument(
        '--clear',
        action='store_true',
        help='Clear all data from databases'
    )
    operations.add_argument(
        '--count-document',
        type=str,
        metavar='DOCUMENT_ID',
        help='Count chunks for specific document_id in Cassandra'
    )
    operations.add_argument(
        '--list-partitions',
        action='store_true',
        help='List per-partition (document) counts for Cassandra tables'
    )

    # Options
    parser.add_argument(
        '--db',
        type=str,
        choices=['mongo', 'cassandra', 'neo4j', 'postgres', 'all'],
        default='all',
        help='Target database (default: all)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts for --clear'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview clear operations without executing'
    )
    parser.add_argument(
        '--cassandra-keyspace',
        type=str,
        default='ttrpg_vectors',
        help='Cassandra keyspace for partition operations (default: ttrpg_vectors)'
    )
    parser.add_argument(
        '--cassandra-table',
        type=str,
        default='embeddings',
        help='Cassandra table for partition operations (default: embeddings)'
    )
    parser.add_argument(
        '--partition-limit',
        type=int,
        default=50,
        help='Max partitions to count with --list-partitions (0 for all, default: 50)'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'db_manager v{__version__}'
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

        # Force Cassandra-only mode for Cassandra partition operations
        if args.count_document or args.list_partitions:
            db_selection = 'cassandra'
        else:
            db_selection = args.db

        # Create managers
        managers = create_managers(db_selection)

        if not managers:
            print("Error: No databases selected", file=sys.stderr)
            return 1

        # Connect to all managers
        print(f"Connecting to databases...")
        connected_managers = []
        for manager in managers:
            if not manager.is_available():
                print(f"  {manager.name}: Driver not installed (skipping)")
                continue

            if manager.connect():
                print(f"  {manager.name}: Connected ✓")
                connected_managers.append(manager)
            else:
                print(f"  {manager.name}: Connection failed (skipping)")

        if not connected_managers:
            print("\nError: No databases are reachable", file=sys.stderr)
            return 1

        print()

        # Execute operation
        if args.count_document:
            # Count document chunks operation - Cassandra only
            cassandra_managers = [m for m in connected_managers if isinstance(m, CassandraManager)]

            if not cassandra_managers:
                print("Error: Cassandra not connected", file=sys.stderr)
                return 1

            cassandra = cassandra_managers[0]
            result = cassandra.count_document_chunks(
                args.count_document,
                keyspace=args.cassandra_keyspace,
                table=args.cassandra_table
            )

            print(f"{'='*60}")
            print(f"Document Chunk Count - Cassandra")
            print(f"{'='*60}")

            if "error" in result:
                print(f"  Error: {result['error']}")
            else:
                if result.get("manifest_found"):
                    print("  Manifest:")
                    print(f"    Chunk Count: {result.get('chunk_count', 0):,}")
                    print(f"    Vector Checksum: {result.get('vector_checksum')}")
                    print(
                        "    Chunk Index Range: "
                        f"{result.get('chunk_index_min')} - {result.get('chunk_index_max')}"
                    )
                    if result.get("updated_at"):
                        print(f"    Updated At: {result.get('updated_at')}")
                        print(f"    Updated By: {result.get('updated_by')}")
                else:
                    print("  Manifest: not found")

                chunk_count = result.get("chunk_count")
                if chunk_count is not None:
                    print(f"  Chunk Count (query): {chunk_count:,}")
                if result.get("method"):
                    print(f"  Method: {result.get('method')}")

                print(f"  Document ID: {result['document_id']}")
                print(f"  Keyspace: {result.get('keyspace', 'N/A')}")
                print(f"  Table: {result.get('table', 'N/A')}")
                print(f"  Found: {'Yes' if result['found'] else 'No'}")

            print()

        elif args.list_partitions:
            cassandra_managers = [m for m in connected_managers if isinstance(m, CassandraManager)]

            if not cassandra_managers:
                print("Error: Cassandra not connected", file=sys.stderr)
                return 1

            cassandra = cassandra_managers[0]
            partition_limit = None if args.partition_limit == 0 else args.partition_limit
            result = cassandra.list_partition_counts(
                keyspace=args.cassandra_keyspace,
                table=args.cassandra_table,
                limit=partition_limit
            )

            print(f"{'='*60}")
            print(f"Cassandra Partition Counts")
            print(f"{'='*60}")

            if "error" in result:
                print(f"  Error: {result['error']}")
            else:
                print(f"  Keyspace: {result.get('keyspace')}")
                print(f"  Table: {result.get('table')}")
                print(f"  Partition Key: {result.get('partition_key')}")
                print(f"  Documents Evaluated: {result.get('documents_evaluated', 0)}")
                print(f"  Total Chunk Count: {result.get('total_chunk_count', 0):,}")
                print()
                print("  Documents:")
                partitions = result.get("partitions", [])
                if not partitions:
                    print("    (none)")
                else:
                    for entry in partitions:
                        doc_id = entry.get("document_id", "<unknown>")
                        if "error" in entry:
                            print(f"    - {doc_id}: ERROR ({entry['error']})")
                        else:
                            chunk_count = entry.get("chunk_count", 0)
                            method = entry.get("method", "count")
                            print(f"    - {doc_id}: {chunk_count:,} chunks ({method})")

                note = result.get("note")
                if note:
                    print()
                    print(f"  Note: {note}")

                if result.get("truncated"):
                    print("  Result truncated; increase --partition-limit or set to 0 for all partitions.")

            print()

        elif args.summarize:
            # Summarize operation
            for manager in connected_managers:
                stats = manager.summarize()
                format_summary_output(manager.name, stats)
                print()

        elif args.clear:
            # Clear operation
            if not args.force and not args.dry_run:
                if not confirm_clear():
                    print("\nOperation cancelled by user")
                    return 0

            print()
            for manager in connected_managers:
                stats = manager.clear(dry_run=args.dry_run)
                format_clear_output(manager.name, stats, args.dry_run)
                print()

            if args.dry_run:
                print("DRY RUN - No changes were made")
            else:
                print("✓ Clear operation completed")

        # Close connections
        for manager in connected_managers:
            manager.close()

        return 0

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
