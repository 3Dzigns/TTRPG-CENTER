"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { EventPayload, EventStreamOptions } from "@ttrpg-center/api";
import { createEventStream } from "@ttrpg-center/api";

export interface UseEventsOptions<T extends EventPayload>
  extends Omit<EventStreamOptions, "filter" | "parse"> {
  parse?: (data: string) => T | T[] | null;
  filter?: (event: T) => boolean;
  onEvent?: (event: T) => void;
}

export const useEvents = <T extends EventPayload>(
  url: string,
  { parse, filter, onEvent, ...rest }: UseEventsOptions<T> = {}
) => {
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [event, setEvent] = useState<T | null>(null);

  const parseRef = useRef(parse);
  const filterRef = useRef(filter);
  const onEventRef = useRef(onEvent);

  parseRef.current = parse;
  filterRef.current = filter;
  onEventRef.current = onEvent;

  const streamOptions = useMemo<EventStreamOptions>(() => {
    return {
      ...rest,
      parse: (data) => parseRef.current?.(data) ?? JSON.parse(data),
      filter: (payload) =>
        filterRef.current ? filterRef.current(payload as T) : true
    };
  }, [rest]);

  useEffect(() => {
    const stream = createEventStream(url, streamOptions);
    setStatus(stream.getStatus());

    const unsubscribe = stream.subscribe((payload) => {
      const events = Array.isArray(payload) ? (payload as T[]) : ([payload] as T[]);
      events.forEach((single) => {
        setEvent(single);
        onEventRef.current?.(single);
      });
    });

    const interval = window.setInterval(() => {
      setStatus(stream.getStatus());
    }, 1000);

    return () => {
      unsubscribe();
      stream.close();
      window.clearInterval(interval);
    };
  }, [streamOptions, url]);

  return { status, event };
};
