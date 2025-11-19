import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { AdminDashboard } from "../admin-dashboard";

const mockApi = {
  getAdminHealth: vi.fn(),
  getSources: vi.fn(),
  getUsers: vi.fn(),
  getAdminAudit: vi.fn(),
  submitAdminOverride: vi.fn(),
  mutateAdminSource: vi.fn(),
  createEventsStream: vi.fn()
};

vi.mock("../../../lib/api", () => ({
  getApiClient: () => mockApi
}));

const createWrapper =
  () =>
  ({ children }: { children: ReactNode }) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };

describe("AdminDashboard", () => {
  let emitMessage: ((event: MessageEvent<string>) => void) | null = null;

  beforeEach(() => {
    vi.restoreAllMocks();
    emitMessage = null;
    mockApi.createEventsStream.mockImplementation(() => {
      return {
        addEventListener: (_type: string, handler: (event: MessageEvent<string>) => void) => {
          emitMessage = handler;
        },
        removeEventListener: () => {},
        close: () => {}
      } as unknown as EventSource;
    });
    mockApi.submitAdminOverride.mockResolvedValue({ traceId: "trace-override", status: "accepted" });
    mockApi.mutateAdminSource.mockResolvedValue({
      traceId: "trace-source",
      action: "update",
      source: {
        id: "source-1",
        name: "Player Handbook",
        category: "ruleset",
        owned: false,
        updatedAt: new Date().toISOString()
      }
    });
    mockApi.getAdminHealth.mockResolvedValue({
      updatedAt: new Date().toISOString(),
      services: [
        {
          id: "cassandra",
          name: "Cassandra",
          status: "healthy",
          lastCheckedAt: new Date().toISOString()
        },
        {
          id: "mongo",
          name: "MongoDB",
          status: "degraded",
          lastCheckedAt: new Date().toISOString()
        }
      ]
    });
    mockApi.getSources.mockResolvedValue([
      {
        id: "source-1",
        name: "Player Handbook",
        category: "ruleset",
        owned: false,
        updatedAt: new Date().toISOString()
      }
    ]);
    mockApi.getUsers.mockResolvedValue([
      {
        id: "user-1",
        displayName: "Taylor GM",
        email: "taylor@example.com",
        roles: ["gm"],
        preferredTheme: "dark",
        usage: {
          totalSecondsPlayed: 0,
          monthlySessionCount: 0,
          automationCreditsRemaining: 0
        }
      }
    ]);
    mockApi.getAdminAudit.mockResolvedValue({
      entries: [
        {
          id: "audit-1",
          actor: "taylor@example.com",
          traceId: "trace_123",
          action: "override:create",
          scope: "cassandra",
          summary: "Created new source",
          createdAt: new Date().toISOString()
        }
      ]
    });
  });

  it("renders health cards, sources, users, and audit entries", async () => {
    render(<AdminDashboard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Cassandra/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/MongoDB/i)).toBeInTheDocument();

    expect(await screen.findByText(/Player Handbook/i)).toBeInTheDocument();
    expect(await screen.findByText(/Taylor GM/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/override:create/i)).toBeInTheDocument();
    });
  });

  it("shows empty states when data sets are empty", async () => {
    mockApi.getSources.mockResolvedValueOnce([]);
    mockApi.getUsers.mockResolvedValueOnce([]);
    mockApi.getAdminAudit.mockResolvedValueOnce({ entries: [] });

    render(<AdminDashboard />, { wrapper: createWrapper() });

    expect(await screen.findByText(/No central sources found/i)).toBeInTheDocument();
    expect(await screen.findByText(/No users found/i)).toBeInTheDocument();
    expect(await screen.findByText(/No audit entries match the current filters/i)).toBeInTheDocument();
  });

  it("surfaces error states for failed calls", async () => {
    mockApi.getAdminHealth.mockRejectedValueOnce(new Error("fail health"));
    mockApi.getSources.mockRejectedValueOnce(new Error("fail sources"));
    mockApi.getUsers.mockRejectedValueOnce(new Error("fail users"));
    mockApi.getAdminAudit.mockRejectedValueOnce(new Error("fail audit"));

    render(<AdminDashboard />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Unable to refresh health data/i)).toBeInTheDocument();
    expect(await screen.findByText(/Failed to load central sources/i)).toBeInTheDocument();
    expect(await screen.findByText(/Failed to load users/i)).toBeInTheDocument();
    expect(await screen.findByText(/Failed to load audit entries/i)).toBeInTheDocument();
  });

  it("handles override events and suggests re-ingestion", async () => {
    render(<AdminDashboard />, { wrapper: createWrapper() });

    await waitFor(() => expect(mockApi.createEventsStream).toHaveBeenCalled());
    const handler = emitMessage;
    expect(handler).toBeTruthy();

    handler?.({
      data: JSON.stringify({
        type: "admin_override",
        traceId: "trace-event",
        target: "cassandra",
        sourceId: "source-99",
        actor: "ops",
        createdAt: new Date().toISOString()
      })
    } as MessageEvent<string>);

    expect(await screen.findByText(/Re-ingest recommended/i)).toBeInTheDocument();
    expect(screen.getByText(/Trace ID: trace-event/i)).toBeInTheDocument();
  });
});
