# Phase 5 — User UI

**Goal:** Query and interact in a themed user interface that feels immersive, supports multiple modes of interaction, remembers context, and responds quickly to retests.

---

## Epic E5.1 — Themed Interface

### US-501: Retro Terminal / LCARS-Inspired Design

**As** a Player or GM
**I want** the UI to have a retro terminal / LCARS-inspired design theme
**So that** the experience is immersive, consistent, and fun.

**Acceptance Criteria**

* Themed CSS/JS applied globally.
* Colors, fonts, and UI elements match LCARS retro terminal style.
* Theme toggle available in settings.

**Testing**

* **Unit:** UI components render with correct theme classes.
* **Functional:** Toggle theme → UI updates without reload.
* **Regression:** No broken styles across DEV/TEST/PROD.
* **Security:** No injection via theme CSS variables.

---

## Epic E5.2 — Multimodal Response Area

### US-502: Text Responses (baseline)

**As** a User
**I want** to see text answers displayed in a scrollable retro terminal panel
**So that** I can read results clearly.

**Acceptance Criteria**

* Text output appears in a distinct pane styled per theme.
* Metadata (time, tokens, model badge) visible inline (from Phase 2).
* Supports markdown (bold, italic, lists, code).

**Testing**

* **Unit:** Markdown rendered safely.
* **Functional:** Queries show both text and provenance blocks.
* **Regression:** Large responses scroll correctly.
* **Security:** Markdown sanitized (no XSS).

---

### US-503: Image Response Slot (future-ready)

**As** a User
**I want** a dedicated area in the response panel for images
**So that** future multimodal models can return illustrations, maps, or diagrams.

**Acceptance Criteria**

* Placeholder “Image will appear here” area.
* API returns optional `image_url`; UI displays it if present.
* Fallback gracefully when no image provided.

**Testing**

* **Unit:** Rendering works with mock image URLs.
* **Functional:** Image loads inline; broken URL shows placeholder.
* **Regression:** Text-only queries unaffected.
* **Security:** Images loaded with sandboxing (no script execution).

---

## Epic E5.3 — Memory Modes

### US-504: Session Memory

**As** a User
**I want** the system to remember context only for the current session
**So that** I can carry on multi-turn conversations without storing data long-term.

**Acceptance Criteria**

* Session memory persists until browser tab closed.
* History available in sidebar; can be cleared manually.
* Memory reset button clears state.

**Testing**

* **Unit:** Session context resets on new session\_id.
* **Functional:** Multi-turn queries reference earlier messages.
* **Regression:** Memory cleared correctly between sessions.
* **Security:** Memory not persisted to disk.

---

### US-505: User Memory

**As** a Returning User
**I want** persistent memory across sessions tied to my account
**So that** my preferences and play history are retained.

**Acceptance Criteria**

* User preferences (style, sources, tone) loaded at login.
* Past conversations viewable under “History.”
* Users can clear memory in settings.

**Testing**

* **Unit:** Preferences stored/retrieved from DB.
* **Functional:** Returning user sees same prefs.
* **Regression:** Memory schema backwards-compatible.
* **Security:** Encrypted at rest; accessible only to owner.

---

### US-506: Party Memory (future feature)

**As** a GM
**I want** a shared memory mode for my party
**So that** all players see the same context during campaign sessions.

**Acceptance Criteria**

* Shared session ID for party.
* Actions broadcast to all connected users.
* GM can reset/lock party memory.

**Testing**

* **Functional:** Multiple users see same context.
* **Security:** Access controlled by GM role.

---

## Epic E5.4 — Fast Retest Behavior

### US-507: Queries Respect Cache Policy

**As** a User
**I want** query retries to respect environment cache settings from Phase 0
**So that** results update instantly after config changes.

**Acceptance Criteria**

* Retrying a query after a config change shows updated answer within ≤5s.
* Cache headers/TTL enforced:

  * DEV = no-store
  * TEST = ≤5s
  * PROD = configurable

**Testing**

* **Unit:** Cache header logic enforced by environment.
* **Functional:** Toggle config → retry → new result shown.
* **Regression:** Cache bypass does not break normal flow.
* **Security:** Cache cannot leak sensitive data across tenants.

**Code Snippet**

```javascript
// Example fetch with cache policy override
async function askQuery(query) {
  const res = await fetch("/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": process.env.ENV === "dev" ? "no-store" : "max-age=5"
    },
    body: JSON.stringify({ query })
  });
  return res.json();
}
```

---

# Phase 5 Test Plan

### Unit Tests

* Theme CSS loads without error.
* Query results render text + optional image slot.
* Session memory resets correctly.
* Cache headers respect `.env` setting.

### Functional Tests

* User runs query → sees themed output with metadata.
* Retry after config toggle → updated result shown.
* Session memory holds context for multi-turn Q\&A.
* User memory loads after re-login.

### Regression Tests

* Previous phases’ query flow still works.
* Fast retest does not introduce stale results.
* UI upgrades do not break Admin console (Phase 4).

### Security Tests

* Markdown/image sanitization.
* Tenant isolation in memory/prefs.
* Cache policies prevent cross-user leakage.

---

✅ **Definition of Done (Phase 5):**

* UI themed per spec (retro/LCARS).
* Multimodal area supports text now, images later.
* Session + user memory working; party memory placeholder.
* Cache-respecting retests proven in DEV/TEST/PROD.
* Unit, functional, regression, and security tests passing in CI.
