import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export type ThemePreference = "light" | "dark" | "system";

export interface TopNavItem {
  label: string;
  href: string;
}

export interface TopNavProps {
  brand?: ReactNode;
  navItems?: TopNavItem[];
  onThemeToggle?: (next: ThemePreference) => void;
  theme?: ThemePreference;
  actions?: ReactNode;
  currentPath?: string;
  className?: string;
}

const themeCycle: ThemePreference[] = ["light", "dark", "system"];

const getNextTheme = (current: ThemePreference = "system"): ThemePreference => {
  const index = themeCycle.indexOf(current);
  const nextIndex = index === -1 ? 0 : (index + 1) % themeCycle.length;
  return themeCycle[nextIndex];
};

export function TopNav({
  brand,
  navItems = [],
  onThemeToggle,
  theme = "system",
  actions,
  currentPath,
  className
}: TopNavProps) {
  return (
    <header
      className={cn(
        "flex h-16 items-center justify-between border-b border-slate-200 bg-surface-50 px-6 dark:border-slate-800 dark:bg-surface-900",
        className
      )}
    >
      <div className="flex items-center gap-6">
        <div className="text-lg font-semibold text-brand-600">{brand}</div>
        <nav aria-label="Global" className="hidden md:block">
          <ul className="flex items-center gap-4 text-sm font-medium text-slate-600 dark:text-slate-300">
            {navItems.map((item) => {
              const isActive =
                currentPath === item.href ||
                (!!currentPath && currentPath.startsWith(item.href) && item.href !== "/");
              return (
                <li key={item.href}>
                  <a
                    href={item.href}
                    className={cn(
                      "rounded-md px-3 py-2 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                      isActive
                        ? "bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-200"
                        : "hover:bg-brand-50 hover:text-brand-700 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                    )}
                    aria-current={isActive ? "page" : undefined}
                    data-active={isActive ? "true" : "false"}
                  >
                    {item.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          aria-label="Toggle theme"
          onClick={() => onThemeToggle?.(getNextTheme(theme))}
          className="rounded-md border border-slate-200 px-2 py-1 text-sm font-medium text-slate-600 transition hover:border-brand-400 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200 dark:hover:border-brand-600 dark:hover:text-brand-300"
        >
          Theme: {theme}
        </button>
        {actions}
      </div>
    </header>
  );
}
