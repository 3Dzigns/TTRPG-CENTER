# Cassandra 5 Native Vector Implementation Guide

## Overview

This implementation migrates from Cassandra `list<float>` to native `vector<float, 1536>` type with Storage-Attached Indexing (SAI) for improved vector search performance and metadata filtering capabilities.

**Key Benefits:**
- Native vector type support (Cassandra 5.0+)
- SAI ANN index for fast approximate nearest neighbor search
- Metadata filtering via SAI indexes (no ALLOW FILTERING overhead)
- Simplified schema optimized for retrieval performance
- LangFlow CassIO and n8n integration ready

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion Pipeline                        │
├─────────────────────────────────────────────────────────────┤
│  Pass D (pass_d_hayhooks.py)                                │
│    ↓                                                         │
│  Generate OpenAI embeddings (1536 dims)                     │
│    ↓                                                         │
│  Store in Cassandra 5 (vector<float, 1536>)                │
│    • System, Source, Section metadata                       │
│    • Tags for flexible filtering                            │
│    • SAI indexes for efficient queries                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Query Interfaces                          │
├─────────────────────────────────────────────────────────────┤
│  1. FastAPI Search Service (search/fastapi_cql_search.py)  │
│     • REST endpoint for n8n integration                     │
│     • ANN search with ORDER BY vector ANN OF ?             │
│     • Dynamic metadata filtering                            │
│                                                              │
│  2. LangFlow CassIO Integration                             │
│     • Visual workflow builder                               │
│     • CassIO library for vector operations                  │
│     • Metadata filter support                               │
│                                                              │
│  3. Direct CQL Queries                                       │
│     • SELECT with similarity_cosine() function              │
│     • Combined ANN + filter queries                         │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Files

### 1. Schema Definition
**File:** `cql/01_vectors_schema.cql`

Creates Cassandra 5 keyspace and table with native vector type:
```sql
CREATE TABLE embeddings (
  document_id text,
  element_id text,
  chunk_index int,
  text text,
  system text,
  source text,
  section text,
  tags set<text>,
  vector vector<float, 1536>,
  updated_at timestamp,
  PRIMARY KEY ((document_id), element_id, chunk_index)
);
```

**SAI Indexes:**
- `embeddings_system_idx` - Filter by game system
- `embeddings_source_idx` - Filter by source book
- `embeddings_section_idx` - Filter by document section
- `embeddings_tags_idx` - Filter by tags (set values)
- `embeddings_vector_ann` - ANN search with cosine similarity

### 2. Ingestion Module
**File:** `ingestion/upsert_embeddings.py`

Standalone module for vector upsert operations:
- Vector dimension validation (1536)
- Prepared statement pattern for performance
- Batch upsert with progress tracking
- Document cleanup for rebuild operations

**Usage:**
```python
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
stats = batch_upsert_embeddings(session, rows, batch_size=100)
```

### 3. FastAPI Search Service
**File:** `search/fastapi_cql_search.py`

REST API for vector search with metadata filtering:

**Endpoints:**
- `POST /search` - Vector similarity search
- `GET /health` - Health check
- `GET /metrics` - Query statistics

**Example Request:**
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.123, -0.456, ...],
    "top_k": 5,
    "system": "D&D 5e",
    "source": "Player'\''s Handbook",
    "tag": "spell"
  }'
```

**Run Service:**
```bash
# Development
docker exec -it n8n_TTRPG_ingestion_engine \
  python3 /app/search/fastapi_cql_search.py

# Production (in container startup)
uvicorn fastapi_cql_search:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Integration with Pass D
**File:** `ingestion/pass_d_hayhooks.py` (updated)

Modified functions:
- `create_cassandra_schema()` - Creates Cassandra 5 schema with native vector type and SAI indexes
- `store_embeddings_cassandra()` - Maps chunk data to new simplified schema

**Changes:**
- Uses `vector<float, 1536>` instead of `list<float>`
- Maps metadata: system (game system), source (filename), section (element_type), tags (derived)
- Automatic tag generation from element_type, category, and publisher

### 5. Smoke Test
**File:** `tests/smoke_vector_ingest_and_search.py`

End-to-end validation:
1. Schema verification
2. Vector ingestion (single + batch)
3. ANN search (unfiltered)
4. Filtered search (system, source, tag, combinations)
5. Cleanup

**Run Test:**
```bash
# Docker execution
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/tests/smoke_vector_ingest_and_search.py

# Skip cleanup (leave test data)
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/tests/smoke_vector_ingest_and_search.py --no-cleanup
```

### 6. LangFlow Demo
**File:** `langflow/cassio_vector_search_demo.json`

Visual flow demonstrating:
- CassIO connection to Cassandra 5
- OpenAI embeddings generation
- ANN search with metadata filters
- Result display

**Configuration:**
- Contact points: `n8n_TTRPG_cassandra`
- Keyspace: `ttrpg_vectors`
- Table: `embeddings`
- Vector dimension: 1536

## Deployment Steps

### Step 1: Apply Schema
```bash
# Connect to Cassandra container
docker exec -it n8n_TTRPG_cassandra cqlsh

# Apply schema (from within cqlsh)
SOURCE '/path/to/cql/01_vectors_schema.cql';

# Or from outside container
docker exec -i n8n_TTRPG_cassandra cqlsh < cql/01_vectors_schema.cql
```

### Step 2: Migrate Existing Data (Optional)
If you have existing embeddings in old schema:

```bash
# Backup existing data
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/scripts/db_manager.py --summarize --db cassandra

# Clear old embeddings
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/scripts/db_manager.py --clear --db cassandra --force

# Re-ingest documents (will use new schema)
# Process documents through Pass D pipeline
```

### Step 3: Update Dependencies
```bash
# Rebuild ingestion container with FastAPI dependencies
docker compose -f docker-compose-n8n_TTRPG.yml down ingestion_engine
docker compose -f docker-compose-n8n_TTRPG.yml up -d ingestion_engine

# Verify installation
docker exec n8n_TTRPG_ingestion_engine pip list | grep -E "(fastapi|uvicorn|pydantic)"
```

### Step 4: Run Smoke Test
```bash
docker exec n8n_TTRPG_ingestion_engine \
  python3 /app/tests/smoke_vector_ingest_and_search.py
```

Expected output:
```
=== Test Summary ===
Schema Verification........................ ✓ PASS
Vector Ingestion........................... ✓ PASS
ANN Search................................. ✓ PASS
Filtered Search............................ ✓ PASS
Cleanup.................................... ✓ PASS
Results: 5/5 tests passed
```

### Step 5: Deploy FastAPI Search Service
```bash
# Option 1: Run manually in container
docker exec -d n8n_TTRPG_ingestion_engine \
  uvicorn search.fastapi_cql_search:app --host 0.0.0.0 --port 8000

# Option 2: Add to docker-compose startup command
# (Modify docker-compose-n8n_TTRPG.yml ingestion_engine service)

# Test health endpoint
curl http://localhost:9009/health
```

### Step 6: Configure LangFlow (Optional)
1. Import `langflow/cassio_vector_search_demo.json` into LangFlow UI
2. Update Cassandra connection settings if needed
3. Set `OPENAI_API_KEY` environment variable in LangFlow container
4. Test with sample queries

## Query Examples

### CQL Direct Queries

**Basic ANN Search:**
```sql
SELECT document_id, element_id, text,
       similarity_cosine(vector, ?) AS score
FROM ttrpg_vectors.embeddings
ORDER BY vector ANN OF ?
LIMIT 5;
```

**Filtered by System:**
```sql
SELECT document_id, element_id, text,
       similarity_cosine(vector, ?) AS score
FROM ttrpg_vectors.embeddings
WHERE system = 'D&D 5e'
ORDER BY vector ANN OF ?
LIMIT 5;
```

**Multiple Filters:**
```sql
SELECT document_id, element_id, text,
       similarity_cosine(vector, ?) AS score
FROM ttrpg_vectors.embeddings
WHERE system = 'D&D 5e' AND tags CONTAINS 'spell'
ORDER BY vector ANN OF ?
LIMIT 5;
```

### Python Examples

**Using upsert_embeddings Module:**
```python
from cassandra.cluster import Cluster
from upsert_embeddings import upsert_embedding

cluster = Cluster(['n8n_TTRPG_cassandra'], port=9042)
session = cluster.connect()

row = {
    "document_id": "phb_2024",
    "element_id": "spell_fireball",
    "chunk_index": 0,
    "text": "Fireball: 3rd-level evocation spell...",
    "system": "D&D 5e",
    "source": "Player's Handbook",
    "section": "Chapter 11: Spells",
    "tags": ["spell", "evocation", "fire", "damage"],
    "vector": openai_embedding  # 1536 floats
}

upsert_embedding(session, row, keyspace="ttrpg_vectors")
```

**Using FastAPI Client:**
```python
import requests

response = requests.post(
    "http://localhost:9009/search",
    json={
        "vector": query_embedding,
        "top_k": 5,
        "system": "D&D 5e",
        "tag": "spell"
    }
)

results = response.json()
for result in results["results"]:
    print(f"Score: {result['score']:.4f}")
    print(f"Text: {result['text']}\n")
```

## Performance Considerations

### SAI ANN Index
- **Approximate Results**: ANN provides fast approximate results, not exact nearest neighbors
- **Optimal for Large Datasets**: Performance advantage grows with dataset size
- **Cosine Similarity**: Scores range from -1.0 to 1.0, higher = more similar
- **LIMIT Clause**: Always use LIMIT to cap result set size

### Metadata Filtering
- **SAI Indexes**: Enable efficient filtering without ALLOW FILTERING overhead
- **Filter Before ANN**: Filters applied before vector search for best performance
- **Set Operations**: `tags CONTAINS ?` efficiently searches set<text> columns
- **Combine Filters**: Use AND for intersection, multiple indexes work together

### Batch Operations
- **Prepared Statements**: Reuse prepared statements for multiple inserts
- **Batch Size**: Default 100 rows per batch, tune based on network/memory
- **Parallel Processing**: Use multiple connections for concurrent ingestion

## Troubleshooting

### Schema Creation Fails
```
Error: vector type not supported
```
**Solution:** Verify Cassandra 5.0+ is running:
```bash
docker exec n8n_TTRPG_cassandra nodetool version
```

### ANN Search Returns No Results
```
Empty result set from ANN query
```
**Checks:**
1. Verify embeddings exist: `SELECT COUNT(*) FROM ttrpg_vectors.embeddings;`
2. Check index status: `SELECT index_name FROM system_schema.indexes WHERE table_name = 'embeddings';`
3. Validate vector dimension: `SELECT vector FROM embeddings LIMIT 1;` (should show 1536 elements)

### Dimension Mismatch Error
```
EmbeddingUpsertError: Vector dimension mismatch: expected 1536, got 768
```
**Solution:** Ensure using `text-embedding-3-small` (1536 dims), not `text-embedding-ada-002` (1536) or older models (768)

### Performance Degradation
- **Check Compaction**: `nodetool compactionstats`
- **Monitor GC**: `nodetool gcstats`
- **Verify Indexes**: Indexes may need time to build after bulk inserts
- **Tune Batch Size**: Reduce batch size if memory constrained

## Migration from Old Schema

### Comparison

| Feature | Old Schema (list<float>) | New Schema (vector<float, 1536>) |
|---------|-------------------------|-----------------------------------|
| Vector Type | `list<float>` | `vector<float, 1536>` |
| Search Method | Manual cosine calculation | SAI ANN index |
| Metadata Filter | `ALLOW FILTERING` required | SAI indexes (no overhead) |
| Query Syntax | Custom similarity logic | `ORDER BY vector ANN OF ?` |
| Performance | Linear scan for search | Approximate nearest neighbor |
| Index Support | Secondary indexes only | Storage-Attached Indexing |

### Migration Strategy

**Option 1: Clean Slate (Recommended)**
1. Export document metadata from MongoDB
2. Clear Cassandra embeddings: `db_manager.py --clear --db cassandra`
3. Re-run Pass D ingestion with new schema

**Option 2: Dual Schema (Transition Period)**
1. Create new table `embeddings_v2` with vector type
2. Ingest new documents to `embeddings_v2`
3. Migrate old data using ETL script
4. Update queries to use `embeddings_v2`
5. Drop old `embeddings` table when migration complete

## References

- [Cassandra 5 Vector Documentation](https://cassandra.apache.org/doc/latest/cassandra/vector-search/)
- [Storage-Attached Indexes (SAI)](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/sai/)
- [CassIO Python Library](https://cassio.org/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [LangFlow Documentation](https://docs.langflow.org/)

## Support

For issues or questions:
1. Run smoke test to validate setup
2. Check Cassandra logs: `docker logs n8n_TTRPG_cassandra`
3. Verify container networking: `docker exec n8n_TTRPG_cassandra nodetool status`
4. Review ingestion logs: `docker logs n8n_TTRPG_ingestion_engine`
