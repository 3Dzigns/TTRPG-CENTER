"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import type { Me } from "@ttrpg-center/types";
import { ApiError } from "@ttrpg-center/api";
import { useEffect } from "react";
import { getApiClient } from "../../lib/api";

type SessionStatus = "loading" | "authenticated" | "unauthenticated" | "error";

interface SessionContextValue {
  data: Me | null;
  error: ApiError | Error | null;
  status: SessionStatus;
  isLoading: boolean;
  isFetching: boolean;
  refetch: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue>({
  data: null,
  error: null,
  status: "loading",
  isLoading: true,
  isFetching: false,
  refetch: async () => {
    // noop placeholder, replaced inside provider
  }
});

export function SessionProvider({ children }: PropsWithChildren) {
  const [data, setData] = useState<Me | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [isFetching, setIsFetching] = useState(false);

  const loadSession = useCallback(async () => {
    setStatus("loading");
    setIsFetching(true);
    try {
      const session = await getApiClient().getMe();
      setData(session);
      setError(null);
      setStatus("authenticated");
    } catch (err) {
      const cast =
        err instanceof ApiError
          ? err
          : err instanceof Error
            ? new ApiError(err.message, 500)
            : new ApiError("Unable to load session", 500);

      setData(null);
      setError(cast);
      setStatus(cast.status === 401 ? "unauthenticated" : "error");
    } finally {
      setIsFetching(false);
    }
  }, []);

  useEffect(() => {
    void loadSession();
  }, [loadSession]);

  const value = useMemo<SessionContextValue>(
    () => ({
      data,
      error,
      status,
      isLoading: status === "loading",
      isFetching,
      refetch: loadSession
    }),
    [data, error, status, isFetching, loadSession]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export const useSessionContext = () => {
  return useContext(SessionContext);
};
