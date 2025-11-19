"use client";

import { cn } from "../lib/cn";

const clamp01 = (value: number) => {
  if (Number.isNaN(value) || !Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(1, value));
};

export interface UsageMeterProps {
  id?: string;
  label: string;
  value: number;
  quota: number;
  description?: string;
  disabled?: boolean;
  disabledReason?: string;
  className?: string;
}

export function UsageMeter({
  id,
  label,
  value,
  quota,
  description,
  disabled = false,
  disabledReason,
  className
}: UsageMeterProps) {
  const ratio = clamp01(quota === 0 ? 0 : value / quota);
  const meterId = id ?? `usage-meter-${label.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between text-sm font-medium text-slate-700 dark:text-slate-200">
        <span id={`${meterId}-label`} className={disabled ? "opacity-70" : undefined}>
          {label}
        </span>
        {disabled ? (
          <span
            className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:bg-slate-800 dark:text-slate-500"
            title={disabledReason ?? "Coming soon"}
          >
            Coming soon
          </span>
        ) : null}
      </div>
      <div
        role="progressbar"
        aria-labelledby={`${meterId}-label`}
        aria-valuemin={0}
        aria-valuemax={quota}
        aria-valuenow={Math.min(value, quota)}
        aria-disabled={disabled}
        className={cn(
          "h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800",
          disabled && "opacity-60"
        )}
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width]",
            disabled ? "bg-slate-400 dark:bg-slate-700" : "bg-brand-500 dark:bg-brand-400"
          )}
          style={{ width: `${disabled ? 0 : ratio * 100}%` }}
          aria-hidden
        />
      </div>
      {description ? (
        <p className="text-xs text-slate-500 dark:text-slate-400">{description}</p>
      ) : null}
    </div>
  );
}
