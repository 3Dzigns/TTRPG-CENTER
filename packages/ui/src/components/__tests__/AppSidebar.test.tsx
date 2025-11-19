import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SidebarNavItem } from "../../components/AppSidebar";
import { AppSidebar } from "../../components/AppSidebar";

const items: SidebarNavItem[] = [
  { label: "Player Overview", href: "/player" },
  { label: "GM Controls", href: "/gm", roles: ["gm"] }
];

describe("AppSidebar", () => {
  it("marks the current page for assistive tech", () => {
    render(
      <AppSidebar
        role="gm"
        items={items}
        currentPath="/gm"
      />
    );

    expect(screen.getByRole("link", { name: /gm controls/i })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /player overview/i })).not.toHaveAttribute("aria-current");
  });
});

