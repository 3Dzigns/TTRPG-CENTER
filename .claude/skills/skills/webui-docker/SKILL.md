# webui-docker

## Purpose
(See procedure below.)

## Required tools
- playwright (>=0.1.0)

## Optional tools
- puppeteer (>=0.1.0)

## When to use
- User asks to operate or test the web UI
- Inputs include `app_url` and `steps[]`

## Inputs
- `task_id` (string, optional)
- `context_delta` (JSON, optional)
- Additional task-specific fields (see examples).

## Procedure (must follow)
1) Open browser (headless true), navigate to `${app_url}` via `playwright`.
2) Execute each action in `steps[]`:
   - Supported: click, fill, select, waitFor, assertText, screenshot.
3) On any error:
   - Take `failure_screenshot.png` and STOP with `web_ui_error.md`.
4) Always produce:
   - `web_run_report.md` (actions, timings, console errors)
   - `before.png` and `after.png` screenshots

## Outputs (artifacts)
- Markdown reports in `artifacts/`
- JSON summaries and scorecards
- Screenshots (for UI tasks)

## Failure policy
- If a **required tool** is unavailable or a call fails twice, STOP and emit a remediation note.
- Never fabricate tool outputs. Provide minimal degraded output only with explicit user confirmation.

## Version
1.0.0
