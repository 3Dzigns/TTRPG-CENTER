-- Seed tier configurations
-- Run this after creating the tier_configs table

-- Free tier (default)
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
) VALUES (
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
) ON CONFLICT (tier) DO UPDATE SET
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

-- Standard tier
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
) VALUES (
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
) ON CONFLICT (tier) DO UPDATE SET
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

-- Premium tier
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
) VALUES (
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
) ON CONFLICT (tier) DO UPDATE SET
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

-- Example: Grant additional sources to a game (replace with actual game ID)
-- INSERT INTO quota_grants (
--   scope,
--   entity_id,
--   grant_type,
--   additional_sources,
--   reason
-- ) VALUES (
--   'game',
--   'your-game-uuid-here',
--   'promotion',
--   5,  -- 5 additional sources
--   'Holiday promotion 2025'
-- );
