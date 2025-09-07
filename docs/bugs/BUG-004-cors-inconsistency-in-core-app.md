# BUG-004: Core App Uses Wildcard CORS Instead of Secure Policy

## Summary
The core FastAPI app (`src_common/app.py`) configures `CORSMiddleware` with `allow_origins=["*"]`. Other apps (e.g., `app_user.py`, `app_admin.py`, `app_requirements.py`, `app_feedback.py`) use `src_common.cors_security.setup_secure_cors()` and validate on startup. This inconsistency weakens FR-SEC-402 alignment and may allow overly permissive cross-origin access.

## Environment
- Application: Core API (src_common/app.py)
- Environments: dev/test/prod
- Date Reported: 2025-09-06
- Severity: Medium (security posture inconsistency)

## Steps to Reproduce
1. Open `src_common/app.py:28` and inspect `setup_middleware()`
2. Observe `allow_origins=["*"]` passed to `CORSMiddleware`
3. Compare with `app_user.py` which wraps CORS via `src_common.cors_security.setup_secure_cors(app)` and `validate_cors_startup()`

## Expected Behavior
- Core app applies the same secure CORS policy used by other apps via `src_common.cors_security.setup_secure_cors()` with environment-aware allowed origins.

## Actual Behavior
- Core app uses a wildcard `*` origin policy, diverging from FR-SEC-402 secure configuration used elsewhere.

## Root Cause Analysis
- Convenience middleware setup in `src_common/app.py` did not adopt the hardened helper in `src_common/cors_security.py`.

## Technical Details
- Affected: `src_common/app.py:36` (CORS config)
- Secure Helper: `src_common/cors_security.py`
- Tests: `tests/security/test_fr_sec_402_cors.py`

## Fix Required
- Replace inline `CORSMiddleware` with `setup_secure_cors(app)` and call `validate_cors_startup()` at startup.
- Ensure allowed origins are controlled through env/config files.

## Priority
Medium

## Related Files
- `src_common/app.py:28`
- `src_common/cors_security.py:1`
- `app_user.py:33`

## Testing Notes
- Run security tests `tests/security/test_fr_sec_402_cors.py`
- Verify no wildcard origins appear in response headers in prod/test; dev may allow localhost variants only per policy.

