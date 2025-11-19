"use client";

import type { Source } from "@ttrpg-center/types";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode
} from "react";
import { cn } from "../lib/cn";

export interface SourceMultiSelectProps {
  sources: Source[];
  selectedIds: string[];
  onChange: (next: string[]) => void;
  ownedSourceIds?: string[];
  selectedLabel?: string;
  renderFooter?: ReactNode;
  className?: string;
}

const ITEM_HEIGHT = 48;

const normalize = (value: string) =>
  value
    .toLowerCase()
    .trim()
    .replace(/\s+/g, " ");

export function SourceMultiSelect({
  sources,
  selectedIds,
  onChange,
  ownedSourceIds = [],
  selectedLabel = "Selected sources",
  renderFooter,
  className
}: SourceMultiSelectProps) {
  const [filter, setFilter] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);

  const dedupedSources = useMemo(() => {
    const unique = new Map<string, Source>();
    sources.forEach((source) => {
      if (!unique.has(source.id)) {
        unique.set(source.id, source);
      }
    });
    return Array.from(unique.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [sources]);

  const filtered = useMemo(() => {
    const searchValue = normalize(filter);
    if (!searchValue) {
      return dedupedSources;
    }
    return dedupedSources.filter((source) => normalize(source.name).includes(searchValue));
  }, [dedupedSources, filter]);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => listRef.current,
    estimateSize: () => ITEM_HEIGHT,
    overscan: 12
  });

  useEffect(() => {
    if (filtered.length > 0) {
      virtualizer.scrollToIndex(0);
    }
  }, [filter, virtualizer, filtered.length]);

  const toggleSource = (sourceId: string) => {
    const isSelected = selectedIds.includes(sourceId);
    if (isSelected) {
      onChange(selectedIds.filter((id) => id !== sourceId));
    } else {
      onChange([...selectedIds, sourceId]);
    }
  };

  const focusItem = (index: number) => {
    const button = listRef.current?.querySelector<HTMLButtonElement>(
      `[data-source-index="${index}"]`
    );
    button?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const { key } = event;
    const active = document.activeElement;

    if (active === listRef.current) {
      if (filtered.length === 0) {
        return;
      }
      if (["ArrowDown", "ArrowUp", "Home", "End", " ", "Enter"].includes(key)) {
        event.preventDefault();
        focusItem(key === "End" ? filtered.length - 1 : 0);
      }
      return;
    }

    if (!(active instanceof HTMLElement)) {
      return;
    }

    const indexAttr = active.dataset.sourceIndex;
    if (indexAttr === undefined) {
      return;
    }
    const currentIndex = Number(indexAttr);
    if (Number.isNaN(currentIndex)) {
      return;
    }

    if (key === "ArrowDown") {
      event.preventDefault();
      focusItem(Math.min(currentIndex + 1, filtered.length - 1));
    } else if (key === "ArrowUp") {
      event.preventDefault();
      focusItem(Math.max(currentIndex - 1, 0));
    } else if (key === "Home") {
      event.preventDefault();
      focusItem(0);
    } else if (key === "End") {
      event.preventDefault();
      focusItem(filtered.length - 1);
    } else if (key === " " || key === "Enter") {
      event.preventDefault();
      const source = filtered[currentIndex];
      if (source) {
        toggleSource(source.id);
      }
    } else if (key === "Escape") {
      event.preventDefault();
      searchRef.current?.focus();
    }
  };

  return (
    <section
      aria-labelledby="source-multiselect-heading"
      className={cn(
        "flex h-full min-h-[20rem] flex-col rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900",
        className
      )}
    >
      <header className="border-b border-slate-200 px-5 py-4 dark:border-slate-800">
        <h2
          id="source-multiselect-heading"
          className="text-lg font-semibold text-slate-900 dark:text-slate-100"
        >
          Available Sources
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Sources owned by your account for rules lookup.
        </p>
      </header>

      {selectedIds.length > 0 ? (
        <div className="flex flex-wrap gap-2 border-b border-slate-200 px-5 py-3 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-300">
          <span className="font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {selectedLabel}
          </span>
          {selectedIds.map((selectedId) => {
            const source = dedupedSources.find((item) => item.id === selectedId);
            return (
              <button
                key={selectedId}
                type="button"
                onClick={() => toggleSource(selectedId)}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-2 py-1 hover:border-brand-300 hover:text-brand-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 dark:border-slate-700 dark:hover:border-brand-500/60"
                aria-label={`Remove ${source?.name ?? selectedId}`}
              >
                <span className="max-w-[10rem] truncate text-xs font-medium text-slate-700 dark:text-slate-200">
                  {source?.name ?? selectedId}
                </span>
                <span aria-hidden className="text-slate-400">×</span>
              </button>
            );
          })}
        </div>
      ) : null}

      <div
        ref={listRef}
        role="listbox"
        tabIndex={0}
        aria-multiselectable="true"
        onKeyDown={handleKeyDown}
        className="relative flex-1 overflow-auto outline-none"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            position: "relative"
          }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const source = filtered[virtualItem.index];
            if (!source || virtualItem.index >= filtered.length) {
              return null;
            }
            const isSelected = selectedIds.includes(source.id);
            const isOwned = ownedSourceIds.includes(source.id);

            return (
              <button
                key={source.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                data-source-index={virtualItem.index}
                onClick={() => toggleSource(source.id)}
                className={cn(
                  "absolute left-0 right-0 flex items-center justify-between gap-3 px-5 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
                  isSelected
                    ? "bg-brand-50 text-brand-700 dark:bg-slate-800 dark:text-brand-200"
                    : "hover:bg-slate-50 dark:hover:bg-slate-800"
                )}
                style={{
                  transform: `translateY(${virtualItem.start}px)`,
                  height: `${virtualItem.size}px`
                }}
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{source.name}</p>
                  <p className="truncate text-xs text-slate-500 dark:text-slate-400">
                    {source.category}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2 text-xs">
                  {isOwned ? (
                    <span className="rounded-full bg-emerald-100 px-2 py-1 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-200">
                      Owned
                    </span>
                  ) : null}
                  <span
                    aria-hidden
                    className={cn(
                      "inline-flex h-3 w-3 rounded-full border",
                      isSelected
                        ? "border-brand-500 bg-brand-500"
                        : "border-slate-300 dark:border-slate-600"
                    )}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {renderFooter ? (
        <footer className="border-t border-slate-200 px-5 py-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
          {renderFooter}
        </footer>
      ) : null}
    </section>
  );
}

