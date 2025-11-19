"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { InlineBanner, UsageGroup, SourceMultiSelect, cn } from "@ttrpg-center/ui";
import type {
  Game,
  GameMember,
  GameMemberInviteInput,
  GameMemberRole,
  GameUpdateInput
} from "@ttrpg-center/types";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createApiClient, ApiError } from "@ttrpg-center/api";
import { CreateGameDialog } from "./create-game-dialog";
import { DeleteGameDialog } from "./delete-game-dialog";
import { InviteMemberDialog } from "./invite-member-dialog";
import { RemoveSourceDialog } from "./remove-source-dialog";
import { useSession } from "../../hooks/useSession";
import { extractTraceId } from "../../lib/errors";
import { ManageBillingButton } from "../billing/manage-billing-button";
import { useToast } from "../toast-provider";

type TabKey = "members" | "sources" | "settings";

interface BannerState {
  message: string;
  variant: "info" | "success" | "warning" | "error";
  traceId?: string;
}

const tabs: { key: TabKey; label: string }[] = [
  { key: "members", label: "Members" },
  { key: "sources", label: "Sources" },
  { key: "settings", label: "Settings" }
];

const roleOptions: { value: GameMemberRole; label: string }[] = [
  { value: "gm", label: "GM" },
  { value: "co-gm", label: "Co-GM" },
  { value: "player", label: "Player" },
  { value: "spectator", label: "Spectator" }
];

const tierLabels: Record<string, string> = {
  free: "Free",
  standard: "Standard",
  premium: "Premium"
};

const toBannerState = (error: unknown): BannerState => {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      variant: "error",
      traceId: extractTraceId(error)
    };
  }
  if (error instanceof Error) {
    return {
      message: error.message,
      variant: "error"
    };
  }
  return {
    message: "An unexpected error occurred.",
    variant: "error"
  };
};

const sortMembers = (members: GameMember[]): GameMember[] => {
  const priority: Record<GameMemberRole, number> = {
    gm: 0,
    "co-gm": 1,
    player: 2,
    spectator: 3
  };
  return [...members].sort((a, b) => {
    const priorityDelta = (priority[a.role] ?? 9) - (priority[b.role] ?? 9);
    if (priorityDelta !== 0) {
      return priorityDelta;
    }
    return a.displayName.localeCompare(b.displayName);
  });
};

export function GmHub() {
  const api = useMemo(() => createApiClient(), []);
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const { showToast } = useToast();

  const [activeGameId, setActiveGameId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("members");

  const applyHashTab = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }
    const hash = window.location.hash.replace(/^#/, "");
    if (hash === "members" || hash === "sources" || hash === "settings") {
      setActiveTab(hash as TabKey);
    }
  }, []);

  const handleTabChange = useCallback((tab: TabKey) => {
    setActiveTab(tab);
    if (typeof window !== "undefined" && window.location) {
      const url = `${window.location.pathname}#${tab}`;
      window.history.replaceState(null, "", url);
    }
  }, []);

  useEffect(() => {
    applyHashTab();
    if (typeof window === "undefined") {
      return;
    }
    window.addEventListener("hashchange", applyHashTab);
    return () => {
      window.removeEventListener("hashchange", applyHashTab);
    };
  }, [applyHashTab]);

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [removeSourceDialogOpen, setRemoveSourceDialogOpen] = useState(false);
  const [gamePendingDelete, setGamePendingDelete] = useState<Game | null>(null);
  const [sourcePendingRemoval, setSourcePendingRemoval] = useState<{ id: string; name: string } | null>(null);

  const [banner, setBanner] = useState<BannerState | null>(null);
  const [aiResponse, setAiResponse] = useState<string>("");
  const [promptInput, setPromptInput] = useState<string>("");
  const [isAiLoading, setIsAiLoading] = useState(false);

  const gamesQuery = useQuery({
    queryKey: ["gm-games"],
    queryFn: () => api.getGames()
  });

  const ownedSourcesQuery = useQuery({
    queryKey: ["gm-sources-owned"],
    queryFn: () => api.getSources({ owned: true })
  });

  const allSourcesQuery = useQuery({
    queryKey: ["gm-sources-all"],
    queryFn: () => api.getSources()
  });

  const gameDetailsQuery = useQuery({
    queryKey: ["gm-game", activeGameId],
    enabled: Boolean(activeGameId),
    queryFn: () =>
      activeGameId ? api.getGameById(activeGameId) : Promise.resolve(null)
  });

  const gameUsageQuery = useQuery({
    queryKey: ["gm-game-usage", activeGameId],
    enabled: Boolean(activeGameId),
    queryFn: () =>
      activeGameId ? api.getUsage("game", activeGameId) : Promise.resolve(null)
  });

  const gameQuotasQuery = useQuery({
    queryKey: ["gm-game-quotas", activeGameId],
    enabled: Boolean(activeGameId),
    queryFn: () =>
      activeGameId ? api.getQuotas("game", activeGameId) : Promise.resolve(null)
  });

  const userQuotasQuery = useQuery({
    queryKey: ["gm-user-quotas", session?.id],
    enabled: Boolean(session?.id),
    queryFn: () =>
      session?.id ? api.getQuotas("user", session.id) : Promise.resolve(null)
  });

  useEffect(() => {
    if (!activeGameId && gamesQuery.data?.length) {
      setActiveGameId(gamesQuery.data[0].id);
    }
  }, [gamesQuery.data, activeGameId]);

  const setErrorBanner = (error: unknown) => {
    setBanner(toBannerState(error));
  };

  const clearBanner = () => setBanner(null);

  const createGameMutation = useMutation<Game, Error, Parameters<typeof api.createGame>[0]>({
    mutationFn: api.createGame.bind(api),
    onSuccess: (game) => {
      clearBanner();
      queryClient.setQueryData<Game[]>(["gm-games"], (current) => {
        if (!current) return [game];
        return [game, ...current];
      });
      setActiveGameId(game.id);
      showToast({
        title: "Campaign created",
        description: `"${game.title}" is ready to go.`,
        variant: "success"
      });
    },
    onError: setErrorBanner,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["gm-games"] });
    }
  });

  const deleteGameMutation = useMutation({
    mutationFn: (gameId: string) => api.deleteGame(gameId),
    onSuccess: (_result, gameId) => {
      clearBanner();
      const deleted = gamesQuery.data?.find((game) => game.id === gameId);
      queryClient.setQueryData<Game[]>(["gm-games"], (current) =>
        current?.filter((game) => game.id !== gameId) ?? current
      );
      if (activeGameId === gameId) {
        setActiveGameId(null);
        setActiveTab("members");
      }
      showToast({
        title: "Campaign deleted",
        description: deleted ? `"${deleted.title}" has been removed.` : "Campaign removed from your hub.",
        variant: "info"
      });
    },
    onError: setErrorBanner,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["gm-games"] });
    }
  });

  const updateGameMutation = useMutation<Game, Error, { gameId: string; payload: GameUpdateInput }>({
    mutationFn: ({
      gameId,
      payload
    }) => api.updateGame(gameId, payload),
    onSuccess: (updatedGame) => {
      clearBanner();
      queryClient.setQueryData<Game>(["gm-game", updatedGame.id], updatedGame);
      queryClient.setQueryData<Game[]>(["gm-games"], (current) =>
        current?.map((game) => (game.id === updatedGame.id ? updatedGame : game)) ??
        current
      );
      showToast({
        title: "Campaign updated",
        description: `"${updatedGame.title}" changes saved.`,
        variant: "success"
      });
    },
    onError: setErrorBanner,
    onSettled: (_result, _error, variables) => {
      if (variables) {
        void queryClient.invalidateQueries({ queryKey: ["gm-game", variables.gameId] });
      }
      void queryClient.invalidateQueries({ queryKey: ["gm-games"] });
    }
  });

  const inviteMemberMutation = useMutation<GameMember, Error, { gameId: string; payload: GameMemberInviteInput }>({
    mutationFn: ({
      gameId,
      payload
    }) => api.addGameMember(gameId, payload),
    onSuccess: (_member, { payload }) => {
      clearBanner();
      showToast({
        title: "Invite sent",
        description: payload.email ? `Invitation emailed to ${payload.email}.` : "Invitation sent.",
        variant: "success"
      });
    },
    onError: setErrorBanner,
    onSettled: (_result, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["gm-game", variables.gameId] });
    }
  });

  const updateMemberRoleMutation = useMutation<GameMember, Error, { gameId: string; userId: string; role: GameMemberRole }>({
    mutationFn: ({
      gameId,
      userId,
      role
    }) => api.updateGameMember(gameId, userId, { role }),
    onSuccess: (_member, variables) => {
      clearBanner();
      showToast({
        title: "Member role updated",
        description: `Role changed to ${variables.role}.`,
        variant: "success"
      });
    },
    onError: setErrorBanner,
    onSettled: (_result, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["gm-game", variables.gameId] });
    }
  });

  const removeMemberMutation = useMutation<void, Error, { gameId: string; userId: string }>({
    mutationFn: ({
      gameId,
      userId
    }) => api.removeGameMember(gameId, userId),
    onSuccess: (_result, variables) => {
      clearBanner();
      showToast({
        title: "Member removed",
        description: "The member no longer has access.",
        variant: "info"
      });
    },
    onError: setErrorBanner,
    onSettled: (_result, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["gm-game", variables.gameId] });
    }
  });

  const addSourceMutation = useMutation({
    mutationFn: ({
      gameId,
      sourceId
    }: {
      gameId: string;
      sourceId: string;
    }) => api.addGameSource(gameId, sourceId),
    onSuccess: (updatedGame) => {
      clearBanner();
      queryClient.setQueryData<Game>(["gm-game", updatedGame.id], updatedGame);
      showToast({
        title: "Source added",
        description: "New content is now available for the campaign.",
        variant: "success"
      });
    },
    onError: setErrorBanner
  });

  const removeSourceMutation = useMutation({
    mutationFn: ({
      gameId,
      sourceId
    }: {
      gameId: string;
      sourceId: string;
    }) => api.removeGameSource(gameId, sourceId),
    onSuccess: (updatedGame) => {
      clearBanner();
      queryClient.setQueryData<Game>(["gm-game", updatedGame.id], updatedGame);
      showToast({
        title: "Source removed",
        description: "The source is no longer linked to this campaign.",
        variant: "info"
      });
    },
    onError: setErrorBanner
  });

  const addUserSourceMutation = useMutation({
    mutationFn: (sourceId: string) => api.addUserSource(sourceId),
    onSuccess: (updatedSources) => {
      clearBanner();
      queryClient.setQueryData<typeof updatedSources>(["gm-sources-owned"], updatedSources);
      showToast({
        title: "Source added",
        description: "The source has been added to your available sources.",
        variant: "success"
      });
    },
    onError: setErrorBanner,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["gm-sources-owned"] });
      void queryClient.invalidateQueries({ queryKey: ["gm-sources-all"] });
    }
  });

  const removeUserSourceMutation = useMutation({
    mutationFn: (sourceId: string) => api.removeUserSource(sourceId),
    onSuccess: (updatedSources) => {
      clearBanner();
      queryClient.setQueryData<typeof updatedSources>(["gm-sources-owned"], updatedSources);
      showToast({
        title: "Source removed",
        description: "The source has been removed from your available sources.",
        variant: "info"
      });
    },
    onError: setErrorBanner,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["gm-sources-owned"] });
      void queryClient.invalidateQueries({ queryKey: ["gm-sources-all"] });
    }
  });

  const games = gamesQuery.data ?? [];
  const activeGame =
    (gameDetailsQuery.data as Game | null | undefined) ?? null;
  const ownedSources = ownedSourcesQuery.data ?? [];
  const allSources = allSourcesQuery.data ?? [];
  const members = sortMembers(activeGame?.members ?? []);
  const gameSources = activeGame?.sources ?? [];
  const gameQuotas = gameQuotasQuery.data;
  const userQuotas = userQuotasQuery.data;

  const availableSources = useMemo(() => {
    const activeIds = new Set(gameSources.map((source) => source.id));
    return ownedSources.filter((source) => !activeIds.has(source.id));
  }, [ownedSources, gameSources]);

  const availableSourcesForSelection = useMemo(() => {
    const ownedIds = new Set(ownedSources.map((source) => source.id));
    return allSources.filter((source) => !ownedIds.has(source.id));
  }, [allSources, ownedSources]);

  const usageMeterItems = useMemo(() => {
    if (!gameUsageQuery.data?.meter) {
      return [];
    }
    const { meter } = gameUsageQuery.data;
    const withQuota = (value?: number, fallback = 100) => {
      const numeric = value ?? 0;
      return {
        value: numeric,
        quota: Math.max(numeric, fallback)
      };
    };
    return [
      {
        label: "Text Assist",
        ...withQuota(meter.textAssistRemaining),
        description: "Assistive responses remaining."
      },
      {
        label: "Automation Credits",
        ...withQuota(meter.automationCreditsRemaining),
        description: "Automation triggers remaining."
      },
      {
        label: "Audio Bridge",
        ...withQuota(meter.audioBridgeRemaining),
        description: "Voice minutes available."
      },
      {
        label: "Discord Bridge",
        ...withQuota(meter.discordBridgeRemaining),
        description: "Discord workflows remaining."
      }
    ];
  }, [gameUsageQuery.data]);

  const handleRoleChange = (member: GameMember, nextRole: GameMemberRole) => {
    if (!activeGame) {
      return;
    }
    if (member.role === nextRole) {
      return;
    }
    updateMemberRoleMutation.mutate({
      gameId: activeGame.id,
      userId: member.userId,
      role: nextRole
    });
  };

  const handleRemoveMember = (member: GameMember) => {
    if (!activeGame) {
      return;
    }
    removeMemberMutation.mutate({
      gameId: activeGame.id,
      userId: member.userId
    });
  };

  const handleAddSource = (sourceId: string) => {
    if (!activeGame) {
      return;
    }
    if (gameSources.some((source) => source.id === sourceId)) {
      return;
    }

    // Check tier limits
    const sourceLimit = gameQuotas?.effectiveSourceLimit ?? 3; // fallback to 3 if quotas not loaded

    if (gameSources.length >= sourceLimit) {
      const tierLabel = tierLabels[activeGame.tier ?? "free"] ?? "Free";
      showToast({
        title: "Source limit reached",
        description: `Your ${tierLabel} tier ${gameQuotas?.additionalSourcesFromGrants ? `(${gameQuotas.baseSourceLimit} + ${gameQuotas.additionalSourcesFromGrants} add-ons) ` : ''}allows up to ${sourceLimit} sources. Upgrade to add more.`,
        variant: "warning"
      });
      return;
    }

    addSourceMutation.mutate({ gameId: activeGame.id, sourceId });
  };

  const handleSourceSelectionChange = (selectedIds: string[]) => {
    if (!activeGame) {
      return;
    }

    const sourceLimit = gameQuotas?.effectiveSourceLimit ?? 3; // fallback to 3 if quotas not loaded

    // Find newly selected sources (not already in gameSources)
    const currentIds = new Set(gameSources.map(s => s.id));
    const newSelections = selectedIds.filter(id => !currentIds.has(id));

    // Check if adding new selections would exceed limit
    if (gameSources.length + newSelections.length > sourceLimit) {
      const tierLabel = tierLabels[activeGame.tier ?? "free"] ?? "Free";
      showToast({
        title: "Source limit reached",
        description: `Your ${tierLabel} tier allows up to ${sourceLimit} sources. You have ${gameSources.length} selected.`,
        variant: "warning"
      });
      return;
    }

    // Add new sources
    newSelections.forEach(sourceId => {
      addSourceMutation.mutate({ gameId: activeGame.id, sourceId });
    });

    // Remove deselected sources
    const removedIds = gameSources
      .map(s => s.id)
      .filter(id => !selectedIds.includes(id));

    removedIds.forEach(sourceId => {
      removeSourceMutation.mutate({ gameId: activeGame.id, sourceId });
    });
  };

  const handleRemoveSource = (sourceId: string) => {
    if (!activeGame) {
      return;
    }
    removeSourceMutation.mutate({ gameId: activeGame.id, sourceId });
  };

  const handleAddUserSource = (sourceId: string) => {
    const sourceLimit = userQuotas?.effectiveSourceLimit ?? 3;

    if (ownedSources.length >= sourceLimit) {
      showToast({
        title: "Source limit reached",
        description: `Your account allows up to ${sourceLimit} sources. Upgrade to add more.`,
        variant: "warning"
      });
      return;
    }

    addUserSourceMutation.mutate(sourceId);
  };

  const handleOwnedSourcesChange = (newSelectedIds: string[]) => {
    const currentIds = ownedSources.map(s => s.id);
    const removedIds = currentIds.filter(id => !newSelectedIds.includes(id));

    if (removedIds.length > 0) {
      // Show confirmation dialog for the first removed source
      const removedSource = ownedSources.find(s => s.id === removedIds[0]);
      if (removedSource) {
        setSourcePendingRemoval({ id: removedSource.id, name: removedSource.name });
        setRemoveSourceDialogOpen(true);
      }
    }
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

  const isLoading =
    gamesQuery.isLoading ||
    gameDetailsQuery.isLoading ||
    ownedSourcesQuery.isLoading;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
          GM Hub
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {session
            ? `Welcome back, ${session.displayName}. Manage campaigns, collaborate with players, and control access.`
            : "Manage campaigns, collaborate with players, and control access."}
        </p>
      </header>

      {banner ? (
        <InlineBanner
          variant={banner.variant}
          title="We couldn't complete that action"
          description={banner.message}
          traceId={banner.traceId}
        />
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[2fr_1.5fr]">
        <div className="space-y-6">
          <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Your games
              </h2>
              <button
                type="button"
                onClick={() => setCreateDialogOpen(true)}
                className="rounded-md border border-transparent bg-brand-500 px-3 py-2 text-sm font-medium text-white transition hover:bg-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                New game
              </button>
            </div>

            <div className="space-y-2" role="list">
              {isLoading ? (
                <div className="space-y-2">
                  {[...Array(3)].map((_, index) => (
                    <div
                      key={index.toString()}
                      className="h-16 animate-pulse rounded-md bg-slate-200/60 dark:bg-slate-800/60"
                    />
                  ))}
                </div>
              ) : games.length ? (
                games.map((game) => {
                  const isActive = game.id === activeGameId;
                  return (
                    <button
                      type="button"
                      key={game.id}
                      onClick={() => {
                        setActiveGameId(game.id);
                        clearBanner();
                      }}
                      className={cn(
                        "flex w-full items-start justify-between rounded-md border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                        isActive
                          ? "border-brand-400 bg-brand-50 text-brand-700 dark:border-brand-500/60 dark:bg-slate-800 dark:text-brand-200"
                          : "border-slate-200 hover:border-brand-300 dark:border-slate-700 dark:hover:border-brand-500/50"
                      )}
                      role="listitem"
                    >
                      <div>
                        <p className="text-sm font-medium">{game.title}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {tierLabels[game.tier ?? "standard"] ?? "Standard"} · {game.status}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400 dark:text-slate-500">
                          {game.playerIds.length} members
                        </span>
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setGamePendingDelete(game);
                            setDeleteDialogOpen(true);
                          }}
                          className="rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-600 transition hover:border-red-300 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 dark:border-red-800 dark:text-red-300"
                        >
                          Delete
                        </button>
                      </div>
                    </button>
                  );
                })
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  No games yet. Create a campaign to start coordinating your party.
                </p>
              )}
            </div>
          </aside>

          {/* AI Assistant Section - Always Visible */}
          <section className="rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                AI Assistant
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Ask questions about rules, campaign management, or player coordination.
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
          {/* Source Selector - Add sources from database */}
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <label htmlFor="add-source" className="mb-2 block text-sm font-medium text-slate-700 dark:text-slate-300">
              Add Source from Library
            </label>
            <select
              id="add-source"
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) {
                  handleAddUserSource(e.target.value);
                  e.target.value = "";
                }
              }}
              disabled={ownedSources.length >= (userQuotas?.effectiveSourceLimit ?? 3)}
            >
              <option value="" disabled>
                {availableSourcesForSelection.length > 0
                  ? "Select a source to add..."
                  : "No sources available"}
              </option>
              {availableSourcesForSelection.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.name} ({source.category})
                </option>
              ))}
            </select>
            {ownedSources.length >= (userQuotas?.effectiveSourceLimit ?? 3) && (
              <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                Source limit reached. Upgrade your account to add more sources.
              </p>
            )}
          </div>

          {/* Sources Panel - Always Visible (User-Level for GMs) */}
          <SourceMultiSelect
            sources={ownedSources}
            selectedIds={ownedSources.map(s => s.id)}
            onChange={handleOwnedSourcesChange}
            ownedSourceIds={ownedSources.map(s => s.id)}
            selectedLabel={`Available sources (${ownedSources.length} of ${userQuotas?.effectiveSourceLimit ?? 3}${userQuotas?.additionalSourcesFromGrants ? ` [${userQuotas.baseSourceLimit}+${userQuotas.additionalSourcesFromGrants}]` : ''})`}
            renderFooter={
              <div className="flex items-center justify-between">
                <span>
                  {ownedSources.length >= (userQuotas?.effectiveSourceLimit ?? 3)
                    ? `Limit reached for your account`
                    : `${(userQuotas?.effectiveSourceLimit ?? 3) - ownedSources.length} source${(userQuotas?.effectiveSourceLimit ?? 3) - ownedSources.length !== 1 ? 's' : ''} remaining`}
                </span>
              </div>
            }
          />
        </div>
      </div>

      {/* Game Details Section - Shown when game is selected */}
      {activeGame ? (
        <div className="space-y-5">
          <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                  {activeGame.title}
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {activeGame.summary ?? "No summary provided yet."}
                </p>
                {activeGame.inviteCode ? (
                  <button
                    type="button"
                    className="mt-2 inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                    onClick={() => {
                      void navigator.clipboard
                        .writeText(activeGame.inviteCode ?? "")
                        .then(() => {
                          showToast({
                            title: "Invite code copied",
                            description: "Share it with your players to grant access.",
                            variant: "success"
                          });
                        })
                        .catch((clipboardError) => {
                          setErrorBanner(clipboardError);
                        });
                    }}
                  >
                    Invite code: {activeGame.inviteCode}
                  </button>
                ) : null}
              </div>
              <button
                type="button"
                className="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                onClick={() => setInviteDialogOpen(true)}
              >
                Invite by email
              </button>
            </div>

            <div className="mt-5 border-t border-slate-200 pt-5 dark:border-slate-800">
              <nav className="flex flex-wrap gap-2">
                {tabs.map((tab) => {
                  const isActive = tab.key === activeTab;
                  return (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => handleTabChange(tab.key)}
                      className={cn(
                        "rounded-md px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                        isActive
                          ? "bg-brand-500 text-white"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                      )}
                    >
                      {tab.label}
                    </button>
                  );
                })}
              </nav>

              <div className="mt-5">
                {activeTab === "members" ? (
                  <div id="members" className="space-y-3">
                    {members.length ? (
                      members.map((member) => (
                        <div
                          key={member.userId}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800"
                        >
                          <div>
                            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                              {member.displayName}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {member.email} · {member.status}
                            </p>
                          </div>
                          <div className="flex items-center gap-3">
                            <select
                              value={member.role}
                              onChange={(event) =>
                                handleRoleChange(
                                  member,
                                  event.target.value as GameMemberRole
                                )
                              }
                              className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                            >
                              {roleOptions.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              disabled={member.role === "gm"}
                              onClick={() => handleRemoveMember(member)}
                              className="rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-600 transition hover:border-red-300 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 disabled:opacity-50 dark:border-red-800 dark:text-red-300"
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        No members yet. Invite players via email or share the invite code.
                      </p>
                    )}
                  </div>
                ) : null}

                {activeTab === "sources" ? (
                  <div id="sources" className="space-y-5">
                    {/* Current Game Sources */}
                    <div>
                      <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
                        Active Sources ({gameSources.length} of {gameQuotas?.effectiveSourceLimit ?? 3}
                        {gameQuotas?.additionalSourcesFromGrants ? ` [${gameQuotas.baseSourceLimit}+${gameQuotas.additionalSourcesFromGrants}]` : ''})
                      </h3>
                      {gameSources.length > 0 ? (
                        <div className="space-y-2">
                          {gameSources.map((source) => (
                            <div
                              key={source.id}
                              className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800"
                            >
                              <div>
                                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                                  {source.name}
                                </p>
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  {source.category}
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleRemoveSource(source.id)}
                                className="rounded-md border border-red-200 px-3 py-1 text-xs font-medium text-red-600 transition hover:border-red-300 hover:text-red-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 dark:border-red-800 dark:text-red-300"
                              >
                                Remove
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          No sources added yet. Add sources from your available sources below.
                        </p>
                      )}
                    </div>

                    {/* Available Sources to Add */}
                    <div>
                      <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-3">
                        Available Sources
                      </h3>
                      {availableSources.length > 0 ? (
                        <div className="space-y-2">
                          {availableSources.map((source) => (
                            <div
                              key={source.id}
                              className="flex items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 dark:border-slate-800"
                            >
                              <div>
                                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                                  {source.name}
                                </p>
                                <p className="text-xs text-slate-500 dark:text-slate-400">
                                  {source.category}
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleAddSource(source.id)}
                                disabled={gameSources.length >= (gameQuotas?.effectiveSourceLimit ?? 3)}
                                className="rounded-md border border-brand-500 px-3 py-1 text-xs font-medium text-brand-600 transition hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-brand-400 dark:text-brand-400 dark:hover:bg-slate-800"
                              >
                                Add
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          All your available sources have been added to this game.
                          {ownedSources.length < (userQuotas?.effectiveSourceLimit ?? 3) && (
                            <> You can add more sources to your account from the GM Hub sidebar.</>
                          )}
                        </p>
                      )}
                    </div>

                    {/* Source Limit Info */}
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm dark:border-slate-700 dark:bg-slate-800">
                      <p className="font-medium text-slate-700 dark:text-slate-200">
                        Source Limit
                      </p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        Your {tierLabels[activeGame.tier ?? "standard"] ?? "Standard"} tier allows up to {gameQuotas?.effectiveSourceLimit ?? 3} sources per game.
                        {gameQuotas?.additionalSourcesFromGrants && gameQuotas.additionalSourcesFromGrants > 0 ? (
                          <> This includes {gameQuotas.baseSourceLimit} base sources and {gameQuotas.additionalSourcesFromGrants} additional sources from add-ons.</>
                        ) : null}
                      </p>
                      {gameSources.length >= (gameQuotas?.effectiveSourceLimit ?? 3) && (
                        <ManageBillingButton
                          scope="game"
                          scopeId={activeGame.id}
                          className="mt-3"
                          description=""
                          buttonLabel="Upgrade for More Sources"
                          disabledLabel=""
                        />
                      )}
                    </div>
                  </div>
                ) : null}

                {activeTab === "settings" ? (
                  <div id="settings" className="space-y-5">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                        Game tier
                      </label>
                      <div className="mt-1 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100">
                        {tierLabels[activeGame.tier ?? "standard"] ?? "Standard"}
                      </div>
                    </div>

                    <div className="space-y-3">
                      {["audio", "summaries", "discord"].map((toggle) => (
                        <label
                          key={toggle}
                          className="flex items-start gap-3 rounded-md border border-slate-200 px-3 py-2 transition hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600"
                          title="Coming soon"
                        >
                          <input
                            type="checkbox"
                            disabled
                            checked={
                              toggle === "audio"
                                ? !!activeGame.allowAudioBridge
                                : toggle === "summaries"
                                  ? !!activeGame.allowSummaries
                                  : !!activeGame.allowDiscordBridge
                            }
                            readOnly
                            className="mt-1"
                          />
                          <span>
                            <span className="font-medium capitalize">{toggle}</span>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {toggle === "audio"
                                ? "Live session transcription and AI-assisted narration."
                                : toggle === "summaries"
                                  ? "Automated recap posts for players."
                                  : "Sync encounters and announcements to Discord."}
                            </p>
                          </span>
                        </label>
                      ))}
                    </div>

                    <div className="rounded-md border border-slate-200 p-4 text-sm dark:border-slate-800">
                      <p className="font-medium text-slate-700 dark:text-slate-200">
                        Billing
                      </p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        Manage your subscription, invoices, and payment methods.
                      </p>
                      <ManageBillingButton
                        scope="game"
                        scopeId={activeGame.id}
                        className="mt-3"
                        description=""
                        buttonLabel="Manage Billing"
                        disabledLabel="Select a game to manage billing."
                      />
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <UsageGroup
            title="Campaign usage"
            description="Track shared allowances for this game."
            items={usageMeterItems}
          />
        </div>
      ) : null}

      <CreateGameDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onCreate={async (payload) => {
          await createGameMutation.mutateAsync(payload);
        }}
        isSubmitting={createGameMutation.isPending}
      />
      <DeleteGameDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        gameName={gamePendingDelete?.title ?? ""}
        onConfirm={async () => {
          if (gamePendingDelete) {
            await deleteGameMutation.mutateAsync(gamePendingDelete.id);
            setGamePendingDelete(null);
          }
        }}
        isDeleting={deleteGameMutation.isPending}
      />
      {activeGame ? (
        <InviteMemberDialog
          open={inviteDialogOpen}
          onOpenChange={setInviteDialogOpen}
          onInvite={async (payload) => {
            await inviteMemberMutation.mutateAsync({
              gameId: activeGame.id,
              payload
            });
          }}
          isSubmitting={inviteMemberMutation.isPending}
        />
      ) : null}
      <RemoveSourceDialog
        open={removeSourceDialogOpen}
        onOpenChange={setRemoveSourceDialogOpen}
        sourceName={sourcePendingRemoval?.name ?? ""}
        onConfirm={async () => {
          if (sourcePendingRemoval) {
            await removeUserSourceMutation.mutateAsync(sourcePendingRemoval.id);
            setSourcePendingRemoval(null);
          }
        }}
        isRemoving={removeUserSourceMutation.isPending}
      />
    </div>
  );
}
