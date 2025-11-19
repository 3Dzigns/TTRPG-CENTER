#!/usr/bin/env python3
"""
cleanup_document.py - Remove Document Artifacts and Database Entries

Removes all artifacts and database entries for a document:
- Job directories and files from /Transfer_Station/jobs/
- Postgres dictionary rows
- Cassandra vectors and checksums
- Neo4j graph nodes and relationships

Usage:
    python3 cleanup_document.py --filename <document.pdf>
    python3 cleanup_document.py --job-id <job_id>
"""

import os
import sys
import json
import logging
import argparse
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from dictionary_store import DictionaryStore, DictionaryStoreError

try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
    CASSANDRA_AVAILABLE = True
except ImportError:
    CASSANDRA_AVAILABLE = False
    print("Warning: cassandra-driver not available, Cassandra cleanup will be skipped")

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("Warning: neo4j not available, Neo4j cleanup will be skipped")


class DocumentCleanup:
    """
    Comprehensive document cleanup utility.

    Removes all traces of a document from:
    - File system (/Transfer_Station/jobs/, /Transfer_Station/output/)
    - Postgres dictionary store
    - Cassandra (vectors, checksums)
    - Neo4j (nodes, relationships)
    """

    def __init__(self, filename: Optional[str] = None, job_id: Optional[str] = None):
        """
        Initialize cleanup utility.

        Args:
            filename: PDF filename (will compute job_id)
            job_id: Direct job_id (if known)
        """
        self.filename = filename
        self.job_id = job_id

        # Setup logging
        self.logger = logging.getLogger("cleanup_document")
        self.logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Paths
        self.transfer_station = Path("/Transfer_Station")
        self.jobs_dir = self.transfer_station / "jobs"
        self.output_dir = self.transfer_station / "output"
        self.logs_dir = self.transfer_station / "Logs"

        # Database connections
        self.cassandra_session = None
        self.neo4j_driver = None
        self.document_id: Optional[str] = None

        # Cleanup stats
        self.stats = {
            "job_dirs_removed": 0,
            "output_files_removed": 0,
            "dictionary_rows_removed": 0,
            "cassandra_vectors_removed": 0,
            "cassandra_checksums_removed": 0,
            "neo4j_nodes_removed": 0,
            "neo4j_relationships_removed": 0
        }

    def _find_job_id_from_filename(self) -> Optional[str]:
        """
        Find job_id by searching job directories for matching filename.

        Returns:
            job_id if found, None otherwise
        """
        if not self.filename:
            return None

        self.logger.info(f"Searching for job_id matching filename: {self.filename}")

        try:
            # Search all stage directories
            for stage_dir in self.jobs_dir.glob("*"):
                if not stage_dir.is_dir():
                    continue

                # Search job directories in this stage
                for job_dir in stage_dir.glob("*"):
                    if not job_dir.is_dir():
                        continue

                    # Check status.json for matching filename
                    status_file = job_dir / "status.json"
                    if status_file.exists():
                        try:
                            with open(status_file, 'r', encoding="utf-8") as f:
                                status = json.load(f)

                            source_pdf = status.get("source_pdf", "")
                            if Path(source_pdf).name == self.filename:
                                job_id = job_dir.name
                                self.logger.info(f"? Found job_id: {job_id}")
                                return job_id

                        except Exception as e:
                            self.logger.debug(f"Failed to read {status_file}: {e}")

        except Exception as e:
            self.logger.error(f"Error searching for job_id: {e}")

        self.logger.warning(f"? No job_id found for filename: {self.filename}")
        return None


    def _resolve_document_id(self) -> Optional[str]:
        """Attempt to read document_id from job status metadata."""
        if self.job_id:
            for stage_dir in self.jobs_dir.glob("*"):
                status_path = stage_dir / self.job_id / "status.json"
                if status_path.exists():
                    try:
                        with status_path.open("r", encoding="utf-8") as handle:
                            status = json.load(handle)
                        doc_id = status.get("document_id") or status.get("document", {}).get("document_id")
                        if doc_id:
                            self.logger.info(f"Resolved document_id={doc_id} from {status_path}")
                            return doc_id
                    except Exception as exc:
                        self.logger.debug(f"Failed to read {status_path}: {exc}")

        if self.filename:
            fallback = Path(self.filename).stem
            self.logger.info(f"Falling back to filename-derived document_id={fallback}")
            return fallback
        return None


    def _cleanup_dictionary(self) -> int:
        """
        Remove dictionary rows for this document from Postgres.

        Returns:
            Number of rows removed (0 or 1)
        """
        if not self.document_id:
            return 0

        self.logger.info(f"Cleaning up dictionary entry for: {self.document_id}")

        try:
            with DictionaryStore() as store:
                removed = store.delete_document(self.document_id)
                if removed:
                    self.logger.info("Removed dictionary row from Postgres")
                else:
                    self.logger.info("No dictionary row found in Postgres")
                return removed
        except DictionaryStoreError as e:
            self.logger.error(f"Error removing dictionary entry: {e}")
            return 0


    def _connect_cassandra(self):
        """Connect to Cassandra."""
        if not CASSANDRA_AVAILABLE:
            self.logger.warning("Cassandra driver not available, skipping Cassandra cleanup")
            return

        try:
            contact_points = os.getenv("CASSANDRA_CONTACT_POINTS", "cassandra").split(",")
            cluster = Cluster(contact_points)
            self.cassandra_session = cluster.connect()
            self.cassandra_session.set_keyspace("ttrpg")
            self.logger.info("✅ Connected to Cassandra")
        except Exception as e:
            self.logger.error(f"Failed to connect to Cassandra: {e}")

    def _connect_neo4j(self):
        """Connect to Neo4j."""
        if not NEO4J_AVAILABLE:
            self.logger.warning("Neo4j driver not available, skipping Neo4j cleanup")
            return

        try:
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

            self.neo4j_driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password)
            )
            self.logger.info("✅ Connected to Neo4j")
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")

    def _cleanup_job_directories(self) -> int:
        """
        Remove all job directories for this document.

        Returns:
            Number of directories removed
        """
        removed_count = 0

        if not self.job_id:
            self.logger.warning("No job_id available, skipping job directory cleanup")
            return 0

        self.logger.info(f"Cleaning up job directories for job_id: {self.job_id}")

        try:
            # Search all stage directories
            for stage_dir in self.jobs_dir.glob("*"):
                if not stage_dir.is_dir():
                    continue

                job_dir = stage_dir / self.job_id
                if job_dir.exists():
                    self.logger.info(f"Removing: {job_dir}")
                    shutil.rmtree(job_dir)
                    removed_count += 1

        except Exception as e:
            self.logger.error(f"Error removing job directories: {e}")

        self.logger.info(f"Removed {removed_count} job directories")
        return removed_count

    def _cleanup_output_files(self) -> int:
        """
        Remove output files for this document.

        Returns:
            Number of files removed
        """
        removed_count = 0

        if not self.filename:
            self.logger.warning("No filename available, skipping output file cleanup")
            return 0

        self.logger.info(f"Cleaning up output files for: {self.filename}")

        try:
            base_name = Path(self.filename).stem

            # Search all output subdirectories
            for output_subdir in self.output_dir.glob("*"):
                if not output_subdir.is_dir():
                    continue

                # Find files matching base_name
                for output_file in output_subdir.glob(f"{base_name}*"):
                    self.logger.info(f"Removing: {output_file}")
                    if output_file.is_file():
                        output_file.unlink()
                        removed_count += 1
                    elif output_file.is_dir():
                        shutil.rmtree(output_file)
                        removed_count += 1

        except Exception as e:
            self.logger.error(f"Error removing output files: {e}")

        self.logger.info(f"Removed {removed_count} output files")
        return removed_count

    def _cleanup_dictionary(self) -> int:
        """
        Remove dictionary rows for this document from Postgres.

        Returns:
            Number of rows removed (0 or 1)
        """
        if not self.filename:
            return 0

        document_id = Path(self.filename).stem
        self.logger.info(f"Cleaning up dictionary entry for: {document_id}")

        try:
            with DictionaryStore() as store:
                removed = store.delete_document(document_id)
                if removed:
                    self.logger.info("Removed dictionary row from Postgres")
                else:
                    self.logger.info("No dictionary row found in Postgres")
                return removed
        except DictionaryStoreError as e:
            self.logger.error(f"Error removing dictionary entry: {e}")
            return 0

    def _cleanup_cassandra(self) -> Dict[str, int]:
        """
        Remove Cassandra entries for this document.

        Returns:
            Dictionary with counts of removed entries
        """
        counts = {"vectors": 0, "checksums": 0}

        if not self.cassandra_session or not self.filename:
            return counts

        self.logger.info(f"Cleaning up Cassandra entries for: {self.filename}")

        try:
            # Remove from chunk_vectors table
            query = "SELECT chunk_id FROM chunk_vectors WHERE source_file = %s"
            rows = self.cassandra_session.execute(query, [self.filename])

            chunk_ids = [row.chunk_id for row in rows]
            if chunk_ids:
                delete_query = "DELETE FROM chunk_vectors WHERE chunk_id = %s"
                for chunk_id in chunk_ids:
                    self.cassandra_session.execute(delete_query, [chunk_id])
                counts["vectors"] = len(chunk_ids)
                self.logger.info(f"Removed {counts['vectors']} vectors from Cassandra")

            # Remove from checksums table (if exists)
            checksum_query = "DELETE FROM checksums WHERE source_file = %s"
            self.cassandra_session.execute(checksum_query, [self.filename])
            counts["checksums"] = 1  # Assume one checksum per file
            self.logger.info(f"Removed checksums from Cassandra")

        except Exception as e:
            self.logger.error(f"Error removing Cassandra entries: {e}")

        return counts

    def _cleanup_neo4j(self) -> Dict[str, int]:
        """
        Remove Neo4j nodes and relationships for this document.

        Returns:
            Dictionary with counts of removed nodes/relationships
        """
        counts = {"nodes": 0, "relationships": 0}

        if not self.neo4j_driver or not self.filename:
            return counts

        self.logger.info(f"Cleaning up Neo4j graph for: {self.filename}")

        try:
            with self.neo4j_driver.session() as session:
                # Remove relationships first
                rel_query = """
                MATCH (n {source_file: $filename})-[r]-()
                DELETE r
                RETURN count(r) as count
                """
                result = session.run(rel_query, filename=self.filename)
                counts["relationships"] = result.single()["count"]
                self.logger.info(f"Removed {counts['relationships']} relationships from Neo4j")

                # Remove nodes
                node_query = """
                MATCH (n {source_file: $filename})
                DELETE n
                RETURN count(n) as count
                """
                result = session.run(node_query, filename=self.filename)
                counts["nodes"] = result.single()["count"]
                self.logger.info(f"Removed {counts['nodes']} nodes from Neo4j")

        except Exception as e:
            self.logger.error(f"Error removing Neo4j entries: {e}")

        return counts

    def cleanup(self) -> Dict[str, int]:
        """
        Execute complete cleanup for document.

        Returns:
            Dictionary with cleanup statistics
        """
        self.logger.info("=" * 80)
        self.logger.info("Starting Document Cleanup")
        self.logger.info("=" * 80)

        # Find job_id if not provided
        if not self.job_id and self.filename:
            self.job_id = self._find_job_id_from_filename()
        self.document_id = self._resolve_document_id()

        # Connect to databases
        self._connect_cassandra()
        self._connect_neo4j()

        # Execute cleanup
        self.stats["job_dirs_removed"] = self._cleanup_job_directories()
        self.stats["output_files_removed"] = self._cleanup_output_files()

        self.stats["dictionary_rows_removed"] = self._cleanup_dictionary()

        cassandra_counts = self._cleanup_cassandra()
        self.stats["cassandra_vectors_removed"] = cassandra_counts["vectors"]
        self.stats["cassandra_checksums_removed"] = cassandra_counts["checksums"]

        neo4j_counts = self._cleanup_neo4j()
        self.stats["neo4j_nodes_removed"] = neo4j_counts["nodes"]
        self.stats["neo4j_relationships_removed"] = neo4j_counts["relationships"]

        # Close connections
        if self.cassandra_session:
            self.cassandra_session.cluster.shutdown()
        if self.neo4j_driver:
            self.neo4j_driver.close()

        # Print summary
        self.logger.info("=" * 80)
        self.logger.info("Cleanup Complete - Summary")
        self.logger.info("=" * 80)
        self.logger.info(f"Filename:                    {self.filename}")
        self.logger.info(f"Job ID:                      {self.job_id}")
        self.logger.info(f"Job directories removed:     {self.stats['job_dirs_removed']}")
        self.logger.info(f"Output files removed:        {self.stats['output_files_removed']}")
        self.logger.info(f"Dictionary rows removed:     {self.stats['dictionary_rows_removed']}")
        self.logger.info(f"Cassandra vectors removed:   {self.stats['cassandra_vectors_removed']}")
        self.logger.info(f"Cassandra checksums removed: {self.stats['cassandra_checksums_removed']}")
        self.logger.info(f"Neo4j nodes removed:         {self.stats['neo4j_nodes_removed']}")
        self.logger.info(f"Neo4j relationships removed: {self.stats['neo4j_relationships_removed']}")
        self.logger.info("=" * 80)

        return self.stats


def main():
    """Main entry point for cleanup script."""
    parser = argparse.ArgumentParser(
        description="Cleanup Document - Remove all artifacts and database entries"
    )
    parser.add_argument(
        "--filename",
        help="PDF filename (e.g., document.pdf)"
    )
    parser.add_argument(
        "--job-id",
        help="Job ID (if known, otherwise will search by filename)"
    )

    args = parser.parse_args()

    if not args.filename and not args.job_id:
        parser.error("Must provide either --filename or --job-id")

    # Create cleanup utility
    cleanup = DocumentCleanup(filename=args.filename, job_id=args.job_id)

    # Execute cleanup
    try:
        stats = cleanup.cleanup()

        # Exit with success if anything was removed
        total_removed = sum(stats.values())
        if total_removed > 0:
            sys.exit(0)
        else:
            print("\n⚠️ Warning: No artifacts found to remove")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
