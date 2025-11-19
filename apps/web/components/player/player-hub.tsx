"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CharacterList,
  GameList,
  SourceMultiSelect
} from "@ttrpg-center/ui";
import type {
  Character,
  CharacterCreateInput,
  CharacterUpdateInput,
  Game,
  Source
} from "@ttrpg-center/types";
import {
  useMutation,
  useQuery,
  useQueryClient
} from "@tanstack/react-query";
import { getApiClient } from "../../lib/api";
import { usePlayerStore } from "../../stores/player-store";
import { CharacterCreateDialog } from "./character-create-dialog";
import { JoinGameDialog } from "./join-game-dialog";
import { useSession } from "../../hooks/useSession";

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
};

export function PlayerHub() {
  const api = getApiClient();
  const queryClient = useQueryClient();
  const { data: session } = useSession();

  const {
    activeCharacterId,
    setActiveCharacter,
    activeGameId,
    setActiveGame,
    activeSourceIds,
    setActiveSources
  } = usePlayerStore();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [joinDialogOpen, setJoinDialogOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [aiResponse, setAiResponse] = useState<string>("");
  const [promptInput, setPromptInput] = useState<string>("");
  const [isAiLoading, setIsAiLoading] = useState(false);

  const charactersQuery = useQuery({
    queryKey: ["characters"],
    queryFn: () => api.getCharacters({ userId: "me" })
  });

  const gamesQuery = useQuery({
    queryKey: ["games"],
    queryFn: () => api.getGames()
  });

  const ownedSourcesQuery = useQuery({
    queryKey: ["sources", "owned"],
    queryFn: () => api.getSources({ owned: true })
  });

  const usageQuery = useQuery({
    queryKey: ["usage", "user", "me"],
    queryFn: () => api.getUsage("user", "me")
  });

  const activeGameDetailsQuery = useQuery({
    queryKey: ["games", activeGameId],
    queryFn: () =>
      activeGameId ? api.getGameById(activeGameId) : Promise.resolve(null),
    enabled: Boolean(activeGameId)
  });

  const createCharacterMutation = useMutation({
    mutationFn: (payload: CharacterCreateInput) => api.createCharacter(payload),
    onSuccess: (character) => {
      setErrorMessage(null);
      queryClient.setQueryData<Character[] | undefined>(
        ["characters"],
        (current) => (current ? [character, ...current] : [character])
      );
      setActiveCharacter(character.id);
      setActiveGame(character.gameId ?? null);
      setActiveSources(character.activeSourceIds ?? []);
    },
    onError: (error) => {
      setErrorMessage(getErrorMessage(error));
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["characters"] });
    }
  });

  const updateCharacterMutation = useMutation({
    mutationFn: ({
      characterId,
      payload
    }: {
      characterId: string;
      payload: CharacterUpdateInput;
    }) => api.updateCharacter(characterId, payload),
    onSuccess: (updatedCharacter) => {
      setErrorMessage(null);
      queryClient.setQueryData<Character[] | undefined>(
        ["characters"],
        (current) =>
          current?.map((character) =>
            character.id === updatedCharacter.id ? updatedCharacter : character
          ) ?? current
      );
      setActiveSources(updatedCharacter.activeSourceIds ?? []);
    },
    onError: (error) => {
      setErrorMessage(getErrorMessage(error));
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["characters"] });
    }
  });

  const joinGameMutation = useMutation({
    mutationFn: (inviteCode: string) => api.joinGame(inviteCode),
    onSuccess: (game) => {
      setErrorMessage(null);
      queryClient.setQueryData<Game[] | undefined>(
        ["games"],
        (current) => {
          if (!current) {
            return [game];
          }
          const exists = current.some((item) => item.id === game.id);
          if (exists) {
            return current.map((item) => (item.id === game.id ? game : item));
          }
          return [game, ...current];
        }
      );
      setActiveGame(game.id);
    },
    onError: (error) => {
      setErrorMessage(getErrorMessage(error));
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["games"] });
    }
  });

  const characters = charactersQuery.data ?? [];
  const games = gamesQuery.data ?? [];
  const ownedSources = ownedSourcesQuery.data ?? [];
  const hasGames = games.length > 0;

  useEffect(() => {
    if (characters.length === 0) {
      return;
    }
    if (!activeCharacterId) {
      const first = characters[0];
      setActiveCharacter(first.id);
      setActiveGame(first.gameId ?? null);
      setActiveSources(first.activeSourceIds ?? []);
    }
  }, [
    characters,
    activeCharacterId,
    setActiveCharacter,
    setActiveGame,
    setActiveSources
  ]);

  const activeCharacter =
    characters.find((character) => character.id === activeCharacterId) ?? null;

  useEffect(() => {
    if (!activeCharacter) {
      if (activeSourceIds.length > 0) {
        setActiveSources([]);
      }
      return;
    }
    const nextSources = activeCharacter.activeSourceIds ?? [];
    if (
      nextSources.length !== activeSourceIds.length ||
      nextSources.some((id) => !activeSourceIds.includes(id))
    ) {
      setActiveSources(nextSources);
    }
    const nextGameId = activeCharacter.gameId ?? null;
    if (nextGameId !== activeGameId) {
      setActiveGame(nextGameId);
    }
  }, [
    activeCharacter,
    activeGameId,
    activeSourceIds,
    setActiveGame,
    setActiveSources
  ]);

  const gameSources = useMemo(() => {
    const game = activeGameDetailsQuery.data;
    if (!game) {
      return [] as Source[];
    }
    // Prefer full source objects if available
    if (game?.sources && game.sources.length > 0) {
      return game.sources.map((source) => ({ ...source, owned: !!source.owned }));
    }
    // Only use sourceIds if we can resolve them from ownedSources (no placeholders)
    if (game?.sourceIds && game.sourceIds.length > 0) {
      return game.sourceIds
        .map((id) => ownedSources.find((source) => source.id === id))
        .filter((source): source is Source => source !== undefined);
    }
    return [] as Source[];
  }, [activeGameDetailsQuery.data, ownedSources]);

  const UsageGroups = useMemo(() => {
    const meter = usageQuery.data?.meter;
    if (!meter) {
      return [];
    }

    const buildItem = (
      label: string,
      rawValue: number | undefined,
      fallbackQuota: number,
      description: string,
      disabledReason?: string
    ) => {
      const value = rawValue ?? 0;
      const quota = Math.max(value, fallbackQuota, 1);
      const disabled = rawValue === undefined;
      return {
        label,
        value: disabled ? 0 : value,
        quota,
        description,
        disabled,
        disabledReason
      };
    };

    return [
      buildItem(
        "Automation credits",
        meter.automationCreditsRemaining,
        200,
        "Triggers remaining for automation workflows."
      ),
      buildItem(
        "Text assist",
        meter.textAssistRemaining,
        150,
        "Text-based assistant prompts available.",
        "Included with upcoming premium plans."
      ),
      buildItem(
        "Audio bridge",
        meter.audioBridgeRemaining,
        60,
        "Audio transcription minutes available.",
        "Audio bridge rollout in progress."
      ),
      buildItem(
        "Discord bridge",
        meter.discordBridgeRemaining,
        40,
        "Campaign announcements synced to Discord.",
        "Discord bridge integration coming soon."
      )
    ];
  }, [usageQuery.data]);

  const combinedSources = useMemo(() => {
    const lookup = new Map<string, Source>();
    [...ownedSources, ...gameSources].forEach((source) => {
      const existing = lookup.get(source.id);
      if (existing) {
        lookup.set(source.id, { ...existing, ...source });
      } else {
        lookup.set(source.id, source);
      }
    });
    return Array.from(lookup.values());
  }, [ownedSources, gameSources]);

  const ownedSourceIds = useMemo(
    () => ownedSources.filter((source) => source.owned).map((source) => source.id),
    [ownedSources]
  );

  const UsageGroupItems = useMemo(() => {
    if (!usageQuery.data?.meter) {
      return [];
    }
    const { meter } = usageQuery.data;
    const withQuota = (value: number | undefined, fallback: number) => {
      const numeric = value ?? 0;
      return {
        value: numeric,
        quota: Math.max(numeric, fallback)
      };
    };
    const textAssist = withQuota(meter.textAssistRemaining, 100);
    const automation = withQuota(meter.automationCreditsRemaining, 100);
    const audio = withQuota(meter.audioBridgeRemaining, 100);
    const discord = withQuota(meter.discordBridgeRemaining, 100);

    return [
      {
        label: "Text Assist",
        value: textAssist.value,
        quota: textAssist.quota,
        description: "Suggested responses remaining this month."
      },
      {
        label: "Automation Credits",
        value: automation.value,
        quota: automation.quota,
        description: "Workflow triggers remaining before renewal."
      },
      {
        label: "Audio Bridge",
        value: audio.value,
        quota: audio.quota,
        description: "Voice minutes for live sessions."
      },
      {
        label: "Discord Bridge",
        value: discord.value,
        quota: discord.quota,
        description: "Discord automations available."
      }
    ];
  }, [usageQuery.data]);

  const isLoading =
    charactersQuery.isLoading ||
    gamesQuery.isLoading ||
    ownedSourcesQuery.isLoading;

  const handleCharacterCreate = async (payload: CharacterCreateInput) => {
    await createCharacterMutation.mutateAsync(payload);
  };

  const handleGameJoin = async (inviteCode: string) => {
    await joinGameMutation.mutateAsync(inviteCode);
  };

  const handleSelectCharacter = (character: Character) => {
    setActiveCharacter(character.id);
    setActiveGame(character.gameId ?? null);
    setActiveSources(character.activeSourceIds ?? []);
  };

  const handleSelectGame = (game: Game) => {
    setActiveGame(game.id);
    if (!activeCharacter) {
      return;
    }
    updateCharacterMutation.mutate({
      characterId: activeCharacter.id,
      payload: { gameId: game.id }
    });
  };

  const handleSourcesChange = (nextSourceIds: string[]) => {
    setActiveSources(nextSourceIds);
    if (!activeCharacter) {
      return;
    }
    updateCharacterMutation.mutate({
      characterId: activeCharacter.id,
      payload: { activeSourceIds: nextSourceIds }
    });
  };

  const handlePromptSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promptInput.trim()) return;

    setIsAiLoading(true);
    try {
      // TODO: Replace with actual AI API call
      // Placeholder response for now
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setAiResponse(`You asked: "${promptInput}"\n\nThis is a placeholder response. AI integration coming soon!`);
      setPromptInput("");
    } catch (error) {
      setAiResponse("Error: Unable to get AI response. Please try again.");
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Player Hub
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {session
            ? `Welcome back, ${session.displayName}. Configure your character, campaign, and sources.`
            : "Configure your character, campaign, and sources."}
        </p>
        {errorMessage ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/60 dark:text-red-200">
            {errorMessage}
          </div>
        ) : null}
      </header>

      {isLoading ? (
        <div className="grid gap-6 md:grid-cols-2">
          {[...Array(3)].map((_, index) => (
            <div
              key={index.toString()}
              className="h-64 animate-pulse rounded-lg bg-slate-200/60 dark:bg-slate-800/60"
            />
          ))}
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[2fr_1.5fr]">
          <div className="space-y-6">
            <CharacterList
              characters={characters}
              selectedId={activeCharacterId}
              onSelect={handleSelectCharacter}
              onCreateClick={() => setCreateDialogOpen(true)}
              disableCreate={!hasGames}
              disableCreateReason={
                !hasGames
                  ? "You must join a game before creating a character. Use the 'Join game' button to enter an invite code."
                  : undefined
              }
              emptyState={
                <p>
                  Create a hero to start tracking sessions and source
                  permissions.
                </p>
              }
            />

            {/* AI Assistant Section */}
            <section className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  AI Assistant
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Ask questions about rules, characters, or campaigns.
                </p>
              </div>

              {/* AI Response Box */}
              <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                <div className="min-h-[12rem] max-h-[24rem] overflow-y-auto rounded-md border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-800">
                  {isAiLoading ? (
                    <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600 dark:border-slate-600 dark:border-t-slate-300" />
                      <span>Thinking...</span>
                    </div>
                  ) : aiResponse ? (
                    <p className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200">
                      {aiResponse}
                    </p>
                  ) : (
                    <p className="text-sm italic text-slate-400 dark:text-slate-500">
                      Ask a question to get started...
                    </p>
                  )}
                </div>
              </div>

              {/* Prompt Input */}
              <form onSubmit={handlePromptSubmit} className="px-5 py-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={promptInput}
                    onChange={(e) => setPromptInput(e.target.value)}
                    placeholder="Type your question here..."
                    disabled={isAiLoading}
                    className="flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder-slate-500"
                  />
                  <button
                    type="submit"
                    disabled={isAiLoading || !promptInput.trim()}
                    className="rounded-md bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              </form>
            </section>
          </div>
          <div className="space-y-6">
            <GameList
              games={games}
              activeGameId={activeGameId}
              onSelect={handleSelectGame}
              onJoinClick={() => setJoinDialogOpen(true)}
              emptyState={
                <p>
                  Join a campaign to sync encounters and shared sources with
                  your GM.
                </p>
              }
            />
            <SourceMultiSelect
              sources={ownedSources}
              selectedIds={activeSourceIds}
              onChange={activeCharacter ? handleSourcesChange : () => {}}
              ownedSourceIds={ownedSourceIds}
              renderFooter={
                !activeCharacter ? (
                  <span>Select a character to manage available sources.</span>
                ) : ownedSources.length === 0 ? (
                  <span>No sources available. Purchase sources to enable rules lookup.</span>
                ) : (
                  <span>
                    Selected {activeSourceIds.length} of {ownedSources.length} sources.
                  </span>
                )
              }
              className={activeCharacter ? undefined : "opacity-75"}
            />
          </div>
        </div>
      )}

      <CharacterCreateDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreate={handleCharacterCreate}
        isSubmitting={createCharacterMutation.isPending}
      />
      <JoinGameDialog
        open={joinDialogOpen}
        onOpenChange={setJoinDialogOpen}
        onJoin={handleGameJoin}
        isSubmitting={joinGameMutation.isPending}
      />
    </div>
  );
}



