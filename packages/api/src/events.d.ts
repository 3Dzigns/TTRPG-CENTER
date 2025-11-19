import type { AdminOverrideEvent, QueryStatusEvent } from "@ttrpg-center/types";
export type EventPayload = QueryStatusEvent | AdminOverrideEvent | {
    type: string;
};
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
export declare const createEventStream: (url: string, options?: EventStreamOptions) => EventStream;
