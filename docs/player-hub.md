# Player Hub Overview

The Player Hub (`P01`) builds on the monorepo scaffold to deliver a role-focused
experience where players can manage characters, games, and source permissions.

## Feature Highlights
- **Character roster** with quick selection, status indicators, and a guided dialog for creating new heroes (react-hook-form + zod).
- **Game selector** that surfaces joined campaigns, supports invite-code onboarding, and persists active campaign associations.
- **Source multi-select** that merges owned and campaign-permitted sources, leveraging virtualization (`@tanstack/react-virtual`) for 100+ entries.
- **Usage overview** with read-only meters for text assist, automation credits, audio, and Discord bridges.
- **Manage billing** button that opens the customer portal in a new tab with double-click protection and trace-aware error messaging.

## Primary Files
- `apps/web/components/player/player-hub.tsx` — Orchestrates data fetching, Zustand state, and mutations.
- `apps/web/app/(dashboard)/player/page.tsx` — Renders the Player Hub within the dashboard layout.
- `packages/ui/src/components/CharacterList.tsx` — Shell component for the roster list + create entry point.
- `packages/ui/src/components/GameList.tsx` — Campaign selector with join button.
- `packages/ui/src/components/SourceMultiSelect.tsx` — Virtualized selector that merges owned and allowed sources.
- `packages/ui/src/components/UsageMeter.tsx` — Reusable progress indicators for usage quotas.

## Data Flow
1. `@ttrpg-center/api` adds character, game, and usage methods (`getCharacters`, `createCharacter`, `updateCharacter`, `joinGame`, `getUsage`).
2. `apps/web/components/player/player-hub.tsx` wires TanStack Query hooks + Zustand (`usePlayerStore`) to track active character/game/source state.
3. Creating characters and joining games push optimistic updates to cached queries, with follow-up invalidations for server parity.
4. Source selection persists through `PATCH /v1/characters/:id`, ensuring server-side sync of activeSourceIds.

## Testing
Vitest/RTL tests exercise:
- Character selection callbacks (`CharacterList`),
- Form validation for the create dialog,
- Source toggle interactions within the virtualized multi-select.

Run from repo root:
```bash
pnpm -w test
```

## Next Steps
- Integrate live backend endpoints (characters/games/sources/usage) and expand optimistic updates to include toast feedback.
- Layer in Playwright smoke coverage once games and sources are wired to production data.
