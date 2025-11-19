import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TopNav, type ThemePreference } from "@ttrpg-center/ui";

describe("TopNav", () => {
  it("cycles theme preference when toggle button is clicked", () => {
    const handleThemeToggle = vi.fn<(theme: ThemePreference) => void>();

    render(
      <TopNav
        brand={<span>Demo</span>}
        navItems={[{ label: "Player", href: "/player" }]}
        theme="light"
        onThemeToggle={handleThemeToggle}
      />
    );

    const button = screen.getByRole("button", { name: /toggle theme/i });
    fireEvent.click(button);

    expect(handleThemeToggle).toHaveBeenCalledWith("dark");
  });
});
