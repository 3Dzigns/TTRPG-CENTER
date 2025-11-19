"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import type { Game, GameMember, Me, QueryCitation, UsageSummary } from "@ttrpg-center/types";
import { UsageGroup, type UsageMeterProps } from "@ttrpg-center/ui";
import { getApiClient } from "../../lib/api";
import { ChatPanel } from "./chat-panel";
import { CitationsList } from "./citations-list";
import { ManageBillingButton } from "../billing/manage-billing-button";

interface GameGmViewProps {
  session: Me;
  gameId: string;
}

const featureToggles: Array<{
  id: string;
  label: string;
  description: string;
}> = [
  {
    id: "audio-review",
    label: "Audio Review",
    description: "Live audio capture, transcription, and playback are coming soon."
  },
  {
    id: "session-summaries",
    label: "AI Summaries",
    description: "Automated recap posts will arrive in a future release."
  },
  {
    id: "discord-bridge",
    label: "Discord Bridge",
    description: "Push encounters and announcements directly to your Discord server (planned)."
  }
];

const formatUsageMeters = (usage: UsageSummary | null): UsageMeterProps[] => {
  if (!usage?.meter) {
    return [];
  }

  const {
    automationCreditsRemaining,
    textAssistRemaining,
    audioBridgeRemaining,
    discordBridgeRemaining,
    totalSecondsPlayed,
    monthlySessionCount
  } = usage.meter;

  const withQuota = (value: number | undefined, fallback: number) => {
    const safeValue = value ?? 0;
    const quota = Math.max(fallback, safeValue, 1);
    return {
      value: safeValue,
      quota
    };
  };

  return [
    {
      label: "Minutes Played",
      description: "Total play time tracked across the campaign.",
      ...withQuota(Math.floor((totalSecondsPlayed ?? 0) / 60), 240)
    },
    {
      label: "Sessions This Month",
      description: "Session count over the last 30 days.",
      ...withQuota(monthlySessionCount, Math.max(monthlySessionCount ?? 0, 12))
    },
    {
      label: "Automation Credits",
      description: "Automation calls available for this campaign.",
      ...withQuota(automationCreditsRemaining, 200)
    },
    {
      label: "Summary Assist",
      description: "GM text prompts shared with players.",
      ...withQuota(textAssistRemaining, 120),
      disabled: textAssistRemaining === undefined,
      disabledReason: "Summary assistant is rolling out soon."
    },
    {
      label: "Audio Bridge",
      description: "Transcription minutes for session recordings.",
      ...withQuota(audioBridgeRemaining, 60),
      disabled: audioBridgeRemaining === undefined,
      disabledReason: "Audio bridge launches later this quarter."
    },
    {
      label: "Discord Bridge",
      description: "Announcements synchronized with Discord.",
      ...withQuota(discordBridgeRemaining, 40),
      disabled: discordBridgeRemaining === undefined,
      disabledReason: "Discord bridge integration coming soon."
    }
  ];
};

const getDisplayRole = (member: GameMember | undefined): string => {
  if (!member?.role) {
    return "GM";
  }
  return member.role.toUpperCase();
};

export function GameGmView({ session, gameId }: GameGmViewProps) {
  const api = getApiClient();

  const [citationState, setCitationState] = useState<{
    citations: QueryCitation[];
    messageId: string | null;
    isStreaming: boolean;
  }>({
    citations: [],
    messageId: null,
    isStreaming: false
  });

  const gameQuery = useQuery({
    queryKey: ["game", gameId],
    queryFn: () => api.getGameById(gameId),
    staleTime: 30_000
  });

  const usageQuery = useQuery({
    queryKey: ["game-usage", gameId],
    queryFn: () => api.getUsage("game", gameId),
    staleTime: 60_000
  });

  const game: Game | undefined = gameQuery.data;
  const usageMeters = useMemo(
    () => formatUsageMeters(usageQuery.data ?? null),
    [usageQuery.data]
  );

  const gmMember = useMemo(
    () => game?.members?.find((member) => member.userId === session.id),
    [game, session.id]
  );

  const sourceIds = useMemo(() => {
    if (!game) {
      return [];
    }
    if (Array.isArray(game.sources) && game.sources.length > 0) {
      return game.sources.map((source) => source.id);
    }
    return Array.isArray(game.sourceIds) ? Array.from(new Set(game.sourceIds)) : [];
  }, [game]);

  const handleCitationsChange = useCallback(
    (citations: QueryCitation[], messageId: string | null, metadata?: { isStreaming: boolean }) => {
      setCitationState({
        citations,
        messageId,
        isStreaming: metadata?.isStreaming ?? false
      });
    },
    []
  );

  if (gameQuery.isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-10 animate-pulse rounded-lg bg-slate-200/60 dark:bg-slate-800/60" />
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index.toString()}
              className="h-32 animate-pulse rounded-lg bg-slate-200/60 dark:bg-slate-800/60"
            />
          ))}
        </div>
      </div>
    );
  }

  if (gameQuery.isError || !game) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-12 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
        Unable to load the campaign right now. Please refresh and try again.
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <div className="space-y-6">
        <ChatPanel
          gameId={gameId}
          actorId={session.id}
          sourceIds={sourceIds}
          onActiveCitationsChange={handleCitationsChange}
          className="xl:h-[calc(100vh-12rem)]"
        />
      </div>

      <div className="space-y-6">
        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <header className="mb-4 flex items-start justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                GM Controls
              </h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Manage advanced features and deeper campaign configuration.
              </p>
            </div>
            <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {getDisplayRole(gmMember)}
            </span>
          </header>

          <div className="grid gap-3 sm:grid-cols-2">
            <Link
              href="/gm"
              className="inline-flex items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            >
              Open GM Hub
              <span aria-hidden>{">"}</span>
            </Link>
            <Link
              href="/gm#members"
              className="inline-flex items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            >
              Manage Members
              <span aria-hidden>{">"}</span>
            </Link>
            <Link
              href="/gm#sources"
              className="inline-flex items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            >
              Manage Sources
              <span aria-hidden>{">"}</span>
            </Link>
            <Link
              href="/gm#settings"
              className="inline-flex items-center justify-between gap-3 rounded-md border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            >
              Game Settings
              <span aria-hidden>{">"}</span>
            </Link>
          </div>
        </section>

        <section
          className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
          aria-labelledby="gm-upcoming-features"
        >
          <header className="mb-4">
            <h2
              id="gm-upcoming-features"
              className="text-base font-semibold text-slate-900 dark:text-slate-100"
            >
              Upcoming Features
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              These controls are disabled while we finalize the underlying services.
            </p>
          </header>

          <ul className="space-y-3">
            {featureToggles.map((toggle) => (
              <li key={toggle.id}>
                <div className="flex items-start gap-3 rounded-md border border-slate-200 px-4 py-3 transition hover:border-brand-300 dark:border-slate-700 dark:hover:border-brand-500/60">
                  <div className="flex h-5 items-center">
                    <input
                      type="checkbox"
                      aria-describedby={`${toggle.id}-note`}
                      disabled
                      title="Coming soon"
                      className="h-4 w-4 rounded border-slate-300 text-brand-500 focus:ring-brand-400 disabled:cursor-not-allowed dark:border-slate-600"
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="font-medium text-slate-800 dark:text-slate-100">{toggle.label}</p>
                    <p
                      id={`${toggle.id}-note`}
                      className="text-sm text-slate-500 dark:text-slate-400"
                    >
                      {toggle.description}
                    </p>
                  </div>
                  <span
                    aria-hidden
                    className="ml-auto rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                  >
                    Disabled
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <CitationsList
          citations={citationState.citations}
          activeMessageId={citationState.messageId}
          isStreaming={citationState.isStreaming}
        />

        <UsageGroup
          title="Campaign usage"
          description="Monitor allowances shared with your players."
          items={usageMeters}
        />

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <header className="mb-3">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Billing & Subscription
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Manage invoices, renewals, and expansion packs in the billing portal.
            </p>
          </header>
          <ManageBillingButton
            scope="game"
            scopeId={gameId}
            description="You'll leave TTRPG Center to manage this game's subscription in a new tab."
            buttonLabel="Manage Billing"
          />
        </section>
      </div>
    </div>
  );
}
