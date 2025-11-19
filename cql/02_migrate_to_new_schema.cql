-- 02_migrate_to_new_schema.cql
-- Migration script to add new metadata columns to existing embeddings table
-- ============================================================================
-- Adds columns for new simplified schema while preserving existing data
--
-- Usage:
--   docker exec -i n8n_TTRPG_cassandra cqlsh < cql/02_migrate_to_new_schema.cql

USE ttrpg_vectors;

-- Add new metadata columns (compatible with existing schema)
ALTER TABLE embeddings ADD system text;
ALTER TABLE embeddings ADD source text;
ALTER TABLE embeddings ADD section text;
ALTER TABLE embeddings ADD tags set<text>;
ALTER TABLE embeddings ADD text text;
ALTER TABLE embeddings ADD updated_at timestamp;

-- Create SAI indexes for new metadata columns
CREATE CUSTOM INDEX IF NOT EXISTS embeddings_system_idx
  ON embeddings (system)
  USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_source_idx
  ON embeddings (source)
  USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_section_idx
  ON embeddings (section)
  USING 'StorageAttachedIndex';

CREATE CUSTOM INDEX IF NOT EXISTS embeddings_tags_idx
  ON embeddings (values(tags))
  USING 'StorageAttachedIndex';

-- Note: embeddings_vector_ann index already exists
-- Verification: SELECT index_name FROM system_schema.indexes WHERE keyspace_name = 'ttrpg_vectors' AND table_name = 'embeddings';
