import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider, useToast } from "../toast-provider";

function TestHarness({ title = "Test toast", duration }: { title?: string; duration?: number }) {
  const { showToast } = useToast();
  return (
    <button
      type="button"
      onClick={() =>
        showToast({
          title,
          description: "Toast body",
          duration
        })
      }
    >
      Trigger toast
    </button>
  );
}

describe("ToastProvider", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders toasts when requested", () => {
    render(
      <ToastProvider>
        <TestHarness />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText(/trigger toast/i));

    expect(screen.getByText("Test toast")).toBeVisible();
    expect(screen.getByText("Toast body")).toBeVisible();
  });

  it("auto dismisses toasts after the default duration", async () => {
    vi.useFakeTimers();

    render(
      <ToastProvider>
        <TestHarness />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText(/trigger toast/i));
    expect(screen.getByText("Test toast")).toBeVisible();

    vi.advanceTimersByTime(6000);

    await waitFor(() => {
      expect(screen.queryByText("Test toast")).not.toBeInTheDocument();
    });
  });

  it("allows persistent toasts when duration is set to zero", () => {
    render(
      <ToastProvider>
        <TestHarness title="Persistent" duration={0} />
      </ToastProvider>
    );

    fireEvent.click(screen.getByText(/trigger toast/i));

    expect(screen.getByText("Persistent")).toBeVisible();
  });
});

