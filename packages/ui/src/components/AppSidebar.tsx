import type { PropsWithChildren, ReactNode } from "react";
import type { UserRole } from "@ttrpg-center/types";
import { cn } from "../lib/cn";

export interface SidebarNavItem {
  label: string;
  href: string;
  icon?: ReactNode;
  roles?: UserRole[];
}

export interface AppSidebarProps extends PropsWithChildren {
  role: UserRole;
  items: SidebarNavItem[];
  footer?: ReactNode;
  currentPath?: string;
  className?: string;
}

const shouldDisplayItem = (role: UserRole, item: SidebarNavItem): boolean => {
  if (!item.roles || item.roles.length === 0) {
    return true;
  }

  return item.roles.includes(role);
};

export function AppSidebar({
  role,
  items,
  footer,
  currentPath,
  className,
  children
}: AppSidebarProps) {
  return (
    <aside
      aria-label="Primary navigation"
      className={cn(
        "flex h-full w-64 flex-col border-r border-surface-100 bg-surface-50 dark:border-surface-900 dark:bg-surface-900",
        className
      )}
    >
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <nav className="space-y-2">
          {items.filter((item) => shouldDisplayItem(role, item)).map((item) => {
            const normalizedHref = item.href.split("#")[0] ?? item.href;
            const isActive =
              currentPath === normalizedHref ||
              (!!currentPath && currentPath.startsWith(normalizedHref) && normalizedHref !== "/");

            return (
              <a
                key={item.href}
                href={item.href}
                className={cn(
                  "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                  isActive
                    ? "bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-200"
                    : "text-slate-700 hover:bg-brand-50 hover:text-brand-700 dark:text-slate-200 dark:hover:bg-slate-800 dark:hover:text-slate-50"
                )}
                aria-current={isActive ? "page" : undefined}
                data-active={isActive ? "true" : "false"}
              >
                {item.icon && (
                  <span
                    aria-hidden
                    className={cn(
                      "text-brand-500 transition group-hover:text-brand-600",
                      isActive && "text-brand-600 dark:text-brand-200"
                    )}
                  >
                    {item.icon}
                  </span>
                )}
                <span>{item.label}</span>
              </a>
            );
          })}
        </nav>
        {children ? (
          <div className="mt-6 space-y-4" aria-label="Secondary content">
            {children}
          </div>
        ) : null}
      </div>
      {footer ? (
        <div className="border-t border-slate-200 px-4 py-4 dark:border-slate-800">
          {footer}
        </div>
      ) : null}
    </aside>
  );
}
