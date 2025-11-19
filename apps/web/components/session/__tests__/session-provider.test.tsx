import { describe, expect, it, beforeEach, vi } from "vitest";
import { act } from "react-dom/test-utils";
import { createRoot } from "react-dom/client";
import { useEffect } from "react";
import { ApiError } from "@ttrpg-center/api";
import { SessionProvider } from "../session-provider";
import { useSession } from "@/hooks/useSession";

const mockGetMe = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", () => ({
  getApiClient: () => ({
    getMe: mockGetMe
  })
}));

type SessionSnapshot = ReturnType<typeof useSession>;

function SessionProbe({ onChange }: { onChange: (value: SessionSnapshot) => void }) {
  const session = useSession();

  useEffect(() => {
    onChange(session);
  }, [session, onChange]);

  return null;
}

async function waitFor(assertion: () => void | boolean, timeoutMs = 1_000) {
  const start = Date.now();
  // eslint-disable-next-line no-constant-condition
  while (true) {
    try {
      const result = assertion();
      if (result === undefined || result === true) {
        return;
      }
    } catch {
      // swallow and retry
    }
    if (Date.now() - start > timeoutMs) {
      throw new Error("waitFor timed out");
    }
    await new Promise((resolve) => setTimeout(resolve, 15));
  }
}

async function renderWithProvider(onChange: (value: SessionSnapshot) => void) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(
      <SessionProvider>
        <SessionProbe onChange={onChange} />
      </SessionProvider>
    );
  });

  return () => {
    act(() => {
      root.unmount();
    });
    container.remove();
  };
}

describe("SessionProvider", () => {
  beforeEach(() => {
    mockGetMe.mockReset();
  });

  it("loads the authenticated session and exposes it to consumers", async () => {
    mockGetMe.mockResolvedValueOnce({
      id: "user-1",
      email: "user@example.com",
      displayName: "Player One",
      roles: ["player"],
      preferredTheme: "light",
      usage: {
        totalSecondsPlayed: 10,
        monthlySessionCount: 2,
        automationCreditsRemaining: 5
      }
    });

    let snapshot: SessionSnapshot | null = null;
    const cleanup = await renderWithProvider((value) => {
      snapshot = value;
    });

    await waitFor(() => snapshot?.status === "authenticated");
    expect(snapshot?.data?.displayName).toBe("Player One");
    expect(snapshot?.error).toBeNull();
    cleanup();
  });

  it("marks the session as unauthenticated on 401 errors", async () => {
    mockGetMe.mockRejectedValueOnce(new ApiError("Unauthorized", 401));

    let snapshot: SessionSnapshot | null = null;
    const cleanup = await renderWithProvider((value) => {
      snapshot = value;
    });

    await waitFor(() => snapshot?.status === "unauthenticated");
    expect(snapshot?.data).toBeNull();
    expect(snapshot?.error).toBeInstanceOf(ApiError);
    cleanup();
  });
});
