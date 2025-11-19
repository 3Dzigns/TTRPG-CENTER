"use client";

import type { QueryCitation } from "@ttrpg-center/types";
import { cn } from "@ttrpg-center/ui";

interface CitationsListProps {
  citations: QueryCitation[];
  activeMessageId?: string | null;
  isStreaming?: boolean;
  className?: string;
}

export function CitationsList({
  citations,
  activeMessageId,
  isStreaming = false,
  className
}: CitationsListProps) {
  return (
    <section
      className={cn(
        "rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
      aria-labelledby="assistant-citations-heading"
    >
      <header className="mb-3">
        <h2
          id="assistant-citations-heading"
          className="text-base font-semibold text-slate-900 dark:text-slate-100"
        >
          Answer Citations
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Citations link responses to campaign sources and knowledge chunks.
        </p>
      </header>

      {isStreaming ? (
        <p className="rounded-md border border-dashed border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-300">
          Generating citations for the current response�
        </p>
      ) : citations.length === 0 ? (
        <p className="rounded-md border border-dashed border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          Select a response to view its supporting citations.
        </p>
      ) : (
        <div className="space-y-3" role="list" aria-live="polite">
          {citations.map((citation, index) => (
            <details
              key={`${citation.sourceId}:${citation.chunkId ?? index}`}
              className="group rounded-md border border-slate-200 px-4 py-3 transition hover:border-brand-300 dark:border-slate-700 dark:hover:border-brand-500/50"
              open={index === 0}
            >
              <summary className="flex cursor-pointer items-center justify-between gap-3 text-sm font-medium text-slate-700 transition group-open:text-brand-600 dark:text-slate-200 dark:group-open:text-brand-300">
                <span className="truncate">
                  {citation.title ?? `Source ${citation.sourceId}`}
                </span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  Chunk {citation.chunkId}
                </span>
              </summary>
              <div className="mt-2 space-y-2 text-xs text-slate-500 dark:text-slate-300">
                <div>
                  <span className="font-medium text-slate-600 dark:text-slate-200">
                    Source ID:
                  </span>{" "}
                  {citation.sourceId}
                </div>
                {citation.url ? (
                  <div>
                    <span className="font-medium text-slate-600 dark:text-slate-200">
                      Reference URL:
                    </span>{" "}
                    <a
                      href={citation.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-brand-600 underline hover:text-brand-500 dark:text-brand-300"
                    >
                      {citation.url}
                    </a>
                  </div>
                ) : null}
              </div>
            </details>
          ))}
          <p className="sr-only">
            Showing citations for message {activeMessageId ?? "unknown"}.
          </p>
        </div>
      )}
    </section>
  );
}
