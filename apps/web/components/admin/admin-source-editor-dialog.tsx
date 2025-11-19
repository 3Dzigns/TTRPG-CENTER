"use client";

import { useEffect, useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import type {
  AdminSourceMutationAction,
  AdminSourceMutationResult,
  Source,
  SourceCategory
} from "@ttrpg-center/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { InlineBanner } from "@ttrpg-center/ui";
import { getApiClient } from "../../lib/api";
import { computeObjectDiff } from "../../lib/diff";

const categories = ["campaign", "module", "expansion", "ruleset", "homebrew"] as const;

const sourceSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  category: z.enum(categories),
  owned: z.boolean()
});

type SourceFormValues = z.infer<typeof sourceSchema>;

type EditorMode = "create" | "edit";

interface AdminSourceEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: EditorMode;
  source?: Source;
  onCompleted: (result: AdminSourceMutationResult) => void;
}

const diffLabels: Record<string, string> = {
  name: "Name",
  category: "Category",
  owned: "Owned"
};

export function AdminSourceEditorDialog({
  open,
  onOpenChange,
  mode,
  source,
  onCompleted
}: AdminSourceEditorDialogProps) {
  const api = getApiClient();
  const queryClient = useQueryClient();
  const [diffMode, setDiffMode] = useState(false);
  const [pendingValues, setPendingValues] = useState<SourceFormValues | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const form = useForm<SourceFormValues>({
    resolver: zodResolver(sourceSchema),
    defaultValues: {
      name: source?.name ?? "",
      category: (source?.category ?? "campaign") as SourceCategory,
      owned: source?.owned ?? false
    }
  });

  const mutation = useMutation({
    mutationFn: async (input: { action: AdminSourceMutationAction; values?: SourceFormValues }) => {
      const payload = {
        action: input.action,
        source: {
          id: source?.id,
          name: input.values?.name ?? "",
          category: input.values?.category ?? "campaign",
          owned: input.values?.owned ?? false
        }
      };
      return api.mutateAdminSource(payload);
    },
    onSuccess: (result) => {
      setErrorMessage(null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "sources"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "audit"] });
      form.reset({
        name: result.source.name,
        category: result.source.category,
        owned: result.source.owned ?? false
      });
      setDiffMode(false);
      setPendingValues(null);
      onCompleted(result);
      onOpenChange(false);
    },
    onError: (error: unknown) => {
      if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("Unable to apply changes.");
      }
    }
  });

  const handleReview = form.handleSubmit((values) => {
    setPendingValues(values);
    setDiffMode(true);
  });

  const diff = useMemo(() => {
    if (!pendingValues) {
      return [];
    }
    const original = source
      ? {
          name: source.name,
          category: source.category,
          owned: source.owned ?? false
        }
      : {
          name: "",
          category: "campaign",
          owned: false
        };
    return computeObjectDiff(original, pendingValues).filter((entry) => diffLabels[entry.key]);
  }, [pendingValues, source]);

  const handleConfirm = () => {
    if (!pendingValues) {
      return;
    }
    mutation.mutate({
      action: mode === "create" ? "create" : "update",
      values: pendingValues
    });
  };

  const title = mode === "create" ? "Add Source" : "Edit Source";

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setDiffMode(false);
          setPendingValues(null);
          setErrorMessage(null);
          form.reset({
            name: source?.name ?? "",
            category: (source?.category ?? "campaign") as SourceCategory,
            owned: source?.owned ?? false
          });
        }
        onOpenChange(next);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
            <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              {title}
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {mode === "create"
                ? "Create a new central source entry for players and GMs."
                : "Update metadata for the selected source."}
            </Dialog.Description>

            {errorMessage ? (
              <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
                {errorMessage}
              </div>
            ) : null}

            {!diffMode ? (
              <form className="mt-6 space-y-4" onSubmit={handleReview}>
                <div className="space-y-1">
                  <label htmlFor="source-name" className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    Name
                  </label>
                  <input
                    id="source-name"
                    type="text"
                    {...form.register("name")}
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  />
                  {form.formState.errors.name ? (
                    <p className="text-xs text-red-500">{form.formState.errors.name.message}</p>
                  ) : null}
                </div>

                <div className="space-y-1">
                  <label
                    htmlFor="source-category"
                    className="text-sm font-medium text-slate-700 dark:text-slate-200"
                  >
                    Category
                  </label>
                  <select
                    id="source-category"
                    {...form.register("category")}
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  >
                    {categories.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    id="source-owned"
                    type="checkbox"
                    {...form.register("owned")}
                    className="h-4 w-4 rounded border-slate-300 text-brand-500 focus:ring-brand-400"
                  />
                  <label htmlFor="source-owned" className="text-sm text-slate-600 dark:text-slate-300">
                    Owned (licensed directly by platform)
                  </label>
                </div>

                <div className="flex items-center justify-end gap-3">
                  <Dialog.Close asChild>
                    <button
                      type="button"
                      className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                    >
                      Cancel
                    </button>
                  </Dialog.Close>
                  <button
                    type="submit"
                    className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                  >
                    Review changes
                  </button>
                </div>
              </form>
            ) : (
              <div className="mt-6 space-y-4">
                <InlineBanner
                  variant={diff.length === 0 ? "info" : "warning"}
                  title={diff.length === 0 ? "No changes detected" : "Confirm changes"}
                  description={
                    diff.length === 0
                      ? "Update at least one field before submitting."
                      : "Review the diff below. Continue to submit to the admin service."
                  }
                />

                {diff.length > 0 ? (
                  <ul className="space-y-3">
                    {diff.map((entry) => (
                      <li
                        key={entry.key}
                        className="rounded border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
                      >
                        <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                          {diffLabels[entry.key] ?? entry.key}
                        </p>
                        <div className="mt-2 grid gap-3 text-xs text-slate-600 dark:text-slate-300 sm:grid-cols-2">
                          <div>
                            <span className="text-[11px] uppercase text-slate-400 dark:text-slate-500">Before</span>
                            <pre className="mt-1 max-h-36 overflow-auto rounded bg-slate-100 p-2 dark:bg-slate-800">
                              {JSON.stringify(entry.before, null, 2)}
                            </pre>
                          </div>
                          <div>
                            <span className="text-[11px] uppercase text-slate-400 dark:text-slate-500">After</span>
                            <pre className="mt-1 max-h-36 overflow-auto rounded bg-slate-100 p-2 dark:bg-slate-800">
                              {JSON.stringify(entry.after, null, 2)}
                            </pre>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : null}

                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => setDiffMode(false)}
                    className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                  >
                    Back to edit
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    disabled={mutation.isPending || diff.length === 0}
                    className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {mutation.isPending ? "Saving..." : "Confirm and save"}
                  </button>
                </div>
              </div>
            )}

            {mode === "edit" && source ? (
              <div className="mt-6 border-t border-slate-200 pt-4 dark:border-slate-800">
                <AlertDialog.Root>
                  <AlertDialog.Trigger asChild>
                    <button
                      type="button"
                      className="rounded-md border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition hover:border-red-300 hover:text-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 dark:border-red-800 dark:text-red-300"
                    >
                      Delete source
                    </button>
                  </AlertDialog.Trigger>
                  <AlertDialog.Portal>
                    <AlertDialog.Overlay className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm" />
                    <AlertDialog.Content className="fixed inset-0 z-50 flex items-center justify-center p-4">
                      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
                        <AlertDialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                          Delete {source.name}?
                        </AlertDialog.Title>
                        <AlertDialog.Description className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                          This removes the source from the central catalog. Players will lose access until it is
                          re-ingested.
                        </AlertDialog.Description>
                        <div className="mt-6 flex items-center justify-end gap-3">
                          <AlertDialog.Cancel asChild>
                            <button
                              type="button"
                              className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                            >
                              Cancel
                            </button>
                          </AlertDialog.Cancel>
                          <AlertDialog.Action asChild>
                            <button
                              type="button"
                              onClick={() => mutation.mutate({ action: "delete" })}
                              className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400"
                            >
                              Delete
                            </button>
                          </AlertDialog.Action>
                        </div>
                      </div>
                    </AlertDialog.Content>
                  </AlertDialog.Portal>
                </AlertDialog.Root>
              </div>
            ) : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
