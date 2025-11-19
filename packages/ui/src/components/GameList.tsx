import type { Game } from "@ttrpg-center/types";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export interface GameListProps {
  games: Game[];
  activeGameId?: string | null;
  onSelect?: (game: Game) => void;
  onJoinClick?: () => void;
  emptyState?: ReactNode;
  className?: string;
}

export function GameList({
  games,
  activeGameId,
  onSelect,
  onJoinClick,
  emptyState,
  className
}: GameListProps) {
  return (
    <section
      className={cn(
        "rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
      aria-labelledby="player-games-heading"
    >
      <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
        <div>
          <h2
            id="player-games-heading"
            className="text-lg font-semibold text-slate-900 dark:text-slate-100"
          >
            Active Games
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Switch campaigns and keep your character in sync.
          </p>
        </div>
        <button
          type="button"
          onClick={onJoinClick}
          className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-brand-400 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200 dark:hover:text-brand-200"
        >
          Join with code
        </button>
      </header>
      <div role="list" className="max-h-72 overflow-y-auto">
        {games.length > 0 ? (
          games.map((game) => {
            const isActive = game.id === activeGameId;
            return (
              <button
                key={game.id}
                type="button"
                role="listitem"
                aria-pressed={isActive}
                onClick={() => onSelect?.(game)}
                className={cn(
                  "flex w-full items-start justify-between gap-3 px-5 py-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                  isActive
                    ? "bg-brand-50 text-brand-700 dark:bg-slate-800 dark:text-brand-200"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800"
                )}
              >
                <div>
                  <p className="text-sm font-medium">
                    {game.title}{" "}
                    <span className="text-xs font-normal uppercase tracking-wide text-slate-400 dark:text-slate-500">
                      {game.status}
                    </span>
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Sessions: {game.sessionCount}
                  </p>
                  {game.lastPlayedAt ? (
                    <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                      Last played: {new Date(game.lastPlayedAt).toLocaleString()}
                    </p>
                  ) : null}
                </div>
                {isActive ? (
                  <span
                    aria-hidden
                    className="mt-1 inline-flex h-2 w-2 rounded-full bg-brand-500"
                  />
                ) : null}
              </button>
            );
          })
        ) : (
          <div className="flex flex-col items-center justify-center px-5 py-10 text-center text-sm text-slate-500 dark:text-slate-400">
            {emptyState ?? (
              <>
                <p>No games joined yet.</p>
                <p className="mt-2">
                  Ask your GM for an invite code to join a campaign.
                </p>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
