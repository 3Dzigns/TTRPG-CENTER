"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ThemePreference } from "@ttrpg-center/ui";

const STORAGE_KEY = "ttrpg-center:theme";

const getStoredTheme = (): ThemePreference | null => {
  if (typeof window === "undefined") {
    return null;
  }

  const value = window.localStorage.getItem(STORAGE_KEY);
  if (!value) {
    return null;
  }

  if (value === "light" || value === "dark" || value === "system") {
    return value;
  }

  return null;
};

const resolveSystemTheme = (): ThemePreference => {
  if (typeof window === "undefined") {
    return "light";
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
};

const applyDocumentTheme = (preference: ThemePreference) => {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;

  const effective = preference === "system" ? resolveSystemTheme() : preference;
  root.dataset.theme = effective;

  if (effective === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
};

export const useThemePreference = (initial: ThemePreference = "system") => {
  const [theme, setTheme] = useState<ThemePreference>(() => {
    if (typeof window === "undefined") {
      return initial;
    }

    return getStoredTheme() ?? initial;
  });
  const mediaQueryRef = useRef<MediaQueryList | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    applyDocumentTheme(theme);

    if (theme === "system") {
      mediaQueryRef.current = window.matchMedia(
        "(prefers-color-scheme: dark)"
      );
      const listener = (event: MediaQueryListEvent) => {
        applyDocumentTheme(event.matches ? "dark" : "light");
      };
      mediaQueryRef.current.addEventListener("change", listener);
      return () => mediaQueryRef.current?.removeEventListener("change", listener);
    }

    return;
  }, [theme]);

  const updateTheme = useCallback((next: ThemePreference) => {
    setTheme(next);
    if (typeof window === "undefined") {
      return;
    }

    if (next === "system") {
      window.localStorage.removeItem(STORAGE_KEY);
    } else {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
    applyDocumentTheme(next);
  }, []);

  useEffect(() => {
    const stored = getStoredTheme();
    if (stored && stored !== theme) {
      setTheme(stored);
    }
  }, [theme]);

  return { theme, setTheme: updateTheme };
};
