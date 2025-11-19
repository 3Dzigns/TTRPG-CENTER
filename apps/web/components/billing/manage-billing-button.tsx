"use client";

import { useState } from "react";
import { InlineBanner, cn } from "@ttrpg-center/ui";
import { useBillingLink, type BillingPortalResult } from "../../hooks/useBillingLink";

interface ManageBillingButtonProps {
  scope: "user" | "game";
  scopeId?: string | null;
  className?: string;
  description?: string;
  buttonLabel?: string;
  disabledLabel?: string;
}

export function ManageBillingButton({
  scope,
  scopeId = null,
  className,
  description = "You'll leave TTRPG Center to manage billing in a new tab.",
  buttonLabel = "Manage Billing",
  disabledLabel = "Select a game to manage billing"
}: ManageBillingButtonProps) {
  const { openBillingPortal, isLoading } = useBillingLink(scope, scopeId);
  const [error, setError] = useState<Extract<BillingPortalResult, { success: false }> | null>(null);

  const handleClick = async () => {
    const result = await openBillingPortal();
    if (result.success) {
      setError(null);
    } else if (result.reason !== "missing-context") {
      setError(result);
    } else {
      setError({
        success: false,
        message: disabledLabel,
        reason: "missing-context"
      });
    }
  };

  const isDisabled = isLoading || !scopeId;

  return (
    <div className={cn("space-y-3", className)}>
      {description ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">{description}</p>
      ) : null}
      {error ? (
        <InlineBanner
          variant="error"
          description={error.message}
          traceId={error.traceId}
        />
      ) : null}
      <button
        type="button"
        onClick={handleClick}
        disabled={isDisabled}
        className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-brand-500/60"
        aria-disabled={isDisabled}
      >
        {isLoading ? "Opening…" : buttonLabel}
      </button>
    </div>
  );
}
