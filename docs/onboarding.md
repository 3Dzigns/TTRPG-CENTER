# Developer Onboarding

Welcome to the TTRPG Center WebUI monorepo. This guide walks you from zero to productive in minutes, covering tooling, project layout, and day‑to‑day commands.

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | 20.x LTS | Use `nvm`/`fnm` for quick switching. |
| pnpm | 9.10+ | Installed via `corepack enable pnpm`. |
| Git | 2.40+ | Configure user name/email before committing. |
| Playwright browsers | latest | Installed via `pnpm dlx playwright install`. |

> Tip: run `node -v && pnpm -v` to confirm versions before installing dependencies.

---

## 2. Quick Start

```bash
git clone https://github.com/<org>/ttrpg-center.git
cd ttrpg-center
corepack enable pnpm             # once per machine
pnpm install                     # install workspace deps
pnpm dlx playwright install      # fetch browser binaries for e2e
make dev                         # or pnpm run dev (see below)
```

Open http://localhost:3000 once the Next.js server reports “ready”. Live reload is enabled by default.

---

## 3. Monorepo Topology

```
.
├─ apps/
│  └─ web/          # Next.js 15 App Router frontend
├─ packages/
│  ├─ api/          # Typed client for /v1 REST calls
│  ├─ types/        # Shared TypeScript models (Me, Game, Source, etc.)
│  └─ ui/           # Design system components (shadcn/ui + Tailwind)
├─ docs/            # Runbooks, onboarding, specs
└─ Makefile         # Convenience commands (dev, lint, test)
```

All workspace scripts are orchestrated through pnpm. Commands run at the root automatically pick the correct package when filtered (e.g., `pnpm --filter @ttrpg-center/web lint`).

---

## 4. Everyday Commands

| Action | Command |
|--------|---------|
| Start web dev server | `make dev` (alias for `pnpm --filter @ttrpg-center/web dev`) |
| Run unit tests (Vitest) | `pnpm --filter @ttrpg-center/web test` |
| Run Playwright smoke tests | `pnpm --filter @ttrpg-center/web test:e2e` |
| Lint + typecheck | `pnpm --filter @ttrpg-center/web lint` |
| Build production bundle | `pnpm --filter @ttrpg-center/web build` |
| Format check (Prettier) | `pnpm run format` |

Scripts can be chained: `pnpm run lint && pnpm run test` prior to opening a PR.

---

## 5. VS Code Setup (Recommended)

### Extensions
- ESLint (dbaeumer.vscode-eslint)
- Tailwind CSS IntelliSense (bradlc.vscode-tailwindcss)
- Prettier (esbenp.prettier-vscode)
- Playwright Test for VSCode (ms-playwright.playwright)

### Suggested `.vscode/settings.json`
```jsonc
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": "explicit"
  },
  "eslint.workingDirectories": [{ "mode": "auto" }],
  "typescript.tsdk": "node_modules/typescript/lib",
  "files.associations": {
    "*.css": "tailwindcss"
  }
}
```

> VS Code automatically picks workspace TypeScript thanks to the `typescript.tsdk` setting.

---

## 6. Glossary

| Term | Meaning |
|------|---------|
| **GM** | Game Master – user role that manages campaigns, invites, and sources. |
| **Player** | End-user consuming GM-curated content and AI assistance. |
| **Source** | A rulebook, module, or data set that powers prompts and embeddings. |
| **HGRN** | Hyper-Graph Retrieval Network – internal service backing vector search and Cassandra storage. |
| **Pass B / C / D** | Internal ingestion pipeline stages for data preparation and embeddings (used in ops logs). |

Keep these roles in mind—many components and API contracts are permission-aware.

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `node: command not found` or wrong version | Confirm Node 20 with `nvm use 20` (or install via https://nodejs.org). |
| pnpm fails with “store corrupted” | Run `pnpm store prune && pnpm install --force`. |
| Stale builds / strange runtime errors | Delete caches: `pnpm exec rimraf apps/web/.next .turbo` then rerun `pnpm install`. |
| Playwright browser mismatch | Reinstall binaries `pnpm dlx playwright install --with-deps`. |
| Turbo cache warnings | Remove `.turbo`, update `pnpm-lock.yaml`, and ensure consistent Node versions across teammates. |
| TypeScript cannot find module | Verify project references built: `pnpm --filter @ttrpg-center/api build`. |

Escalate persistent issues by opening an Ops ticket with the command, stack trace, and OS details.

---

## 8. Next Steps

1. Read `docs/conventions.md` for code and commit standards.
2. Use `docs/feature-template.md` to capture new work items.
3. Explore existing docs (e.g., `docs/e2e-smoke.md`, `docs/ERROR_HANDLING.md`) for advanced workflows.

Once comfortable, pick up a “good first issue” in the backlog or shadow an existing PR to observe review expectations.
