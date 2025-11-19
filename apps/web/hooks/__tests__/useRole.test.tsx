import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useRole } from "../../hooks/useRole";
import { useAuthStore } from "../../stores/auth-store";

describe("useRole", () => {
  it("selects the first available role when none chosen", () => {
    act(() => {
      useAuthStore.getState().clear();
    });

    const { result } = renderHook(() => useRole(["player", "gm"]));

    expect(result.current.role).toBe("player");
  });

  it("keeps existing selection if still available", () => {
    act(() => {
      useAuthStore.getState().setSelectedRole("gm");
    });

    const { result } = renderHook(() => useRole(["player", "gm"]));
    expect(result.current.role).toBe("gm");
  });

  it("falls back when previous role is no longer allowed", () => {
    act(() => {
      useAuthStore.getState().setSelectedRole("admin");
    });

    const { result } = renderHook(() => useRole(["player"]));
    expect(result.current.role).toBe("player");
  });
});
