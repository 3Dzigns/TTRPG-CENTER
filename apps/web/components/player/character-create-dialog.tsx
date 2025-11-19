import * as Dialog from "@radix-ui/react-dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { CharacterCreateInput, CharacterSystem } from "@ttrpg-center/types";
import { useMemo } from "react";

const characterSchema = z.object({
  name: z.string().min(1, "Name is required"),
  className: z.string().min(1, "Class is required"),
  level: z.coerce
    .number({ invalid_type_error: "Level must be a number" })
    .min(1, "Level must be at least 1")
    .max(20, "Level must be 20 or lower"),
  system: z.string().min(1, "Select a system")
});

export type CharacterFormValues = z.infer<typeof characterSchema>;

const characterSystems: CharacterSystem[] = [
  "dnd-5e",
  "pf2e",
  "cyberpunk-red",
  "generic",
  "custom"
];

export interface CharacterCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: CharacterCreateInput) => Promise<void>;
  isSubmitting?: boolean;
}

export function CharacterCreateDialog({
  open,
  onOpenChange,
  onCreate,
  isSubmitting = false
}: CharacterCreateDialogProps) {
  const form = useForm<CharacterFormValues>({
    resolver: zodResolver(characterSchema),
    defaultValues: {
      name: "",
      className: "",
      level: 1,
      system: "dnd-5e"
    }
  });

  const systemOptions = useMemo(
    () =>
      characterSystems.map((system) => ({
        value: system,
        label: system.replace(/-/g, " ").toUpperCase()
      })),
    []
  );

  const handleSubmit = form.handleSubmit(async (values) => {
    await onCreate({
      name: values.name,
      className: values.className,
      level: values.level,
      system: values.system as CharacterSystem
    });
    form.reset();
    onOpenChange(false);
  });

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900">
            <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Create character
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Provide basic details to add a new hero to your roster.
            </Dialog.Description>

            <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
              <div>
                <label
                  htmlFor="character-name"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Name
                </label>
                <input
                  id="character-name"
                  type="text"
                  {...form.register("name")}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
                {form.formState.errors.name ? (
                  <p className="mt-1 text-xs text-red-500">
                    {form.formState.errors.name.message}
                  </p>
                ) : null}
              </div>

              <div>
                <label
                  htmlFor="character-class"
                  className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Class
                </label>
                <input
                  id="character-class"
                  type="text"
                  {...form.register("className")}
                  className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
                {form.formState.errors.className ? (
                  <p className="mt-1 text-xs text-red-500">
                    {form.formState.errors.className.message}
                  </p>
                ) : null}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="character-level"
                    className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                  >
                    Level
                  </label>
                  <input
                    id="character-level"
                    type="number"
                    min={1}
                    max={20}
                    {...form.register("level")}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  />
                  {form.formState.errors.level ? (
                    <p className="mt-1 text-xs text-red-500">
                      {form.formState.errors.level.message}
                    </p>
                  ) : null}
                </div>

                <div>
                  <label
                    htmlFor="character-system"
                    className="block text-sm font-medium text-slate-700 dark:text-slate-200"
                  >
                    System
                  </label>
                  <select
                    id="character-system"
                    {...form.register("system")}
                    className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm transition focus:border-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                  >
                    {systemOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  {form.formState.errors.system ? (
                    <p className="mt-1 text-xs text-red-500">
                      {form.formState.errors.system.message}
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
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
                  {isSubmitting ? "Creating…" : "Create character"}
                </button>
              </div>
            </form>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
