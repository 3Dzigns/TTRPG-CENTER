import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  CharacterList,
  SourceMultiSelect
} from "@ttrpg-center/ui";
import type { Character, Source } from "@ttrpg-center/types";
import { CharacterCreateDialog } from "../character-create-dialog";

const mockCharacters: Character[] = [
  {
    id: "char-1",
    name: "Aelar",
    className: "Wizard",
    level: 5,
    ownerId: "me",
    portraitUrl: undefined,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    system: "dnd-5e",
    activeSourceIds: ["source-1"],
    gameId: "game-1"
  },
  {
    id: "char-2",
    name: "Bryn",
    className: "Rogue",
    level: 3,
    ownerId: "me",
    portraitUrl: undefined,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    system: "pf2e",
    activeSourceIds: [],
    gameId: null
  }
];

const mockSources: Source[] = Array.from({ length: 5 }).map((_, index) => ({
  id: `source-${index + 1}`,
  name: `Source ${index + 1}`,
  category: "module",
  owned: index % 2 === 0,
  updatedAt: new Date().toISOString()
}));

describe("Player hub components", () => {
  it("calls onSelect when a character is clicked", () => {
    const handleSelect = vi.fn();
    render(
      <CharacterList
        characters={mockCharacters}
        selectedId={mockCharacters[0].id}
        onSelect={handleSelect}
        onCreateClick={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText(/Bryn/i));
    expect(handleSelect).toHaveBeenCalledWith(mockCharacters[1]);
  });

  it("validates character creation form inputs", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);

    render(
      <CharacterCreateDialog
        open
        onOpenChange={() => {}}
        onCreate={onCreate}
        isSubmitting={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /create character/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/name is required/i)
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: "Cal" }
    });
    fireEvent.change(screen.getByLabelText(/class/i), {
      target: { value: "Bard" }
    });
    fireEvent.change(screen.getByLabelText(/level/i), {
      target: { value: "2" }
    });

    fireEvent.click(screen.getByRole("button", { name: /create character/i }));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith({
        name: "Cal",
        className: "Bard",
        level: 2,
        system: "dnd-5e"
      });
    });
  });

  it("toggles sources via multi-select list", async () => {
    const onChange = vi.fn();
    render(
      <div style={{ height: 300 }}>
        <SourceMultiSelect
          sources={mockSources}
          selectedIds={["source-1"]}
          onChange={onChange}
          ownedSourceIds={["source-1"]}
        />
      </div>
    );

    const option = await screen.findByRole("option", {
      name: /source 2/i
    });

    fireEvent.click(option);

    expect(onChange).toHaveBeenCalledWith(["source-1", "source-2"]);
  });
});
