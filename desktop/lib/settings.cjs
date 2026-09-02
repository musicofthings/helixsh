"use strict";

const fs = require("node:fs");
const path = require("node:path");

/**
 * The themes the app ships.
 *
 * `background` is the window's own background colour, which Electron paints
 * before the renderer has drawn anything. It has to match the theme's page
 * background or every launch starts with a flash of the wrong colour, so it
 * lives here rather than only in the stylesheet.
 *
 * `scheme` tells the renderer which way round the palette runs, so a "system"
 * preference can resolve to a real theme without the renderer knowing the
 * palettes.
 */
const THEMES = Object.freeze([
  Object.freeze({
    id: "helix-dark",
    label: "Helix Dark",
    scheme: "dark",
    background: "#0b1210",
  }),
  Object.freeze({
    id: "helix-light",
    label: "Helix Light",
    scheme: "light",
    background: "#f4f7f5",
  }),
  Object.freeze({
    id: "cursor-dark",
    label: "Cursor Dark",
    scheme: "dark",
    background: "#141414",
  }),
  Object.freeze({
    id: "cursor-light",
    label: "Cursor Light",
    scheme: "light",
    background: "#f8f8f8",
  }),
  Object.freeze({
    id: "paper",
    label: "Paper",
    scheme: "light",
    background: "#faf8f4",
  }),
]);

// Stored when the user wants the OS to decide. It is not a palette: the
// renderer resolves it against `prefers-color-scheme` before painting.
const SYSTEM_THEME = "system";
const DEFAULT_THEME = SYSTEM_THEME;
// What "system" resolves to in each direction.
const SYSTEM_PAIR = Object.freeze({ dark: "helix-dark", light: "cursor-light" });

const SETTINGS_FILE = "settings.json";

function isKnownTheme(id) {
  return id === SYSTEM_THEME || THEMES.some((theme) => theme.id === id);
}

/** Fall back to the default rather than letting an unknown id reach the DOM. */
function normalizeTheme(id) {
  return typeof id === "string" && isKnownTheme(id) ? id : DEFAULT_THEME;
}

/**
 * The window background to paint for a stored preference.
 *
 * "system" cannot be resolved here — the main process is asked for this before
 * the renderer exists, and Electron's own `nativeTheme` is the only thing that
 * knows the OS preference — so the caller passes what it read from there.
 */
function backgroundFor(themeId, { prefersDark = true } = {}) {
  const resolved =
    normalizeTheme(themeId) === SYSTEM_THEME
      ? SYSTEM_PAIR[prefersDark ? "dark" : "light"]
      : normalizeTheme(themeId);
  return THEMES.find((theme) => theme.id === resolved).background;
}

function settingsPath(directory) {
  return path.join(directory, SETTINGS_FILE);
}

/**
 * Read stored settings, treating anything unreadable as "no settings yet".
 *
 * A corrupt or hand-edited file must not stop the app from opening: the worst
 * outcome of ignoring it is that the user picks their theme again.
 */
function readSettings(directory) {
  let raw;
  try {
    raw = fs.readFileSync(settingsPath(directory), "utf8");
  } catch {
    return { theme: DEFAULT_THEME };
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { theme: DEFAULT_THEME };
  }
  if (!parsed || typeof parsed !== "object") return { theme: DEFAULT_THEME };
  return { theme: normalizeTheme(parsed.theme) };
}

/** Merge a patch into the stored settings and return the result. */
function writeSettings(directory, patch) {
  const merged = { ...readSettings(directory), ...patch };
  merged.theme = normalizeTheme(merged.theme);
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(settingsPath(directory), `${JSON.stringify(merged, null, 2)}\n`, "utf8");
  return merged;
}

module.exports = {
  DEFAULT_THEME,
  SYSTEM_PAIR,
  SYSTEM_THEME,
  THEMES,
  backgroundFor,
  isKnownTheme,
  normalizeTheme,
  readSettings,
  settingsPath,
  writeSettings,
};
