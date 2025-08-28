# User Interface — User Stories & Test Plan

**Scope:** End-user interface for querying the TTRPG system

## User Stories

- As a **stakeholder**, I want **Query interface with performance metrics** (**UI-001**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **LCARS/Star Wars retro terminal visual design** (**UI-002**, priority=medium), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Response area with multimodal support** (**UI-003**, priority=high), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Memory mode selection** (**UI-004**, priority=medium), so that we meet the MVP acceptance criteria.

## Acceptance Criteria

### UI-001: Query interface with performance metrics
- [ ] Text input field with submit functionality
- [ ] Real-time timer display in milliseconds
- [ ] Token usage counter
- [ ] Model identification badge
### UI-002: LCARS/Star Wars retro terminal visual design
- [ ] Background art integration from provided image
- [ ] LCARS-inspired accent grids and typography
- [ ] Retro terminal aesthetic with appropriate color palette
### UI-003: Response area with multimodal support
- [ ] Text response display
- [ ] Image display capability (future)
- [ ] Source provenance toggle when available
### UI-004: Memory mode selection
- [ ] Session-only memory mode
- [ ] User-wide memory mode
- [ ] Party-wide placeholder for future implementation

## Test Plan

### Unit Tests

- UI-001: Unit tests for core logic/config implementing 'Query interface with performance metrics'.
- UI-002: Unit tests for core logic/config implementing 'LCARS/Star Wars retro terminal visual design'.
- UI-003: Unit tests for core logic/config implementing 'Response area with multimodal support'.
- UI-004: Unit tests for core logic/config implementing 'Memory mode selection'.

### Functional (E2E) Tests

- UI-001: End-to-end scenario demonstrating all acceptance criteria.
- UI-002: End-to-end scenario demonstrating all acceptance criteria.
- UI-003: End-to-end scenario demonstrating all acceptance criteria.
- UI-004: End-to-end scenario demonstrating all acceptance criteria.

### Regression Tests

- UI-001: Snapshot/behavioral checks to prevent future regressions.
- UI-002: Snapshot/behavioral checks to prevent future regressions.
- UI-003: Snapshot/behavioral checks to prevent future regressions.
- UI-004: Snapshot/behavioral checks to prevent future regressions.

### Security Tests

- Escape/encode model output (XSS); sanitize markdown before render.
- Rate-limit queries and cap payloads; input validation on server.
- No API keys in client bundle.

## Example Snippet

```html
<div class="ui">
  <label>Ask:</label>
  <input id="q" placeholder="e.g., 'What are PF2E bulk rules?'" />
  <button onclick="submit()">Go</button>
</div>
<pre id="out"></pre>
```
