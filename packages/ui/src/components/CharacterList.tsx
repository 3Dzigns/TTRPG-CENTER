import type { Character } from "@ttrpg-center/types";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export interface CharacterListProps {
  characters: Character[];
  selectedId?: string | null;
  onSelect?: (character: Character) => void;
  onCreateClick?: () => void;
  emptyState?: ReactNode;
  actionSlot?: ReactNode;
  className?: string;
  disableCreate?: boolean;
  disableCreateReason?: string;
}

export function CharacterList({
  characters,
  selectedId,
  onSelect,
  onCreateClick,
  emptyState,
  actionSlot,
  className,
  disableCreate = false,
  disableCreateReason
}: CharacterListProps) {
  const hasCharacters = characters.length > 0;

  return (
    <section
      className={cn(
        "rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
      aria-labelledby="player-characters-heading"
    >
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
        <div>
          <h2
            id="player-characters-heading"
            className="text-lg font-semibold text-slate-900 dark:text-slate-100"
          >
            Characters
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Choose an adventurer to focus play and source permissions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {actionSlot}
          <div className="relative group">
            <button
              type="button"
              onClick={onCreateClick}
              disabled={disableCreate}
              className={cn(
                "rounded-md border px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                disableCreate
                  ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500"
                  : "border-transparent bg-brand-500 text-white hover:bg-brand-600"
              )}
              aria-disabled={disableCreate}
            >
              New character
            </button>
            {disableCreate && disableCreateReason ? (
              <div className="pointer-events-none absolute right-0 top-full z-10 mt-1 hidden w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-lg group-hover:block dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {disableCreateReason}
              </div>
            ) : null}
          </div>
        </div>
      </header>
      <div role="list" className="max-h-80 overflow-y-auto">
        {hasCharacters ? (
          characters.map((character) => {
            const isSelected = character.id === selectedId;
            return (
              <button
                type="button"
                key={character.id}
                onClick={() => onSelect?.(character)}
                className={cn(
                  "flex w-full items-start justify-between gap-3 px-5 py-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                  isSelected
                    ? "bg-brand-50 text-brand-700 dark:bg-slate-800 dark:text-brand-200"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800"
                )}
                role="listitem"
                aria-pressed={isSelected}
              >
                <div>
                  <p className="text-sm font-medium">
                    {character.name} · L{character.level} {character.className}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    System: {character.system ?? "Unknown"}
                  </p>
                  {character.gameId ? (
                    <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                      Linked game: {character.gameId}
                    </p>
                  ) : null}
                </div>
                <span
                  className={cn(
                    "mt-1 inline-flex h-2 w-2 rounded-full",
                    isSelected
                      ? "bg-brand-500"
                      : "bg-slate-300 dark:bg-slate-600"
                  )}
                  aria-hidden
                />
              </button>
            );
          })
        ) : (
          <div className="flex flex-col items-center justify-center px-5 py-10 text-center text-sm text-slate-500 dark:text-slate-400">
            {emptyState ?? (
              <>
                <p>No characters yet.</p>
                <p className="mt-2">
                  Create one to personalize sheets and source permissions.
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
