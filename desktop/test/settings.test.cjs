"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  DEFAULT_THEME,
  SYSTEM_PAIR,
  SYSTEM_THEME,
  THEMES,
  backgroundFor,
  normalizeTheme,
  readSettings,
  settingsPath,
  writeSettings,
} = require("../lib/settings.cjs");

function scratch() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "helixsh-settings-"));
}

test("settings default when nothing has been stored", () => {
  assert.deepEqual(readSettings(path.join(scratch(), "missing")), { theme: DEFAULT_THEME });
});

test("a corrupt settings file does not stop the app opening", () => {
  const dir = scratch();
  fs.writeFileSync(settingsPath(dir), "{ this is not json");
  assert.deepEqual(readSettings(dir), { theme: DEFAULT_THEME });
});

test("a theme the app does not ship falls back to the default", () => {
  const dir = scratch();
  fs.writeFileSync(settingsPath(dir), JSON.stringify({ theme: "../../etc/passwd" }));
  assert.equal(readSettings(dir).theme, DEFAULT_THEME);
  assert.equal(normalizeTheme("no-such-theme"), DEFAULT_THEME);
  assert.equal(normalizeTheme(undefined), DEFAULT_THEME);
});

test("a stored theme survives a round trip", () => {
  const dir = path.join(scratch(), "nested", "userData");
  assert.deepEqual(writeSettings(dir, { theme: "cursor-light" }), { theme: "cursor-light" });
  assert.equal(readSettings(dir).theme, "cursor-light");
});

test("every shipped theme has a window background to paint", () => {
  for (const theme of THEMES) {
    assert.match(theme.background, /^#[0-9a-f]{6}$/, theme.id);
    assert.equal(backgroundFor(theme.id), theme.background);
    assert.ok(["light", "dark"].includes(theme.scheme), theme.id);
  }
});

test("the system theme resolves in both directions", () => {
  const dark = THEMES.find((theme) => theme.id === SYSTEM_PAIR.dark);
  const light = THEMES.find((theme) => theme.id === SYSTEM_PAIR.light);
  assert.equal(dark.scheme, "dark");
  assert.equal(light.scheme, "light");
  assert.equal(backgroundFor(SYSTEM_THEME, { prefersDark: true }), dark.background);
  assert.equal(backgroundFor(SYSTEM_THEME, { prefersDark: false }), light.background);
});

// ── the renderer carries its own copy of the theme list ─────────────────────
//
// It has to: the switcher is markup, and theme.js runs before any IPC could
// answer. These checks are what keeps the copies from drifting apart.

const renderer = (file) =>
  fs.readFileSync(path.join(__dirname, "..", "renderer", file), "utf8");

test("the switcher offers exactly the themes the app ships", () => {
  const options = [...renderer("index.html").matchAll(/<option value="([^"]+)">/g)]
    .map((match) => match[1])
    .filter((value) => value === SYSTEM_THEME || THEMES.some((theme) => theme.id === value));
  assert.deepEqual(options, [SYSTEM_THEME, ...THEMES.map((theme) => theme.id)]);
});

test("theme.js knows the same themes as the main process", () => {
  const source = renderer("theme.js");
  const ids = JSON.parse(source.match(/const THEME_IDS = (\[[^\]]*\])/)[1].replace(/'/g, '"'));
  assert.deepEqual(ids, THEMES.map((theme) => theme.id));
  const pair = source.match(/const SYSTEM_PAIR = \{ dark: "([^"]+)", light: "([^"]+)" \}/);
  assert.equal(pair[1], SYSTEM_PAIR.dark);
  assert.equal(pair[2], SYSTEM_PAIR.light);
});

test("every theme id used in markup has a palette in the stylesheet", () => {
  const css = renderer("styles.css");
  for (const theme of THEMES) {
    assert.ok(css.includes(`[data-theme="${theme.id}"]`), `${theme.id} has no palette`);
  }
});
