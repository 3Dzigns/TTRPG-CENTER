# Auth Database Integration Plan

## Overview

We are moving the web application away from mock session data and into a real OAuth-backed authentication system that persists identities and role assignments in PostgreSQL. All auth lookups will ultimately flow through a dedicated `ttrpg_auth` database that lives inside the existing `ttrpg_postgres` container.

## Decisions (Phase 1)

- **Database engine**: PostgreSQL (existing `ttrpg_postgres` service).
- **Database name**: `ttrpg_auth` (created via `CREATE DATABASE ttrpg_auth`).
- **Node driver / ORM**: `drizzle-orm` with the Postgres driver. We will use the lightweight schema builder API and control SQL migrations ourselves (no external CLI dependencies).
- **Connection management**: central helper in `apps/web/lib/db.ts` that reads from `AUTH_DATABASE_URL`. Pooling will be handled by `pg`'s `Pool` to avoid exhausting connections during SSR.
- **Secret management**: `AUTH_DATABASE_URL` has been added to `.env` and the secrets template. CI/CD will need to expose the same variable.

## Go / No-Go Checklist

- [x] `ttrpg_auth` database exists inside `ttrpg_postgres`.
- [x] `.env` and `secrets/.env.example` expose `AUTH_DATABASE_URL`.
- [x] Runtime dependencies (`drizzle-orm`, `pg`) declared in `apps/web/package.json`.
- [x] Database helper skeleton checked into `apps/web/lib/db.ts`.
- [x] Migrations directory scaffolded under `apps/web/db/migrations`.

Phase 2 expands on this foundation with the concrete schema and migration logic.

## Phase 4: Next.js Auth API Surface

- `/api/v1/me` resolves the authenticated user and returns a sanitized `Me` payload with non-cacheable headers.
- Admin-only `/api/v1/users` endpoint stays wired to Drizzle for role-aware listings.
- New sessions stamp `last_login_at` on first insert for accurate activity tracking.

**Go / No-Go Test**

```bash
pnpm --filter @ttrpg-center/web test -- run apps/web/app/api/v1/me/__tests__/route.test.ts
```

## Phase 5: Client Session Context & Guard

- `SessionProvider` loads `/v1/me`, surfaces status (`loading`, `authenticated`, `unauthenticated`, `error`), and caches the last good payload.
- `SessionGuard` redirects 401s to `/auth/signin?redirect=...` while exposing retry hooks for recoverable errors.
- Zustand-backed role selection stays in sync with the resolved session.

**Go / No-Go Test**

```bash
pnpm --filter @ttrpg-center/web test -- run apps/web/components/session/__tests__/session-provider.test.tsx
```

## Phase 6: Middleware & Route Protection

- `middleware.ts` blocks anonymous access to `/player`, `/gm`, `/admin`, `/game/*`, and shortcuts authenticated users past `/auth/signin`.
- Redirects preserve the original destination via the `redirect` query param.
- Cookie detection honors `AUTH_COOKIE_NAME` (defaults to `tc_session`) with a graceful fallback.

**Go / No-Go Test**

```bash
pnpm --filter @ttrpg-center/web test -- run apps/web/__tests__/middleware.test.ts
```

## Phase 7: Sign-out & Client Cleanup

- `/api/auth/signout` clears local sessions and proxies remote gateways when configured.
- Client `signOut()` now propagates failures, resets the API client cache, and is easy to stub in dashboards.
- Dashboard handlers flush Zustand and React Query caches before routing back to `/auth/signin`.

**Go / No-Go Test**

```bash
pnpm --filter @ttrpg-center/web test -- run apps/web/lib/__tests__/auth.test.ts
```
