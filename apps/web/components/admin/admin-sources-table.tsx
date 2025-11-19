"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AdminSourceMutationResult, Source } from "@ttrpg-center/types";
import { InlineBanner } from "@ttrpg-center/ui";
import { getApiClient } from "../../lib/api";
import { AdminSourceEditorDialog } from "./admin-source-editor-dialog";

const PAGE_SIZE = 10;

const formatDate = (value: string | undefined) => {
  if (!value) {
    return "â€”";
  }
  const date = new Date(value);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit"
  })}`;
};

interface AdminSourcesTableProps {
  onMutationCompleted?: (result: AdminSourceMutationResult) => void;
}

export function AdminSourcesTable({ onMutationCompleted }: AdminSourcesTableProps) {
  const api = getApiClient();
  const [page, setPage] = useState(0);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create");
  const [selectedSource, setSelectedSource] = useState<Source | undefined>(undefined);
  const [status, setStatus] = useState<{ traceId: string; action: string } | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["admin", "sources", { owned: false }],
    queryFn: () => api.getSources({ owned: false }),
    staleTime: 60_000
  });

  const totalPages = useMemo(() => {
    const count = sourcesQuery.data?.length ?? 0;
    return Math.max(1, Math.ceil(count / PAGE_SIZE));
  }, [sourcesQuery.data]);

  const pageItems = useMemo(() => {
    if (!sourcesQuery.data) {
      return [];
    }
    const start = page * PAGE_SIZE;
    return sourcesQuery.data.slice(start, start + PAGE_SIZE);
  }, [page, sourcesQuery.data]);

  const handleEdit = (source: Source) => {
    setSelectedSource(source);
    setEditorMode("edit");
    setEditorOpen(true);
  };

  const handleCreate = () => {
    setSelectedSource(undefined);
    setEditorMode("create");
    setEditorOpen(true);
  };

  const handleCompleted = (result: AdminSourceMutationResult) => {
    setStatus({ traceId: result.traceId, action: result.action });
    onMutationCompleted?.(result);
  };

  return (
    <section aria-labelledby="admin-sources-heading" className="space-y-4">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="admin-sources-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Central Sources
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Manage centrally curated sources available to player workspaces.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Page {page + 1} of {totalPages}
          </p>
          <button
            type="button"
            onClick={handleCreate}
            className="inline-flex items-center rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
          >
            + Add source
          </button>
        </div>
      </header>

      {status ? (
        <InlineBanner
          variant="success"
          title="Source mutation sent"
          description={`Action: ${status.action.toUpperCase()} â€¢ Trace ID: ${status.traceId}`}
          className="text-sm"
        />
      ) : null}

      <div className="overflow-hidden rounded-lg border border-slate-200 shadow-sm dark:border-slate-800">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
          <caption className="sr-only">Central source catalog</caption>
          <thead className="bg-slate-50 dark:bg-slate-900/40">
            <tr>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300"
              >
                Name
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300"
              >
                Category
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300"
              >
                Updated
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300"
              >
                Availability
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300"
              >
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white text-sm dark:divide-slate-800 dark:bg-slate-900">
            {sourcesQuery.isLoading
              ? Array.from({ length: PAGE_SIZE }).map((_, index) => (
                  <tr key={`sources-skeleton-${index}`} aria-hidden>
                    {Array.from({ length: 5 }).map((__, cellIndex) => (
                      <td key={cellIndex} className="px-4 py-3">
                        <div className="h-4 w-3/4 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
                      </td>
                    ))}
                  </tr>
                ))
              : pageItems.map((source) => (
                  <tr key={source.id} className="focus-within:bg-slate-50 focus-within:outline-none dark:focus-within:bg-slate-800/70">
                    <td className="px-4 py-3 text-slate-900 dark:text-slate-100">
                      <div className="flex flex-col">
                        <span className="font-medium">{source.name}</span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">{source.id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-600 dark:text-slate-300">{source.category}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{formatDate(source.updatedAt)}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      {source.owned ? "Owned" : "Shared"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => handleEdit(source)}
                        className="inline-flex items-center rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
            {!sourcesQuery.isLoading && pageItems.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-sm text-slate-500 dark:text-slate-400">
                  No central sources found.
                </td>
              </tr>
            ) : null}
            {sourcesQuery.isError ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-sm text-red-500">
                  Failed to load central sources.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setPage((current) => Math.max(0, current - 1))}
          disabled={page === 0}
          className="inline-flex items-center rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => setPage((current) => Math.min(totalPages - 1, current + 1))}
          disabled={page >= totalPages - 1}
          className="inline-flex items-center rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200"
        >
          Next
        </button>
      </div>

      <AdminSourceEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        mode={editorMode}
        source={selectedSource}
        onCompleted={handleCompleted}
      />
    </section>
  );
}
