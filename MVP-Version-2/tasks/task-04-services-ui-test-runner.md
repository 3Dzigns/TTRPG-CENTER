# Task 04 — Services, Admin/User UI, and External Test Runner

## Objective
Upgrade the Admin API, User API, Admin UI, and test runner to deliver Phase 3 functionality: artifact management, HGRN reviews, external test orchestration, session memory, and themed user experience.

## Why This Matters
- Admin API still imports test helpers via `sys.path` hacks and lacks CRUD/bulk endpoints for dictionary, artifacts, jobs, HGRN actions.
- Test runner writes artifacts to `env/test/...` regardless of target environment and doesn’t expose streaming/log APIs expected by the Admin UI.
- User API maintains in-memory sessions with mock plan/run executors rather than orchestrator-backed workflows and Redis persistence.
- Admin UI test console is a 500-line component with placeholder hooks and no integration with real endpoints; User UI retro theme/flows are missing.

## Deliverables
- Admin API endpoints for dictionary CRUD, artifact browsing/downloading, job management, bulk cleanup, and HGRN action review with RBAC hooks.
- External test runner API that honours `environment` parameter, streams logs via SSE/WS, saves artifacts under `env/<env>/artifacts/tests/{id}`, and wraps pytest/newman/zap/k6 invocations.
- User API with orchestrator integration (`/ask`, `/plan`, `/run`), Redis-backed session memory, cache headers per env, and streaming support.
- Refactored Admin UI components (Test Console split into subcomponents/hooks) consuming the real Admin API endpoints, with accessibility and loading states covered by tests.
- Initial User UI (LCARS/retro theme) implementing ask/plan/run flows, provenance display, session context, and latency/model badges.
- Updated runbooks for orchestrator/admin/test-runner, plus README changes to describe service responsibilities and setup.

## Dependencies / Sequencing
- Consumes Task 01 environment config (Redis endpoints, artifacts paths) and Task 02/03 artefacts.
- Security middleware from Task 05 will wrap the new endpoints after implementation; design with RBAC hooks ready.

## Detailed Steps
1. **Admin API refactor**
   - Replace `sys.path` injection with a proper service client for the test runner (HTTP or message queue).
   - Implement CRUD endpoints: dictionary entries, chunks, graph nodes/edges, jobs, artifacts, logs, HGRN actions.
   - Add bulk cleanup operations (delete old logs, purge document artifacts) and surface manifest metadata.
   - Ensure endpoints emit structured logs and follow the error envelope.
2. **External test runner**
   - Parameterise suite execution by environment (DEV/TEST/PROD), mapping to commands defined in `MVP-V2-UserStories-and-TestCases.md`.
   - Implement streaming output via SSE and store artifacts under `env/<env>/artifacts/tests/{timestamp}`.
   - Add status polling, cancel, and result download endpoints.
   - Cover with unit tests (mock subprocess) and functional tests hitting the API.
3. **User API enhancements**
   - Integrate Redis (via env config) for session storage, ensuring TTL per environment (DEV no-store, TEST 5s, PROD configurable).
   - Replace mock plan/run logic with orchestrator-driven workflows; persist plan/run state and allow resumable sessions.
   - Implement streaming responses for `/ask/stream` using Server Sent Events or websockets.
   - Add functional tests verifying ask/plan/run flows and cache headers.
4. **Admin UI improvements**
   - Break `TestConsole.tsx` into smaller components (suite selector, run list, log stream, artifact viewer) and share state via hooks/context.
   - Wire components to real Admin API endpoints, handling SSE streams and download links.
   - Add UI for HGRN review and artifact browser leveraging new API endpoints.
   - Update unit/integration tests (Vitest/Testing Library) to cover states, streaming, and accessibility.
5. **User UI implementation**
   - Scaffold React app (Vite + Tailwind) with retro/LCARS theme, integrating ask/plan/run flows with the User API.
   - Display provenance citations, latency, model badges, and session history per requirements.
   - Add Playwright smoke tests for key flows and accessibility checks.
6. **Documentation & runbooks**
   - Update `MVP-Version-2/RUNBOOKS/orchestrator.md`, `admin_api.md`, `test_runner.md` with deployment, scaling, rollback, and troubleshooting steps.
   - Refresh service READMEs to describe endpoints, configuration, and testing commands.
