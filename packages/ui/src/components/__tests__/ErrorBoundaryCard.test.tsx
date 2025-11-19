import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { ErrorBoundaryCard } from "../ErrorBoundaryCard";

describe("ErrorBoundaryCard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders title, description, and trace id", () => {
    render(
      <ErrorBoundaryCard
        title="Unable to load dashboard"
        description="We could not retrieve your data."
        traceId="trace-123"
      />
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Unable to load dashboard")).toBeVisible();
    expect(screen.getByText("We could not retrieve your data.")).toBeVisible();
    expect(screen.getByText("trace-123")).toBeVisible();
  });

  it("invokes retry handler when retry button clicked", () => {
    const handleRetry = vi.fn();

    render(
      <ErrorBoundaryCard
        onRetry={handleRetry}
        retryLabel="Try again"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });

  it("disables retry button when requested", () => {
    const handleRetry = vi.fn();

    render(
      <ErrorBoundaryCard
        onRetry={handleRetry}
        retryDisabled
      />
    );

    const button = screen.getByRole("button", { name: /retry/i });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(handleRetry).not.toHaveBeenCalled();
  });

  it("copies trace id to clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true
    });

    render(
      <ErrorBoundaryCard
        traceId="trace-abc"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /copy trace id/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith("trace-abc");
      expect(screen.getByText(/copied/i)).toBeVisible();
    });

    if (originalClipboard) {
      Object.defineProperty(navigator, "clipboard", originalClipboard);
    }
  });
});
