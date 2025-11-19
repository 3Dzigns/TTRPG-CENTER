"use client";

import { useEffect } from "react";
import type { AdminOverrideEvent } from "@ttrpg-center/types";
import { createEventStream } from "@ttrpg-center/api";

type OverrideEventCallback = (event: AdminOverrideEvent) => void;

const parseAdminOverride = (data: string): AdminOverrideEvent[] | null => {
  try {
    const parsed = JSON.parse(data);
    if (Array.isArray(parsed)) {
      return parsed.filter((item): item is AdminOverrideEvent => item?.type === "admin_override");
    }
    if (parsed && typeof parsed === "object" && parsed.type === "admin_override") {
      return [parsed as AdminOverrideEvent];
    }
  } catch (error) {
    console.warn("Failed to parse admin override event", error);
  }
  return null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/v1";
const NORMALIZED_API_BASE = API_BASE.endsWith("/")
  ? API_BASE.slice(0, -1)
  : API_BASE;

const ADMIN_EVENTS_PATH =
  process.env.NEXT_PUBLIC_ADMIN_EVENTS_PATH ??
  `${NORMALIZED_API_BASE}/events`;

export const useAdminOverrideStream = (onEvent: OverrideEventCallback | null) => {
  useEffect(() => {
    if (!onEvent) {
      return;
    }

    const stream = createEventStream(ADMIN_EVENTS_PATH, {
      parse: parseAdminOverride,
      filter: (payload) => payload.type === "admin_override"
    });

    const unsubscribe = stream.subscribe((payload) => {
      if (payload.type === "admin_override") {
        onEvent(payload as AdminOverrideEvent);
      }
    });

    return () => {
      unsubscribe();
      stream.close();
    };
  }, [onEvent]);
};
