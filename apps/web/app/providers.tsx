"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import * as React from "react";
import * as ReactDOM from "react-dom";
import { useEffect, useState } from "react";
import { ThemeProvider } from "../components/theme-provider";
import { ToastProvider } from "../components/toast-provider";
import { SessionProvider } from "../components/session/session-provider";

export function Providers({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false
          }
        }
      })
  );

  useEffect(() => {
    if (
      process.env.NODE_ENV === "production" ||
      typeof window === "undefined" ||
      (window as unknown as { __axe_initialized?: boolean }).__axe_initialized
    ) {
      return;
    }

    (window as unknown as { __axe_initialized?: boolean }).__axe_initialized = true;

    import("@axe-core/react")
      .then(({ default: axe }) => {
        axe(React, ReactDOM, 1000);
      })
      .catch(() => {
        // axe is a dev-only helper; ignore failures quietly
      });
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <ThemeProvider>
          <ToastProvider>{children}</ToastProvider>
        </ThemeProvider>
      </SessionProvider>
    </QueryClientProvider>
  );
}
