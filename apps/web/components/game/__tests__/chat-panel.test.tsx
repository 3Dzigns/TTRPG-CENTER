import { fireEvent, render, screen, waitFor, act, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "../chat-panel";

const submitQueryMock = vi.fn();
const createEventsStreamMock = vi.fn();

vi.mock("../../../lib/api", () => ({
  getApiClient: () => ({
    submitQuery: submitQueryMock,
    createEventsStream: createEventsStreamMock
  })
}));

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  withCredentials: boolean;
  readyState = 0;
  private listeners = new Map<string, Set<(event: MessageEvent<string>) => void>>();

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.withCredentials = Boolean(init?.withCredentials);
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    const listeners = this.listeners.get(type);
    listeners?.delete(listener);
  }

  dispatchEvent(): boolean {
    return true;
  }

  close() {
    this.readyState = 2;
  }

  emit(type: string, payload: unknown) {
    const listeners = this.listeners.get(type);
    if (!listeners || listeners.size === 0) {
      return;
    }
    const event = {
      data: typeof payload === "string" ? payload : JSON.stringify(payload)
    } as MessageEvent<string>;
    listeners.forEach((listener) => listener(event));
  }
}

// @ts-expect-error - assign test double
globalThis.EventSource = MockEventSource;

const renderChatPanel = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPanel
        gameId="game-1"
        actorId="player-1"
        characterId="char-1"
        sourceIds={["source-1"]}
      />
    </QueryClientProvider>
  );
};

beforeEach(() => {
  submitQueryMock.mockReset();
  createEventsStreamMock.mockReset();
  MockEventSource.instances = [];
  localStorage.clear();
  createEventsStreamMock.mockImplementation(
    (path: string) => new MockEventSource(path ?? "/v1/events", { withCredentials: true })
  );
});

afterEach(() => {
  cleanup();
});

describe("ChatPanel", () => {
  it("disables input until acknowledgement and re-enables after completion", async () => {
    submitQueryMock.mockResolvedValue({
      requestId: "req-1",
      status: "queued"
    });

    renderChatPanel();

    const textarea = screen.getByLabelText(/ask the assistant/i);
    fireEvent.change(textarea, { target: { value: "How many actions do I have?" } });

    const sendButton = screen.getByRole("button", { name: /send/i });
    fireEvent.click(sendButton);

    expect(sendButton).toBeDisabled();
    expect(submitQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        scope: "game",
        gameId: "game-1",
        actorId: "player-1"
      })
    );

    await waitFor(() => expect(createEventsStreamMock).toHaveBeenCalled());

    const eventSource = MockEventSource.instances.at(-1);
    expect(eventSource).toBeDefined();

    act(() => {
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-1",
        status: "completed",
        answer: "Players receive one action and one bonus action per turn."
      });
    });

    await waitFor(() => expect(sendButton).not.toBeDisabled());
    expect(
      screen.getByText(/players receive one action/i)
    ).toBeInTheDocument();
  });

  it("appends streamed deltas into the transcript", async () => {
    submitQueryMock.mockResolvedValue({
      requestId: "req-stream",
      status: "queued"
    });

    renderChatPanel();

    const textarea = screen.getByLabelText(/ask the assistant/i);
    fireEvent.change(textarea, { target: { value: "Describe the goblin lair." } });

    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(createEventsStreamMock).toHaveBeenCalled());
    const eventSource = MockEventSource.instances.at(-1);

    act(() => {
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-stream",
        status: "streaming",
        delta: "The lair is a cramped cavern "
      });
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-stream",
        status: "streaming",
        delta: "with flickering torchlight."
      });
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-stream",
        status: "completed"
      });
    });

    await waitFor(() =>
      expect(
        screen.getByText(/cramped cavern with flickering torchlight/i)
      ).toBeInTheDocument()
    );
  });

  it("offers retry when the assistant fails", async () => {
    submitQueryMock
      .mockResolvedValueOnce({
        requestId: "req-fail",
        status: "queued"
      })
      .mockResolvedValueOnce({
        requestId: "req-retry",
        status: "queued"
      });

    renderChatPanel();

    const textarea = screen.getByLabelText(/ask the assistant/i);
    fireEvent.change(textarea, { target: { value: "Summarize the last session." } });

    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(createEventsStreamMock).toHaveBeenCalled());
    const eventSource = MockEventSource.instances.at(-1);

    act(() => {
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-fail",
        status: "failed",
        error: "Assistant unavailable"
      });
    });

    const retryButton = await screen.findByRole("button", { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);

    await waitFor(() => expect(submitQueryMock).toHaveBeenCalledTimes(2));
  });

  it("allows cancelling an in-flight response", async () => {
    submitQueryMock.mockResolvedValue({
      requestId: "req-stop",
      status: "queued"
    });

    renderChatPanel();

    fireEvent.change(screen.getByLabelText(/ask the assistant/i), {
      target: { value: "Stop this response." }
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(createEventsStreamMock).toHaveBeenCalled());

    const stopButton = await screen.findByRole("button", { name: /stop streaming response/i });
    fireEvent.click(stopButton);

    expect(
      screen.queryByRole("button", { name: /stop streaming response/i })
    ).not.toBeInTheDocument();

    const eventSource = MockEventSource.instances.at(-1);
    act(() => {
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-stop",
        status: "completed",
        answer: "You should not see this."
      });
    });

    await waitFor(() =>
      expect(screen.getByText(/stopped/i)).toBeInTheDocument()
    );
    expect(
      screen.queryByText(/you should not see this/i)
    ).not.toBeInTheDocument();
  });

  it("renders citation pills and opens the citation modal", async () => {
    submitQueryMock.mockResolvedValue({
      requestId: "req-citation",
      status: "queued"
    });

    renderChatPanel();

    fireEvent.change(screen.getByLabelText(/ask the assistant/i), {
      target: { value: "Show citations please." }
    });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(createEventsStreamMock).toHaveBeenCalled());
    const eventSource = MockEventSource.instances.at(-1);

    act(() => {
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-citation",
        status: "streaming",
        delta: "Here is the answer."
      });
      eventSource?.emit("message", {
        type: "query.status",
        requestId: "req-citation",
        status: "completed",
        citations: [
          { sourceId: "src-1", chunkId: "12", title: "Goblin Den" },
          { sourceId: "src-2", chunkId: "7" }
        ]
      });
    });

    const citationButtons = await screen.findAllByRole("button", {
      name: /view citation/i
    });
    expect(citationButtons).toHaveLength(2);

    fireEvent.click(citationButtons[0]);

    await waitFor(() =>
      expect(screen.getByText(/citation details/i)).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /close/i }));

    await waitFor(() =>
      expect(screen.queryByText(/citation details/i)).not.toBeInTheDocument()
    );
  });
});
