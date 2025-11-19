import { cn } from "../lib/cn";
import type { ReactNode } from "react";

export type InlineBannerVariant = "info" | "success" | "warning" | "error";

const variantStyles: Record<InlineBannerVariant, string> = {
  info: "border-sky-200 bg-sky-50 text-sky-800 dark:border-sky-800 dark:bg-sky-900/40 dark:text-sky-200",
  success:
    "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  warning:
    "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  error:
    "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200"
};

export interface InlineBannerProps {
  title?: string;
  description?: ReactNode;
  variant?: InlineBannerVariant;
  traceId?: string;
  actions?: ReactNode;
  className?: string;
}

export function InlineBanner({
  title,
  description,
  variant = "info",
  traceId,
  actions,
  className
}: InlineBannerProps) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn(
        "flex flex-col gap-2 rounded-md border px-4 py-3 text-sm",
        variantStyles[variant],
        className
      )}
    >
      {title ? <p className="font-medium">{title}</p> : null}
      {description ? <div className="text-sm">{description}</div> : null}
      {traceId ? (
        <p className="text-xs opacity-80">
          Trace ID: <code>{traceId}</code>
        </p>
      ) : null}
      {actions ? <div className="mt-1 flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
