# claude.md — Project Policy (Skills + MCP)

- Always prefer **Skills** when available.
- For any stateful task, MUST use **memory** MCP (read before, write after).
- For complex analysis, plan with **sequential-thinking** MCP (3–7 steps).
- Do not fabricate tool results. If a required MCP server is missing, STOP and emit a remediation note.
- Prefer Playwright MCP for any web UI interaction; include before/after screenshots.
- Batch related actions in a single message when feasible.