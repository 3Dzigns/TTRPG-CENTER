"use client";

import type { AdminOverrideEvent, QueryStatusEvent } from "@ttrpg-center/types";

export type EventPayload = QueryStatusEvent | AdminOverrideEvent | { type: string };

export interface EventStreamOptions {
  withCredentials?: boolean;
  maxRetries?: number;
  initialDelayMs?: number;
  jitterRatio?: number;
  parse?: (data: string) => EventPayload | EventPayload[] | null;
  filter?: (event: EventPayload) => boolean;
}

export interface EventStream {
  subscribe: (listener: (event: EventPayload) => void) => () => void;
  getStatus: () => "connecting" | "open" | "closed";
  close: () => void;
}

const defaultParse = (data: string): EventPayload | EventPayload[] | null => {
  try {
    const parsed = JSON.parse(data);
    if (Array.isArray(parsed)) {
      return parsed as EventPayload[];
    }
    if (parsed && typeof parsed === "object") {
      return parsed as EventPayload;
    }
  } catch (error) {
    console.warn("Failed to parse event payload", error);
  }
  return null;
};

export const createEventStream = (
  url: string,
  options: EventStreamOptions = {}
): EventStream => {
  if (typeof window === "undefined") {
    throw new Error("Event streams are only available in the browser.");
  }

  const withCredentials = options.withCredentials ?? true;
  const maxRetries = options.maxRetries ?? 5;
  const initialDelayMs = options.initialDelayMs ?? 1000;
  const jitterRatio = options.jitterRatio ?? 0.25;
  const parse = options.parse ?? defaultParse;
  const filter = options.filter ?? (() => true);

  let eventSource: EventSource | null = null;
  let closed = false;
  let status: "connecting" | "open" | "closed" = "connecting";
  let retryCount = 0;
  const listeners = new Set<(event: EventPayload) => void>();

  const notify = (payload: EventPayload | EventPayload[]) => {
    const events = Array.isArray(payload) ? payload : [payload];
    events.forEach((event) => {
      if (!filter(event)) {
        return;
      }
      listeners.forEach((listener) => listener(event));
    });
  };

  const connect = () => {
    if (closed) {
      return;
    }
    if (eventSource) {
      eventSource.close();
    }
    status = "connecting";
    eventSource = new EventSource(url, { withCredentials });

    eventSource.addEventListener("open", () => {
      status = "open";
      retryCount = 0;
    });

    eventSource.addEventListener("message", (event: MessageEvent<string>) => {
      if (!event.data) {
        return;
      }
      const payload = parse(event.data);
      if (payload) {
        notify(payload);
      }
    });

    eventSource.addEventListener("error", (event) => {
      console.warn("Event stream error", event);
      if (closed) {
        return;
      }
      if (eventSource) {
        eventSource.close();
      }
      status = "connecting";
      if (retryCount >= maxRetries) {
        console.error("Event stream reached max retries");
        return;
      }
      retryCount += 1;
      const baseDelay = initialDelayMs * Math.pow(2, retryCount - 1);
      const jitter = baseDelay * jitterRatio * Math.random();
      const delay = baseDelay + jitter;
      window.setTimeout(connect, delay);
    });
  };

  connect();

  const subscribe = (listener: (event: EventPayload) => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };

  const close = () => {
    closed = true;
    status = "closed";
    eventSource?.close();
    eventSource = null;
    listeners.clear();
  };

  return {
    subscribe,
    getStatus: () => status,
    close
  };
};
