"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { InlineBanner } from "@ttrpg-center/ui";
import type { AdminOverrideResponse, AdminSourceMutationResult } from "@ttrpg-center/types";
import { AdminHealthGrid } from "./admin-health-grid";
import { AdminSourcesTable } from "./admin-sources-table";
import { AdminUsersTable } from "./admin-users-table";
import { AdminAuditLog } from "./admin-audit-log";
import { AdminOverridePanel } from "./admin-override-panel";
import { useAdminOverrideStream } from "../../hooks/useAdminOverrideStream";

export function AdminDashboard() {
  const queryClient = useQueryClient();
  const [lastOverride, setLastOverride] = useState<{
    traceId: string;
    target: string;
    sourceId?: string;
  } | null>(null);

  const [reingestSources, setReingestSources] = useState<Map<string, string>>(new Map());

  const handleOverrideCompleted = (
    response: AdminOverrideResponse,
    target: string,
    sourceId?: string
  ) => {
    setLastOverride({ traceId: response.traceId, target, sourceId });
    if (target === "cassandra" && sourceId) {
      setReingestSources((current) => {
        const next = new Map(current);
        next.set(sourceId, response.traceId);
        return next;
      });
    }
  };

  const handleSourceMutation = (result: AdminSourceMutationResult) => {
    setLastOverride({ traceId: result.traceId, target: "catalog" });
  };

  useAdminOverrideStream((event) => {
    setLastOverride({ traceId: event.traceId, target: event.target, sourceId: event.sourceId });
    if (event.target === "cassandra" && event.sourceId && event.traceId) {
      setReingestSources((current) => {
        const next = new Map(current);
        next.set(event.sourceId!, event.traceId!);
        return next;
      });
    }
    void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
  });

  const reingestBanner = useMemo(() => {
    if (reingestSources.size === 0) {
      return null;
    }
    const entries = Array.from(reingestSources.entries());
    return (
      <InlineBanner
        variant="warning"
        title="Re-ingest recommended"
        description={`Cassandra records updated for ${entries.length} source${entries.length > 1 ? "s" : ""}. Trigger re-ingestion to propagate changes.`}
        actions={
          <button
            type="button"
            onClick={() => setReingestSources(new Map())}
            className="rounded border border-slate-200 px-3 py-1 text-xs font-medium transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:hover:border-slate-600"
          >
            Dismiss
          </button>
        }
        className="text-sm"
      />
    );
  }, [reingestSources]);

  const lastOverrideBanner = lastOverride ? (
    <InlineBanner
      variant="info"
      title="Override event recorded"
      description={`Trace ID: ${lastOverride.traceId}${lastOverride.sourceId ? ` â€¢ Source: ${lastOverride.sourceId}` : ""}`}
      className="text-sm"
    />
  ) : null;

  return (
    <div className="space-y-10">
      {reingestBanner}
      {lastOverrideBanner}
      <AdminHealthGrid />
      <AdminSourcesTable onMutationCompleted={handleSourceMutation} />
      <AdminUsersTable />
      <AdminOverridePanel onCompleted={handleOverrideCompleted} />
      <AdminAuditLog />
    </div>
  );
}
