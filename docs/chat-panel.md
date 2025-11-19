# Chat Panel Streaming Guide

The `ChatPanel` in the game space provides a streaming assist experience that speaks directly to `/v1/query` and listens to `/v1/events`. This guide captures usage patterns and implementation notes so designers and engineers share a common reference.

## Sending & Streaming
- Compose a prompt in the multiline textarea; `Enter` submits while `Shift+Enter` inserts a line break.
- The panel disables input until the `/v1/query` acknowledgement arrives and keeps the transcript scrolled near the latest reply.
- While the assistant is responding, a status banner and a dedicated **Stop** button appear. Selecting **Stop** cancels the client-side stream, marks the response as `Stopped`, and ignores any late SSE updates for the aborted request.

## Citations & Transcript Controls
- Each assistant response lists citation pills inline. Pills reflect the source title (or ID) and chunk identifier.
- Selecting a pill opens a modal with placeholder metadata: source name, chunk number, source ID, optional URL, and a reserved space for future chunk previews.
- Clicking any transcript card, using the new citation pills, or the "Jump to latest" control updates the side-panel citations and announces streaming state changes.

## Event & State Handling
- `useGameChat` batches chat history, posts queries through the typed API client, and persists transcripts per `actorId` + `gameId` namespace in `localStorage`.
- SSE events from `/v1/events` are parsed as `query.status` updates; late events for cancelled requests are dropped to prevent resurrecting stopped messages.
- Assistant retries reuse the prior user message payload so upstream tooling receives a consistent conversation log.

## Testing & Verification
- Unit coverage lives in `apps/web/components/game/__tests__/chat-panel.test.tsx` (submit/stream/retry flows, stop control, citation modal).
- Run `pnpm --filter @ttrpg-center/web test` after ensuring dependencies are installed. If pnpm install fails on Windows (rename errors inside `.pnpm`), rerun once filesystem locks clear before executing the test suite.
