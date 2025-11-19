import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TopNavItem } from "../../components/TopNav";
import { TopNav } from "../../components/TopNav";

const navItems: TopNavItem[] = [
  { label: "Player", href: "/player" },
  { label: "GM", href: "/gm" }
];

describe("TopNav", () => {
  it("applies aria-current when the nav item matches the current path", () => {
    render(
      <TopNav
        brand="Brand"
        navItems={navItems}
        currentPath="/player"
      />
    );

    expect(screen.getByRole("link", { name: /player/i })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /gm/i })).not.toHaveAttribute("aria-current");
  });
});

