import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SourceMultiSelect } from "../SourceMultiSelect";

if (!("ResizeObserver" in globalThis)) {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  // @ts-expect-error - test polyfill
  globalThis.ResizeObserver = ResizeObserver;
}

const sources = Array.from({ length: 30 }).map((_, index) => ({
  id: `source-${index + 1}`,
  name: `Source ${index + 1}`,
  category: index % 2 === 0 ? "module" : "campaign",
  owned: index % 3 === 0,
  updatedAt: new Date().toISOString()
}));

describe("SourceMultiSelect", () => {
  it("filters sources when typing", async () => {
    const handleChange = vi.fn();
    render(
      <SourceMultiSelect sources={sources} selectedIds={[]} onChange={handleChange} />
    );

    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Source 30" } });

    expect(await screen.findByRole("option", { name: /Source 30/i })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /Source 10/i })).toBeNull();
  });

  it("toggle selection with keyboard", async () => {
    const handleChange = vi.fn();
    render(
      <SourceMultiSelect sources={sources} selectedIds={[]} onChange={handleChange} />
    );

    const listbox = screen.getByRole("listbox");
    listbox.focus();
    fireEvent.keyDown(listbox, { key: "ArrowDown" });
    fireEvent.keyDown(listbox, { key: "Enter" });

    await screen.findByRole("option", { name: /Source 1/i });
    expect(handleChange).toHaveBeenCalledWith(["source-1"]);
  });
});
