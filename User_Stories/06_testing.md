# Testing & Quality Assurance — User Stories & Test Plan

**Scope:** Automated testing and feedback systems

## User Stories

- As a **stakeholder**, I want **UAT feedback system with automatic regression creation** (**TEST-001**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Bug bundle generation from negative feedback** (**TEST-002**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **DEV environment testing gates** (**TEST-003**, priority=high), so that we meet the MVP acceptance criteria.

## Acceptance Criteria

### TEST-001: UAT feedback system with automatic regression creation
- [ ] Thumbs-up creates regression test case automatically
- [ ] Test cases include query, context, expected outcomes
- [ ] Snapshots stored for comparison
### TEST-002: Bug bundle generation from negative feedback
- [ ] Thumbs-down creates comprehensive bug bundle
- [ ] Bundle includes query, trace, metadata, user feedback
- [ ] Token usage and performance metrics captured
### TEST-003: DEV environment testing gates
- [ ] All initial requirements must pass
- [ ] All approved feature requests must pass
- [ ] Superseded requirements ignored only after approval

## Test Plan

### Unit Tests

- TEST-001: Unit tests for core logic/config implementing 'UAT feedback system with automatic regression creation'.
- TEST-002: Unit tests for core logic/config implementing 'Bug bundle generation from negative feedback'.
- TEST-003: Unit tests for core logic/config implementing 'DEV environment testing gates'.

### Functional (E2E) Tests

- TEST-001: End-to-end scenario demonstrating all acceptance criteria.
- TEST-002: End-to-end scenario demonstrating all acceptance criteria.
- TEST-003: End-to-end scenario demonstrating all acceptance criteria.

### Regression Tests

- TEST-001: Snapshot/behavioral checks to prevent future regressions.
- TEST-002: Snapshot/behavioral checks to prevent future regressions.
- TEST-003: Snapshot/behavioral checks to prevent future regressions.

### Security Tests

- Regression/bug bundles scrub secrets and PII automatically.
- CI artifacts are private; test data is synthetic or sanitized.
- Test harness prevents external calls unless explicitly mocked.

## Example Snippet

```python
def test_feedback_up_creates_regression(client, db):
    r = client.post("/feedback", json={"env":"test","thumbs":"up","q":"Fireball damage dice"})
    assert r.status_code == 200
    assert db.find_regression("Fireball damage dice") is not None
```
