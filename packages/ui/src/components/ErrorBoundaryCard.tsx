'use client';

import { useCallback, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export interface ErrorBoundaryCardProps {
  title?: string;
  description?: ReactNode;
  traceId?: string;
  onRetry?: () => void;
  retryLabel?: string;
  retryDisabled?: boolean;
  actions?: ReactNode;
  className?: string;
  footer?: ReactNode;
}

/**
 * Displays a consistent critical-error surface that surfaces trace identifiers
 * and recommended remediation actions. Intended for blocking failures where
 * inline banners are insufficient.
 */
export function ErrorBoundaryCard({
  title = "Something went wrong",
  description = "We hit an unexpected error. Please try again or share the trace ID with support.",
  traceId,
  onRetry,
  retryLabel = "Retry",
  retryDisabled = false,
  actions,
  className,
  footer
}: ErrorBoundaryCardProps) {
  const [copiedTrace, setCopiedTrace] = useState(false);

  const handleCopyTrace = useCallback(async () => {
    if (!traceId || typeof navigator === "undefined") {
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(traceId);
        setCopiedTrace(true);
      }
    } catch {
      // Silently ignore clipboard failures; users can still manually copy the code.
    }
  }, [traceId]);

  const actionButtons =
    onRetry || actions ? (
      <div className="flex flex-wrap items-center gap-2">
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            disabled={retryDisabled}
            className={cn(
              "inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-brand-400/80",
              retryDisabled && "cursor-not-allowed opacity-60"
            )}
            aria-disabled={retryDisabled}
          >
            {retryLabel}
          </button>
        ) : null}
        {actions}
      </div>
    ) : null;

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-red-200 bg-white p-6 text-sm text-slate-700 shadow-sm dark:border-red-900/60 dark:bg-slate-950 dark:text-slate-200",
        className
      )}
    >
      <div className="flex flex-col gap-2">
        {title ? (
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">
            {title}
          </h2>
        ) : null}
        {description ? (
          <div className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            {description}
          </div>
        ) : null}
      </div>

      {traceId ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span>Trace ID:</span>
          <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
            {traceId}
          </code>
          <button
            type="button"
            onClick={handleCopyTrace}
            className="inline-flex items-center rounded border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            aria-label="Copy trace ID"
          >
            Copy
          </button>
          {copiedTrace ? (
            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400" aria-live="polite">
              Copied
            </span>
          ) : null}
        </div>
      ) : null}

      {actionButtons}

      {footer ? <div className="text-xs text-slate-500 dark:text-slate-400">{footer}</div> : null}
    </div>
  );
}
