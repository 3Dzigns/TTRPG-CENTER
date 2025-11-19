-- ================================================================================
-- Job Registry Schema Migration
-- ================================================================================
-- Purpose: Track async job lifecycle states and history for TTRPG ingestion pipeline
-- Phase: P01 - Postgres Infrastructure
-- Dependencies: PostgreSQL 12+
-- ================================================================================

-- Create jobs schema
CREATE SCHEMA IF NOT EXISTS jobs;

-- ================================================================================
-- Main Registry Table
-- ================================================================================
-- Tracks current state of all ingestion jobs with deduplication support
CREATE TABLE IF NOT EXISTS jobs.registry (
  job_id              UUID PRIMARY KEY,
  source_path         TEXT NOT NULL,
  source_id           TEXT NOT NULL,
  refresh             BOOLEAN NOT NULL DEFAULT false,
  state               TEXT NOT NULL,  -- NEW, QUEUED, RUNNING, STAGED, UPSERTING, VERIFYING, CLEANUP, COMPLETED, FAILED, REMOVED
  stage               TEXT NOT NULL,  -- gate_0_hash, pass_a_unstructured, pass_b_chunker, pass_c_parsing, pass_d_hayhooks, pass_e_graph_builder
  expected_checksum   TEXT,           -- SHA256 hash for content validation
  last_seen           TIMESTAMP NOT NULL DEFAULT now(),
  created_at          TIMESTAMP NOT NULL DEFAULT now(),
  updated_at          TIMESTAMP NOT NULL DEFAULT now(),

  -- Constraints
  CONSTRAINT valid_state CHECK (state IN (
    'NEW', 'QUEUED', 'RUNNING', 'STAGED', 'UPSERTING',
    'VERIFYING', 'CLEANUP', 'COMPLETED', 'FAILED', 'REMOVED'
  )),
  CONSTRAINT valid_stage CHECK (stage IN (
    'gate_0_hash', 'gate_0_validate', 'pass_a_unstructured', 'pass_a_metadata',
    'pass_b_chunker', 'pass_c_parsing', 'pass_d_hayhooks', 'pass_e_graph_builder',
    'pass_f_cleanup', 'complete'
  ))
);

-- ================================================================================
-- History/Audit Table
-- ================================================================================
-- Immutable audit log of all state transitions and events
CREATE TABLE IF NOT EXISTS jobs.history (
  id                  BIGSERIAL PRIMARY KEY,
  job_id              UUID NOT NULL,
  ts                  TIMESTAMP NOT NULL DEFAULT now(),
  state               TEXT,
  stage               TEXT,
  message             TEXT,
  details             JSONB,

  -- Foreign key to registry (nullable for REMOVED jobs)
  CONSTRAINT fk_job_id FOREIGN KEY (job_id)
    REFERENCES jobs.registry(job_id)
    ON DELETE SET NULL
);

-- ================================================================================
-- Indexes for Performance Optimization
-- ================================================================================

-- Deduplication index: Prevent multiple active jobs for same source_path
-- Partial index only covers active states to minimize index size
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_dedupe
  ON jobs.registry (source_path, state, stage)
  WHERE state IN ('QUEUED', 'RUNNING', 'STAGED', 'UPSERTING', 'VERIFYING');

-- Source lookup index: Fast retrieval by source_id (dictionary FK)
CREATE INDEX IF NOT EXISTS idx_jobs_source_id
  ON jobs.registry(source_id);

-- State filtering index: Common query pattern for job monitoring
CREATE INDEX IF NOT EXISTS idx_jobs_state
  ON jobs.registry(state);

-- Stage filtering index: Track pipeline stage distribution
CREATE INDEX IF NOT EXISTS idx_jobs_stage
  ON jobs.registry(stage);

-- Timestamp index: Support time-based queries (stale job detection)
CREATE INDEX IF NOT EXISTS idx_jobs_last_seen
  ON jobs.registry(last_seen);

-- History lookup index: Fast audit log retrieval by job_id
CREATE INDEX IF NOT EXISTS idx_history_job_id
  ON jobs.history(job_id);

-- History timestamp index: Time-based audit queries
CREATE INDEX IF NOT EXISTS idx_history_ts
  ON jobs.history(ts DESC);

-- ================================================================================
-- Triggers for Automated Maintenance
-- ================================================================================

-- Auto-update updated_at timestamp on registry changes
CREATE OR REPLACE FUNCTION jobs.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_registry_updated_at
  BEFORE UPDATE ON jobs.registry
  FOR EACH ROW
  EXECUTE FUNCTION jobs.update_timestamp();

-- Auto-log state transitions to history table
CREATE OR REPLACE FUNCTION jobs.log_state_change()
RETURNS TRIGGER AS $$
BEGIN
  -- Only log if state or stage changed
  IF (TG_OP = 'INSERT') OR
     (OLD.state IS DISTINCT FROM NEW.state) OR
     (OLD.stage IS DISTINCT FROM NEW.stage) THEN

    INSERT INTO jobs.history (job_id, state, stage, message, details)
    VALUES (
      NEW.job_id,
      NEW.state,
      NEW.stage,
      CASE
        WHEN TG_OP = 'INSERT' THEN 'Job created'
        ELSE 'State transition'
      END,
      jsonb_build_object(
        'operation', TG_OP,
        'old_state', OLD.state,
        'new_state', NEW.state,
        'old_stage', OLD.stage,
        'new_stage', NEW.stage
      )
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_registry_state_log
  AFTER INSERT OR UPDATE ON jobs.registry
  FOR EACH ROW
  EXECUTE FUNCTION jobs.log_state_change();

-- ================================================================================
-- Utility Views
-- ================================================================================

-- Active jobs view: Currently executing or queued jobs
CREATE OR REPLACE VIEW jobs.active_jobs AS
SELECT
  job_id,
  source_path,
  source_id,
  state,
  stage,
  created_at,
  updated_at,
  EXTRACT(EPOCH FROM (now() - updated_at)) AS seconds_since_update
FROM jobs.registry
WHERE state IN ('QUEUED', 'RUNNING', 'STAGED', 'UPSERTING', 'VERIFYING')
ORDER BY created_at ASC;

-- Failed jobs view: Jobs requiring attention
CREATE OR REPLACE VIEW jobs.failed_jobs AS
SELECT
  r.job_id,
  r.source_path,
  r.source_id,
  r.state,
  r.stage,
  r.created_at,
  r.updated_at,
  h.message AS last_error,
  h.details AS error_details
FROM jobs.registry r
LEFT JOIN LATERAL (
  SELECT message, details
  FROM jobs.history
  WHERE job_id = r.job_id
  ORDER BY ts DESC
  LIMIT 1
) h ON true
WHERE r.state = 'FAILED'
ORDER BY r.updated_at DESC;

-- ================================================================================
-- Permissions (adjust as needed)
-- ================================================================================
-- Example: Grant access to ingestion service account
-- GRANT USAGE ON SCHEMA jobs TO ingestion_service;
-- GRANT ALL ON ALL TABLES IN SCHEMA jobs TO ingestion_service;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA jobs TO ingestion_service;

-- ================================================================================
-- Migration Validation Queries
-- ================================================================================
-- Run these after migration to verify correctness:

-- Check table structure
-- SELECT table_name, column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_schema = 'jobs'
-- ORDER BY table_name, ordinal_position;

-- Verify indexes
-- SELECT schemaname, tablename, indexname, indexdef
-- FROM pg_indexes
-- WHERE schemaname = 'jobs';

-- Test deduplication constraint
-- INSERT INTO jobs.registry (job_id, source_path, source_id, state, stage)
-- VALUES
--   (gen_random_uuid(), '/test/path.pdf', 'test-source', 'QUEUED', 'gate_0_hash'),
--   (gen_random_uuid(), '/test/path.pdf', 'test-source', 'QUEUED', 'gate_0_hash');
-- Expected: Unique constraint violation on second insert

-- ================================================================================
-- End of Migration
-- ================================================================================
