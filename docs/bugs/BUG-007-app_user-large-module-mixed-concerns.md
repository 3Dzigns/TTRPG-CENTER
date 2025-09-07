# BUG-007: app_user.py Mixes UI, Auth, Caching, and RAG Bridge (Maintainability)

## Summary
`app_user.py` contains UI route handling, session/user memory, CORS/TLS fallback, OAuth aliasing, token verification, WebSocket management, and the RAG bridge. This concentration of responsibilities raises maintenance risk and complicates testing.

## Environment
- Application: User UI
- Date Reported: 2025-09-06
- Severity: Medium (tech debt / maintainability)

## Evidence
- Single file holds: templates/static wiring, JWT verification, OAuth callback aliasing, session memory, cache policy, query processing, WebSocket manager, and RAG bridging.

## Expected State
- UI routes thin, delegating to service modules: auth, memory/cache, RAG client, websocket manager.

## Actual State
- Monolithic file with many concerns interleaved.

## Root Cause
- Feature additions accumulated in a single module without refactors.

## Fix Required
- Extract into `src_common/user_services/` or similar: `memory.py`, `rag_client.py`, `ws_manager.py`.
- Keep `app_user.py` as a composition layer.

## Priority
Medium

## Related Files
- `app_user.py:1`

## Testing Notes
- Ensure unit tests for extracted services; functional tests for UI remain green.

