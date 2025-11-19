"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { Me } from "@ttrpg-center/types";
import { ApiError, extractTraceId as resolveTraceId } from "@ttrpg-center/api";
import { ErrorBoundaryCard } from "@ttrpg-center/ui";
import { useSession } from "../hooks/useSession";
import { useRole } from "../hooks/useRole";

interface SessionGuardProps {
  children: (session: Me) => ReactNode;
  loading?: ReactNode;
  errorFallback?: (message: string) => ReactNode;
}

const DefaultLoading = () => (
  <div className="flex h-screen items-center justify-center bg-surface-50 text-slate-500 dark:bg-surface-900 dark:text-slate-300">
    <p>Loading your dashboard...</p>
  </div>
);

function SessionGuardContent({
  session,
  children
}: {
  session: Me;
  children: (session: Me) => ReactNode;
}) {
  useRole(session.roles);

  return <>{children(session)}</>;
}

export function SessionGuard({
  children,
  loading,
  errorFallback
}: SessionGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data, isLoading, error, refetch, isFetching } = useSession();

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      const redirectPath = `${pathname}${searchParams.toString() ? `?${searchParams}` : ""}`;
      const signIn = new URL(`/auth/signin`, window.location.origin);
      signIn.searchParams.set("redirect", redirectPath);
      router.replace(signIn.toString() as any);
    }
  }, [error, pathname, router, searchParams]);

  if (isLoading) {
    return (loading ?? <DefaultLoading />) as React.ReactElement;
  }

  if (error || !data) {
    if (error instanceof ApiError && error.status === 401) {
      return (loading ?? <DefaultLoading />) as React.ReactElement;
    }

    const message =
      error instanceof Error
        ? error.message
        : "We couldn't load your session. Please try again.";

    if (errorFallback) {
      return errorFallback(message) as React.ReactElement;
    }

    return (
      <div className="flex h-screen items-center justify-center bg-surface-50 p-6 dark:bg-surface-900">
        <ErrorBoundaryCard
          title="We couldn't load your session"
          description={message}
          traceId={resolveTraceId(error)}
          onRetry={() => {
            void refetch();
          }}
          retryLabel={isFetching ? "Retrying..." : "Retry"}
          retryDisabled={isFetching}
          footer="If the issue persists, share the trace ID above with support so we can investigate quickly."
        />
      </div>
    );
  }

  return <SessionGuardContent session={data}>{children}</SessionGuardContent>;
}
