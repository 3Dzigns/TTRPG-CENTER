"use client";

import { Suspense, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AppSidebar,
  TopNav,
  UserMenu,
  UsageBar,
  type ThemePreference
} from "@ttrpg-center/ui";
import { useTheme } from "../../components/theme-provider";
import { SessionGuard } from "../../components/session-guard";
import { sidebarNavItems, topNavItems } from "../../lib/navigation";
import { useRole } from "../../hooks/useRole";
import { signOut } from "../../lib/auth";
import { useAuthStore } from "../../stores/auth-store";

interface DashboardClientProps {
  children: React.ReactNode;
}

function DashboardContent({ children }: DashboardClientProps) {
  const { theme, setTheme } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const clearAuth = useAuthStore((state) => state.clear);

  const handleThemeToggle = (next: ThemePreference) => {
    setTheme(next);
  };

  return (
    <SessionGuard>
      {(session) => {
        const { role, setRole } = useRole(session.roles);
        const activeRole = (role ?? "player") as "player" | "gm" | "admin";

        const navItems = useMemo(() => {
          return topNavItems.filter((item) =>
            session.roles.some((roleName) => item.label.toLowerCase().includes(roleName))
          );
        }, [session.roles]);

        const handleSignOut = async () => {
          await signOut();
          clearAuth();
          queryClient.clear();
          router.replace("/auth/signin");
        };

        return (
          <div className="flex min-h-screen bg-surface-50 text-slate-900 dark:bg-surface-900 dark:text-slate-50">
            <AppSidebar
              role={activeRole}
              items={sidebarNavItems}
              currentPath={pathname}
              footer={
                <div className="space-y-3">
                  <p className="text-xs text-slate-400 dark:text-slate-500">
                    Signed in as <span className="font-medium">{session.displayName}</span>
                  </p>
                  {/* Player Usage - always shown */}
                  {/* TODO: Connect to real token usage data when API is updated */}
                  <UsageBar
                    used={0}
                    total={1000000}
                    label="Player Usage"
                  />
                  {/* GM Usage - only shown if user has GM role */}
                  {session.roles.includes("gm") && (
                    <>
                      {/* TODO: Connect to real GM token usage data when API is updated */}
                      <UsageBar
                        used={0}
                        total={1000000}
                        label="GM Usage"
                      />
                    </>
                  )}
                </div>
              }
            />
            <div className="flex flex-1 flex-col">
              <TopNav
                brand={<span>TTRPG Center</span>}
                navItems={navItems}
                theme={theme}
                currentPath={pathname}
                onThemeToggle={handleThemeToggle}
                actions={
                  <UserMenu
                    user={session}
                    onManageAccount={() => router.push("/settings")}
                    onSignOut={handleSignOut}
                  />
                }
              />
              <main
                id="main-content"
                tabIndex={-1}
                className="flex-1 overflow-y-auto bg-surface-50 p-6 focus:outline-none dark:bg-surface-900"
              >
                {children}
              </main>
            </div>
          </div>
        );
      }}
    </SessionGuard>
  );
}

export default function DashboardClient({ children }: DashboardClientProps) {
  return (
    <Suspense fallback={<div className="p-6 text-slate-500">Loading workspace…</div>}>
      <DashboardContent>{children}</DashboardContent>
    </Suspense>
  );
}
