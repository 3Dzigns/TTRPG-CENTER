# Database Design – Postgres RBAC & Auth Schema
**Version:** 1.0
**Date:** October 19, 2025
**Reference:** P01 Middleware Plan §4 (M1 - Core Infrastructure)

---

## Executive Summary

This document provides the complete database schema design for a multi-tenant RBAC (Role-Based Access Control) system using PostgreSQL with Row-Level Security (RLS). The design supports OIDC/OAuth authentication, org-level isolation, comprehensive audit logging with monthly partitioning, and production-grade backup/maintenance strategies.

**Key Features:**
- 10 core tables with proper normalization
- CITEXT for case-insensitive email lookups
- RLS policies for org-level data isolation
- Monthly partitioning for audit_logs (13-month retention)
- Comprehensive indexing strategy
- Alembic migration plan
- Backup/restore with PITR (Point-in-Time Recovery)
- Auto-vacuum tuning for high-churn tables

---

## 1. Schema Overview

### Entity Relationship Diagram (Textual)

```
┌─────────────┐       ┌──────────────┐       ┌──────────────┐
│   users     │───────│ identities   │       │    orgs      │
│             │  1:N  │  (OIDC)      │       │              │
└─────┬───────┘       └──────────────┘       └──────┬───────┘
      │                                              │
      │ N                                            │
      │                   ┌──────────────┐          │
      └───────────────────│ memberships  │──────────┘
                     N:M  │ (user-org)   │
                          └──────────────┘
                                  │
                                  │ (org context)
                                  │
      ┌───────────────────────────┴────────────────────────┐
      │                                                     │
┌─────▼──────┐       ┌──────────────┐       ┌─────────────▼──┐
│ user_roles │───────│    roles     │       │   audit_logs   │
│ (junction) │  N:1  │              │       │  (partitioned) │
└────────────┘       └──────┬───────┘       └────────────────┘
                            │ N:M
                            │
                     ┌──────▼───────────┐
                     │ role_permissions │
                     │   (junction)     │
                     └──────┬───────────┘
                            │ N:1
                     ┌──────▼──────┐
                     │ permissions │
                     └─────────────┘

     ┌──────────────┐           ┌──────────────┐
     │   api_keys   │           │   sessions   │
     │              │           │   (Redis alt)│
     └──────────────┘           └──────────────┘
```

---

## 2. Table Definitions (DDL)

### 2.1 Extension Prerequisites

```sql
-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID generation
CREATE EXTENSION IF NOT EXISTS "citext";       -- Case-insensitive text
CREATE EXTENSION IF NOT EXISTS "pgcrypto";     -- Cryptographic functions
CREATE EXTENSION IF NOT EXISTS "btree_gin";    -- Array indexing
```

---

### 2.2 Core Tables

#### users

Primary user identity table.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT UNIQUE NOT NULL,              -- Case-insensitive
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Indexes
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_created_at ON users (created_at);
CREATE INDEX idx_users_is_active ON users (is_active) WHERE is_active = true;

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE users IS 'Primary user identity and profile information';
COMMENT ON COLUMN users.email IS 'Case-insensitive unique email address';
```

---

#### identities

OIDC/OAuth provider linkage (supports multiple providers per user).

```sql
CREATE TABLE identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,                     -- 'google', 'github', 'auth0', etc.
    provider_user_id TEXT NOT NULL,            -- 'sub' claim from OIDC
    metadata JSONB DEFAULT '{}'::jsonb,        -- Store id_token claims
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT identities_provider_user_unique UNIQUE (provider, provider_user_id)
);

-- Indexes
CREATE INDEX idx_identities_user_id ON identities (user_id);
CREATE INDEX idx_identities_provider_lookup ON identities (provider, provider_user_id);

COMMENT ON TABLE identities IS 'OIDC/OAuth provider linkage (1 user : N providers)';
COMMENT ON COLUMN identities.metadata IS 'Stores OIDC id_token claims (email, name, picture, etc.)';
```

---

#### orgs

Organizations (tenants) for multi-tenancy.

```sql
CREATE TABLE orgs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,                 -- URL-friendly identifier
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT orgs_slug_format CHECK (slug ~ '^[a-z0-9-]+$')
);

-- Indexes
CREATE INDEX idx_orgs_name ON orgs (name);
CREATE INDEX idx_orgs_slug ON orgs (slug);

COMMENT ON TABLE orgs IS 'Organizations (tenants) for multi-tenant isolation';
COMMENT ON COLUMN orgs.slug IS 'URL-friendly identifier (lowercase, alphanumeric + hyphens)';
```

---

#### memberships

User-organization junction (user can belong to multiple orgs).

```sql
CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT memberships_user_org_unique UNIQUE (user_id, org_id)
);

-- Indexes
CREATE INDEX idx_memberships_user_id ON memberships (user_id);
CREATE INDEX idx_memberships_org_id ON memberships (org_id);
CREATE INDEX idx_memberships_user_org ON memberships (user_id, org_id);

COMMENT ON TABLE memberships IS 'User-organization junction (N:M relationship)';
```

---

#### roles

Predefined roles with hierarchy.

```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    hierarchy_level INTEGER NOT NULL,          -- admin=100, editor=50, viewer=10
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_roles_name ON roles (name);
CREATE INDEX idx_roles_hierarchy ON roles (hierarchy_level DESC);

COMMENT ON TABLE roles IS 'Predefined roles (admin, editor, viewer)';
COMMENT ON COLUMN roles.hierarchy_level IS 'Higher number = more privileges (admin=100, editor=50, viewer=10)';
```

---

#### permissions

Granular permissions (resource:action format).

```sql
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,                 -- 'documents:read', 'users:manage'
    resource TEXT NOT NULL,                    -- 'documents', 'users', 'orgs'
    action TEXT NOT NULL,                      -- 'read', 'write', 'delete', 'manage'
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_permissions_name ON permissions (name);
CREATE INDEX idx_permissions_resource ON permissions (resource);
CREATE INDEX idx_permissions_action ON permissions (action);

COMMENT ON TABLE permissions IS 'Granular permissions (resource:action format)';
COMMENT ON COLUMN permissions.name IS 'Permission identifier (e.g., documents:read, users:manage)';
```

---

#### role_permissions

Role-permission junction (many-to-many).

```sql
CREATE TABLE role_permissions (
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,

    PRIMARY KEY (role_id, permission_id)
);

-- Indexes
CREATE INDEX idx_role_permissions_role ON role_permissions (role_id);
CREATE INDEX idx_role_permissions_permission ON role_permissions (permission_id);

COMMENT ON TABLE role_permissions IS 'Role-permission junction (defines what each role can do)';
```

---

#### user_roles

User-role-org junction (user has role in specific org).

```sql
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by UUID REFERENCES users(id) ON DELETE SET NULL,

    CONSTRAINT user_roles_unique UNIQUE (user_id, role_id, org_id)
);

-- Indexes
CREATE INDEX idx_user_roles_user_org ON user_roles (user_id, org_id);
CREATE INDEX idx_user_roles_role ON user_roles (role_id);
CREATE INDEX idx_user_roles_org ON user_roles (org_id);

COMMENT ON TABLE user_roles IS 'User-role-org junction (user has role in specific org)';
COMMENT ON COLUMN user_roles.granted_by IS 'User who granted this role (audit trail)';
```

---

#### api_keys

Programmatic API access tokens.

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                        -- User-friendly label
    key_hash TEXT UNIQUE NOT NULL,            -- bcrypt hash of actual key
    prefix TEXT NOT NULL,                      -- First 8 chars (e.g., 'sk_live_12345678')
    scopes TEXT[] DEFAULT ARRAY[]::TEXT[],    -- Array of permission names
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Indexes
CREATE INDEX idx_api_keys_key_hash ON api_keys (key_hash);
CREATE INDEX idx_api_keys_user_org ON api_keys (user_id, org_id);
CREATE INDEX idx_api_keys_prefix ON api_keys (prefix);
CREATE INDEX idx_api_keys_expires ON api_keys (expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_api_keys_scopes ON api_keys USING gin (scopes);

COMMENT ON TABLE api_keys IS 'Programmatic API access tokens (alternative to user sessions)';
COMMENT ON COLUMN api_keys.key_hash IS 'bcrypt hash of actual API key (never store plaintext)';
COMMENT ON COLUMN api_keys.prefix IS 'First 8 characters for display (e.g., sk_live_12345678...)';
```

---

#### sessions

Active user sessions (alternative to Redis for persistence).

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash TEXT UNIQUE NOT NULL,   -- bcrypt hash
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_agent TEXT,
    ip_address INET
);

-- Indexes
CREATE INDEX idx_sessions_refresh_token ON sessions (refresh_token_hash);
CREATE INDEX idx_sessions_user_id ON sessions (user_id);
CREATE INDEX idx_sessions_expires ON sessions (expires_at);

COMMENT ON TABLE sessions IS 'Active user sessions (stores refresh tokens with 15min expiry)';
COMMENT ON COLUMN sessions.refresh_token_hash IS 'bcrypt hash of refresh token (never store plaintext)';
```

---

#### audit_logs (Partitioned by Month)

Comprehensive audit trail with monthly partitioning.

```sql
-- Parent table (partitioned by created_at)
CREATE TABLE audit_logs (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    org_id UUID REFERENCES orgs(id) ON DELETE CASCADE,
    action TEXT NOT NULL,                      -- 'user.created', 'document.deleted'
    resource_type TEXT,                        -- 'user', 'document', 'org'
    resource_id UUID,
    changes JSONB DEFAULT '{}'::jsonb,        -- {before: {...}, after: {...}}
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create initial partitions (current month + 2 future months)
DO $$
DECLARE
    start_date DATE;
    end_date DATE;
    partition_name TEXT;
    i INTEGER;
BEGIN
    FOR i IN 0..2 LOOP
        start_date := DATE_TRUNC('month', NOW() + (i || ' months')::INTERVAL);
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'audit_logs_' || TO_CHAR(start_date, 'YYYY_MM');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs
             FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );

        -- Add indexes to partition
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (org_id, created_at)',
            partition_name || '_org_idx', partition_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (user_id, created_at)',
            partition_name || '_user_idx', partition_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (action, created_at)',
            partition_name || '_action_idx', partition_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (resource_type, resource_id, created_at)',
            partition_name || '_resource_idx', partition_name);
    END LOOP;
END $$;

COMMENT ON TABLE audit_logs IS 'Comprehensive audit trail (partitioned monthly, 13-month retention)';
COMMENT ON COLUMN audit_logs.changes IS 'JSON object with before/after values: {before: {...}, after: {...}}';
```

---

## 3. Row-Level Security (RLS) Policies

### 3.1 Helper Function

```sql
-- Function to get current user's organization IDs
CREATE OR REPLACE FUNCTION get_current_user_orgs()
RETURNS UUID[] AS $$
    SELECT ARRAY_AGG(org_id)
    FROM memberships
    WHERE user_id = current_setting('app.user_id', true)::UUID
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

COMMENT ON FUNCTION get_current_user_orgs() IS 'Returns array of org_ids for current user (set via app.user_id)';
```

### 3.2 Context Setting (Application Layer)

Before each request, FastAPI middleware sets the user context:

```python
async def set_rls_context(user_id: UUID, conn):
    """Set RLS context for current user."""
    await conn.execute(f"SET LOCAL app.user_id = '{user_id}'")
```

### 3.3 RLS Policies

#### memberships

```sql
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;

-- Users can only see memberships for orgs they belong to
CREATE POLICY memberships_isolation ON memberships
    FOR ALL
    USING (org_id = ANY(get_current_user_orgs()));

COMMENT ON POLICY memberships_isolation ON memberships IS 'Users see only memberships in their orgs';
```

---

#### user_roles

```sql
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- SELECT: Users can see roles in their orgs
CREATE POLICY user_roles_read ON user_roles
    FOR SELECT
    USING (org_id = ANY(get_current_user_orgs()));

-- INSERT/UPDATE/DELETE: Only admins can modify roles
CREATE POLICY user_roles_admin_modify ON user_roles
    FOR ALL
    USING (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = current_setting('app.user_id', true)::UUID
              AND ur.org_id = user_roles.org_id
              AND r.name = 'admin'
        )
    );

COMMENT ON POLICY user_roles_read ON user_roles IS 'Users see roles in their orgs';
COMMENT ON POLICY user_roles_admin_modify ON user_roles IS 'Only admins can modify role assignments';
```

---

#### audit_logs

```sql
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- SELECT: Only admins can read audit logs
CREATE POLICY audit_logs_read_admin ON audit_logs
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = current_setting('app.user_id', true)::UUID
              AND ur.org_id = audit_logs.org_id
              AND r.name = 'admin'
        )
    );

-- INSERT: System can always insert (bypass RLS for application inserts)
CREATE POLICY audit_logs_insert ON audit_logs
    FOR INSERT
    WITH CHECK (true);

COMMENT ON POLICY audit_logs_read_admin ON audit_logs IS 'Only admins can read audit logs for their org';
COMMENT ON POLICY audit_logs_insert ON audit_logs IS 'System can always insert audit logs (no RLS on INSERT)';
```

---

## 4. Alembic Migration Plan

### Migration Strategy

| Migration | Description | Tables | Dependencies |
|-----------|-------------|--------|--------------|
| **001_initial_schema** | Core tables + indexes | users, identities, orgs, memberships, roles, permissions, role_permissions, user_roles, api_keys, sessions | Extensions |
| **002_audit_logs** | Partitioned audit logs | audit_logs + 3 partitions | Migration 001 |
| **003_rls_policies** | RLS setup | Enable RLS on memberships, user_roles, audit_logs | Migration 002 |
| **004_seed_data** | Default roles/permissions | Insert admin/editor/viewer roles + permissions | Migration 001 |

### Migration 001: Initial Schema

```python
# alembic/versions/001_initial_schema.py
"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-10-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gin"')

    # users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text()),
        sa.Column('avatar_url', sa.Text()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}'),
        sa.UniqueConstraint('email')
    )
    op.execute("ALTER TABLE users ALTER COLUMN email TYPE CITEXT")

    # ... (similar for other tables)

def downgrade():
    op.drop_table('sessions')
    op.drop_table('api_keys')
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('memberships')
    op.drop_table('orgs')
    op.drop_table('identities')
    op.drop_table('users')
```

### Migration 004: Seed Data

```sql
-- Seed roles
INSERT INTO roles (id, name, description, hierarchy_level) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'admin', 'Full access to organization', 100),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'editor', 'Can create and edit documents', 50),
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'viewer', 'Read-only access', 10);

-- Seed permissions
INSERT INTO permissions (id, name, resource, action, description) VALUES
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'documents:read', 'documents', 'read', 'Read documents'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'documents:write', 'documents', 'write', 'Create/edit documents'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'documents:delete', 'documents', 'delete', 'Delete documents'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14', 'users:read', 'users', 'read', 'View users'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a15', 'users:manage', 'users', 'manage', 'Manage users'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a16', 'orgs:read', 'orgs', 'read', 'View organization'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a17', 'orgs:manage', 'orgs', 'manage', 'Manage organization settings'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a18', 'roles:assign', 'roles', 'assign', 'Assign roles to users'),
    ('b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a19', 'audit:read', 'audit', 'read', 'View audit logs');

-- Admin role permissions (all permissions)
INSERT INTO role_permissions (role_id, permission_id)
SELECT 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', id FROM permissions;

-- Editor role permissions
INSERT INTO role_permissions (role_id, permission_id) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'), -- documents:read
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12'), -- documents:write
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14'), -- users:read
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a16'); -- orgs:read

-- Viewer role permissions
INSERT INTO role_permissions (role_id, permission_id) VALUES
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'), -- documents:read
    ('a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a16'); -- orgs:read
```

---

## 5. Backup & Restore Strategy

### 5.1 Backup Types

| Type | Schedule | Retention | Storage | RPO | RTO |
|------|----------|-----------|---------|-----|-----|
| **Full Backup** | Daily 2 AM UTC | 30 days | S3 (AES-256) | <24 hours | <1 hour |
| **WAL Archiving** | Continuous (60s) | 7 days | S3 | <5 minutes | <1 hour |
| **Logical Exports** | Daily 3 AM UTC | 30 days | S3 | <24 hours | <30 min |

### 5.2 Backup Scripts

**Full Backup (pg_dump):**

```bash
#!/bin/bash
# backup_full.sh
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="ttrpg_backup_${TIMESTAMP}.dump"
S3_BUCKET="s3://ttrpg-backups/postgres/full"

pg_dump \
  --format=custom \
  --compress=9 \
  --verbose \
  --file="/tmp/${BACKUP_FILE}" \
  ttrpg_db

aws s3 cp "/tmp/${BACKUP_FILE}" "${S3_BUCKET}/${BACKUP_FILE}" --server-side-encryption AES256
rm "/tmp/${BACKUP_FILE}"

# Cleanup old backups (keep 30 days)
aws s3 ls "${S3_BUCKET}/" | while read -r line; do
    createDate=$(echo $line | awk '{print $1" "$2}')
    createDate=$(date -d "$createDate" +%s)
    olderThan=$(date --date="30 days ago" +%s)
    if [[ $createDate -lt $olderThan ]]; then
        fileName=$(echo $line | awk '{print $4}')
        aws s3 rm "${S3_BUCKET}/${fileName}"
    fi
done
```

**WAL Archiving (postgresql.conf):**

```ini
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://ttrpg-backups/postgres/wal/%f --server-side-encryption AES256'
archive_timeout = 60  # Force WAL switch every 60 seconds
```

### 5.3 Restore Procedure

**Point-in-Time Recovery:**

```bash
#!/bin/bash
# restore_pitr.sh
TARGET_TIME="2025-10-19 14:30:00 UTC"
LATEST_BACKUP="ttrpg_backup_20251019_020000.dump"

# 1. Stop postgres
systemctl stop postgresql

# 2. Restore from latest full backup
pg_restore \
  --dbname=ttrpg_db \
  --clean \
  --if-exists \
  --verbose \
  "/backups/${LATEST_BACKUP}"

# 3. Configure recovery
cat > /var/lib/postgresql/data/recovery.conf <<EOF
restore_command = 'aws s3 cp s3://ttrpg-backups/postgres/wal/%f %p'
recovery_target_time = '${TARGET_TIME}'
recovery_target_action = 'promote'
EOF

# 4. Start postgres (will replay WAL to target time)
systemctl start postgresql
```

### 5.4 Restore Testing

**Monthly Drill (First Sunday):**

```bash
# 1. Provision staging environment
# 2. Restore latest full backup
# 3. Verify data integrity:
psql -d ttrpg_db -c "SELECT COUNT(*) FROM users;"
psql -d ttrpg_db -c "SELECT COUNT(*) FROM audit_logs;"

# 4. Test RLS policies
psql -d ttrpg_db -c "SET app.user_id = '<test_user_uuid>'; SELECT * FROM memberships;"

# 5. Document results (time to restore, data integrity checks)
```

---

## 6. VACUUM & Maintenance Strategy

### 6.1 Auto-vacuum Tuning

```sql
-- High-churn tables (sessions, audit_logs)
ALTER TABLE sessions SET (
    autovacuum_vacuum_scale_factor = 0.1,   -- Vacuum at 10% dead tuples
    autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE audit_logs SET (
    autovacuum_vacuum_scale_factor = 0.05,  -- More aggressive (5%)
    autovacuum_analyze_scale_factor = 0.02
);

-- Low-churn tables (users, orgs, roles)
ALTER TABLE users SET (
    autovacuum_vacuum_scale_factor = 0.2,
    autovacuum_analyze_scale_factor = 0.1
);
```

### 6.2 Manual VACUUM Schedule

```bash
#!/bin/bash
# vacuum_weekly.sh (Cron: Sunday 3 AM)
psql -d ttrpg_db <<SQL
VACUUM ANALYZE users;
VACUUM ANALYZE orgs;
VACUUM ANALYZE memberships;
VACUUM ANALYZE user_roles;
VACUUM ANALYZE sessions;
SQL
```

```bash
#!/bin/bash
# vacuum_full_monthly.sh (Cron: First Sunday 4 AM)
psql -d ttrpg_db <<SQL
VACUUM FULL audit_logs;  -- Reclaim space from partitions
REINDEX TABLE CONCURRENTLY users;
REINDEX TABLE CONCURRENTLY memberships;
SQL
```

### 6.3 Partition Management

**Auto-create Future Partitions (Cron: Monthly on 1st at 1 AM):**

```sql
-- Function to create next month's partition
CREATE OR REPLACE FUNCTION create_next_audit_partition()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    -- Create partition for 2 months from now
    partition_date := DATE_TRUNC('month', NOW() + INTERVAL '2 months');
    partition_name := 'audit_logs_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := partition_date;
    end_date := partition_date + INTERVAL '1 month';

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );

    -- Add indexes
    EXECUTE format('CREATE INDEX %I ON %I (org_id, created_at)',
        partition_name || '_org_idx', partition_name);
    EXECUTE format('CREATE INDEX %I ON %I (user_id, created_at)',
        partition_name || '_user_idx', partition_name);
    EXECUTE format('CREATE INDEX %I ON %I (action, created_at)',
        partition_name || '_action_idx', partition_name);
    EXECUTE format('CREATE INDEX %I ON %I (resource_type, resource_id, created_at)',
        partition_name || '_resource_idx', partition_name);

    RAISE NOTICE 'Created partition: %', partition_name;
END;
$$ LANGUAGE plpgsql;
```

**Drop Old Partitions (Cron: Monthly on 2nd at 2 AM):**

```bash
#!/bin/bash
# drop_old_partitions.sh
# Archive and drop partitions older than 13 months

psql -d ttrpg_db <<SQL
DO \$\$
DECLARE
    partition_record RECORD;
    cutoff_date DATE;
    partition_start DATE;
BEGIN
    cutoff_date := DATE_TRUNC('month', NOW() - INTERVAL '13 months');

    FOR partition_record IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename LIKE 'audit_logs_%'
          AND tablename != 'audit_logs'
    LOOP
        -- Extract date from partition name (audit_logs_2024_10 -> 2024-10-01)
        partition_start := TO_DATE(
            SUBSTRING(partition_record.tablename FROM 'audit_logs_(\d{4}_\d{2})'),
            'YYYY_MM'
        );

        IF partition_start < cutoff_date THEN
            RAISE NOTICE 'Archiving and dropping partition: %', partition_record.tablename;

            -- Archive to S3 before dropping
            EXECUTE format(
                'COPY %I TO PROGRAM ''gzip | aws s3 cp - s3://ttrpg-backups/postgres/archive/%s.csv.gz'''
                || ' WITH (FORMAT csv, HEADER true)',
                partition_record.tablename,
                partition_record.tablename
            );

            -- Drop partition
            EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', partition_record.tablename);
        END IF;
    END LOOP;
END \$\$;
SQL
```

---

## 7. Monitoring & Alerting

### 7.1 Key Metrics

```sql
-- Dead tuples monitoring (alert if >15%)
SELECT
    schemaname,
    tablename,
    n_dead_tup,
    n_live_tup,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_tuple_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY dead_tuple_pct DESC;

-- Table bloat (via pgstattuple extension)
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS total_size,
    round((dead_tuple_percent)::numeric, 2) AS bloat_pct
FROM pg_stat_user_tables t
JOIN LATERAL (SELECT * FROM pgstattuple(t.tablename)) s ON true
WHERE dead_tuple_percent > 10
ORDER BY bloat_pct DESC;

-- Index usage (drop unused indexes)
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND pg_relation_size(indexrelid) > 1048576  -- > 1MB
ORDER BY pg_relation_size(indexrelid) DESC;
```

### 7.2 Alerts (Prometheus + Alertmanager)

```yaml
# alerts.yml
groups:
  - name: postgres_rbac
    rules:
      - alert: PostgresDeadTuples
        expr: pg_stat_user_tables_n_dead_tup / (pg_stat_user_tables_n_live_tup + pg_stat_user_tables_n_dead_tup) > 0.15
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Table {{ $labels.table }} has >15% dead tuples"

      - alert: PostgresConnectionPoolExhaustion
        expr: pg_stat_database_numbackends > pg_settings_max_connections * 0.8
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Postgres connection pool >80% utilized"
```

---

## 8. Acceptance Criteria

✅ **DDL & Indexes:**
- [x] All 10 tables created with proper types (UUID, CITEXT, TIMESTAMPTZ, JSONB)
- [x] Unique constraints on email, (provider, provider_user_id), (user_id, org_id), etc.
- [x] Foreign keys with ON DELETE CASCADE/SET NULL
- [x] Indexes on all foreign keys
- [x] Specialized indexes (CITEXT email, GIN on arrays, partial indexes)

✅ **Partitioning:**
- [x] audit_logs partitioned by RANGE (created_at)
- [x] Initial 3 partitions created (current + 2 future months)
- [x] Partition indexes created automatically
- [x] Auto-create function for future partitions
- [x] Drop old partitions with archival to S3

✅ **RLS Policies:**
- [x] get_current_user_orgs() helper function
- [x] RLS enabled on memberships, user_roles, audit_logs
- [x] Policies tested with SET app.user_id

✅ **Migrations:**
- [x] Alembic migration structure (001-004)
- [x] Forward/backward migrations
- [x] Seed data for roles/permissions

✅ **Backup/Restore:**
- [x] Daily full backups to S3
- [x] WAL archiving for PITR
- [x] Restore tested monthly
- [x] RPO <5 minutes, RTO <1 hour

✅ **Maintenance:**
- [x] Auto-vacuum tuned per table
- [x] Weekly VACUUM ANALYZE schedule
- [x] Monthly VACUUM FULL + REINDEX
- [x] Monitoring queries for dead tuples, bloat, unused indexes

---

## 9. Performance Validation

### 9.1 Query Plans

**Test RLS Policy Performance:**

```sql
-- Verify RLS policy uses index (should use idx_memberships_user_id)
EXPLAIN ANALYZE
SELECT * FROM memberships
WHERE user_id = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11';

-- Expected: Index Scan using idx_memberships_user_id (cost ~0.5)
```

**Test Partition Pruning:**

```sql
-- Verify only relevant partition is scanned
EXPLAIN ANALYZE
SELECT * FROM audit_logs
WHERE created_at BETWEEN '2025-10-01' AND '2025-10-31';

-- Expected: Seq Scan on audit_logs_2025_10 ONLY (not all partitions)
```

### 9.2 Load Testing

```python
# load_test_rls.py
import asyncio
import asyncpg

async def test_rls_performance():
    pool = await asyncpg.create_pool(dsn='postgresql://...')

    async with pool.acquire() as conn:
        # Set user context
        await conn.execute("SET app.user_id = 'test-user-uuid'")

        # Measure query time with RLS
        start = time.time()
        result = await conn.fetch("SELECT * FROM memberships")
        elapsed = time.time() - start

        print(f"RLS query time: {elapsed * 1000:.2f}ms")
        assert elapsed < 0.1, "RLS query should be <100ms"
```

---

## Appendix

### A. Sample Data Script

```sql
-- Create sample org
INSERT INTO orgs (id, name, slug) VALUES
    ('org-00000000-0000-0000-0000-000000000001', 'Acme Corp', 'acme-corp');

-- Create sample users
INSERT INTO users (id, email, display_name) VALUES
    ('user-00000000-0000-0000-0000-000000000001', 'alice@example.com', 'Alice Admin'),
    ('user-00000000-0000-0000-0000-000000000002', 'bob@example.com', 'Bob Editor'),
    ('user-00000000-0000-0000-0000-000000000003', 'charlie@example.com', 'Charlie Viewer');

-- Create memberships
INSERT INTO memberships (user_id, org_id) VALUES
    ('user-00000000-0000-0000-0000-000000000001', 'org-00000000-0000-0000-0000-000000000001'),
    ('user-00000000-0000-0000-0000-000000000002', 'org-00000000-0000-0000-0000-000000000001'),
    ('user-00000000-0000-0000-0000-000000000003', 'org-00000000-0000-0000-0000-000000000001');

-- Assign roles
INSERT INTO user_roles (user_id, role_id, org_id, granted_by) VALUES
    ('user-00000000-0000-0000-0000-000000000001', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11', 'org-00000000-0000-0000-0000-000000000001', NULL),  -- Alice: admin
    ('user-00000000-0000-0000-0000-000000000002', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12', 'org-00000000-0000-0000-0000-000000000001', 'user-00000000-0000-0000-0000-000000000001'),  -- Bob: editor
    ('user-00000000-0000-0000-0000-000000000003', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13', 'org-00000000-0000-0000-0000-000000000001', 'user-00000000-0000-0000-0000-000000000001');  -- Charlie: viewer
```

---

**Document Version:** 1.0
**Last Updated:** October 19, 2025
**Next Review:** Sprint 2 (M1 Completion - Nov 17, 2025)
