# Backend Integration Task List

## Quick Reference - Action Items

### 🔴 Critical Path (Must Complete in Order)

#### Week 1: Database Foundation

**Day 1-2: Database Schema**
- [ ] Create `apps/web/db/migrations/002_games_and_content.sql`
  - Games table with all columns
  - Characters table
  - Sources table
  - Game members (many-to-many)
  - User sources (many-to-many)
  - Game sources (many-to-many)
  - Character sources (many-to-many)
  - Usage metrics table
  - All indexes

- [ ] Update `apps/web/db/schema.ts` with Drizzle definitions
  - Import all new tables
  - Define relationships
  - Export table types

- [ ] Create `apps/web/db/seeds/002_seed_content.sql`
  - Convert mock sources to seed data
  - Convert mock games to seed data
  - Convert mock characters to seed data
  - Create sample usage metrics

- [ ] Run migrations
  ```bash
  docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -f db/migrations/002_games_and_content.sql
  docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -f db/seeds/002_seed_content.sql
  ```

- [ ] Verify tables created
  ```bash
  docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "\dt"
  ```

**Day 3-4: Core API Endpoints**

- [ ] `apps/web/app/api/v1/characters/route.ts`
  - Replace MOCK_CHARACTERS import
  - Implement GET with Drizzle query
  - Add userId filter
  - Add gameId filter
  - Implement POST for character creation
  - Test with curl/Postman

- [ ] `apps/web/app/api/v1/characters/[id]/route.ts`
  - Implement GET by ID
  - Implement PATCH for updates
  - Implement DELETE
  - Handle character_sources join table

- [ ] `apps/web/app/api/v1/games/route.ts`
  - Replace MOCK_GAMES import
  - Implement GET with members join
  - Implement POST for game creation
  - Test game creation flow

- [ ] `apps/web/app/api/v1/games/[id]/route.ts`
  - Implement GET by ID
  - Implement PATCH for updates
  - Implement DELETE with cascade
  - Load full game with members and sources

- [ ] `apps/web/app/api/v1/sources/route.ts`
  - Replace MOCK_SOURCES import
  - Implement GET with ownership join
  - Filter by owned parameter
  - Test source listing

- [ ] `apps/web/app/api/v1/usage/route.ts`
  - Replace mock usage data
  - Implement GET with scope filter
  - Query usage_metrics table
  - Handle user and game scopes

- [ ] `apps/web/app/api/v1/me/route.ts`
  - Keep auth_users query
  - Add usage_metrics join
  - Add user preferences
  - Implement PATCH for profile updates

#### Week 2: Game Management & Testing

**Day 5-6: Game Management APIs**

- [ ] `apps/web/app/api/v1/games/[id]/members/route.ts`
  - Implement POST to invite member
  - Implement PATCH to update role
  - Implement DELETE to remove member
  - Validate permissions (only GM can modify)

- [ ] `apps/web/app/api/v1/games/[id]/sources/route.ts`
  - Implement POST to add source
  - Implement DELETE to remove source
  - Update game_sources join table

- [ ] `apps/web/app/api/v1/games/join/route.ts`
  - Implement POST with invite code
  - Validate invite code exists
  - Add user to game_members
  - Return full game object

**Day 7: Cleanup & Validation**

- [ ] Delete mock endpoints
  ```bash
  rm -rf apps/web/app/api/mock/
  rm apps/web/app/api/_shared/mock-data.ts
  ```

- [ ] Update tests to use real API
  - Fix failing tests in `__tests__` directories
  - Update test fixtures
  - Add integration tests

- [ ] Frontend validation
  - Sign in to WebUI
  - Navigate to each page
  - Verify no console errors
  - Test game creation
  - Test character creation

---

## 🟡 High Priority (Week 2-3)

### Query API Integration

- [ ] `apps/web/app/api/v1/query/route.ts`
  - Install cassandra-driver package
  - Connect to Cassandra cluster
  - Implement vector similarity search
  - Integrate OpenAI embeddings API
  - Return formatted results

- [ ] `apps/web/app/api/v1/events/route.ts`
  - Implement Server-Sent Events
  - Stream query progress updates
  - Handle connection management

### Admin Features

- [ ] `apps/web/app/api/v1/admin/health/route.ts`
  - PostgreSQL health check
  - Cassandra health check
  - Return service status

- [ ] `apps/web/app/api/v1/admin/source/route.ts`
  - Implement source CRUD
  - Add authorization checks
  - Create audit trail

---

## 🟢 Medium Priority (Week 3-4)

### Advanced Features

- [ ] Create audit_log table
- [ ] Implement audit trail for admin actions
- [ ] Add user preferences column to auth_users
- [ ] Implement theme preference persistence
- [ ] Add billing link generation logic
- [ ] Create usage quota enforcement

### Testing

- [ ] Write integration tests for all endpoints
- [ ] Create E2E tests with Playwright
- [ ] Load testing for query API
- [ ] Security audit of all endpoints

---

## 📋 SQL Scripts Needed

### 1. Migration Script (002_games_and_content.sql)

Location: `apps/web/db/migrations/002_games_and_content.sql`

**Tables to create:**
1. games
2. game_members
3. characters
4. sources
5. user_sources
6. game_sources
7. character_sources
8. usage_metrics

**Indexes to create:**
- idx_games_gm_id
- idx_games_status
- idx_game_members_user_id
- idx_characters_owner_id
- idx_characters_game_id
- idx_usage_metrics_scope_entity

### 2. Seed Script (002_seed_content.sql)

Location: `apps/web/db/seeds/002_seed_content.sql`

**Data to seed:**
- 3 sources (Lost Mines, Rise of Runelords, GM Library)
- 2 games (Shadows over Neverwinter, Echoes of Astral Sea)
- 2 characters (Elira Moonfall, Torren Blackroot)
- Usage metrics for both games and user

---

## 🔍 Verification Commands

### Check Tables Created
```bash
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "\dt"
```

### View Table Structure
```bash
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "\d games"
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "\d characters"
```

### Check Seed Data
```bash
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "SELECT * FROM games;"
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "SELECT * FROM characters;"
docker exec ttrpg_postgres psql -U ttrpg -d ttrpg_auth -c "SELECT * FROM sources;"
```

### Test API Endpoint
```bash
# Get user's characters
curl http://localhost:3000/api/v1/characters?userId=<user-id>

# Get all games
curl http://localhost:3000/api/v1/games

# Get sources
curl http://localhost:3000/api/v1/sources
```

---

## 🛠️ Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/real-backend-integration
```

### 2. Work in Small Commits
```bash
# After each task completion
git add .
git commit -m "feat: implement characters GET endpoint with real DB"
git push origin feature/real-backend-integration
```

### 3. Test Locally
```bash
# Start dev server
cd apps/web
pnpm dev

# In another terminal, test endpoints
curl http://localhost:3000/api/v1/characters
```

### 4. Run Tests
```bash
# Unit tests
pnpm test

# E2E tests
pnpm test:e2e
```

### 5. Create PR When Phase Complete
- Phase 1 complete → PR for review
- Phase 2 complete → PR for review
- Continue iteratively

---

## 📊 Progress Tracking

### Phase 1: Database Schema ⏳
- [ ] Migration script created
- [ ] Drizzle schema updated
- [ ] Seed script created
- [ ] Migrations run successfully
- [ ] Tables verified in database

### Phase 2: Core APIs ⏳
- [ ] Characters GET/POST implemented
- [ ] Characters PATCH/DELETE implemented
- [ ] Games GET/POST implemented
- [ ] Games PATCH/DELETE implemented
- [ ] Sources GET implemented
- [ ] Usage GET implemented
- [ ] Me GET/PATCH implemented

### Phase 3: Game Management ⏳
- [ ] Members POST/PATCH/DELETE implemented
- [ ] Sources POST/DELETE implemented
- [ ] Join game implemented

### Phase 4: Mock Cleanup ⏳
- [ ] Mock directory deleted
- [ ] Mock data file deleted
- [ ] All imports removed
- [ ] Tests updated

### Phase 5: Query Integration ⏳
- [ ] Cassandra connection established
- [ ] Vector search implemented
- [ ] OpenAI integration working
- [ ] Events streaming working

### Phase 6: Testing ⏳
- [ ] Integration tests passing
- [ ] E2E tests passing
- [ ] Manual QA complete
- [ ] Performance validated

### Phase 7: Deployment ✅
- [ ] Backup created
- [ ] Production deployed
- [ ] Smoke tests passing
- [ ] Monitoring configured

---

## 🚨 Blockers & Issues

**Track any blockers here:**

- [ ] Issue #1: _________________________
- [ ] Issue #2: _________________________
- [ ] Issue #3: _________________________

---

## 📝 Notes

- All development in `apps/web/` directory
- Database connection already configured: `postgres://ttrpg:ttrpg@127.0.0.1:5432/ttrpg_auth`
- Drizzle ORM already installed and configured
- Authentication system working - DO NOT MODIFY
- Focus on data layer integration only

---

## 🎯 Success Metrics

- [ ] Zero mock data in production
- [ ] All API endpoints return real data
- [ ] Database queries < 200ms average
- [ ] All tests passing (100% pass rate)
- [ ] Zero console errors in WebUI
- [ ] Can create/read/update/delete all entities
- [ ] Query API returns Cassandra results

---

**Last Updated**: 2025-11-06
**Status**: Planning Complete - Ready for Implementation
**Estimated Completion**: 7-12 developer days
