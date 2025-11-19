# FR-INGEST-CASS-V5-VECTORS (Hotfix)

**Goal:** Make our ingestion engine write searchable vector rows into **Cassandra 5** using the new `vector<float, DIM>` type + SAI ANN, with metadata filters. Ensure **LangFlow** (via CassIO) and **n8n** (via a tiny HTTP wrapper) can perform ANN + filtered lookups.

---

## Acceptance criteria
1. Schema with vector<float, 1536> and metadata filters.
2. Ingestion engine validates vector length and upserts correctly.
3. LangFlow CassIO and n8n FastAPI search integration functional.
4. CLI test harness for vector insert + ANN search.

---

## DDL (CQL)

CREATE KEYSPACE IF NOT EXISTS ttrpg_vectors
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};

USE ttrpg_vectors;

CREATE TABLE IF NOT EXISTS embeddings (
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
) WITH CLUSTERING ORDER BY (element_id ASC, chunk_index ASC);

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_system_idx
  ON embeddings (system) USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_source_idx
  ON embeddings (source) USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_section_idx
  ON embeddings (section) USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_tags_idx
  ON embeddings (values(tags)) USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_vector_ann
  ON embeddings (vector)
  USING 'StorageAttachedIndex'
  WITH OPTIONS = {'similarity_function': 'cosine'};

---

## Python Ingestion Example

from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from datetime import datetime

EMBED_DIM = 1536

def upsert_embedding(session, row):
    vec = row["vector"]
    assert len(vec) == EMBED_DIM, f"Bad dim {len(vec)} != {EMBED_DIM}"
    q = session.prepare('''
        INSERT INTO ttrpg_vectors.embeddings (
          document_id, element_id, chunk_index, text, system, source, section, tags, vector, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''')
    session.execute(q, (
        row["document_id"], row["element_id"], row["chunk_index"],
        row["text"], row["system"], row["source"], row["section"],
        set(row.get("tags", [])), vec, datetime.utcnow()
    ))

---

## FastAPI Search Service

from fastapi import FastAPI
from pydantic import BaseModel
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

app = FastAPI()
EMBED_DIM = 1536

class SearchReq(BaseModel):
    vector: list[float]
    top_k: int = 5
    system: str | None = None
    source: str | None = None
    tag: str | None = None

@app.post("/search")
def search(req: SearchReq):
    vec = req.vector
    assert len(vec) == EMBED_DIM
    filters, params = [], []
    if req.system: filters.append("system = ?"); params.append(req.system)
    if req.source: filters.append("source = ?"); params.append(req.source)
    if req.tag: filters.append("tags CONTAINS ?"); params.append(req.tag)
    where = "WHERE " + " AND ".join(filters) if filters else ""
    cql = f'''
        SELECT document_id, element_id, chunk_index, text,
               similarity_cosine(vector, ?) AS score
        FROM embeddings {where}
        ORDER BY vector ANN OF ?
        LIMIT {req.top_k};
    '''
    rows = session.execute(session.prepare(cql), [vec] + params + [vec])
    return [{
        "document_id": r.document_id,
        "element_id": r.element_id,
        "chunk_index": r.chunk_index,
        "score": float(r.score),
        "text": r.text
    } for r in rows]

---

## Example Query (CQL)

SELECT document_id, element_id, chunk_index, text,
       similarity_cosine(vector, ?) AS score
FROM ttrpg_vectors.embeddings
ORDER BY vector ANN OF ?
LIMIT 5;

---

## Deliverables
- cql/01_vectors_schema.cql
- ingest/upsert_embeddings.py
- search/fastapi_cql_search.py
- tests/smoke_vector_ingest_and_search.py
- LangFlow JSON demo flow
