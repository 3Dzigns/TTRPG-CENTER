# WebUI Backend Integration Plan

## Executive Summary

The WebUI is currently using mock data instead of connecting to real backend databases. This document provides a comprehensive analysis and implementation roadmap to wire up the full backend connections.

**Issue Date**: 2025-11-06
**Status**: Planning Phase
**Priority**: HIGH
**Complexity**: Medium-High

---

## Problem Analysis

### Current State

#### ✅ What's Working
1. **Authentication System**: Fully functional with PostgreSQL backend
   - Tables: `auth_users`, `auth_sessions`, `auth_roles`, `auth_user_roles`, `auth_oauth_accounts`
   - Connection: `postgres://ttrpg:ttrpg@127.0.0.1:5432/ttrpg_auth`
   - Status: ✅ Deployed and operational

2. **Frontend Infrastructure**: Complete Next.js 14 application
   - React Query for data fetching
   - API client package (`@ttrpg-center/api`)
   - TypeScript types package (`@ttrpg-center/types`)
   - Status: ✅ Fully implemented

3. **Cassandra Vector Database**: Deployed for RAG/embeddings
   - Keyspace: `ttrpg_vectors`
   - Table: `embeddings` with vector search
   - Status: ✅ Operational but not connected to WebUI

#### ❌ What's Broken

**All data-driven features are using mock data:**

1. **Mock API Endpoints** (apps/web/app/api/mock/)
   - `/api/mock/characters` → Hard-coded character data
   - `/api/mock/games` → Hard-coded game data
   - `/api/mock/sources` → Hard-coded source data
   - `/api/mock/usage` → Hard-coded usage metrics
   - `/api/mock/me` → Hard-coded user profile

2. **Real API Endpoints Also Using Mock Data** (apps/web/app/api/v1/)
   - `/api/v1/characters/route.ts` imports `MOCK_CHARACTERS`
   - `/api/v1/games/route.ts` imports `MOCK_GAMES`
   - `/api/v1/sources/route.ts` imports `MOCK_SOURCES`
   - `/api/v1/usage/route.ts` imports mock usage data

3. **Missing Database Tables**
   - No `games` table in PostgreSQL
   - No `characters` table in PostgreSQL
   - No `sources` table in PostgreSQL
   - No `usage_metrics` table in PostgreSQL
   - No `game_members` table in PostgreSQL

### Root Cause

**Developer implemented UI-first development approach:**
- Created mock data for rapid prototyping (apps/web/app/api/_shared/mock-data.ts)
- Built all UI components against mock endpoints
- Never migrated to real database connections
- Both `/api/mock/` and `/api/v1/` endpoints return mock data

---

## Architecture Analysis

### Current Data Flow (MOCK)
```
Frontend Components
  ↓ (React Query)
API Client (@ttrpg-center/api)
  ↓ (fetch /api/v1/*)
Next.js API Routes
  ↓ (import MOCK_DATA)
apps/web/app/api/_shared/mock-data.ts
  ↓ (returns static arrays)
Hard-coded Mock Objects
```

### Target Data Flow (REAL)
```
Frontend Components
  ↓ (React Query)
API Client (@ttrpg-center/api)
  ↓ (fetch /api/v1/*)
Next.js API Routes
  ↓ (Drizzle ORM queries)
PostgreSQL Database
  ↓ (SQL queries)
Real Database Tables
```

### Database Architecture

#### PostgreSQL (Primary Application Database)
**Purpose**: Structured relational data for games, characters, users, sources

**Required Tables:**
1. `games` - Game sessions and campaigns
2. `characters` - Player characters
3. `sources` - Source books and materials
4. `game_members` - Game membership and roles
5. `game_sources` - Game-to-source relationships
6. `usage_metrics` - Usage tracking and quotas

#### Cassandra (Vector Database)
**Purpose**: RAG embeddings and semantic search
**Current Status**: ✅ Deployed but isolated from WebUI
**Connection Point**: Query API endpoint for semantic search

#### Neo4j (Knowledge Graph)
**Purpose**: Relationship mapping and content connections
**Current Status**: Deployed (credentials in .env)
**Integration**: Future phase (not in scope for this plan)

---

## Implementation Roadmap

### Phase 1: Database Schema Design & Migration (Priority: CRITICAL)

**Estimated Time**: 4-6 hours

#### Task 1.1: Design PostgreSQL Schema
**File**: `apps/web/db/migrations/002_games_and_content.sql`

```sql
-- Games table
CREATE TABLE IF NOT EXISTS games (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT,
    status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'archived')),
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

-- Game members table
CREATE TABLE IF NOT EXISTS game_members (
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('gm', 'co-gm', 'player', 'spectator')),
    status TEXT NOT NULL CHECK (status IN ('active', 'invited', 'removed')),
    invited_at TIMESTAMPTZ,
    joined_at TIMESTAMPTZ,
    PRIMARY KEY (game_id, user_id)
);

-- Characters table
CREATE TABLE IF NOT EXISTS characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    owner_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    portrait_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    system TEXT NOT NULL DEFAULT 'dnd-5e',
    game_id UUID REFERENCES games(id) ON DELETE SET NULL
);

-- Sources table
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK (category IN ('campaign', 'module', 'expansion', 'ruleset', 'homebrew')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User-owned sources (many-to-many)
CREATE TABLE IF NOT EXISTS user_sources (
    user_id UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, source_id)
);

-- Game sources (many-to-many)
CREATE TABLE IF NOT EXISTS game_sources (
    game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, source_id)
);

-- Character active sources (many-to-many)
CREATE TABLE IF NOT EXISTS character_sources (
    character_id UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    PRIMARY KEY (character_id, source_id)
);

-- Usage metrics table
CREATE TABLE IF NOT EXISTS usage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope TEXT NOT NULL CHECK (scope IN ('user', 'game')),
    entity_id UUID NOT NULL,
    total_seconds_played INTEGER NOT NULL DEFAULT 0,
    monthly_session_count INTEGER NOT NULL DEFAULT 0,
    automation_credits_remaining INTEGER NOT NULL DEFAULT 0,
    text_assist_remaining INTEGER,
    audio_bridge_remaining INTEGER,
    discord_bridge_remaining INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scope, entity_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_games_gm_id ON games(gm_id);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_game_members_user_id ON game_members(user_id);
CREATE INDEX IF NOT EXISTS idx_characters_owner_id ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_characters_game_id ON characters(game_id);
CREATE INDEX IF NOT EXISTS idx_usage_metrics_scope_entity ON usage_metrics(scope, entity_id);
```

#### Task 1.2: Update Drizzle Schema
**File**: `apps/web/db/schema.ts`

Add table definitions using Drizzle ORM syntax to match the SQL schema above.

#### Task 1.3: Seed Initial Data
**File**: `apps/web/db/seeds/002_seed_content.sql`

Convert mock data to database seed data:
- 3 sample sources
- 2 sample games
- 2 sample characters
- Sample usage metrics

#### Task 1.4: Run Migrations
```bash
cd apps/web
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -f db/migrations/002_games_and_content.sql
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -f db/seeds/002_seed_content.sql
```

---

### Phase 2: API Endpoint Replacement (Priority: HIGH)

**Estimated Time**: 6-8 hours

#### Task 2.1: Replace Characters Endpoint
**File**: `apps/web/app/api/v1/characters/route.ts`

**Before** (Mock):
```typescript
import { MOCK_CHARACTERS } from "../../_shared/mock-data";
export async function GET(request: NextRequest) {
  let data = MOCK_CHARACTERS;
  return NextResponse.json(data);
}
```

**After** (Real):
```typescript
import { db } from "../../../lib/db";
import { characters, characterSources } from "../../../db/schema";
import { eq } from "drizzle-orm";

export async function GET(request: NextRequest) {
  const userId = request.nextUrl.searchParams.get("userId");
  const gameId = request.nextUrl.searchParams.get("gameId");

  let query = db.select().from(characters);

  if (userId && userId !== "all") {
    query = query.where(eq(characters.ownerId, userId));
  }
  if (gameId) {
    query = query.where(eq(characters.gameId, gameId));
  }

  const data = await query;
  return NextResponse.json(data);
}
```

#### Task 2.2: Replace Games Endpoint
**File**: `apps/web/app/api/v1/games/route.ts`

Implement:
- GET /api/v1/games - List games with members
- POST /api/v1/games - Create game
- GET /api/v1/games/[id] - Get game details
- PATCH /api/v1/games/[id] - Update game
- DELETE /api/v1/games/[id] - Delete game

#### Task 2.3: Replace Sources Endpoint
**File**: `apps/web/app/api/v1/sources/route.ts`

Implement:
- GET /api/v1/sources?owned=true - List sources with ownership filter
- Join with user_sources table for ownership data

#### Task 2.4: Replace Usage Endpoint
**File**: `apps/web/app/api/v1/usage/route.ts`

Implement:
- GET /api/v1/usage?scope=user&id=xxx - Get usage metrics
- GET /api/v1/usage?scope=game&id=xxx - Get game usage

#### Task 2.5: Replace Me Endpoint
**File**: `apps/web/app/api/v1/me/route.ts`

Enhance to include:
- Real usage metrics from usage_metrics table
- User preferences (theme stored in new column)

#### Task 2.6: Delete Mock Endpoints
**Action**: Remove entire directory tree
```bash
rm -rf apps/web/app/api/mock/
rm apps/web/app/api/_shared/mock-data.ts
```

---

### Phase 3: Game Management Endpoints (Priority: HIGH)

**Estimated Time**: 4-6 hours

#### Task 3.1: Game Members API
**File**: `apps/web/app/api/v1/games/[id]/members/route.ts`

Implement:
- POST - Invite member
- PATCH /[userId] - Update member role
- DELETE /[userId] - Remove member

#### Task 3.2: Game Sources API
**File**: `apps/web/app/api/v1/games/[id]/sources/route.ts`

Implement:
- POST - Add source to game
- DELETE /[sourceId] - Remove source from game

#### Task 3.3: Join Game API
**File**: `apps/web/app/api/v1/games/join/route.ts`

Implement:
- POST - Join game by invite code

---

### Phase 4: Character Management Endpoints (Priority: MEDIUM)

**Estimated Time**: 3-4 hours

#### Task 4.1: Character CRUD
**Files**: `apps/web/app/api/v1/characters/[id]/route.ts`

Implement:
- PATCH /api/v1/characters/[id] - Update character
- DELETE /api/v1/characters/[id] - Delete character

#### Task 4.2: Character Sources
Handle activeSourceIds in character updates by managing character_sources join table.

---

### Phase 5: Admin & Advanced Features (Priority: LOW)

**Estimated Time**: 4-6 hours

#### Task 5.1: Admin Health Endpoint
**File**: `apps/web/app/api/v1/admin/health/route.ts`

Connect to:
- PostgreSQL health check
- Cassandra health check
- Neo4j health check (future)

#### Task 5.2: Admin Audit Log
**File**: `apps/web/app/api/v1/admin/audit/route.ts`

Create audit_log table and implement tracking.

#### Task 5.3: Admin Source Management
**File**: `apps/web/app/api/v1/admin/source/route.ts`

Implement source CRUD operations with admin authorization.

#### Task 5.4: Admin Override System
**File**: `apps/web/app/api/v1/admin/override/route.ts`

Implement direct database override capability with audit trail.

---

### Phase 6: Query API Integration (Priority: MEDIUM)

**Estimated Time**: 6-8 hours

#### Task 6.1: Connect to Cassandra Vector Store
**File**: `apps/web/app/api/v1/query/route.ts`

Implement:
- Query request processing
- Cassandra vector similarity search
- OpenAI embeddings generation
- RAG response generation

**Connection Details:**
- Cassandra Host: docker-cassandra_upsert-1, ttrpg_cassandra
- Keyspace: ttrpg_vectors
- Table: embeddings

#### Task 6.2: Query Event Streaming
**File**: `apps/web/app/api/v1/events/route.ts`

Implement Server-Sent Events (SSE) for real-time query status updates.

---

### Phase 7: Testing & Validation (Priority: CRITICAL)

**Estimated Time**: 6-8 hours

#### Task 7.1: API Integration Tests
**File**: `apps/web/app/api/v1/**/__tests__/route.test.ts`

Create tests for:
- All GET endpoints
- All POST/PATCH/DELETE endpoints
- Error handling
- Authorization checks

#### Task 7.2: Frontend Component Tests
**File**: `apps/web/components/**/__tests__/*.test.tsx`

Update tests to:
- Mock real API responses (not mock data)
- Test error states
- Test loading states

#### Task 7.3: E2E Tests
**File**: `apps/web/e2e/**/*.spec.ts`

Create Playwright tests for:
- Game creation flow
- Character creation flow
- Game joining flow
- Query submission flow

#### Task 7.4: Manual QA Checklist
1. ✅ User can sign in and see real dashboard data
2. ✅ User can create a new game
3. ✅ User can invite members to game
4. ✅ User can create characters
5. ✅ User can link characters to games
6. ✅ User can view sources and mark as owned
7. ✅ User can submit queries and see results
8. ✅ Admin can view system health
9. ✅ Admin can manage sources
10. ✅ Usage metrics display correctly

---

### Phase 8: Deployment & Migration (Priority: HIGH)

**Estimated Time**: 2-4 hours

#### Task 8.1: Environment Configuration
**File**: `webui/.env.docker`

Ensure:
- AUTH_DATABASE_URL points to correct database
- CASSANDRA connection strings configured
- OpenAI API key configured

#### Task 8.2: Docker Compose Updates
**File**: `webui/Dockerfile`

Already configured correctly - no changes needed.

#### Task 8.3: Database Backup
```bash
docker exec ttrpg_postgres pg_dump -U ttrpg ttrpg_auth > backup_pre_integration.sql
```

#### Task 8.4: Production Deployment
```bash
cd webui
docker build -t ttrpg-webui:latest .
docker-compose up -d
```

---

## Risk Assessment

### High Risk Items
1. **Data Loss**: Migration could fail → Mitigation: Full backup before changes
2. **Breaking Changes**: API changes break frontend → Mitigation: Comprehensive testing
3. **Performance**: Database queries slower than mock → Mitigation: Proper indexing

### Medium Risk Items
1. **Cassandra Integration**: Vector search untested → Mitigation: Separate testing phase
2. **User Sessions**: Auth issues during transition → Mitigation: Staged rollout
3. **Missing Features**: Discover additional gaps → Mitigation: Iterative approach

### Low Risk Items
1. **Theme Preferences**: Minor UI persistence issue → Mitigation: Add later
2. **Audit Logging**: Nice-to-have feature → Mitigation: Phase 5 (low priority)

---

## Success Criteria

### Phase Completion Checklist
- [ ] All database tables created and seeded
- [ ] All API endpoints return real data
- [ ] All mock endpoints deleted
- [ ] All integration tests passing
- [ ] All E2E tests passing
- [ ] Manual QA checklist 100% complete
- [ ] WebUI deployed and accessible
- [ ] No console errors in browser
- [ ] Performance within acceptable range (<500ms for most queries)

### Validation Steps
1. Delete all mock data files
2. Restart WebUI container
3. Sign in and verify all pages load
4. Create test game with real data
5. Create test character with real data
6. Submit test query and verify response
7. Check PostgreSQL for new records
8. Verify Cassandra connection works

---

## Dependencies

### External Services
- ✅ PostgreSQL (ttrpg_postgres container) - Running
- ✅ Cassandra (docker-cassandra_upsert-1, ttrpg_cassandra) - Running
- ⚠️ OpenAI API (for embeddings) - API key in .env, needs validation

### Internal Packages
- ✅ @ttrpg-center/types - Complete
- ✅ @ttrpg-center/api - Complete
- ✅ @ttrpg-center/ui - Complete
- ✅ Drizzle ORM - Installed and configured

### Tools Required
- Docker & Docker Compose
- Node.js 20+
- pnpm 9+
- PostgreSQL client (docker exec)

---

## Timeline Estimate

### Optimistic (Single Developer, Full-Time)
- Phase 1-2: 2 days
- Phase 3-4: 2 days
- Phase 5-6: 2 days
- Phase 7-8: 1 day
- **Total: 7 days**

### Realistic (Single Developer, Part-Time)
- Phase 1-2: 4 days
- Phase 3-4: 3 days
- Phase 5-6: 3 days
- Phase 7-8: 2 days
- **Total: 12 days**

### With Team (2-3 Developers)
- All phases parallel: 3-4 days
- **Total: 4 days**

---

## Next Steps

### Immediate Actions (Today)
1. ✅ Review this plan with team
2. ✅ Backup current database
3. ⏳ Start Phase 1, Task 1.1 (schema design)
4. ⏳ Set up development branch: `feature/real-backend-integration`

### This Week
1. Complete Phase 1 (Database Schema)
2. Complete Phase 2 (API Replacement)
3. Begin Phase 3 (Game Management)

### Next Week
1. Complete Phase 3-4
2. Begin Phase 5-6
3. Start testing phase

---

## Questions for Product Owner

1. **Priority Clarification**: Should we focus on specific features first? (e.g., Games before Query API)
2. **Migration Strategy**: Can we do phased rollout or need complete migration?
3. **Data Migration**: Do we need to preserve any existing mock data as real data?
4. **Cassandra Integration**: Is vector search a must-have for v1.0 or can it be v1.1?
5. **Admin Features**: How critical is the admin override panel vs. basic CRUD?

---

## Conclusion

The WebUI has strong foundations with authentication working correctly and all frontend infrastructure in place. The primary issue is that **all API endpoints are returning mock data** instead of querying real databases.

The fix requires:
1. Creating PostgreSQL tables for games, characters, sources, and usage
2. Replacing all mock data returns with real Drizzle ORM queries
3. Integrating Cassandra for the query/RAG functionality
4. Comprehensive testing to ensure data integrity

**Estimated effort: 7-12 developer days** depending on team size and availability.

The good news: The architecture is sound, and this is primarily a "wiring up" exercise rather than a redesign. All the pieces exist; they just need to be connected properly.
