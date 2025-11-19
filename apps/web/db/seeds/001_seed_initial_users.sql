INSERT INTO auth_users (email, display_name, avatar_url)
VALUES
    ('admin@example.com', 'Admin User', NULL),
    ('player@example.com', 'Player One', NULL)
ON CONFLICT (email) DO UPDATE
SET display_name = EXCLUDED.display_name,
    updated_at = NOW();

WITH target_user AS (
    SELECT id FROM auth_users WHERE email = 'admin@example.com'
),
role_ids AS (
    SELECT id FROM auth_roles WHERE name IN ('player', 'gm', 'admin')
)
INSERT INTO auth_user_roles (user_id, role_id)
SELECT target_user.id, role_ids.id
FROM target_user, role_ids
ON CONFLICT (user_id, role_id) DO NOTHING;

WITH target_user AS (
    SELECT id FROM auth_users WHERE email = 'player@example.com'
),
role_ids AS (
    SELECT id FROM auth_roles WHERE name = 'player'
)
INSERT INTO auth_user_roles (user_id, role_id)
SELECT target_user.id, role_ids.id
FROM target_user, role_ids
ON CONFLICT (user_id, role_id) DO NOTHING;
