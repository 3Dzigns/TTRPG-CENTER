"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import type { QueryCitation } from "@ttrpg-center/types";
import { cn } from "@ttrpg-center/ui";
import { useGameChat, type GameChatMessage } from "../../hooks/useGameChat";

interface ChatPanelProps {
  gameId: string;
  actorId: string;
  characterId?: string | null;
  sourceIds?: string[];
  onActiveCitationsChange?: (
    citations: QueryCitation[],
    messageId: string | null,
    metadata?: { isStreaming: boolean }
  ) => void;
  className?: string;
}

interface Measurement {
  id: string;
  index: number;
  offset: number;
  height: number;
}

const statusLabels: Record<string, string> = {
  queued: "Queued",
  in_progress: "Working",
  streaming: "Streaming",
  completed: "Completed",
  failed: "Failed"
};

const BUFFER_PX = 240;

const estimateItemSize = (message: GameChatMessage | undefined): number => {
  if (!message) {
    return 120;
  }
  if (message.role === "assistant") {
    return 220;
  }
  return 140;
};

const findStartIndex = (items: Measurement[], scrollTop: number) => {
  if (items.length === 0) {
    return 0;
  }
  let low = 0;
  let high = items.length - 1;
  let answer = 0;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    const item = items[mid];
    if (item.offset + item.height < scrollTop) {
      low = mid + 1;
      answer = mid + 1;
    } else if (item.offset > scrollTop) {
      high = mid - 1;
    } else {
      return mid;
    }
  }

  return Math.min(answer, items.length - 1);
};

export function ChatPanel({
  gameId,
  actorId,
  characterId,
  sourceIds,
  onActiveCitationsChange,
  className
}: ChatPanelProps) {
  const { messages, sendMessage, retryMessage, stopMessage, clearTranscript, phase } = useGameChat({
    gameId,
    actorId,
    characterId,
    sourceIds
  });

  const [inputValue, setInputValue] = useState("");
  const [activeCitation, setActiveCitation] = useState<{ message: GameChatMessage; citation: QueryCitation } | null>(null);
  const [manualSelection, setManualSelection] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  const streamingAssistantMessage = useMemo(
    () =>
      [...messages]
        .reverse()
        .find((message) => message.role === "assistant" && message.isStreaming),
    [messages]
  );

  const citationDialogOpen = Boolean(activeCitation);

  const listRef = useRef<HTMLDivElement | null>(null);
  const heightsRef = useRef<Map<string, number>>(new Map());
  const elementsRef = useRef<Map<string, HTMLElement>>(new Map());
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const [heightVersion, setHeightVersion] = useState(0);
  const [visibleRange, setVisibleRange] = useState<{ start: number; end: number }>({
    start: 0,
    end: 0
  });

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      let changed = false;
      entries.forEach(({ target, contentRect }) => {
        const id = (target as HTMLElement).dataset.messageId;
        if (!id) {
          return;
        }
        const nextHeight = contentRect.height;
        const previous = heightsRef.current.get(id);
        if (!previous || Math.abs(previous - nextHeight) > 1) {
          heightsRef.current.set(id, nextHeight);
          changed = true;
        }
      });
      if (changed) {
        setHeightVersion((value) => value + 1);
      }
    });
    resizeObserverRef.current = observer;
    return () => {
      observer.disconnect();
      resizeObserverRef.current = null;
    };
  }, []);

  const attachElement = useCallback((messageId: string, element: HTMLElement | null) => {
    const observer = resizeObserverRef.current;
    const existing = elementsRef.current.get(messageId);
    if (existing && observer) {
      observer.unobserve(existing);
    }

    if (!element) {
      elementsRef.current.delete(messageId);
      heightsRef.current.delete(messageId);
      setHeightVersion((value) => value + 1);
      return;
    }

    element.dataset.messageId = messageId;
    elementsRef.current.set(messageId, element);
    if (observer) {
      observer.observe(element);
    }

    const currentHeight = element.getBoundingClientRect().height;
    const previous = heightsRef.current.get(messageId);
    if (!previous || Math.abs(previous - currentHeight) > 1) {
      heightsRef.current.set(messageId, currentHeight);
      setHeightVersion((value) => value + 1);
    }
  }, []);

  const measurements = useMemo(() => {
    let offset = 0;
    const items: Measurement[] = messages.map((message, index) => {
      const height = heightsRef.current.get(message.id) ?? estimateItemSize(message);
      const measurement: Measurement = {
        id: message.id,
        index,
        offset,
        height
      };
      offset += height;
      return measurement;
    });
    return {
      items,
      totalHeight: offset
    };
  }, [messages, heightVersion]);

  const computeVisibleRange = useCallback(() => {
    const container = listRef.current;
    const items = measurements.items;
    if (!container || items.length === 0) {
      setVisibleRange({ start: 0, end: 0 });
      return;
    }

    const scrollTop = container.scrollTop;
    const viewportHeight = container.clientHeight;
    const startIndex = findStartIndex(items, Math.max(0, scrollTop - BUFFER_PX));

    let endIndex = startIndex;
    const stopAt = scrollTop + viewportHeight + BUFFER_PX;
    while (endIndex < items.length && items[endIndex].offset < stopAt) {
      endIndex += 1;
    }

    setVisibleRange({
      start: startIndex,
      end: Math.min(items.length, Math.max(endIndex + 1, startIndex + 1))
    });
  }, [measurements]);

  useEffect(() => {
    computeVisibleRange();
  }, [computeVisibleRange]);

  useEffect(() => {
    if (!selectedMessageId || !messages.some((message) => message.id === selectedMessageId)) {
      const lastAssistant = [...messages]
        .reverse()
        .find((message) => message.role === "assistant");
      if (lastAssistant) {
        setSelectedMessageId(lastAssistant.id);
        setManualSelection(false);
      } else {
        onActiveCitationsChange?.([], null, { isStreaming: false });
      }
    }
  }, [messages, onActiveCitationsChange, selectedMessageId]);

  const selectedMessage = useMemo(() => {
    if (!selectedMessageId) {
      return null;
    }
    return messages.find((message) => message.id === selectedMessageId) ?? null;
  }, [messages, selectedMessageId]);

  useEffect(() => {
    if (selectedMessage?.role === "assistant") {
      onActiveCitationsChange?.(
        selectedMessage.citations ?? [],
        selectedMessage.id,
        { isStreaming: Boolean(selectedMessage.isStreaming) }
      );
    } else if (!selectedMessage) {
      onActiveCitationsChange?.([], null, { isStreaming: false });
    }
  }, [selectedMessage, onActiveCitationsChange]);

  useEffect(() => {
    if (
      activeCitation &&
      !messages.some((message) => message.id === activeCitation.message.id)
    ) {
      setActiveCitation(null);
    }
  }, [activeCitation, messages]);

  useEffect(() => {
    const container = listRef.current;
    if (!container || measurements.items.length === 0) {
      return;
    }
    const nearBottom =
      container.scrollTop + container.clientHeight >= measurements.totalHeight - 320;
    if (!manualSelection || phase !== "idle" || nearBottom) {
      container.scrollTo({
        top: measurements.totalHeight,
        behavior: phase === "streaming" ? "auto" : "smooth"
      });
    }
  }, [measurements.totalHeight, messages.length, phase, manualSelection]);

  const disableSend = phase !== "idle" || inputValue.trim().length === 0;

  const handleSubmit = async () => {
    const content = inputValue.trim();
    if (!content || phase !== "idle") {
      return;
    }
    await sendMessage(content);
    setInputValue("");
    setManualSelection(false);
    setActiveCitation(null);
  };

  const handleMessageClick = (messageId: string) => {
    setSelectedMessageId(messageId);
    setManualSelection(true);
    setActiveCitation(null);
  };

  const handleJumpToLatest = () => {
    const lastAssistant = [...messages]
      .reverse()
      .find((message) => message.role === "assistant");
    if (!lastAssistant) {
      return;
    }
    setSelectedMessageId(lastAssistant.id);
    setManualSelection(false);
    setActiveCitation(null);
    const container = listRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  };

  const handleCitationClick = useCallback(
    (message: GameChatMessage, citation: QueryCitation) => {
      setSelectedMessageId(message.id);
      setManualSelection(true);
      setActiveCitation({ message, citation });
    },
    [setActiveCitation, setManualSelection, setSelectedMessageId]
  );

  const handleCitationDialogChange = useCallback(
    (open: boolean) => {
      if (!open) {
        setActiveCitation(null);
      }
    },
    [setActiveCitation]
  );

  const handleStopStreaming = useCallback(() => {
    if (!streamingAssistantMessage) {
      return;
    }
    stopMessage(streamingAssistantMessage.id);
    setSelectedMessageId(streamingAssistantMessage.id);
    setManualSelection(true);
  }, [stopMessage, streamingAssistantMessage, setSelectedMessageId, setManualSelection]);

  const visibleItems = useMemo(() => {
    const { start, end } = visibleRange;
    return measurements.items.slice(start, end);
  }, [measurements.items, visibleRange]);

  return (
    <section
      className={cn(
        "flex h-full min-h-[32rem] flex-col rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
      aria-label="Game text assist"
    >
      <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Text Assist</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Ask rules questions or request summaries. Responses stream live with citations.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {manualSelection ? (
            <button
              type="button"
              onClick={handleJumpToLatest}
              className="rounded-md border border-slate-200 px-3 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
            >
              Jump to latest
            </button>
          ) : null}
          <button
            type="button"
            onClick={clearTranscript}
            className="rounded-md border border-transparent px-3 py-1 text-xs font-medium text-slate-500 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Clear
          </button>
        </div>
      </header>

      <div
        ref={listRef}
        className="relative flex-1 overflow-y-auto px-4 py-4"
        aria-live="polite"
        aria-atomic="false"
        onScroll={computeVisibleRange}
      >
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50/60 px-6 py-12 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/40 dark:text-slate-400">
            Begin the conversation by asking about rules, requesting summaries, or clarifying
            campaign lore.
          </div>
        ) : (
          <div
            style={{
              height: `${measurements.totalHeight}px`,
              position: "relative"
            }}
          >
            {visibleItems.map((item) => {
              const message = messages[item.index];
              if (!message) {
                return null;
              }
              const isAssistant = message.role === "assistant";
              const isSelected = selectedMessageId === message.id;

              return (
                <article
                  key={message.id}
                  ref={(element) => attachElement(message.id, element)}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    transform: `translateY(${item.offset}px)`
                  }}
                  className="px-3 py-2 outline-none"
                >
                  <button
                    type="button"
                    onClick={() => handleMessageClick(message.id)}
                    className={cn(
                      "w-full rounded-lg border px-4 py-3 text-left shadow-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                      isAssistant
                        ? "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
                        : "border-transparent bg-brand-50/70 dark:bg-brand-900/40",
                      isSelected
                        ? "border-brand-400 shadow-md ring-1 ring-brand-400 dark:border-brand-500"
                        : "hover:border-brand-200 dark:hover:border-brand-400/50"
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {isAssistant ? "Assistant" : "You"}
                      </span>
                      {isAssistant ? (
                        <span className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <span
                            className={cn(
                              "inline-flex h-2 w-2 rounded-full",
                              message.status === "completed"
                                ? "bg-emerald-500"
                                : message.status === "failed"
                                  ? "bg-red-500"
                                  : "bg-amber-400 animate-pulse"
                            )}
                            aria-hidden
                          />
                          {statusLabels[message.status ?? "queued"] ?? "Working"}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-2 text-sm leading-6 text-slate-800 dark:text-slate-100">
                      {message.content ? (
                        message.content.split("\n").map((line, index) => (
                          <p key={`${message.id}-line-${index}`} className="whitespace-pre-wrap">
                            {line}
                          </p>
                        ))
                      ) : (
                        <p className="italic text-slate-400 dark:text-slate-500">
                          {phase === "streaming" && isAssistant
                            ? "Streaming response…"
                            : "Awaiting response…"}
                        </p>
                      )}
                    </div>
                    {isAssistant ? (
                      <footer className="mt-3 space-y-2 text-xs text-slate-500 dark:text-slate-400">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="flex items-center gap-3">
                            <span>
                              Updated{" "}
                              {new Date(message.createdAt).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit"
                              })}
                            </span>
                            {message.citations && message.citations.length > 0 ? (
                              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                                {message.citations.length} citation
                                {message.citations.length > 1 ? "s" : ""}
                              </span>
                            ) : null}
                          </div>
                          {message.status === "failed" ? (
                            <div className="flex items-center gap-2">
                              <span className="text-red-500">{message.error}</span>
                              <button
                                type="button"
                                onClick={() => retryMessage(message.id)}
                                className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                              >
                                Retry
                              </button>
                            </div>
                          ) : null}
                        </div>
                        {message.citations && message.citations.length > 0 ? (
                          <div className="flex flex-wrap gap-2" role="group" aria-label="Response citations">
                            {message.citations.map((citation, index) => (
                              <button
                                key={`${message.id}-citation-${index}`}
                                type="button"
                                onClick={() => handleCitationClick(message, citation)}
                                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-100 px-3 py-1 text-[11px] font-medium text-slate-600 transition hover:border-brand-300 hover:bg-white hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-brand-500/40 dark:hover:text-brand-300"
                                aria-label={`View citation ${citation.title ?? `from source ${citation.sourceId}`}`}
                              >
                                <span className="max-w-[12rem] truncate">
                                  {citation.title ?? `Source ${citation.sourceId}`}
                                </span>
                                {citation.chunkId ? (
                                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-900 dark:text-slate-300">
                                    #{citation.chunkId}
                                  </span>
                                ) : null}
                              </button>
                            ))}
                          </div>
                        ) : null}
                      </footer>
                    ) : null}
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </div>

      <form
        className="border-t border-slate-200 bg-slate-50 px-5 py-4 dark:border-slate-800 dark:bg-slate-900/60"
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask the assistant
        </label>
        <textarea
          id="chat-input"
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about rules, request summaries, or plan your next move…"
          className="h-28 w-full resize-none rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-sm transition focus:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          disabled={phase !== "idle"}
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span>
            Press <kbd className="rounded border border-slate-200 px-1 dark:border-slate-700">Enter</kbd>{" "}
            to send, <kbd className="rounded border border-slate-200 px-1 dark:border-slate-700">Shift</kbd>+
            <kbd className="rounded border border-slate-200 px-1 dark:border-slate-700">Enter</kbd> for a new line.
          </span>
          <div className="flex items-center gap-3">
            {phase === "submitting" ? (
              <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-amber-400" aria-hidden />
                Waiting for acknowledgement…
              </span>
            ) : phase === "streaming" ? (
              <span className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-emerald-500" aria-hidden />
                Streaming response…
              </span>
            ) : null}
            {streamingAssistantMessage ? (
              <button
                type="button"
                onClick={handleStopStreaming}
                className="inline-flex items-center gap-2 rounded-md border border-red-200 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-600 transition hover:border-red-300 hover:bg-red-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300 dark:border-red-400/40 dark:bg-red-500/10 dark:text-red-300 dark:hover:bg-red-500/20"
                aria-label="Stop streaming response"
              >
                Stop
              </button>
            ) : null}
            <button
              type="submit"
              disabled={disableSend}
              className="inline-flex items-center gap-2 rounded-md border border-transparent bg-brand-500 px-4 py-2 text-sm font-medium text-white transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Send
            </button>
          </div>
        </div>
      </form>

      <Dialog.Root open={citationDialogOpen} onOpenChange={handleCitationDialogChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" />
          <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center px-4 py-10">
            <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-700 dark:bg-slate-900">
              <Dialog.Title className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Citation details
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Detailed source context coming soon. Review the extracted reference metadata below.
              </Dialog.Description>
              {activeCitation ? (
                <div className="mt-5 space-y-3 text-sm text-slate-600 dark:text-slate-300">
                  <div>
                    <span className="font-medium text-slate-700 dark:text-slate-200">Source</span>{" "}
                    <span>
                      {activeCitation.citation.title ?? `Source ${activeCitation.citation.sourceId}`}
                    </span>
                  </div>
                  <div>
                    <span className="font-medium text-slate-700 dark:text-slate-200">Chunk</span>{" "}
                    <span>{activeCitation.citation.chunkId ?? "unknown"}</span>
                  </div>
                  <div className="space-y-1">
                    <span className="font-medium text-slate-700 dark:text-slate-200">Source ID</span>
                    <p className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-mono text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      {activeCitation.citation.sourceId}
                    </p>
                  </div>
                  {activeCitation.citation.url ? (
                    <a
                      href={activeCitation.citation.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 underline hover:text-brand-500 dark:text-brand-300"
                    >
                      Open reference
                    </a>
                  ) : null}
                  <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-400">
                    Placeholder content for future chunk preview.
                  </div>
                </div>
              ) : null}
              <div className="mt-6 flex justify-end">
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="rounded-md border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:text-slate-200"
                  >
                    Close
                  </button>
                </Dialog.Close>
              </div>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}


