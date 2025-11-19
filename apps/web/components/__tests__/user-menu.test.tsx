import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UserMenu } from "@ttrpg-center/ui";

describe("UserMenu", () => {
  const baseUser = {
    displayName: "Taylor GM",
    email: "taylor@example.com",
    avatarUrl: undefined,
    roles: ["gm", "player"]
  };

  it("allows switching roles", () => {
    const handleRoleChange = vi.fn();

    render(
      <UserMenu
        user={baseUser}
        selectedRole="gm"
        onRoleChange={handleRoleChange}
      />
    );

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(screen.getByText(/player/i));

    expect(handleRoleChange).toHaveBeenCalledWith("player");
  });

  it("calls sign out handler", () => {
    const handleSignOut = vi.fn();

    render(
      <UserMenu
        user={{ ...baseUser, roles: ["gm"] }}
        onSignOut={handleSignOut}
      />
    );

    fireEvent.click(screen.getByRole("button"));
    fireEvent.click(screen.getByText(/sign out/i));

    expect(handleSignOut).toHaveBeenCalled();
  });
});
