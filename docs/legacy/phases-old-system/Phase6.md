# Phase 6 — Testing & Feedback

**Goal:** Automate regression and bug capture, enforce requirements/tests in DEV, and ensure feedback bypasses cache for instant updates.

---

## Epic E6.1 — Feedback to Tests

### US-601: 👍 Creates Regression Test

**As** a User
**I want** that when I give a “thumbs up” on an answer, the system automatically creates a regression test case
**So that** the behavior is preserved in future releases.

**Acceptance Criteria**

* Feedback UI includes 👍 button per answer.
* Clicking 👍 stores `{query, answer, chunks, model, trace_id}` as a regression test fixture.
* Test case runs automatically in next DEV/TEST pipeline.

**Testing**

* **Unit:** 👍 feedback triggers test fixture creation.
* **Functional:** Next CI run executes new regression test.
* **Regression:** Golden answer remains stable across versions.
* **Security:** User PII excluded from fixture.

---

### US-602: 👎 Creates Bug Bundle

**As** a User
**I want** that when I give a “thumbs down” on an answer, the system automatically creates a bug report bundle
**So that** developers can diagnose and fix it quickly.

**Acceptance Criteria**

* Feedback UI includes 👎 button per answer.
* Clicking 👎 stores `{query, answer, context_chunks, trace_id, logs}` into `./artifacts/bugs/{JOB_ID}/bundle.json`.
* Bug bundle visible in Admin UI (Phase 4).

**Testing**

* **Unit:** 👎 feedback creates bug JSON file.
* **Functional:** Admin UI shows new bug bundle.
* **Regression:** Bundle schema validated.
* **Security:** Bundle sanitized for secrets.

---

## Epic E6.2 — DEV Gates Enforce Requirements & Tests

### US-603: DEV Pipeline Blocks on Failed Tests

**As** a Developer
**I want** the DEV environment to enforce requirements and run all regression/bug tests
**So that** broken code never gets promoted.

**Acceptance Criteria**

* CI/CD gates include:

  * Run unit, functional, regression, and security tests.
  * Fail build if requirements not met.
* Gates run automatically on push/PR.
* Admin can view gate status in dashboard.

**Testing**

* **Unit:** Gate job fails on test failure.
* **Functional:** Bad commit blocked from promotion.
* **Regression:** Previously passing commits unaffected.
* **Security:** Test logs redact secrets.

---

## Epic E6.3 — Feedback Bypasses Cache

### US-604: Immediate Feedback Updates

**As** a User
**I want** feedback (👍/👎) to bypass cache
**So that** my input appears in the Admin UI instantly.

**Acceptance Criteria**

* Feedback POST requests use `Cache-Control: no-store`.
* Admin UI refresh shows feedback within seconds.
* Acceptance test: Submit feedback → Admin console shows it live.

**Testing**

* **Unit:** Feedback API returns updated state instantly.
* **Functional:** Admin UI refresh after feedback → entry visible.
* **Regression:** Feedback bypass doesn’t break normal cache flow.
* **Security:** Feedback submission rate-limited to prevent spam.

**Code Snippet**

```javascript
// Feedback API call bypassing cache
async function sendFeedback(traceId, rating, note) {
  return fetch("/feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store"
    },
    body: JSON.stringify({ trace_id: traceId, rating, note })
  }).then(r => r.json());
}
```

---

# Phase 6 Test Plan

### Unit Tests

* 👍 creates regression test fixture.
* 👎 creates bug bundle JSON.
* Feedback API enforces `no-store`.
* DEV gates block on failing tests.

### Functional Tests

* User 👍 → regression test created and runs in next pipeline.
* User 👎 → bug bundle visible in Admin UI.
* Failed regression test blocks promotion.
* Feedback appears in Admin dashboard instantly.

### Regression Tests

* Golden tests from Phase 5 remain intact.
* Feedback bypass doesn’t degrade normal query caching.

### Security Tests

* Feedback sanitized (no HTML/JS injection).
* Bug bundles redacted of sensitive tokens.
* Rate limits on feedback submission.

---

✅ **Definition of Done (Phase 6):**

* 👍 generates regression tests automatically.
* 👎 generates bug bundles automatically.
* DEV gates block on failing requirements/tests.
* Feedback bypasses cache → Admin UI updates immediately.
* All unit, functional, regression, and security tests green in CI.
