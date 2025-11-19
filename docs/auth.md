# Authentication Flow

The web app now integrates with the backend OAuth/OIDC gateway.

## Sign-in
- `/auth/signin` renders provider buttons. Selecting one calls `/api/auth/start`, which proxies to `${AUTH_BASE_URL}/auth/start` and returns a redirect URL.
- The backend sets the secure session cookie; the callback handler at `/auth/callback` forwards query params, applies `Set-Cookie`, and redirects back to the requested page (default `/player`).

## Session Fetching
- `useSession` delegates to `fetchSession`, which wraps `GET /v1/me`. 401 responses trigger the client guard to redirect to `/auth/signin` while preserving the destination.
- Session roles feed a Zustand store (`useAuthStore`), enabling fast role switching without refetching.

## Role Switching & Sign-out
- The dashboard layout exposes a role selector and enhanced `UserMenu`; selecting a new role updates navigation instantly.
- `signOut()` posts to `/api/auth/signout`, clears the session cookie, resets local caches, and routes back to the sign-in page.

## Middleware
- `middleware.ts` protects `/player`, `/gm`, `/admin`, and `/game/*`, redirecting unauthenticated visitors to the sign-in screen and skipping already-authenticated leaks.

## Configuration
- `AUTH_BASE_URL` (and optional `AUTH_COOKIE_NAME`) should be set in the runtime environment to point at the backend auth gateway.
