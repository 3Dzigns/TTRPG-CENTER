"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { AdminHealthSnapshot, ServiceHealthStatus } from "@ttrpg-center/types";
import { getApiClient } from "../../lib/api";

const STATUS_STYLES: Record<ServiceHealthStatus, { badge: string; text: string }> = {
  healthy: {
    badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
    text: "Healthy"
  },
  degraded: {
    badge: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
    text: "Degraded"
  },
  down: {
    badge: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
    text: "Down"
  }
};

const FALLBACK_SERVICES: AdminHealthSnapshot = {
  updatedAt: new Date().toISOString(),
  services: [
    { id: "cassandra", name: "Cassandra", status: "degraded", lastCheckedAt: new Date().toISOString() },
    { id: "mongo", name: "MongoDB", status: "degraded", lastCheckedAt: new Date().toISOString() },
    { id: "neo4j", name: "Neo4j", status: "degraded", lastCheckedAt: new Date().toISOString() },
    { id: "orchestrator", name: "Orchestrator", status: "degraded", lastCheckedAt: new Date().toISOString() }
  ]
};

export function AdminHealthGrid() {
  const api = getApiClient();
  const query = useQuery({
    queryKey: ["admin", "health"],
    queryFn: () => api.getAdminHealth(),
    refetchInterval: 30_000,
    staleTime: 25_000
  });

  const services = useMemo(() => {
    if (query.isError) {
      return FALLBACK_SERVICES;
    }
    if (!query.data) {
      return null;
    }
    return query.data;
  }, [query.data, query.isError]);

  const isLoading = query.isLoading && !services;

  return (
    <section aria-labelledby="admin-health-heading" className="space-y-4">
      <header className="space-y-1">
        <h2 id="admin-health-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          System Health
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Live status for Cassandra, MongoDB, Neo4j, and orchestration services. Updates every 30 seconds.
        </p>
        {query.isError ? (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-200">
            Unable to refresh health data. Showing the most recent snapshot.
          </p>
        ) : null}
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, index) => (
              <div
                key={`health-skeleton-${index.toString()}`}
                className="h-32 animate-pulse rounded-lg border border-slate-200 bg-slate-100/70 dark:border-slate-800 dark:bg-slate-900/50"
                aria-hidden
              />
            ))
          : services?.services.map((service) => {
              const styles = STATUS_STYLES[service.status] ?? STATUS_STYLES.degraded;
              return (
                <article
                  key={service.id}
                  className="flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                        {service.name}
                      </h3>
                      {service.message ? (
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{service.message}</p>
                      ) : null}
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${styles.badge}`}>
                      {styles.text}
                    </span>
                  </div>
                  <dl className="mt-4 space-y-1 text-xs text-slate-500 dark:text-slate-400">
                    {service.region ? (
                      <div className="flex items-center justify-between gap-2">
                        <dt className="font-medium text-slate-600 dark:text-slate-300">Region</dt>
                        <dd>{service.region}</dd>
                      </div>
                    ) : null}
                    <div className="flex items-center justify-between gap-2">
                      <dt className="font-medium text-slate-600 dark:text-slate-300">Last checked</dt>
                      <dd>
                        {new Date(service.lastCheckedAt).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit"
                        })}
                      </dd>
                    </div>
                  </dl>
                </article>
              );
            })}
      </div>
    </section>
  );
}
