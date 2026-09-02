"use strict";

/**
 * Theme resolution, applied before the body paints.
 *
 * The stored preference arrives on the page URL rather than over IPC: IPC is a
 * round trip, and anything asynchronous here means the window paints the
 * default palette first and swaps, which a user on a light theme sees as a
 * dark flash on every launch. The main process already knows the preference
 * when it loads the file, so it passes it as `?theme=`.
 *
 * "system" is not a palette. It resolves against `prefers-color-scheme`, and
 * keeps resolving: the OS can change theme while the app is open.
 */
(() => {
  const THEME_IDS = ["helix-dark", "helix-light", "cursor-dark", "cursor-light", "paper"];
  const SYSTEM = "system";
  // What "system" means in each direction. Kept in step with
  // desktop/lib/settings.cjs by desktop/test/theme.test.cjs.
  const SYSTEM_PAIR = { dark: "helix-dark", light: "cursor-light" };
  const DEFAULT_CHOICE = SYSTEM;

  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  let choice = DEFAULT_CHOICE;

  const isKnown = (value) => value === SYSTEM || THEME_IDS.includes(value);

  function resolve(value) {
    return value === SYSTEM ? SYSTEM_PAIR[darkQuery.matches ? "dark" : "light"] : value;
  }

  function paint() {
    document.documentElement.dataset.theme = resolve(choice);
  }

  function apply(value) {
    choice = isKnown(value) ? value : DEFAULT_CHOICE;
    paint();
    return choice;
  }

  const fromUrl = new URLSearchParams(window.location.search).get("theme");
  apply(fromUrl);

  // Only matters while the user has chosen to follow the OS, but the listener
  // is cheap and `paint` is a no-op for a pinned theme.
  darkQuery.addEventListener("change", paint);

  window.helixshTheme = Object.freeze({
    DEFAULT_CHOICE,
    SYSTEM,
    SYSTEM_PAIR: Object.freeze({ ...SYSTEM_PAIR }),
    THEME_IDS: Object.freeze([...THEME_IDS]),
    apply,
    choice: () => choice,
    isKnown,
    resolve,
  });
})();
