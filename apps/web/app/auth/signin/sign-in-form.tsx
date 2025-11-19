"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

const providers = [{ id: "oidc", label: "Continue with Google" }];

interface SignInFormProps {
  redirectPath: string;
}

export function SignInForm({ redirectPath }: SignInFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const handleSignIn = async (provider: string) => {
    setError(null);
    startTransition(async () => {
      try {
        const response = await fetch("/api/auth/start", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ provider, redirect: redirectPath })
        });
        if (!response.ok) {
          throw new Error("Failed to initiate sign in");
        }
        const data = (await response.json()) as { redirectTo?: string };
        if (!data.redirectTo) {
          throw new Error("Authentication provider did not return a redirect URL");
        }
        window.location.assign(data.redirectTo);
      } catch (signInError) {
        setError(signInError instanceof Error ? signInError.message : "Unable to start sign in");
      }
    });
  };

  return (
    <div className="w-full max-w-md space-y-6 rounded-lg border border-slate-200 bg-white p-8 shadow-lg dark:border-slate-800 dark:bg-slate-900">
      <header className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Sign in to TTRPG Center</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Choose your identity provider to continue.
        </p>
      </header>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="space-y-3">
        {providers.map((provider) => (
          <button
            key={provider.id}
            type="button"
            onClick={() => handleSignIn(provider.id)}
            disabled={isPending}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-100"
          >
            {isPending ? "Redirecting..." : provider.label}
          </button>
        ))}
      </div>

      <p className="text-center text-xs text-slate-400 dark:text-slate-500">
        Need access? Contact your workspace administrator.
      </p>
    </div>
  );
}
