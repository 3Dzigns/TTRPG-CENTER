# Engineering Conventions

This document outlines the shared expectations for code structure, commit hygiene, and collaboration inside the TTRPG Center monorepo.

---

## 1. Code Organization

- **Feature-first folders** – Components live under `apps/web/components/<domain>/`. Hooks go in `apps/web/hooks/`. Shared primitives belong in `packages/ui` or `packages/api` depending on scope.
- **Co-locate tests** – Place Vitest specs in `__tests__` directories next to the subject file. Playwright specs live in `apps/web/e2e`.
- **Avoid monoliths** – Break components at ~300 LOC. Extract dialog, list, and mutation helpers into child components or hooks.
- **Named exports** – Default exports only for Next.js pages/routes to leverage framework conventions.

```
apps/
  web/
    components/
      player/
        character-list.tsx
        __tests__/character-list.test.tsx
    hooks/
      useGameChat.ts
packages/
  ui/
    src/components/InlineBanner.tsx
```

---

## 2. TypeScript & Styling

- Strict TypeScript: no `any` or `@ts-ignore`. When suppression is unavoidable, document the reason inline.
- Prefer `type` aliases over `interface` unless extending existing shapes.
- Use Tailwind utility classes for layout. Shared styles belong in the design system (`packages/ui`).
- Dark mode, focus states, and accessibility annotations (aria-label, role) are required for new UI.
- Keep effects pure: React `useEffect` dependencies must be exhaustive; bypass only with justification.

---

## 3. Testing

- **Unit** – Vitest + RTL for components, hooks, and utilities. Snapshot tests only for stable markup (icons, static data).
- **E2E** – Playwright smoke suite (`pnpm --filter @ttrpg-center/web test:e2e`) runs in CI. Add to `apps/web/e2e/*.spec.ts`.
- **Coverage mindset** – For net-new features, cover the happy path plus at least one error/edge branch.
- Mock network calls with `vi.fn()` or Playwright `page.route(...)`; do not hit real services in automated runs.

---

## 4. Git Workflow & Commit Messages

- Branch names: `feature/<short-description>` or `fix/<bug-id>`.
- Rebase before opening PRs (`git pull --rebase origin main`).
- Use **Conventional Commits**. Squash commits on merge unless the PR contains multiple semantic changes.

| Type | Description |
|------|-------------|
| `feat:` | User-facing feature or API addition. |
| `fix:` | Bug fix. |
| `docs:` | Documentation only. |
| `chore:` | Build scripts, dependencies, config. |
| `refactor:` | Code change without functional impact. |
| `test:` | Add or update tests. |
| `perf:` | Performance improvements. |
| `build:` | Tooling or CI/CD changes. |

**Example**
```
feat(player): allow selecting owned sources

- add SourceMultiSelect footer with counts
- persist selections per character
```

---

## 5. Pull Request Checklist

Before requesting review:

- [ ] `pnpm run lint` passes (no warnings promoted in CI).
- [ ] `pnpm --filter @ttrpg-center/web test` and `pnpm test:e2e` pass locally when applicable.
- [ ] Screenshots or GIFs attached for UI changes.
- [ ] Docs updated (`docs/` or component Storybook notes) when behaviour is user-visible.
- [ ] Applied `docs/feature-template.md` to capture scope & rollout notes if the work is sizable.

Reviewers expect PR descriptions with:
- Summary (1‑2 sentences).
- Before/after or acceptance criteria.
- Testing evidence (`pnpm test`, `pnpm test:e2e`, manual QA).

---

## 6. Feature Lifecycle

1. Capture scope using `docs/feature-template.md` (commit into `/docs/features/` if helpful).
2. Align on API contracts with backend; update `packages/types` concurrently.
3. Build behind feature flags when the surface is large or requires backfilling data.
4. Ship with observability—log trace IDs or surface them via InlineBanner/ErrorBoundaryCard where applicable.

---

## 7. Collaboration Norms

- Respond to review comments within 1 business day. Use GitHub suggestions when accepting alternative implementations.
- Use Slack `#webui-dev` for quick pings; escalate blockers via @oncall.
- Pair on architecture changes (>500 LOC or cross-package refactors) during sprint planning or via design doc.

Stay consistent with these conventions and we keep the codebase approachable, testable, and review-friendly for everyone.*** End Patch
