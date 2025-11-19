"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { User } from "@ttrpg-center/types";
import { getApiClient } from "../../lib/api";

const PAGE_SIZE = 8;

export function AdminUsersTable() {
  const api = getApiClient();
  const [page, setPage] = useState(0);

  const usersQuery = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.getUsers(),
    staleTime: 60_000
  });

  const totalPages = useMemo(() => {
    const count = usersQuery.data?.length ?? 0;
    return Math.max(1, Math.ceil(count / PAGE_SIZE));
  }, [usersQuery.data]);

  const pagedUsers = useMemo(() => {
    if (!usersQuery.data) {
      return [];
    }
    const start = page * PAGE_SIZE;
    return usersQuery.data.slice(start, start + PAGE_SIZE);
  }, [page, usersQuery.data]);

  const handlePageChange = (next: number) => {
    setPage(Math.min(Math.max(next, 0), totalPages - 1));
  };

  return (
    <section aria-labelledby="admin-users-heading" className="space-y-3">
      <header className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 id="admin-users-heading" className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Users
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Read-only roster of active accounts and assigned roles.
          </p>
        </div>
        <div className="text-xs text-slate-500 dark:text-slate-400">
          Page {page + 1} of {totalPages}
        </div>
      </header>

      <div className="overflow-hidden rounded-lg border border-slate-200 shadow-sm dark:border-slate-800">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800" aria-describedby="admin-users-description">
          <caption id="admin-users-description" className="sr-only">
            System user directory
          </caption>
          <thead className="bg-slate-50 dark:bg-slate-900/40">
            <tr>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
                User
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
                Email
              </th>
              <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-300">
                Roles
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white text-sm dark:divide-slate-800 dark:bg-slate-900">
            {usersQuery.isLoading
              ? Array.from({ length: PAGE_SIZE }).map((_, index) => (
                  <tr key={`users-skeleton-${index.toString()}`} aria-hidden>
                    <td className="px-4 py-3">
                      <div className="h-4 w-2/3 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
                    </td>
                    <td className="px-4 py-3">
                      <div className="h-4 w-full animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
                    </td>
                    <td className="px-4 py-3">
                      <div className="h-4 w-1/2 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
                    </td>
                  </tr>
                ))
              : pagedUsers.map((user) => (
                  <tr key={user.id} className="focus-within:bg-slate-50 focus-within:outline-none dark:focus-within:bg-slate-800/70">
                    <td className="px-4 py-3 text-slate-900 dark:text-slate-100">
                      <div className="flex flex-col">
                        <span className="font-medium">{user.displayName}</span>
                        <span className="text-xs text-slate-500 dark:text-slate-400">{user.id}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{user.email}</td>
                    <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                      <span className="inline-flex flex-wrap gap-2">
                        {user.roles.map((role) => (
                          <span
                            key={role}
                            className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                          >
                            {role}
                          </span>
                        ))}
                      </span>
                    </td>
                  </tr>
                ))}
            {!usersQuery.isLoading && pagedUsers.length === 0 ? (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-sm text-slate-500 dark:text-slate-400">
                  No users found.
                </td>
              </tr>
            ) : null}
            {usersQuery.isError ? (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-sm text-red-500">
                  Failed to load users.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => handlePageChange(page - 1)}
          disabled={page === 0}
          className="inline-flex items-center rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => handlePageChange(page + 1)}
          disabled={page >= totalPages - 1}
          className="inline-flex items-center rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-50 dark:border-slate-700 dark:text-slate-200"
        >
          Next
        </button>
      </div>
    </section>
  );
}
