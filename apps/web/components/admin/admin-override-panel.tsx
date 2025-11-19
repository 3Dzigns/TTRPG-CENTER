"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import type { AdminOverrideRequest, AdminOverrideResponse, AdminOverrideTarget } from "@ttrpg-center/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { InlineBanner } from "@ttrpg-center/ui";
import { getApiClient } from "../../lib/api";

const overrideSchema = z.object({
  target: z.enum(["cassandra", "mongo", "neo4j"]),
  recordPath: z.string().min(3, "Provide a record path (e.g., keyspace.table/id)."),
  payload: z
    .string()
    .min(2, "Provide a JSON payload.")
    .refine((value) => {
      try {
        JSON.parse(value);
        return true;
      } catch {
        return false;
      }
    }, "Payload must be valid JSON."),
  sourceId: z.string().optional(),
  reason: z.string().min(5, "Reason must be at least 5 characters.")
});

type OverrideFormValues = z.infer<typeof overrideSchema>;

interface AdminOverridePanelProps {
  onCompleted: (response: AdminOverrideResponse, target: AdminOverrideTarget, sourceId?: string) => void;
}

export function AdminOverridePanel({ onCompleted }: AdminOverridePanelProps) {
  const api = getApiClient();
  const queryClient = useQueryClient();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastTraceId, setLastTraceId] = useState<string | null>(null);

  const form = useForm<OverrideFormValues>({
    resolver: zodResolver(overrideSchema),
    defaultValues: {
      target: "cassandra",
      recordPath: "",
      payload: "{\n  \n}",
      sourceId: "",
      reason: ""
    }
  });

  const mutation = useMutation({
    mutationFn: async (values: OverrideFormValues) => {
      const request: AdminOverrideRequest = {
        target: values.target,
        recordPath: values.recordPath,
        payload: JSON.parse(values.payload),
        reason: values.reason,
        sourceId: values.sourceId?.trim() || undefined
      };
      return api.submitAdminOverride(request);
    },
    onSuccess: (response, variables) => {
      setErrorMessage(null);
      setLastTraceId(response.traceId);
      onCompleted(response, variables.target, variables.sourceId?.trim() || undefined);
      form.reset({
        target: variables.target,
        recordPath: "",
        payload: "{\n  \n}",
        sourceId: "",
        reason: ""
      });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
    },
    onError: (error: unknown) => {
      if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Override request failed.");
      }
    }
  });

  const handleSubmit = form.handleSubmit((values) => {
    mutation.mutate(values);
  });

  return (
    <section aria-labelledby="admin-overrides-heading" className="space-y-4">
      <header className="space-y-1">
        <h2 id="admin-overrides-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Write-through Overrides
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Submit targeted mutations to Cassandra, MongoDB, or Neo4j. Each override captures a trace ID and appends to
          the audit log.
        </p>
      </header>

      {lastTraceId ? (
        <InlineBanner
          variant="success"
          title="Override accepted"
          description={`Trace ID: ${lastTraceId}`}
          className="text-sm"
        />
      ) : null}

      {errorMessage ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
          {errorMessage}
        </div>
      ) : null}

      <form className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900" onSubmit={handleSubmit}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1">
            <label htmlFor="override-target" className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Target database
            </label>
            <select
              id="override-target"
              {...form.register("target")}
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="cassandra">Cassandra</option>
              <option value="mongo">MongoDB</option>
              <option value="neo4j">Neo4j</option>
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="override-source-id" className="text-sm font-medium text-slate-700 dark:text-slate-200">
              Source ID (optional)
            </label>
            <input
              id="override-source-id"
              type="text"
              placeholder="source-123"
              {...form.register("sourceId")}
              className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Required for Cassandra overrides to trigger re-ingestion guidance.
            </p>
          </div>
        </div>

        <div className="space-y-1">
          <label htmlFor="override-record-path" className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Record path
          </label>
          <input
            id="override-record-path"
            type="text"
            placeholder="keyspace.table/id"
            {...form.register("recordPath")}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          {form.formState.errors.recordPath ? (
            <p className="text-xs text-red-500">{form.formState.errors.recordPath.message}</p>
          ) : null}
        </div>

        <div className="space-y-1">
          <label htmlFor="override-payload" className="text-sm font-medium text-slate-700 dark:text-slate-200">
            JSON payload
          </label>
          <textarea
            id="override-payload"
            rows={8}
            {...form.register("payload")}
            className="w-full rounded-md border border-slate-200 px-3 py-2 font-mono text-xs text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          {form.formState.errors.payload ? (
            <p className="text-xs text-red-500">{form.formState.errors.payload.message}</p>
          ) : (
            <p className="text-xs text-slate-500 dark:text-slate-400">JSON will be sent verbatim to the admin service.</p>
          )}
        </div>

        <div className="space-y-1">
          <label htmlFor="override-reason" className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Reason
          </label>
          <textarea
            id="override-reason"
            rows={3}
            placeholder="Explain why this mutation is required."
            {...form.register("reason")}
            className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
          {form.formState.errors.reason ? (
            <p className="text-xs text-red-500">{form.formState.errors.reason.message}</p>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="reset"
            className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            onClick={() =>
              form.reset({
                target: form.getValues("target"),
                recordPath: "",
                payload: "{\n  \n}",
                sourceId: "",
                reason: ""
              })
            }
          >
            Clear
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {mutation.isPending ? "Submitting..." : "Submit override"}
          </button>
        </div>
      </form>
    </section>
  );
}
