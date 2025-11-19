import type { UserRole } from "@ttrpg-center/types";
import { create } from "zustand";

interface AuthState {
  selectedRole: UserRole | null;
  setSelectedRole: (role: UserRole) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  selectedRole: null,
  setSelectedRole: (role) => set({ selectedRole: role }),
  clear: () => set({ selectedRole: null })
}));
