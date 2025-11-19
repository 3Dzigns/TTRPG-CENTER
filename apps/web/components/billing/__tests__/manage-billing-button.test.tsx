import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { ApiError } from "@ttrpg-center/api";
import { ManageBillingButton } from "../manage-billing-button";

const getBillingLink = vi.fn();

vi.mock("../../../lib/api", () => ({
  getApiClient: () => ({
    getBillingLink
  })
}));

describe("ManageBillingButton", () => {
  const openSpy = vi.spyOn(window, "open");

  beforeEach(() => {
    getBillingLink.mockReset();
    openSpy.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("opens billing portal in a new tab on success", async () => {
    getBillingLink.mockResolvedValue({
      url: "https://billing.example.com/portal",
      label: "Manage subscription",
      expiresAt: new Date(Date.now() + 60_000).toISOString()
    });
    openSpy.mockReturnValue(window);

    render(<ManageBillingButton scope="user" scopeId="me" />);

    fireEvent.click(screen.getByRole("button", { name: /manage billing/i }));

    await waitFor(() => {
      expect(getBillingLink).toHaveBeenCalledWith("user", "me");
      expect(openSpy).toHaveBeenCalledWith(
        "https://billing.example.com/portal",
        "_blank",
        "noopener,noreferrer"
      );
    });

    expect(
      screen.queryByRole("alert", { name: "" })
    ).not.toBeInTheDocument();
  });

  it("shows an error banner when the billing API fails", async () => {
    const error = new ApiError("Billing unavailable", 500, { trace_id: "trace-123" });
    getBillingLink.mockRejectedValue(error);
    openSpy.mockReturnValue(window);

    render(<ManageBillingButton scope="user" scopeId="me" />);

    fireEvent.click(screen.getByRole("button", { name: /manage billing/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Billing unavailable");
      expect(screen.getByText(/trace id/i)).toHaveTextContent("trace-123");
    });
  });

  it("warns when the browser blocks the pop-up", async () => {
    getBillingLink.mockResolvedValue({
      url: "https://billing.example.com/portal",
      label: "Manage subscription",
      expiresAt: new Date(Date.now() + 60_000).toISOString()
    });
    openSpy.mockReturnValue(null);

    render(<ManageBillingButton scope="user" scopeId="me" />);

    fireEvent.click(screen.getByRole("button", { name: /manage billing/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/pop-up blocked/i)
      ).toBeInTheDocument();
    });
  });
});
