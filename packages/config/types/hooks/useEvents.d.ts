import type { EventPayload, EventStreamOptions } from "@ttrpg-center/api";
export interface UseEventsOptions<T extends EventPayload> extends Omit<EventStreamOptions, "filter" | "parse"> {
    parse?: (data: string) => T | T[] | null;
    filter?: (event: T) => boolean;
    onEvent?: (event: T) => void;
}
export declare const useEvents: <T extends EventPayload>(url: string, { parse, filter, onEvent, ...rest }?: UseEventsOptions<T>) => {
    status: any;
    event: any;
};
