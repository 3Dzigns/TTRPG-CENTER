import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'terminal' | 'lcars';

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'terminal',
      setTheme: (theme: Theme) => set({ theme }),
      toggleTheme: () => set({ theme: get().theme === 'terminal' ? 'lcars' : 'terminal' }),
    }),
    {
      name: 'ttrpg-theme-storage',
    }
  )
);