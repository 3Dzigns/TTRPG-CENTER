import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, beforeEach, vi } from "vitest";
import type { Me } from "@ttrpg-center/types";
import type { ReactNode } from "react";
import { GamePageClient } from "../[id]/page-client";

const baseSession: Me = {
  id: "user-1",
  displayName: "Test User",
  email: "user@example.com",
  roles: ["player"],
  preferredTheme: "dark",
  usage: {
    totalSecondsPlayed: 0,
    monthlySessionCount: 0,
    automationCreditsRemaining: 0
  }
};

let currentSession: Me = { ...baseSession };

const getGameById = vi.fn(async () => ({
  id: "game-1",
  title: "Campaign",
  members: [
    {
      userId: currentSession.id,
      email: currentSession.email,
      displayName: currentSession.displayName,
      role: currentSession.roles.includes("gm") ? "gm" : "player",
      status: "active"
    }
  ],
  tier: "standard",
  status: "active",
  gmId: "gm-123",
  playerIds: [currentSession.id],
  sessionCount: 2,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString()
}));

vi.mock("../../../components/session-guard", () => ({
  SessionGuard: ({ children }: { children: (session: Me) => ReactNode }) => (
    <>{children(currentSession)}</>
  )
}));

vi.mock("../../../components/game/game-player-view", () => ({
  GamePlayerView: () => <div data-testid="player-view" />
}));

vi.mock("../../../components/game/game-gm-view", () => ({
  GameGmView: () => <div data-testid="gm-view" />
}));

vi.mock("../../../lib/api", () => ({
  getApiClient: () => ({
    getGameById
  })
}));

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
      <GamePageClient gameId="game-1" />
    </QueryClientProvider>
  );
};

describe("GamePageClient", () => {
  beforeEach(() => {
    currentSession = { ...baseSession, roles: ["player"] };
    getGameById.mockClear();
  });

  it("renders player view for non-GM members", async () => {
    renderWithClient();

    await waitFor(() => expect(getGameById).toHaveBeenCalled());

    expect(screen.getByTestId("player-view")).toBeInTheDocument();
    expect(screen.queryByTestId("gm-view")).not.toBeInTheDocument();
  });

  it("renders GM view when session has GM role", async () => {
    currentSession = { ...baseSession, roles: ["gm"] };

    renderWithClient();

    await waitFor(() => expect(getGameById).toHaveBeenCalled());

    expect(screen.getByTestId("gm-view")).toBeInTheDocument();
    expect(screen.queryByTestId("player-view")).not.toBeInTheDocument();
  });

  it("returns unauthorized message when user lacks required roles", async () => {
    currentSession = { ...baseSession, roles: [] };

    renderWithClient();

    expect(
      screen.getByText(/player access required/i)
    ).toBeInTheDocument();
  });
});
