-- 002_seed_content.sql
-- Seeds initial data for games, characters, sources, and usage
-- Seed Date: 2025-11-06

-- =====================================================
-- SOURCES
-- =====================================================

INSERT INTO sources (id, name, category, created_at, updated_at) VALUES
    ('550e8400-e29b-41d4-a716-446655440001', 'Lost Mines of Phandelver', 'campaign', now() - interval '3 days', now() - interval '3 days'),
    ('550e8400-e29b-41d4-a716-446655440002', 'Rise of the Runelords', 'module', now() - interval '10 days', now() - interval '10 days'),
    ('550e8400-e29b-41d4-a716-446655440003', 'GM Encounter Library', 'homebrew', now() - interval '6 hours', now() - interval '6 hours')
ON CONFLICT (name) DO NOTHING;

-- =====================================================
-- GAMES
-- =====================================================

-- Get a valid user ID from auth_users table
DO $$
DECLARE
    first_user_id UUID;
    gm_user_id UUID;
BEGIN
    -- Get the first user from auth_users to use as GM
    SELECT id INTO first_user_id FROM auth_users ORDER BY created_at LIMIT 1;

    -- If no user exists, create a demo user
    IF first_user_id IS NULL THEN
        INSERT INTO auth_users (id, email, display_name, created_at, updated_at)
        VALUES (
            '550e8400-e29b-41d4-a716-446655440099',
            'demo.gm@ttrpg.local',
            'Demo GM',
            now(),
            now()
        )
        ON CONFLICT (email) DO NOTHING
        RETURNING id INTO first_user_id;
    END IF;

    gm_user_id := first_user_id;

    -- Insert games with the valid user ID
    INSERT INTO games (id, title, summary, status, gm_id, session_count, last_played_at, created_at, updated_at, invite_code, tier, allow_audio_bridge, allow_summaries, allow_discord_bridge) VALUES
        (
            '660e8400-e29b-41d4-a716-446655440001',
            'Shadows over Neverwinter',
            'Investigate a surge in planar breaches beneath the city.',
            'active',
            gm_user_id,
            12,
            now() - interval '4 hours',
            now() - interval '90 days',
            now() - interval '4 hours',
            'NW-7135',
            'standard',
            true,
            true,
            false
        ),
        (
            '660e8400-e29b-41d4-a716-446655440002',
            'Echoes of the Astral Sea',
            'A plane-hopping adventure through ancient ruins.',
            'draft',
            gm_user_id,
            0,
            NULL,
            now() - interval '14 days',
            now() - interval '12 hours',
            'AS-9041',
            'free',
            false,
            false,
            false
        )
    ON CONFLICT (id) DO NOTHING;

    -- Insert game members (GM is automatically a member)
    INSERT INTO game_members (game_id, user_id, role, status, joined_at) VALUES
        ('660e8400-e29b-41d4-a716-446655440001', gm_user_id, 'gm', 'active', now() - interval '90 days'),
        ('660e8400-e29b-41d4-a716-446655440002', gm_user_id, 'gm', 'active', now() - interval '14 days')
    ON CONFLICT (game_id, user_id) DO NOTHING;

    -- Insert game sources
    INSERT INTO game_sources (game_id, source_id, added_at) VALUES
        ('660e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', now() - interval '90 days'),
        ('660e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440003', now() - interval '85 days'),
        ('660e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440002', now() - interval '14 days')
    ON CONFLICT (game_id, source_id) DO NOTHING;

    -- Insert user sources (sources owned by the GM)
    INSERT INTO user_sources (user_id, source_id, acquired_at) VALUES
        (gm_user_id, '550e8400-e29b-41d4-a716-446655440001', now() - interval '100 days'),
        (gm_user_id, '550e8400-e29b-41d4-a716-446655440003', now() - interval '95 days')
    ON CONFLICT (user_id, source_id) DO NOTHING;

    -- Insert characters
    INSERT INTO characters (id, name, class_name, level, owner_id, created_at, updated_at, system, game_id) VALUES
        (
            '770e8400-e29b-41d4-a716-446655440001',
            'Elira Moonfall',
            'Wizard',
            7,
            gm_user_id,
            now() - interval '30 days',
            now() - interval '2 hours',
            'dnd-5e',
            '660e8400-e29b-41d4-a716-446655440001'
        ),
        (
            '770e8400-e29b-41d4-a716-446655440002',
            'Torren Blackroot',
            'Ranger',
            5,
            gm_user_id,
            now() - interval '45 days',
            now() - interval '1 day',
            'dnd-5e',
            '660e8400-e29b-41d4-a716-446655440002'
        )
    ON CONFLICT (id) DO NOTHING;

    -- Insert character sources (active sources for characters)
    INSERT INTO character_sources (character_id, source_id, added_at) VALUES
        ('770e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440001', now() - interval '30 days'),
        ('770e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440003', now() - interval '45 days')
    ON CONFLICT (character_id, source_id) DO NOTHING;

    -- Insert usage metrics for user
    INSERT INTO usage_metrics (
        scope,
        entity_id,
        total_seconds_played,
        monthly_session_count,
        automation_credits_remaining,
        text_assist_remaining,
        audio_bridge_remaining,
        discord_bridge_remaining,
        updated_at
    ) VALUES
        (
            'user',
            gm_user_id,
            169200, -- 47 hours
            3,
            42,
            10,
            5,
            8,
            now() - interval '30 minutes'
        )
    ON CONFLICT (scope, entity_id) DO UPDATE SET
        total_seconds_played = EXCLUDED.total_seconds_played,
        monthly_session_count = EXCLUDED.monthly_session_count,
        automation_credits_remaining = EXCLUDED.automation_credits_remaining,
        text_assist_remaining = EXCLUDED.text_assist_remaining,
        audio_bridge_remaining = EXCLUDED.audio_bridge_remaining,
        discord_bridge_remaining = EXCLUDED.discord_bridge_remaining,
        updated_at = EXCLUDED.updated_at;

    -- Insert usage metrics for games
    INSERT INTO usage_metrics (
        scope,
        entity_id,
        total_seconds_played,
        monthly_session_count,
        automation_credits_remaining,
        text_assist_remaining,
        updated_at
    ) VALUES
        (
            'game',
            '660e8400-e29b-41d4-a716-446655440001',
            115200, -- 32 hours
            2,
            12,
            6,
            now() - interval '15 minutes'
        ),
        (
            'game',
            '660e8400-e29b-41d4-a716-446655440002',
            28800, -- 8 hours
            1,
            5,
            2,
            now() - interval '6 hours'
        )
    ON CONFLICT (scope, entity_id) DO UPDATE SET
        total_seconds_played = EXCLUDED.total_seconds_played,
        monthly_session_count = EXCLUDED.monthly_session_count,
        automation_credits_remaining = EXCLUDED.automation_credits_remaining,
        text_assist_remaining = EXCLUDED.text_assist_remaining,
        updated_at = EXCLUDED.updated_at;
END $$;

-- =====================================================
-- VERIFICATION QUERIES (commented out - for manual testing)
-- =====================================================

-- Count records
-- SELECT
--     'sources' as table_name, COUNT(*) as count FROM sources
-- UNION ALL
-- SELECT 'games', COUNT(*) FROM games
-- UNION ALL
-- SELECT 'characters', COUNT(*) FROM characters
-- UNION ALL
-- SELECT 'game_members', COUNT(*) FROM game_members
-- UNION ALL
-- SELECT 'game_sources', COUNT(*) FROM game_sources
-- UNION ALL
-- SELECT 'user_sources', COUNT(*) FROM user_sources
-- UNION ALL
-- SELECT 'character_sources', COUNT(*) FROM character_sources
-- UNION ALL
-- SELECT 'usage_metrics', COUNT(*) FROM usage_metrics;

-- View games with GM info
-- SELECT g.title, g.status, u.display_name as gm_name, g.session_count
-- FROM games g
-- JOIN auth_users u ON g.gm_id = u.id;

-- View characters with owner and game
-- SELECT c.name, c.class_name, c.level, u.display_name as owner, g.title as game
-- FROM characters c
-- JOIN auth_users u ON c.owner_id = u.id
-- LEFT JOIN games g ON c.game_id = g.id;

-- Seed complete
