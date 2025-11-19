# GM Hub Overview

The GM Hub (`P02`) equips game masters with campaign management controls across members, sources, and billing.

## Key Features
- **Game roster** with create/delete actions, tier badges, and quick metrics.
- **Tabbed admin surface** (`Members`, `Sources`, `Settings`) operating on the selected game.
- **Members tab**: invite via email, view invite codes, adjust roles (GM/Co-GM/Player/Spectator), and remove members (auto-refresh handles source cleanup).
- **Sources tab**: merge GM-owned sources with in-game library, add/remove entries with idempotent API calls.
- **Settings tab**: tier selector, upcoming toggle previews, usage/billing summaries powered by `UsageMeter`, and the new Manage Billing button with pop-up protection.

## Primary Files
- `apps/web/components/gm/gm-hub.tsx` — Core container combining TanStack Query, Zustand-free local state, and mutations.
- `apps/web/components/gm/create-game-dialog.tsx` — react-hook-form + zod for game creation.
- `apps/web/components/gm/delete-game-dialog.tsx` — Safeguarded delete flow requiring name re-entry.
- `apps/web/components/gm/invite-member-dialog.tsx` — Email invite dialog with role selection.
- `packages/api/src/index.ts` — Extended to cover game CRUD, members, sources, billing.
- `packages/types/src/index.ts` — Added game tiers, members, and payload types.
- `packages/ui/src/components/InlineBanner.tsx` — Reusable inline alert banner with trace support.

## Data & Error Handling
- All mutations surface `trace_id` when returned by the backend by parsing `ApiError.details` and routing through `InlineBanner`.
- Game/member/source queries invalidate appropriately to keep cache consistency and reflect backend business rules (e.g., source pruning when a member leaves).
- Billing link retrieval occurs lazily per selected game (`getBillingLink("game", id)`), opening in a new tab for PCI-safe handling.
- Manage Billing button guards against pop-up blockers and surfaces trace-aware inline errors when the portal cannot be opened.

## Usage
From repo root:
```bash
pnpm dev            # Launches Next.js with GM Hub under /gm
pnpm -w test        # Runs Vitest suite, including GM dialog validation tests
pnpm --filter @ttrpg-center/web build
```

## Next Steps
- Wire invite + removal flows to real backend notifications and SSE updates.
- Expand component coverage with Playwright smoke tests once endpoints are stable.
- Introduce optimistic toasts for CRUD actions and expose audit logs per `trace_id`.
