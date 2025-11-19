# Playwright Smoke Tests

## Overview
The end-to-end smoke suite (`apps/web/e2e/smoke.spec.ts`) exercises the four critical journeys:

1. **Sign-in start** – verifies the SSO bootstrap request.
2. **Player source management** – selects a character and toggles sources.
3. **GM campaign management** – adds an owned source to the active game.
4. **In-game chat** – submits a prompt and streams the assistant reply via mocked SSE.
5. **Admin dashboard** – confirms health snapshots render with catalog data.

All network traffic to `/v1/*` and `/api/auth/start` is stubbed with deterministic fixtures so the tests run without a seeded backend.

## Running Locally
```bash
cd apps/web
pnpm install
pnpm dlx playwright install
pnpm test:e2e
```

Key config (see `apps/web/playwright.config.ts`):
- Headless Chromium only, retries on CI (2x).
- Screenshots/video/trace captured on failure for upload to CI artifacts.
- Dev server auto-starts via `pnpm dev` unless `PLAYWRIGHT_BASE_URL` points to an existing instance.

Use `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 pnpm test:e2e` to reuse a running Next.js server.

## Extending
- Add new journeys in `apps/web/e2e/` and register additional fixtures using `page.route(...)` before navigation.
- Emit SSE events in tests with `window.__emitServerEvent(<substring>, JSON.stringify(event))`.
- Keep runtime < 2 minutes; stub long polls or background fetches if flows expand.
