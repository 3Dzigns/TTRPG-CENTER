-- jobs schema for fully async ingestion pipeline
-- Creates registry, history, and event tables to back Celery-based orchestration.

CREATE SCHEMA IF NOT EXISTS jobs;

CREATE TABLE IF NOT EXISTS jobs.registry (
    job_id UUID PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    job_type TEXT NOT NULL,
    refresh BOOLEAN NOT NULL DEFAULT FALSE,
    state TEXT NOT NULL,
    stage TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    last_error TEXT,
    next_run_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_registry_source_id
    ON jobs.registry (source_id);

CREATE INDEX IF NOT EXISTS idx_registry_state_stage
    ON jobs.registry (state, stage);

CREATE INDEX IF NOT EXISTS idx_registry_next_run
    ON jobs.registry (next_run_at)
    WHERE next_run_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS jobs.history (
    history_id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs.registry(job_id) ON DELETE CASCADE,
    stage TEXT,
    state TEXT NOT NULL,
    message TEXT,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_history_job_id
    ON jobs.history (job_id);

CREATE TABLE IF NOT EXISTS jobs.events (
    event_id BIGSERIAL PRIMARY KEY,
    job_id UUID,
    event_type TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_job_id
    ON jobs.events (job_id);

CREATE OR REPLACE FUNCTION jobs.touch_registry_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_registry_updated_at ON jobs.registry;
CREATE TRIGGER trg_registry_updated_at
    BEFORE UPDATE ON jobs.registry
    FOR EACH ROW
    EXECUTE FUNCTION jobs.touch_registry_updated_at();
