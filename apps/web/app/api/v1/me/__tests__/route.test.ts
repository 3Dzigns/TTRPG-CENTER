import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "../route";

const mockServerSession = vi.hoisted(() => ({
  getAuthenticatedSession: vi.fn()
}));

vi.mock("@/lib/auth/server-session", () => mockServerSession);

describe("GET /api/v1/me", () => {
  beforeEach(() => {
    mockServerSession.getAuthenticatedSession.mockReset();
  });

  it("returns 401 when the request is unauthenticated", async () => {
    mockServerSession.getAuthenticatedSession.mockResolvedValue(null);

    const request = new NextRequest("http://localhost/api/v1/me");
    const response = await GET(request);

    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const payload = await response.json();
    expect(payload).toEqual({ error: "Unauthorized" });
  });

  it("returns session details for authenticated requests", async () => {
    mockServerSession.getAuthenticatedSession.mockResolvedValue({
      user: {
        id: "user-123",
        email: "user@example.com",
        displayName: "Auth User",
        avatarUrl: "https://example.com/avatar.png"
      },
      roles: ["player", "gm"]
    });

    const request = new NextRequest("http://localhost/api/v1/me");
    const response = await GET(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const payload = await response.json();

    expect(payload).toMatchObject({
      id: "user-123",
      email: "user@example.com",
      displayName: "Auth User",
      roles: ["player", "gm"],
      avatarUrl: "https://example.com/avatar.png",
      preferredTheme: "system"
    });
    expect(payload.usage).toEqual({
      totalSecondsPlayed: 0,
      monthlySessionCount: 0,
      automationCreditsRemaining: 0,
      textAssistRemaining: 0,
      audioBridgeRemaining: 0,
      discordBridgeRemaining: 0
    });
  });
});
