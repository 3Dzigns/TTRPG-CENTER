-- Migration: Add preferred_theme column to auth_users
-- Date: 2025-11-06

-- Add preferred_theme column with default value 'system'
ALTER TABLE auth_users
ADD COLUMN IF NOT EXISTS preferred_theme TEXT NOT NULL DEFAULT 'system';

-- Add check constraint to ensure valid theme values
ALTER TABLE auth_users
ADD CONSTRAINT auth_users_preferred_theme_check
CHECK (preferred_theme IN ('light', 'dark', 'system'));

-- Comment on the column
COMMENT ON COLUMN auth_users.preferred_theme IS 'User theme preference: light, dark, or system';
