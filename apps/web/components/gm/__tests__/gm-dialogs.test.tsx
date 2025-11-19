import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CreateGameDialog } from "../create-game-dialog";
import { DeleteGameDialog } from "../delete-game-dialog";
import { InviteMemberDialog } from "../invite-member-dialog";

describe("GM dialogs", () => {
  it("validates required fields in CreateGameDialog", async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);

    render(
      <CreateGameDialog
        open
        onOpenChange={() => {}}
        onCreate={onCreate}
        isSubmitting={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /create game/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/game name is required/i)
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/game name/i), {
      target: { value: "Stormreach Saga" }
    });
    fireEvent.change(screen.getByLabelText(/summary/i), {
      target: { value: "Weekly actual-play campaign." }
    });
    fireEvent.click(screen.getByRole("radio", { name: /premium/i }));

    fireEvent.click(screen.getByRole("button", { name: /create game/i }));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith({
        title: "Stormreach Saga",
        summary: "Weekly actual-play campaign.",
        tier: "premium"
      });
    });
  });

  it("requires exact name match before deleting a game", async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined);

    render(
      <DeleteGameDialog
        open
        onOpenChange={() => {}}
        gameName="Vault Hunters"
        onConfirm={onConfirm}
        isDeleting={false}
      />
    );

    const confirmButton = screen.getByRole("button", { name: /delete game/i });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/type/i), {
      target: { value: "vault hunters" }
    });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/type/i), {
      target: { value: "Vault Hunters" }
    });
    expect(confirmButton).toBeEnabled();

    fireEvent.click(confirmButton);
    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalled();
    });
  });

  it("validates email input in InviteMemberDialog", async () => {
    const onInvite = vi.fn().mockResolvedValue(undefined);

    render(
      <InviteMemberDialog
        open
        onOpenChange={() => {}}
        onInvite={onInvite}
        isSubmitting={false}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /send invite/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/provide a valid email address/i)
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "gm@example.com" }
    });
    fireEvent.change(screen.getByLabelText(/role/i), {
      target: { value: "co-gm" }
    });
    fireEvent.click(screen.getByRole("button", { name: /send invite/i }));

    await waitFor(() => {
      expect(onInvite).toHaveBeenCalledWith({
        email: "gm@example.com",
        role: "co-gm"
      });
    });
  });
});
