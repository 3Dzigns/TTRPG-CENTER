# Changelog

## Unreleased
- Scaffolded pnpm monorepo with Next.js app and shared configuration packages.
- Added typed API client, domain models, and reusable UI shell built on Tailwind.
- Implemented theme persistence, session guard, and role-based dashboard layout.
- Introduced Vitest + RTL smoke test and documentation for web app shell usage.
- Delivered Player Hub selectors (characters, games, sources) with persistence, dialogs, virtualization, and unit tests.
- Added GM Hub with game CRUD, member/source management, billing link surfacing, and dialog validations.
- Implemented player game space with streaming chat, SSE handling, read-only sources, and coverage for submit/stream/retry flows.
- Expanded ChatPanel with stop control, inline citation pills + modal details, and refreshed docs/tests for streaming interactions.
- Integrated Manage Billing buttons for player and GM flows with pop-up safe navigation, trace-aware errors, and portal tests.
- Delivered read-only Admin Dashboard with live health cards, central sources/users tables, virtualized audit log, and supporting docs/tests.
- Enabled admin overrides with diff-aware source editing, write-through database mutations, SSE-driven re-ingest banners, and comprehensive tests/docs.
- Wired OAuth/OIDC sign-in + callback flow, session guard, role switcher, and middleware-based route protection.
- Added reusable SSE client (`createEventStream`) with retry logic, React `useEvents` hook, and docs/tests for live updates.
- Refined usage meters with grouped layout, disabled tooltips, updated Player/GM dashboards, and new UI tests/docs.
- Upgraded source multi-select with chips, debounced filtering, keyboard navigation improvements, and virtualization tests.
- Standardized error handling with `ErrorBoundaryCard`, trace-aware API errors, toast provider, and refreshed coverage/docs.
- Completed WCAG 2.2 AA sweep: skip link + landmark updates, route-aware nav highlighting, dev-time axe audits, and accessibility docs/tests.
- Shipped Playwright smoke suite with stubbed data fixtures covering login, player source management, GM catalog updates, game chat streaming, and admin health checks (CI-ready with screenshots on failure).
- Published developer onboarding/conventions docs, feature brief template, and repo Makefile for fast dev workflows.

- Stabilized /v1/query contract with shared Zod/JSON schemas, query mocks, and documentation for independent frontend/back-end development.
