# FR-CONFIG-601 — Centralize Secrets and Env Loading

## Summary
Use `src_common/ttrpg_secrets.py` (via `src_common/secrets.py`) as the single interface for env/secret access. Remove ad-hoc `dotenv` loads inside application modules (e.g., `app_user.py:real_rag_query`).

## Rationale
- Single source of truth for secrets
- Fewer environment inconsistencies between services

## Acceptance Criteria
- No application modules import/load `dotenv` directly
- All secrets and config come from the central secrets/config APIs
- Security tests continue to pass

## Implementation Notes
- Replace local env loads with helpers from `src_common/secrets.py`
- Provide per-env overrides via `env/{env}/config/*.env` where appropriate

