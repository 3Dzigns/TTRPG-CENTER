# FR-ARCH-602 — Decouple UI App Into Service Modules

## Summary
Extract responsibilities from `app_user.py` into focused service modules (auth client, memory/cache manager, RAG client, WebSocket manager). Keep `app_user.py` as a thin composition layer.

## Rationale
- Improves maintainability and testability
- Clear separation of concerns

## Acceptance Criteria
- New modules host: memory manager, RAG client, WS manager
- `app_user.py` routes delegate to services; file size and complexity reduced substantially
- Unit tests for services; existing functional tests pass

## Implementation Notes
- Introduce `src_common/user_services/` or similar package
- Move logic without changing external contracts

