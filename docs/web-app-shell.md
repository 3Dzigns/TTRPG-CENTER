# Web App Shell Overview

The `P00` scaffold introduces a pnpm-powered monorepo with a Next.js App Router
frontend, shared UI primitives, typed API access, and configuration packages.

## Workspace Layout
- `apps/web`: Next.js 15 application with Tailwind, TanStack Query, and role-aware dashboards.
- `packages/ui`: Reusable shadcn-inspired shell components (`TopNav`, `AppSidebar`, `UserMenu`).
- `packages/api`: Fetch-based client for `/v1/me`, `/v1/games`, and `/v1/sources`.
- `packages/types`: Shared domain contracts (`User`, `Game`, `Source`, `Character`, `Usage`, `BillingLink`).
- `packages/config`: Theme tokens, Tailwind preset, tsconfig, and flat ESLint config.

## Getting Started
```bash
pnpm install
pnpm dev          # Runs Next.js app at http://localhost:3000
pnpm test         # Executes Vitest suite (TopNav smoke test included)
pnpm lint         # Applies shared ESLint flat config
pnpm build        # Builds all packages via project references
```

## Theming & Accessibility
- Theme preference persists to `localStorage` (`ttrpg-center:theme`) and syncs with system dark mode.
- CSS variables are exposed via `packages/config/theme.ts` and consumed through a Tailwind preset.
- Keyboard focus states and WCAG 2.2 friendly contrast palettes are baked into shell components.

## Next Steps
- Connect `packages/api` to real backend endpoints for live data.
- Expand Vitest/RTL coverage to player, GM, and admin pages.
- Replace mocked session fallback with production authentication flow.
