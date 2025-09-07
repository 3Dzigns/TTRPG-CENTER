# BUG-008: Graph Builder Not Invoked by Runtime Routes

## Summary
`src_common/graph/build.py` (GraphBuilder) is referenced in tests and documentation but is not called by any runtime HTTP route. Knowledge graph construction from enriched chunks appears to be unintegrated.

## Environment
- Component: Graph Builder
- Date Reported: 2025-09-06
- Severity: Medium (feature unused in production flows)

## Steps to Reproduce
1. Search for imports of `src_common.graph.build` in app/routers; only tests/doc references are found.
2. Run the app and inspect available routes; no route triggers graph build.

## Expected Behavior
- When applicable (e.g., ingestion pipeline completion), graph builder is invoked to populate `GraphStore`.

## Actual Behavior
- Graph builder not called; `GraphStore` used by planner/executor lacks build integration.

## Root Cause Analysis
- Graph build path not yet wired to ingestion outputs or admin actions.

## Technical Details
- Module: `src_common/graph/build.py:1`
- Store: `src_common/graph/store.py:1`
- Admin/Ingestion services: `src_common/admin/*`

## Fix Required
- Add an admin or ingestion-triggered route/action to run graph build on enriched chunks; persist outputs to `GraphStore`.

## Priority
Medium

## Related Files
- `src_common/graph/build.py:1`
- `src_common/admin/ingestion.py:1`
- `src_common/graph/store.py:1`

## Testing Notes
- Extend `tests/unit/test_graph_build.py` and a functional test to call the new route and verify nodes/edges persisted.

