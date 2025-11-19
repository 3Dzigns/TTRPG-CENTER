import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { UsageGroup } from "../UsageGroup";

describe("UsageGroup", () => {
  it("renders meters with accessible progress bars", () => {
    render(
      <UsageGroup
        title="Usage"
        description="Test description"
        items={[
          { label: "Automation", value: 40, quota: 100, description: "Automation usage." },
          { label: "Audio bridge", value: 0, quota: 60, disabled: true, disabledReason: "Coming soon" }
        ]}
      />
    );

    const progress = screen.getAllByRole("progressbar");
    expect(progress).toHaveLength(2);
    expect(progress[0]).toHaveAttribute("aria-valuenow", "40");
    expect(progress[1]).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/Automation/)).toBeInTheDocument();
    expect(screen.getByText(/Coming soon/i)).toHaveAttribute("title", "Coming soon");
  });
});

