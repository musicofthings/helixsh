import { writable } from "svelte/store";

/**
 * Theme selection for the command shell.
 *
 * The ids match the ones the Electron runner ships, so the two surfaces read
 * as the same product. "system" is not a palette -- it resolves against
 * `prefers-color-scheme`, and keeps resolving while the app is open.
 */
export const THEMES = [
  { id: "system", label: "Match system" },
  { id: "helix-dark", label: "Helix Dark" },
  { id: "helix-light", label: "Helix Light" },
  { id: "cursor-dark", label: "Cursor Dark" },
  { id: "cursor-light", label: "Cursor Light" },
  { id: "paper", label: "Paper" },
];

const SYSTEM = "system";
const SYSTEM_PAIR = { dark: "helix-dark", light: "cursor-light" };
const STORAGE_KEY = "helixsh.theme";
const DEFAULT_CHOICE = SYSTEM;

const isKnown = (id) => THEMES.some((theme) => theme.id === id);

const darkQuery =
  typeof window === "undefined" ? null : window.matchMedia("(prefers-color-scheme: dark)");

export function resolveTheme(choice) {
  if (choice !== SYSTEM) return choice;
  return SYSTEM_PAIR[darkQuery?.matches ? "dark" : "light"];
}

function stored() {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return isKnown(value) ? value : DEFAULT_CHOICE;
  } catch {
    // Private windows and locked-down webviews throw rather than return null.
    return DEFAULT_CHOICE;
  }
}

export const theme = writable(stored());

function paint(choice) {
  document.documentElement.dataset.theme = resolveTheme(choice);
}

theme.subscribe((choice) => {
  if (typeof document === "undefined") return;
  paint(choice);
  try {
    window.localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    // A theme that does not survive a restart still beats failing to set one.
  }
});

// Only matters while the user is following the OS, but repainting a pinned
// theme is a no-op.
darkQuery?.addEventListener("change", () => {
  theme.update((choice) => {
    paint(choice);
    return choice;
  });
});
