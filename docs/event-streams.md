# Event Streams

A shared SSE utility powers live updates from `/v1/events`.

## API Client
`createEventStream(url, options)` (exported from `@ttrpg-center/api`) wraps `EventSource` with:
- exponential backoff + jitter on errors (defaults: 1s, max 5 retries)
- optional `parse` (string → event or array of events) and `filter` callbacks
- `subscribe(listener)` to receive typed payloads; returns unsubscribe function
- `close()` to permanently dispose the stream when the component unmounts

```ts
import { createEventStream } from "@ttrpg-center/api";

const stream = createEventStream("/v1/events", {
  parse: (data) => JSON.parse(data),
  filter: (event) => event.type === "query.status"
});

const unsubscribe = stream.subscribe((event) => {
  console.log(event.requestId, event.status);
});
```

## React Hook
`useEvents(url, options)` in `@ttrpg-center/ui` wraps the client for React usage. It exposes `{ status, event }` and optional `onEvent` callback.

```ts
const { event } = useEvents<QueryStatusEvent>("/v1/events", {
  filter: (payload) => payload.type === "query.status"
});
```

## Guidelines
- Always unsubscribe/close the stream when the owning component unmounts (hook handles this for you).
- Narrow payloads via `parse` + `filter` so downstream code only sees the messages it expects.
- Errors are logged but non-blocking; design UI to handle temporary disconnects gracefully.
