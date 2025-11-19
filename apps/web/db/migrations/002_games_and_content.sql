-- 002_games_and_content.sql
-- Creates tables for games, characters, sources, and usage tracking
-- Migration Date: 2025-11-06

-- =====================================================
-- GAMES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'archived')) DEFAULT 'draft',
    gm_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    session_count INTEGER NOT NULL DEFAULT 0,
    last_played_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    invite_code TEXT UNIQUE,
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'standard', 'premium')),
    allow_audio_bridge BOOLEAN NOT NULL DEFAULT false,
    allow_summaries BOOLEAN NOT NULL DEFAULT false,
    allow_discord_bridge BOOLEAN NOT NULL DEFAULT false
);

-- =====================================================
-- GAME MEMBERS TABLE (Many-to-Many: Users <-> Games)
-- =====================================================
CREATE TABLE IF NOT EXISTS game_members (
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('gm', 'co-gm', 'player', 'spectator')) DEFAULT 'player',
    status TEXT NOT NULL CHECK (status IN ('active', 'invited', 'removed')) DEFAULT 'active',
    invited_at TIMESTAMPTZ,
    joined_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (game_id, user_id)
);

-- =====================================================
-- CHARACTERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1 CHECK (level >= 1 AND level <= 20),
    owner_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    portrait_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    system TEXT NOT NULL DEFAULT 'dnd-5e' CHECK (system IN ('dnd-5e', 'pf2e', 'cyberpunk-red', 'generic', 'custom')),
    game_id UUID REFERENCES games(id) ON DELETE SET NULL
);

-- =====================================================
-- SOURCES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (category IN ('campaign', 'module', 'expansion', 'ruleset', 'homebrew')) DEFAULT 'module',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================
-- USER SOURCES TABLE (Many-to-Many: Users <-> Sources)
-- =====================================================
CREATE TABLE IF NOT EXISTS user_sources (
    user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, source_id)
);

-- =====================================================
-- GAME SOURCES TABLE (Many-to-Many: Games <-> Sources)
-- =====================================================
CREATE TABLE IF NOT EXISTS game_sources (
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, source_id)
);

-- =====================================================
-- CHARACTER SOURCES TABLE (Many-to-Many: Characters <-> Sources)
-- =====================================================
CREATE TABLE IF NOT EXISTS character_sources (
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (character_id, source_id)
);

-- =====================================================
-- USAGE METRICS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS usage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT NOT NULL CHECK (scope IN ('user', 'game')),
    entity_id UUID NOT NULL,
    total_seconds_played INTEGER NOT NULL DEFAULT 0 CHECK (total_seconds_played >= 0),
    monthly_session_count INTEGER NOT NULL DEFAULT 0 CHECK (monthly_session_count >= 0),
    automation_credits_remaining INTEGER NOT NULL DEFAULT 0 CHECK (automation_credits_remaining >= 0),
    text_assist_remaining INTEGER CHECK (text_assist_remaining >= 0),
    audio_bridge_remaining INTEGER CHECK (audio_bridge_remaining >= 0),
    discord_bridge_remaining INTEGER CHECK (discord_bridge_remaining >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope, entity_id)
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Games indexes
CREATE INDEX IF NOT EXISTS idx_games_gm_id ON games(gm_id);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_games_created_at ON games(created_at DESC);

-- Game members indexes
CREATE INDEX IF NOT EXISTS idx_game_members_user_id ON game_members(user_id);
CREATE INDEX IF NOT EXISTS idx_game_members_status ON game_members(status);

-- Characters indexes
CREATE INDEX IF NOT EXISTS idx_characters_owner_id ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_characters_game_id ON characters(game_id);
CREATE INDEX IF NOT EXISTS idx_characters_system ON characters(system);

-- Usage metrics indexes
CREATE INDEX IF NOT EXISTS idx_usage_metrics_scope_entity ON usage_metrics(scope, entity_id);
CREATE INDEX IF NOT EXISTS idx_usage_metrics_updated_at ON usage_metrics(updated_at DESC);

-- User sources indexes
CREATE INDEX IF NOT EXISTS idx_user_sources_user_id ON user_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sources_source_id ON user_sources(source_id);

-- Game sources indexes
CREATE INDEX IF NOT EXISTS idx_game_sources_game_id ON game_sources(game_id);
CREATE INDEX IF NOT EXISTS idx_game_sources_source_id ON game_sources(source_id);

-- Character sources indexes
CREATE INDEX IF NOT EXISTS idx_character_sources_character_id ON character_sources(character_id);

-- =====================================================
-- FUNCTIONS FOR AUTO-UPDATE TIMESTAMPS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for auto-updating updated_at
DROP TRIGGER IF EXISTS update_games_updated_at ON games;
CREATE TRIGGER update_games_updated_at
    BEFORE UPDATE ON games
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_characters_updated_at ON characters;
CREATE TRIGGER update_characters_updated_at
    BEFORE UPDATE ON characters
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_sources_updated_at ON sources;
CREATE TRIGGER update_sources_updated_at
    BEFORE UPDATE ON sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_usage_metrics_updated_at ON usage_metrics;
CREATE TRIGGER update_usage_metrics_updated_at
    BEFORE UPDATE ON usage_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- VERIFICATION QUERIES (commented out - for manual testing)
-- =====================================================

-- List all tables
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- Check games table structure
-- \d games

-- Count records in each table
-- SELECT 'games' as table_name, COUNT(*) as count FROM games
-- UNION ALL
-- SELECT 'characters', COUNT(*) FROM characters
-- UNION ALL
-- SELECT 'sources', COUNT(*) FROM sources
-- UNION ALL
-- SELECT 'game_members', COUNT(*) FROM game_members
-- UNION ALL
-- SELECT 'usage_metrics', COUNT(*) FROM usage_metrics;

-- Migration complete
