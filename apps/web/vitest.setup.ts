import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const envPath = resolve(__dirname, "../../.env");
try {
  const envContent = readFileSync(envPath, "utf8");
  for (const line of envContent.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const [key, ...rest] = trimmed.split("=");
    if (!key) {
      continue;
    }
    const value = rest.join("=");
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
} catch (error) {
  console.warn("Failed to load .env for vitest setup", error);
}

if (!("ResizeObserver" in globalThis)) {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserver;
}

if (!(HTMLElement.prototype as HTMLElement & { scrollTo?: () => void }).scrollTo) {
  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    value: () => {},
    configurable: true
  });
}
