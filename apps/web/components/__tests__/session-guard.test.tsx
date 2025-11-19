import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionGuard } from "../session-guard";
import { ApiError } from "@ttrpg-center/api";
import { useSession } from "../../hooks/useSession";

vi.mock("../../hooks/useSession");

const mockUseSession = vi.mocked(useSession);

describe("SessionGuard", () => {
  beforeEach(() => {
    mockUseSession.mockReset();
  });

  it("renders children when session is available", () => {
    mockUseSession.mockReturnValue({
      data: {
        id: "user-1",
        displayName: "Taylor",
        email: "taylor@example.com",
        roles: ["player"],
        preferredTheme: "dark",
        usage: {
          totalSecondsPlayed: 0,
          monthlySessionCount: 0,
          automationCreditsRemaining: 0
        }
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false
    });

    render(
      <SessionGuard>
        {() => <div data-testid="protected">Protected content</div>}
      </SessionGuard>
    );

    expect(screen.getByTestId("protected")).toBeInTheDocument();
  });

  it("shows error boundary card with trace id and retry", () => {
    const refetch = vi.fn();
    const error = new ApiError(
      "Unable to load session",
      500,
      { trace_id: "trace-789" },
      { traceId: "trace-789" }
    );

    mockUseSession.mockReturnValue({
      data: undefined,
      isLoading: false,
      error,
      refetch,
      isFetching: false
    });

    render(
      <SessionGuard>
        {() => <div data-testid="protected">Protected content</div>}
      </SessionGuard>
    );

    expect(screen.getByText(/trace id/i)).toHaveTextContent("trace-789");
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalled();
  });
});

