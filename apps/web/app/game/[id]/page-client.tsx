"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Me } from "@ttrpg-center/types";
import { SessionGuard } from "../../../components/session-guard";
import { GamePlayerView } from "../../../components/game/game-player-view";
import { GameGmView } from "../../../components/game/game-gm-view";
import { getApiClient } from "../../../lib/api";

interface GamePageClientProps {
  gameId: string;
}

const LoadingFallback = () => (
  <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-500 dark:text-slate-300">
    Loading game workspace...
  </div>
);

const Unauthorized = ({ session }: { session: Me }) => (
  <section className="mx-auto flex max-w-3xl flex-col items-center justify-center gap-4 rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
    <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
      Player access required
    </h1>
    <p className="text-sm text-slate-500 dark:text-slate-400">
      The game workspace is available to players and GMs. Your account ({session.email}) does not
      have the required role.
    </p>
  </section>
);

const canAccessGame = (session: Me) =>
  session.roles.includes("player") || session.roles.includes("gm") || session.roles.includes("admin");

function GamePageContent({ session, gameId }: { session: Me; gameId: string }) {
  const api = getApiClient();

  const gameQuery = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => api.getGameById(gameId),
    staleTime: 1000 * 30
  });

  const members = gameQuery.data?.members ?? null;

  const isGameGm = useMemo(() => {
    if (!members || members.length === 0) {
      return session.roles.includes("gm") || session.roles.includes("admin");
    }
    const membership = members.find((member) => member.userId === session.id);
    if (!membership) {
      return session.roles.includes("gm") || session.roles.includes("admin");
    }
    return membership.role === "gm" || membership.role === "co-gm" || session.roles.includes("admin");
  }, [members, session.id, session.roles]);

  if (!canAccessGame(session)) {
    return <Unauthorized session={session} />;
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Game Space</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Collaborate with the assistant for rules lookups, summaries, and source-backed chat.
        </p>
      </header>
      {isGameGm ? (
        <GameGmView session={session} gameId={gameId} />
      ) : (
        <GamePlayerView session={session} gameId={gameId} />
      )}
    </div>
  );
}

export function GamePageClient({ gameId }: GamePageClientProps) {
  return (
    <SessionGuard loading={<LoadingFallback />}>
      {(session) => <GamePageContent session={session} gameId={gameId} />}
    </SessionGuard>
  );
}
