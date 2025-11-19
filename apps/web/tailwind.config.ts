import type { TailwindConfig } from "../../packages/config/tailwind.types";
import tailwindPreset from "../../packages/config/tailwind.preset";

const config: TailwindConfig = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}"
  ],
  presets: [tailwindPreset],
  theme: {
    extend: {}
  },
  plugins: []
};

export default config;
