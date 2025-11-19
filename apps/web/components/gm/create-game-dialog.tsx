"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { GameCreateInput } from "@ttrpg-center/types";

const createGameSchema = z.object({
  title: z.string().min(1, "Game name is required"),
  summary: z.string().max(240, "Summary should be under 240 characters").optional()
});

type CreateGameFormValues = z.infer<typeof createGameSchema>;

export interface CreateGameDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: GameCreateInput) => Promise<void>;
  isSubmitting?: boolean;
}

export function CreateGameDialog({
  open,
  onOpenChange,
  onCreate,
  isSubmitting = false
}: CreateGameDialogProps) {
  const form = useForm<CreateGameFormValues>({
    resolver: zodResolver(createGameSchema),
    defaultValues: {
      title: "",
      summary: ""
    }
  });

  const submit = form.handleSubmit(async (values) => {
    await onCreate({
      title: values.title,
      summary: values.summary?.trim() || undefined,
      tier: "standard" // Default tier, will be managed later
    });
    form.reset();
    onOpenChange(false);
  });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900">
            <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Create new game
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Spin up a new campaign workspace for your party.
            </Dialog.Description>

            <form className="mt-6 space-y-5" onSubmit={submit}>
              <div>
                <label
                  htmlFor="game-title"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Game name
                </label>
                <input
                  id="game-title"
                  type="text"
                  {...form.register("title")}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
                {form.formState.errors.title ? (
                  <p className="mt-1 text-xs text-red-500">
                    {form.formState.errors.title.message}
                  </p>
                ) : null}
              </div>

              <div>
                <label
                  htmlFor="game-summary"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Summary <span className="text-xs text-slate-400">(optional)</span>
                </label>
                <textarea
                  id="game-summary"
                  rows={3}
                  {...form.register("summary")}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
                {form.formState.errors.summary ? (
                  <p className="mt-1 text-xs text-red-500">
                    {form.formState.errors.summary.message}
                  </p>
                ) : null}
              </div>

              <div className="flex justify-end gap-3">
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
                  disabled={isSubmitting}
                  className="rounded-md border border-transparent bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:opacity-60"
                >
                  {isSubmitting ? "Creating…" : "Create game"}
                </button>
              </div>
            </form>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
