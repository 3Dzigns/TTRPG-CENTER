"use client";

import { useCallback, useState } from "react";
import { ApiError } from "@ttrpg-center/api";
import { getApiClient } from "../lib/api";
import { extractTraceId } from "../lib/errors";

export type BillingPortalFailureReason =
  | "missing-context"
  | "popup-blocked"
  | "api-error"
  | "invalid-link";

export type BillingPortalResult =
  | {
      success: true;
    }
  | {
      success: false;
      message: string;
      traceId?: string;
      reason: BillingPortalFailureReason;
    };

export const useBillingLink = (
  scope: "user" | "game",
  scopeId: string | null | undefined
) => {
  const api = getApiClient();
  const [isLoading, setIsLoading] = useState(false);

  const openBillingPortal = useCallback(async (): Promise<BillingPortalResult> => {
    if (!scopeId) {
      return {
        success: false,
        message: "Select a game to manage billing.",
        reason: "missing-context"
      };
    }

    setIsLoading(true);
    try {
      const link = await api.getBillingLink(scope, scopeId);
      if (!link?.url) {
        return {
          success: false,
          message: "Billing portal link is unavailable. Please try again later.",
          reason: "invalid-link"
        };
      }

      const opened = typeof window !== "undefined"
        ? window.open(link.url, "_blank", "noopener,noreferrer")
        : null;

      if (!opened) {
        return {
          success: false,
          message: "Pop-up blocked. Allow pop-ups to manage billing in a new tab.",
          reason: "popup-blocked"
        };
      }

      return { success: true };
    } catch (error) {
      const traceId =
        error instanceof ApiError
          ? error.traceId ?? extractTraceId(error.details)
          : extractTraceId(error);
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Unable to open the billing portal.";

      return {
        success: false,
        message,
        traceId,
        reason: "api-error"
      };
    } finally {
      setIsLoading(false);
    }
  }, [api, scope, scopeId]);

  return {
    openBillingPortal,
    isLoading
  };
};
