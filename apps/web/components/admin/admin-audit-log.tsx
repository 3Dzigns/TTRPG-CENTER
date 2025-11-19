"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AdminAuditEntry } from "@ttrpg-center/types";
import { getApiClient } from "../../lib/api";

const ROW_HEIGHT = 72;
const OVERSCAN = 8;

const EMPTY_AUDIT: AdminAuditEntry[] = [];

function useDebouncedValue<T>(value: T, delay: number) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(handle);
  }, [value, delay]);

  return debounced;
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  })}`;
}

export function AdminAuditLog() {
  const api = getApiClient();
  const [actorFilter, setActorFilter] = useState("");
  const [traceFilter, setTraceFilter] = useState("");
  const debouncedActor = useDebouncedValue(actorFilter.trim(), 400);
  const debouncedTrace = useDebouncedValue(traceFilter.trim(), 400);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerHeight, setContainerHeight] = useState(400);
  const [scrollTop, setScrollTop] = useState(0);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }

    const updateHeight = () => {
      setContainerHeight(element.clientHeight);
    };

    updateHeight();
    window.addEventListener("resize", updateHeight);

    return () => {
      window.removeEventListener("resize", updateHeight);
    };
  }, []);

  const query = useQuery({
    queryKey: ["admin", "audit", { actor: debouncedActor, traceId: debouncedTrace }],
    queryFn: () =>
      api.getAdminAudit({
        actor: debouncedActor || undefined,
        traceId: debouncedTrace || undefined,
        limit: 5000
      }),
    placeholderData: (previousData) => previousData,
    staleTime: 30_000
  });

  const entries = query.data?.entries ?? EMPTY_AUDIT;
  const totalHeight = entries.length * ROW_HEIGHT;

  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const endIndex = Math.min(
    entries.length,
    Math.ceil((scrollTop + containerHeight) / ROW_HEIGHT) + OVERSCAN
  );
  const visibleEntries = entries.slice(startIndex, endIndex);

  const handleScroll: React.UIEventHandler<HTMLDivElement> = (event) => {
    setScrollTop(event.currentTarget.scrollTop);
  };

  return (
    <section aria-labelledby="admin-audit-heading" className="space-y-4">
      <header className="space-y-1">
        <h2 id="admin-audit-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Audit Log
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Track administrative actions. Filter by actor or trace ID to isolate events. Optimized for large datasets.
        </p>
      </header>

      <form
        className="grid gap-3 sm:grid-cols-2"
        aria-label="Filter audit log"
        onSubmit={(event) => event.preventDefault()}
      >
        <div className="space-y-1">
          <label htmlFor="audit-actor" className="text-xs font-medium text-slate-600 dark:text-slate-300">
            Actor
          </label>
          <input
            id="audit-actor"
            value={actorFilter}
            onChange={(event) => setActorFilter(event.target.value)}
            placeholder="e.g. gm@example.com"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="audit-trace" className="text-xs font-medium text-slate-600 dark:text-slate-300">
            Trace ID
          </label>
          <input
            id="audit-trace"
            value={traceFilter}
            onChange={(event) => setTraceFilter(event.target.value)}
            placeholder="e.g. trace_12345"
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
      </form>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          <span>{entries.length} entries</span>
          {query.isFetching ? <span className="animate-pulse">Refreshing…</span> : null}
        </div>

        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="relative max-h-[28rem] overflow-auto"
          role="region"
          aria-live="polite"
          aria-label="Audit log results"
        >
          {query.isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 8 }).map((_, index) => (
                <div
                  key={`audit-skeleton-${index.toString()}`}
                  className="h-[64px] animate-pulse rounded-md bg-slate-100 dark:bg-slate-800/80"
                  aria-hidden
                />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="p-6 text-sm text-slate-500 dark:text-slate-300">
              No audit entries match the current filters.
            </div>
          ) : (
            <div style={{ height: totalHeight ? `${totalHeight}px` : undefined, position: "relative" }}>
              {visibleEntries.map((entry, index) => {
                const rowIndex = startIndex + index;
                const offset = rowIndex * ROW_HEIGHT;
                return (
                  <div
                    key={entry.id}
                    role="row"
                    tabIndex={0}
                    className="absolute left-0 right-0 flex rounded-md border border-transparent bg-white px-4 py-3 text-sm shadow-sm transition focus-visible:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:bg-slate-900"
                    style={{ transform: `translateY(${offset}px)` }}
                  >
                    <div role="cell" className="flex-1">
                      <p className="font-medium text-slate-900 dark:text-slate-100">{entry.action}</p>
                      {entry.summary ? (
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{entry.summary}</p>
                      ) : null}
                    </div>
                    <div role="cell" className="w-48 shrink-0 text-xs text-slate-500 dark:text-slate-300">
                      <dl className="space-y-1">
                        <div>
                          <dt className="font-medium text-slate-600 dark:text-slate-300">Actor</dt>
                          <dd>{entry.actor}</dd>
                        </div>
                        <div>
                          <dt className="font-medium text-slate-600 dark:text-slate-300">Scope</dt>
                          <dd>{entry.scope}</dd>
                        </div>
                      </dl>
                    </div>
                    <div role="cell" className="w-56 shrink-0 text-xs text-slate-500 dark:text-slate-300">
                      <dl className="space-y-1">
                        <div>
                          <dt className="font-medium text-slate-600 dark:text-slate-300">Trace ID</dt>
                          <dd className="break-all" title={entry.traceId}>
                            {entry.traceId}
                          </dd>
                        </div>
                        <div>
                          <dt className="font-medium text-slate-600 dark:text-slate-300">Timestamp</dt>
                          <dd>{formatTimestamp(entry.createdAt)}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {query.isError ? (
          <div className="border-t border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-900 dark:bg-red-900/20 dark:text-red-200">
            Failed to load audit entries.
          </div>
        ) : null}
      </div>
    </section>
  );
}
