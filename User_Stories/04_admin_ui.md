# Admin User Interface — User Stories & Test Plan

**Scope:** Administrative interface for system management and monitoring

## User Stories

- As a **stakeholder**, I want **System Status dashboard with health checks** (**ADM-001**, priority=critical), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Ingestion Console with progress tracking** (**ADM-002**, priority=high), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Dictionary management interface** (**ADM-003**, priority=medium), so that we meet the MVP acceptance criteria.
- As a **stakeholder**, I want **Regression test and bug bundle management** (**ADM-004**, priority=high), so that we meet the MVP acceptance criteria.

## Acceptance Criteria

### ADM-001: System Status dashboard with health checks
- [ ] Environment and build ID display
- [ ] Health checks for Astra Vector, Astra Graph, OpenAI
- [ ] ngrok public URL display for PROD environment
### ADM-002: Ingestion Console with progress tracking
- [ ] Single file and bulk upload capabilities
- [ ] Real-time progress for each ingestion pass
- [ ] Live tail of processing status
### ADM-003: Dictionary management interface
- [ ] View current dictionary entries
- [ ] Add/remove/edit dictionary terms
- [ ] Configure enrichment thresholds
### ADM-004: Regression test and bug bundle management
- [ ] List and view regression test cases
- [ ] Invalidate/remove test cases
- [ ] View and download bug bundles from thumbs-down feedback

## Test Plan

### Unit Tests

- ADM-001: Unit tests for core logic/config implementing 'System Status dashboard with health checks'.
- ADM-002: Unit tests for core logic/config implementing 'Ingestion Console with progress tracking'.
- ADM-003: Unit tests for core logic/config implementing 'Dictionary management interface'.
- ADM-004: Unit tests for core logic/config implementing 'Regression test and bug bundle management'.

### Functional (E2E) Tests

- ADM-001: End-to-end scenario demonstrating all acceptance criteria.
- ADM-002: End-to-end scenario demonstrating all acceptance criteria.
- ADM-003: End-to-end scenario demonstrating all acceptance criteria.
- ADM-004: End-to-end scenario demonstrating all acceptance criteria.

### Regression Tests

- ADM-001: Snapshot/behavioral checks to prevent future regressions.
- ADM-002: Snapshot/behavioral checks to prevent future regressions.
- ADM-003: Snapshot/behavioral checks to prevent future regressions.
- ADM-004: Snapshot/behavioral checks to prevent future regressions.

### Security Tests

- Admin API requires auth; CSRF on state-changing endpoints.
- Bug bundle downloads redacted and access-controlled.
- SSE/Websocket channels are namespaced per ENV with auth.

## Example Snippet

```typescript
// Health/status fetch
async function getStatus() {
  const [health, status] = await Promise.all([
    fetch("/health").then(r=>r.json()),
    fetch("/status").then(r=>r.json())
  ]);
  return { health, status };
}
```
