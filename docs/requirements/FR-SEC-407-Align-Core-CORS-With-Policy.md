# FR-SEC-407 — Align Core App CORS With Security Policy

## Summary
Apply `src_common.cors_security.setup_secure_cors()` and `validate_cors_startup()` in `src_common/app.py` to match FR-SEC-402 behavior used by other apps.

## Rationale
- Consistent security posture across all apps
- Avoids wildcard origins in production

## Acceptance Criteria
- Core app no longer sets `allow_origins=["*"]`
- Allowed origins configured per env via config files
- `tests/security/test_fr_sec_402_cors.py` passes for core app as well

## Implementation Notes
- Replace direct `CORSMiddleware` usage with the shared helper
- Provide minimal dev fallbacks consistent with the other apps

