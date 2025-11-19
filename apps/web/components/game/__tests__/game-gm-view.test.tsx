import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Me, UsageSummary } from "@ttrpg-center/types";
import { GameGmView } from "../game-gm-view";

const mockGame = {
  id: "game-1",
  title: "The Emerald Spire",
  members: [
    {
      userId: "gm-1",
      email: "gm@example.com",
      displayName: "GM Example",
      role: "gm",
      status: "active"
    }
  ],
  tier: "premium",
  sources: [
    {
      id: "source-1",
      name: "Player Handbook",
      category: "ruleset",
      owned: true,
      updatedAt: new Date().toISOString()
    }
  ],
  sourceIds: ["source-1"],
  status: "active",
  gmId: "gm-1",
  playerIds: [],
  sessionCount: 3,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString()
};

const mockUsage: UsageSummary = {
  scope: "game",
  id: "game-1",
  updatedAt: new Date().toISOString(),
  meter: {
    totalSecondsPlayed: 7200,
    monthlySessionCount: 4,
    automationCreditsRemaining: 80,
    textAssistRemaining: 40,
    audioBridgeRemaining: 15,
    discordBridgeRemaining: 10
  }
};

const mockSession: Me = {
  id: "gm-1",
  displayName: "GM Example",
  email: "gm@example.com",
  roles: ["gm"],
  preferredTheme: "dark",
  usage: {
    totalSecondsPlayed: 0,
    monthlySessionCount: 0,
    automationCreditsRemaining: 0
  }
};

const submitQuery = vi.fn();
const createEventsStream = vi.fn();
const getGameById = vi.fn(async () => mockGame);
const getUsage = vi.fn(async () => mockUsage);
const getBillingLink = vi.fn(async () => ({
  url: "https://billing.example.com/manage",
  expiresAt: new Date(Date.now() + 1000 * 60 * 60).toISOString(),
  label: "Manage subscription"
}));
const windowOpen = vi.spyOn(window, "open");

vi.mock("../../../lib/api", () => ({
  getApiClient: () => ({
    getGameById,
    getUsage,
    getBillingLink,
    submitQuery,
    createEventsStream
  })
}));

vi.mock("../chat-panel", () => ({
  ChatPanel: ({
    onActiveCitationsChange
  }: {
    onActiveCitationsChange?: (citations: unknown[], messageId: string | null, metadata?: { isStreaming: boolean }) => void;
  }) => {
    onActiveCitationsChange?.(
      [{ sourceId: "source-1", title: "Player Handbook" }],
      "message-1",
      { isStreaming: false }
    );
    return <div data-testid="chat-panel" />;
  }
}));

vi.mock("../citations-list", () => ({
  CitationsList: ({ citations }: { citations: unknown[] }) => (
    <div data-testid="citations">{citations.length} citations</div>
  )
}));

describe("GameGmView", () => {
  beforeEach(() => {
    getGameById.mockClear();
    getUsage.mockClear();
    getBillingLink.mockClear();
  });

  const renderWithClient = () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <GameGmView session={mockSession} gameId="game-1" />
      </QueryClientProvider>
    );
  };

  it("renders GM controls with disabled toggles and quick links", async () => {
    renderWithClient();

    await waitFor(() => expect(getGameById).toHaveBeenCalled());

    expect(screen.getByText(/GM Controls/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open GM Hub/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Manage Members/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Manage Sources/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Game Settings/i })).toBeInTheDocument();

    const toggles = screen.getAllByRole("checkbox");
    expect(toggles).toHaveLength(3);
    toggles.forEach((toggle) => {
      expect(toggle).toBeDisabled();
      expect(toggle).toHaveAttribute("title", "Coming soon");
    });
  });

  it("opens the billing portal in a new tab", async () => {
    windowOpen.mockReturnValue(window);

    renderWithClient();

    const billingButton = await screen.findByRole("button", { name: /manage billing/i });
    expect(billingButton).toBeEnabled();

    billingButton.click();

    await waitFor(() => {
      expect(getBillingLink).toHaveBeenCalledWith("game", "game-1");
      expect(windowOpen).toHaveBeenCalledWith(
        "https://billing.example.com/manage",
        "_blank",
        "noopener,noreferrer"
      );
    });
  });

  it("shows an error banner when billing portal fails", async () => {
    getBillingLink.mockRejectedValueOnce(new Error("Billing offline"));
    windowOpen.mockReturnValue(window);

    renderWithClient();

    const billingButton = await screen.findByRole("button", { name: /manage billing/i });
    billingButton.click();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/billing offline/i);
    });
  });  it("surfaces citations from the chat panel callback", async () => {
    renderWithClient();

    await waitFor(() => expect(screen.getByTestId("citations")).toHaveTextContent("1 citations"));
  });
});




