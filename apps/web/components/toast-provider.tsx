"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import type { PropsWithChildren, ReactNode } from "react";

export type ToastVariant = "info" | "success" | "warning" | "error";

export interface ShowToastOptions {
  id?: string;
  title: string;
  description?: ReactNode;
  variant?: ToastVariant;
  duration?: number;
  traceId?: string;
  actionLabel?: string;
  onAction?: () => void;
}

interface ToastRecord extends ShowToastOptions {
  id: string;
  variant: ToastVariant;
  duration: number;
}

interface ToastContextValue {
  showToast: (options: ShowToastOptions) => string;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const variantStyles: Record<ToastVariant, string> = {
  info: "border-sky-200 bg-white text-slate-700 dark:border-sky-800 dark:bg-slate-900 dark:text-slate-200",
  success:
    "border-emerald-200 bg-white text-slate-700 dark:border-emerald-800 dark:bg-slate-900 dark:text-slate-200",
  warning:
    "border-amber-200 bg-white text-slate-700 dark:border-amber-800 dark:bg-slate-900 dark:text-slate-200",
  error:
    "border-red-200 bg-white text-slate-700 dark:border-red-800 dark:bg-slate-900 dark:text-slate-200"
};

const DEFAULT_DURATION = 6000;

const generateId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `toast-${Math.random().toString(36).slice(2, 9)}`;
};

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const timers = useRef<Map<string, number>>(new Map());

  const dismissToast = useCallback((id: string) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== id));
    const timeoutId = timers.current.get(id);
    if (timeoutId) {
      window.clearTimeout(timeoutId);
      timers.current.delete(id);
    }
  }, []);

  const scheduleAutoDismiss = useCallback(
    (toast: ToastRecord) => {
      if (toast.duration === 0) {
        return;
      }
      const timeoutId = window.setTimeout(() => dismissToast(toast.id), toast.duration);
      timers.current.set(toast.id, timeoutId);
    },
    [dismissToast]
  );

  const showToast = useCallback(
    (options: ShowToastOptions) => {
      const id = options.id ?? generateId();
      const toast: ToastRecord = {
        ...options,
        id,
        variant: options.variant ?? "info",
        duration: options.duration ?? DEFAULT_DURATION
      };
      setToasts((previous) => [...previous, toast]);
      scheduleAutoDismiss(toast);
      return id;
    },
    [scheduleAutoDismiss]
  );

  useEffect(() => () => {
    timers.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
    timers.current.clear();
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({
      showToast,
      dismissToast
    }),
    [dismissToast, showToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed top-4 right-4 z-50 flex w-full max-w-sm flex-col gap-3">
        {toasts.map((toast) => (
          <article
            key={toast.id}
            role="status"
            aria-live={toast.variant === "error" ? "assertive" : "polite"}
            className="pointer-events-auto"
          >
            <div
              className={`flex flex-col gap-2 rounded-lg border px-4 py-3 shadow-lg ${variantStyles[toast.variant]}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-sm font-semibold">{toast.title}</p>
                  {toast.description ? (
                    <div className="text-sm text-slate-600 dark:text-slate-300">
                      {toast.description}
                    </div>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => dismissToast(toast.id)}
                  className="rounded-md border border-transparent p-1 text-xs text-slate-400 transition hover:text-slate-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:text-slate-500 dark:hover:text-slate-300"
                  aria-label="Dismiss notification"
                >
                  ×
                </button>
              </div>
              {toast.traceId ? (
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Trace ID: <code>{toast.traceId}</code>
                </p>
              ) : null}
              {toast.onAction && toast.actionLabel ? (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => {
                      toast.onAction?.();
                      dismissToast(toast.id);
                    }}
                    className="rounded-md border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                  >
                    {toast.actionLabel}
                  </button>
                </div>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
};

