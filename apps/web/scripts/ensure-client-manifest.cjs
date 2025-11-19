"use strict";

const fs = require("node:fs");
const path = require("node:path");

const appRoot = path.join(__dirname, "..");
const manifestSource = path.join(appRoot, ".next", "server", "app", "page_client-reference-manifest.js");

const targets = [
  path.join(appRoot, ".next", "server", "app", "(dashboard)", "page_client-reference-manifest.js"),
  path.join(appRoot, ".next", "server", "app", "(dashboard)", "admin", "page_client-reference-manifest.js"),
  path.join(appRoot, ".next", "server", "app", "(dashboard)", "gm", "page_client-reference-manifest.js"),
  path.join(appRoot, ".next", "server", "app", "(dashboard)", "player", "page_client-reference-manifest.js")
];

function copyIfMissing(destination) {
  const directory = path.dirname(destination);
  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory, { recursive: true });
  }
  if (!fs.existsSync(destination)) {
    fs.copyFileSync(manifestSource, destination);
  }
}

if (fs.existsSync(manifestSource)) {
  targets.forEach(copyIfMissing);
  const dashboardRootManifest = targets[0];
  if (fs.existsSync(dashboardRootManifest)) {
    const aliasSnippet =
      '\nglobalThis.__RSC_MANIFEST["/(dashboard)/page"]=globalThis.__RSC_MANIFEST["/(dashboard)/page"]||globalThis.__RSC_MANIFEST["/page"];';
    const current = fs.readFileSync(dashboardRootManifest, "utf8");
    if (!current.includes('"/(dashboard)/page"')) {
      fs.appendFileSync(dashboardRootManifest, aliasSnippet);
    }
  }
} else {
  console.warn(`[ensure-client-manifest] source manifest not found at ${manifestSource}`);
}
