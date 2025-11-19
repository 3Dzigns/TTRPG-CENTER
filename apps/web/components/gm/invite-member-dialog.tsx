"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import type { GameMemberInviteInput } from "@ttrpg-center/types";

const inviteSchema = z.object({
  email: z.string().email("Provide a valid email address"),
  role: z.enum(["player", "co-gm"])
});

type InviteFormValues = z.infer<typeof inviteSchema>;

export interface InviteMemberDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvite: (payload: GameMemberInviteInput) => Promise<void>;
  isSubmitting?: boolean;
}

export function InviteMemberDialog({
  open,
  onOpenChange,
  onInvite,
  isSubmitting = false
}: InviteMemberDialogProps) {
  const form = useForm<InviteFormValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: {
      email: "",
      role: "player"
    }
  });

  const submit = form.handleSubmit(async (values) => {
    await onInvite({
      email: values.email.trim(),
      role: values.role
    });
    form.reset();
    onOpenChange(false);
  });

  return (
    <Dialog.Root open={open} onOpenChange={(value) => {
      if (!value) {
        form.reset({ email: "", role: "player" });
      }
      onOpenChange(value);
    }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900">
            <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Invite player
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Send an invite email with campaign join instructions.
            </Dialog.Description>

            <form className="mt-6 space-y-4" onSubmit={submit}>
              <div>
                <label
                  htmlFor="invite-email"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Email address
                </label>
                <input
                  id="invite-email"
                  type="email"
                  {...form.register("email")}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
                {form.formState.errors.email ? (
                  <p className="mt-1 text-xs text-red-500">
                    {form.formState.errors.email.message}
                  </p>
                ) : null}
              </div>

              <div>
                <label
                  htmlFor="invite-role"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Role
                </label>
                <select
                  id="invite-role"
                  {...form.register("role")}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                >
                  <option value="player">Player</option>
                  <option value="co-gm">Co-GM</option>
                </select>
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
                  {isSubmitting ? "Sending…" : "Send invite"}
                </button>
              </div>
            </form>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
