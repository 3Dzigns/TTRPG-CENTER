# Query Orchestration Contract

This document captures the canonical request/response formats for the `/v1/query` orchestration endpoint and its accompanying server‑sent events. The goal is to let UI and backend teams iterate independently with shared schemas and mocks.

---

## 1. Summary
- **Endpoint:** `POST /v1/query`
- **Events:** `GET /v1/events` (SSE stream) – see mock instructions below
- **Version:** `2025-10-17` (aligned with WebUI Standards v0.1 sections A·5.7 & A·9)
- **Artifacts:** Exported from `@ttrpg-center/types`
  - `queryRequestSchema` / `queryRequestJsonSchema`
  - `queryResponseSchema` / `queryResponseJsonSchema`
  - `queryStatusEventSchema` / `queryStatusEventJsonSchema`

---

## 2. Request Payload

```ts
type QueryRequestInput = z.infer<typeof queryRequestSchema>;
```

```jsonc
POST /v1/query
Content-Type: application/json

{
  "scope": "game",
  "gameId": "game-1",
  "actorId": "user-1",
  "characterId": "char-7",
  "messages": [
    { "role": "system", "content": "You are the TTRPG campaign orchestrator." },
    { "role": "user", "content": "Summarize the last session for the party." }
  ],
  "sourceIds": ["src-arcana", "src-legends"]
}
```

### Validation Rules
- `scope` – currently only `"game"` (future‑proofed via Zod literal).
- `messages` – at least one entry; `content` capped at 4 000 characters.
- `characterId` – optional / nullable (GM queries) but must be non-empty if provided.
- `sourceIds` – optional array of non-empty strings.
- Additional metadata can be supplied via the optional `metadata` map (ignored by the mock, forwarded by the real service).

---

## 3. Response Payload

```ts
type QueryResponse = z.infer<typeof queryResponseSchema>;
```

```json
HTTP/1.1 200 OK
Content-Type: application/json

{
  "requestId": "req-123e4567",
  "status": "queued",
  "issuedAt": "2025-10-17T09:30:12.000Z"
}
```

- `status` reflects initial orchestration state (`queued | in_progress | streaming | completed | failed`).
- `requestId` is referenced by downstream SSE messages.

Errors return `400` with diagnostics:

```json
{
  "error": {
    "message": "Invalid /v1/query payload",
    "issues": [
      { "path": ["messages", 0, "content"], "message": "Message content cannot be empty" }
    ]
  }
}
```

---

## 4. Event Stream (`/v1/events`)

Every orchestration status update is sent as a JSON payload via SSE (`data:` lines). The canonical schema:

```ts
type QueryStatusEvent = z.infer<typeof queryStatusEventSchema>;
```

| Field | Type | Notes |
|-------|------|-------|
| `type` | `"query.status"` | Distinguishes payloads on shared streams. |
| `requestId` | string | Matches `QueryResponse.requestId`. |
| `status` | `QueryRunStatus` | Same union as response. |
| `delta` | string? | Streaming fragment appended to prior content. |
| `answer` | string? | Final consolidated response (sent on completion). |
| `citations` | `QueryCitation[]` | Optional references to sources (`sourceId`, `chunkId`, `title`, `url`). |
| `error` | string? | Present when `status === "failed"`. |

### Example Stream

```
: connected
data: {"type":"query.status","requestId":"req-123","status":"in_progress"}

data: {"type":"query.status","requestId":"req-123","status":"streaming","delta":"Drawing on the latest reports..."}

data: {"type":"query.status","requestId":"req-123","status":"streaming","delta":" The keystone resonates with elemental energy."}

data: {
  "type": "query.status",
  "requestId": "req-123",
  "status": "completed",
  "answer": "The party secured the planar keystone...",
  "citations": [
    { "sourceId": "src-arcana", "chunkId": "arcana-42", "title": "Arcane Compendium · Chapter 5" },
    { "sourceId": "src-legends", "chunkId": "legends-3", "title": "Legends of the Realm · Keystone Myths" }
  ]
}
```

Clients accumulate `delta` fragments while `status === "streaming"`. Once `status` transitions to `completed` the `answer` field represents the authoritative content. If `status === "failed"` the `error` field must be displayed to the user alongside the trace ID surfaced by the REST response.

---

## 5. Zod & JSON Schema Exports

```ts
import {
  queryRequestSchema,
  queryRequestJsonSchema,
  queryResponseSchema,
  queryStatusEventSchema,
  queryStatusEventJsonSchema
} from "@ttrpg-center/types";
```

Use the Zod instances for runtime validation and type inference; the JSON Schemas can be published or embedded in backend codegen pipelines. The schema names are `QueryRequest`, `QueryResponse`, and `QueryStatusEvent` respectively.

---

## 6. Mock Implementation

The monorepo ships a minimal mock server under `apps/web/app/api/mock/`:

| Route | Method | Description |
|-------|--------|-------------|
| `/api/mock/query` | POST | Validates payload via `queryRequestSchema` and returns a canned `QueryResponse`. |
| `/api/mock/events` | GET | Emits an SSE stream that walks through queued → streaming (with `delta`s) → completed with citations. Optional `requestId` query parameter defaults to `"mock-request"`. |

### Running Against Mocks

```bash
# .env.local (or shell)
NEXT_PUBLIC_API_BASE=/api/mock

pnpm --filter @ttrpg-center/web dev
```

- REST calls now target `/api/mock/query`.
- `useGameChat` and `useAdminOverrideStream` subscribe to `/api/mock/events` transparently (the base URL drives both REST and SSE endpoints).
- Playwright smoke tests already rely on in-memory fixtures; use these mocks for manual QA without backend dependencies.

When hitting the SSE endpoint manually:

```bash
curl -N "http://localhost:3000/api/mock/events?requestId=req-demo"
```

---

## 7. Change Management
- **Versioning:** Any contract change must update the Zod schema, regenerate JSON schemas, and record the revision date in this document.
- **Backwards compatibility:** Introduce additive fields whenever possible. Removing or renaming properties requires a major revision and a communication plan with the backend team.
- **Testing:** Update Playwright smoke tests or Vitest suites to exercise new scenarios (e.g., error surfaces, additional event statuses).

---

Maintainers: `#webui-platform` (frontend) & `#orchestration` (backend). Please raise a shared RFC before altering the contract shape.*** End Patch
