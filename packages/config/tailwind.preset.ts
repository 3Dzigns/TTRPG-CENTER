import { themeTokens } from "./theme";
import type { TailwindPreset } from "./tailwind.types";

const preset: TailwindPreset = {
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        brand: themeTokens.colors.brand,
        surface: themeTokens.colors.surface,
        accent: themeTokens.colors.accent
      },
      borderRadius: themeTokens.radii,
      spacing: themeTokens.spacing,
      fontFamily: {
        sans: [...themeTokens.typography.fontFamily.sans],
        mono: [...themeTokens.typography.fontFamily.mono]
      }
    }
  },
  plugins: []
};

export default preset;
