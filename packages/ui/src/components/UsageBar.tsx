import { cn } from "../lib/cn";

export interface UsageBarProps {
  used: number;
  total: number;
  label?: string;
  className?: string;
}

export function UsageBar({
  used,
  total,
  label = "Usage",
  className
}: UsageBarProps) {
  const percentRemaining = total > 0 ? ((total - used) / total) * 100 : 100;

  // Determine color based on remaining percentage
  const getBarColor = () => {
    if (percentRemaining <= 25) return "bg-red-500";
    if (percentRemaining <= 75) return "bg-yellow-500";
    return "bg-green-500";
  };

  const getOutlineColor = () => {
    if (percentRemaining <= 25) return "border-red-200 dark:border-red-800";
    if (percentRemaining <= 75) return "border-yellow-200 dark:border-yellow-800";
    return "border-green-200 dark:border-green-800";
  };

  return (
    <section
      className={cn(
        "rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
      aria-labelledby="usage-bar-heading"
    >
      <div className="flex items-center justify-between mb-3">
        <h2
          id="usage-bar-heading"
          className="text-base font-semibold text-slate-900 dark:text-slate-100"
        >
          {label}
        </h2>
        <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
          {Math.round(percentRemaining)}%
        </span>
      </div>

      <div
        className={cn(
          "relative h-6 rounded-full border-2",
          getOutlineColor()
        )}
        role="progressbar"
        aria-valuenow={percentRemaining}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${Math.round(percentRemaining)}% of monthly usage remaining`}
      >
        <div
          className={cn(
            "absolute inset-0.5 rounded-full transition-all duration-500 ease-out",
            getBarColor()
          )}
          style={{ width: `${Math.max(0, Math.min(100, percentRemaining))}%` }}
        />
      </div>

      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        {Math.round(total - used).toLocaleString()} of {total.toLocaleString()} remaining this month
      </p>
    </section>
  );
}
