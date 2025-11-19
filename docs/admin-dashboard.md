# Admin Dashboard Read-Only & Overrides

The admin workspace surfaces platform health, central sources, users, and audit events in a single view. Manual overrides expand capabilities with audited write-through actions.

## Highlights
- **System Health**: Cassandra, MongoDB, Neo4j, and orchestrator services refresh every 30 seconds. Status badges reflect the latest check and region when available.
- **Central Sources**: Paginated table of shared sources fetched via /v1/sources?owned=false, with inline edit, create, and delete flows. Saving presents a diff preview and captures the 	raceId.
- **Users**: Read-only roster of accounts with their role badges.
- **Write-through Overrides**: Form-based interface posts to /v1/admin/override for Cassandra/Mongo/Neo4j records, including reason capture and JSON payload validation.
- **Audit Log**: Virtualized list supports actor and trace ID filters while efficiently rendering large result sets. New overrides trigger immediate refreshes through the SSE stream.
- **Re-ingestion Guidance**: Cassandra overrides flag affected sources with a banner prompting re-ingestion before closing the dialog.

## Developer Notes
- Health data loads through pi.getAdminHealth() with automatic refetch. Errors fall back to the last snapshot and surface a warning banner.
- Source mutations call pi.mutateAdminSource() and invalidate both source and audit caches. Diff previews compare name/category/owned fields before dispatching mutations.
- Overrides rely on pi.submitAdminOverride(); payload is JSON-parsed with zod validation, and the panel highlights the trace ID on success.
- useAdminOverrideStream listens to /v1/events for dmin_override messages, enqueuing re-ingestion banners and forcing audit query refreshes.
- Tables embrace accessible markup (captions, header cells) and keyboard focus states. Audit virtualization uses fixed row heights for smooth scrolling at 10k+ entries.

## Follow-Up
Re-ingestion workflow automation and richer diff visualizations (JSON tree) are slated for later milestones.
