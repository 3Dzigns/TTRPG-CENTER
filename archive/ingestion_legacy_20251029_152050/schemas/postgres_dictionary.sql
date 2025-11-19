-- ================================================================================
-- Dictionary Schema Migration
-- ================================================================================
-- Purpose: Store TTRPG rulebook terminology and definitions with fast lookup
-- Phase: P01 - Postgres Infrastructure
-- Dependencies: PostgreSQL 12+
-- Performance: Dedicated tablespace for I/O optimization
-- ================================================================================

-- Create dictionary schema
CREATE SCHEMA IF NOT EXISTS dictionary;

-- ================================================================================
-- Tablespace Configuration
-- ================================================================================
-- Dedicated tablespace for dictionary data to optimize I/O performance
-- Note: Tablespace location must exist and have proper permissions
-- Create directory: mkdir -p /var/lib/postgresql/data/dictionary && chown postgres:postgres /var/lib/postgresql/data/dictionary

-- Check if tablespace exists before creating
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'dictionary_ts') THEN
    CREATE TABLESPACE dictionary_ts LOCATION '/var/lib/postgresql/data/dictionary';
  END IF;
END $$;

-- ================================================================================
-- Sources Table
-- ================================================================================
-- Stores metadata about TTRPG rulebooks and source materials
CREATE TABLE IF NOT EXISTS dictionary.sources (
  source_id       TEXT PRIMARY KEY,          -- Unique identifier (e.g., 'dnd5e-phb', 'pf2e-crb')
  title           TEXT NOT NULL,              -- Human-readable title
  system          TEXT NOT NULL,              -- Game system (D&D 5E, Pathfinder 2E, etc.)
  publisher       TEXT,                       -- Publishing company
  version         TEXT,                       -- Edition/version info
  checksum        TEXT,                       -- SHA256 hash of source file
  isbn            TEXT,                       -- ISBN if available
  publication_date DATE,                      -- Original publication date
  created_at      TIMESTAMP NOT NULL DEFAULT now(),
  updated_at      TIMESTAMP NOT NULL DEFAULT now(),

  -- Metadata fields
  metadata        JSONB,                      -- Extensible metadata (page count, language, etc.)

  -- Constraints
  CONSTRAINT valid_checksum CHECK (checksum ~ '^[a-f0-9]{64}$' OR checksum IS NULL)
) TABLESPACE dictionary_ts;

-- ================================================================================
-- Terms Table
-- ================================================================================
-- Stores individual terms/definitions extracted from sources
CREATE TABLE IF NOT EXISTS dictionary.terms (
  term_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       TEXT NOT NULL REFERENCES dictionary.sources(source_id) ON DELETE CASCADE,
  term            TEXT NOT NULL,              -- Original term as it appears in source
  normalized_term TEXT NOT NULL,              -- Lowercase, trimmed version for matching
  definition      TEXT,                       -- Full definition text
  page_ref        TEXT,                       -- Page reference (e.g., 'p. 123', 'Chapter 5')
  category        TEXT,                       -- Term category (spell, feat, rule, etc.)
  subcategory     TEXT,                       -- Subcategory for finer classification
  created_at      TIMESTAMP NOT NULL DEFAULT now(),
  updated_at      TIMESTAMP NOT NULL DEFAULT now(),

  -- Metadata fields
  metadata        JSONB,                      -- Extensible metadata (rareness, level, etc.)

  -- Constraints
  CONSTRAINT unique_term_per_source UNIQUE (source_id, normalized_term),
  CONSTRAINT non_empty_term CHECK (length(trim(term)) > 0),
  CONSTRAINT non_empty_normalized CHECK (length(trim(normalized_term)) > 0)
) TABLESPACE dictionary_ts;

-- ================================================================================
-- Cross-references Table (Optional Enhancement)
-- ================================================================================
-- Tracks relationships between terms (synonyms, related concepts, etc.)
CREATE TABLE IF NOT EXISTS dictionary.cross_references (
  id              BIGSERIAL PRIMARY KEY,
  from_term_id    UUID NOT NULL REFERENCES dictionary.terms(term_id) ON DELETE CASCADE,
  to_term_id      UUID NOT NULL REFERENCES dictionary.terms(term_id) ON DELETE CASCADE,
  relationship    TEXT NOT NULL,              -- synonym, related, antonym, parent, child
  created_at      TIMESTAMP NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT valid_relationship CHECK (relationship IN (
    'synonym', 'related', 'antonym', 'parent', 'child', 'see_also'
  )),
  CONSTRAINT no_self_reference CHECK (from_term_id != to_term_id),
  CONSTRAINT unique_cross_ref UNIQUE (from_term_id, to_term_id, relationship)
) TABLESPACE dictionary_ts;

-- ================================================================================
-- Indexes for Performance Optimization
-- ================================================================================

-- Sources table indexes
CREATE INDEX IF NOT EXISTS idx_sources_system
  ON dictionary.sources(system);

CREATE INDEX IF NOT EXISTS idx_sources_checksum
  ON dictionary.sources(checksum)
  WHERE checksum IS NOT NULL;

-- Terms table indexes
-- Primary lookup: Fast normalized term search (case-insensitive matching)
CREATE INDEX IF NOT EXISTS idx_terms_normalized
  ON dictionary.terms(normalized_term);

-- Source filtering: Retrieve all terms from a specific source
CREATE INDEX IF NOT EXISTS idx_terms_source
  ON dictionary.terms(source_id);

-- Category filtering: Find terms by type (spells, feats, etc.)
CREATE INDEX IF NOT EXISTS idx_terms_category
  ON dictionary.terms(category)
  WHERE category IS NOT NULL;

-- Full-text search support (GIN index for definition text)
CREATE INDEX IF NOT EXISTS idx_terms_definition_fts
  ON dictionary.terms USING GIN(to_tsvector('english', definition))
  WHERE definition IS NOT NULL;

-- Composite index for filtered searches
CREATE INDEX IF NOT EXISTS idx_terms_source_category
  ON dictionary.terms(source_id, category);

-- Cross-references indexes
CREATE INDEX IF NOT EXISTS idx_xref_from_term
  ON dictionary.cross_references(from_term_id);

CREATE INDEX IF NOT EXISTS idx_xref_to_term
  ON dictionary.cross_references(to_term_id);

CREATE INDEX IF NOT EXISTS idx_xref_relationship
  ON dictionary.cross_references(relationship);

-- ================================================================================
-- Triggers for Automated Maintenance
-- ================================================================================

-- Auto-update updated_at timestamp on sources table
CREATE OR REPLACE FUNCTION dictionary.update_sources_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sources_updated_at
  BEFORE UPDATE ON dictionary.sources
  FOR EACH ROW
  EXECUTE FUNCTION dictionary.update_sources_timestamp();

-- Auto-update updated_at timestamp on terms table
CREATE OR REPLACE FUNCTION dictionary.update_terms_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_terms_updated_at
  BEFORE UPDATE ON dictionary.terms
  FOR EACH ROW
  EXECUTE FUNCTION dictionary.update_terms_timestamp();

-- Auto-normalize term on insert/update
CREATE OR REPLACE FUNCTION dictionary.normalize_term()
RETURNS TRIGGER AS $$
BEGIN
  NEW.normalized_term = lower(trim(NEW.term));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_terms_normalize
  BEFORE INSERT OR UPDATE ON dictionary.terms
  FOR EACH ROW
  EXECUTE FUNCTION dictionary.normalize_term();

-- ================================================================================
-- Utility Views
-- ================================================================================

-- Term lookup view with source information
CREATE OR REPLACE VIEW dictionary.terms_with_source AS
SELECT
  t.term_id,
  t.term,
  t.normalized_term,
  t.definition,
  t.page_ref,
  t.category,
  t.subcategory,
  s.source_id,
  s.title AS source_title,
  s.system,
  s.publisher,
  s.version,
  t.metadata AS term_metadata,
  s.metadata AS source_metadata
FROM dictionary.terms t
INNER JOIN dictionary.sources s ON t.source_id = s.source_id;

-- Source statistics view
CREATE OR REPLACE VIEW dictionary.source_stats AS
SELECT
  s.source_id,
  s.title,
  s.system,
  COUNT(t.term_id) AS term_count,
  COUNT(DISTINCT t.category) AS category_count,
  s.created_at,
  s.updated_at
FROM dictionary.sources s
LEFT JOIN dictionary.terms t ON s.source_id = t.source_id
GROUP BY s.source_id, s.title, s.system, s.created_at, s.updated_at;

-- ================================================================================
-- Utility Functions
-- ================================================================================

-- Search terms by normalized text (case-insensitive, partial match)
CREATE OR REPLACE FUNCTION dictionary.search_terms(
  search_text TEXT,
  limit_results INT DEFAULT 50
)
RETURNS TABLE (
  term_id UUID,
  term TEXT,
  definition TEXT,
  source_title TEXT,
  page_ref TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    t.term_id,
    t.term,
    t.definition,
    s.title,
    t.page_ref
  FROM dictionary.terms t
  INNER JOIN dictionary.sources s ON t.source_id = s.source_id
  WHERE t.normalized_term LIKE '%' || lower(trim(search_text)) || '%'
  ORDER BY t.normalized_term
  LIMIT limit_results;
END;
$$ LANGUAGE plpgsql STABLE;

-- Get related terms (using cross-references)
CREATE OR REPLACE FUNCTION dictionary.get_related_terms(
  input_term_id UUID,
  max_depth INT DEFAULT 1
)
RETURNS TABLE (
  term_id UUID,
  term TEXT,
  relationship TEXT,
  depth INT
) AS $$
WITH RECURSIVE term_graph AS (
  -- Base case: direct relationships
  SELECT
    xr.to_term_id AS term_id,
    xr.relationship,
    1 AS depth
  FROM dictionary.cross_references xr
  WHERE xr.from_term_id = input_term_id

  UNION

  -- Recursive case: follow relationships up to max_depth
  SELECT
    xr.to_term_id,
    xr.relationship,
    tg.depth + 1
  FROM dictionary.cross_references xr
  INNER JOIN term_graph tg ON xr.from_term_id = tg.term_id
  WHERE tg.depth < max_depth
)
SELECT DISTINCT
  tg.term_id,
  t.term,
  tg.relationship,
  tg.depth
FROM term_graph tg
INNER JOIN dictionary.terms t ON tg.term_id = t.term_id
ORDER BY tg.depth, t.term;
$$ LANGUAGE sql STABLE;

-- ================================================================================
-- Permissions (adjust as needed)
-- ================================================================================
-- Example: Grant access to ingestion service account
-- GRANT USAGE ON SCHEMA dictionary TO ingestion_service;
-- GRANT ALL ON ALL TABLES IN SCHEMA dictionary TO ingestion_service;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA dictionary TO ingestion_service;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA dictionary TO ingestion_service;

-- ================================================================================
-- Migration Validation Queries
-- ================================================================================
-- Run these after migration to verify correctness:

-- Check table structure
-- SELECT table_name, column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_schema = 'dictionary'
-- ORDER BY table_name, ordinal_position;

-- Verify indexes
-- SELECT schemaname, tablename, indexname, indexdef
-- FROM pg_indexes
-- WHERE schemaname = 'dictionary';

-- Verify tablespace assignment
-- SELECT tablename, tablespace
-- FROM pg_tables
-- WHERE schemaname = 'dictionary';

-- Test term normalization trigger
-- INSERT INTO dictionary.sources (source_id, title, system)
-- VALUES ('test-source', 'Test Rulebook', 'Test System');
--
-- INSERT INTO dictionary.terms (source_id, term, definition)
-- VALUES ('test-source', '  FIREBALL  ', 'A powerful evocation spell.');
--
-- SELECT term, normalized_term FROM dictionary.terms WHERE source_id = 'test-source';
-- Expected: normalized_term = 'fireball'

-- Test cross-reference constraints
-- INSERT INTO dictionary.terms (term_id, source_id, term, definition) VALUES
--   ('11111111-1111-1111-1111-111111111111', 'test-source', 'Magic Missile', 'A spell.'),
--   ('22222222-2222-2222-2222-222222222222', 'test-source', 'Arcane Missile', 'Same spell.');
--
-- INSERT INTO dictionary.cross_references (from_term_id, to_term_id, relationship)
-- VALUES ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'synonym');
-- Expected: Success
--
-- INSERT INTO dictionary.cross_references (from_term_id, to_term_id, relationship)
-- VALUES ('11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', 'synonym');
-- Expected: Check constraint violation (no_self_reference)

-- ================================================================================
-- End of Migration
-- ================================================================================
