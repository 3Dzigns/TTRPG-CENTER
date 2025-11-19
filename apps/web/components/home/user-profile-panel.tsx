"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import type { ThemePreference } from "@ttrpg-center/ui";
import { useSession } from "../../hooks/useSession";
import { getApiClient } from "../../lib/api";
import { useTheme } from "../theme-provider";

const THEME_OPTIONS: ThemePreference[] = ["light", "dark", "system"];

interface FormState {
  displayName: string;
  email: string;
  preferredTheme: ThemePreference;
}

export function UserProfilePanel() {
  const { data: session, refetch, isFetching } = useSession();
  const { setTheme } = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [formState, setFormState] = useState<FormState | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (session) {
      setFormState({
        displayName: session.displayName,
        email: session.email,
        preferredTheme: session.preferredTheme
      });
    }
  }, [session?.displayName, session?.email, session?.preferredTheme]);

  if (!session || !formState) {
    return null;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccess(false);

    try {
      const payload = {
        displayName: formState.displayName.trim(),
        email: session.email, // Use session email (read-only, not editable)
        preferredTheme: formState.preferredTheme
      };

      if (!payload.displayName) {
        throw new Error("Display name cannot be empty.");
      }

      await getApiClient().updateProfile(payload);
      await refetch();
      setTheme(payload.preferredTheme);
      setIsEditing(false);
      setSuccess(true);
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "We couldn't update your profile. Please try again."
      );
    } finally {
      setIsSaving(false);
    }
  };

  const resetForm = () => {
    setFormState({
      displayName: session.displayName,
      email: session.email,
      preferredTheme: session.preferredTheme
    });
    setError(null);
    setSuccess(false);
    setIsEditing(false);
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Profile</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Update your display name and theme preference.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setIsEditing((prev) => !prev);
            setError(null);
            setSuccess(false);
          }}
          className="rounded-md border border-slate-200 px-3 py-1 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
        >
          {isEditing ? "Close" : "Edit profile"}
        </button>
      </div>

      {!isEditing ? (
        <dl className="mt-6 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Display name</dt>
            <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
              {session.displayName}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Email</dt>
            <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
              {session.email}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Theme</dt>
            <dd className="mt-1 text-sm font-medium capitalize text-slate-900 dark:text-slate-100">
              {session.preferredTheme}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Roles</dt>
            <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">
              {session.roles.map(r => r.charAt(0).toUpperCase() + r.slice(1)).join(", ") || "Player"}
            </dd>
          </div>
        </dl>
      ) : (
        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1">
              <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Display name
              </span>
              <input
                type="text"
                value={formState.displayName}
                onChange={(event) =>
                  setFormState((prev) => prev && { ...prev, displayName: event.target.value })
                }
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <div className="space-y-1">
              <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Email
              </span>
              <div className="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
                {session.email}
              </div>
              <p className="text-xs text-slate-400 dark:text-slate-500">
                Email cannot be changed
              </p>
            </div>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Theme preference
            </legend>
            <div className="flex flex-wrap gap-3">
              {THEME_OPTIONS.map((option) => (
                <label
                  key={option}
                  className={`inline-flex items-center gap-2 rounded-md border px-3 py-1 text-sm transition ${
                    formState.preferredTheme === option
                      ? "border-brand-400 bg-brand-50 text-brand-700 dark:border-brand-400/70 dark:bg-brand-500/10 dark:text-brand-200"
                      : "border-slate-200 text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600"
                  }`}
                >
                  <input
                    type="radio"
                    name="theme"
                    value={option}
                    checked={formState.preferredTheme === option}
                    onChange={() =>
                      setFormState((prev) => prev && { ...prev, preferredTheme: option })
                    }
                    className="hidden"
                  />
                  <span className="capitalize">{option}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {success ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-200">
              Profile updated successfully.
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-brand-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-70 dark:bg-brand-500 dark:hover:bg-brand-400"
            >
              {isSaving ? "Saving..." : "Save changes"}
            </button>
            <button
              type="button"
              onClick={resetForm}
              disabled={isSaving || isFetching}
              className="inline-flex items-center rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-200 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:border-slate-600 dark:hover:bg-slate-800"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
