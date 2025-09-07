# FR-001: Local AuthZ/AuthN Store + Domain Links (SQLite + SQLModel + Alembic)

## Summary

Add a zero-cost, local system-of-record to manage credentials, OAuth linkages, roles/permissions, and domain relationships between Users, Games, GMs/Players, and Sources. Provide full CRUD via service layer and (optionally) FastAPI endpoints. Support schema evolution via Alembic.

## Goals

* Centralize identity + RBAC + domain links.
* Zero cost, local-first; swappable to Postgres later.
* Full CRUD for all entities and join relations.
* Safe migrations & seeding flows tied to CI.

## Non-Goals

* Building a full admin GUI (basic APIs are enough now).
* Multi-region HA database.

## High-Level Design

* **DB**: SQLite (WAL on), SQLModel/SQLAlchemy 2.x
* **Migrations**: Alembic autogenerate
* **Crypto**: passlib (hash), Fernet (optional token enc)
* **Key Entities**

  * `User`, `Role`, `Permission`, `UserRole`, `RolePermission`
  * `OAuthAccount` (provider linkage)
  * `Game`, `GameMembership (GM|Player)`
  * `Source`, `SourceAccess (included|alacarte|trial)`

## Deliverables / Feature Items

1. **DB bootstrap**

   * `db.py` engine factory (WAL, FK=ON), `init_db()`
   * `.env` support for `APP_DB_PATH`
2. **Models** in `models.py` (as above) with indices/uniques
3. **Migrations**

   * `alembic init db_migrations`
   * `env.py` wired to app models
   * First revision: `init schema`
   * Seed script for roles/permissions/admin user
4. **Service layer** (`services/…`)

   * Users: create/update/delete, role assignment
   * Roles/Permissions: CRUD + attach/detach
   * Games: CRUD + membership add/remove
   * Sources: CRUD + add/remove SourceAccess
5. **(Optional) FastAPI endpoints**

   * `/admin/users`, `/admin/roles`, `/sources`, `/games`
6. **Security**

   * Password hashing (bcrypt) if local login used
   * Optional Fernet encryption for refresh tokens
7. **Testing hooks**

   * Test DB path override; auto-migrate; teardown
   * Seed minimal fixtures

## Configuration

* `APP_DB_PATH=./data/app.db`
* `FERNET_KEY=<generated once>` (optional)

## User Stories

### US-DB-001 (Admin creates a GM)

**Given** an Admin is authenticated
**When** they submit new user info and select role GM
**Then** the system creates the `User`, assigns `gm` role, and returns the user id
**And** the action is persisted in SQLite

**Acceptance**: API returns 201 with new user id; DB row exists; role linkage exists.

---

### US-DB-002 (GM creates a game and invites players)

**Given** a GM is authenticated
**When** they POST a new `Game`
**Then** a row is created with `created_by_user_id=GM`
**And** the GM can add `GameMembership` rows for players with role\_in\_game=`Player`

**Acceptance**: Game row + membership rows exist; foreign keys enforced.

---

### US-DB-003 (Admin grants source access)

**Given** a User exists and a `Source` exists
**When** Admin grants `SourceAccess` with type `alacarte` and expiry
**Then** `SourceAccess` row is upserted with correct attributes

**Acceptance**: API 200; row exists; subsequent read shows access.

---

### US-DB-004 (Schema evolves safely)

**Given** a new feature adds `SourceAccess.license_key`
**When** dev runs `alembic revision --autogenerate` and `upgrade head`
**Then** the column is added without data loss

**Acceptance**: Migration applies cleanly; rollback works in dev; seed still runs.

## Test Notes

* Unit: model constraints, service logic branches
* Functional: endpoint CRUD, 400/404/409 cases
* Regression: re-run seed, alembic upgrade/downgrade cycles
* Security: bcrypt hash verification, Fernet decrypt round-trip (if used)

---

# FR-002: Redis Layer (Caching, Sessions, Conversation Context) + Auto-Compaction with UI Status

## Summary

Introduce Redis (local, free) as speed layer for:

1. **Caching** (e.g., permissions, rules lookups),
2. **Session management** (server-side sessions),
3. **Conversation context buffers**, and
4. **Automatic compaction** of chat sessions when context usage crosses a threshold.
   Include a **status bar** that shows context usage and a **visible “Compacted” indicator** when compaction runs.

## Goals

* Reduce DB + API load, speed up responses.
* Provide robust session store with bulk logout.
* Maintain short-lived chat context per user/thread.
* Prevent prompt/context overflow via smart compaction.
* Give users clear visibility into context budget and compaction events.

## Non-Goals

* Long-term analytics store (this stays ephemeral).
* Vector search in Redis (future option with RedisJSON/FT).

## High-Level Design

* **Redis** 7 (local) with AOF + `allkeys-lru` for cache.
* Python `redis>=5` client; single `get_redis()` factory.
* **Keys**

  * Cache: `cache:*` (TTL)
  * Rate limit: `ratelimit:*`
  * Sessions: `sess:{sid}`, `idx:user_sessions:{uid}`
  * Context: `ctx:{uid}:{thread}` (List) + `ctxmeta:{uid}:{thread}` (Hash)
  * Compaction events: `ctxevents:{uid}:{thread}` (List or Stream)
* **UI Status**: progress bar fed by `/chat/{thread}/context-usage` endpoint.
* **Compaction**: background hook or per-write check that summarises/merges older messages.

## Deliverables / Feature Items

1. **Docker Compose + redis.conf** (bind=127.0.0.1, protected-mode yes, AOF on, maxmemory policy)
2. **Client factory** `cache/redis_client.py`
3. **Caching helpers** `cache/cache.py` (read-through cache + invalidation + rate limit)
4. **Sessions** `auth/sessions.py` (create/touch/destroy, bulk user logout)
5. **Chat Context** `chat/context.py` (append/get, TTL, trim to MAX\_MESSAGES)
6. **Context Usage API**

   * `GET /chat/{thread}/context-usage` → returns:

     * `message_count`, `approx_tokens`, `threshold_pct`, `compaction_pending`
7. **Auto-Compaction Engine** `chat/compact.py`

   * Trigger on write when usage ≥ `COMPACT_TRIGGER_PCT` (e.g., 80%)
   * Repeat until usage ≤ `COMPACT_TARGET_PCT` (e.g., 60%)
   * Strategies (configurable, in order):

     1. **Header dedupe & system folding** (merge repeated system/tool notices)
     2. **Oldest message summarization** (LLM or rule-based)
     3. **Windowed merge** (collapse N oldest user/assistant turns into a concise summary)
     4. **Drop non-essential artifacts** (e.g., large code blocks preserved as links/attachments)
   * Emit event to `ctxevents:*` and update `ctxmeta:*` with last\_compacted timestamp, counts before/after.
8. **UI Indicators**

   * **Status bar** in chat UI (client) that shows: “Context 72% · Next compact at 80%”
   * When compaction occurs: inline banner “Conversation compacted · −18 messages · + summary” (with a “View diff”/“Undo” button in dev mode)
9. **Admin/Dev Controls**

   * ENV config: thresholds, estimation mode (chars/4 vs tokenizer), compaction strategies on/off
   * Test flag to disable compaction
   * Endpoint: `POST /chat/{thread}/compact-now` (admin/dev only)
10. **Observability**

    * Counters: compactions run, messages summarized/dropped, avg latency per strategy
    * Logs for before/after token estimates

## Configuration

```
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=2592000
CONTEXT_TTL_SECONDS=86400
MAX_MESSAGES=50
CTX_MAX_TOKENS=16000            # “reasonable max context size” (tunable)
COMPACT_TRIGGER_PCT=80
COMPACT_TARGET_PCT=60
COMPACT_STRATEGIES=dedupe,summarize,window,drop
TOKEN_ESTIMATOR=chars_div_4     # or cl100k_base
```

## Compaction Algorithm (detail)

1. **Estimate usage**:

   * `approx_tokens = total_chars // 4` (fast) or real tokenizer if available.
   * `usage_pct = round(approx_tokens / CTX_MAX_TOKENS * 100)`.
2. **Trigger** when `usage_pct >= COMPACT_TRIGGER_PCT`.
3. **Apply strategies** in order, re-estimate after each step.
4. **Stop** when `usage_pct <= COMPACT_TARGET_PCT` or no further reduction is possible.
5. **Record event**: `{before_tokens, after_tokens, before_msgs, after_msgs, strategies_used, ts}`.
6. **User feedback**: push a UI banner and update status bar.

## API Surface (FastAPI examples)

* `GET /chat/{thread}` → returns compacted/active message window
* `POST /chat/{thread}` → append message; may trigger compaction; returns new usage stats
* `GET /chat/{thread}/context-usage` → {usage\_pct, approx\_tokens, next\_compact\_at\_pct}
* `POST /chat/{thread}/compact-now` → admin/dev manual compact
* `GET /chat/{thread}/events` → recent compaction events (for UI to show “Compacted”)

## User Stories

### US-REDIS-001 (Developer caches an expensive rules lookup)

**Given** an API that fetches complex rules data
**When** the request is executed
**Then** the result is stored under `cache:rules:{key}` with TTL
**And** subsequent calls within TTL are served from Redis in <5ms

**Acceptance**: first call hits source; subsequent call hits cache; TTL respected; invalidation works.

---

### US-REDIS-002 (Player session persists across restarts)

**Given** a Player logs in successfully
**When** the app restarts
**Then** the Player’s session id remains valid until TTL expiry
**And** last\_seen is refreshed on use

**Acceptance**: session hash exists; TTL decrements then refreshes on requests; logout deletes keys.

---

### US-REDIS-003 (Admin logs out a compromised account everywhere)

**Given** a User has multiple active sessions
**When** Admin triggers “logout all”
**Then** all `sess:{sid}` keys for that user are deleted
**And** the user is unauthenticated on next request

**Acceptance**: count of destroyed sessions > 0; subsequent protected request returns 401.

---

### US-REDIS-004 (Context status bar reflects budget)

**Given** a running chat thread
**When** messages are added
**Then** `GET /chat/{thread}/context-usage` returns increasing `usage_pct`
**And** the UI bar shows “Context 55% · Next compact at 80%”

**Acceptance**: usage increases deterministically with text length; threshold math correct.

---

### US-REDIS-005 (Auto-compaction keeps conversation within budget)

**Given** CTX\_MAX\_TOKENS=16000, trigger at 80%, target 60%
**When** a new message pushes usage to 83%
**Then** compaction runs (dedupe→summarize→window…)
**And** usage drops to ≤60%
**And** the UI shows a “Compacted” banner with details

**Acceptance**: before/after tokens recorded; usage\_pct after ≤ 60%; event logged; banner visible in UI.

---

### US-REDIS-006 (Developer manually compacts for debugging)

**Given** a thread is large
**When** dev calls `POST /chat/{thread}/compact-now`
**Then** compaction runs immediately
**And** an event is appended to `ctxevents:*`

**Acceptance**: status 200; usage decreases (if possible); event readable.

---

### US-REDIS-007 (Prevent runaway growth)

**Given** a thread receives rapid long messages
**When** compaction cannot reach target after all strategies
**Then** the system returns `413 Payload Too Large` with advice
**And** does not corrupt the context list

**Acceptance**: safe failure; no key corruption; UI error state shown.

## Acceptance Criteria (Epic)

* Redis is provisioned and reachable via `REDIS_URL`.
* Session CRUD (create/touch/destroy/all-user) fully working.
* Caching helper used in at least one hot path (and measurably faster).
* Chat context APIs implemented; TTL trimming works.
* Auto-compaction triggers at configured thresholds; reduces usage; emits event.
* UI status bar shows live usage and compaction banners.
* Tests cover success and failure paths; fakeredis works in CI.

## Test Notes

* **Unit**: key naming, TTL math, rate limiter, compaction step functions.
* **Functional**: end-to-end session lifecycle; context append→trigger→compact.
* **Load**: simulate many short writes; ensure latency acceptable and no lockups.
* **Security**: session id entropy; no PII in cache keys; protected Redis config (loopback).

---

## Implementation Checklist (both features)

* [ ] Add deps to `requirements.txt`

  * `sqlmodel`, `SQLAlchemy>=2`, `alembic`, `passlib[bcrypt]`, `cryptography`
  * `redis>=5`, `python-dotenv`, `itsdangerous` (optional), `fakeredis` (tests)
* [ ] Create `/ops/redis/redis.conf` and `docker-compose.yml` (optional RedisInsight)
* [ ] Implement DB engine + models + services + alembic init + seed
* [ ] Implement Redis client + cache helpers + sessions + context + compaction
* [ ] Add FastAPI endpoints (admin + chat)
* [ ] Wire UI status bar to `context-usage` endpoint; add “Compacted” banner hook
* [ ] CI: run alembic migrations; run unit/functional tests with fakeredis
* [ ] Docs: ENV, thresholds, maintenance procedures (backup `.db`, clear Redis safely)

