import * as Dialog from "@radix-ui/react-dialog";
import { useForm } from "react-hook-form";

export interface JoinGameDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onJoin: (inviteCode: string) => Promise<void>;
  isSubmitting?: boolean;
}

export function JoinGameDialog({
  open,
  onOpenChange,
  onJoin,
  isSubmitting = false
}: JoinGameDialogProps) {
  const { register, handleSubmit, reset, formState } = useForm<{
    inviteCode: string;
  }>({ defaultValues: { inviteCode: "" } });

  const submit = handleSubmit(async ({ inviteCode }) => {
    await onJoin(inviteCode.trim());
    reset();
    onOpenChange(false);
  });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900">
            <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Join a game
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Paste the invite code provided by your GM.
            </Dialog.Description>
            <form className="mt-6 space-y-4" onSubmit={submit}>
              <div>
                <label
                  htmlFor="game-invite-code"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Invite code
                </label>
                <input
                  id="game-invite-code"
                  type="text"
                  {...register("inviteCode", {
                    required: "Invite code is required"
                  })}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
                {formState.errors.inviteCode ? (
                  <p className="mt-1 text-xs text-red-500">
                    {formState.errors.inviteCode.message}
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
                  {isSubmitting ? "Joining…" : "Join game"}
                </button>
              </div>
            </form>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
