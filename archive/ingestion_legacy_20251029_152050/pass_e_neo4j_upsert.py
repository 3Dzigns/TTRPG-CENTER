#!/usr/bin/env python3
"""
pass_e_neo4j_upsert.py - Neo4j Upsert for Pass E Knowledge Graph
================================================================

Loads Pass E graph JSON and upserts nodes/edges into Neo4j with optional
index creation and manifest reporting.
Supports document-specific cleanup via Gate 0 rebuild flags (v2.0.0).

Usage:
  pass_e_neo4j_upsert.py <graph_json> [options]
  pass_e_neo4j_upsert.py -v | --version
  pass_e_neo4j_upsert.py -? | --help

Arguments:
  graph_json            Path to Pass E graph JSON file

Options:
  -o, --output DIR           Output directory for manifest (default: config or /Transfer_Station/Pass_E_Out)
  --host HOST                Neo4j host (default: config or n8n_TTRPG_neo4j)
  --port PORT                Neo4j bolt port (default: 7687)
  --database NAME            Neo4j database name (default: neo4j)
  --user USER                Neo4j username (default: env NEO4J_USER)
  --password PASSWORD        Neo4j password (default: env NEO4J_PASSWORD)
  --env-file PATH            Optional .env path to load credentials
  --gate-marker FILE         Gate 0 marker file (v2.0.0, enables rebuild mode)
  --create-indexes           Create standard indexes before upsert
  --dry-run                  Load and validate graph without writing to Neo4j
  --node-batch-size N        Batch size for node upserts (default: 100)
  --edge-batch-size N        Batch size for edge upserts (default: 200)
  -v, --version              Show version information
  -?, --help                 Show this help message and exit

Examples:
  # With Gate 0 marker (rebuild mode enabled)
  pass_e_neo4j_upsert.py /Transfer_Station/Pass_E_Out/doc_graph.json \
    --gate-marker /Transfer_Station/Gate_0_Out/document_20251009_120000.json --create-indexes

  # Legacy mode (no cleanup)
  pass_e_neo4j_upsert.py /Transfer_Station/Pass_E_Out/doc_graph.json --create-indexes

  # Dry run
  pass_e_neo4j_upsert.py doc_graph.json --dry-run

Version: 2.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from path_utils import resolve_transfer_path

from dotenv import load_dotenv

try:
    from neo4j import GraphDatabase, basic_auth
    from neo4j.exceptions import Neo4jError
except ImportError:
    print("Error: neo4j driver is not installed. Run: pip install neo4j", file=sys.stderr)
    sys.exit(1)

try:
    from config_loader import load_config, get_pass_e_config, ConfigurationError  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_config = None  # type: ignore
    get_pass_e_config = None  # type: ignore
    ConfigurationError = Exception  # type: ignore


__version__ = "2.0.0"

DEFAULT_OUTPUT_DIR = resolve_transfer_path("Pass_E_Out")
DEFAULT_NEO4J_HOST = "n8n_TTRPG_neo4j"
DEFAULT_NEO4J_PORT = 7687
DEFAULT_NEO4J_DATABASE = "neo4j"
DEFAULT_NODE_BATCH_SIZE = 100
DEFAULT_EDGE_BATCH_SIZE = 200


class PassENeo4jUpsertError(Exception):
    """Raised when Pass E Neo4j upsert encounters an error."""


class ChangeTracker:
    """Track node and relationship changes during upsert."""

    def __init__(self) -> None:
        self.node_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {'created': 0, 'matched': 0})
        self.relationship_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {'created': 0, 'properties_set': 0})

    def add_node_result(self, label: str, created: int, matched: int) -> None:
        stats = self.node_stats[label]
        stats['created'] += int(created or 0)
        stats['matched'] += int(matched or 0)

    def add_relationship_result(self, rel_type: str, created: int, properties_set: int) -> None:
        stats = self.relationship_stats[rel_type]
        stats['created'] += int(created or 0)
        stats['properties_set'] += int(properties_set or 0)

    def total_nodes_created(self) -> int:
        return sum(stats['created'] for stats in self.node_stats.values())

    def total_nodes_matched(self) -> int:
        return sum(stats['matched'] for stats in self.node_stats.values())

    def total_relationships_created(self) -> int:
        return sum(stats['created'] for stats in self.relationship_stats.values())

    def as_dict(self) -> Dict[str, Any]:
        return {
            'nodes_by_label': dict(self.node_stats),
            'relationships_by_type': dict(self.relationship_stats),
            'totals': {
                'nodes_created': self.total_nodes_created(),
                'nodes_matched': self.total_nodes_matched(),
                'relationships_created': self.total_relationships_created()
            }
        }


def load_default_settings() -> Dict[str, Any]:
    """Load default Pass E settings from ingestion.cfg when available."""
    defaults: Dict[str, Any] = {
        'output_dir': DEFAULT_OUTPUT_DIR,
        'neo4j_host': DEFAULT_NEO4J_HOST,
        'neo4j_port': DEFAULT_NEO4J_PORT,
        'neo4j_database': DEFAULT_NEO4J_DATABASE,
    }

    if load_config and get_pass_e_config:
        try:
            config = load_config()
            pass_e_cfg = get_pass_e_config(config)
            if 'output_dir' in pass_e_cfg:
                defaults['output_dir'] = Path(pass_e_cfg['output_dir'])
            if 'neo4j_host' in pass_e_cfg:
                defaults['neo4j_host'] = pass_e_cfg['neo4j_host']
            if 'neo4j_port' in pass_e_cfg:
                defaults['neo4j_port'] = int(pass_e_cfg['neo4j_port'])
            if 'neo4j_database' in pass_e_cfg:
                defaults['neo4j_database'] = pass_e_cfg['neo4j_database']
        except Exception:
            # Config loading is optional; ignore failures to allow standalone usage.
            pass

    return defaults


def load_environment(env_path: Optional[Path]) -> None:
    """Load environment variables from the provided .env path or repository root."""
    if env_path:
        load_dotenv(env_path)
    else:
        repo_env = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(repo_env)
        load_dotenv()


def load_graph_data(graph_path: Path) -> Dict[str, Any]:
    """Load and validate graph JSON output from pass_e_graph_builder."""
    if not graph_path.exists():
        raise PassENeo4jUpsertError(f"Graph file not found: {graph_path}")

    try:
        with open(graph_path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        raise PassENeo4jUpsertError(f"Failed to read graph JSON: {exc}") from exc

    if 'document_id' not in data:
        raise PassENeo4jUpsertError("Graph JSON missing required 'document_id' field")
    if 'nodes' not in data or 'edges' not in data:
        raise PassENeo4jUpsertError("Graph JSON missing 'nodes' or 'edges' sections")

    return data


def compute_graph_statistics(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return statistics for the graph, computing when not supplied."""
    if 'statistics' in graph_data and isinstance(graph_data['statistics'], dict):
        return graph_data['statistics']

    nodes = graph_data.get('nodes', {})
    edges = graph_data.get('edges', {})

    nodes_by_type = {label: len(items) for label, items in nodes.items()}
    edges_by_type = {edge_type: len(items) for edge_type, items in edges.items()}

    return {
        'nodes_by_type': nodes_by_type,
        'edges_by_type': edges_by_type,
        'total_nodes': sum(nodes_by_type.values()),
        'total_edges': sum(edges_by_type.values())
    }


def batch_iterable(items: List[Dict[str, Any]], batch_size: int) -> Iterable[List[Dict[str, Any]]]:
    """Yield successive batches from a list."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


def clear_document_graph(
    session,
    document_id: str,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    Clear all nodes and relationships for a specific document_id from Neo4j.
    Enables document-specific rebuilds without affecting other documents.

    Args:
        session: Neo4j session
        document_id: Document identifier to clear
        dry_run: If True, report counts without deleting

    Returns:
        Dict with deletion counts per label

    Raises:
        PassENeo4jUpsertError: If deletion fails
    """
    try:
        deletion_counts = {}

        # Count nodes by label
        count_query = """
            MATCH (n {document_id: $document_id})
            WITH labels(n)[0] AS label, count(n) AS count
            RETURN label, count
        """
        result = session.run(count_query, document_id=document_id)
        for record in result:
            label = record["label"]
            count = record["count"]
            deletion_counts[label] = count

        # Delete if not dry run
        if not dry_run and deletion_counts:
            delete_query = """
                MATCH (n {document_id: $document_id})
                DETACH DELETE n
            """
            session.run(delete_query, document_id=document_id)

        return deletion_counts

    except Neo4jError as e:
        raise PassENeo4jUpsertError(f"Failed to clear Neo4j nodes: {e}")


def connect_neo4j(uri: str, user: str, password: str):
    """Create and verify a Neo4j driver connection."""
    try:
        driver = GraphDatabase.driver(uri, auth=basic_auth(user, password))
        driver.verify_connectivity()
        return driver
    except Neo4jError as exc:
        raise PassENeo4jUpsertError(f"Neo4j connection failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover - safety net
        raise PassENeo4jUpsertError(f"Unexpected Neo4j connection error: {exc}") from exc


def create_indexes(session) -> int:
    """Create standard indexes to speed up MERGE operations."""
    statements = [
        "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.document_id)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Chunk) ON (c.chunk_id)",
        "CREATE INDEX IF NOT EXISTS FOR (t:Term) ON (t.term)",
        "CREATE INDEX IF NOT EXISTS FOR (cat:Category) ON (cat.name)"
    ]

    for statement in statements:
        session.run(statement)

    return len(statements)


def _run_node_upsert(tx, query: str, nodes: List[Dict[str, Any]]) -> Tuple[int, int]:
    result = tx.run(query, nodes=nodes)
    record = result.single()
    if record is None:
        return 0, 0
    return int(record.get('created', 0) or 0), int(record.get('matched', 0) or 0)


def upsert_nodes_by_label(
    session,
    label: str,
    match_key: str,
    nodes: List[Dict[str, Any]],
    tracker: ChangeTracker,
    batch_size: int
) -> None:
    """Upsert nodes of a single label using batched MERGE statements."""
    if not nodes:
        return

    query = (
        f"UNWIND $nodes AS node\n"
        f"MERGE (n:{label} {{{match_key}: node.{match_key}}})\n"
        f"ON CREATE SET n += node,\n"
        f"              n.__is_new__ = true,\n"
        f"              n.pass_e_created_at = datetime(),\n"
        f"              n.pass_e_updated_at = datetime()\n"
        f"ON MATCH SET n += node,\n"
        f"             n.pass_e_updated_at = datetime()\n"
        f"WITH n, coalesce(n.__is_new__, false) AS is_new\n"
        f"REMOVE n.__is_new__\n"
        f"RETURN\n"
        f"  sum(CASE WHEN is_new THEN 1 ELSE 0 END) AS created,\n"
        f"  sum(CASE WHEN is_new THEN 0 ELSE 1 END) AS matched"
    )

    for batch in batch_iterable(nodes, batch_size):
        created, matched = session.execute_write(_run_node_upsert, query, batch)  # type: ignore[arg-type]
        tracker.add_node_result(label, created, matched)


def _run_edge_upsert(tx, query: str, edges: List[Dict[str, Any]]) -> Tuple[int, int]:
    result = tx.run(query, edges=edges)
    summary = result.consume()
    counters = summary.counters
    return counters.relationships_created, counters.properties_set


def upsert_edges(
    session,
    rel_type: str,
    from_label: str,
    from_key: str,
    to_label: str,
    to_key: str,
    edges: List[Dict[str, Any]],
    tracker: ChangeTracker,
    batch_size: int,
    properties: Optional[List[str]] = None
) -> None:
    """Upsert relationships between existing nodes."""
    if not edges:
        return

    properties = properties or []
    set_statements = ["r.pass_e_last_upsert = datetime()"]
    for prop in properties:
        set_statements.append(f"r.{prop} = edge.{prop}")

    set_clause = "SET " + ", ".join(set_statements)

    query = (
        f"UNWIND $edges AS edge\n"
        f"MATCH (from:{from_label} {{{from_key}: edge.from}})\n"
        f"MATCH (to:{to_label} {{{to_key}: edge.to}})\n"
        f"MERGE (from)-[r:{rel_type}]->(to)\n"
        f"{set_clause}"
    )

    for batch in batch_iterable(edges, batch_size):
        created, properties_set = session.execute_write(_run_edge_upsert, query, batch)  # type: ignore[arg-type]
        tracker.add_relationship_result(rel_type, created, properties_set)


def write_manifest(
    manifest_path: Path,
    document_id: str,
    graph_path: Path,
    graph_stats: Dict[str, Any],
    tracker: ChangeTracker,
    timings: Dict[str, float],
    neo4j_info: Dict[str, Any],
    indexes_created: int
) -> Path:
    """Write Pass E manifest summarizing Neo4j upsert results."""
    manifest_data = {
        "document_id": document_id,
        "input_graph": str(graph_path),
        "processing": {
            "graph_loaded": True,
            "neo4j_upsert_seconds": timings.get("total_seconds"),
            "node_upsert_seconds": timings.get("node_upsert_seconds"),
            "edge_upsert_seconds": timings.get("edge_upsert_seconds"),
            "indexes_created": indexes_created,
        },
        "graph_statistics": graph_stats,
        "neo4j": {
            "host": neo4j_info["host"],
            "port": neo4j_info["port"],
            "database": neo4j_info["database"],
            "nodes_created": tracker.total_nodes_created(),
            "nodes_matched": tracker.total_nodes_matched(),
            "relationships_created": tracker.total_relationships_created(),
            "change_breakdown": tracker.as_dict()
        },
        "output_files": {
            "manifest": manifest_path.name
        },
        "timings": timings,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, 'w', encoding='utf-8') as handle:
        json.dump(manifest_data, handle, indent=2, ensure_ascii=False)

    return manifest_path


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    defaults = load_default_settings()

    parser = argparse.ArgumentParser(
        description="Upsert Pass E knowledge graph data into Neo4j",
        add_help=False
    )

    parser.add_argument("graph_json", type=Path, help="Path to Pass E graph JSON file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=defaults["output_dir"],
        help=f"Output directory for manifest (default: {defaults['output_dir']})"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=defaults["neo4j_host"],
        help=f"Neo4j host (default: {defaults['neo4j_host']})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=defaults["neo4j_port"],
        help=f"Neo4j bolt port (default: {defaults['neo4j_port']})"
    )
    parser.add_argument(
        "--database",
        type=str,
        default=defaults["neo4j_database"],
        help=f"Neo4j database name (default: {defaults['neo4j_database']})"
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="Neo4j username (default: environment variable NEO4J_USER)"
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Neo4j password (default: environment variable NEO4J_PASSWORD)"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to .env file with credentials (optional)"
    )
    parser.add_argument(
        "--gate-marker",
        type=Path,
        help="Gate 0 marker file (v2.0.0, enables rebuild mode)"
    )
    parser.add_argument(
        "--create-indexes",
        action="store_true",
        help="Create recommended indexes before upserting nodes"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate graph and show summary without writing to Neo4j"
    )
    parser.add_argument(
        "--node-batch-size",
        type=int,
        default=DEFAULT_NODE_BATCH_SIZE,
        help=f"Batch size for node upserts (default: {DEFAULT_NODE_BATCH_SIZE})"
    )
    parser.add_argument(
        "--edge-batch-size",
        type=int,
        default=DEFAULT_EDGE_BATCH_SIZE,
        help=f"Batch size for edge upserts (default: {DEFAULT_EDGE_BATCH_SIZE})"
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-?",
        "--help",
        action="help",
        help="Show this help message and exit"
    )

    return parser.parse_args()


def main() -> int:
    """Entrypoint for command line execution."""
    args = parse_args()

    load_environment(args.env_file)

    user = args.user or os.getenv("NEO4J_USER")
    password = args.password or os.getenv("NEO4J_PASSWORD")

    if not user or not password:
        raise PassENeo4jUpsertError(
            "Neo4j credentials not provided. Use --user/--password or set NEO4J_USER / NEO4J_PASSWORD."
        )

    start_time = time.time()
    graph_load_start = time.time()
    graph_data = load_graph_data(args.graph_json)
    graph_statistics = compute_graph_statistics(graph_data)
    graph_load_seconds = round(time.time() - graph_load_start, 2)

    document_id = graph_data["document_id"]

    print(f"Loaded graph for document {document_id}")
    print(f"  Nodes: {graph_statistics['nodes_by_type']}")
    print(f"  Edges: {graph_statistics['edges_by_type']}")

    if args.dry_run:
        print("\n--dry-run mode: Graph validated, no changes applied to Neo4j.")
        return 0

    uri = f"bolt://{args.host}:{args.port}"
    print(f"\nConnecting to Neo4j at {uri} (database: {args.database})...")
    driver = connect_neo4j(uri, user, password)

    tracker = ChangeTracker()
    timings: Dict[str, float] = {
        "graph_load_seconds": graph_load_seconds
    }
    indexes_created = 0

    try:
        with driver.session(database=args.database) as session:
            if args.create_indexes:
                index_start = time.time()
                indexes_created = create_indexes(session)
                timings["indexes_seconds"] = round(time.time() - index_start, 2)
                print(f"  Ensured {indexes_created} indexes")

            # v2.0.0: Load Gate 0 marker for rebuild control
            rebuild_mode = False
            rebuild_scope = {}
            deletion_counts = {}
            if args.gate_marker and args.gate_marker.exists():
                try:
                    with open(args.gate_marker, 'r', encoding='utf-8') as f:
                        gate_marker = json.load(f)
                        rebuild_mode = gate_marker.get('rebuild_mode', False)
                        rebuild_scope = gate_marker.get('rebuild_scope', {})
                except (IOError, json.JSONDecodeError) as e:
                    raise PassENeo4jUpsertError(f"Failed to load Gate 0 marker: {e}")

                # Document-specific cleanup if rebuild enabled for Neo4j
                if rebuild_mode and rebuild_scope.get('neo4j', False):
                    print(f"\n⚠️  Rebuild mode enabled for Neo4j")
                    deletion_counts = clear_document_graph(session, document_id, dry_run=False)
                    total_deleted = sum(deletion_counts.values())
                    if total_deleted > 0:
                        print(f"✓ Cleared {total_deleted} existing nodes for document_id: {document_id}")
                        for label, count in deletion_counts.items():
                            print(f"  {label}: {count}")
                        print()

            # Upsert nodes
            node_start = time.time()
            nodes = graph_data.get("nodes", {})
            upsert_nodes_by_label(
                session,
                "Document",
                "document_id",
                nodes.get("Document", []),
                tracker,
                args.node_batch_size
            )
            upsert_nodes_by_label(
                session,
                "Chunk",
                "chunk_id",
                nodes.get("Chunk", []),
                tracker,
                args.node_batch_size
            )
            upsert_nodes_by_label(
                session,
                "Term",
                "term",
                nodes.get("Term", []),
                tracker,
                args.node_batch_size
            )
            upsert_nodes_by_label(
                session,
                "Category",
                "name",
                nodes.get("Category", []),
                tracker,
                args.node_batch_size
            )
            timings["node_upsert_seconds"] = round(time.time() - node_start, 2)

            # Upsert edges
            edge_start = time.time()
            edges = graph_data.get("edges", {})
            upsert_edges(
                session,
                "CONTAINS",
                "Document",
                "document_id",
                "Chunk",
                "chunk_id",
                edges.get("CONTAINS", []),
                tracker,
                args.edge_batch_size
            )
            upsert_edges(
                session,
                "BELONGS_TO",
                "Chunk",
                "chunk_id",
                "Category",
                "name",
                edges.get("BELONGS_TO", []),
                tracker,
                args.edge_batch_size
            )
            upsert_edges(
                session,
                "MENTIONS",
                "Chunk",
                "chunk_id",
                "Term",
                "term",
                edges.get("MENTIONS", []),
                tracker,
                args.edge_batch_size
            )
            upsert_edges(
                session,
                "SIMILAR_TO",
                "Chunk",
                "chunk_id",
                "Chunk",
                "chunk_id",
                edges.get("SIMILAR_TO", []),
                tracker,
                args.edge_batch_size,
                properties=["similarity"]
            )
            timings["edge_upsert_seconds"] = round(time.time() - edge_start, 2)

    finally:
        driver.close()

    timings["total_seconds"] = round(time.time() - start_time, 2)

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{document_id}_pass_e_manifest.json"

    write_manifest(
        manifest_path,
        document_id,
        args.graph_json,
        graph_statistics,
        tracker,
        timings,
        {
            "host": args.host,
            "port": args.port,
            "database": args.database
        },
        indexes_created
    )

    totals = tracker.as_dict()["totals"]
    print("\nNeo4j upsert complete")
    print(f"  Nodes created: {totals['nodes_created']}")
    print(f"  Nodes matched: {totals['nodes_matched']}")
    print(f"  Relationships created: {totals['relationships_created']}")
    print(f"  Manifest written to: {manifest_path}")
    print(f"  Total time: {timings['total_seconds']}s")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PassENeo4jUpsertError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(130)
