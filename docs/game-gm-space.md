## Game Space - GM Mode

### Overview
The GM version of the Game Space builds on player mode with a right-rail control surface aimed at campaign management. Primary chat and citation handling mirror the player experience to maintain parity while adding GM-specific tooling.

### Key Elements
- **Streaming Assist Chat** uses the shared `ChatPanel`/`useGameChat` pipeline. Responses stream via `/v1/events` and surface citations for quick source review.
- **GM Controls Panel** offers quick access back to the GM Hub, members, and sources. Scheduled features (Audio Review, AI Summaries, Discord Bridge) render as disabled toggles with tooltips clarifying roadmap status and remain non-focusable for non-GM users.
- **Campaign Usage Meter** pulls `GET /v1/usage?scope=game&id=:id` and renders quota progress for automation credits, assist limits, and upcoming bridges inline with the chat view.
- **Billing Portal Shortcut** reuses the typed `getBillingLink` helper, opening the external portal in a safe `noopener,noreferrer` tab once loaded.

### Role Detection
`GamePageClient` seeds `['game', gameId]` queries, inspecting `game.members` to decide between GM and player views. Admins inherit GM access; players fall back to the player layout. The GM panel is omitted entirely for non-authorised users to keep focus order tight.

### Testing Notes
- `game-gm-view.test.tsx` mocks the chat surface to assert disabled controls, billing state transitions, and citation propagation.
- `page-client.test.tsx` verifies role-based rendering and the unauthorized fallback message.
