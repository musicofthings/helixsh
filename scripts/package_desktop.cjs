"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { packager } = require("@electron/packager");

const projectRoot = path.resolve(__dirname, "..");
const outputRoot = path.join(projectRoot, "dist-desktop");

async function main() {
  const stagingRoot = fs.mkdtempSync(path.join(os.tmpdir(), "helixsh-desktop-"));
  const stagedBackend = path.join(stagingRoot, "src");
  fs.cpSync(path.join(projectRoot, "src"), stagedBackend, {
    recursive: true,
    filter: (source) =>
      !source.endsWith(".DS_Store") &&
      !source.endsWith(".pyc") &&
      !source.split(path.sep).includes("__pycache__"),
  });

  try {
    const appPaths = await packager({
      dir: projectRoot,
      name: "Helixsh",
      appBundleId: "bio.helixsh.desktop",
      appCategoryType: "public.app-category.developer-tools",
      platform: "darwin",
      arch: process.arch === "arm64" ? "arm64" : "x64",
      out: outputRoot,
      overwrite: true,
      asar: true,
      prune: true,
      extraResource: [stagedBackend],
      ignore: [
        /^\/\.git(?:\/|$)/,
        /^\/\.pytest_cache(?:\/|$)/,
        /^\/dist(?:\/|$)/,
        /^\/dist-desktop(?:\/|$)/,
        /^\/tests(?:\/|$)/,
        /^\/src(?:\/|$)/,
        /^\/desktop\/test(?:\/|$)/,
        /^\/scripts(?:\/|$)/,
        /\.DS_Store$/,
        /\.pyc$/,
        /__pycache__/,
      ],
    });
    process.stdout.write(`Built Helixsh desktop app: ${appPaths.join(", ")}\n`);
  } finally {
    fs.rmSync(stagingRoot, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
