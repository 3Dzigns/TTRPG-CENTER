export type TailwindDarkMode =
  | "media"
  | "class"
  | false
  | [string, ...string[]]
  | {
      [key: string]: unknown;
    };

export interface TailwindConfig {
  darkMode?: TailwindDarkMode;
  content?: Array<string | { files: string | string[]; extract?: unknown }>;
  presets?: TailwindConfig[];
  plugins?: unknown[];
  theme?: Record<string, unknown>;
  corePlugins?: Record<string, unknown> | false;
  important?: boolean | string;
  prefix?: string;
  separator?: string;
  safelist?: unknown;
  future?: Record<string, unknown>;
  experimental?: Record<string, unknown>;
  [key: string]: unknown;
}

export type TailwindPreset = Partial<TailwindConfig>;

