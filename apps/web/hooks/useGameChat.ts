"use client";


import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { QueryCitation, QueryMessage, QueryRequestInput, QueryResponse, QueryRunStatus, QueryStatusEvent } from "@ttrpg-center/types";
import { createEventStream } from "@ttrpg-center/api";
import { getApiClient } from "../lib/api";

const QUERY_EVENTS_PATH = process.env.NEXT_PUBLIC_QUERY_EVENTS_PATH ?? "/events";

export interface GameChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status?: QueryRunStatus;
  requestId?: string;
  isStreaming?: boolean;
  citations?: QueryCitation[];
  error?: string;
  relatedUserId?: string;
}

type SendOverrides = {
  userMessageId?: string;
  assistantMessageId?: string;
};

export interface UseGameChatOptions {
  gameId: string;
  actorId: string;
  characterId?: string | null;
  sourceIds?: string[];
}

export interface UseGameChatResult {
  messages: GameChatMessage[];
  sendMessage: (prompt: string, overrides?: SendOverrides) => Promise<void>;
  retryMessage: (assistantMessageId: string) => Promise<void>;
  stopMessage: (assistantMessageId: string) => void;
  clearTranscript: () => void;
  phase: "idle" | "submitting" | "streaming";
}

const STORAGE_NAMESPACE = "ttrpg-center/chat";

const createId = () =>
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const isBrowser = typeof window !== "undefined";

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unable to complete the request. Please try again.";
};

const sanitizeMessages = (messages: unknown): GameChatMessage[] => {
  if (!Array.isArray(messages)) {
    return [];
  }
  return messages
    .map((entry): GameChatMessage | null => {
      if (
        !entry ||
        typeof entry !== "object" ||
        (entry as GameChatMessage).role === undefined ||
        (entry as GameChatMessage).content === undefined
      ) {
        return null;
      }
      const cast = entry as GameChatMessage;
      return {
        id: cast.id ?? createId(),
        role: cast.role === "assistant" ? "assistant" : "user",
        content: String(cast.content),
        createdAt: typeof cast.createdAt === "number" ? cast.createdAt : Date.now(),
        status: cast.status,
        requestId: cast.requestId,
        isStreaming: false,
        citations: Array.isArray(cast.citations) ? cast.citations : undefined,
        error: typeof cast.error === "string" ? cast.error : undefined,
        relatedUserId:
          typeof cast.relatedUserId === "string" ? cast.relatedUserId : undefined
      } satisfies GameChatMessage;
    })
    .filter((entry): entry is GameChatMessage => Boolean(entry));
};

const parseQueryStatusEvents = (data: string): QueryStatusEvent[] | null => {
  try {
    const parsed = JSON.parse(data);
    if (Array.isArray(parsed)) {
      return parsed.filter(
        (item): item is QueryStatusEvent =>
          item && typeof item === "object" && item.type === "query.status"
      );
    }
    if (parsed && typeof parsed === "object" && parsed.type === "query.status") {
      return [parsed as QueryStatusEvent];
    }
  } catch (error) {
    console.warn("Failed to parse query status event", error);
  }
  return null;
};

export const useGameChat = ({
  gameId,
  actorId,
  characterId,
  sourceIds = []
}: UseGameChatOptions): UseGameChatResult => {
  const storageKey = useMemo(() => {
    return `${STORAGE_NAMESPACE}/${actorId}/${gameId}`;
  }, [actorId, gameId]);

  const [messages, setMessages] = useState<GameChatMessage[]>(() => {
    if (!isBrowser) {
      return [];
    }
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) {
        return [];
      }
      return sanitizeMessages(JSON.parse(raw));
    } catch {
      return [];
    }
  });

  const messagesRef = useRef<GameChatMessage[]>(messages);
  const requestToMessageRef = useRef<Map<string, string>>(new Map());
  const pendingEventsRef = useRef<Map<string, QueryStatusEvent[]>>(new Map());
  const cancelledRequestsRef = useRef<Set<string>>(new Set());
  const activeAssistantsRef = useRef<Set<string>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);

  const applyStatusUpdate = useCallback(
    (event: QueryStatusEvent, messageId: string) => {
      if (cancelledRequestsRef.current.has(event.requestId)) {
        if (event.status === "completed" || event.status === "failed") {
          cancelledRequestsRef.current.delete(event.requestId);
        }
        return;
      }

      setMessages((prev) =>
        prev.map((message) => {
          if (message.id !== messageId) {
            return message;
          }
          const next: GameChatMessage = {
            ...message,
            requestId: event.requestId,
            status: event.status,
            isStreaming:
              event.status === "queued" ||
              event.status === "in_progress" ||
              event.status === "streaming",
            error:
              event.status === "failed"
                ? event.error ?? "Assistant failed to complete the request."
                : undefined
          };

          if (typeof event.delta === "string") {
            next.content = `${next.content ?? ""}${event.delta}`;
          }
          if (typeof event.answer === "string") {
            next.content = event.answer;
          }
          if (Array.isArray(event.citations)) {
            next.citations = event.citations;
          }

          if (event.status === "completed" || event.status === "failed") {
            next.isStreaming = false;
          }

          return next;
        })
      );

      if (event.status === "completed" || event.status === "failed") {
        activeAssistantsRef.current.delete(messageId);
        setIsStreaming(activeAssistantsRef.current.size > 0);
      }
    },
    [setIsStreaming, setMessages]
  );

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    requestToMessageRef.current.clear();
    for (const message of messages) {
      if (message.requestId) {
        requestToMessageRef.current.set(message.requestId, message.id);
      }
    }
  }, [messages, storageKey]);

  useEffect(() => {
    if (!isBrowser) {
      return;
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(messages));
    } catch {
      // ignore persistence failures
    }
  }, [messages, storageKey]);

  useEffect(() => {
    if (!isBrowser) {
      return;
    }
    const api = getApiClient();
    let eventSource: EventSource | null = null;

    try {
      eventSource = api.createEventsStream(QUERY_EVENTS_PATH);
    } catch (error) {
      console.warn("Failed to create events stream", error);
      return;
    }

    const handleStatus = (payload: QueryStatusEvent) => {
      if (payload.type !== "query.status") {
        return;
      }
      if (cancelledRequestsRef.current.has(payload.requestId)) {
        if (payload.status === "completed" || payload.status === "failed") {
          cancelledRequestsRef.current.delete(payload.requestId);
        }
        return;
      }
      const messageId = requestToMessageRef.current.get(payload.requestId);
      if (!messageId) {
        const existing = pendingEventsRef.current.get(payload.requestId) ?? [];
        existing.push(payload);
        pendingEventsRef.current.set(payload.requestId, existing);
        return;
      }
      applyStatusUpdate(payload, messageId);
    };

    const handleMessage = (event: MessageEvent<string>) => {
      if (!event.data) {
        return;
      }
      try {
        const parsed = JSON.parse(event.data);
        if (Array.isArray(parsed)) {
          parsed.forEach((value) => handleStatus(value));
        } else {
          handleStatus(parsed);
        }
      } catch (error) {
        console.warn("Unable to parse event payload", error);
      }
    };

    eventSource.addEventListener("message", handleMessage);

    eventSource.addEventListener("error", () => {
      // Let browser handle reconnect attempts; we just log for observability.
      console.warn("Query events stream encountered an error");
    });

    return () => {
      eventSource?.removeEventListener("message", handleMessage);
      eventSource?.close();
      pendingEventsRef.current.clear();
    };
  }, [actorId, gameId]);

  const buildPayloadMessages = useCallback(
    (
      existing: GameChatMessage[],
      prompt: string,
      reuseUserId?: string
    ): QueryMessage[] => {
      const history: QueryMessage[] = [];
      let reuseHandled = false;

      for (const message of existing) {
        if (message.role === "user") {
          const content =
            reuseUserId && message.id === reuseUserId ? prompt : message.content;
          history.push({
            role: "user",
            content
          });
          if (reuseUserId && message.id === reuseUserId) {
            reuseHandled = true;
          }
        } else if (message.role === "assistant" && message.status === "completed") {
          history.push({
            role: "assistant",
            content: message.content
          });
        }
      }

      if (!reuseUserId || !reuseHandled) {
        history.push({
          role: "user",
          content: prompt
        });
      }

      return history;
    },
    []
  );

  const clearTranscript = useCallback(() => {
    setMessages([]);
    requestToMessageRef.current.clear();
    pendingEventsRef.current.clear();
    activeAssistantsRef.current.clear();
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (prompt: string, overrides?: SendOverrides) => {
      const trimmed = prompt.trim();
      if (!trimmed) {
        return;
      }

      if (isSubmitting || isStreaming) {
        return;
      }

      const userMessageId = overrides?.userMessageId ?? createId();
      const assistantMessageId = overrides?.assistantMessageId ?? createId();
      const now = Date.now();

      setMessages((prev) => {
        const next = [...prev];

        if (!overrides?.userMessageId) {
          next.push({
            id: userMessageId,
            role: "user",
            content: trimmed,
            createdAt: now
          });
        } else {
          const userIndex = next.findIndex((message) => message.id === overrides.userMessageId);
          if (userIndex !== -1) {
            next[userIndex] = {
              ...next[userIndex],
              content: trimmed
            };
          }
        }

        if (!overrides?.assistantMessageId) {
          next.push({
            id: assistantMessageId,
            role: "assistant",
            content: "",
            createdAt: now,
            status: "queued",
            isStreaming: true,
            citations: [],
            error: undefined,
            relatedUserId: userMessageId
          });
        } else {
          const assistantIndex = next.findIndex(
            (message) => message.id === overrides.assistantMessageId
          );
          if (assistantIndex !== -1) {
            next[assistantIndex] = {
              ...next[assistantIndex],
              content: "",
              createdAt: now,
              status: "queued",
              isStreaming: true,
              citations: [],
              error: undefined,
              relatedUserId: userMessageId,
              requestId: undefined
            };
          } else {
            next.push({
              id: assistantMessageId,
              role: "assistant",
              content: "",
              createdAt: now,
              status: "queued",
              isStreaming: true,
              citations: [],
              error: undefined,
              relatedUserId: userMessageId
            });
          }
        }

        return next;
      });

      activeAssistantsRef.current.add(assistantMessageId);
      setIsStreaming(true);
      setIsSubmitting(true);

      const history = buildPayloadMessages(
        messagesRef.current,
        trimmed,
        overrides?.userMessageId
      );

      const payload: QueryRequestInput = {
        scope: "game",
        gameId,
        actorId,
        characterId: characterId ?? undefined,
        sourceIds: sourceIds.length ? Array.from(new Set(sourceIds)) : undefined,
        messages: history
      };

      try {
        const response: QueryResponse = await getApiClient().submitQuery(payload);
        requestToMessageRef.current.set(response.requestId, assistantMessageId);
        cancelledRequestsRef.current.delete(response.requestId);

        setMessages((prev) =>
          prev.map((message) => {
            if (message.id !== assistantMessageId) {
              return message;
            }
            return {
              ...message,
              requestId: response.requestId,
              status: response.status ?? message.status,
              isStreaming: true
            };
          })
        );

        const pending = pendingEventsRef.current.get(response.requestId);
        if (pending && pending.length > 0) {
          pending.forEach((event) => applyStatusUpdate(event, assistantMessageId));
          pendingEventsRef.current.delete(response.requestId);
        }
      } catch (error) {
        setMessages((prev) =>
          prev.map((message) => {
            if (message.id !== assistantMessageId) {
              return message;
            }
            return {
              ...message,
              status: "failed",
              error: getErrorMessage(error),
              isStreaming: false
            };
          })
        );
        activeAssistantsRef.current.delete(assistantMessageId);
        setIsStreaming(activeAssistantsRef.current.size > 0);
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      actorId,
      applyStatusUpdate,
      buildPayloadMessages,
      characterId,
      gameId,
      isStreaming,
      isSubmitting,
      sourceIds
    ]
  );

  const retryMessage = useCallback(
    async (assistantMessageId: string) => {
      if (isSubmitting || isStreaming) {
        return;
      }
      const currentMessages = messagesRef.current;
      const assistant = currentMessages.find(
        (message) => message.id === assistantMessageId && message.role === "assistant"
      );
      if (!assistant || !assistant.relatedUserId) {
        return;
      }
      const user = currentMessages.find(
        (message) => message.id === assistant.relatedUserId && message.role === "user"
      );
      if (!user) {
        return;
      }
      await sendMessage(user.content, {
        userMessageId: user.id,
        assistantMessageId
      });
    },
    [isStreaming, isSubmitting, sendMessage]
  );

  const stopMessage = useCallback(
    (assistantMessageId: string) => {
      const current = messagesRef.current.find(
        (message) => message.id === assistantMessageId && message.role === "assistant"
      );
      if (!current) {
        return;
      }
      if (current.requestId) {
        cancelledRequestsRef.current.add(current.requestId);
        pendingEventsRef.current.delete(current.requestId);
      }
      activeAssistantsRef.current.delete(assistantMessageId);
      setMessages((prev) =>
        prev.map((message) => {
          if (message.id !== assistantMessageId) {
            return message;
          }
          return {
            ...message,
            isStreaming: false,
            status: message.status === "completed" ? message.status : "failed",
            error: "Stopped"
          };
        })
      );
      setIsStreaming(activeAssistantsRef.current.size > 0);
    },
    []
  );

  const phase: UseGameChatResult["phase"] = isSubmitting
    ? "submitting"
    : isStreaming
      ? "streaming"
      : "idle";

  return {
    messages,
    sendMessage,
    retryMessage,
    stopMessage,
    clearTranscript,
    phase
  };
};










