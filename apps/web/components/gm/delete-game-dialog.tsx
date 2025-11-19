"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

export interface DeleteGameDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  gameName: string;
  onConfirm: () => Promise<void>;
  isDeleting?: boolean;
}

export function DeleteGameDialog({
  open,
  onOpenChange,
  gameName,
  onConfirm,
  isDeleting = false
}: DeleteGameDialogProps) {
  const [confirmation, setConfirmation] = useState("");

  const reset = () => {
    setConfirmation("");
  };

  const handleOpenChange = (value: boolean) => {
    if (!value) {
      reset();
    }
    onOpenChange(value);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (confirmation !== gameName) {
      return;
    }
    await onConfirm();
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-lg rounded-lg border border-red-200 bg-white p-6 shadow-xl dark:border-red-800 dark:bg-slate-950">
            <Dialog.Title className="text-lg font-semibold text-red-700 dark:text-red-200">
              Delete game?
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-red-600 dark:text-red-300">
              This action permanently removes the campaign, including invites and source configuration. Type the game name to confirm.
            </Dialog.Description>

            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
              <div>
                <label
                  htmlFor="delete-game-confirm"
                  className="block text-sm font-medium text-red-700 dark:text-red-200"
                >
                  Type <strong>{gameName}</strong> to confirm
                </label>
                <input
                  id="delete-game-confirm"
                  type="text"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  className="mt-1 w-full rounded-md border border-red-200 px-3 py-2 text-sm text-red-900 shadow-sm transition focus:border-red-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 dark:border-red-800 dark:bg-slate-900 dark:text-red-100"
                />
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
                  disabled={confirmation !== gameName || isDeleting}
                  className="rounded-md border border-transparent bg-red-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:opacity-60"
                >
                  {isDeleting ? "Deleting…" : "Delete game"}
                </button>
              </div>
            </form>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
