# WebUI Tester

## Purpose
Execute E2E testing, visual regression, accessibility validation, and cross-browser testing for web applications.

## Required tools
- playwright (>=0.1.0)
- memory (>=0.3.0)

## Optional tools
- puppeteer (>=0.1.0)
- sequential-thinking (>=0.1.0)

## When to use
- Running E2E tests for UI features
- Validating accessibility compliance
- Visual regression testing
- Cross-browser compatibility testing
- Inputs include `test_spec`, `app_url`, or `test_suite`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- `app_url` (string, required) - Application URL to test
- `test_spec` (object, optional) - Test specification
- `browsers` (array, optional) - Browser targets (chromium/firefox/webkit)
- `accessibility` (boolean, optional) - Run accessibility tests

## Procedure (must follow)
1) For complex test suites, use `sequential-thinking` to plan test execution order.
2) Read previous test results from `memory` key `webui/tests/{test_suite}`.
3) Use `playwright` to execute tests:
   - Navigate to `app_url`
   - Run E2E test scenarios
   - Capture screenshots (before/after)
   - Check console errors
   - Validate accessibility (if enabled)
4) Use `puppeteer` as fallback if playwright unavailable.
5) Create test artifacts:
   - `TestReport.md` - Test results summary
   - `FailureScreenshots/` - Failed test screenshots
   - `AccessibilityReport.md` - WCAG violations (if applicable)
   - `TestMetrics.json` - Performance metrics
6) Store test results in `memory` under `webui/tests/{test_suite}`.

## Outputs (artifacts)
- `TestReport.md` - Detailed test results
- Screenshots (before/after, failures)
- `AccessibilityReport.md` - WCAG compliance report
- `TestMetrics.json` - Performance/timing data
- Console error logs

## Failure policy
- If `playwright` AND `puppeteer` both unavailable, STOP and emit remediation note.
- If tests fail, always capture screenshots and logs.
- Never skip accessibility tests when enabled.

## Version
1.0.0
