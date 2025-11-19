"use client";

import type { ReactNode } from "react";
import { cn } from "../lib/cn";
import { UsageMeter, type UsageMeterProps } from "./UsageMeter";

export interface UsageGroupProps {
  title: string;
  description?: string;
  items: UsageMeterProps[];
  footer?: ReactNode;
  className?: string;
}

export function UsageGroup({
  title,
  description,
  items,
  footer,
  className
}: UsageGroupProps) {
  return (
    <section
      aria-labelledby={`${title.replace(/\s+/g, "-").toLowerCase()}-heading`}
      className={cn(
        "rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
    >
      <header className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
        <h2
          id={`${title.replace(/\s+/g, "-").toLowerCase()}-heading`}
          className="text-lg font-semibold text-slate-900 dark:text-slate-100"
        >
          {title}
        </h2>
        {description ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">{description}</p>
        ) : null}
      </header>
      <div className="space-y-4 px-5 py-5">
        {items.map((item) => (
          <UsageMeter key={item.label} {...item} />
        ))}
      </div>
      {footer ? (
        <footer className="border-t border-slate-200 px-5 py-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          {footer}
        </footer>
      ) : null}
    </section>
  );
}
