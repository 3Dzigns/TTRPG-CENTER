"use client";

import type { Source } from "@ttrpg-center/types";
import { cn } from "@ttrpg-center/ui";

interface ActiveSourcesProps {
  sources: Source[];
  isLoading?: boolean;
  className?: string;
}

export function ActiveSources({
  sources,
  isLoading = false,
  className
}: ActiveSourcesProps) {
  return (
    <section
      className={cn(
        "rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
      aria-labelledby="active-sources-heading"
    >
      <header className="mb-3">
        <h2
          id="active-sources-heading"
          className="text-base font-semibold text-slate-900 dark:text-slate-100"
        >
          Active Sources
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          These sources are available to the assistant for this game session.
        </p>
      </header>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index.toString()}
              className="h-10 animate-pulse rounded-md bg-slate-200/70 dark:bg-slate-800/60"
            />
          ))}
        </div>
      ) : sources.length === 0 ? (
        <p className="rounded-md border border-dashed border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
          No sources selected. Enable sources in the Player Hub to enrich assistant answers.
        </p>
      ) : (
        <ul className="space-y-3">
          {sources.map((source) => (
            <li
              key={source.id}
              className="flex items-start justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 text-sm transition hover:border-brand-300 dark:border-slate-700 dark:hover:border-brand-500/50"
            >
              <div>
                <p className="font-medium text-slate-800 dark:text-slate-100">{source.name}</p>
                <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {source.category}
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                Updated {new Date(source.updatedAt).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
