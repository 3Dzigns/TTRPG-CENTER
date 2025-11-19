#!/usr/bin/env python3
"""
pass_e_document_node_validator.py - Document Node Validation (Fix for Issue #4)
================================================================================

Ensures Neo4j document nodes are created and validated after Pass E upsert.
Implements rollback capability for failed document node creation.

This module addresses the root cause identified in Pass F validation failures:
- Document nodes missing for all files
- Orphaned chunk nodes without parent document
- Neo4j scores of 0.0 due to missing document-level nodes

Usage:
  Integrated into pass_e_neo4j_upsert.py automatically
  Can also be used standalone for validation:
    pass_e_document_node_validator.py <document_id> [options]

Version: 1.0.0
Author: n8n TTRPG Center
"""

import logging
from typing import Any, Dict, Optional, Tuple

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import Neo4jError
except ImportError:
    print("ERROR: neo4j driver not installed. Run: pip install neo4j")
    import sys
    sys.exit(1)

logger = logging.getLogger(__name__)


class DocumentNodeValidationError(Exception):
    """Raised when document node validation fails."""


class DocumentNodeValidator:
    """
    Validates and ensures document nodes exist in Neo4j.
    Implements create-verify-rollback pattern for robustness.
    """

    def __init__(self, neo4j_session):
        """
        Initialize validator with active Neo4j session.

        Args:
            neo4j_session: Active neo4j.Session object
        """
        self.session = neo4j_session

    def create_document_node_with_validation(
        self,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Create document node with validation and rollback on failure.

        This implements the fix for Issue #4: Neo4j document nodes missing.

        Process:
        1. Create document node with MERGE
        2. Verify node was actually created (first validation)
        3. Re-query to confirm node persistence (second validation)
        4. If validation fails, rollback any partial chunks

        Args:
            document_id: Unique document identifier
            metadata: Document metadata (title, game_system, page_count, etc.)

        Returns:
            Tuple of (success: bool, message: str, node_data: Optional[Dict])

        Raises:
            DocumentNodeValidationError: If creation or validation fails
        """
        try:
            # Step 1: Create document node
            logger.info(f"Creating document node: {document_id}")

            create_result = self.session.run("""
                MERGE (d:Document {document_id: $doc_id})
                SET d.title = $title,
                    d.game_system = $game_system,
                    d.publisher = $publisher,
                    d.page_count = $page_count,
                    d.total_chunks = $total_chunks,
                    d.pass_e_created_at = datetime(),
                    d.pass_e_updated_at = datetime()
                RETURN d
            """, {
                'doc_id': document_id,
                'title': metadata.get('title', ''),
                'game_system': metadata.get('game_system', ''),
                'publisher': metadata.get('publisher', ''),
                'page_count': metadata.get('page_count', 0),
                'total_chunks': metadata.get('total_chunks', 0)
            })

            # Step 2: First validation - check MERGE returned a result
            record = create_result.single()
            if not record:
                error_msg = f"Document node creation failed: MERGE returned no record"
                logger.error(f"  ❌ {error_msg}")
                self._rollback_chunks(document_id)
                return False, error_msg, None

            node_data = dict(record['d'])
            logger.info(f"  ✅ Document node created: {node_data.get('document_id')}")

            # Step 3: Second validation - re-query to confirm persistence
            logger.info(f"Validating document node persistence...")
            verify_result = self.session.run("""
                MATCH (d:Document {document_id: $doc_id})
                RETURN d, id(d) as node_id
            """, doc_id=document_id)

            verify_record = verify_result.single()
            if not verify_record:
                error_msg = f"Document node verification failed: Node not found after creation"
                logger.error(f"  ❌ {error_msg}")
                self._rollback_chunks(document_id)
                return False, error_msg, None

            node_id = verify_record['node_id']
            logger.info(f"  ✅ Document node verified (Neo4j ID: {node_id})")

            # Step 4: Success - return node data
            return True, f"Document node created and validated (ID: {node_id})", node_data

        except Neo4jError as e:
            error_msg = f"Neo4j error during document node creation: {e}"
            logger.error(f"  ❌ {error_msg}")
            self._rollback_chunks(document_id)
            raise DocumentNodeValidationError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error during document node creation: {e}"
            logger.error(f"  ❌ {error_msg}")
            self._rollback_chunks(document_id)
            raise DocumentNodeValidationError(error_msg) from e

    def _rollback_chunks(self, document_id: str) -> int:
        """
        Rollback (delete) any chunk nodes if document node creation failed.

        This prevents orphaned chunks without a parent document.

        Args:
            document_id: Document identifier for chunks to delete

        Returns:
            Number of chunks deleted
        """
        try:
            logger.warning(f"Rolling back chunk nodes for failed document: {document_id}")

            result = self.session.run("""
                MATCH (c:Chunk {document_id: $doc_id})
                DETACH DELETE c
                RETURN count(c) as deleted_count
            """, doc_id=document_id)

            record = result.single()
            deleted_count = record['deleted_count'] if record else 0

            if deleted_count > 0:
                logger.warning(f"  ⚠️  Rolled back {deleted_count} orphaned chunk nodes")
            else:
                logger.info(f"  ℹ️  No chunk nodes to rollback")

            return deleted_count

        except Neo4jError as e:
            logger.error(f"  ❌ Rollback failed: {e}")
            return 0

    def validate_existing_document_node(
        self,
        document_id: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validate that a document node exists for the given document_id.

        Use this to check document nodes after pipeline completion.

        Args:
            document_id: Document identifier to validate

        Returns:
            Tuple of (exists: bool, message: str, node_data: Optional[Dict])
        """
        try:
            result = self.session.run("""
                MATCH (d:Document {document_id: $doc_id})
                RETURN d, id(d) as node_id
            """, doc_id=document_id)

            record = result.single()
            if not record:
                return False, f"Document node not found: {document_id}", None

            node_data = dict(record['d'])
            node_id = record['node_id']

            return True, f"Document node exists (Neo4j ID: {node_id})", node_data

        except Neo4jError as e:
            error_msg = f"Error validating document node: {e}"
            logger.error(error_msg)
            return False, error_msg, None

    def count_orphaned_chunks(self, document_id: str) -> int:
        """
        Count chunk nodes that exist without a parent document node.

        Args:
            document_id: Document identifier

        Returns:
            Number of orphaned chunks
        """
        try:
            result = self.session.run("""
                MATCH (c:Chunk {document_id: $doc_id})
                OPTIONAL MATCH (d:Document {document_id: $doc_id})
                WITH c, d
                WHERE d IS NULL
                RETURN count(c) as orphaned_count
            """, doc_id=document_id)

            record = result.single()
            return record['orphaned_count'] if record else 0

        except Neo4jError as e:
            logger.error(f"Error counting orphaned chunks: {e}")
            return 0

    def link_orphaned_chunks(self, document_id: str) -> int:
        """
        Create HAS_CHUNK relationships for orphaned chunks.

        Use this if document node was created but relationships weren't.

        Args:
            document_id: Document identifier

        Returns:
            Number of relationships created
        """
        try:
            logger.info(f"Linking orphaned chunks to document: {document_id}")

            result = self.session.run("""
                MATCH (d:Document {document_id: $doc_id})
                MATCH (c:Chunk {document_id: $doc_id})
                WHERE NOT (d)-[:HAS_CHUNK]->(c)
                MERGE (d)-[:HAS_CHUNK]->(c)
                RETURN count(c) as linked_count
            """, doc_id=document_id)

            record = result.single()
            linked_count = record['linked_count'] if record else 0

            if linked_count > 0:
                logger.info(f"  ✅ Linked {linked_count} orphaned chunks")
            else:
                logger.info(f"  ℹ️  No orphaned chunks found")

            return linked_count

        except Neo4jError as e:
            logger.error(f"Error linking orphaned chunks: {e}")
            return 0


def integrate_with_upsert(session, document_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Integration point for pass_e_neo4j_upsert.py.

    Call this BEFORE upserting chunk nodes to ensure document node exists.

    Args:
        session: Active Neo4j session
        document_id: Document identifier
        metadata: Document metadata

    Returns:
        True if document node created/validated successfully, False otherwise
    """
    validator = DocumentNodeValidator(session)
    success, message, node_data = validator.create_document_node_with_validation(
        document_id, metadata
    )

    if not success:
        logger.error(f"Document node validation failed: {message}")
        return False

    logger.info(f"Document node validation passed: {message}")
    return True


if __name__ == "__main__":
    # Standalone validation mode
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validate Neo4j document nodes")
    parser.add_argument('document_id', help='Document ID to validate')
    parser.add_argument('--neo4j-uri', default='bolt://localhost:9005', help='Neo4j URI')
    parser.add_argument('--neo4j-user', default='neo4j', help='Neo4j username')
    parser.add_argument('--neo4j-pass', default='password', help='Neo4j password')
    parser.add_argument('--fix-orphans', action='store_true', help='Link orphaned chunks')

    args = parser.parse_args()

    try:
        driver = GraphDatabase.driver(
            args.neo4j_uri,
            auth=(args.neo4j_user, args.neo4j_pass)
        )

        with driver.session() as session:
            validator = DocumentNodeValidator(session)

            # Validate document node
            exists, message, node_data = validator.validate_existing_document_node(args.document_id)
            print(f"\n{'='*60}")
            print(f"Document Node Validation: {args.document_id}")
            print(f"{'='*60}")
            print(f"Status: {'✅ EXISTS' if exists else '❌ MISSING'}")
            print(f"Message: {message}")

            if exists and node_data:
                print(f"\nNode Data:")
                for key, value in node_data.items():
                    print(f"  {key}: {value}")

            # Check for orphaned chunks
            orphaned_count = validator.count_orphaned_chunks(args.document_id)
            print(f"\nOrphaned Chunks: {orphaned_count}")

            # Fix orphans if requested
            if args.fix_orphans and orphaned_count > 0:
                linked = validator.link_orphaned_chunks(args.document_id)
                print(f"Linked Chunks: {linked}")

        driver.close()
        sys.exit(0 if exists else 1)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
