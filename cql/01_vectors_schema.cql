-- 01_vectors_schema.cql
-- Cassandra 5 Vector Schema for TTRPG Document Embeddings
-- =========================================================
-- Creates keyspace and table for storing OpenAI embeddings with metadata filters.
-- Uses native vector<float, 1536> type and SAI indexes for ANN search.
--
-- Features:
-- - Native vector type (Cassandra 5.0+)
-- - Storage-Attached Indexing (SAI) for metadata filters
-- - SAI ANN index with cosine similarity
-- - Optimized for LangFlow CassIO and n8n integration
--
-- Usage:
--   cqlsh -f 01_vectors_schema.cql
--   docker exec -it n8n_TTRPG_cassandra cqlsh -f /path/to/01_vectors_schema.cql

-- Create keyspace with SimpleStrategy (single-node development)
-- For production, use NetworkTopologyStrategy with appropriate replication
CREATE KEYSPACE IF NOT EXISTS ttrpg_vectors
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': '1'};

USE ttrpg_vectors;

-- Drop existing table if migrating from list<float> to vector<float, 1536>
-- WARNING: This removes all existing data. Use db_manager.py for backups.
-- DROP TABLE IF EXISTS embeddings;

-- Create embeddings table with native vector type
CREATE TABLE IF NOT EXISTS embeddings (
  document_id text,        -- Unique document identifier (partition key)
  element_id text,         -- Element identifier within document (clustering key)
  chunk_index int,         -- Chunk sequence number (clustering key)
  text text,               -- Raw text content for retrieval
  system text,             -- Game system (e.g., "D&D 5e", "Pathfinder 2e")
  source text,             -- Source book/module (e.g., "Player's Handbook")
  section text,            -- Document section (e.g., "Chapter 3: Classes")
  tags set<text>,          -- Flexible metadata tags
  vector vector<float, 1536>, -- OpenAI text-embedding-3-small (1536 dimensions)
  updated_at timestamp,    -- Last update timestamp
  PRIMARY KEY ((document_id), element_id, chunk_index)
) WITH CLUSTERING ORDER BY (element_id ASC, chunk_index ASC);

-- Create SAI indexes for metadata filters
-- These enable efficient filtered vector search (e.g., "D&D spells only")

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_system_idx
  ON embeddings (system)
  USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_source_idx
  ON embeddings (source)
  USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_section_idx
  ON embeddings (section)
  USING 'StorageAttachedIndex';

-- Index on set values requires values() function
CREATE CUSTOM INDEX IF NOT EXISTS embeddings_tags_idx
  ON embeddings (values(tags))
  USING 'StorageAttachedIndex';

-- Create SAI ANN index for vector similarity search
-- Uses cosine similarity (range: -1 to 1, higher = more similar)
CREATE CUSTOM INDEX IF NOT EXISTS embeddings_vector_ann
  ON embeddings (vector)
  USING 'StorageAttachedIndex'
  WITH OPTIONS = {'similarity_function': 'cosine'};

-- Verification queries
-- ====================

-- 1. List all indexes
-- SELECT index_name, options FROM system_schema.indexes WHERE keyspace_name = 'ttrpg_vectors' AND table_name = 'embeddings';

-- 2. Count embeddings per document
-- SELECT document_id, COUNT(*) as chunk_count FROM embeddings GROUP BY document_id;

-- 3. Test ANN search (requires existing data)
-- SELECT document_id, element_id, chunk_index, text, similarity_cosine(vector, ?) AS score
-- FROM embeddings
-- ORDER BY vector ANN OF ?
-- LIMIT 5;

-- 4. Test filtered ANN search
-- SELECT document_id, element_id, chunk_index, text, similarity_cosine(vector, ?) AS score
-- FROM embeddings
-- WHERE system = 'D&D 5e'
-- ORDER BY vector ANN OF ?
-- LIMIT 5;

-- Schema Notes
-- ============
-- 1. Vector dimension (1536) matches OpenAI text-embedding-3-small
-- 2. Partition key (document_id) distributes data across nodes
-- 3. Clustering keys (element_id, chunk_index) enable range queries within documents
-- 4. SAI indexes allow efficient filtering without ALLOW FILTERING
-- 5. Cosine similarity: 1.0 = identical, 0.0 = orthogonal, -1.0 = opposite
-- 6. ANN search is approximate but fast; use with LIMIT for best results
