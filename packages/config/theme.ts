export const themeTokens = {
  colors: {
    brand: {
      50: "#f3f5ff",
      100: "#e4e9ff",
      200: "#c7d0ff",
      300: "#9ba9ff",
      400: "#6674ff",
      500: "#4c5fff",
      600: "#3447e6",
      700: "#2334b5",
      800: "#1d2a8f",
      900: "#192472"
    },
    surface: {
      50: "#ffffff",
      100: "#f5f5f5",
      900: "#0f1116"
    },
    accent: {
      success: "#16a34a",
      warning: "#f59e0b",
      danger: "#dc2626",
      info: "#0ea5e9"
    }
  },
  radii: {
    none: "0px",
    sm: "4px",
    md: "6px",
    lg: "12px",
    full: "9999px"
  },
  spacing: {
    xs: "0.25rem",
    sm: "0.5rem",
    md: "1rem",
    lg: "1.5rem",
    xl: "2rem"
  },
  typography: {
    fontFamily: {
      sans: ["'Inter'", "system-ui", "sans-serif"],
      mono: ["'JetBrains Mono'", "monospace"]
    }
  }
} as const;

export type ThemeTokens = typeof themeTokens;
