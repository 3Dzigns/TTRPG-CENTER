#!/usr/bin/env python3
"""
pass_e_graph_builder.py - Knowledge Graph Construction (Pass E)
================================================================

Builds knowledge graph structure from Cassandra vectors and Pass C metadata.
Hybrid approach combining structured metadata with optional semantic similarity.

Usage:
  pass_e_graph_builder.py <pass_d_manifest> [options]
  pass_e_graph_builder.py -v | --version
  pass_e_graph_builder.py -? | --help

Arguments:
  pass_d_manifest    Path to Pass D manifest JSON

Options:
  -o, --output DIR          Output directory (default: /Transfer_Station/Pass_E_Out)
  --pass-c-dir DIR          Pass C metadata directory (default: /Transfer_Station/Pass_C_Out)
  --host HOST               Cassandra host (default: n8n_TTRPG_cassandra)
  --port PORT               Cassandra port (default: 9042)
  --keyspace KEYSPACE       Cassandra keyspace (default: ttrpg_vectors)
  --fetch-size N            Cassandra fetch size per page (default: 500)
  --max-retries N           Max Cassandra timeout retries before fallback (default: 3)
  --enable-similarity       Compute SIMILAR_TO edges (default: false)
  --similarity-threshold F  Cosine similarity threshold (default: 0.82)
  --similarity-top-k N      Max similar chunks per chunk (default: 5)
  --dry-run                 Validate inputs without building graph
  -v, --version             Show version
  -?, --help                Show help

Examples:
  # Basic graph building (no similarity edges)
  pass_e_graph_builder.py /Transfer_Station/Pass_D_Out/doc_pass_d_manifest.json

  # With semantic similarity edges
  pass_e_graph_builder.py /Transfer_Station/Pass_D_Out/doc_pass_d_manifest.json \\
    --enable-similarity --similarity-threshold 0.85 --similarity-top-k 3

  # Dry run validation
  pass_e_graph_builder.py /Transfer_Station/Pass_D_Out/doc_pass_d_manifest.json --dry-run

Output Files:
  {document_id}_vectors.json          - Raw vector data from Cassandra
  {document_id}_graph.json            - Graph structure (nodes + edges)
  {document_id}_pass_e_intermediate.json - Combined data for debugging

Version: 1.0.0
Author: n8n TTRPG Center
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from path_utils import resolve_transfer_path

try:
    from cassandra import OperationTimedOut, ReadTimeout
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.query import SimpleStatement
except ImportError:
    print("Error: cassandra-driver not installed. Run: pip install cassandra-driver", file=sys.stderr)
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("Error: numpy not installed. Run: pip install numpy", file=sys.stderr)
    sys.exit(1)


__version__ = "1.0.0"

DEFAULT_OUTPUT_DIR = resolve_transfer_path("Pass_E_Out")
DEFAULT_PASS_C_DIR = resolve_transfer_path("Pass_C_Out")
DEFAULT_CASSANDRA_HOST = "n8n_TTRPG_cassandra"
DEFAULT_CASSANDRA_PORT = 9042
DEFAULT_CASSANDRA_KEYSPACE = "ttrpg_vectors"
DEFAULT_CASSANDRA_FETCH_SIZE = 500
DEFAULT_CASSANDRA_MAX_RETRIES = 3
DEFAULT_SIMILARITY_THRESHOLD = 0.82
DEFAULT_SIMILARITY_TOP_K = 5


class PassEGraphBuilderError(Exception):
    """Base exception for Pass E graph builder errors."""
    pass


class CassandraVectorFetchError(PassEGraphBuilderError):
    """Raised when Cassandra vector retrieval fails after retries."""

    def __init__(self, message: str, attempts: int, last_fetch_size: int):
        super().__init__(message)
        self.attempts = attempts
        self.last_fetch_size = last_fetch_size


def load_pass_d_manifest(manifest_path: Path) -> Dict[str, Any]:
    """
    Load Pass D manifest to extract document_id and Cassandra config.

    Args:
        manifest_path: Path to Pass D manifest JSON

    Returns:
        Manifest dictionary

    Raises:
        PassEGraphBuilderError: If manifest cannot be loaded or is invalid
    """
    if not manifest_path.exists():
        raise PassEGraphBuilderError(f"Pass D manifest not found: {manifest_path}")

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise PassEGraphBuilderError(f"Failed to load manifest: {e}")

    # Validate required fields
    if 'document_id' not in manifest:
        raise PassEGraphBuilderError("Pass D manifest missing 'document_id' field")

    return manifest


def load_pass_c_metadata(document_id: str, pass_c_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Load Pass C metadata file.

    Args:
        document_id: Document identifier
        pass_c_dir: Pass C output directory

    Returns:
        Metadata dictionary or None if not found
    """
    metadata_filename = f"{document_id}_pass_c_metadata.json"
    metadata_path = pass_c_dir / metadata_filename

    if not metadata_path.exists():
        print(f"Warning: Pass C metadata not found: {metadata_filename}", file=sys.stderr)
        return None

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to load Pass C metadata: {e}", file=sys.stderr)
        return None


def connect_cassandra(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    fetch_size: int = DEFAULT_CASSANDRA_FETCH_SIZE
) -> Tuple[Cluster, Any]:
    """
    Connect to Cassandra cluster.

    Args:
        host: Cassandra host
        port: Cassandra port
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Tuple of (cluster, session)

    Raises:
        PassEGraphBuilderError: If connection fails
    """
    try:
        auth_provider = None
        if username and password:
            auth_provider = PlainTextAuthProvider(username=username, password=password)

        cluster = Cluster([host], port=port, auth_provider=auth_provider)
        session = cluster.connect()
        session.default_timeout = 120
        session.default_fetch_size = max(50, fetch_size)
        return cluster, session
    except NoHostAvailable as e:
        raise PassEGraphBuilderError(f"Cannot connect to Cassandra at {host}:{port}: {e}")
    except Exception as e:
        raise PassEGraphBuilderError(f"Cassandra connection failed: {e}")


def query_cassandra_vectors(
    session: Any,
    keyspace: str,
    document_id: str,
    fetch_size: int = DEFAULT_CASSANDRA_FETCH_SIZE,
    max_retries: int = DEFAULT_CASSANDRA_MAX_RETRIES
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Query all vectors for a document from Cassandra in paged batches.

    Args:
        session: Cassandra session
        keyspace: Keyspace name
        document_id: Document identifier
        fetch_size: Page size for Cassandra paging
        max_retries: Maximum retry attempts on timeouts

    Returns:
        Tuple of (vector records, fetch statistics)

    Raises:
        CassandraVectorFetchError: If the query repeatedly times out
        PassEGraphBuilderError: For other query errors
    """
    try:
        session.set_keyspace(keyspace)

        base_query = """
            SELECT document_id, element_id, chunk_index, sub_chunk, source_part,
                   text_content, embedding, element_type, page_number, filename,
                   game_system, publisher, category, embedding_model, created_at
            FROM embeddings
            WHERE document_id = %s
        """

        attempts = 0
        current_fetch_size = max(50, fetch_size)

        while attempts < max_retries:
            attempts += 1
            statement = SimpleStatement(base_query, fetch_size=current_fetch_size)

            try:
                rows = session.execute(statement, [document_id], timeout=120)
                vectors: List[Dict[str, Any]] = []
                total_rows = 0

                for row in rows:
                    total_rows += 1
                    if total_rows % current_fetch_size == 0:
                        print(f"    Cassandra batch fetched: {total_rows} rows so far (fetch_size={current_fetch_size})")

                    vectors.append({
                        'document_id': row.document_id,
                        'element_id': row.element_id,
                        'chunk_index': row.chunk_index,
                        'sub_chunk': row.sub_chunk,
                        'source_part': row.source_part,
                        'text_content': row.text_content,
                        'embedding': list(row.embedding) if row.embedding else [],
                        'element_type': row.element_type,
                        'page_number': row.page_number,
                        'filename': row.filename,
                        'game_system': row.game_system,
                        'publisher': row.publisher,
                        'category': row.category,
                        'embedding_model': row.embedding_model,
                        'created_at': row.created_at.isoformat() if row.created_at else None
                    })

                fetch_stats = {
                    'attempts': attempts,
                    'final_fetch_size': current_fetch_size,
                    'rows': total_rows
                }
                return vectors, fetch_stats

            except (ReadTimeout, OperationTimedOut) as exc:
                print(f"  Warning: Cassandra read timeout on attempt {attempts}/{max_retries}: {exc}", file=sys.stderr)
                if attempts >= max_retries:
                    raise CassandraVectorFetchError(
                        f"Cassandra query timed out after {attempts} attempts",
                        attempts=attempts,
                        last_fetch_size=current_fetch_size
                    )

                current_fetch_size = max(50, current_fetch_size // 2)
                print(f"           Retrying with fetch_size={current_fetch_size}...", file=sys.stderr)
                time.sleep(1)
            except Exception as exc:
                raise PassEGraphBuilderError(f"Failed to query Cassandra: {exc}")

        raise CassandraVectorFetchError(
            f"Cassandra query exhausted {max_retries} attempts without success",
            attempts=max_retries,
            last_fetch_size=current_fetch_size
        )

    except CassandraVectorFetchError:
        raise
    except PassEGraphBuilderError:
        raise
    except Exception as exc:
        raise PassEGraphBuilderError(f"Unexpected Cassandra error: {exc}")


def load_vectors_from_pass_c_chunks(
    document_id: str,
    pass_c_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
    pass_c_metadata: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Load vector-like records from Pass C chunk JSON files as a fallback.

    Args:
        document_id: Document identifier
        pass_c_dir: Directory containing Pass C outputs
        manifest: Optional Pass D manifest for part ordering
        pass_c_metadata: Optional Pass C metadata for defaults

    Returns:
        List of vector records approximated from Pass C chunks
    """
    parts = []
    if manifest and isinstance(manifest, dict):
        parts = manifest.get('parts_detail', [])

    if not parts:
        pattern = f"{document_id}_*_elements.json"
        parts = [
            {'part': idx + 1, 'element_file': path.name}
            for idx, path in enumerate(sorted(pass_c_dir.glob(pattern)))
        ]

    if not parts:
        raise PassEGraphBuilderError(
            f"No Pass C chunk files located for fallback (pattern {document_id}_*_elements.json)"
        )

    default_game_system = None
    default_publisher = None
    if pass_c_metadata:
        extraction_info = pass_c_metadata.get('extraction', {})
        default_game_system = extraction_info.get('system')
        default_publisher = extraction_info.get('publisher')

    embedding_model = None
    if manifest:
        embedding_model = manifest.get('processing', {}).get('embedding_model')

    vectors: List[Dict[str, Any]] = []

    for idx, part_info in enumerate(parts, start=1):
        element_file = part_info.get('element_file')
        if not element_file:
            continue

        chunk_path = pass_c_dir / element_file
        if not chunk_path.exists():
            print(f"  Warning: Pass C chunk file missing for fallback: {element_file}", file=sys.stderr)
            continue

        try:
            with open(chunk_path, 'r', encoding='utf-8') as handle:
                elements = json.load(handle)
        except (json.JSONDecodeError, IOError) as exc:
            print(f"  Warning: Failed to load Pass C chunk file {element_file}: {exc}", file=sys.stderr)
            continue

        print(f"    Fallback loading part {idx}: {element_file} ({len(elements)} elements)")

        for element in elements:
            metadata = element.get('metadata', {}) or {}
            existing_chunk_index = metadata.get('chunk_index')
            chunk_index = existing_chunk_index if existing_chunk_index is not None else len(vectors)

            vectors.append({
                'document_id': document_id,
                'element_id': element.get('element_id'),
                'chunk_index': chunk_index,
                'sub_chunk': metadata.get('sub_chunk', 0),
                'source_part': part_info.get('part', idx),
                'text_content': element.get('text', ''),
                'embedding': element.get('embedding') or [],
                'element_type': element.get('type'),
                'page_number': metadata.get('page_number'),
                'filename': metadata.get('filename'),
                'game_system': metadata.get('game_system') or default_game_system,
                'publisher': metadata.get('publisher') or default_publisher,
                'category': metadata.get('category'),
                'embedding_model': embedding_model,
                'created_at': None,
                'fallback_source': 'pass_c'
            })

    return vectors


def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity (0.0-1.0)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    arr1 = np.array(vec1)
    arr2 = np.array(vec2)

    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(arr1, arr2) / (norm1 * norm2))


def find_similar_chunks(
    vectors: List[Dict[str, Any]],
    threshold: float,
    top_k: int
) -> List[Tuple[str, str, float]]:
    """
    Find semantically similar chunk pairs using cosine similarity.

    Args:
        vectors: List of vector records
        threshold: Minimum similarity threshold
        top_k: Maximum similar chunks per chunk

    Returns:
        List of (chunk_id_1, chunk_id_2, similarity) tuples
    """
    if not vectors:
        return []

    print(f"  Computing pairwise similarities for {len(vectors)} chunks...")
    print(f"  Threshold: {threshold}, Top-K: {top_k}")

    # Build chunk ID -> embedding mapping
    chunk_embeddings = {}
    for vec in vectors:
        chunk_id = f"{vec['element_id']}_{vec['chunk_index']}"
        if vec['embedding']:
            chunk_embeddings[chunk_id] = vec['embedding']

    # Compute similarities
    similarities = []
    chunk_ids = list(chunk_embeddings.keys())

    for i, chunk_id_1 in enumerate(chunk_ids):
        if (i + 1) % 100 == 0:
            print(f"    Processed {i + 1}/{len(chunk_ids)} chunks...")

        chunk_similarities = []

        for j in range(i + 1, len(chunk_ids)):
            chunk_id_2 = chunk_ids[j]

            sim = compute_cosine_similarity(
                chunk_embeddings[chunk_id_1],
                chunk_embeddings[chunk_id_2]
            )

            if sim >= threshold:
                chunk_similarities.append((chunk_id_2, sim))

        # Keep top-K most similar
        chunk_similarities.sort(key=lambda x: x[1], reverse=True)
        for chunk_id_2, sim in chunk_similarities[:top_k]:
            similarities.append((chunk_id_1, chunk_id_2, sim))

    print(f"  Found {len(similarities)} similar pairs")
    return similarities


def build_graph_structure(
    document_id: str,
    vectors: List[Dict[str, Any]],
    pass_c_metadata: Optional[Dict[str, Any]],
    similarities: Optional[List[Tuple[str, str, float]]] = None,
    manifest: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build graph structure with nodes and edges.

    Args:
        document_id: Document identifier
        vectors: List of vector records from Cassandra
        pass_c_metadata: Pass C metadata (categories, terms)
        similarities: Optional list of similar chunk pairs
        manifest: Optional Pass D manifest for supplemental metadata

    Returns:
        Graph structure dictionary
    """
    print("  Building graph nodes...")

    def prune_none(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove keys with None values to keep payload concise."""
        return {key: value for key, value in data.items() if value is not None}

    graph = {
        'document_id': document_id,
        'nodes': {
            'Document': [],
            'Chunk': [],
            'Term': [],
            'Category': []
        },
        'edges': {
            'CONTAINS': [],
            'BELONGS_TO': [],
            'MENTIONS': [],
            'SIMILAR_TO': []
        }
    }

    categories: Dict[str, Any] = {}
    terms: List[Dict[str, Any]] = []
    game_system: Optional[str] = None
    publisher: Optional[str] = None
    document_title: Optional[str] = None
    page_count: Optional[int] = None

    if pass_c_metadata:
        categories = pass_c_metadata.get('categories', {})
        terms = pass_c_metadata.get('terms', [])
        extraction = pass_c_metadata.get('extraction', {})
        game_system = extraction.get('system') or extraction.get('game_system')
        publisher = extraction.get('publisher')

        document_meta = pass_c_metadata.get('document', {})
        document_title = document_meta.get('title') or document_meta.get('name')
        page_count = document_meta.get('page_count')

        if not game_system:
            game_system = document_meta.get('game_system')
        if not publisher:
            publisher = document_meta.get('publisher')

    if manifest:
        manifest_doc = manifest.get('document', {})
        document_title = (
            manifest.get('document_title')
            or manifest_doc.get('title')
            or document_title
        )
        page_count = (
            manifest_doc.get('page_count')
            or manifest.get('page_count')
            or page_count
        )

        game_system = (
            manifest_doc.get('game_system')
            or manifest.get('game_system')
            or game_system
        )
        publisher = (
            manifest_doc.get('publisher')
            or manifest.get('publisher')
            or publisher
        )

    document_node = prune_none({
        'document_id': document_id,
        'title': document_title,
        'game_system': game_system,
        'publisher': publisher,
        'page_count': page_count,
        'total_chunks': len(vectors)
    })
    graph['nodes']['Document'].append(document_node)

    belongs_to_edges = set()
    lower_vectors: List[Tuple[str, str]] = []
    for vec in vectors:
        base_chunk_id = f"{vec['element_id']}_{vec['chunk_index']}"
        sub_chunk = vec.get('sub_chunk')
        chunk_id = f"{base_chunk_id}_{sub_chunk}" if sub_chunk is not None else base_chunk_id

        chunk_node = prune_none({
            'chunk_id': chunk_id,
            'element_id': vec.get('element_id'),
            'chunk_index': vec.get('chunk_index'),
            'sub_chunk': sub_chunk,
            'text_content': vec.get('text_content'),
            'element_type': vec.get('element_type'),
            'page_number': vec.get('page_number'),
            'category': vec.get('category'),
            'source_part': vec.get('source_part'),
            'embedding_model': vec.get('embedding_model'),
            'created_at': vec.get('created_at'),
            'filename': vec.get('filename')
        })
        graph['nodes']['Chunk'].append(chunk_node)

        graph['edges']['CONTAINS'].append({
            'from': document_id,
            'to': chunk_id
        })

        category = vec.get('category')
        if category:
            edge_key = (chunk_id, category)
            if edge_key not in belongs_to_edges:
                graph['edges']['BELONGS_TO'].append({
                    'from': chunk_id,
                    'to': category
                })
                belongs_to_edges.add(edge_key)

        lower_vectors.append((
            chunk_id,
            (vec.get('text_content') or '').lower()
        ))

    for category_name, items in categories.items():
        graph['nodes']['Category'].append({
            'name': category_name,
            'item_count': len(items)
        })

    print("  Creating term nodes and MENTIONS edges...")
    seen_terms = set()
    mention_edges = set()

    for term_data in terms:
        term_text = term_data.get('term', '')
        if not term_text:
            continue

        term_key = term_text.lower()
        if term_key not in seen_terms:
            graph['nodes']['Term'].append(prune_none({
                'term': term_text,
                'category': term_data.get('category'),
                'page_references': term_data.get('page_references', [])
            }))
            seen_terms.add(term_key)

        for chunk_id, text_content_lower in lower_vectors:
            if term_key in text_content_lower:
                edge_key = (chunk_id, term_text)
                if edge_key not in mention_edges:
                    graph['edges']['MENTIONS'].append({
                        'from': chunk_id,
                        'to': term_text
                    })
                    mention_edges.add(edge_key)

    if similarities:
        print(f"  Adding {len(similarities)} SIMILAR_TO edges...")
        similar_edges = set()
        for chunk_id_1, chunk_id_2, sim in similarities:
            similarity_score = round(sim, 4)

            forward_key = (chunk_id_1, chunk_id_2)
            if forward_key not in similar_edges:
                graph['edges']['SIMILAR_TO'].append({
                    'from': chunk_id_1,
                    'to': chunk_id_2,
                    'similarity': similarity_score
                })
                similar_edges.add(forward_key)

            reverse_key = (chunk_id_2, chunk_id_1)
            if reverse_key not in similar_edges:
                graph['edges']['SIMILAR_TO'].append({
                    'from': chunk_id_2,
                    'to': chunk_id_1,
                    'similarity': similarity_score
                })
                similar_edges.add(reverse_key)

    node_counts = {node_type: len(entries) for node_type, entries in graph['nodes'].items()}
    edge_counts = {edge_type: len(entries) for edge_type, entries in graph['edges'].items()}

    graph['statistics'] = {
        'nodes_by_type': node_counts,
        'edges_by_type': edge_counts,
        'total_nodes': sum(node_counts.values()),
        'total_edges': sum(edge_counts.values())
    }

    print("  Graph construction complete")
    print(f"    Nodes: Document={node_counts['Document']}, "
          f"Chunk={node_counts['Chunk']}, "
          f"Term={node_counts['Term']}, "
          f"Category={node_counts['Category']}")
    print(f"    Edges: CONTAINS={edge_counts['CONTAINS']}, "
          f"BELONGS_TO={edge_counts['BELONGS_TO']}, "
          f"MENTIONS={edge_counts['MENTIONS']}, "
          f"SIMILAR_TO={edge_counts['SIMILAR_TO']}")

    return graph


def write_graph_outputs(
    graph: Dict[str, Any],
    vectors: List[Dict[str, Any]],
    output_dir: Path,
    document_id: str,
    timings: Dict[str, Any],
    vector_source: str
) -> Dict[str, Path]:
    """
    Write graph output files.

    Args:
        graph: Graph structure
        vectors: Raw vector data
        output_dir: Output directory
        document_id: Document identifier
        timings: Timing statistics and metadata
        vector_source: Source of vector data ('cassandra' or fallback label)

    Returns:
        Dictionary of output file paths

    Raises:
        PassEGraphBuilderError: If writing fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write vectors.json
    vectors_file = output_dir / f"{document_id}_vectors.json"
    try:
        with open(vectors_file, 'w', encoding='utf-8') as f:
            json.dump(vectors, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise PassEGraphBuilderError(f"Failed to write vectors file: {e}")

    # Write graph.json
    graph_file = output_dir / f"{document_id}_graph.json"
    try:
        with open(graph_file, 'w', encoding='utf-8') as f:
            json.dump(graph, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise PassEGraphBuilderError(f"Failed to write graph file: {e}")

    # Write intermediate.json (combined data for debugging)
    intermediate_file = output_dir / f"{document_id}_pass_e_intermediate.json"
    intermediate_data = {
        'document_id': document_id,
        'graph': graph,
        'vectors_count': len(vectors),
        'graph_statistics': graph.get('statistics', {}),
        'timings': timings,
        'vector_source': vector_source,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    try:
        with open(intermediate_file, 'w', encoding='utf-8') as f:
            json.dump(intermediate_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise PassEGraphBuilderError(f"Failed to write intermediate file: {e}")

    return {
        'vectors': vectors_file,
        'graph': graph_file,
        'intermediate': intermediate_file
    }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Build knowledge graph from Pass D vectors (Pass E)',
        add_help=False
    )

    parser.add_argument(
        'pass_d_manifest',
        type=Path,
        help='Path to Pass D manifest JSON'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})'
    )
    parser.add_argument(
        '--pass-c-dir',
        type=Path,
        default=DEFAULT_PASS_C_DIR,
        help=f'Pass C metadata directory (default: {DEFAULT_PASS_C_DIR})'
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
        '--fetch-size',
        type=int,
        default=DEFAULT_CASSANDRA_FETCH_SIZE,
        help=f'Cassandra fetch size per page (default: {DEFAULT_CASSANDRA_FETCH_SIZE})'
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=DEFAULT_CASSANDRA_MAX_RETRIES,
        help=f'Max retry attempts on Cassandra timeouts (default: {DEFAULT_CASSANDRA_MAX_RETRIES})'
    )
    parser.add_argument(
        '--enable-similarity',
        action='store_true',
        help='Compute SIMILAR_TO edges (default: false)'
    )
    parser.add_argument(
        '--similarity-threshold',
        type=float,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help=f'Cosine similarity threshold (default: {DEFAULT_SIMILARITY_THRESHOLD})'
    )
    parser.add_argument(
        '--similarity-top-k',
        type=int,
        default=DEFAULT_SIMILARITY_TOP_K,
        help=f'Max similar chunks per chunk (default: {DEFAULT_SIMILARITY_TOP_K})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate inputs without building graph'
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    parser.add_argument(
        '-?', '--help',
        action='help',
        help='Show this help message and exit'
    )

    return parser.parse_args()


def main() -> int:
    """Main execution function."""
    args = parse_args()

    timings = {}
    cluster: Optional[Cluster] = None
    session = None

    try:
        # Load Pass D manifest
        print(f"Loading Pass D manifest from {args.pass_d_manifest.name}...")
        manifest = load_pass_d_manifest(args.pass_d_manifest)
        document_id = manifest['document_id']
        print(f"  Document: {document_id}")

        cassandra_cfg = manifest.get('cassandra') or manifest.get('cassandra_config') or {}
        cassandra_host = cassandra_cfg.get('host', args.host)
        cassandra_port = cassandra_cfg.get('port', args.port)
        cassandra_keyspace = cassandra_cfg.get('keyspace', args.keyspace)
        cassandra_username = (
            cassandra_cfg.get('username')
            or manifest.get('cassandra_username')
        )
        cassandra_password = (
            cassandra_cfg.get('password')
            or manifest.get('cassandra_password')
        )

        try:
            cassandra_port = int(cassandra_port)
        except (TypeError, ValueError):
            cassandra_port = args.port

        cassandra_keyspace = cassandra_keyspace or args.keyspace

        # Load Pass C metadata
        print(f"\nLoading Pass C metadata from {args.pass_c_dir}...")
        pass_c_metadata = load_pass_c_metadata(document_id, args.pass_c_dir)
        if pass_c_metadata:
            stats = pass_c_metadata.get('statistics', {})
            print(f"  Loaded metadata: {stats.get('unique_terms', 0)} terms, "
                  f"{stats.get('unique_categories', 0)} categories")
        else:
            print("  No Pass C metadata found (graph will have fewer nodes)")

        if args.dry_run:
            print("\n--dry-run mode: Validation complete, no graph built")
            return 0

        fetch_size = max(1, args.fetch_size)
        max_retries = max(1, args.max_retries)

        # Connect to Cassandra
        print(f"\nConnecting to Cassandra at {cassandra_host}:{cassandra_port} (keyspace: {cassandra_keyspace})...")
        start_time = time.time()
        cluster, session = connect_cassandra(
            cassandra_host,
            cassandra_port,
            username=cassandra_username,
            password=cassandra_password,
            fetch_size=fetch_size
        )
        print(f"  Connected (session fetch_size={session.default_fetch_size})")

        vectors: List[Dict[str, Any]] = []
        vector_source = "cassandra"

        # Query vectors
        print(f"\nQuerying vectors from keyspace '{cassandra_keyspace}'...")
        query_start = time.time()
        try:
            vectors, fetch_stats = query_cassandra_vectors(
                session,
                cassandra_keyspace,
                document_id,
                fetch_size=fetch_size,
                max_retries=max_retries
            )
            fetch_duration = round(time.time() - query_start, 2)
            timings['vector_fetch_seconds'] = fetch_duration
            timings['cassandra_query_seconds'] = fetch_duration
            timings['vector_fetch_attempts'] = fetch_stats['attempts']
            timings['vector_fetch_final_batch_size'] = fetch_stats['final_fetch_size']
            timings['vector_fetch_rows'] = fetch_stats['rows']
            print(
                f"  Retrieved {len(vectors)} vectors in {fetch_duration}s "
                f"(attempts={fetch_stats['attempts']}, fetch_size={fetch_stats['final_fetch_size']})"
            )
        except CassandraVectorFetchError as exc:
            timings['cassandra_query_seconds'] = round(time.time() - query_start, 2)
            timings['vector_fetch_attempts'] = exc.attempts
            timings['vector_fetch_final_batch_size'] = exc.last_fetch_size
            print(
                f"  Cassandra query failed after {exc.attempts} attempts "
                f"({timings['cassandra_query_seconds']}s): {exc}",
                file=sys.stderr
            )
            print("  Falling back to Pass C chunk JSON...", file=sys.stderr)
            vector_source = "pass_c_chunks"
            fallback_start = time.time()
            vectors = load_vectors_from_pass_c_chunks(
                document_id,
                args.pass_c_dir,
                manifest=manifest,
                pass_c_metadata=pass_c_metadata
            )
            fallback_duration = round(time.time() - fallback_start, 2)
            timings['fallback_seconds'] = fallback_duration
            timings['vector_fetch_seconds'] = timings.get('cassandra_query_seconds', 0.0) + fallback_duration
            timings['vector_fetch_rows'] = len(vectors)
            print(f"  Loaded {len(vectors)} fallback chunk records in {fallback_duration}s")

        timings['vector_source'] = vector_source

        if not vectors:
            print("  Warning: No vector records available for graph construction.", file=sys.stderr)

        # Compute similarities if enabled
        similarities = None
        if args.enable_similarity and vector_source == "cassandra":
            print(f"\nComputing semantic similarities...")
            sim_start = time.time()
            similarities = find_similar_chunks(
                vectors,
                args.similarity_threshold,
                args.similarity_top_k
            )
            timings['similarity_compute_seconds'] = round(time.time() - sim_start, 2)
            print(f"  Found {len(similarities)} similar pairs ({timings['similarity_compute_seconds']}s)")
        elif args.enable_similarity:
            print("  Similarity computation skipped: fallback vector data lacks embeddings.", file=sys.stderr)

        # Build graph
        print(f"\nBuilding graph structure...")
        graph_start = time.time()
        graph = build_graph_structure(
            document_id,
            vectors,
            pass_c_metadata,
            similarities,
            manifest=manifest
        )
        timings['graph_build_seconds'] = round(time.time() - graph_start, 2)

        graph_metadata = graph.setdefault('metadata', {})
        graph_metadata['vector_source'] = vector_source
        graph_metadata['vector_count'] = len(vectors)
        graph_metadata['vector_fetch_attempts'] = timings.get('vector_fetch_attempts')
        graph_metadata['fallback_used'] = vector_source != "cassandra"

        # Write outputs
        print(f"\nWriting output files to {args.output}...")
        output_files = write_graph_outputs(
            graph,
            vectors,
            args.output,
            document_id,
            timings,
            vector_source
        )

        timings['total_seconds'] = round(time.time() - start_time, 2)

        # Success summary
        stats = graph.get('statistics', {})
        total_nodes = stats.get('total_nodes') or sum(len(nodes) for nodes in graph['nodes'].values())
        total_edges = stats.get('total_edges') or sum(len(edges) for edges in graph['edges'].values())

        print("\nPass E graph building complete")
        print(f"  Document: {document_id}")
        print(f"  Vectors: {len(vectors)}")
        print(f"  Vector Source: {vector_source}")
        print(f"  Nodes: {total_nodes}")
        print(f"  Edges: {total_edges}")
        print(f"  Time: {timings['total_seconds']}s")
        print(f"  Outputs:")
        print(f"    - {output_files['vectors'].name}")
        print(f"    - {output_files['graph'].name}")
        print(f"    - {output_files['intermediate'].name}")

        return 0

    except PassEGraphBuilderError as e:
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
    finally:
        if session is not None:
            try:
                session.shutdown()
            except Exception:
                pass
        if cluster is not None:
            try:
                cluster.shutdown()
            except Exception:
                pass


if __name__ == '__main__':
    sys.exit(main())

