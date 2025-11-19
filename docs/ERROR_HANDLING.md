# Error Handling Toolkit

We now standardise failure UX across the Web UI with three building blocks:

1. **`ApiError` envelopes** – `packages/api` unwraps `{ error, trace_id }` responses, maps friendly messages for 4xx/5xx, and exposes `traceId`/`code` for UI use.
2. **`ErrorBoundaryCard`** – drop-in critical failure surface (trace copy + retry) exported from `@ttrpg-center/ui`.
3. **Toast provider** – `apps/web/components/toast-provider.tsx` exposes `useToast()` for transient success/info/error notifications. Banners (e.g. `InlineBanner`) remain for blocking states.

```tsx
import { ErrorBoundaryCard } from "@ttrpg-center/ui";
import { useToast } from "@/components/toast-provider";
import { ApiError } from "@ttrpg-center/api";

const { showToast } = useToast();

try {
  await action();
  showToast({ title: "Saved", variant: "success" });
} catch (error) {
  if (error instanceof ApiError) {
    return (
      <ErrorBoundaryCard
        title="We couldn't save your changes"
        description={error.message}
        traceId={error.traceId}
        onRetry={retry}
      />
    );
  }
  throw error;
}
```

Notes:
- `showToast` auto-dismisses after 6s by default (`duration: 0` keeps it onscreen).
- `ErrorBoundaryCard` exposes a copy-to-clipboard button for the trace id and disables the retry button while a new request is running.
- Use `extractTraceId(error)` (exported from the API package) when you need to surface trace ids inside banners or logs.
