## Game Space � Player Mode

The Game Space exposes the assisted chat experience for players once they open `/game/:id`.

### Layout Overview
- **ChatPanel** (left column) streams responses via `/v1/events` and archives transcripts to `localStorage` per user+game.
- **Active Character** card surfaces the character bound to the session or the first character assigned to the game.
- **Active Sources** lists the read-only sources selected from the Player Hub (owned + campaign) to clarify context.
- **Citations List** expands the citations returned with each assistant response and links back to the referenced source IDs.

### Chat Workflow
1. Submit prompts with `Enter` (Shift+Enter for multiline). Input locks until the `POST /v1/query` acknowledgement returns.
2. Streaming deltas append live while `query.status` events remain in `queued | in_progress | streaming`.
3. Completed responses persist to the local transcript and hydrate automatically on revisit. Failures surface a Retry action that replays the last exchange.

### Implementation Notes
- API client now provides `submitQuery` and `createEventsStream` helpers used by the `useGameChat` hook.
- SSE routing keys off `requestId` to correlate streamed deltas with the matching assistant message.
- Tests cover prompt submission, streaming accumulation, and retry flow via a mocked `EventSource`.

