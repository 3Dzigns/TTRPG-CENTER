import { useEffect, useRef, useState } from "react";
import type { User, UserRole } from "@ttrpg-center/types";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export interface UserMenuProps {
  user: Pick<User, "displayName" | "email" | "avatarUrl" | "roles">;
  onSignOut?: () => void;
  onManageAccount?: () => void;
  onRoleChange?: (role: UserRole) => void;
  selectedRole?: UserRole | null;
  className?: string;
  trigger?: ReactNode;
}

export function UserMenu({
  user,
  onSignOut,
  onManageAccount,
  onRoleChange,
  selectedRole,
  className,
  trigger
}: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const activeRole = selectedRole ?? user.roles[0] ?? "player";

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleClick);
    }
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleToggle = () => {
    setOpen((previous) => !previous);
  };

  const handleRoleSelect = (role: UserRole) => {
    onRoleChange?.(role);
    setOpen(false);
  };

  return (
    <div ref={menuRef} className={cn("relative inline-flex items-center gap-2", className)}>
      {trigger ?? (
        <button
          type="button"
          onClick={handleToggle}
          className="flex items-center gap-2 rounded-full border border-transparent px-2 py-1 text-sm font-medium text-slate-600 transition hover:border-brand-400 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:text-slate-200 dark:hover:text-brand-200"
        >
          <span
            aria-hidden
            className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500 text-xs font-semibold uppercase text-white"
          >
            {user.avatarUrl ? (
              <img
                src={user.avatarUrl}
                alt={user.displayName}
                className="h-full w-full rounded-full object-cover"
              />
            ) : (
              user.displayName.slice(0, 2)
            )}
          </span>
          <span className="hidden text-left leading-tight md:block">
            <span className="block">{user.displayName}</span>
          </span>
        </button>
      )}

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-full z-50 mt-2 w-60 space-y-3 rounded-md border border-slate-200 bg-white p-3 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-900"
        >
          <div>
            <p className="font-medium text-slate-700 dark:text-slate-100">{user.displayName}</p>
            <p className="truncate text-xs text-slate-400 dark:text-slate-500">{user.email}</p>
          </div>
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onManageAccount?.();
              }}
              className="flex w-full items-center rounded-md px-2 py-1 text-left text-slate-600 transition hover:bg-brand-50 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Manage account
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onSignOut?.();
              }}
              className="flex w-full items-center rounded-md px-2 py-1 text-left text-slate-600 transition hover:bg-brand-50 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
