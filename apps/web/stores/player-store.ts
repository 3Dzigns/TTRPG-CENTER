import { create } from "zustand";

interface PlayerState {
  activeCharacterId: string | null;
  activeGameId: string | null;
  activeSourceIds: string[];
  setActiveCharacter: (characterId: string | null) => void;
  setActiveGame: (gameId: string | null) => void;
  setActiveSources: (sourceIds: string[]) => void;
  reset: () => void;
}

export const usePlayerStore = create<PlayerState>((set) => ({
  activeCharacterId: null,
  activeGameId: null,
  activeSourceIds: [],
  setActiveCharacter: (characterId) =>
    set((state) => ({
      activeCharacterId: characterId,
      // clear sources if character changed
      activeSourceIds:
        characterId === state.activeCharacterId ? state.activeSourceIds : []
    })),
  setActiveGame: (gameId) =>
    set({
      activeGameId: gameId
    }),
  setActiveSources: (sourceIds) =>
    set({
      activeSourceIds: Array.from(new Set(sourceIds))
    }),
  reset: () =>
    set({
      activeCharacterId: null,
      activeGameId: null,
      activeSourceIds: []
    })
}));
