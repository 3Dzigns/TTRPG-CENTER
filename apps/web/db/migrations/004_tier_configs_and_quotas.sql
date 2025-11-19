-- Migration: Add tier_configs and quota_grants tables
-- Date: 2025-11-07
-- Description: Adds database-driven tier configuration and quota grant system

-- Create tier_configs table
CREATE TABLE IF NOT EXISTS tier_configs (
  tier TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  base_source_limit INTEGER NOT NULL DEFAULT 0,
  base_text_assist_limit INTEGER NOT NULL DEFAULT 0,
  base_automation_credits_limit INTEGER NOT NULL DEFAULT 0,
  base_audio_bridge_limit INTEGER NOT NULL DEFAULT 0,
  base_discord_bridge_limit INTEGER NOT NULL DEFAULT 0,
  allow_audio_bridge BOOLEAN NOT NULL DEFAULT FALSE,
  allow_summaries BOOLEAN NOT NULL DEFAULT FALSE,
  allow_discord_bridge BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create quota_grants table
CREATE TABLE IF NOT EXISTS quota_grants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scope TEXT NOT NULL,
  entity_id UUID NOT NULL,
  grant_type TEXT NOT NULL,
  additional_sources INTEGER NOT NULL DEFAULT 0,
  additional_text_assist INTEGER NOT NULL DEFAULT 0,
  additional_automation_credits INTEGER NOT NULL DEFAULT 0,
  additional_audio_bridge INTEGER NOT NULL DEFAULT 0,
  additional_discord_bridge INTEGER NOT NULL DEFAULT 0,
  granted_by UUID REFERENCES auth_users(id),
  granted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE,
  reason TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Create indexes for quota_grants
CREATE INDEX IF NOT EXISTS idx_quota_grants_entity ON quota_grants(scope, entity_id);
CREATE INDEX IF NOT EXISTS idx_quota_grants_active ON quota_grants(is_active, expires_at);

-- Insert default tier configurations
INSERT INTO tier_configs (
  tier,
  display_name,
  base_source_limit,
  base_text_assist_limit,
  base_automation_credits_limit,
  base_audio_bridge_limit,
  base_discord_bridge_limit,
  allow_audio_bridge,
  allow_summaries,
  allow_discord_bridge
) VALUES
  -- Free tier (Tier 1)
  (
    'free',
    'Free',
    3,      -- 3 sources
    100,    -- 100 text assist queries
    10,     -- 10 automation credits
    0,      -- no audio bridge
    0,      -- no discord bridge
    false,  -- audio bridge not allowed
    false,  -- summaries not allowed
    false   -- discord bridge not allowed
  ),
  -- Standard tier (Tier 2)
  (
    'standard',
    'Standard',
    10,     -- 10 sources
    1000,   -- 1000 text assist queries
    100,    -- 100 automation credits
    60,     -- 60 minutes audio bridge
    100,    -- 100 discord bridge operations
    true,   -- audio bridge allowed
    true,   -- summaries allowed
    true    -- discord bridge allowed
  ),
  -- Premium tier (Tier 3)
  (
    'premium',
    'Premium',
    999,    -- unlimited sources (practical limit)
    9999,   -- 9999 text assist queries
    999,    -- 999 automation credits
    999,    -- unlimited audio bridge (practical limit)
    999,    -- unlimited discord bridge (practical limit)
    true,   -- audio bridge allowed
    true,   -- summaries allowed
    true    -- discord bridge allowed
  )
ON CONFLICT (tier) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  base_source_limit = EXCLUDED.base_source_limit,
  base_text_assist_limit = EXCLUDED.base_text_assist_limit,
  base_automation_credits_limit = EXCLUDED.base_automation_credits_limit,
  base_audio_bridge_limit = EXCLUDED.base_audio_bridge_limit,
  base_discord_bridge_limit = EXCLUDED.base_discord_bridge_limit,
  allow_audio_bridge = EXCLUDED.allow_audio_bridge,
  allow_summaries = EXCLUDED.allow_summaries,
  allow_discord_bridge = EXCLUDED.allow_discord_bridge,
  updated_at = NOW();

-- Add comment to migration
COMMENT ON TABLE tier_configs IS 'Defines base limits and features for each subscription tier';
COMMENT ON TABLE quota_grants IS 'Tracks additional quotas granted through purchases, promotions, or manual grants';
