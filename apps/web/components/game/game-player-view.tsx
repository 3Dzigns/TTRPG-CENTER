"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Me, Game, QueryCitation, Source } from "@ttrpg-center/types";
import { getApiClient } from "../../lib/api";
import { usePlayerStore } from "../../stores/player-store";
import { ChatPanel } from "./chat-panel";
import { ActiveSources } from "./active-sources";
import { CitationsList } from "./citations-list";

interface GamePlayerViewProps {
  session: Me;
  gameId: string;
}

const createPlaceholderSource = (id: string): Source => ({
  id,
  name: `Source ${id}`,
  category: "campaign",
  owned: false,
  updatedAt: new Date().toISOString()
});

export function GamePlayerView({ session, gameId }: GamePlayerViewProps) {
  const api = getApiClient();
  const {
    activeCharacterId,
    setActiveCharacter,
    activeSourceIds,
    setActiveSources,
    setActiveGame
  } = usePlayerStore();

  const [citationState, setCitationState] = useState<{
    citations: QueryCitation[];
    messageId: string | null;
    isStreaming: boolean;
  }>({
    citations: [],
    messageId: null,
    isStreaming: false
  });

  useEffect(() => {
    setActiveGame(gameId);
  }, [gameId, setActiveGame]);

  const gameQuery = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => api.getGameById(gameId),
    staleTime: 1000 * 30
  });

  const charactersQuery = useQuery({
    queryKey: ["characters", session.id],
    queryFn: () => api.getCharacters({ userId: "me" }),
    staleTime: 1000 * 30
  });

  const ownedSourcesQuery = useQuery({
    queryKey: ["sources", "owned"],
    queryFn: () => api.getSources({ owned: true }),
    staleTime: 1000 * 60
  });

  useEffect(() => {
    if (!charactersQuery.data || activeCharacterId) {
      return;
    }
    const match = charactersQuery.data.find((character) => character.gameId === gameId);
    if (match) {
      setActiveCharacter(match.id);
      setActiveSources(match.activeSourceIds ?? []);
    }
  }, [
    activeCharacterId,
    charactersQuery.data,
    gameId,
    setActiveCharacter,
    setActiveSources
  ]);

  const activeCharacter = useMemo(() => {
    if (!charactersQuery.data) {
      return null;
    }
    return (
      charactersQuery.data.find((character) => character.id === activeCharacterId) ??
      charactersQuery.data.find((character) => character.gameId === gameId) ??
      null
    );
  }, [activeCharacterId, charactersQuery.data, gameId]);

  const sourceDictionary = useMemo(() => {
    const map = new Map<string, Source>();
    const gameSources =
      (gameQuery.data as Game | undefined)?.sources ?? (gameQuery.data?.sourceIds ?? []).map(
        createPlaceholderSource
      );
    gameSources.forEach((source) => {
      map.set(source.id, source);
    });
    ownedSourcesQuery.data?.forEach((source) => {
      map.set(source.id, source);
    });
    return map;
  }, [gameQuery.data, ownedSourcesQuery.data]);

  const activeSources = useMemo(() => {
    if (activeSourceIds.length === 0) {
      return (gameQuery.data?.sources ?? []).map((source) => ({
        ...source,
        owned: sourceDictionary.get(source.id)?.owned ?? source.owned
      }));
    }
    return activeSourceIds.map((sourceId) => {
      const match = sourceDictionary.get(sourceId);
      if (match) {
        return match;
      }
      return createPlaceholderSource(sourceId);
    });
  }, [activeSourceIds, gameQuery.data?.sources, sourceDictionary]);

  const handleCitationsChange = useCallback(
    (citations: QueryCitation[], messageId: string | null, metadata?: { isStreaming: boolean }) => {
      const enriched = citations.map((citation) => ({
        ...citation,
        title:
          citation.title ?? sourceDictionary.get(citation.sourceId)?.name ?? `Source ${citation.sourceId}`,
        chunkId: citation.chunkId ?? "unknown"
      }));
      setCitationState({
        citations: enriched,
        messageId,
        isStreaming: metadata?.isStreaming ?? false
      });
    },
    [sourceDictionary]
  );

  const isLoading =
    gameQuery.isLoading || charactersQuery.isLoading || ownedSourcesQuery.isLoading;

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <ChatPanel
        gameId={gameId}
        actorId={session.id}
        characterId={activeCharacter?.id}
        sourceIds={activeSources.map((source) => source.id)}
        onActiveCitationsChange={(citations, messageId, metadata) =>
          handleCitationsChange(citations, messageId, metadata)
        }
        className="xl:h-[calc(100vh-10rem)]"
      />

      <div className="flex flex-col gap-6">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <header className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Active Character
            </h2>
            <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Player Mode
            </span>
          </header>
          {charactersQuery.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index.toString()}
                  className="h-10 animate-pulse rounded-md bg-slate-200/60 dark:bg-slate-800/60"
                />
              ))}
            </div>
          ) : activeCharacter ? (
            <dl className="grid gap-3 text-sm text-slate-600 dark:text-slate-300">
              <div className="flex items-center justify-between gap-3">
                <dt className="font-medium text-slate-700 dark:text-slate-200">Name</dt>
                <dd>{activeCharacter.name}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="font-medium text-slate-700 dark:text-slate-200">Class</dt>
                <dd>{activeCharacter.className}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="font-medium text-slate-700 dark:text-slate-200">Level</dt>
                <dd>{activeCharacter.level}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="font-medium text-slate-700 dark:text-slate-200">System</dt>
                <dd>{activeCharacter.system.toUpperCase()}</dd>
              </div>
            </dl>
          ) : (
            <p className="rounded-md border border-dashed border-slate-200 px-4 py-3 text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
              Select a character in the Player Hub to personalise the assistant response.
            </p>
          )}
        </section>

        <ActiveSources sources={activeSources} isLoading={isLoading} />

        <CitationsList
          citations={citationState.citations}
          activeMessageId={citationState.messageId}
          isStreaming={citationState.isStreaming}
        />
      </div>
    </div>
  );
}
