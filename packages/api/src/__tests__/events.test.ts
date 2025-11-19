import { beforeEach, describe, expect, it, vi } from "vitest";
import { createEventStream } from "../events";

class MockEventSource {
  static instances: MockEventSource[] = [];
  public url: string;
  public options?: EventSourceInit;
  private listeners = new Map<string, ((event: any) => void)[]>();
  public closed = false;

  constructor(url: string, options?: EventSourceInit) {
    this.url = url;
    this.options = options;
    MockEventSource.instances.push(this);
    window.setTimeout(() => {
      this.dispatchEvent("open", new Event("open"));
    }, 0);
  }

  addEventListener(type: string, handler: (event: any) => void) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  removeEventListener(type: string, handler: (event: any) => void) {
    const handlers = this.listeners.get(type) ?? [];
    this.listeners.set(
      type,
      handlers.filter((stored) => stored !== handler)
    );
  }

  dispatchEvent(type: string, event: any) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.forEach((handler) => handler(event));
  }

  close() {
    this.closed = true;
  }
}

describe("createEventStream", () => {
  afterEach(() => {
    vi.useRealTimers();
  });
  beforeEach(() => {
    vi.useFakeTimers();
    MockEventSource.instances = [];
    // @ts-expect-error - assign test double
    globalThis.EventSource = MockEventSource;
  });

  it("notifies listeners with parsed payloads", () => {
    const stream = createEventStream("/events");
    const listener = vi.fn();
    stream.subscribe(listener);

    const instance = MockEventSource.instances.at(-1);
    expect(instance).toBeTruthy();

    instance?.dispatchEvent("message", { data: JSON.stringify({ type: "query.status", requestId: "req-1" }) });

    expect(listener).toHaveBeenCalledWith({ type: "query.status", requestId: "req-1" });
  });

  it("applies retry backoff", () => {
    createEventStream("/events", { initialDelayMs: 1000, maxRetries: 2 });

    const first = MockEventSource.instances.at(-1);
    expect(first).toBeTruthy();

    first?.dispatchEvent("error", new Event("error"));

    vi.advanceTimersByTime(1000);
    expect(MockEventSource.instances).toHaveLength(2);
  });
});


