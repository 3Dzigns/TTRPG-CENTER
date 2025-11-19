"use client";

import { Suspense } from "react";
import Link from "next/link";
import type { Me } from "@ttrpg-center/types";
import { SessionGuard } from "../session-guard";
import { UserSettingsPanel } from "./user-settings-panel";

const numberFormatter = new Intl.NumberFormat("en-US");

function HomeOverview({ session }: { session: Me }) {
  const totalHoursPlayed = Math.round((session.usage.totalSecondsPlayed ?? 0) / 3600);
  const sessionsThisMonth = session.usage.monthlySessionCount ?? 0;
  const automationsLeft = session.usage.automationCreditsRemaining ?? 0;
  const textAssistRemaining = session.usage.textAssistRemaining ?? 0;

  const roles = new Set(session.roles);
  const isPlayer = roles.has("player");
  const isGM = roles.has("gm");
  const isAdmin = roles.has("admin");

  return (
    <main className="mx-auto max-w-6xl space-y-10 px-6 py-10">
      <section className="rounded-2xl border border-slate-200 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 p-[1px] shadow-lg dark:border-slate-800 dark:from-slate-700 dark:via-indigo-700 dark:to-purple-700">
        <div className="rounded-2xl bg-white/90 p-8 backdrop-blur-sm dark:bg-slate-950/80">
          <p className="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Welcome back
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-50 sm:text-4xl">
            {session.displayName}
          </h1>
          <p className="mt-4 max-w-2xl text-base text-slate-600 dark:text-slate-300">
            Orchestrate campaigns, manage table resources, and track usage - all from a single control
            center. Choose a workspace below to jump straight into your next adventure.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            {isPlayer && (
              <Link
                href="/player"
                className="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
              >
                Open Player Workspace
              </Link>
            )}
            {isGM && (
              <Link
                href="/gm"
                className="inline-flex items-center rounded-full border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
              >
                Visit GM Console
              </Link>
            )}
            {isAdmin && (
              <Link
                href="/admin"
                className="inline-flex items-center rounded-full border border-transparent px-4 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:text-indigo-200 dark:hover:bg-indigo-950/60"
              >
                Review Admin Insights
              </Link>
            )}
          </div>
        </div>
      </section>

      <UserSettingsPanel />

      <section className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">Hours Logged</h2>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-50">
            {numberFormatter.format(totalHoursPlayed)}
          </p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Total table time tracked across characters.
          </p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">Sessions This Month</h2>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-50">
            {numberFormatter.format(sessionsThisMonth)}
          </p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Session records synced with your campaigns.
          </p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">Automation Credits</h2>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-50">
            {numberFormatter.format(automationsLeft)}
          </p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Remaining workflow executions for ingest and tooling.
          </p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">Text Assist</h2>
          <p className="mt-3 text-3xl font-semibold text-slate-900 dark:text-slate-50">
            {numberFormatter.format(textAssistRemaining)}
          </p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            AI-assisted prompts remaining for lore and encounter prep.
          </p>
        </article>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        {(isPlayer || isGM) && (
          <article className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Continue Your Campaign</h2>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-300">
                Coordinate character updates, share player sources, and track session summaries within the player and GM hubs.
              </p>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              {isPlayer && (
                <Link
                  href="/player"
                  className="inline-flex items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white shadow transition hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                >
                  Manage Characters
                </Link>
              )}
              {isGM && (
                <Link
                  href="/gm"
                  className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-500"
                >
                  Open Encounter Prep
                </Link>
              )}
            </div>
          </article>
        )}

        {isAdmin && (
          <article className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">Stay in Sync</h2>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-300">
                Review usage analytics, download billing statements, and monitor worker health from the admin workspace.
              </p>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <Link
                href="/admin"
                className="inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow transition hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:bg-indigo-500 dark:hover:bg-indigo-400"
              >
                View Admin Dashboard
              </Link>
              <a
                href="https://docs.ttrpg-center.local/"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded-lg border border-transparent px-4 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 dark:text-indigo-200 dark:hover:bg-indigo-950/60"
              >
                Open Documentation
              </a>
            </div>
          </article>
        )}
      </section>
    </main>
  );
}

export function HomeLanding() {
  return (
    <Suspense fallback={<div className="p-8 text-slate-500">Loading workspace...</div>}>
      <SessionGuard>{(session) => <HomeOverview session={session} />}</SessionGuard>
    </Suspense>
  );
}

