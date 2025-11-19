"use client";

import * as Dialog from "@radix-ui/react-dialog";

export interface RemoveSourceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceName: string;
  onConfirm: () => Promise<void>;
  isRemoving?: boolean;
}

export function RemoveSourceDialog({
  open,
  onOpenChange,
  sourceName,
  onConfirm,
  isRemoving = false
}: RemoveSourceDialogProps) {
  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await onConfirm();
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-950">
            <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Remove source?
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Are you sure you want to remove <strong>{sourceName}</strong> from your available sources?
              This will also remove it from any campaigns using this source.
            </Dialog.Description>

            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
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
                  disabled={isRemoving}
                  className="rounded-md border border-transparent bg-red-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:opacity-60"
                >
                  {isRemoving ? "Removing…" : "Remove source"}
                </button>
              </div>
            </form>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
