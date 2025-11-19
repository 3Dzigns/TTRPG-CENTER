# Feature Brief Template

Use this template to capture the scope, constraints, and rollout plan for a new capability. Copy into your issue tracker or a doc in `/docs/features/` before implementation begins.

---

## 1. Summary
- **Feature name:** <!-- Short human-readable title -->
- **Owner(s):** <!-- Who is accountable -->
- **Target release:** <!-- Sprint / date -->

## 2. Motivation
- Problem statement / user story.
- KPIs or success metrics.
- Links to customer feedback, RFCs, or incident reports.

## 3. Requirements
- [ ] Functional requirement 1
- [ ] Functional requirement 2
- Non-functional: performance, accessibility, security, localization, etc.

## 4. Architecture Notes
- Existing routes/components touched.
- New APIs or contracts (update `packages/types` if necessary).
- Data migration implications (seeding, cleanup, backfills).

## 5. UI & UX
- Mockups / Figma links.
- State handling (loading, empty, error).
- Accessibility considerations (focus order, aria labels).

## 6. Implementation Plan
1. Task / PR 1
2. Task / PR 2
3. Task / PR 3

> Tip: Use small, reviewable PRs. Reference this doc in each description.

## 7. Testing Strategy
- Unit tests (Vitest/RTL) – what modules/assertions.
- E2E (Playwright) – new or updated journeys.
- Manual QA checklist (devices, browsers, feature flags).

## 8. Observability & Rollout
- Logging, metrics, feature flags, kill switches.
- Rollout plan (beta cohort, dark launch, full release).
- Post-launch verification steps.

## 9. Dependencies & Risks
- External teams, services, or libraries to coordinate with.
- Known risks and mitigations.

## 10. Open Questions
- Pending decisions or clarifications required before coding.

---

Once approved, link this document in the tracking ticket and keep it updated as work progresses.*** End Patch
