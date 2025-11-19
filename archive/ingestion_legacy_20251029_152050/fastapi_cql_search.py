#!/usr/bin/env python3
"""
fastapi_cql_search.py - FastAPI Vector Search Service for Cassandra 5
======================================================================

REST API service for Approximate Nearest Neighbor (ANN) vector search with
metadata filtering using Cassandra 5 native vector types and SAI indexes.

Features:
- ANN search with ORDER BY vector ANN OF ? syntax
- Metadata filtering (system, source, tag)
- Cosine similarity scoring via similarity_cosine()
- Dynamic query construction based on filters
- Health check and metrics endpoints

Usage:
  # Development
  uvicorn fastapi_cql_search:app --host 0.0.0.0 --port 8000 --reload

  # Production
  uvicorn fastapi_cql_search:app --host 0.0.0.0 --port 8000 --workers 4

  # Docker
  docker exec -it n8n_TTRPG_ingestion_engine python3 /app/search/fastapi_cql_search.py

API Endpoints:
  POST /search         - Vector similarity search with filters
  GET  /health         - Health check
  GET  /metrics        - Query statistics

Example Request:
  curl -X POST http://localhost:8000/search \
    -H "Content-Type: application/json" \
    -d '{
      "vector": [0.123, -0.456, ...],
      "top_k": 5,
      "system": "D&D 5e",
      "source": "Player'\''s Handbook",
      "tag": "spell"
    }'

Version: 1.0.0
Author: n8n TTRPG Center
"""

import os
import sys
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# Cassandra driver
try:
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.query import SimpleStatement, PreparedStatement
except ImportError:
    print("Error: cassandra-driver not installed. Run: pip install cassandra-driver", file=sys.stderr)
    sys.exit(1)


__version__ = "1.0.0"

# Configuration from environment variables
CASSANDRA_HOST = os.getenv("CASSANDRA_HOST", "n8n_TTRPG_cassandra")
CASSANDRA_PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "ttrpg_vectors")
EMBED_DIM = 1536  # OpenAI text-embedding-3-small

# FastAPI app
app = FastAPI(
    title="TTRPG Vector Search API",
    description="Cassandra 5 Vector Search with ANN and Metadata Filters",
    version=__version__
)

# Global Cassandra session (initialized on startup)
cassandra_session = None
cassandra_cluster = None

# Query statistics
query_stats = {
    "total_queries": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "avg_results_per_query": 0.0,
    "last_query_time": None
}


# Pydantic models for request/response
class SearchRequest(BaseModel):
    """Request model for vector search endpoint."""
    vector: List[float] = Field(
        ...,
        description="Embedding vector (1536 dimensions for text-embedding-3-small)"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of results to return (1-100)"
    )
    system: Optional[str] = Field(
        default=None,
        description="Filter by game system (e.g., 'D&D 5e', 'Pathfinder 2e')"
    )
    source: Optional[str] = Field(
        default=None,
        description="Filter by source book/module (e.g., 'Player's Handbook')"
    )
    tag: Optional[str] = Field(
        default=None,
        description="Filter by tag (e.g., 'spell', 'monster', 'magic-item')"
    )

    @field_validator("vector")
    @classmethod
    def validate_vector_dimension(cls, v: List[float]) -> List[float]:
        """Validate vector has correct dimension."""
        if len(v) != EMBED_DIM:
            raise ValueError(f"Vector must have {EMBED_DIM} dimensions, got {len(v)}")
        return v


class SearchResult(BaseModel):
    """Model for individual search result."""
    document_id: str
    element_id: str
    chunk_index: int
    text: str
    score: float = Field(description="Cosine similarity score (-1.0 to 1.0)")


class SearchResponse(BaseModel):
    """Response model for vector search endpoint."""
    results: List[SearchResult]
    query_time_ms: float
    total_results: int
    filters_applied: Dict[str, Any]


# Cassandra connection lifecycle
@app.on_event("startup")
async def startup_event():
    """Initialize Cassandra connection on startup."""
    global cassandra_cluster, cassandra_session

    try:
        print(f"Connecting to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}...")
        cassandra_cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        cassandra_session = cassandra_cluster.connect(CASSANDRA_KEYSPACE)
        print(f"✓ Connected to Cassandra keyspace: {CASSANDRA_KEYSPACE}")

    except NoHostAvailable as e:
        print(f"✗ Failed to connect to Cassandra: {e}", file=sys.stderr)
        print("Ensure Cassandra container is running and healthy")
        raise

    except Exception as e:
        print(f"✗ Unexpected error during startup: {e}", file=sys.stderr)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup Cassandra connection on shutdown."""
    global cassandra_cluster, cassandra_session

    if cassandra_session:
        cassandra_session.shutdown()
    if cassandra_cluster:
        cassandra_cluster.shutdown()
    print("✓ Cassandra connection closed")


# API endpoints
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.

    Returns service status and Cassandra connectivity.
    """
    if cassandra_session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cassandra session not initialized"
        )

    try:
        # Test query to verify connection
        cassandra_session.execute("SELECT now() FROM system.local", timeout=5)
        return {
            "status": "healthy",
            "cassandra": "connected",
            "keyspace": CASSANDRA_KEYSPACE,
            "version": __version__,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cassandra health check failed: {str(e)}"
        )


@app.get("/metrics")
async def get_metrics():
    """
    Get query statistics and metrics.

    Returns aggregated query statistics for monitoring.
    """
    return {
        "query_stats": query_stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    """
    Perform ANN vector search with optional metadata filters.

    Uses Cassandra 5 SAI ANN index with cosine similarity.
    Filters are applied before ANN search for efficient retrieval.

    Args:
        req: SearchRequest with vector and optional filters

    Returns:
        SearchResponse with matching results and metadata

    Raises:
        HTTPException: If search fails or session unavailable
    """
    if cassandra_session is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cassandra session not initialized"
        )

    start_time = datetime.utcnow()

    # Build dynamic CQL query with filters
    filters = []
    params = []
    filters_applied = {}

    # Add metadata filters
    if req.system:
        filters.append("system = ?")
        params.append(req.system)
        filters_applied["system"] = req.system

    if req.source:
        filters.append("source = ?")
        params.append(req.source)
        filters_applied["source"] = req.source

    if req.tag:
        filters.append("tags CONTAINS ?")
        params.append(req.tag)
        filters_applied["tag"] = req.tag

    # Construct WHERE clause
    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    # Build complete CQL query with ANN search
    # Note: Vector parameter appears twice (similarity calculation + ANN ordering)
    cql = f'''
        SELECT document_id, element_id, chunk_index, text,
               similarity_cosine(vector, ?) AS score
        FROM embeddings
        {where_clause}
        ORDER BY vector ANN OF ?
        LIMIT ?
    '''

    # Prepare parameters: [vector_for_similarity] + filters + [vector_for_ann, limit]
    query_params = [req.vector] + params + [req.vector, req.top_k]

    try:
        # Execute query
        rows = cassandra_session.execute(cql, query_params, timeout=10)

        # Convert results
        results = [
            SearchResult(
                document_id=row.document_id,
                element_id=row.element_id,
                chunk_index=row.chunk_index,
                text=row.text,
                score=float(row.score)
            )
            for row in rows
        ]

        # Update statistics
        query_stats["total_queries"] += 1
        query_stats["successful_queries"] += 1
        query_stats["last_query_time"] = datetime.utcnow().isoformat()

        if query_stats["total_queries"] > 0:
            # Running average of results per query
            total_results_so_far = (
                query_stats["avg_results_per_query"] * (query_stats["successful_queries"] - 1)
                + len(results)
            )
            query_stats["avg_results_per_query"] = (
                total_results_so_far / query_stats["successful_queries"]
            )

        # Calculate query time
        query_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return SearchResponse(
            results=results,
            query_time_ms=round(query_time_ms, 2),
            total_results=len(results),
            filters_applied=filters_applied
        )

    except Exception as e:
        query_stats["total_queries"] += 1
        query_stats["failed_queries"] += 1
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search query failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "TTRPG Vector Search API",
        "version": __version__,
        "endpoints": {
            "search": "POST /search - Vector similarity search",
            "health": "GET /health - Health check",
            "metrics": "GET /metrics - Query statistics",
            "docs": "GET /docs - OpenAPI documentation"
        },
        "cassandra": {
            "host": CASSANDRA_HOST,
            "port": CASSANDRA_PORT,
            "keyspace": CASSANDRA_KEYSPACE
        }
    }


# CLI runner for development
if __name__ == "__main__":
    import uvicorn

    print("Starting TTRPG Vector Search API...")
    print(f"Version: {__version__}")
    print(f"Cassandra: {CASSANDRA_HOST}:{CASSANDRA_PORT}/{CASSANDRA_KEYSPACE}\n")

    uvicorn.run(
        "fastapi_cql_search:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
